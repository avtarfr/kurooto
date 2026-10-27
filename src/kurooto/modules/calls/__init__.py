"""Phone calls: talk to Kurooto like a phone call, and let it call you (reminders, check-ins, the wake-up alarm).

How it works: Kurooto deploys your own call line (a small Cloudflare Worker, free plan) and keeps one connection
to it. Your phone (the Android app, or the call page added to an iPhone's Home Screen) pairs with that line. On a
call the audio goes between your phone and Google's Gemini Live, using your free Gemini key; only tool requests
("what's due?", "add a reminder", "search my notes") come back here. If this computer is off, calls still work from
what it last sent, and anything that needs it waits until it's back.

Telegram: /call gives you a call link, /phone pairs a phone, /phones lists them, /unpair removes one.

The paired phones are also a second channel for messages (questions and approvals by default; see phone.py), and
while a call is live, nothing else rings: availability says "you're on a call" (updates wait for it too).

When Gemini Live won't take a call (Google's "503 UNAVAILABLE"), the call goes on anyway (fallback.py): Live again with
the next model (calls.live_models), then turn by turn with the phone's own speech, then as text on Telegram.
"""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

from kurooto.core import egress, layout
from kurooto.core.clock import now, parse_when
from kurooto.core.config import register_defaults
from kurooto.core.lock import Lock
from kurooto.core.state import jload, jsave
from kurooto.modules.base import Command, Incoming, Intent, Module
from kurooto.modules.calls import line, review
from kurooto.modules.calls.chat import PhoneChat
from kurooto.modules.calls.connector import Connector
from kurooto.modules.calls.fallback import LiveHealth, TextCall, VoiceTurns, live_profile
from kurooto.modules.calls.phone import PhoneApp
from kurooto.modules.calls.sessions import MAIN, Sessions
from kurooto.modules.calls.today import PhoneToday
from kurooto.modules.calls.tools import Tool, arg, clip, keyword_search, notes_index, read_note
from kurooto.modules.calls.views import PhoneViews
from kurooto.modules.drafts import wants as wants_check
from kurooto.modules.text import a_time, stale_time

register_defaults(
    "calls",
    {
        "worker": {"url": "", "name": "", "version": ""},
        "live_model": "gemini-3.8-live",
        # more Gemini Live models to try, in order, when live_model is unavailable (fallback.py); they get a plainer
        # session (tools that wait, a voice they know), and voice_by_model picks a voice per model
        "live_models": ["gemini-3.1-flash-live-preview", "gemini-2.5-flash-native-audio-latest"],
        "voice_by_model": {},
        # how calls listen and speak: "live" (Gemini Live), "phone" (the phone's own speech recognition and voice,
        # turn by turn), "auto" (Live, and the phone's speech when Live fails). voice_by_kind: per kind of call, e.g.
        # {"alarm": "phone", "checkins:evening": "live"}; kinds: a feature's id (alarm, checkins, weekly, quiz,
        # deadlines, research), "<feature>:<name>" (checkins:night), "reminder", and "outgoing" (calls you start)
        "voice_mode": "auto",
        "voice_by_kind": {},
        "turn_brain": "gemini",  # answers turn-by-turn calls here: "gemini" (your key) or "local" (Local AI models)
        "text_model": "gemini-flash-latest",  # the Gemini model for turn-by-turn calls (here, or on your call line)
        "voice": "",  # a Gemini Live voice name (e.g. "Kore"); empty = Google's default
        "persona": "",  # extra words on how to talk on calls, e.g. "be brief and a bit cheeky"
        "ntfy_server": "https://ntfy.sh",
        "ring_s": 60,  # how long a call rings before it counts as missed (a wake-up call rings 5 minutes)
        "later_min": 30,  # "Later" on a ringing call calls back after this long
        "realert_min": [3, 6],  # a call you didn't answer rings again this many minutes after the first; [] = once
        "notes_repo": "",  # owner/repo of your notes on GitHub (Notes sync), so calls can read notes while off
        "review": True,  # after every call, an AI request looks back at it: does what slipped through, keeps lessons
        "review_effort": "high",  # how hard that look back thinks (low, medium, high)
        "review_brain": "",  # which AI does the look back ("" = your main one)
        "lessons_max": 12,  # the most lessons every call is told; a new one that says the same replaces the old
        "today": True,  # the Android app's Today screen and its copy of your alarm, sealed for each phone (today.py)
        "views": False,  # Systems and the Notes map on the Android app (notes' titles, features' health; views.py)
        "views_being": True,  # the being in the app's Views (with calls.views): its readings, settings, no note text
        "views_notes": 5000,  # most notes on the phone's Notes map (best linked first); lower it on a slow phone
        "views_links": 20000,  # the most links on it (a book's "Seen in" links go first)
        # the phone app's chat (0.8.10; chat.py, sessions.py): each part on until you turn it off, unseen until used
        "chat_sessions": True,  # separate chats in the phone app, each its own AI conversation that keeps its context
        "chat_files_inline": True,  # files in the phone app's chat both ways, shown in place (photos, documents, audio)
        "chat_edit": True,  # edit (15 minutes), delete and pin your messages in the phone app's chat
        "chat_titles": "first words",  # a new chat's name: "first words" of its first message, or "ai" (a short title)
    },
)

SECRETS = ("calls.call_secret", "calls.connector_secret", "calls.ntfy_topic", "calls.ntfy_key")
ALARM_RING_S = 300  # how long the call line and the Android app ring a wake-up call (worker.js ALARM_RING_S)
ON_CALL_S = 90  # a live call checks in every few seconds; this long after the last sign of it, it's over
GEMINI_KEY = "gemini.api_key"
ASKED_WHYS = ("", "asked", "calls.own")  # a call you asked for (or an alarm, a reminder): Brain's register leaves it be
APP_LINE_SOON_MIN = 1  # a new phone app goes to the call line this soon after it's fetched
APP_LINE_BUSY_MIN = 10  # on a call, or another deploy running: looked at again this much later
APP_LINE_RETRY_MIN = 30  # a deploy that failed (offline, Cloudflare): tried again this much later
APP_LINE_TRIES = 6  # then the 05:10 line update takes it
PHONES_FRESH_S = 1800  # the health check trusts the last device list (who's connected straight to the line) this long


def check_ntfy_token(server: str, token: str) -> tuple[str, str]:
    """(the ntfy account's name, "") if the server takes this token, else ("", why not)."""
    req = urllib.request.Request(  # noqa: S310 (your ntfy server, https)
        f"{server.rstrip('/')}/v1/account", headers={"Authorization": f"Bearer {token}"}
    )
    try:
        with egress.urlopen(req, "Phone calls", timeout=20, own=True) as r:
            user = json.loads(r.read() or b"{}").get("username") or ""
    except urllib.error.HTTPError as e:
        return "", "ntfy didn't accept that token." if e.code in (401, 403) else f"ntfy answered HTTP {e.code}."
    except OSError as e:
        return "", f"Couldn't reach ntfy: {e}"[:200]
    if not user or user == "*":
        return "", "ntfy didn't take that as an account's token."
    return user, ""


class Calls(Module):
    setup_notes = (
        (
            "A free Gemini API key (calls talk through Gemini Live)",
            "dashboard → Features → Calls → Set up, or kurooto keys set gemini",
            "kurooto keys remove gemini",
        ),
        (
            "Your call line on Cloudflare (a free account), so calls ring even when this computer is off",
            "dashboard → Features → Calls → Set up",
            "Features → Calls → turn off (the line stays until you delete it on Cloudflare)",
        ),
    )
    id = "calls"
    title = "Phone calls"
    description = (
        "Call Kurooto like a phone call and let it call you (reminders, check-ins, wake-up), on your own free call "
        "line. Needs a free Gemini key and a free Cloudflare account."
    )
    privacy = (
        "Call audio goes between your phone and Google (Gemini Live, your own key); calls turn by turn use your "
        "phone's own speech recognition instead. Your call line runs on your own Cloudflare account and keeps a short "
        "brief for when this computer is off. Transcripts are kept on this computer (the call line holds them only "
        "while it's off); after each call the transcript and what the call did go to your chosen AI for the look back "
        "(calls.review)."
    )

    def __init__(self, app):
        super().__init__(app)
        self.dir = app.paths.state / "calls"
        self.connector = Connector(self)
        self.finished: dict[str, dict] = {}  # call tasks done but not yet told on the call
        self.phone = PhoneApp(self)  # messages to the phone app, and the answers that come back
        self.sessions = Sessions(self)  # the phone app's separate chats (sessions.py)
        self.chat = PhoneChat(self)  # the phone app as a chat, beside Telegram (chat.py)
        self._unsub_chat = None
        self.today = PhoneToday(self)  # the app's Today screen and its copy of the alarm (today.py)
        self._unsub_today = None
        self.views = PhoneViews(self)  # Systems and the Notes map on the app (views.py, calls.views)
        self._unsub_views = None
        self.live = LiveHealth(self)  # when Gemini Live won't take a call (fallback.py)
        self.turns = VoiceTurns(self)
        self.textcall = TextCall(self)
        # each call's tool uses, by the call's "since" ("" when the call page didn't say), for the look back after it
        # (review.py); two calls at once, or work queued while the computer was off, each keep their own
        self.tool_log: dict[str, list[dict]] = {}
        self._devices_seen: tuple[float, list[dict]] = (0.0, [])  # the last device list, and when (phones_direct)

    # ------------------------------------------------------------------------------------------ setup
    def worker_url(self) -> str:
        return ((self.setting("worker") or {}).get("url") or "").rstrip("/")

    def ready(self):
        if not self.app.secrets.get(GEMINI_KEY):
            return False, "needs your free Gemini key (from Google AI Studio)"
        if not self.worker_url() or not all(self.app.secrets.get(k) for k in SECRETS):
            return False, "needs setting up: Kurooto makes your call line on your free Cloudflare account"
        return True, ""

    def setup(self, progress=print) -> tuple[bool, str]:
        from kurooto.modules.calls import deploy

        return deploy.deploy(self.app, progress)

    def health(self):
        ok, why = self.ready()
        if not ok:
            return ok, why
        if not self.connector.connected:
            return False, "not connected to your call line right now"
        limited = self.ntfy_limited()
        if limited and not self.phones_direct():
            return False, (
                f"ntfy refused {limited} ring{'s' if limited != 1 else ''} or message{'s' if limited != 1 else ''} to "
                "your phone this week: it limits each internet address, and yours is shared (a free ntfy account is "
                "counted the same way). The Kurooto app from 0.7.0 gets them straight from your call line: update "
                "the app on your phone and let it run in the background (battery: unrestricted)"
            )
        return True, ""

    def phones_direct(self) -> bool:
        """Every paired Android phone was connected straight to the call line (0.7.0) when the devices were last
        listed (the Phone tab, the last PHONES_FRESH_S): then ntfy refusing something doesn't matter."""
        at, devs = self._devices_seen
        android = [d for d in devs if d.get("kind") == "android"]
        return time.time() - at < PHONES_FRESH_S and bool(android) and all(d.get("connected") for d in android)

    def ntfy_limited(self, days: int = 7) -> int:
        """Rings and messages ntfy refused for its rate limit (429) in the last `days`."""
        since = (now() - dt.timedelta(days=days)).isoformat()
        return sum(
            1 for e in self.app.events.tail(20000) if e.get("kind") == "calls_ntfy_limited" and e.get("ts", "") >= since
        )

    def set_ntfy_token(self, token: str) -> tuple[bool, str]:
        """Keep (or with "" clear) an ntfy account token, checked with ntfy first; the call line is then deployed
        again in the background so it publishes with it too (the dashboard's Phone tab and the setup page)."""
        token = (token or "").strip()
        if token:
            user, err = check_ntfy_token(self.setting("ntfy_server") or "https://ntfy.sh", token)
            if err:
                return False, err
            self.app.secrets.set("calls.ntfy_token", token)
            msg = f"Kept: rings are published as your ntfy account ({user})."
        else:
            self.app.secrets.delete("calls.ntfy_token")
            msg = "No ntfy token now: rings are published without one."
        self.app.events.emit("calls_ntfy_token", set=bool(token))
        from kurooto.modules.calls import deploy

        if not deploy.needs_redeploy(self.app):
            return True, msg

        def go():
            ok, why = deploy.deploy(self.app, progress=lambda line: None, unattended=True)
            self.app.events.emit("calls_line_updated", ok=ok)
            if not ok:
                self.app.notify(
                    f"Your call line couldn't take the ntfy token yet: {why} (it tries again at 05:10).",
                    kind="info",
                    why="calls.line_update",
                )

        threading.Thread(target=go, name="call-line-ntfy", daemon=True).start()
        return True, msg + " Your call line is updated with it in the background (a minute or two)."

    # ------------------------------------------------------------------------------------- lifecycle
    def start(self):
        self.action("ring", self._scheduled_ring)
        self._unpark()
        self.action("missed", self._missed)
        self.action("task_check", self._task_check)
        self.action("realert", self._realert)
        self.every("line_update", "daily 05:10", self._line_update)
        self.action("app_line", self._app_line)  # a new phone app goes to the line soon, not at 05:10
        self.app.jobs.then_actions["calls.task_done"] = self._task_done
        self.action("textcall_idle", self.textcall.idle)  # a call that went on as text (fallback.py)
        self.app.jobs.then_actions["calls.textcall_said"] = self.textcall.said
        self.app.jobs.then_actions["calls.reviewed"] = lambda job, result, payload: review.reviewed(
            self, job, result, payload
        )
        self.app.notifier.register("app", self.phone.send, self.phone.retract)  # questions etc. (phone.py)
        self.app.notifier.register("chat", self.chat.send)  # answers to what you typed in the app (chat.py)
        self.app.jobs.then_actions["calls.chat_title"] = self.sessions.titled  # calls.chat_titles = "ai"
        if self._unsub_chat is None:  # an AI request for a chat ended: "idle" (chat.py)
            from kurooto.core.events import subscribe

            self._unsub_chat = subscribe(self.chat.on_event)
        if self._unsub_today is None:  # what the Today list shows changed: the phones get it soon (today.py)
            from kurooto.core.events import subscribe

            self._unsub_today = subscribe(self.today.on_event)
        if self._unsub_views is None:  # calls.views turned on or off: the call line hears soon (views.py)
            from kurooto.core.events import subscribe

            self._unsub_views = subscribe(self.views.on_event)

    def stop(self):
        """Turned off: calls you booked are kept (not cancelled) and booked again when it's turned back on."""
        rows = [
            {"key": j.key, "at": j.next_run, "payload": j.payload}
            for j in self.app.scheduler.jobs("calls:ring:")
            if j.action == "calls.ring"
        ]
        if rows:
            jsave(self.parked_file, rows)
        super().stop()
        self.app.notifier.unregister("app")
        self.app.notifier.unregister("chat")
        if self._unsub_today is not None:
            self._unsub_today()
            self._unsub_today = None
        if self._unsub_chat is not None:
            self._unsub_chat()
            self._unsub_chat = None
        if self._unsub_views is not None:
            self._unsub_views()
            self._unsub_views = None

    @property
    def parked_file(self):
        return self.dir / "parked-calls.json"

    def _unpark(self) -> None:
        """Back on: the calls booked before it was turned off ring when they're due; one whose time passed meanwhile
        isn't rung late: you're told about it instead."""
        rows = jload(self.parked_file, []) or []
        missed = []
        for r in rows:
            if r["at"] > time.time():
                self.app.scheduler.at(
                    r["at"], "calls.ring", r.get("payload") or {}, key=r["key"], module=self.id, grace_s=900,
                    respect="none", replace=False,
                )  # fmt: skip
            else:
                missed.append(
                    f"{dt.datetime.fromtimestamp(r['at']):%a %H:%M} {(r.get('payload') or {}).get('reason', '')}"
                )
        self.parked_file.unlink(missing_ok=True)
        if missed:
            self.app.notify(
                "While Phone calls was off, these calls came due and didn't ring:\n" + "\n".join(missed),
                kind="info",
                why="calls.own",
            )

    def _line_update(self, p: dict | None = None) -> bool:
        """After Kurooto updated itself, the call line's code may be newer than what's deployed: redeploy it (in the
        background; it takes a minute or two). Skipped when updates are off."""
        from kurooto.modules.calls import deploy

        if (self.app.settings.get("updates.mode") or "night") == "off" or not deploy.needs_redeploy(self.app):
            return False

        def go():
            ok, msg = deploy.deploy(self.app, progress=lambda line: None, unattended=True)
            self.app.events.emit("calls_line_updated", ok=ok)
            if not ok:
                self.app.notify(
                    f"Your call line couldn't be updated: {msg} (calls keep working on the old version; "
                    "Settings → Features → Phone calls → Set up tries again).",
                    kind="info",
                    why="calls.line_update",
                )

        threading.Thread(target=go, name="call-line-update", daemon=True).start()
        return True

    def app_line_soon(self, tries: int = 0, minutes: float = APP_LINE_SOON_MIN, replace: bool = False) -> None:
        """Take the phone app fetched after an update to the call line in a few minutes (the pairing page's
        /kurooto.apk), instead of at the next 05:10 line update. One booking: a retry already waiting is kept."""
        self.app.scheduler.at(
            now() + dt.timedelta(minutes=minutes), "calls.app_line", {"tries": tries}, key="calls:app_line",
            module=self.id, replace=replace,
        )  # fmt: skip

    def _app_line(self, p: dict | None = None) -> str:
        """Redeploy the call line for a new phone app: never during a call or another deploy (it waits 10 minutes),
        and a failure (offline, Cloudflare) tries again in 30. One event per try; you hear only of a second failure."""
        from kurooto.modules.calls import deploy

        tries = int((p or {}).get("tries") or 0)
        if not deploy.app_behind(self.app):
            return "the call line has this phone app already"
        if self.app.availability.on_call_until() is not None or deploy.deploying():
            self.app_line_soon(tries, APP_LINE_BUSY_MIN, replace=True)
            return f"busy; trying again in {APP_LINE_BUSY_MIN} min"
        self._spawn(lambda: self._app_line_go(tries), "call-line-app")
        return "updating the call line with the new phone app"

    def _app_line_go(self, tries: int) -> None:
        from kurooto.modules.calls import deploy
        from kurooto.update import phone_app

        ok, why = deploy.deploy(self.app, progress=lambda line: None, unattended=True)
        if not ok and why == deploy.BUSY:  # another deploy started meanwhile: it may take the app; looked at again
            self.app_line_soon(tries, APP_LINE_BUSY_MIN, replace=True)
            return
        app_v = phone_app.version(self.app.paths.data)
        if ok:
            self.app.events.emit("calls_line_updated", ok=True, why="phone_app", app=app_v)
            return
        tries += 1
        self.app.events.emit("calls_line_updated", ok=False, why="phone_app", app=app_v, tries=tries, error=why[:200])
        if tries < APP_LINE_TRIES:
            self.app_line_soon(tries, APP_LINE_RETRY_MIN, replace=True)
        if tries == 2:
            self.app.notify(
                f"Your call line couldn't take the new phone app{' ' + app_v if app_v else ''}: {why[:300]} "
                "(the pairing page hands out the older app until it can; it keeps trying).",
                kind="info",
                why="calls.line_update",
            )

    def _spawn(self, fn, name: str) -> None:
        threading.Thread(target=fn, name=name, daemon=True).start()

    def _scheduled_ring(self, p: dict) -> None:
        if (p.get("late_s") or p.get("missed")) and self.worker_url():
            return  # this computer was asleep when it was due, so the call line has placed it already
        if not p.get("alarm") and self._held_call(p):
            return
        why = {k: p[k] for k in ("why", "due") if p.get(k)}  # the envelope (core/calm.py), when it was booked with one
        self.ring(p.get("reason", ""), alarm=bool(p.get("alarm")), key=p.get("key", ""), **why)

    def place(
        self,
        reason: str,
        key: str = "",
        alarm: bool = False,
        force: bool = False,
        why: str | None = None,
        due: str | None = None,
    ) -> str:
        """Call now; or, if a class, a hold, focus or the night blocks calls (and it isn't an alarm or forced), hold
        the call, place it by itself when the block ends, and tell you so. key "<module>:..." makes that module hear
        how the call went (call_outcome, call_transcript). why/due: the envelope (core/calm.py): why it calls by
        itself ("calls.own" when you asked), and a deadline's due time."""
        if not alarm and not force:
            held = self._held_call({"reason": reason, "key": key, "why": why, "due": due})
            if held:
                return held
        self.ring(reason, alarm=alarm, key=key, why=why, due=due)
        return f"Calling you now: {reason}"

    def _held_call(self, p: dict) -> str | None:
        """If calls are blocked now: schedule this one for when they're allowed, say so, and return what was said."""
        av = self.app.availability
        why, _ = av.call_block()
        if not why:
            return None
        when, _ = av.next_callable()
        key = p.get("key") or "held-" + hashlib.sha256(str(p.get("reason", "")).encode()).hexdigest()[:10]
        # the same call held twice is still one booking
        self.schedule(when, p.get("reason", ""), key=key, why=p.get("why"), due=p.get("due"))
        at = f"{when:%H:%M}" if when.date() == now().date() else f"{when:%a %H:%M}"
        text = f"Held a call until {at} ({why}): {p.get('reason', '')}"
        self.app.notify(text, kind="info", why=p.get("why") or "calls.held", due=p.get("due"))
        self.app.events.emit("call_held", reason=why, until=when.isoformat())
        return text

    async def background(self, stop):
        await self.connector.run(stop)

    # ----------------------------------------------------------------------------------------- tools
    def tools(self) -> list[Tool]:
        from kurooto.core.tools import sync_tools  # sync_status, shared with unattended AI runs

        out = self._own_tools() + self.app.ask.call_tools() + sync_tools(self.app)  # + answer_question/_approval
        for m in self.app.enabled():
            if m.id != self.id and hasattr(m, "call_tools"):
                try:
                    out += m.call_tools()
                except Exception as e:
                    self.app.events.emit("calls_tools_failed", module=m.id, error=str(e)[:200])
        return out

    def _own_tools(self, live: bool = True) -> list[Tool]:
        on = self.app.is_on
        t = [
            Tool(
                "pending_items",
                "What needs their attention now: deadlines soon, today's classes and check-ins, scheduled calls, "
                "open questions. Call it at the start of every call.",
                lambda a: self.pending(),
                offline="brief",
                hint="At the start of every call, call pending_items and bring up what matters, briefly.",
            ),
            Tool(
                "send_message",
                "Send them a message on their chat (Telegram, or the phone app's): something they asked to have in "
                "writing, a list, a link, a summary of what was decided. Never say you'll send something without "
                "calling this.",
                lambda a: self._tool_message(a),
                {"text": arg("the message, plain text")},
                ("text",),
                offline="queue",
                hint="When they say 'send it on Telegram' or 'tell me on Telegram', call send_message (or send_file "
                "for a file); never just promise it.",
            ),
            Tool(
                "search_notes",
                "Search their notes (courses, plans, journal, anything they wrote)"
                + (" by meaning, through their notes brain: a whole question works." if on("gbrain") else "."),
                self._search,
                {"query": arg("what to look for, in plain words")},
                ("query",),
                hint="Use search_notes for anything about their notes, plans or work, and read_note to open one. "
                "Never invent what their notes say; if nothing is found, say so.",
            ),
            Tool(
                "read_note",
                "Read one note by its slug (from search_notes), e.g. courses/linear-algebra.",
                self._read,
                {"slug": arg()},
                ("slug",),
            ),
            Tool(
                "schedule_call",
                "Call them later about something new (a reminder call). To have THIS call later (a check-in), use "
                "change_checkin instead; used during a check-in, this moves the check-in anyway.",
                lambda a: self._schedule_tool(a, live),
                {"when": arg('e.g. "17:30", "tomorrow 7:00", "in 20 minutes"'), "reason": arg("what the call is for")},
                ("when", "reason"),
                offline="queue",
                hint="schedule_call calls them back later; hold_calls stops calls until a time.",
                guarded="call.place",
            ),
            Tool(
                "call_now",
                "Call their phone right now (rings their phone immediately).",
                lambda a: self.place(str(a.get("reason") or "you asked me to call"), force=True, why="calls.own"),
                {"reason": arg("what the call is for, optional")},
                (),
                hint="Use call_now to ring their phone immediately.",
                guarded="call.place",
            ),
            Tool(
                "hold_calls",
                'No calls until a time ("18:00", "2h"); "off" lifts the hold.',
                self._hold,
                {"until": arg()},
                ("until",),
                offline="queue",
            ),
        ]
        if on("chat"):
            t.append(
                Tool(
                    "run_task",
                    "Hand a job to the AI on their computer (writing, planning, filing notes, long answers). It runs "
                    "in the background, 20 s to a few minutes; the result arrives later as a [Task finished] message.",
                    self._run_task,
                    {"request": arg("the full request, in their words plus any detail from the call")},
                    ("request",),
                    offline="queue",
                    hint="Use run_task for anything that needs real work: say it's started and keep talking; when a "
                    "[Task finished] message arrives, tell them the result in a sentence or two.",
                )
            )
        return t

    def agent_tools(self) -> list[Tool]:
        """What unattended AI requests may do with calls: call back later, hold calls (core/tools.py)."""
        return [t for t in self._own_tools(live=False) if t.name in ("schedule_call", "hold_calls")]

    def run_tool(self, name: str, args: dict, since: str = ""):
        tool = next((t for t in self.tools() if t.name == name), None)
        if not tool:
            return f"There's no {name} tool (that feature may be off)."
        self.app.events.emit("calls_tool", name=name)
        if name == "search_notes":  # what you look up, for Dreaming's curious line (modules/curious.py)
            from kurooto.modules import curious

            curious.searched(self.app, (args or {}).get("query", ""))
        keep = getattr(self.app, "keep", None)  # what you use of each feature (core/keep.py)
        if keep is not None:
            keep.used(keep.tool_owner(name), "tool")
        try:
            out = tool.run(args or {})
        except Exception as e:
            out = f"That failed: {type(e).__name__}: {e}"[:300]
        log = self.tool_log.setdefault(str(since or ""), [])
        log[:] = [*log[-59:], {"name": name, "args": str(args or {})[:300], "result": str(out)[:300]}]
        for old in list(self.tool_log)[:-10]:  # calls that never sent a transcript don't pile up
            self.tool_log.pop(old, None)
        return out

    def _tool_message(self, a: dict) -> str:
        text = str(a.get("text") or "").strip()[:3500]
        if not text:
            return "Nothing to send."
        self.app.notify(text, kind="result", title="From your call", why="calls.own")
        return "Sent on their chat."

    def _zone(self) -> str:
        from kurooto.core import zones

        return zones.canonical(self.app.settings.get("you.timezone")) or "this computer's time zone"

    def pending(self) -> dict:
        out: dict = {"now": f"{now():%A %d %B, %H:%M}, their local time ({self._zone()})"}
        for m in self.app.enabled():
            if hasattr(m, "call_brief"):
                try:
                    out.update(m.call_brief() or {})
                except Exception as e:
                    self.app.events.emit("calls_brief_failed", module=m.id, error=str(e)[:200])
        try:  # one part failing never hurts the call: the rest of the brief still goes
            out.update(self.app.ask.call_brief())  # open questions and approvals for you (core/ask.py)
        except Exception as e:
            self.app.events.emit("calls_brief_failed", module="ask", error=str(e)[:200])
        try:  # what you're in the middle of and what was said since yesterday, within its budget (core/assembler.py)
            from kurooto.core import assembler

            out.update(assembler.call_brief(self.app))
        except Exception as e:
            self.app.events.emit("calls_brief_failed", module="memory", error=str(e)[:200])
        try:  # (Brain, stage 08) a call starts from the same life story as every other request (mind/story.py)
            from kurooto.mind import story

            tale = story.prompt(self.app)
            if tale:
                out["story"] = tale
        except Exception as e:
            self.app.events.emit("calls_brief_failed", module="story", error=str(e)[:200])
        try:  # (Brain 0.8.14, mind.register) a call it placed itself opens as its register says; one you asked for not
            from kurooto.mind import register

            cur = self.live_call()
            asked = cur is None or str(cur.get("why") or "") in ASKED_WHYS
            line = register.opener(self.app, asked=asked)
            if line:
                out["opener"] = line
        except Exception as e:
            self.app.events.emit("calls_brief_failed", module="register", error=str(e)[:200])
        upcoming = [f"{dt.datetime.fromtimestamp(c['at']):%H:%M} {c['reason']}" for c in self.schedule_list()[:5]]
        if upcoming:
            out["calls_planned"] = upcoming
        return out if len(out) > 1 else {**out, "note": "nothing needs attention right now"}

    def _search(self, a: dict):
        q = str(a.get("query", ""))
        gb = self.app.modules.get("gbrain")
        if gb and self.app.is_on("gbrain"):
            found = gb.search(q, n=6)
            if found:
                return clip(found, 3500)
        hits = keyword_search(self.app.workspace, q)
        return {"hits": hits} if hits else "Nothing found in the notes."

    def _read(self, a: dict):
        text = read_note(self.app.workspace, a.get("slug", ""))
        return clip(text, 6000) if text is not None else f'No note "{a.get("slug", "")}".'

    def _schedule_tool(self, a: dict, live: bool = True) -> str:
        try:
            at = parse_when(str(a.get("when", "")))
        except ValueError:
            return f"I couldn't read the time {a.get('when')!r}."
        reason = str(a.get("reason") or "").strip()
        cur = self.live_call() if live else None
        if cur and cur.get("key") and self._same_call(reason, cur["reason"]):
            # "call me back in an hour" during a check-in: the same check-in later, with its steps, not a new call
            mid = cur["key"].split(":")[0]
            m = self.app.modules.get(mid)
            if m and self.app.is_on(mid) and hasattr(m, "call_reschedule"):
                out = m.call_reschedule(cur["key"], at)
                if out:
                    return out
            return self.schedule(at, cur["reason"], key=cur["key"], why="calls.own")
        return self.schedule(at, reason or "a reminder", why="calls.own")

    def busy_with(self, key: str = "") -> str:
        """Why a new call of Kurooto's own shouldn't ring now: "a call is going on" or "a call is ringing" (one rang
        within calls.ring_s and wasn't answered, missed or declined yet); "" when the line is free. A call with this
        key (the same check-in, ringing again) replaces its own ring: that isn't a second call."""
        live = self.live_call()
        if live is not None and not (key and live.get("key") == key):
            return "a call is going on"
        t = time.time()
        wait = float(self.setting("ring_s") or 60) + 20
        for r in (jload(self.dir / "rings.json", {}) or {}).values():
            if (
                isinstance(r, dict)
                and r.get("state") == "ringing"
                and not r.get("alarm")
                and not (key and r.get("key") == key)
                and t - float(r.get("at") or 0) < wait
            ):
                return "a call is ringing"
        return ""

    def live_call(self) -> dict | None:
        """The call going on now, if Kurooto placed it: {"key", "reason"} (for at most two hours)."""
        cur = jload(self.dir / "live.json", {}) or {}
        return cur if cur.get("reason") and time.time() - float(cur.get("at") or 0) < 7200 else None

    @staticmethod
    def _same_call(reason: str, live_reason: str) -> bool:
        """Is "call me later" about the call going on (no new topic), rather than a new reminder call?"""
        if not reason or re.search(
            r"check.?in|debrief|night call|evening call|wake.?up|review|call (?:me )?back|callback|continue|finish|"
            r"the rest|this call|same call|again|later|postpone|reminder call",
            reason,
            re.I,
        ):
            return True
        words = lambda t: {w for w in re.findall(r"[a-z]{4,}", t.lower())}  # noqa: E731
        return bool(words(reason) & words(live_reason))

    def _hold(self, a: dict) -> str:
        until = str(a.get("until", "")).strip()
        if re.fullmatch(r"(?i)off|none|lift|stop", until):
            self.app.availability.set_quiet(None)
            return "Calls are allowed again."
        try:
            when = parse_when(until)
        except ValueError:
            return f"I couldn't read {until!r}."
        self.app.availability.set_quiet(when, reason="you asked on a call")
        return f"No calls until {when:%H:%M}."

    # ----------------------------------------------------------------------------------- call tasks
    def _run_task(self, a: dict) -> dict:
        req = str(a.get("request", "")).strip()
        jid = self.app.jobs.submit(req, title=f"From a call: {req[:60]}", quiet=True, then="calls.task_done")
        return {"task_id": jid, "status": "started", "note": "Say it's running; the result comes as [Task finished]."}

    def _task_done(self, job, result, payload) -> None:
        text = result.text if result.ok else (result.detail or "it failed")
        self.finished[job.id] = {
            "id": job.id,
            "request": job.prompt[:300],
            "status": "done" if result.ok else "failed",
            "result": clip(text, 1500),
            "full": text,
            "fetched": False,
        }
        self.app.scheduler.at(
            time.time() + 60, "calls.task_check", {"job": job.id}, key=f"calls:task:{job.id}", module=self.id
        )

    def _task_check(self, p: dict) -> None:
        """No call picked the result up within a minute (the call ended): send it to Telegram instead."""
        t = self.finished.pop(p.get("job", ""), None)
        if t and not t["fetched"]:
            self.app.notify(f"From your call: {t['request'][:80]}\n\n{t['full'][:3500]}", kind="result", why="asked")

    # ---------------------------------------------------------------------------------------- ringing
    def schedule(
        self,
        at: dt.datetime,
        reason: str,
        key: str | None = None,
        alarm: bool = False,
        why: str | None = None,
        due: str | None = None,
    ) -> str:
        """Book a call. why/due: the envelope (core/calm.py), kept with the booking for when it rings."""
        key = key or uuid.uuid4().hex[:8]
        self.app.scheduler.at(
            at,
            "calls.ring",
            {"reason": reason, "alarm": alarm, "key": key, **{k: v for k, v in (("why", why), ("due", due)) if v}},
            key=f"calls:ring:{key}",
            module=self.id,
            grace_s=900,
            respect="none",  # a no-call time is checked when it's due, so you can be told the call is held
        )
        self.connector.poke()
        self.app.events.emit("call_scheduled", at=at.isoformat())
        return f"I'll call you {at:%a %d %b at %H:%M}: {reason}"

    def schedule_list(self) -> list[dict]:
        """Calls due in the next day, for the call line to place itself if this computer is off then."""
        horizon = time.time() + 86400
        out = [
            {
                "at": int(j.next_run),
                "reason": j.payload.get("reason", ""),
                "alarm": bool(j.payload.get("alarm")),
                "key": j.payload.get("key", ""),
            }
            for j in self.app.scheduler.jobs("calls:ring:")
            if j.next_run <= horizon
        ]
        for m in self.app.enabled():
            if hasattr(m, "call_schedule"):
                try:
                    out += [c for c in m.call_schedule() if c["at"] <= horizon]
                except Exception as e:
                    self.app.events.emit("calls_schedule_failed", module=m.id, error=str(e)[:200])
        for c in out:  # how each call listens, for the call line to ring with (voice_mode, voice_by_kind)
            c["voice"] = self.voice_for(c.get("key", ""))
        return sorted(out, key=lambda c: c["at"])[:30]

    def link(self, reason: str = "", hours: float = 2, since: str = "", voice: str = "") -> str:
        q = urllib.parse.urlencode({k: v for k, v in (("p", reason), ("s", since), ("v", voice)) if v})
        t = line.ticket(self.app.secrets.get("calls.call_secret") or "", hours)
        return f"{self.worker_url()}/{'?' + q if q else ''}#{t}"

    def send_phones(self, fields: dict) -> bool:
        """A message for the Android app when the call line's WebSocket is down (0.7.0): handed to the line over HTTPS
        (`POST /send` with the connector secret), which sends it down the phones' own connections (and ntfy for a
        phone it hasn't heard from); only when the line can't be reached, or is older than 0.7.0, or had no way to
        the phone, does this computer publish to ntfy itself. True when a phone got it."""
        got = self._via_line(fields)
        if got is not None and (got.get("android") or not got.get("phones")):
            return bool(got.get("android"))
        return self.publish_ntfy(fields)

    def _via_line(self, fields: dict) -> dict | None:
        """The line's answer to /send ({ok, android, phones}), or None (unreachable, refused, or a line from before
        0.7.0, which doesn't know /send)."""
        url, secret = self.worker_url(), self.app.secrets.get("calls.connector_secret")
        if not url or not secret:
            return None
        body = json.dumps({"fields": fields, "assistant": self.app.name}).encode()
        req = urllib.request.Request(  # noqa: S310 (your own call line, https)
            f"{url}/send",
            data=body,
            headers={"Content-Type": "application/json", "x-connector-secret": secret},
            method="POST",
        )
        try:
            with egress.urlopen(req, "Phone calls", timeout=10, own=True) as r:
                got = json.loads(r.read() or b"{}")
        except Exception as e:
            self.app.events.emit("calls_line_send_failed", error=str(e)[:200])
            return None
        return got if isinstance(got, dict) and got.get("ok") else None

    def publish_ntfy(self, fields: dict) -> bool:
        """Publish an encrypted k1 payload directly to ntfy from this computer: the last resort (send_phones). ntfy
        limits each internet address, and a free ntfy account is counted by address too, so on a shared network
        (a campus) this can be refused (429); only a paid ntfy account's token (`kurooto ntfy-token`) is counted
        apart. A token ntfy refuses falls back to publishing without."""
        topic = self.app.secrets.get("calls.ntfy_topic")
        key = self.app.secrets.get("calls.ntfy_key")
        server = (self.setting("ntfy_server") or "https://ntfy.sh").rstrip("/")
        if not topic or not key:
            return False
        token = self.app.secrets.get("calls.ntfy_token") or ""
        try:
            sealed = line.seal_k1(key, json.dumps(fields))
            body = json.dumps(
                {"topic": topic, "message": sealed, "priority": fields.get("priority", 3), "tags": ["k1"]}
            ).encode()
            for auth in [token, ""] if token else [""]:
                headers = {"Content-Type": "application/json", **({"Authorization": f"Bearer {auth}"} if auth else {})}
                req = urllib.request.Request(  # noqa: S310
                    f"{server}/",
                    data=body,
                    headers=headers,
                    method="POST",
                )
                try:
                    with egress.urlopen(req, "Phone calls", timeout=10, own=True) as r:
                        return r.status in (200, 201, 204)
                except urllib.error.HTTPError as e:
                    if not (auth and e.code in (401, 403)):
                        raise
                    self.app.events.emit("calls_ntfy_token_refused", code=e.code)
            return False
        except Exception as e:
            if isinstance(e, urllib.error.HTTPError) and e.code == 429:
                self.app.events.emit("calls_ntfy_limited")  # the health check suggests a token (ntfy_limited)
            self.app.events.emit("calls_ntfy_publish_failed", error=str(e)[:200])
            return False

    def ring(
        self,
        reason: str,
        alarm: bool = False,
        key: str = "",
        buttons: list | None = None,
        why: str | None = None,
        due: str | None = None,
    ) -> str:
        """Ring your paired phones now (and say so on Telegram, with a link to answer from anywhere). `buttons`: more
        buttons for that Telegram message, e.g. [("Tomorrow morning", "chk:night:defer")]. why/due: the envelope
        (core/calm.py). Past the day's calls (notify.calm.calls) it doesn't ring: its feature hears "held", or it
        waits in the evening bundle with a call link; then "" is returned."""
        why = why or ("alarm.ring" if alarm else None)
        calm = getattr(self.app, "calm", None)
        if calm is not None and not calm.call_ok(why, key=key, alarm=alarm, due=due):
            if not self._tell_owner_module({"key": key, "reason": reason}, "held"):
                n = calm.limit("calls", 1)
                calm.hold(
                    f"A call that waited ({n} a day comes by itself): {reason}",
                    why,
                    kind="info",
                    buttons=[[("Call now", {"url": self.link(reason, hours=26)})]],
                )
            self.app.events.emit("call_not_placed", key=key)
            return ""
        from kurooto.mind import gate  # Brain's gate (mind/gate.py): the first 15 minutes after waking, a muted kind

        # a call Kurooto starts by itself (a check-in, a deadline nudge: it has a reason of its own) waits while
        # another is going on or ringing (0.7.3), or while Brain's gate says wait; an alarm always rings, and a call you
        # asked for goes through
        automatic = bool(why) and why not in ("calls.own", "alarm.ring")
        verdict = gate.check_call(self.app, why or "", asked=why == "calls.own", alarm=alarm)
        busy = self.busy_with(key) if automatic and not alarm else ""
        if automatic and not alarm and (verdict != "ring" or busy):  # it waits: the owning feature hears "held"
            self.app.events.emit(
                "call_not_placed",
                key=key,
                **({"gate": verdict} if verdict != "ring" else {}),
                **({"busy": busy} if busy else {}),
            )
            self._tell_owner_module({"key": key, "reason": reason}, "held")
            return ""
        since = str(int(time.time()))
        rings = jload(self.dir / "rings.json", {}) or {}
        while since in rings:  # two calls in the same second (a repeat ring right after another call)
            since = str(int(since) + 1)
        rings[since] = {"reason": reason, "alarm": alarm, "key": key, "at": time.time(), "state": "ringing"}
        rings[since].update({k: v for k, v in (("why", why), ("due", due)) if v})
        if buttons:
            rings[since]["buttons"] = [list(b) for b in buttons]
        jsave(self.dir / "rings.json", dict(list(rings.items())[-100:]))
        voice = self.voice_for(key)
        push = {
            "title": "Wake-up call" if alarm else "Incoming call",
            "message": str(reason)[:300],
            "priority": 5,
            "tags": ["call", f"since-{since}"] + (["alarm"] if alarm else []),
            "click": self.link(reason, since=since, voice=voice),
            "time": int(time.time()),
            "assistant": self.app.name,
        }
        sent = self.connector.admin_later(
            "ring",
            then=lambda res: self._ring_fallback(push, res),
            reason=reason,
            alarm=alarm,
            since=since,
            key=key,
            assistant=self.app.name,
            voice=voice,
        )
        if not sent:  # the line's WebSocket is down: handed to it over HTTPS, else ntfy from here
            self.send_phones(push)
        extra = [tuple(b) for b in buttons or []]
        # a label over 10 characters ("Tomorrow morning") is cut off in a row of three: it gets a row of its own (0.7.4)
        answer = [
            [
                ("Answer", {"url": self.link(reason, since=since, voice=voice)}),
                *[b for b in extra if len(str(b[0])) <= 10],
            ],
            *[[b] for b in extra if len(str(b[0])) > 10],
        ]
        if sent:  # the phone rings; Telegram just keeps a quiet record with a link
            text = f"{'Wake-up call' if alarm else 'Calling you'}: {reason}"
            self.app.notify(text, kind="call", buttons=answer, why=why)
        else:
            self.app.notify(
                f"I tried to call you, but your call line isn't connected. {reason}",
                kind="reminder",
                buttons=answer,
                urgent=True,
                why=why or "calls.no_line",
            )
        self.app.scheduler.at(  # the call line and the app ring an alarm for ALARM_RING_S, other calls for ring_s
            time.time() + (ALARM_RING_S if alarm else (self.setting("ring_s") or 60)) + 30,
            "calls.missed",
            {"since": since},
            key=f"calls:missed:{since}",
            module=self.id,
        )
        self.app.events.emit("call_rang", alarm=alarm, key=key, line=sent)
        self.connector.poke()  # the call line's copy of the schedule no longer has this one
        return since

    def _ring_fallback(self, push: dict, res: dict | None) -> None:
        """The call line's answer to "ring": it rings the Android app itself ("android": true: on the phone's own
        connection or ntfy), so this computer publishes only when it didn't (an error, no answer, or neither way
        worked): one ring, not two. A line from 0.7.0 also says how many Android phones are paired ("phones"):
        with none, nothing is published."""
        res = res or {}
        if not res.get("android") and res.get("phones", 1):
            self.publish_ntfy(push)

    def _ring_state(self, since: str, state: str) -> dict | None:
        with Lock(self.app.paths.state, "calls-rings"):
            rings = jload(self.dir / "rings.json", {}) or {}
            r = rings.get(since)
            if r:
                r["state"] = state
                jsave(self.dir / "rings.json", rings)
            return r

    def _missed(self, p: dict) -> None:
        r = (jload(self.dir / "rings.json", {}) or {}).get(p.get("since", ""))
        if not r or r["state"] != "ringing":
            return
        self._ring_state(p["since"], "missed")
        if not self.connector.admin_later("stop-ring", since=p["since"]):  # the line stops the app's ring itself
            self.send_phones(
                {"title": "stop", "message": "", "tags": ["stop", f"since-{p['since']}"], "time": int(time.time())}
            )
        if not self._realert_later(p["since"], r):
            self._missed_for_good(p["since"], r)

    def _missed_for_good(self, since: str, r: dict) -> None:
        self.app.notify(
            f"Missed call: {r['reason']}",
            kind="info",
            buttons=[
                [
                    ("Call back", {"url": self.link(r["reason"], voice=self.voice_for(r.get("key", "")))}),
                    ("In 30 min", f"call:{since}:later"),
                ]
            ],
            why=r.get("why"),
            due=r.get("due"),
        )
        self.app.events.emit("call_missed", key=r.get("key", ""))
        self._tell_owner_module(r, "missed")

    def _chain(self, first: str) -> list[dict]:
        rings = jload(self.dir / "rings.json", {}) or {}
        return [r for s, r in rings.items() if s == first or r.get("first") == first]

    def _realert_later(self, since: str, r: dict) -> bool:
        """An unanswered call (not the alarm, which repeats by itself) rings again at +3 and +6 minutes (realert_min)
        unless calls are blocked by then. False when there are no more repeats: it's a missed call."""
        steps = [] if r.get("alarm") else list(self.setting("realert_min") or [])
        n, first = int(r.get("again", 0)), r.get("first") or since
        if n >= len(steps) or self.app.availability.call_block()[0]:
            return False
        try:
            at = max(float(r.get("first_at") or r["at"]) + float(steps[n]) * 60, time.time() + 5)
        except (TypeError, ValueError):
            return False
        self.app.scheduler.at(at, "calls.realert", {"since": since}, key=f"calls:realert:{first}", module=self.id)
        return True

    def _realert(self, p: dict) -> None:
        since = p.get("since", "")
        r = (jload(self.dir / "rings.json", {}) or {}).get(since)
        if not r or r["state"] != "missed":
            return
        first = r.get("first") or since
        if any(x.get("state") not in ("missed", "ringing", "realerted") for x in self._chain(first)):
            return  # answered or put off from another of its rings
        if self.app.availability.call_block()[0]:
            self._missed_for_good(since, r)
            return
        new = self.ring(
            r["reason"], alarm=False, key=r.get("key", ""), buttons=r.get("buttons"), why=r.get("why"), due=r.get("due")
        )
        with Lock(self.app.paths.state, "calls-rings"):
            rings = jload(self.dir / "rings.json", {}) or {}
            if new in rings:
                rings[new].update(again=int(r.get("again", 0)) + 1, first=first, first_at=r.get("first_at") or r["at"])
            if since in rings and since != new:
                rings[since]["state"] = "realerted"
            jsave(self.dir / "rings.json", rings)
        self.app.events.emit("call_realert", n=int(r.get("again", 0)) + 1, key=r.get("key", ""))

    def _tell_owner_module(self, ring: dict, outcome: str) -> bool:
        """A check-in or alarm call was answered, missed or put off: its feature hears about it. True if that
        feature took care of what happens next (e.g. the alarm snoozes itself)."""
        mid = (ring.get("key") or "").split(":")[0]
        m = self.app.modules.get(mid)
        if m and self.app.is_on(mid) and hasattr(m, "call_outcome"):
            return bool(m.call_outcome(ring["key"], outcome))
        return False

    def callbacks(self):
        return {"call": self._button, "callchat": self.textcall.button, "callx": self._cancel_button}

    def replies(self):
        return {"callchat": self.textcall.reply}  # a call that went on as text messages (fallback.py)

    def _cancel_button(self, ref: str, act: str) -> str:
        return "Cancelled." if self.cancel_booked(ref.replace("|", ":")) else "Already gone."

    def cancel_booked(self, key: str) -> bool:
        """Take a booked call off (and off the call line, so it doesn't ring while this computer is off)."""
        gone = self.app.scheduler.cancel(f"calls:ring:{key}")
        if gone:
            self.connector.poke()
            self.app.events.emit("call_cancelled", via="intent")
        return gone

    def booked(self) -> list:
        """Calls booked for later ("call me at 5", held calls, ones the AI booked), soonest first. Check-ins and the
        alarm have their own commands, so they aren't here."""
        return [
            j
            for j in self.app.scheduler.jobs("calls:ring:")
            if not j.payload.get("alarm") and not str(j.payload.get("key", "")).startswith("checkins:")
        ]

    def cancel_by_words(self, msg: Incoming, sl: dict) -> str:
        """ "cancel that call", "cancel the 12:00 call": the one booked call it can mean goes; otherwise the list,
        each with a Cancel button and its key (for `kurooto call --cancel KEY` in a terminal)."""
        booked = self.booked()
        pick, tm = booked, sl.get("time")
        if tm:
            h, mi = map(int, tm.split(":"))
            at = [dt.datetime.fromtimestamp(j.next_run) for j in pick]
            pick = [j for j, w in zip(pick, at, strict=True) if w.minute == mi and w.hour % 12 == h % 12]  # am or pm
        if sl.get("tomorrow"):
            day = now().date() + dt.timedelta(days=1)
            pick = [j for j in pick if dt.datetime.fromtimestamp(j.next_run).date() == day]
        if len(pick) == 1:
            j = pick[0]
            self.cancel_booked(j.key.removeprefix("calls:ring:"))
            return f"Cancelled the {dt.datetime.fromtimestamp(j.next_run):%a %H:%M} call: {j.payload.get('reason', '')}"
        if not booked:
            return "No calls booked. (Check-ins and the alarm: /checkins and /alarm.)"
        msg.reply(
            (f"No booked call at {sl.get('said') or tm}." if tm and not pick else "Which one?") + " Booked calls:"
        )
        for j in booked[:10]:
            key = j.key.removeprefix("calls:ring:")
            msg.reply(
                f"{dt.datetime.fromtimestamp(j.next_run):%a %d %b %H:%M}  {key}  {j.payload.get('reason', '')[:80]}",
                buttons=[[("Cancel", f"callx:{key.replace(':', '|')}:x")]],
            )
        return 'Or say "cancel the 12:00 call" (in a terminal: kurooto call --cancel KEY).'

    def _button(self, since: str, act: str) -> str:
        r = (jload(self.dir / "rings.json", {}) or {}).get(since)
        if not r:
            return "That call is gone."
        if act == "later":
            at = now() + dt.timedelta(minutes=self.setting("later_min") or 30)
            self.schedule(
                at,
                r["reason"],
                key=r.get("key") or None,
                alarm=r.get("alarm", False),
                why=r.get("why"),
                due=r.get("due"),
            )
            return f"I'll call again at {at:%H:%M}."
        return "OK."

    # ---------------------------------------------------------------------------- from the call line
    def on_event(self, m: dict) -> None:
        name = m.get("name")
        if name == "call_started":
            self.on_call(m.get("at"))
            self.app.events.emit(
                "call_answered", via=m.get("via"), offline=bool(m.get("offline")), layer=m.get("layer") or "live"
            )
            r = self._ring_state(m.get("since", ""), "answered") if m.get("since") else None
            jsave(
                self.dir / "live.json",
                {"key": r.get("key", ""), "reason": r["reason"], "at": time.time(), "why": r.get("why") or ""}
                if r
                else {},
            )
            if r:
                self.app.scheduler.cancel(f"calls:missed:{m['since']}")
                self.app.scheduler.cancel(f"calls:realert:{r.get('first') or m['since']}")
                self._tell_owner_module(r, "answered")
        elif name == "ring_reply":
            since, act = m.get("since", ""), m.get("action", "")
            r = self._ring_state(since, act)
            self.app.scheduler.cancel(f"calls:missed:{since}")
            self.app.scheduler.cancel(f"calls:realert:{(r or {}).get('first') or since}")
            if r and not self._tell_owner_module(r, act) and act == "later":
                self._button(since, "later")
            self.app.events.emit("call_" + (act or "reply"))
        elif name == "device_paired":
            self.app.notify(
                f"A device was paired with your call line: {m.get('device_name')} ({m.get('kind')}). If that wasn't "
                "you, remove it with /phones.",
                kind="info",
                why="calls.device_paired",
            )
            self.app.events.emit("calls_device_paired", kind=m.get("kind"))
        elif name == "shortcut_made":  # a phone made a Tell Kurooto link (public/shortcut.js)
            self.app.notify(
                f"A Tell Kurooto link was made on {m.get('device_name') or 'a paired phone'}: its Shortcut can send "
                "you messages as that phone. If that wasn't you, revoke it on the dashboard (Phone).",
                kind="info",
                why="calls.shortcut_made",
            )
            self.app.events.emit("calls_shortcut_made")
        elif name == "rang_offline":
            self.app.events.emit("call_rang_offline", key=m.get("key", ""))
            self.app.notify(
                f"While this computer was off, your call line called you: {m.get('reason') or 'a call'}",
                kind="info",
                why="calls.rang_offline",
            )
        elif name in ("sealed_sent", "sealed_failed", "device_key"):  # reminders with the lid shut (lidsafe.py)
            if name == "device_key":  # a phone gave its key: its Today list can be sealed for it now (today.py)
                self.today.poke()
            ls = self.app.modules.get("lidsafe")
            if ls is not None and self.app.is_on("lidsafe"):
                ls.on_line_event(m)
        elif name in ("live_failed", "live_recovered", "call_fallback"):  # Gemini Live wouldn't (fallback.py)
            self.live.record(name, m)
        elif name == "text_call":  # a call handed to Telegram while this computer was off
            self.textcall.start_late(m)
        elif name == "views_watch":  # the phone app has Systems open: fresh copies while it watches (views.py)
            self.views.watch(m)

    def on_queue(self, items: list[dict]) -> None:
        """What waited on the call line while this computer was off, all at once (a call line from before 0.5.16;
        newer ones hand it over one item at a time: Connector._drainer)."""
        tools = 0
        for it in items:
            self.take_queued(it)
            tools += it.get("kind") == "tool"
        self.queued_tools_done(tools)

    def take_queued(self, it: dict) -> tuple[int, str]:
        """One thing that waited on the call line: what you asked for on a call while this computer was off (a tool,
        a transcript, an event), or what you did on your phone (the phone outbox: an answer, a chat message, a part
        of a shared file). Returns its status and a short note for the phone."""
        kind = it.get("kind")
        try:
            if kind == "tool":
                self.run_tool(it.get("name", ""), it.get("args") or {}, str(it.get("since") or ""))
            elif kind == "transcript":
                self._transcript(json.loads(it.get("body") or "{}"))
            elif kind == "event":
                self.on_event(it)
            elif kind == "answer":  # answered on a phone while this computer was off
                status, out = self.phone.answer(it.get("body") or {})
                if status == 200 and out.get("note"):
                    self.app.notify(f"Your answer from the phone: {out['note']}", kind="info", why="asked")
                return status, str(out.get("note") or "")
            elif kind == "chat":  # typed in the app's chat (chat.py); the being's requests aren't done late
                status, out = self.chat.take(it.get("body") or {}, queued=True)
                return status, str(out.get("note") or "")
            elif kind == "upload":  # a part of a file shared from the phone
                q = urllib.parse.parse_qs(urllib.parse.urlsplit(str(it.get("search") or "")).query)
                status, out = self._upload(q, base64.b64decode(it.get("body_b64") or ""))
                return status, str(out.get("saved") or out.get("error") or "")
            else:
                return 400, "unknown"
            return 200, ""
        except Exception as e:
            self.app.events.emit("calls_queue_failed", error=str(e)[:200])
            return 500, f"{type(e).__name__}: {e}"[:200]

    def queued_tools_done(self, n: int) -> None:
        if n:
            self.app.notify(
                f"Done what you asked for on a call while the computer was off ({n} item(s)).",
                kind="info",
                why="asked",
            )

    def handle_request(self, method: str, path: str, body: bytes) -> tuple[int, dict]:
        url = urllib.parse.urlsplit(path)
        if url.path in ("/tool", "/tasks"):
            self.on_call()  # a live call uses these every few seconds
        if url.path == "/answer":
            return self.phone.answer(json.loads(body or b"{}"))
        if url.path == "/chat":
            return self.chat.take(json.loads(body or b"{}"))
        if url.path == "/tool":
            b = json.loads(body or b"{}")
            return 200, {
                "result": self.run_tool(str(b.get("name", "")), b.get("args") or {}, str(b.get("since") or ""))
            }
        if url.path == "/tasks":
            out = [t for t in self.finished.values() if not t["fetched"]]
            for t in out:
                t["fetched"] = True
            running = sum(
                1
                for j in self.app.jobs.recent(20)
                if j.status in ("queued", "running") and j.title.startswith("From a call")
            )
            return 200, {
                "finished": [{k: t[k] for k in ("id", "request", "status", "result")} for t in out],
                "running": running,
                "approvals": self.app.ask.call_approvals(),  # asked once on the call (core/ask.py)
                "computer": "online",
            }
        if url.path == "/transcript":
            return 200, self._transcript(json.loads(body or b"{}"))
        if url.path == "/turn":  # a turn-by-turn call: Gemini Live is down (fallback.py)
            self.on_call()
            return self.turns.answer(json.loads(body or b"{}"))
        if url.path == "/textcall":  # ...and the phone can't listen: the call goes on as text
            return 200, self.textcall.start(json.loads(body or b"{}"))
        if url.path == "/upload":
            return self._upload(urllib.parse.parse_qs(url.query), body)
        return 404, {"error": "not found"}

    def _transcript(self, b: dict) -> dict:
        self.app.availability.set_on_call(None)  # the call page sends this when the call ends
        (self.dir / "live.json").unlink(missing_ok=True)
        return self.save_transcript(b)

    def save_transcript(self, b: dict) -> dict:
        """Keep a call's transcript, however it went (live voice, turn by turn, or text on Telegram: "layer"), and
        hand it to the feature that placed the call (a check-in writes your journal and study logs from it)."""
        lines = [x for x in (b.get("lines") or []) if isinstance(x, dict)][:5000]
        if not lines:
            return {"ok": True}
        d = self.dir / "transcripts"
        d.mkdir(parents=True, exist_ok=True)
        f = d / f"{now():%Y-%m-%d-%H%M%S}.txt"
        while f.exists():  # two calls ending in the same second (a text call and a voice one)
            f = f.with_name(f.stem + "-1.txt")
        purpose = str(b.get("purpose") or "")
        how = {"turns": "turn by turn", "telegram": "text on Telegram"}.get(str(b.get("layer") or ""), "")
        head = " ".join(x for x in (purpose, f"({how})" if how else "") if x)
        text = "".join(f"{x.get('who', '?')}: {x.get('text', '')}\n" for x in lines)
        f.write_text((f"# {head}\n" if head else "") + text, encoding="utf-8")
        f.chmod(0o600)
        r = (jload(self.dir / "rings.json", {}) or {}).get(str(b.get("since") or ""))
        if r:
            mid = (r.get("key") or "").split(":")[0]
            m = self.app.modules.get(mid)
            if m and self.app.is_on(mid) and hasattr(m, "call_transcript"):
                m.call_transcript(r["key"], lines)
        self.app.events.emit("call_transcript", lines=len(lines), layer=str(b.get("layer") or "live")[:10])
        used = self.tool_log.pop(str(b.get("since") or ""), [])
        from kurooto.core import gists

        gists.note_call(f, purpose, used)  # what it did, for its gist when the transcript is forgotten
        from kurooto.core import threads

        threads.from_call(self.app, lines)  # "I'll send the draft tonight" said on the call: an open thread
        try:  # the look back never stands in the way of keeping the transcript
            review.review(self, lines, used, purpose)
        except Exception as e:
            self.app.events.emit("call_review_failed", error=f"{type(e).__name__}: {e}"[:200])
        return {"ok": True}

    def _upload(self, q: dict, body: bytes) -> tuple[int, dict]:
        name = re.sub(r"[^\w.-]+", "-", (q.get("name") or ["shared"])[0])[:80] or "shared"
        note = (q.get("note") or [""])[0][:500]
        uid = re.sub(r"[^\w-]", "", (q.get("id") or [""])[0])[:40]
        part, parts = int((q.get("part") or ["0"])[0]), int((q.get("parts") or ["1"])[0])
        inbox = layout.file_dir(self.app, "inbox")  # your notes' inbox, or your files folder's (core/layout.py)
        inbox.mkdir(parents=True, exist_ok=True)
        tmp = inbox / f".part-{uid}" if uid else None
        target = tmp or inbox / f"{now():%Y-%m-%d-%H%M%S}-{name}"
        so_far = tmp.stat().st_size if tmp and part > 0 and tmp.exists() else 0
        if len(body) > 1 << 20 or so_far + len(body) > 50 * 1024 * 1024:
            return 413, {"error": "files can be at most 50 MB, sent in parts of at most 1 MB"}
        with open(target, "ab" if tmp and part > 0 else "wb") as f:
            f.write(body)
        if tmp and part < parts - 1:
            return 200, {"ok": True, "part": part}
        dest = inbox / f"{now():%Y-%m-%d-%H%M%S}-{name}"
        if tmp:
            tmp.replace(dest)
        rel = layout.shown(self.app, dest)
        self.app.events.emit("files_shared", via="phone", bytes=dest.stat().st_size)
        chat = (q.get("chat") or [""])[0]  # sent into a chat (0.8.10): saved, then a chat message names it (its fid)
        if chat and self.setting("chat_files_inline"):
            fid = uid or uuid.uuid4().hex[:16]
            self.chat.shared(dest, note, fid=fid, session=self.sessions.norm(chat) or MAIN)
            return 200, {"ok": True, "saved": rel, "fid": fid}
        self.chat.shared(dest, note)  # "summarise the PDF I just sent" finds it (chat.py, modules/chat.py)
        from kurooto.modules import photodates  # a photo shared with "dates" as its note: its dates as buttons

        if note and photodates.on(self.app) and photodates.WORDS.search(note) and photodates.pictures([dest]):
            self.app.notify(photodates.start(self.app, [dest], via="app"), kind="info", why="asked")
            return 200, {"ok": True, "saved": rel}
        drafts = self.app.modules.get("drafts")  # shared with "check this": Check my draft (modules/drafts.py)
        if drafts is not None and self.app.is_on("drafts") and note and wants_check(note):
            self.app.notify(drafts.check([dest], note, via="app"), kind="info", why="asked")
            return 200, {"ok": True, "saved": rel}
        if self.app.is_on("chat"):
            jid = self.app.jobs.submit(
                f"A file was shared from my phone: {rel}"
                + (f" (my note: {note})" if note else "")
                + ". File it into my notes where it belongs, and tell me where it went.",
                title=f"Shared: {name}",
            )
            self.app.modules["chat"].own(jid)  # part of the conversation: where it went is known to what you ask next
        else:
            self.app.notify(f"Got {name} from your phone: saved to {rel}.", kind="info", why="asked")
        return 200, {"ok": True, "saved": rel}

    # ------------------------------------------------------------------------ what the line is told
    def config_template(self) -> dict:
        tools = self.tools()
        you = self.app.settings.get("you.name") or ""
        whose = f"{you}'s" if you else "the user's"
        lines = [
            f"You are {self.app.name}, {whose} personal assistant, on a live voice call.",
            f"It is %%NOW%%, their local time ({self._zone()}). Say every time and plan the day in this local "
            "time, counting from now: never UTC, never a time that has already passed today.",
            "Talk like a friend on a call: short and natural; never read out lists or markdown. Answer in the "
            "language they speak.",
            *[t.hint for t in tools if t.hint],
            "If something needs a screen or their computer, say so. Don't read out email contents or other people's "
            "details.",
        ]
        from kurooto.core import persona  # the persona card and boundaries; calls.persona the same rules

        lines += [x for x in (persona.card_text(self.app), persona.rule(self.app)) if x]
        if self.setting("persona"):
            lines.append(persona.clean(str(self.setting("persona")), 500)[0])
        learned = review.lessons(self.app)
        if learned:
            lines.append("What earlier calls taught you (follow these):\n" + "\n".join(f"- {x}" for x in learned))
        cfg = {
            "_model": self.setting("live_model") or "gemini-3.8-live",
            "responseModalities": ["AUDIO"],
            "systemInstruction": "\n".join(lines),
            "tools": [{"functionDeclarations": [t.declaration() for t in tools]}],
            "inputAudioTranscription": {},
            "outputAudioTranscription": {},
            "contextWindowCompression": {"slidingWindow": {}},
            # less trigger-happy than the default: fan noise and the speaker's echo kept counting as speech
            "realtimeInputConfig": {
                "automaticActivityDetection": {
                    "startOfSpeechSensitivity": "START_SENSITIVITY_LOW",
                    "prefixPaddingMs": 300,
                    "silenceDurationMs": 800,
                }
            },
        }
        if self.setting("voice"):
            cfg["speechConfig"] = {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": self.setting("voice")}}}
        return cfg

    def texts(self) -> dict:
        notes = (
            "notes search is keyword-only, and read_note reads from their notes repo"
            if self.setting("notes_repo")
            else "notes search is keyword-only over titles and headings, and whole notes can't be opened"
        )
        return {
            "offline": f"Their computer is OFF right now (last update %%BRIEF_AT%%): pending_items answers from that "
            f"update; {notes}; anything that needs the computer is saved and done when it's back on. Say so when it "
            "matters.",
            "purpose": "You placed this call yourself. Reason: %%REASON%%. When the call connects, speak first: greet "
            "them and get straight to the reason.",
            "queued": "Saved. Their computer is off; it will do this as soon as it's back on.",
            # when Gemini Live is down (fallback.py): turn by turn with the phone's own speech, or text on Telegram
            "turns": "This call goes turn by turn: their phone turns what they say into text and reads your answers "
            "aloud. Keep each answer to one to three short spoken sentences: no lists, markdown, emojis or stage "
            "directions.",
            "text_call": "The voice service is down, so this call goes on as text messages on Telegram. Write like a "
            "friend texting: short messages, no headings or tables. Keep to what the call is for.",
            "needs_computer": "That needs their computer, which is off right now.",
            "no_notes": "Their computer is off, so whole notes can't be read right now.",
        }

    def offline_notes(self) -> bool:
        return True

    def live_models(self) -> list[str]:
        """The Gemini Live models a call tries, in order: live_model, then live_models (fallback.py)."""
        extra = self.setting("live_models") or []
        extra = [extra] if isinstance(extra, str) else list(extra)
        names = [str(m).strip() for m in [self.setting("live_model") or "gemini-3.8-live", *extra]]
        return list(dict.fromkeys(m for m in names if re.fullmatch(r"[A-Za-z0-9][\w.-]{0,79}", m)))[:6]

    def live_profiles(self) -> dict:
        """Per Live model, how its session differs from the call setup (fallback.live_profile)."""
        models = self.live_models()
        by = self.setting("voice_by_model") or {}
        by = by if isinstance(by, dict) else {}
        voice = str(self.setting("voice") or "")
        return {m: live_profile(m, i == 0, voice, by) for i, m in enumerate(models)}

    def voice_for(self, key: str | None = None, outgoing: bool = False) -> str:
        """How a call listens and speaks: "live", "phone" or "auto" (voice_mode), or what voice_by_kind says for its
        kind: "<feature>:<name>" or "<feature>" from its key (checkins:evening, then checkins), "reminder" for a call
        with no feature's key, "outgoing" for calls you start. key None: the default."""
        modes = ("auto", "live", "phone")
        by = self.setting("voice_by_kind") or {}
        by = by if isinstance(by, dict) else {}
        if outgoing:
            kinds = ["outgoing"]
        elif key is None:
            kinds = []
        elif ":" not in key:  # a reminder call (its key is random, or "held-..." while calls were blocked)
            kinds = ["reminder"]
        else:
            parts = key.split(":")
            kinds = list(dict.fromkeys([":".join(parts[:2]), parts[0]]))
        for k in kinds:
            if str(by.get(k) or "").lower() in modes:
                return str(by[k]).lower()
        mode = str(self.setting("voice_mode") or "auto").lower()
        return mode if mode in modes else "auto"

    def doctor_checks(self) -> list[tuple]:
        """`kurooto doctor`: "Phone calls: voice service", how often Gemini Live failed and what calls did instead."""
        return [("voice service", *self.live.line())]

    # ------------------------------------------------------------------------------ on a call right now
    def on_call(self, at: str | None = None) -> None:
        """A call is live (it just started, or the call page checked in): nothing else rings for a while.
        `at` is when the call line saw it (ISO time), for events it kept while this computer was off."""
        t = time.time()
        if at:
            try:
                t = dt.datetime.fromisoformat(str(at).replace("Z", "+00:00")).timestamp()
            except ValueError:
                pass
        if time.time() - t < ON_CALL_S:
            self.app.availability.set_on_call(dt.datetime.fromtimestamp(t + ON_CALL_S))

    def index_items(self) -> list[dict]:
        return notes_index(self.app.workspace)

    def state_message(self) -> dict:
        if getattr(self, "silenced", False):
            return {"schedule": []}
        tools = self.tools()
        briefs = {t.name: t.name for t in tools if t.offline == "brief"}
        self.phone.flush()  # messages the line missed while it was down
        self.chat.flush()
        return {
            "schedule": self.schedule_list(),
            "inbox": self.phone.inbox(),
            "names": {"assistant": self.app.name, "owner": self.app.settings.get("you.name") or ""},
            "config": self.config_template(),
            "texts": self.texts(),
            "offline": {
                "brief": briefs,
                "queue": [t.name for t in tools if t.offline == "queue"],
                "notes": self.offline_notes(),
            },
            "brief": {t.name: self._brief_value(t) for t in tools if t.name in briefs},
            "presence": self._presence(),  # speaking for this computer while it's gone (core/presence.py)
            "live": {  # Gemini Live's models in order, and how calls listen (fallback.py)
                "models": self.live_models(),
                "profiles": self.live_profiles(),  # what each model's session drops or changes (fallback.py)
                "text_model": self.setting("text_model") or "gemini-flash-latest",
                "voice": self.voice_for(),
                "outgoing": self.voice_for(outgoing=True),
            },
            "sealed_on": self.app.is_on("lidsafe"),  # off: the line drops the reminders it holds (lidsafe.py)
        }

    def _presence(self) -> dict:
        try:
            return self.app.presence.line_config()
        except Exception as e:
            return {"on": False, "error": str(e)[:200]}

    def _brief_value(self, t: Tool):
        try:
            v = t.run({})
            return v if isinstance(v, dict) else {"answer": v}
        except Exception as e:
            return {"note": f"couldn't prepare this: {e}"[:200]}

    def silence_line(self) -> bool:
        """Kurooto is being turned off: the call line forgets the scheduled calls (and sealed reminders), so it doesn't
        ring meanwhile."""
        import asyncio

        self.silenced = True
        c = self.connector
        if c.loop is None or c.ws is None:
            return False
        try:
            msg = json.dumps({"type": "state", "schedule": [], "sealed_on": False})
            asyncio.run_coroutine_threadsafe(c.ws.send(msg), c.loop).result(10)
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------------------------ phones
    def pair_start(self) -> dict:
        """A one-time code (15 minutes) for pairing a phone, as a link and a QR code."""
        import segno

        code = line.pair_code()
        res = self.connector.admin_wait("pair-code", code=code, minutes=15)
        if res.get("error"):
            raise RuntimeError(res["error"])
        link = f"{self.worker_url()}/pair#c={code}"
        qr = segno.make(link, error="m")
        return {
            "code": code,
            "link": link,
            "svg": qr.svg_inline(scale=5, dark="#0b0f0a", light="#ffffff"),
            "expires_min": 15,
        }

    def devices(self) -> list[dict]:
        """The paired phones; an Android one has `connected` (its own connection to the line, 0.7.0) and `heard`."""
        devs = self.connector.admin_wait("devices").get("devices", [])
        self._devices_seen = (time.time(), devs)
        return devs

    def revoke(self, device_id: str) -> bool:
        # `device`, not `id`: that's the admin request's own (before 0.6.0 this waited for an answer that never came)
        self.views.keys_at = 0.0  # the phones' keys are asked for again (views.py)
        return bool(self.connector.admin_wait("revoke", device=device_id).get("ok"))

    def shortcuts(self) -> list[dict]:
        """The Tell Kurooto links your phones made (0.6.0; one per phone): id, device, device_name, created, used.
        A line from before 0.6.0 doesn't know them: none."""
        return list(self.connector.admin_wait("tells").get("tells") or [])

    def shortcut_revoke(self, shortcut_id: str) -> bool:
        """Revoke one Tell Kurooto link: the Shortcut that holds it stops working at once. Its phone stays paired."""
        if not re.fullmatch(r"[0-9a-f]{8}", shortcut_id or ""):
            return False
        return bool(self.connector.admin_wait("tell-revoke", tid=shortcut_id).get("ok"))

    def status(self) -> dict:
        link = jload(self.dir / "link.json", {}) or {}
        return {
            "url": self.worker_url(),
            "connected": self.connector.connected,
            "since": link.get("since"),
            "error": link.get("error", ""),
            "line_version": self.connector.version,
            "live": self.live.summary(),  # Gemini Live's failures this week, and what calls did instead
        }

    # -------------------------------------------------------------------------------------- telegram
    def commands(self):
        return [
            Command("call", "a link to call me now (from any phone or browser, for 2 hours)", self._cmd_call),
            Command("phone", "pair a phone so calls ring it", self._cmd_phone),
            Command("phones", "paired phones (and /unpair <id> to remove one)", self._cmd_phones),
            Command("unpair", "remove a paired phone: /unpair <id>", self._cmd_unpair),
            Command(
                "lessons",
                "what calls have learned from looking back (/lessons forget 2, /lessons clear)",
                self._cmd_lessons,
            ),
        ]

    def _cmd_lessons(self, msg, arg: str) -> str:
        return review.command(self.app, arg)

    def _cmd_call(self, msg: Incoming, arg: str) -> str:
        if not self.worker_url():
            return "Phone calls aren't set up yet (Settings → Features → Phone calls)."
        link = self.link(voice=self.voice_for(outgoing=True))
        msg.reply("Tap to call (this link works for 2 hours):", buttons=[[("Call now", {"url": link})]])
        return None

    def _cmd_phone(self, msg: Incoming, arg: str) -> str:
        try:
            p = self.pair_start()
        except Exception as e:
            return f"Couldn't make a pairing link: {e}. Is the computer connected to your call line?"
        msg.reply(
            "Open this on the phone you want to pair (within 15 minutes). Android: it offers the Kurooto app. iPhone: "
            "it shows how to add Kurooto to your Home Screen.",
            buttons=[[("Pair this phone", {"url": p["link"]})]],
        )
        return None

    def _cmd_phones(self, msg: Incoming, arg: str) -> str:
        try:
            ds = self.devices()
        except Exception as e:
            return f"Couldn't ask your call line: {e}"
        if not ds:
            return "No phones are paired. /phone pairs one."
        return (
            "Paired:\n"
            + "\n".join(
                f"{d['id']}  {d['name']} ({d['kind']}{', notifications on' if d.get('push') else ''}), "
                f"since {d['created'][:10]}"
                for d in ds
            )
            + "\n\n/unpair <id> removes one."
        )

    def _cmd_unpair(self, msg: Incoming, arg: str) -> str:
        if not re.fullmatch(r"[0-9a-f]{8}", arg.strip()):
            return "Usage: /unpair <id> (ids are in /phones)."
        try:
            return "Removed." if self.revoke(arg.strip()) else "No device with that id."
        except Exception as e:
            return f"Couldn't ask your call line: {e}"

    def intents(self):
        pat = re.compile(
            r"^(?:please )?call me (?:back )?((?:at|in|on|tomorrow|tonight)\b.+?)(?: (?:to|about|and|for|so) (.+))?$",
            re.I,
        )

        def match(text: str):
            m = pat.match(text.strip().rstrip(".!"))
            if not m:
                return None
            w = m.group(1)
            if re.fullmatch(r"at \d{1,2}(?:[:.]\d{2})?\s*(?:am|pm)?", w, re.I):
                w = a_time(w) or w  # "at 5" is five o'clock, never "in 5 minutes"
            try:
                return {"at": parse_when(w), "reason": (m.group(2) or "a reminder call").strip()}
            except ValueError:
                return None

        now_pat = re.compile(
            r"^(?:please |can you |could you )?(?:call|ring|phone) me(?: (?:right )?now| back)?"
            r"(?:[,:\s]+(?:to|about|so|and|we|i|because)?\s*(.+))?$"
            r"|^give me a (?:call|ring)(?: now)?(?:[,:\s]+(?:to|about|so|and)?\s*(.+))?$",
            re.I,
        )

        def match_now(text: str):
            t = text.strip().rstrip(".!")
            m = now_pat.match(t)
            if not m or re.search(r"\bquiz|\btest me\b", t, re.I):  # "call me for a quiz" is the quiz's
                return None
            return {"reason": (m.group(1) or m.group(2) or "you asked me to call").strip()}

        ask_pat = re.compile(
            r"^(?:please |can you |could you )?(?:(?:call|ring|phone) me|give me a (?:call|ring))\b", re.I
        )

        def match_when(text: str):
            """ "call me, I didn't wake up at 12": its only time is one that didn't happen, so it asks."""
            t = text.strip()
            said = stale_time(t)
            if not ask_pat.match(t) or not said or a_time(t) or re.search(r"\bquiz|\btest me\b", t, re.I):
                return None
            return {"said": said}

        cancel_pat = re.compile(
            r"^(?:please )?(?:cancel|drop|delete|remove|scrap|kill|call off)\b.*\b(?:calls?|ring)\b", re.I
        )

        def match_cancel(text: str):
            t = text.strip().rstrip(".!")
            if not cancel_pat.match(t) or re.search(r"\b(?:alarm|wake-?up|check-?in|debrief)\b", t, re.I):
                return None
            said = re.search(r"\b\d{1,2}(?:[:.]\d{2})?(?:\s*[ap]m)?\b", t, re.I)
            tm = (a_time(t) or a_time(f"at {said[0]}")) if said else None
            return {"time": tm, "said": said[0] if said else "", "tomorrow": bool(re.search(r"\btomorrow\b", t, re.I))}

        return [
            Intent(
                "call_me",
                "call me at/in … (about …)",
                match,
                lambda msg, sl: self.schedule(sl["at"], sl["reason"], why="calls.own"),
                examples=("call me at 17:30 about the essay", "call me in 20 minutes"),
                guarded="call.place",
            ),
            Intent(
                "call_when",
                "call me (its only time is one that didn't happen): asks when",
                match_when,
                lambda msg, sl: (
                    f"When should I call? I didn't book one: the {sl['said']} in that is about what "
                    'didn\'t happen or what was planned. Say "call me now" or "call me at 4:30".'
                ),
                examples=("call me, I didn't wake up at 7",),
            ),
            Intent(
                "call_now",
                "call me now",
                match_now,
                lambda msg, sl: self.place(sl["reason"], force=True, why="calls.own"),
                examples=("call me now",),
                guarded="call.place",
            ),
            Intent(
                "cancel_call",
                "cancel that call, cancel the 12:00 call",
                match_cancel,
                self.cancel_by_words,
                examples=("cancel the 12:00 call", "cancel that call"),
            ),
        ]

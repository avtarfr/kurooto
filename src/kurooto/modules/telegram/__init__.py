"""Telegram: your own bot is Kurooto's main channel. Only your account is served; anyone else is ignored.

Setup (the wizard does this): make a bot with @BotFather, paste its token, then tap the one-time link the
wizard shows so Kurooto learns which chat is yours.
"""

from __future__ import annotations

import asyncio
import json
import re
import secrets as pysecrets
import time
from pathlib import Path

from kurooto.core.clock import now, parse_when
from kurooto.core.config import register_defaults
from kurooto.core.lock import Lock
from kurooto.core.notify import Message
from kurooto.core.state import jload, jsave
from kurooto.modules.base import Command, Incoming, Intent, Module
from kurooto.modules.telegram.api import TelegramAPI, TelegramError
from kurooto.modules.text import a_minutes, a_time, another_day

register_defaults(
    "telegram",
    {"chat_id": None, "allowed_users": [], "silent_kinds": ["call"], "api_base": "https://api.telegram.org"},
)

TOKEN = "telegram.token"  # noqa: S105 (the secret's name, not its value)
PAIR_S = 3600  # a pairing link works for an hour
_START = re.compile(r"^/start(?:@\w+)?(?:\s+(\S+))?\s*$", re.I)  # "/start CODE", "/start@bot CODE", "/start"


class PairingProblem(Exception):
    """Why pressing Start hasn't connected yet, in words for the setup page. `retry`: keep waiting meanwhile."""

    def __init__(self, kind: str, message: str, retry: bool = True):
        super().__init__(message)
        self.kind, self.message, self.retry = kind, message, retry


class Telegram(Module):
    id = "telegram"
    title = "Telegram"
    description = "Talk to Kurooto from your own Telegram bot: messages, reminders, questions with buttons."
    privacy = "Your messages travel through Telegram's servers to your own bot, then to this computer."

    def __init__(self, app):
        super().__init__(app)
        self.dir = app.paths.state / "telegram"

    # ------------------------------------------------------------------------------------------ setup
    def api(self) -> TelegramAPI | None:
        tok = self.app.secrets.get(TOKEN)
        return TelegramAPI(tok, self.setting("api_base")) if tok else None

    def ready(self):
        if not self.app.secrets.get(TOKEN):
            return False, "paste your bot's token from @BotFather"
        if not self.setting("chat_id"):
            return False, "open your bot with the one-time link so Kurooto knows it's you"
        return True, ""

    def check_token(self, token: str) -> dict:
        """Raises TelegramError if the token is wrong; returns the bot's details."""
        return TelegramAPI(token.strip(), self.setting("api_base")).me()

    def pair_start(self, token: str) -> dict:
        """Save the token and make a one-time link that tells Kurooto which chat is yours."""
        me = self.check_token(token)
        self.app.secrets.set(TOKEN, token.strip())
        code = pysecrets.token_urlsafe(9).replace("-", "x").replace("_", "y")
        jsave(self.dir / "pairing.json", {"code": code, "created": time.time()})
        return {"bot": me.get("username"), "code": code, "link": f"https://t.me/{me.get('username')}?start={code}"}

    def pairing(self) -> dict:
        """The pairing in progress ({} if none, or if its hour is up)."""
        p = jload(self.dir / "pairing.json", {}) or {}
        return p if p.get("code") and time.time() - p.get("created", 0) <= PAIR_S else {}

    def pair_relink(self) -> dict:
        """A new pairing link for the bot whose token is already saved (the old link expired)."""
        tok = self.app.secrets.get(TOKEN)
        if not tok:
            raise PairingProblem("token", "Paste your bot's token first.", retry=False)
        return self.pair_start(tok)

    def drop_webhook(self) -> None:
        """The bot was connected to a web address (a webhook), which stops Kurooto reading its messages."""
        api = self.api()
        if api:
            api.call("deleteWebhook", {"drop_pending_updates": False})
            self.app.events.emit("telegram_webhook_removed")

    def _updates(self, api: TelegramAPI, offset: int, wait: int) -> list:
        """getUpdates, with its failures turned into what the person can do about them."""
        try:
            return api.call(
                "getUpdates", {"offset": offset, "timeout": wait, "allowed_updates": ["message"]}, timeout=wait + 15
            )
        except TelegramError as e:
            if e.code == 401:
                raise PairingProblem(
                    "revoked", "That token was revoked. Get the new one from @BotFather and paste it above.", False
                ) from None
            if e.code == 409:
                hook = ""
                try:
                    hook = (api.call("getWebhookInfo") or {}).get("url") or ""
                except (TelegramError, OSError):
                    pass
                if hook or "webhook" in (e.description or "").lower():
                    raise PairingProblem(
                        "webhook",
                        "This bot is connected to a web address (a webhook), so Kurooto can't read its messages. "
                        "Disconnect it to use the bot with Kurooto.",
                    ) from None
                raise PairingProblem(
                    "conflict",
                    "Another program is reading this bot's messages (maybe another Kurooto using the same bot). "
                    "Make a new bot with @BotFather, or stop the other program.",
                ) from None
            raise PairingProblem("telegram", f"Telegram said: {e.description}"[:200]) from None
        except OSError:
            raise PairingProblem(
                "network", "Can't reach Telegram right now (is the internet on?). Still trying."
            ) from None

    def pair_poll(self, wait: int = 25) -> dict | None:
        """Look for "/start <code>" from the person who tapped the link. On success, save their chat and say hi.
        None while nothing has come yet; PairingProblem says why it can't work (or what came instead)."""
        p = self.pairing()
        if not p:
            raise PairingProblem("expired", "This link expired: get a new one.", retry=False)
        api = self.api()
        if not api:
            raise PairingProblem("token", "Paste your bot's token first.", retry=False)
        offset = (jload(self.dir / "offset.json", {}) or {}).get("offset", 0)
        updates = self._updates(api, offset, wait)
        found, bare = None, False
        for u in updates:
            offset = u["update_id"] + 1
            m = u.get("message") or {}
            hit = _START.match((m.get("text") or "").strip())
            if m.get("chat", {}).get("type") != "private" or not hit:
                continue
            if (hit.group(1) or "").lower() == p["code"].lower():
                found = m
            elif not found:  # Start pressed without the code (or with an old one): say where the right one is
                bare = True
                hinted = set(p.get("hinted") or [])
                if m["chat"]["id"] not in hinted:
                    hinted.add(m["chat"]["id"])
                    p["hinted"] = sorted(hinted)
                    jsave(self.dir / "pairing.json", p)
                    try:
                        api.send(
                            m["chat"]["id"],
                            "Almost: send the message shown on Kurooto's setup page here (it starts with /start).",
                        )
                    except (TelegramError, OSError):
                        pass
        jsave(self.dir / "offset.json", {"offset": offset})
        if not found:
            if bare:
                raise PairingProblem("no_code", "Got a /start without the code: send the full message shown here.")
            return None
        self.app.settings.set("telegram.chat_id", found["chat"]["id"])
        self.app.settings.set("telegram.allowed_users", [found["from"]["id"]])
        (self.dir / "pairing.json").unlink(missing_ok=True)
        who = found["from"].get("first_name") or ""
        api.send(
            found["chat"]["id"],
            f"Hi{' ' + who if who else ''}! I'm {self.app.name}. This chat is now ours; "
            "I'll ignore everyone else. Send /help to see what I can do.",
        )
        self.app.events.emit("telegram_paired")
        return {"chat_id": found["chat"]["id"], "name": who}

    # ------------------------------------------------------------------------------------ the channel
    def start(self):
        self.app.notifier.register("telegram", self._send)

    def stop(self):
        super().stop()
        self.app.notifier.unregister("telegram")

    def _send(self, msg: Message):
        api, chat = self.api(), self.setting("chat_id")
        if not api or not chat:
            return None
        text = f"{msg.title}\n\n{msg.text}" if msg.title else msg.text
        silent = msg.kind in (self.setting("silent_kinds") or []) and "app" in self.app.notifier.channels
        if msg.file:
            mid = api.document(chat, msg.file, caption=text[:1000], reply_to=msg.reply_to)
        else:
            mid = api.send(chat, text, buttons=msg.buttons, reply_to=msg.reply_to, silent=silent)
        if msg.map_kind:
            self.map_set(mid, msg.map_kind, msg.map_ref)
        return mid

    def map_set(self, message_id, kind: str, ref) -> None:
        """Remember what a sent message is about, so replies to it and its buttons find their way back."""
        with Lock(self.app.paths.state, "telegram-map"):
            m = jload(self.dir / "map.json", {}) or {}
            m[str(message_id)] = {"kind": kind, "ref": ref, "ts": now().isoformat()}
            if len(m) > 3000:
                for k in sorted(m, key=lambda k: m[k]["ts"])[:1000]:
                    m.pop(k)
            jsave(self.dir / "map.json", m)

    def map_get(self, message_id) -> dict | None:
        return (jload(self.dir / "map.json", {}) or {}).get(str(message_id))

    # ------------------------------------------------------------------------------------- the gateway
    async def background(self, stop: asyncio.Event) -> None:
        await self.run(stop)

    async def run(self, stop: asyncio.Event) -> None:
        """Long-poll Telegram and hand every message from you to the assistant."""
        backoff = 5
        while not stop.is_set():
            api = self.api()
            allowed = set(self.setting("allowed_users") or [])
            if not api or not allowed or self.pairing():  # while the setup page pairs, it reads the messages
                await asyncio.sleep(10)
                continue
            offset = (jload(self.dir / "offset.json", {}) or {}).get("offset", 0)
            try:
                updates = await asyncio.to_thread(
                    api.call,
                    "getUpdates",
                    {"offset": offset, "timeout": 50, "allowed_updates": ["message", "callback_query"]},
                    None,
                    70,
                )
                backoff = 5
            except TelegramError as e:
                self.app.events.emit("telegram_error", code=e.code, error=e.description[:200])
                if e.code == 401:  # the token was revoked
                    self.app.notifier.channels.pop("telegram", None)
                    await asyncio.sleep(300)
                await asyncio.sleep(30 if e.code == 409 else backoff)  # 409: the bot runs somewhere else too
                continue
            except Exception as e:
                self.app.events.emit("telegram_error", error=f"{type(e).__name__}: {e}"[:200])
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 120)
                continue
            for u in updates:
                jsave(self.dir / "offset.json", {"offset": u["update_id"] + 1})
                try:
                    await asyncio.to_thread(self._update, api, u, allowed)
                except Exception as e:
                    self.app.events.emit("telegram_error", error=f"{type(e).__name__}: {e}"[:300])

    def _update(self, api: TelegramAPI, u: dict, allowed: set) -> None:
        if "callback_query" in u:
            cb = u["callback_query"]
            if cb.get("from", {}).get("id") in allowed:
                note = self.app.callback(cb.get("data", ""))
                try:
                    api.call("answerCallbackQuery", {"callback_query_id": cb["id"], "text": (note or "ok")[:190]})
                except TelegramError:
                    pass
            return
        m = u.get("message") or {}
        if m.get("from", {}).get("id") not in allowed or m.get("chat", {}).get("type") != "private":
            return
        chat = m["chat"]["id"]
        if self.app.power.current == "paused" and not re.match(
            r"/(resume|pause|status|help|start)\b", m.get("text") or ""
        ):
            with Lock(self.app.paths.state, "telegram-paused"):  # handled when Kurooto resumes
                with open(self.dir / "paused.jsonl", "a", encoding="utf-8") as f:
                    f.write(json.dumps(u) + "\n")
            api.send(
                chat,
                f"I'm paused {self.app.power.why()}; I'll do this when I'm back. /resume wakes me now.",
                reply_to=m.get("message_id"),
            )
            return

        def respond(text, buttons=None):
            return api.send(chat, text, buttons=buttons, reply_to=m["message_id"])

        files: list[Path] = []
        inbox = self.app.workspace / "inbox"
        stamp = now().strftime("%Y-%m-%d-%H%M%S")
        voice = m.get("voice") or (m.get("audio") if not (m.get("audio") or {}).get("file_name") else None)
        try:
            if voice:
                files.append(api.download(voice["file_id"], inbox, "voice.ogg", stamp))
            else:
                if m.get("photo"):
                    files.append(api.download(m["photo"][-1]["file_id"], inbox, "photo.jpg", stamp))
                for key in ("document", "video", "audio"):
                    if m.get(key):
                        files.append(api.download(m[key]["file_id"], inbox, m[key].get("file_name") or key, stamp))
        except Exception as e:
            respond(f"Couldn't get that file: {e}")
            return
        reply_to = None
        if m.get("reply_to_message"):
            reply_to = self.map_get(m["reply_to_message"]["message_id"])
        msg = Incoming(
            text=(m.get("text") or m.get("caption") or "").strip(),
            via="telegram",
            message_id=m["message_id"],
            files=files,
            reply_to=reply_to,
            voice=bool(voice),
            respond=respond,
        )
        if voice:
            vn = self.app.modules.get("voice_notes")
            if vn and self.app.is_on("voice_notes"):
                try:
                    heard = vn.transcribe(files[0])
                except Exception as e:
                    respond(f"Couldn't make out that voice note: {e}")
                    return
                respond(f"Heard: {heard[:600]}")
                msg.text, msg.files = (msg.text + "\n" + heard).strip(), []
            else:
                respond("Voice notes are off. Turn on Voice notes in Settings (it uses your free Gemini key).")
                return
        self.app.handle(msg)

    def replay_paused(self) -> int:
        """Kurooto resumed: handle what you sent while it was paused, in order."""
        f = self.dir / "paused.jsonl"
        with Lock(self.app.paths.state, "telegram-paused"):
            try:
                lines = f.read_text(encoding="utf-8").splitlines()
            except OSError:
                return 0
            f.unlink(missing_ok=True)
        api, allowed = self.api(), set(self.setting("allowed_users") or [])
        n = 0
        for ln in lines:
            try:
                self._update(api, json.loads(ln), allowed)
                n += 1
            except Exception as e:
                self.app.events.emit("telegram_error", error=f"replay: {type(e).__name__}: {e}"[:200])
        return n

    # ----------------------------------------------------------------------------------- commands
    def commands(self):
        return [
            Command("pause", "pause me (/pause, /pause 2h, /pause until 18:00); reminders wait too", self._pause),
            Command("resume", "wake me up after /pause", lambda m, a: self.app.power.resume()),
            Command("status", "what's going on", self._status),
            Command("hold", "no calls until a time (/hold 18:00, /hold 2h)", self._hold),
            Command("calls", "allow calls again", self._calls),
            Command("focus", "do-not-disturb (/focus 2h, /focus until 18:00, /focus off)", self._focus),
        ]

    def _status(self, msg: Incoming, arg: str) -> str:
        a = self.app.availability
        reason, until = a.call_block()
        lines = [f"Calls: {'held (' + reason + ') until ' + until.strftime('%a %H:%M') if reason else 'allowed now'}"]
        f = a.focus_until()
        if f:
            lines.append(f"Focus until {f.strftime('%H:%M')}")
        jobs = [j for j in self.app.scheduler.jobs() if j.kind == "once"][:5]
        if jobs:
            rows = [f"  {j.when.astimezone():%a %H:%M}  {j.label[:80]}" for j in jobs]
            lines.append("Coming up:\n" + "\n".join(rows))
        if self.app.ask.status_line():  # questions waiting for you (core/ask.py)
            lines.append(self.app.ask.status_line())
        lines += self._status_more()
        lines.append("On: " + ", ".join(m.title for m in self.app.enabled()))
        return "\n".join(lines)

    def _status_more(self) -> list[str]:
        """(ws5) Today's check-ins, what's due in 3 days, the alarm, the last AI requests, and add-ons' lines. Each
        part is skipped when its feature is off or fails."""
        app, out = self.app, []

        def part(fn) -> None:
            try:
                got = fn()
            except Exception as e:
                app.events.emit("status_failed", error=f"{type(e).__name__}: {e}"[:200])
                return
            out.extend([got] if isinstance(got, str) else got or [])

        def checkins():
            plan = app.modules["checkins"].today() if app.is_on("checkins") else {}
            rows = [f"{n} {c.get('time') or '-'} ({c.get('status', '?')})" for n, c in plan.items()]
            return f"Check-ins today: {', '.join(rows)}" if rows else []

        def due():
            if not app.is_on("deadlines"):
                return []
            soon = app.modules["deadlines"].deadlines_soon(72)
            if not soon:
                return "Nothing due in the next 3 days."
            rows = [f"  {r['title'][:70]} ({r['when']})" for r in soon[:6]]
            more = [f"  and {len(soon) - 6} more (/deadlines)"] if len(soon) > 6 else []
            return "Due in the next 3 days:\n" + "\n".join(rows + more)

        def alarm():
            t = app.modules["alarm"].next() if app.is_on("alarm") else None
            return f"Alarm: {t:%a %H:%M}" if t else []

        def jobs():
            recent = app.jobs.recent(3)
            rows = [f"  {j.status:7} {j.title[:60]}" + (f" ({j.seconds:.0f}s)" if j.seconds else "") for j in recent]
            return "Recent AI requests (/jobs):\n" + "\n".join(rows) if rows else []

        for fn in (checkins, due, alarm, jobs):
            part(fn)
        for m in app.enabled():  # an add-on's own lines (core/overlay.py: status_lines)
            if callable(getattr(m, "status_lines", None)):
                part(lambda m=m: [str(x)[:300] for x in (m.status_lines() or [])][:5])
        return out

    def _pause(self, msg: Incoming, arg: str) -> str:
        arg = arg.strip().lower().removeprefix("for ").removeprefix("until ")
        if not arg:
            return self.app.power.pause(None)
        try:
            until = parse_when(arg)
        except ValueError:
            return "How long? /pause 2h, /pause until 18:00, or /pause on its own until /resume."
        return self.app.power.pause(max(1.0, (until - now()).total_seconds() / 60))

    def _hold(self, msg: Incoming, arg: str) -> str:
        try:
            until = parse_when(arg or "1h")
        except ValueError as e:
            return str(e)
        self.app.availability.set_quiet(until)
        self.app.events.emit("calls_held", until=until.isoformat())
        return f"No calls until {until:%a %H:%M}. Messages still come here. /calls lifts it."

    def _calls(self, msg: Incoming, arg: str) -> str:
        self.app.availability.set_quiet(None)
        return "Calls are allowed again (night hours and other holds still apply)."

    def _focus(self, msg: Incoming, arg: str) -> str:
        a = self.app.availability
        arg = arg.strip().lower()
        if arg in ("off", "stop", "end"):
            a.set_focus(None)
            n = self.app.notifier.flush_queue()
            return "Focus off." + (f" {n} message{'s' if n != 1 else ''} waited for you." if n else "")
        if not arg or arg == "status":
            f = a.focus_until()
            return f"Focus until {f:%H:%M}." if f else "Not in focus. /focus 2h starts it."
        try:
            until = parse_when(arg.removeprefix("until ").strip())
        except ValueError as e:
            return str(e)
        a.set_focus(until)
        self.app.scheduler.action("telegram.focus_end", lambda p: self.app.notifier.flush_queue())
        self.app.scheduler.at(until, "telegram.focus_end", key="telegram:focus-end", module=self.id)
        return f"Focus until {until:%H:%M}: I'll hold everything that isn't urgent until then."

    def intents(self):
        import re

        def hold(text: str):
            if not re.search(r"\b(no calls?|don'?t call(?: me)?|hold (?:the )?calls?|no ringing)\b", text, re.I):
                return None
            if another_day(text):  # "no calls on Friday": the AI works out the day
                return None
            mins, tm = a_minutes(text), a_time(text)
            if mins:
                return {"until": f"{mins}m"}
            return {"until": tm} if tm else None

        def calls_ok(text: str):
            return (
                {} if re.search(r"\bcalls? (?:are )?(?:fine|ok(?:ay)?|allowed) (?:again|now)\b", text, re.I) else None
            )

        def focus(text: str):
            if not re.search(r"\b(focus|do not disturb|dnd)\b", text, re.I) or another_day(text):
                return None
            if re.search(r"\b(off|stop|end|done|over)\b", text, re.I):
                return {"arg": "off"}
            mins, tm = a_minutes(text), a_time(text)
            return {"arg": f"{mins}m" if mins else f"until {tm}"} if (mins or tm) else None

        return [
            Intent("hold_calls", "no calls for a while", hold, lambda m, s: self._hold(m, s["until"])),
            Intent("calls_ok", "calls are fine again", calls_ok, lambda m, s: self._calls(m, "")),
            Intent("focus", "do-not-disturb on or off", focus, lambda m, s: self._focus(m, s["arg"])),
        ]

"""Chat: anything you type that isn't a command or an instant request goes to the AI you picked, and the answer
comes back as a reply. Start a message with "high:" (or "low:") to choose how hard it thinks.

The conversation's context: Telegram and the phone app's chat with Kurooto itself ("main") share one history
(chat/history.json) of which the last 6 turns from the last 2 hours go with each request. Each other chat in the phone
app (a session, 0.8.10: calls/sessions.py) has its own history (chat/sessions/<id>.json) that carries over for as long
as the chat lives, like an AI web app: its latest turns, up to SESSION_CHARS, go with each request. A reply in the app
brings the quoted message along (Incoming.quote), and a file sent in a session is named in that session's context.

How it came (0.9.0, chat.context_line): every turn ends with one "[How it came]" line in coarse words, as spoken ones
did since 0.8.17: typed on Telegram, in the phone app or on this computer; on a phone call now; and, from Face
presence, that they stepped away from the desk and since when. Never a place: Brain's phone places and Wi-Fi labels go
in only with chat.context_places (off). Spoken turns keep their line, plus (face.greet.tell_ai) the greeting Kurooto
had just said when they answer it. With Brain's "Why this?" on (mind.why.to_ai), a turn that asks why also gets the
plain reasons for its last few messages that came by themselves (mind/records.py), never a sense, a mood or a tone."""

from __future__ import annotations

import datetime as dt
import re
import time

from kurooto import providers
from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave
from kurooto.modules.base import Command, Incoming, Module

register_defaults(
    "chat",
    {
        "context_line": True,  # (0.9.0) each turn tells your AI how it came, in plain words (typed where, a call, away)
        # (0.9.0) and your phone's last saved place and Wi-Fi name (Brain's phone senses), off until you say so
        "context_places": False,
    },
)

SHARED_S = 2 * 3600  # files shared from the phone this recently are mentioned to the AI when you talk of a file
SESSION_KEEP = 40  # turns kept per phone app chat (session)
SESSION_CHARS = 16000  # of them, the latest that fit in this many characters go with each request
JOBS_KEEP = 200  # which session each recent request was asked in (its answer becomes that session's turn)
MAIN = "main"
SHARED_NOTE = "\n\n[Shared from their phone lately"
HOW = "[How it came] "  # (0.9.0) the context line chat.ask puts last; chat history leaves it out
WHY_ASKED = re.compile(r"\bwhy\b", re.I)  # (mind.why.to_ai) a turn that asks why gets the records' reasons
WHY_ROWS = 3  # ...the last this many messages it started by itself
WHY_S = 24 * 3600  # ...from the last day
REFERS = re.compile(r"\b(files?|pdfs?|photos?|pictures?|images?|docs?|documents?|screenshots?|attachments?|sent|shared|"
                    r"uploaded)\b", re.I)  # fmt: skip


class Chat(Module):
    id = "chat"
    title = "Chat with your AI"
    description = "Ask anything in plain words; the AI you picked answers, with your notes at hand."
    privacy = "What you ask, and notes it needs to read, go to the AI service you picked."

    def __init__(self, app):
        super().__init__(app)
        self.dir = app.paths.state / "chat"
        self.mine: set[str] = set()  # the requests chat sent: only their answers become the conversation
        self.turns: dict[str, str] = {}  # (0.8.17) request -> its conversation ("main" or a session's id)

    def owns(self, jid: str) -> bool:
        return jid in self.mine

    def conversation(self, jid: str) -> str:
        """(0.8.17) The conversation a request of chat's is a turn of ("main", or a phone app chat's id); "" for one
        on its own (the terminal's, another feature's). An AI may keep a program running for it
        (brain.claude.session)."""
        return self.turns.get(jid, "")

    # ------------------------------------------------------------------------------ sessions (0.8.10)
    def session_file(self, sid: str):
        return self.dir / "sessions" / f"{sid}.json"

    def _jobs_file(self):
        return self.dir / "session-jobs.json"

    def _job_session(self, jid: str, sid: str | None = None) -> str:
        """Which session a request was asked in (set with sid; read without). Kept on disk: an answer can come
        after a restart."""
        f = self._jobs_file()
        rows = jload(f, {}) or {}
        if sid is None:
            return str(rows.get(jid) or "")
        rows[jid] = sid
        jsave(f, dict(list(rows.items())[-JOBS_KEEP:]))
        return sid

    def _vias_file(self):
        return self.dir / "job-via.json"

    def job_via(self, jid: str, via: str | None = None) -> tuple[str, str]:
        """(0.9.0) Where a request was asked (Incoming.via: telegram, app, terminal, voice, ...) and its phone app chat:
        set with via, read without. Ids and words of a few letters only, for the AI jobs tab (core/jobs.py:source)."""
        f = self._vias_file()
        rows = jload(f, {}) or {}
        if via is not None:
            rows[jid] = via
            jsave(f, dict(list(rows.items())[-JOBS_KEEP:]))
        return str(rows.get(jid) or ""), self._job_session(jid)

    def forget_session(self, sid: str) -> None:
        """A phone app chat was deleted: its context goes too."""
        if sid and sid != MAIN:
            self.session_file(sid).unlink(missing_ok=True)

    def own(self, jid: str) -> None:
        """A request made for you elsewhere (a file shared from the phone) becomes part of the conversation."""
        self.mine = {*list(self.mine)[-50:], jid}

    @property
    def history_file(self):
        return self.dir / "history.json"

    def ready(self):
        main = self.app.settings.get("brain.main")
        if not main:
            return False, "pick an AI model first"
        brain = providers.build(self.app, main)
        ok, why = brain.available() if brain else (False, "unknown brain")
        return (True, "") if ok else (False, f"{providers.label(main, main)}: {why}")

    def ask(self, msg: Incoming) -> str:
        text = msg.text.strip()
        sid = str(getattr(msg, "session", "") or "")
        sid = "" if sid == MAIN else sid  # a phone app chat of its own, or "" (Telegram, main: as before)
        if text.lower() in ("/new", "/clear", "new", "clear") and not msg.files:
            return self.clear_history(sid)
        quote = getattr(msg, "quote", None)
        if quote and quote.get("text"):  # a reply in the phone app: the message it answers comes along
            whose = "your" if quote.get("from") == "kurooto" else "their own"
            text = f'[They are replying to {whose} earlier message: "{quote["text"]}"]\n\n{text}'
        if msg.files:  # a photo or file sent with it (or alone): the AI is told where it is, to open it
            sent = ", ".join(str(f) for f in msg.files)
            text = (
                f"{text}\n\n" if text else "They sent this with no words: say what it is, or answer what it asks.\n\n"
            ) + f"Files they sent with it (on this computer; open them to read them): {sent}"
        elif REFERS.search(text):  # "summarise the PDF I just sent" from the phone app (calls/chat.py:shared)
            text += self._shared_note(sid)

        terminal = msg.via in ("terminal", "setup")
        quiet = terminal or msg.via == "voice"  # spoken (modules/voice): the answer comes back aloud, not on Telegram
        now_ts = time.time()
        if sid:  # a session's context carries over for as long as it lives, as much of it as fits
            recent, size = [], 0
            for h in reversed(jload(self.session_file(sid), []) or []):
                size += len(str(h.get("user") or "")) + len(str(h.get("assistant") or ""))
                if size > SESSION_CHARS:
                    break
                recent.insert(0, h)
        else:  # Only inject history if there is recent conversation within 2 hours
            history = jload(self.history_file, []) or []
            recent = [h for h in history if now_ts - h.get("at", 0) < 7200][-6:]

        if recent and not terminal:
            conv = ["Previous conversation:"]
            for h in recent:
                conv.append(f"User: {h['user']}")
                conv.append(f"Assistant: {h['assistant']}")
            conv.append(f"\nCurrent request:\n{text}")
            prompt = "\n".join(conv)
        else:
            prompt = text
        if msg.via != "voice" and self.app.settings.get("chat.context_line", True):  # (0.9.0) typed: where, a call,
            line = self._how_line(msg)  # away from the desk; before the register line, which stays last
            if line:
                prompt = f"{prompt}\n\n{line}"
        why = self._why_line(msg.text)  # (0.9.0, mind.why.to_ai) "why did you...": its own reasons
        if why:
            prompt = f"{prompt}\n\n{why}"
        from kurooto.core import persona  # (register) a short message, a short answer; a voice note, spoken style

        style = persona.register_line(self.app, msg.text.strip(), voice=msg.voice, files=bool(msg.files))
        if style:
            prompt = f"{prompt}\n\n{style}"  # last, so a "high:" prefix still comes first
        if msg.via == "voice":  # (0.8.17) said at the desk: who Kurooto knows said it (asked, it said it can't see)
            prompt = f"{prompt}\n\n{self._heard_line(msg)}"
        else:  # (0.9.0, voice.mirror_to_chat) typed right after it said something aloud by itself: what it said
            v = self.app.modules.get("voice")
            said = v.unasked_line() if v is not None and self.app.is_on("voice") else ""
            if said:
                prompt = f"{said}\n\n{prompt}"

        helper = getattr(self.app, "helper", None)  # the internet down: the offline helper (core/helper.py)
        if helper is not None and not recent:
            quick = helper.offline_reply(msg.text, files=bool(msg.files))
            if quick:
                return quick
        if not msg.files:  # "tidy my LA notes' headings": done in a scratch folder, comes as a proposal
            from kurooto.core import proposals

            said = proposals.notes_request(self.app, msg, msg.text.strip())
            if said:
                return said
        title = msg.text.strip()[:80] or (msg.files[0].name if msg.files else "")
        waits = helper is not None and helper.holds() and not helper.here(self._main())  # said here, not again
        jid = self.app.jobs.submit(
            prompt,
            title=title,
            reply_to=None if quiet else msg.message_id,
            quiet=quiet,
            offline=waits,
            images=self._pictures(msg.files) or None,
        )
        msg.job = jid
        self.mine = {*list(self.mine)[-50:], jid}
        if sid:
            self._job_session(jid, sid)
        try:
            self.job_via(jid, str(msg.via or ""))  # the AI jobs tab says where it came from (look.jobs_source)
        except Exception:
            pass
        if not terminal:
            self.turns = {**dict(list(self.turns.items())[-50:]), jid: sid or MAIN}
        return helper.waiting_line() if waits else "On it."

    def _pictures(self, files) -> list:
        """(0.9.0) The pictures among the files sent with a message (a photo on Telegram or from the phone, one attached
        on the dashboard's Chat page), for the request's Task.images: an API brain gets them with the request and
        Claude Code may open exactly those; agy opens them where the prompt says. None when your AI says it can't read
        pictures (an Ollama model without vision would refuse the whole request)."""
        from pathlib import Path

        from kurooto.providers.openai_compat import PICTURE_TYPES

        pics = [Path(f) for f in files or [] if Path(f).suffix.lower() in PICTURE_TYPES and Path(f).is_file()]
        if not pics:
            return []
        try:
            ok, _ = providers.sees(self.app)
        except Exception:
            ok = None
        return pics if ok is not False else []

    def _heard_line(self, msg: Incoming) -> str:
        """(0.8.17) How a spoken turn came: the desk's microphone, Voice ID's verdict, what Face presence sees now."""
        bits = ["They said this aloud to you at their desk (your own microphone, written out on this computer)."]
        if msg.speaker == "owner":
            bits.append("Voice ID recognised their voice.")
        if self.app.is_on("face"):
            from kurooto.core import nearby

            v = nearby.view(self.app)
            if v and v[1]:
                bits.append("Face presence recognises their face in front of your camera right now.")
            elif v and v[0]:
                bits.append(f"Face presence sees {v[0]} face{'s' if v[0] != 1 else ''} in front of your camera.")
            bits.append(
                "You never see the camera's pictures: Face presence recognises faces on this computer and tells you "
                "only this."
            )
        greeting = self._greeting_said()
        if greeting:  # (0.9.0, face.greet.tell_ai) they're answering the greeting it just said
            bits.append(f'Just before, you had greeted them aloud, unasked, with: "{greeting}"')
        return HOW + " ".join(bits)

    def _greeting_said(self) -> str:
        """(0.9.0, face.greet.tell_ai) The desk greeting Voice just said, while its conversation is open and this is
        the first turn in it; else "". Rule-made words (counts, a class's or a deadline's title), never the camera."""
        if not self.app.settings.get("face.greet.tell_ai", True):
            return ""
        v = self.app.modules.get("voice")
        p = getattr(v, "portal", None)
        if p is None or not p.open or p.opened_why != "greeting" or getattr(p, "turns", 0):
            return ""
        return str(p.last_reply or "")[:300]

    def _how_line(self, msg: Incoming) -> str:
        """(0.9.0, chat.context_line) How a typed turn came, in coarse words: where it was typed, a call going on,
        Face presence's "stepped away from the desk" with its time, and (chat.context_places) the phone's last saved
        place and Wi-Fi name. "" when there's nothing to say (a check-up run, the setup page)."""
        where = {
            "telegram": "They typed this on Telegram.",
            "app": "They typed this in the phone app.",
            "terminal": "They typed this on this computer (the dashboard or a terminal).",
        }.get(msg.via, "")
        if not where:
            return ""
        bits = [where]
        try:
            from kurooto.web.tools_api import live_call

            if live_call(self.app):
                bits.append("They're on a phone call right now.")
        except Exception:
            pass
        face = self.app.modules.get("face")
        if face is not None and self.app.is_on("face"):
            try:
                left = face.left_at()
            except Exception:
                left = None
            if left is not None:
                bits.append(f"Face presence noticed they stepped away from their desk at {left:%H:%M}.")
        if self.app.settings.get("chat.context_places", False):
            bits += self._places()
        return HOW + " ".join(bits)

    def _places(self) -> list[str]:
        """(chat.context_places, off) Brain's phone senses (mind/senses/phone.py): the last saved place the phone
        reported in the last day, whether it left one, and the Wi-Fi's name you gave it. Labels only, never a
        position; nothing when Brain or those senses are off."""
        import time as _t

        from kurooto.core import nearby

        out = []
        try:
            from kurooto.mind.senses import phone, store

            since = _t.time() - 86400
            out_at = nearby.phone_out(self.app)
            p = store.events(self.app, "phone:places", since) if phone.enabled(self.app, "places") else []
            if p and p[-1].get("target"):
                at = dt.datetime.fromtimestamp(float(p[-1]["t"]))
                did = "left" if out_at is not None else "was last at or near"
                out.append(f'Their phone {did} the place they saved as "{p[-1]["target"]}" ({at:%H:%M}).')
            w = store.events(self.app, "phone:wifi", since) if phone.enabled(self.app, "wifi") else []
            name = phone.wifi_label(self.app, str(w[-1].get("target") or "")) if w else ""
            if name:
                out.append(f'Their phone is on the Wi-Fi they call "{name}".')
        except Exception:
            return []
        return out

    def _why_line(self, text: str) -> str:
        """(0.9.0, mind.why.to_ai, under Brain's mind.why.on) A turn that asks why gets the reasons for the last few
        messages Kurooto started by itself: when, the plain reason, the setting, whether Brain's gate made it quieter,
        what it expected and what came of it. Never a sense, the read, a mood or a tone (the door's and gate's own
        words aren't passed on)."""
        if not WHY_ASKED.search(text or "") or not self.app.settings.get("mind.why.to_ai", True):
            return ""
        try:
            from kurooto.mind import records

            if not records.why_on(self.app):
                return ""
            import time as _t

            rows = [r for r in records._load(self.app)["rows"] if _t.time() - float(r.get("at") or 0) <= WHY_S]
            calm = getattr(self.app, "calm", None)
            said = []
            for r in rows[-WHY_ROWS:]:
                reason = calm.reason(r.get("why")) if calm is not None else None
                what = reason.what if reason is not None else "no reason recorded"
                bit = f"{dt.datetime.fromtimestamp(float(r['at'])):%H:%M}: {what}"
                if reason is not None and reason.setting:
                    bit += f" (setting {reason.setting})"
                if str(r.get("gate") or "").startswith("Brain's gate made it quieter"):
                    bit += "; Brain's gate made it quieter"
                oc = (r.get("outcome") or {}).get("result")
                if r.get("expect"):
                    want = "a reply" if r["expect"]["what"] == "reply" else "that they'd act on it"
                    bit += f"; it expected {want}: {records.SAID.get(oc or '', 'still open')}"
                said.append(bit)
        except Exception:
            return ""
        if not said:
            return ""
        return (
            "[Why it did things lately] What it started by itself, newest last (its own records): "
            + "; ".join(said)
            + "."
        )

    def _main(self):
        from kurooto import providers

        return providers.build(self.app, self.app.settings.get("brain.main") or "")

    def _shared_note(self, sid: str = "") -> str:
        """Files shared from the phone: in a session, the ones sent in it (however long ago); elsewhere, the last 2
        hours' that weren't sent in a session."""
        rows = [r for r in jload(self.app.paths.state / "calls" / "shared.json", []) or [] if isinstance(r, dict)]
        if sid:
            recent = [r for r in rows if r.get("session") == sid][-5:]
        else:
            t = time.time()
            recent = [r for r in rows if r.get("session", MAIN) == MAIN and t - r.get("at", 0) < SHARED_S][-5:]
        if not recent:
            return ""
        files = "; ".join(f"{r.get('name')} at {r.get('path')}" + (f" (note: {r['note']})" if r.get("note") else "")
                          for r in recent)  # fmt: skip
        return (
            f"{SHARED_NOTE}, newest last; if they mean one, open it there (gone from there: it was filed into "
            f"their notes under a similar name): {files}]"
        )

    def record_turn(self, prompt: str, reply: str, jid: str = "") -> None:
        """Record a completed turn into chat history for context continuity (jid: the request's id, so a phone app
        chat's answer goes into that chat's own history)."""
        if not reply or reply.startswith("I couldn't "):
            return
        sid = self._job_session(jid) if jid else ""
        # Extract the user's actual prompt if wrapped in history
        from kurooto.core.persona import strip_register

        user_text = prompt = strip_register(prompt)
        if "Current request:\n" in prompt:
            user_text = prompt.split("Current request:\n", 1)[1].strip()
        user_text = user_text.split(SHARED_NOTE, 1)[0].split("\n\n" + HOW, 1)[0]
        user_text = user_text.split("\n\n[Why it did things lately]", 1)[0]
        if sid:
            if not self._session_lives(sid):  # deleted while the AI was answering
                return
            f = self.session_file(sid)
            history = jload(f, []) or []
            history.append({"user": user_text[:4000], "assistant": reply[:4000].strip(), "at": time.time()})
            jsave(f, history[-SESSION_KEEP:])
            if len(history) == 1:  # the first answer in it: maybe an AI title (calls.chat_titles)
                calls = self.app.modules.get("calls")
                if calls is not None and hasattr(calls, "sessions"):
                    try:
                        calls.sessions.first_answer(sid, user_text, reply)
                    except Exception as e:
                        self.app.events.emit("chat_title_failed", error=f"{type(e).__name__}: {e}"[:200])
            return
        history = jload(self.history_file, []) or []
        history.append(
            {
                "user": user_text[:1200],
                "assistant": reply[:1200].strip(),
                "at": time.time(),
            }
        )
        jsave(self.history_file, history[-10:])

    def _session_lives(self, sid: str) -> bool:
        calls = self.app.modules.get("calls")
        return calls is None or not hasattr(calls, "sessions") or calls.sessions.get(sid) is not None

    def clear_history(self, sid: str = "") -> str:
        if sid:
            jsave(self.session_file(sid), [])
            return "Started this chat over: what was said in it before is forgotten."
        jsave(self.history_file, [])
        return "Started a new conversation. Previous context cleared."

    def commands(self):
        return [
            Command("new", "start a fresh conversation, clearing previous chat context", self._cmd_new),
            Command("clear", "clear conversation history", self._cmd_new),
            Command("brain", "which AI answers, and whether it's working", self._brain),
            Command(
                "usage", "AI requests per day over the last week, usage limits hit, and today's limits", self._usage
            ),
        ]

    def _cmd_new(self, msg: Incoming, arg: str) -> str:
        sid = str(getattr(msg, "session", "") or "")  # in a phone app chat: that chat starts over
        return self.clear_history("" if sid == MAIN else sid)

    def _brain(self, msg: Incoming, arg: str) -> str:
        s = self.app.settings
        out = []
        roles = [("main", s.get("brain.main"))] + [("fallback", k) for k in providers.fallback.chosen(self.app)]
        for role, which in roles:
            if not which:
                continue
            b = providers.build(self.app, which)
            ok, why = b.available() if b else (False, "unknown")
            out.append(f"{role}: {providers.label(which, which)} ({'ready' if ok else why})")
        if not out:
            return "No AI model is set up yet."
        extra = providers.claude_accounts.accounts(self.app)
        if extra:
            out.append("Claude accounts: Claude Code, " + ", ".join(a.label for a in extra))
        if not providers.fallback.chosen(self.app) and providers.fallback.triggers(self.app):
            auto = [b.id for b in providers.fallback.candidates(self.app, {s.get("brain.main") or ""})]
            if auto:
                out.append("at a limit: " + " → ".join(providers.fallback.name(b) for b in auto))
        return "\n".join(out + limit_lines(self.app))

    def _usage(self, msg: Incoming, arg: str) -> str:
        days = int(arg) if arg.strip().isdigit() and 1 <= int(arg) <= 60 else 7
        from kurooto.core.readbudget import usage_text as reading
        from kurooto.providers.agy import log_usage, log_usage_text  # (ws5) agy's own count, interactive use too

        # today's free limits: used, learned, when they reset (core/quota.py); the concept graph's reading budget
        waiting = limit_lines(self.app)
        return (
            usage_text(self.app.jobs.usage(days), days)
            + log_usage_text(log_usage(days))
            + self.app.quota.text()
            + ("\n" + "\n".join(waiting) if waiting else "")
            + reading(self.app)
        )


def history_files(app) -> list:
    """Every file of chat turns: Telegram's and main's, then each phone app chat's (core/retention.py, gists.py)."""
    d = app.paths.state / "chat"
    return [d / "history.json", *sorted((d / "sessions").glob("*.json"))]


def limit_lines(app) -> list[str]:
    """The AIs skipped for a limit until its reset (providers/fallback.py), one line each."""
    import datetime as dt

    out = []
    for bid, rec in providers.fallback.status(app).items():
        when = dt.datetime.fromtimestamp(float(rec["until"]))
        how = "as it said" if rec.get("src") == "said" else "a guess: it didn't say"
        out.append(
            f"{providers.fallback.name(bid)} is at its limit until {when:%a %H:%M} ({how}); others answer meanwhile."
        )
    return out


def usage_text(rows: list[dict], days: int) -> str:
    """/usage: one line per day, each brain's requests and usage-limit hits."""
    import datetime as dt

    from kurooto.core.clock import now

    def label(brain: str) -> str:
        return providers.label(brain, brain or "?")

    by_day: dict[str, list[dict]] = {}
    for r in rows:
        by_day.setdefault(r["day"], []).append(r)
    lines = [f"AI requests, last {days} days:"]
    today = now().date()
    for i in range(days - 1, -1, -1):
        d = today - dt.timedelta(days=i)
        parts = [
            f"{label(r['brain'])} {r['requests']}" + (f" (limit hit {r['limited']})" if r["limited"] else "")
            for r in by_day.get(d.isoformat(), [])
        ]
        lines.append(f"{d:%a %d %b}  {', '.join(parts) or '-'}")
    total = sum(r["requests"] for r in rows)
    limited = sum(r["limited"] for r in rows)
    brains: dict[str, int] = {}
    for r in rows:
        brains[r["brain"]] = brains.get(r["brain"], 0) + r["requests"]
    split = ", ".join(f"{label(b)} {n}" for b, n in sorted(brains.items(), key=lambda x: -x[1]))
    lines.append(f"\nTotal: {total} request{'s' if total != 1 else ''}" + (f" ({split})" if split else "") + ".")
    if limited:
        lines.append(f"Usage limit hit {limited} time{'s' if limited != 1 else ''}; /brain shows the fallback.")
    tools = sum(r.get("tool_calls", 0) for r in rows)
    if tools:
        lines.append(f"The AI used tools {tools} time{'s' if tools != 1 else ''}.")
    lines.append("Not counted: quick checks (how hard a request is, grading a quiz answer) and phone calls.")
    return "\n".join(lines)

"""Chat: anything you type that isn't a command or an instant request goes to the AI you picked, and the answer
comes back as a reply. Start a message with "high:" (or "low:") to choose how hard it thinks."""

from __future__ import annotations

import re
import time

from kurooto import providers
from kurooto.core.state import jload, jsave
from kurooto.modules.base import Command, Incoming, Module

SHARED_S = 2 * 3600  # files shared from the phone this recently are mentioned to the AI when you talk of a file
SHARED_NOTE = "\n\n[Shared from their phone lately"
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

    def owns(self, jid: str) -> bool:
        return jid in self.mine

    def own(self, jid: str) -> None:
        """A request made for you elsewhere (a file shared from the phone) becomes part of the conversation."""
        self.mine = {*list(self.mine)[-50:], jid}

    @property
    def history_file(self):
        return self.dir / "history.json"

    def ready(self):
        main = self.app.settings.get("brain.main")
        if not main:
            return False, "pick an AI brain first"
        brain = providers.build(self.app, main)
        ok, why = brain.available() if brain else (False, "unknown brain")
        return (True, "") if ok else (False, f"{providers.label(main, main)}: {why}")

    def ask(self, msg: Incoming) -> str:
        text = msg.text.strip()
        if text.lower() in ("/new", "/clear", "new", "clear") and not msg.files:
            return self.clear_history()
        if msg.files:  # a photo or file sent with it (or alone): the AI is told where it is, to open it
            sent = ", ".join(str(f) for f in msg.files)
            text = (
                f"{text}\n\n" if text else "They sent this with no words: say what it is, or answer what it asks.\n\n"
            ) + f"Files they sent with it (on this computer; open them to read them): {sent}"
        elif REFERS.search(text):  # "summarise the PDF I just sent" from the phone app (calls/chat.py:shared)
            text += self._shared_note()

        terminal = msg.via in ("terminal", "setup")
        quiet = terminal or msg.via == "voice"  # spoken (modules/voice): the answer comes back aloud, not on Telegram
        history = jload(self.history_file, []) or []

        # Only inject history if there is recent conversation within 2 hours
        now_ts = time.time()
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
        from kurooto.core import persona  # (register) a short message, a short answer; a voice note, spoken style

        style = persona.register_line(self.app, msg.text.strip(), voice=msg.voice, files=bool(msg.files))
        if style:
            prompt = f"{prompt}\n\n{style}"  # last, so a "high:" prefix still comes first

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
            prompt, title=title, reply_to=None if quiet else msg.message_id, quiet=quiet, offline=waits
        )
        msg.job = jid
        self.mine = {*list(self.mine)[-50:], jid}
        return helper.waiting_line() if waits else "On it."

    def _main(self):
        from kurooto import providers

        return providers.build(self.app, self.app.settings.get("brain.main") or "")

    def _shared_note(self) -> str:
        rows = jload(self.app.paths.state / "calls" / "shared.json", []) or []
        recent = [r for r in rows if isinstance(r, dict) and time.time() - r.get("at", 0) < SHARED_S][-5:]
        if not recent:
            return ""
        files = "; ".join(f"{r.get('name')} at {r.get('path')}" + (f" (note: {r['note']})" if r.get("note") else "")
                          for r in recent)  # fmt: skip
        return (
            f"{SHARED_NOTE}, newest last; if they mean one, open it there (gone from there: it was filed into "
            f"their notes under a similar name): {files}]"
        )

    def record_turn(self, prompt: str, reply: str) -> None:
        """Record a completed turn into chat history for context continuity."""
        if not reply or reply.startswith("I couldn't "):
            return
        # Extract the user's actual prompt if wrapped in history
        from kurooto.core.persona import strip_register

        user_text = prompt = strip_register(prompt)
        if "Current request:\n" in prompt:
            user_text = prompt.split("Current request:\n", 1)[1].strip()
        user_text = user_text.split(SHARED_NOTE, 1)[0]
        history = jload(self.history_file, []) or []
        history.append(
            {
                "user": user_text[:1200],
                "assistant": reply[:1200].strip(),
                "at": time.time(),
            }
        )
        jsave(self.history_file, history[-10:])

    def clear_history(self) -> str:
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
        return self.clear_history()

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
            return "No AI brain is set up yet."
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

"""Chat: anything you type that isn't a command or an instant request goes to the AI you picked, and the answer
comes back as a reply. Start a message with "high:" (or "low:") to choose how hard it thinks."""

from __future__ import annotations

import time

from kurooto import providers
from kurooto.core.state import jload, jsave
from kurooto.modules.base import Command, Incoming, Module


class Chat(Module):
    id = "chat"
    title = "Chat with your AI"
    description = "Ask anything in plain words; the AI you picked answers, with your notes at hand."
    privacy = "What you ask, and notes it needs to read, go to the AI service you picked."

    def __init__(self, app):
        super().__init__(app)
        self.dir = app.paths.state / "chat"

    @property
    def history_file(self):
        return self.dir / "history.json"

    def ready(self):
        main = self.app.settings.get("brain.main")
        if not main:
            return False, "pick an AI brain first"
        brain = providers.build(self.app, main)
        ok, why = brain.available() if brain else (False, "unknown brain")
        return (True, "") if ok else (False, f"{providers.CHOICES.get(main, main)}: {why}")

    def ask(self, msg: Incoming) -> str:
        text = msg.text.strip()
        if text.lower() in ("/new", "/clear", "new", "clear"):
            return self.clear_history()

        terminal = msg.via in ("terminal", "setup")
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

        jid = self.app.jobs.submit(prompt, title=text[:80], reply_to=None if terminal else msg.message_id, quiet=terminal)
        msg.job = jid
        return "On it."

    def record_turn(self, prompt: str, reply: str) -> None:
        """Record a completed turn into chat history for context continuity."""
        if not reply or reply.startswith("I couldn't "):
            return
        # Extract the user's actual prompt if wrapped in history
        user_text = prompt
        if "Current request:\n" in prompt:
            user_text = prompt.split("Current request:\n", 1)[1].strip()
        history = jload(self.history_file, []) or []
        history.append({
            "user": user_text,
            "assistant": reply[:1200].strip(),
            "at": time.time(),
        })
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
        for role in ("main", "fallback"):
            which = s.get(f"brain.{role}")
            if not which:
                continue
            b = providers.build(self.app, which)
            ok, why = b.available() if b else (False, "unknown")
            out.append(f"{role}: {providers.CHOICES.get(which, which)} ({'ready' if ok else why})")
        return "\n".join(out) or "No AI brain is set up yet."

    def _usage(self, msg: Incoming, arg: str) -> str:
        days = int(arg) if arg.strip().isdigit() and 1 <= int(arg) <= 60 else 7
        from kurooto.providers.agy import log_usage, log_usage_text  # (ws5) agy's own count, interactive use too

        # today's free limits: used, learned, when they reset (core/quota.py)
        return usage_text(self.app.jobs.usage(days), days) + log_usage_text(log_usage(days)) + self.app.quota.text()


def usage_text(rows: list[dict], days: int) -> str:
    """/usage: one line per day, each brain's requests and usage-limit hits."""
    import datetime as dt

    from kurooto.core.clock import now

    def label(brain: str) -> str:
        return providers.CHOICES.get(brain, brain or "?")

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

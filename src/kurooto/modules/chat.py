"""Chat: anything you type that isn't a command or an instant request goes to the AI you picked, and the answer
comes back as a reply. Start a message with "high:" (or "low:") to choose how hard it thinks."""

from __future__ import annotations

from kurooto import providers
from kurooto.modules.base import Command, Incoming, Module


class Chat(Module):
    id = "chat"
    title = "Chat with your AI"
    description = "Ask anything in plain words; the AI you picked answers, with your notes at hand."
    privacy = "What you ask, and notes it needs to read, go to the AI service you picked."

    def ready(self):
        main = self.app.settings.get("brain.main")
        if not main:
            return False, "pick an AI brain first"
        brain = providers.build(self.app, main)
        ok, why = brain.available() if brain else (False, "unknown brain")
        return (True, "") if ok else (False, f"{providers.CHOICES.get(main, main)}: {why}")

    def ask(self, msg: Incoming) -> str:
        # `kurooto ask` and the setup page's try-it box wait for the answer themselves; Telegram doesn't get it
        terminal = msg.via in ("terminal", "setup")
        jid = self.app.jobs.submit(msg.text, reply_to=None if terminal else msg.message_id, quiet=terminal)
        msg.job = jid
        return "On it."

    def commands(self):
        return [
            Command("brain", "which AI answers, and whether it's working", self._brain),
            Command("jobs", "the last few requests and how they went", self._jobs),
            Command(
                "usage", "AI requests per day over the last week, usage limits hit, and today's limits", self._usage
            ),
        ]

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

    def _jobs(self, msg: Incoming, arg: str) -> str:
        rows = [
            f"{j.status:7} {j.effort or '-':6} {f'{j.seconds:.0f}s' if j.seconds else '':>5}  {j.title}"
            for j in self.app.jobs.recent(8)
        ]
        return "\n".join(rows) or "No requests yet."

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

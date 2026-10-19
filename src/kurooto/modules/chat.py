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
        self.app.jobs.submit(msg.text, reply_to=msg.message_id)
        return "On it."

    def commands(self):
        return [
            Command("brain", "which AI answers, and whether it's working", self._brain),
            Command("jobs", "the last few requests and how they went", self._jobs),
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

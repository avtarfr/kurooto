"""After class: a couple of minutes after each class in your timetable ends, Kurooto asks what was worth keeping.
Reply on Telegram and it goes into that subject's class log in your notes (<subject>/class-log.md)."""

from __future__ import annotations

import datetime as dt

from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.modules.base import Incoming, Module

register_defaults("capture", {"delay_min": 2})


class Capture(Module):
    id = "capture"
    title = "After-class notes"
    description = (
        "A couple of minutes after each class ends, you're asked what was worth keeping; replies go to its log."
    )
    requires = ("telegram", "subjects")

    def start(self):
        self.action("ask", self._ask)
        self.every("plan", "daily 00:10", lambda p: self._plan())
        self._plan()

    def _plan(self) -> None:
        subjects = self.app.modules["subjects"]
        delay = dt.timedelta(minutes=self.setting("delay_min") or 2)
        for c in subjects.classes_on():
            at = c["end_dt"] + delay
            if at > now():
                self.app.scheduler.at(
                    at,
                    "capture.ask",
                    {"subject": c["subject"], "name": c["name"], "day": at.date().isoformat()},
                    key=f"capture:{c['subject']}:{c['end']}",
                    module=self.id,
                    grace_s=3 * 3600,
                )

    def _ask(self, p: dict) -> None:
        if p["subject"] in self.app.modules["subjects"].skipped():
            return
        self.app.notify(
            f"How was {p['name']}? Anything worth keeping (a definition, a doubt, homework)? Reply here.",
            kind="question",
            map_kind="capture",
            map_ref=f"{p['subject']}|{p['day']}",
            buttons=[[("Nothing today", f"cap:{p['subject']}:none")]],
        )
        self.app.events.emit("capture_asked", subject=p["subject"])

    def replies(self):
        return {"capture": self._answer}

    def _answer(self, msg: Incoming, ref: str) -> str:
        slug, _, day = ref.partition("|")
        f = self.app.workspace / slug / "class-log.md"
        f.parent.mkdir(parents=True, exist_ok=True)
        new = not f.exists()
        with open(f, "a", encoding="utf-8") as out:
            if new:
                out.write(f"# {self.app.modules['subjects'].name_of(slug)}: class log\n")
            out.write(f"\n## {day or now().date().isoformat()}\n\n{msg.text.strip()}\n")
        self.app.events.emit("capture_answered", subject=slug)
        return f"Saved to {slug}/class-log.md."

    def callbacks(self):
        return {"cap": lambda ref, act: "OK."}

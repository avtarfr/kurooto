"""The week in numbers, from what Kurooto saw: requests, reminders, check-ins answered, deadlines done, quiz
grades. Sent on Sundays (time in Settings) and on /week. Counted from the local event log; nothing leaves here."""

from __future__ import annotations

import datetime as dt
from collections import Counter

from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.modules.base import Command, Module
from kurooto.modules.calls.tools import Tool

register_defaults("weekly", {"when": "weekly sun 19:00"})


class Weekly(Module):
    id = "weekly"
    title = "Weekly summary"
    description = "The week in numbers every Sunday: requests, reminders, check-ins, deadlines, quiz."
    requires = ("telegram",)

    def start(self):
        self.every("summary", self.setting("when") or "weekly sun 19:00", lambda p: self.app.notify(self.summary()))

    def summary(self, days: int = 7) -> str:
        since = now() - dt.timedelta(days=days)
        c: Counter = Counter()
        grades = []
        for e in self.app.events.tail(20000):
            try:
                if dt.datetime.fromisoformat(e["ts"]) < since:
                    continue
            except (KeyError, ValueError):
                continue
            k = e.get("kind")
            c[k] += 1
            if k == "job_done":
                c["job_ok" if e.get("ok") else "job_failed"] += 1
            if k == "quiz_graded":
                grades.append(e.get("q", 0))
        lines = [f"Your week ({since:%a %d %b} – {now():%a %d %b}):"]
        lines.append(
            f"Messages to me: {c['message_in']}; AI requests: {c['job_ok']} answered"
            + (f", {c['job_failed']} failed" if c["job_failed"] else "")
        )
        if c["reminder_fired"] or c["reminder_set"]:
            lines.append(f"Reminders: {c['reminder_set']} set, {c['reminder_fired']} delivered")
        if c["checkin_asked"]:
            lines.append(f"Check-ins answered: {c['checkin_answered']} of {c['checkin_asked']}")
        if c["deadline_done"] or c["deadline_told"]:
            lines.append(f"Deadlines: {c['deadline_done']} marked done, {c['deadline_told']} nudges")
        if grades:
            lines.append(f"Quiz: {len(grades)} answered, average {sum(grades) / len(grades):.1f}/5")
        for m in self.app.enabled():  # features with their own line (Study tracker, Research)
            if m.id != self.id and hasattr(m, "weekly_lines"):
                try:
                    lines += m.weekly_lines()
                except Exception as e:
                    self.app.events.emit("weekly_line_failed", module=m.id, error=str(e)[:200])
        return "\n".join(lines)

    def commands(self):
        return [Command("week", "the week in numbers", lambda m, a: self.summary())]

    def call_tools(self):
        return [
            Tool(
                "weekly_summary",
                "The week in numbers (messages, reminders, check-ins, deadlines, quiz).",
                lambda a: self.summary(),
            )
        ]

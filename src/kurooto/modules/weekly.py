"""The week in numbers, from what Kurooto saw: requests, reminders, check-ins answered, deadlines done, quiz
grades, study hours, journal days. Sent on Sundays (time in Settings) and on /week. Counted from the local event log;
nothing leaves here.

Optionally (Settings → Weekly summary → call) the summary is followed by a Sunday review call: the week in numbers,
what went well and what didn't, anything Kurooto should do differently, and next week's deadlines and priorities.
After it, with Chat on, the AI writes it up as a weekly review in your journal; without Chat, your words go there.
"""

from __future__ import annotations

import datetime as dt
from collections import Counter

from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.modules import daily
from kurooto.modules.base import Command, Module
from kurooto.modules.calls.tools import Tool

register_defaults("weekly", {"when": "weekly sun 19:00", "call": False})  # call: also a Sunday review call
REASON = "Sunday review"


class Weekly(Module):
    id = "weekly"
    title = "Weekly summary"
    description = "The week in numbers every Sunday: requests, reminders, check-ins, deadlines, quiz."
    requires = ("telegram",)

    def start(self):
        self.every("summary", self.setting("when") or "weekly sun 19:00", self._sunday)

    def _sunday(self, p: dict) -> None:
        self.app.notify(self.summary())
        calls = self.app.modules.get("calls")
        if self.setting("call") and calls and self.app.is_on("calls") and calls.ready()[0]:
            calls.place(REASON, key=f"weekly:review:{now().date().isoformat()}")
            self.app.events.emit("weekly_review_called")

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
        if c["checkin_asked"] or c["checkin_called"]:
            lines.append(
                f"Check-ins answered: {c['checkin_answered']} of {c['checkin_asked'] + c['checkin_called']}"
                + (f"; {c['checkin_skipped']} skipped" if c["checkin_skipped"] else "")
            )
        if c["deadline_done"] or c["deadline_told"]:
            lines.append(f"Deadlines: {c['deadline_done']} marked done, {c['deadline_told']} nudges")
        if grades:
            lines.append(f"Quiz: {len(grades)} answered, average {sum(grades) / len(grades):.1f}/5")
        jd = self.journal_days(days)
        if jd:
            lines.append(f"Journal: {jd} of {days} days")
        for m in self.app.enabled():  # features with their own line (Study tracker, Research)
            if m.id != self.id and hasattr(m, "weekly_lines"):
                try:
                    lines += m.weekly_lines()
                except Exception as e:
                    self.app.events.emit("weekly_line_failed", module=m.id, error=str(e)[:200])
        return "\n".join(lines)

    def journal_days(self, days: int = 7) -> int:
        today = now().date()
        return sum(1 for i in range(days) if daily.note_path(self.app, today - dt.timedelta(days=i)).is_file())

    def commands(self):
        return [Command("week", "the week in numbers", lambda m, a: self.summary())]

    # ------------------------------------------------------------------------------- the review call
    def script(self) -> str:
        """The Sunday review call, step by step, with the week's details filled in."""
        app = self.app
        steps = [f"The week in numbers, briefly, from this:\n{self.summary()}"]
        study = app.modules.get("study")
        if study is not None and app.is_on("study"):
            t = study.totals(7)
            if t:
                name = app.modules["subjects"].name_of
                per = ", ".join(f"{name(k)} {v / 3600:.1f} h" for k, v in sorted(t.items(), key=lambda kv: -kv[1]))
                steps.append(f"Study hours per subject this week: {per}. Ask how that compares with what they wanted.")
        steps.append("Ask what went well this week, and what didn't.")
        steps.append("Ask if there's anything Kurooto should do differently (save it with remember, if you have it).")
        dl = app.modules.get("deadlines")
        soon = getattr(dl, "deadlines_soon", None) if dl is not None and app.is_on("deadlines") else None
        due = []
        if soon:
            try:
                due = soon(hours=7 * 24) or []
            except Exception as e:
                app.events.emit("weekly_script_failed", error=str(e)[:200])
        listed = "; ".join(f"{d.get('title')} ({d.get('when') or d.get('due', '')})" for d in due[:10])
        steps.append(
            (f"Next week: {listed}. " if listed else "Next week: ")
            + "Ask their top priorities for next week, per subject if they have classes."
        )
        steps.append(
            "Wrap up warmly. Don't write notes yourself: the review goes into their journal after the call."
            if daily.ai_on(app)
            else "Wrap up warmly. What they said goes into their journal after the call."
        )
        head = "Sunday review, about 15 minutes. Go step by step and keep it in their words."
        return "\n".join([head] + [f"{i}. {s}" for i, s in enumerate(steps, 1)])

    def call_outcome(self, key: str, outcome: str) -> bool:
        return False  # missed: the text summary is already there

    def call_transcript(self, key: str, lines: list[dict]) -> None:
        """After the review call: a weekly review in the journal (by the AI with Chat on; your words otherwise)."""
        said = daily.their_words(self.app, lines)
        if not said:
            return
        if daily.ai_on(self.app):
            jid = daily.run_skill(
                self.app,
                "journal",
                "Weekly review, from my Sunday review call (write it up as a weekly review, with next week's "
                f"priorities as a list):\n\n{daily.transcript(self.app, lines)}",
                title="Weekly review from your call",
            )
            if jid:
                return
        daily.append(self.app, f"Weekly review, by call ({now():%H:%M})", said)

    def call_tools(self):
        return [
            Tool(
                "weekly_summary",
                "The week in numbers (messages, reminders, check-ins, deadlines, quiz).",
                lambda a: self.summary(),
            ),
            Tool(
                "weekly_review",
                "The steps for the Sunday review call, with the week's numbers and next week's deadlines.",
                lambda a: self.script(),
                offline="brief",
                hint="On the Sunday review call, first call weekly_review and follow it.",
            ),
        ]

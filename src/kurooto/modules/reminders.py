"""Reminders: "remind me at 9 to call mum", "remind me in 20 minutes to take the tea off", /remind tomorrow 7am gym.
They arrive on Telegram. If the computer was asleep at the time, the reminder still comes when it wakes, marked
late; with Reminders with the lid shut on, your phone gets it at its time instead (lidsafe.py)."""

from __future__ import annotations

import datetime as dt
import re
import time
import uuid

from kurooto.core.clock import now, parse_when
from kurooto.modules.base import Command, Incoming, Intent, Module
from kurooto.modules.calls.tools import Tool, arg
from kurooto.modules.text import NEG, when_from

REMIND = re.compile(r"^\s*remind me\s+(?P<rest>.+)$", re.I)
WHEN_WORDS = re.compile(
    r"\b(?:in\s+\d+(?:\.\d+)?\s*[a-z]+|in\s+(?:an?|half an?)\s+[a-z]+|(?:at|by)\s+\d{1,2}(?:[:.]\d{2})?\s*(?:am|pm)?"
    r"|\d{1,2}(?:[:.]\d{2})\s*(?:am|pm)?|\d{1,2}\s*(?:am|pm)|tomorrow|tonight|today)\b",
    re.I,
)


class Reminders(Module):
    id = "reminders"
    title = "Reminders"
    description = 'Plain English: "remind me at 9 to call mum". They arrive on Telegram, even after the laptop slept.'
    requires = ("telegram",)

    def __init__(self, app):
        super().__init__(app)
        # registered at once: a reminder set in the setup page's try-it box (web/tryit.py), before this feature is
        # on, still fires after a restart
        app.scheduler.action("reminders.fire", self._fire)

    def start(self):
        self.action("fire", self._fire)

    def add(self, when: dt.datetime, what: str) -> str:
        key = f"reminders:{uuid.uuid4().hex[:8]}"
        self.app.scheduler.action("reminders.fire", self._fire)
        self.app.scheduler.at(
            when, "reminders.fire", {"what": what, "ref": key.split(":", 1)[1]}, key=key, module=self.id
        )
        self.app.events.emit("reminder_set", at=when.isoformat())
        self._lidsafe_poke()
        return f"I'll remind you {when:%a %d %b at %H:%M}: {what}"

    def _lidsafe(self):
        """Reminders with the lid shut (lidsafe.py), when it's on: your call line holds the next day's reminders."""
        m = self.app.modules.get("lidsafe")
        return m if m is not None and self.app.is_on("lidsafe") else None

    def _lidsafe_poke(self) -> None:
        m = self._lidsafe()
        if m is not None:
            m.poke()

    def _fire(self, p: dict):
        ls = self._lidsafe()
        if ls is not None and ls.handed_over("reminders.fire", p):
            return  # your call line has a sealed copy: whichever side is awake now says it, once (lidsafe.py)
        what = p.get("what", "")
        late = " (late: the computer was asleep)" if p.get("late_s") or p.get("missed") else ""
        ref = uuid.uuid4().hex[:8]
        self._snoozable(ref, what)
        self.app.notify(
            f"Reminder{late}: {what}",
            kind="reminder",
            buttons=[[("+10 min", f"rem:{ref}:10"), ("+1 h", f"rem:{ref}:60")]],
        )
        self.app.events.emit("reminder_fired", late=bool(late))

    def _snoozable(self, ref: str, what: str) -> None:
        from kurooto.core.state import jload, jsave

        f = self.app.paths.state / "reminders-snooze.json"
        d = jload(f, {}) or {}
        d[ref] = what
        jsave(f, dict(list(d.items())[-200:]))

    def callbacks(self):
        return {"rem": self._snooze, "remx": self._cancel}

    def _snooze(self, ref: str, act: str) -> str:
        from kurooto.core.state import jload

        what = (jload(self.app.paths.state / "reminders-snooze.json", {}) or {}).get(ref)
        if not what:
            return "That reminder is gone."
        when = now() + dt.timedelta(minutes=int(act or 10))
        self.add(when, what)
        return f"Again at {when:%H:%M}"

    def _cancel(self, ref: str, act: str) -> str:
        gone = self.app.scheduler.cancel(f"reminders:{ref}")
        self._lidsafe_poke()
        return "Cancelled." if gone else "Already gone."

    # ------------------------------------------------------------------------------- plain English
    def intents(self):
        def match(text: str):
            m = REMIND.match(text)
            if not m or NEG.search(text):
                return None
            rest = m["rest"]
            when = when_from(rest)
            if not when:
                return None
            what = WHEN_WORDS.sub("", rest)
            what = re.sub(r"^\s*(?:to|that|about)\s+", "", re.sub(r"\s+", " ", what).strip(" ,.")).strip(" ,.")
            return {"when": when, "what": what or "you asked me to remind you"}

        return [Intent("remind", "set a reminder", match, lambda msg, s: self.add(s["when"], s["what"]))]

    def commands(self):
        return [
            Command("remind", "a reminder (/remind 21:30 call mum, /remind tomorrow 7am gym)", self._cmd),
            Command("reminders", "your upcoming reminders", self._list),
        ]

    def _cmd(self, msg: Incoming, arg: str) -> str:
        parts = arg.split()
        for n in (3, 2, 1):  # "tomorrow 7am gym", "in 20m tea", "21:30 call mum"
            if len(parts) >= n:
                try:
                    when = parse_when(" ".join(parts[:n]))
                except ValueError:
                    continue
                return self.add(when, " ".join(parts[n:]) or "you asked me to remind you")
        return "Usage: /remind 21:30 call mum   (or: tomorrow 7am gym, in 20m tea)"

    def _list(self, msg: Incoming, arg: str) -> str | None:
        jobs = self.app.scheduler.jobs("reminders:")
        if not jobs:
            return "No reminders set."
        for j in jobs[:15]:
            msg.reply(
                f"{j.when.astimezone():%a %d %b %H:%M}  {j.payload.get('what')}",
                buttons=[[("Cancel", f"remx:{j.key.split(':', 1)[1]}:x")]],
            )
        return None

    def help(self):
        return ['"remind me at 9 to …", /remind, /reminders']

    # -------------------------------------------------------------------------------------- on calls
    def call_tools(self):
        return [
            Tool(
                "add_reminder",
                'A reminder message at a time, e.g. when "18:30", "in 2 hours", "tomorrow 9am".',
                self._tool_add,
                {"when": arg(), "what": arg("what to remind them of")},
                ("when", "what"),
                offline="queue",
                hint="add_reminder sets a reminder message; schedule_call is for a reminder call instead.",
            )
        ]

    def _tool_add(self, a: dict) -> str:
        try:
            when = parse_when(str(a.get("when", "")))
        except ValueError:
            return f"I couldn't read the time {a.get('when')!r}."
        return self.add(when, str(a.get("what") or "a reminder"))

    def call_brief(self) -> dict:
        soon = [j for j in self.app.scheduler.jobs("reminders:") if j.next_run < time.time() + 86400]
        if not soon:
            return {}
        return {
            "reminders_next_24h": [
                f"{dt.datetime.fromtimestamp(j.next_run):%a %H:%M} {j.payload.get('what', '')}" for j in soon[:8]
            ]
        }

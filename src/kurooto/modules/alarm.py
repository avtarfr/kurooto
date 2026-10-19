"""Morning alarm: Kurooto wakes you with a call. On the Android app it rings with your alarm sound on the alarm
stream (so it rings on silent); answer and it says good morning and goes through your day. The call is placed by
your call line, so it rings even if this computer is asleep or off.

Set it in plain English ("wake me at 6:45", "set my alarm for 7 tomorrow", "cancel my alarm"), with /alarm, on a
call ("set my alarm for 7"), or as a daily default in Settings. Not answered: it rings again 5 minutes later, up to
twice more. "Later" on the ringing call snoozes for 10 minutes.
"""

from __future__ import annotations

import datetime as dt
import re

from kurooto.core.clock import now, parse_when
from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave
from kurooto.modules.base import Command, Incoming, Intent, Module
from kurooto.modules.calls.tools import Tool, arg

register_defaults(
    "alarm",
    {
        "daily": None,  # "07:00" rings every day (on the days below) unless you set another time; None = off
        "days": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
        "reason": "Wake-up call: say good morning, then go through today briefly and ask what's first.",
        "retries": 2,
        "snooze_min": 10,
    },
)
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
KEY = "alarm:next"


class Alarm(Module):
    id = "alarm"
    title = "Morning alarm"
    description = "Kurooto wakes you with a call that rings like an alarm, even if this computer is asleep."
    requires = ("calls",)
    privacy = "The alarm time is kept on your call line so it can ring while this computer is off."

    @property
    def file(self):
        return self.app.paths.state / "alarm.json"

    def start(self):
        self.action("ring", self._ring)
        self.every("plan", "daily 00:02", lambda p: self._plan())
        self._plan()

    def next(self) -> dt.datetime | None:
        j = self.app.scheduler.get(f"{self.id}:ring")
        return dt.datetime.fromtimestamp(j.next_run) if j else None

    def _plan(self) -> None:
        """The daily default: schedule today's (or tomorrow's) alarm unless one is already set."""
        t = self.setting("daily")
        if not t or self.next():
            return
        base = now()
        for add in (0, 1):
            day = base.date() + dt.timedelta(days=add)
            at = dt.datetime.combine(day, dt.time.fromisoformat(t))
            if DAYS[day.weekday()] in (self.setting("days") or DAYS) and at > base.replace(tzinfo=None):
                self.set(at, daily=True)
                return

    def set(self, at: dt.datetime, daily: bool = False, tries: int = 0) -> str:
        self.app.scheduler.at(
            at, "alarm.ring", {"tries": tries}, key=f"{self.id}:ring", module=self.id, grace_s=1800, respect="none"
        )
        jsave(self.file, {"at": at.isoformat(), "daily": daily})
        self._poke()
        self.app.events.emit("alarm_set", at=at.isoformat())
        return f"Alarm set for {at:%a %d %b, %H:%M}."

    def clear(self) -> str:
        had = self.app.scheduler.cancel(f"{self.id}:ring")
        jsave(self.file, {})
        self._poke()
        return "Alarm off." if had else "There was no alarm set."

    def _poke(self) -> None:
        calls = self.app.modules.get("calls")
        if calls:
            calls.connector.poke()

    def _ring(self, p: dict) -> None:
        if p.get("missed") or p.get("late_s"):  # this computer was asleep then; the call line rang it already
            return
        jsave(self.file, {**(jload(self.file, {}) or {}), "tries": p.get("tries", 0)})
        self.app.modules["calls"].ring(self.setting("reason") or "Wake-up call", alarm=True, key=KEY)

    # --------------------------------------------------------------------------- what the call line hears
    def call_schedule(self) -> list[dict]:
        at = self.next()
        if not at:
            return []
        return [
            {"at": int(at.timestamp()), "reason": self.setting("reason") or "Wake-up call", "alarm": True, "key": KEY}
        ]

    def call_outcome(self, key: str, outcome: str) -> bool:
        tries = (jload(self.file, {}) or {}).get("tries", 0)
        if outcome == "later":
            self.set(now().replace(tzinfo=None) + dt.timedelta(minutes=self.setting("snooze_min") or 10))
            return True
        if outcome == "missed" and tries < (self.setting("retries") or 0):
            self.set(now().replace(tzinfo=None) + dt.timedelta(minutes=5), tries=tries + 1)
            return True
        if outcome in ("answered", "skip", "decline"):
            jsave(self.file, {})
        return False

    def call_tools(self):
        return [
            Tool(
                "set_alarm",
                'Set the wake-up alarm (a call that rings like an alarm), e.g. "7:30" or "tomorrow 6:45"; '
                '"off" clears it.',
                self._tool,
                {"time": arg()},
                ("time",),
                offline="queue",
                hint="set_alarm sets the wake-up call; in an evening call, ask when to wake them and set it.",
            )
        ]

    def call_brief(self) -> dict:
        at = self.next()
        return {"alarm": f"{at:%a %H:%M}"} if at else {}

    def _tool(self, a: dict) -> str:
        t = str(a.get("time", "")).strip()
        if re.fullmatch(r"(?i)off|none|cancel|clear", t):
            return self.clear()
        try:
            return self.set(parse_when(t).replace(tzinfo=None))
        except ValueError:
            return f"I couldn't read {t!r}."

    # -------------------------------------------------------------------------------------- telegram
    def commands(self):
        return [Command("alarm", "the wake-up call: /alarm 6:45, /alarm tomorrow 7, /alarm off", self._cmd)]

    def _cmd(self, msg: Incoming, arg: str) -> str:
        if not arg:
            at = self.next()
            return f"Alarm: {at:%a %d %b, %H:%M}." if at else "No alarm set. /alarm 6:45 sets one."
        return self._tool({"time": arg})

    def intents(self):
        set_pat = re.compile(
            r"^(?:please )?(?:wake me(?: up)?|set (?:an |my |the )?alarm(?: for)?) (?:at |for |in )?(.+)$", re.I
        )
        off_pat = re.compile(r"^(?:cancel|turn off|delete|remove|clear|no) (?:my |the )?alarm\b", re.I)

        def match(text: str):
            t = text.strip().rstrip(".!")
            if off_pat.match(t):
                return {"off": True}
            m = set_pat.match(t)
            if not m:
                return None
            try:
                return {"at": parse_when(m.group(1)).replace(tzinfo=None)}
            except ValueError:
                return None

        return [
            Intent(
                "alarm", "wake me at …", match, lambda msg, sl: self.clear() if sl.get("off") else self.set(sl["at"])
            )
        ]

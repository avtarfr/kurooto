"""Morning alarm: Kurooto wakes you with a call. On the Android app it rings with your alarm sound on the alarm
stream (so it rings on silent); answer and it says good morning and goes through your day. The call is placed by
your call line, so it rings even if this computer is asleep or off.

Set it in plain English ("wake me at 6:45", "set my alarm for 7 tomorrow", "cancel my alarm"), with /alarm, on a
call ("set my alarm for 7"), or as a daily default in Settings. Not answered: it rings again 5 minutes later, up to
twice more. "Later" on the ringing call snoozes for 10 minutes.

While it's set, the night runs from your bedtime until the alarm: no other calls then, and once you're up they can
come. With Chat on, 20 minutes before the alarm the AI drafts the day's plan into today's daily note (the
morning-prep skill); the call goes through it with you, and if this computer is awake it opens the morning page.
"""

from __future__ import annotations

import datetime as dt
import os
import re
import sys

from kurooto.core.clock import now, parse_when
from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave
from kurooto.modules import daily
from kurooto.modules.base import Command, Incoming, Intent, Module
from kurooto.modules.calls.tools import Tool, arg

register_defaults(
    "alarm",
    {
        "daily": None,  # "07:00" rings every day (on the days below) unless you set another time; None = off
        "days": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
        "reason": "Wake-up call",
        "retries": 2,
        "snooze_min": 10,
        "bedtime": None,  # "23:00": with the alarm set, no calls from then until it rings; None = the night's start
        "prep_min": 20,  # with Chat on: the AI drafts the day's plan this long before the alarm; 0 = don't
        "open_page": True,  # at the alarm, open the morning page on this computer if it's awake
        "notes": True,  # after the wake-up call: today's plan (with Chat on) or what you said, in the daily note
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

    @property
    def last_file(self):
        return self.app.paths.state / "alarm-last.json"

    def start(self):
        self.action("ring", self._ring)
        self.action("prep", self._prep)
        self.every("plan", "daily 00:02", lambda p: self._plan())
        self.app.availability.sleep = self.sleep_windows
        self._plan()

    def stop(self):
        super().stop()
        if self.app.availability.sleep == self.sleep_windows:
            self.app.availability.sleep = None

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

    def set(self, at: dt.datetime, daily: bool = False, tries: int = 0, first: bool = True) -> str:
        """Set the alarm. first=False for a snooze or a repeat ring: no new plan, no morning page."""
        self.app.scheduler.at(
            at,
            "alarm.ring",
            {"tries": tries, "first": first},
            key=f"{self.id}:ring",
            module=self.id,
            grace_s=1800,
            respect="none",
        )
        jsave(self.file, {"at": at.isoformat(), "daily": daily, "set_at": now().isoformat()})
        mins = self.setting("prep_min") or 0
        if first and mins:
            when = max(at - dt.timedelta(minutes=mins), now() + dt.timedelta(minutes=1))
            self.app.scheduler.at(
                when,
                "alarm.prep",
                {"day": at.date().isoformat(), "at": f"{at:%H:%M}"},
                key=f"{self.id}:prep",
                module=self.id,
                grace_s=1800,
            )
        self._poke()
        self.app.events.emit("alarm_set", at=at.isoformat())
        return f"Alarm set for {at:%a %d %b, %H:%M}."

    def clear(self) -> str:
        had = self.app.scheduler.cancel(f"{self.id}:ring")
        self.app.scheduler.cancel(f"{self.id}:prep")
        jsave(self.file, {})
        self._poke()
        return "Alarm off." if had else "There was no alarm set."

    # ---------------------------------------------------------------------------------- the night
    def sleep_windows(self) -> list[tuple[dt.datetime, dt.datetime]]:
        """The nights the alarm covers, (bedtime, alarm): the coming one, and the one that just ended (so the fixed
        night hours don't hold calls after you're up)."""
        out = []
        at = self.next()
        if at:
            j = jload(self.file, {}) or {}
            out.append((self._bedtime(at, j), at))
        last = jload(self.last_file, {}) or {}
        try:
            was = dt.datetime.fromisoformat(last["at"])
        except (KeyError, ValueError, TypeError):
            was = None
        if was and now() - dt.timedelta(hours=18) < was <= now():
            out.append((self._bedtime(was, last), was))
        return out

    def _bedtime(self, at: dt.datetime, info: dict) -> dt.datetime:
        night = self.app.settings.get("availability.night") or {}
        try:
            bed = dt.time.fromisoformat(self.setting("bedtime") or night.get("from") or "23:30")
        except ValueError:
            bed = dt.time(23, 30)
        start = dt.datetime.combine(at.date(), bed)
        if start >= at:
            start -= dt.timedelta(days=1)
        start = max(start, at - dt.timedelta(hours=12))
        if not info.get("daily") and info.get("set_at"):  # an alarm set for a nap counts from when it was set
            try:
                start = max(start, dt.datetime.fromisoformat(info["set_at"]))
            except ValueError:
                pass
        return start

    # ----------------------------------------------------------------------------------- mornings
    def _prep(self, p: dict) -> None:
        """Before the alarm: the AI drafts the day's plan into the daily note (once a day)."""
        if p.get("missed") or not daily.ai_on(self.app):
            return
        day = dt.date.fromisoformat(p.get("day") or now().date().isoformat())
        if daily.has_section(self.app, "Plan", day):
            return
        jid = daily.run_skill(
            self.app,
            "morning-prep",
            f"Today is {day.isoformat()}; the alarm is at {p.get('at', '')}.",
            title="Drafting today's plan",
            quiet=True,
        )
        self.app.events.emit("morning_prep", started=bool(jid))

    def open_morning_page(self) -> bool:
        """Open the morning page in the browser, if this computer has a screen and the home page is running."""
        port = getattr(self.app, "web_port", None)
        if not port or not self.setting("open_page"):
            return False
        if sys.platform not in ("win32", "darwin") and not (
            os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
        ):
            return False
        import webbrowser

        try:
            return bool(webbrowser.open(f"http://127.0.0.1:{port}/morning"))
        except Exception:
            return False

    def script(self) -> str:
        """What the wake-up call goes through, with today's details."""
        app, today = self.app, now().date()
        steps = []
        plan = daily.plan(app, today, 2000)
        steps.append(
            f"Today's plan (drafted before the alarm):\n{plan}\nGo through it in a few sentences and ask its "
            "questions one at a time."
            if plan
            else "Ask what matters most today."
        )
        if app.is_on("subjects"):
            cls = app.modules["subjects"].classes_on(today)
            if cls:
                names = ", ".join(f"{c['name']} ({c['start']})" for c in cls)
                steps.append(f"Today's classes: {names}. Ask which they're skipping, if any (skip_class).")
        if app.is_on("calendar"):
            evs = app.modules["calendar"].call_brief().get("calendar_today")
            if evs:
                steps.append("In their calendar today: " + "; ".join(evs[:8]) + ".")
        dl = app.modules.get("deadlines")
        soon = getattr(dl, "deadlines_soon", None) if dl is not None and app.is_on("deadlines") else None
        if soon:
            try:
                due = soon(hours=72) or []
            except Exception:
                due = []
            if due:
                steps.append("Due soon: " + "; ".join(f"{d.get('title')} ({d.get('when', '')})" for d in due[:6]) + ".")
        if app.is_on("checkins"):
            plan_today = app.modules["checkins"].today()
            ev = (plan_today.get("evening") or {}).get("time")
            steps.append(
                (f"Ask when to call today: the evening check-in is at {ev}" if ev else "Ask when to call this evening")
                + " (change_checkin moves or skips it), and whether they want a midday check-in."
            )
        steps.append("Wish them a good day.")
        head = "Wake-up call. Say good morning, briefly and warmly; they've just woken up, so keep it light."
        return "\n".join([head] + [f"{i}. {x}" for i, x in enumerate(steps, 1)])

    def call_transcript(self, key: str, lines: list[dict]) -> None:
        """After the wake-up call: with Chat on, the AI settles today's plan in the daily note from what you said;
        without it, your words go there as they are."""
        if not self.setting("notes"):
            return
        said = daily.their_words(self.app, lines)
        if not said:
            return
        if daily.ai_on(self.app):
            jid = daily.run_skill(
                self.app,
                "morning",
                f"From my wake-up call:\n\n{daily.transcript(self.app, lines)}",
                title="Today's plan, from your wake-up call",
            )
            if jid:
                return
        daily.append(self.app, f"Wake-up call ({now():%H:%M})", said)

    def _poke(self) -> None:
        calls = self.app.modules.get("calls")
        if calls:
            calls.connector.poke()

    def _ring(self, p: dict) -> None:
        j = jload(self.file, {}) or {}
        first = p.get("first", True)
        if j.get("at") and first:  # the night this alarm ends (snoozes and repeat rings keep the first one's)
            jsave(self.last_file, {k: j.get(k) for k in ("at", "daily", "set_at")})
        if p.get("missed") or p.get("late_s"):  # this computer was asleep then; the call line rang it already
            return
        jsave(self.file, {**j, "tries": p.get("tries", 0)})
        self.app.modules["calls"].ring(self.setting("reason") or "Wake-up call", alarm=True, key=KEY)
        if first:
            self.app.events.emit("alarm_rang", page=self.open_morning_page())

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
            self.set(now().replace(tzinfo=None) + dt.timedelta(minutes=self.setting("snooze_min") or 10), first=False)
            return True
        if outcome == "missed" and tries < (self.setting("retries") or 0):
            self.set(now().replace(tzinfo=None) + dt.timedelta(minutes=5), tries=tries + 1, first=False)
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
            ),
            Tool(
                "morning_plan",
                "The steps for the wake-up call: today's drafted plan, classes, what's due, when to call later.",
                lambda a: self.script(),
                offline="brief",
                hint="On the wake-up call, first call morning_plan and follow it.",
            ),
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

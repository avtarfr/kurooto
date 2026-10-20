"""Morning alarm: Kurooto wakes you with a call. On the Android app it rings with your alarm sound on the alarm
stream (so it rings on silent); answer and it says good morning and goes through your day. The call is placed by
your call line, so it rings even if this computer is asleep or off.

Set it in plain English ("wake me at 6:45", "set my alarm for 7 tomorrow", "cancel my alarm"), with /alarm, on a
call ("set my alarm for 7"), or as a daily default in Settings. Not answered: it rings again 5 minutes later, up to
twice more. "Later" on the ringing call snoozes for 10 minutes.

The daily alarm: the next one is always with your call line well before the night (planned as soon as one has rung,
and again at start and after this computer wakes), so it rings even if this computer sleeps all night. One alarm per
morning: an alarm you set for a morning replaces the daily one. "No alarm tomorrow" (or "cancel tomorrow's alarm",
"/alarm skip friday") skips one day and the daily alarm is back after it; "cancel my alarm" skips the one that's set;
"turn my daily alarm off" (/alarm daily off) stops it, and "/alarm daily 7:00" sets it.

While it's set, the night runs from your bedtime until the alarm: no other calls then, and once you're up they can
come. With Chat on, 20 minutes before the alarm the AI drafts the day's plan into today's daily note (the
morning-prep skill); the call goes through it with you, and if this computer is awake it opens the morning page.

Keep awake (alarm.keep_awake, off unless you turn it on): this computer doesn't sleep in the 12 hours before the
alarm, until 15 minutes after it rings (or until you answer), so the plan is drafted in time even if it would have
gone to sleep overnight. On Linux it keeps running with the lid closed too; a Mac sleeps when its lid is closed, and
Windows follows its own lid setting. Plug it in: it stays awake all night.
"""

from __future__ import annotations

import datetime as dt
import os
import re
import sys

from kurooto.core.clock import now, parse_when
from kurooto.core.config import register_defaults
from kurooto.core.inhibit import Inhibitor
from kurooto.core.power import on_ac
from kurooto.core.state import jload, jsave
from kurooto.modules import daily
from kurooto.modules.base import Command, Incoming, Intent, Module
from kurooto.modules.calls.tools import Tool, arg
from kurooto.modules.text import a_day

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
        "keep_awake": False,  # keep this computer awake until the alarm (Linux: lid closed too), so the plan is drafted
    },
)
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
KEY = "alarm:next"
PLAN_EVERY = "every 30m"  # the next daily alarm is checked this often too (and caught up after sleep)
AWAKE_AFTER_MIN = 15  # keep_awake holds until this long after the alarm (repeat rings, the plan)
AWAKE_BEFORE_H = 12  # ... from this long before it (a daily alarm set in the morning doesn't hold all day)


def _clock_time(text: str) -> str | None:
    """A time of day as written ("6:30", "7", "6:30am", "18:00") -> "HH:MM"; None if it isn't one."""
    m = re.fullmatch(r"(?:at )?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", text.strip().lower())
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2) or 0)
    h += 12 if m.group(3) == "pm" and h < 12 else 0
    h -= 12 if m.group(3) == "am" and h == 12 else 0
    return f"{h:02d}:{mi:02d}" if h < 24 and mi < 60 else None


class Alarm(Module):
    id = "alarm"
    title = "Morning alarm"
    description = "Kurooto wakes you with a call that rings like an alarm, even if this computer is asleep."
    requires = ("calls",)
    privacy = "The alarm time is kept on your call line so it can ring while this computer is off."

    def __init__(self, app):
        super().__init__(app)
        self.inhibitor = Inhibitor(why="Morning alarm: drafting your day before it rings")
        self.on_ac = on_ac

    @property
    def file(self):
        return self.app.paths.state / "alarm.json"

    @property
    def last_file(self):
        return self.app.paths.state / "alarm-last.json"

    @property
    def ringing_file(self):  # the ring in progress: its repeat count (planning the next day doesn't touch it)
        return self.app.paths.state / "alarm-ringing.json"

    @property
    def skip_file(self):  # days the daily alarm doesn't ring ("no alarm tomorrow")
        return self.app.paths.state / "alarm-skip.json"

    def start(self):
        self.action("ring", self._ring)
        self.action("prep", self._prep)
        self.action("awake", lambda p: self.keep_awake())
        self.every("plan", PLAN_EVERY, lambda p: self._plan())
        self.app.availability.sleep = self.sleep_windows
        self._plan()
        self.keep_awake()

    def stop(self):
        super().stop()
        self.inhibitor.release()
        if self.app.availability.sleep == self.sleep_windows:
            self.app.availability.sleep = None

    def health(self):
        ok, why = self.ready()
        if not ok or not self.setting("keep_awake"):
            return ok, why
        can, msg = self.inhibitor.supported()
        if not can:
            return True, f"can't keep this computer awake until the alarm: {msg}"
        held = self.inhibitor.describe()
        return True, f"keeping this computer {held}" if held else ""

    def keep_awake(self) -> bool:
        """With alarm.keep_awake: hold this computer awake until the alarm (and a little after), else let it sleep.
        The hold ends by itself, even if Kurooto stops. True while it's held."""
        after = dt.timedelta(minutes=AWAKE_AFTER_MIN)
        windows = []  # (from, until)
        at = self.next()
        if at:
            windows.append((at - dt.timedelta(hours=AWAKE_BEFORE_H), at + after))
        last = jload(self.last_file, {}) or {}
        try:
            if not last.get("done"):  # the morning that just rang, until you answered
                was = dt.datetime.fromisoformat(last["at"])
                windows.append((was, was + after))
        except (KeyError, ValueError, TypeError):
            pass
        self.app.scheduler.cancel(f"{self.id}:awake")
        t = now()
        until = max((end for start, end in windows if start <= t < end), default=None)
        later = min((start for start, end in windows if start > t), default=None)
        if not self.setting("keep_awake") or not until:
            self.inhibitor.release()
            if self.setting("keep_awake") and later:  # not yet: from 12 hours before
                self.app.scheduler.at(later, "alarm.awake", key=f"{self.id}:awake", module=self.id, grace_s=86400)
            return False
        return self.inhibitor.hold((until - t).total_seconds(), lid=True)

    def next(self) -> dt.datetime | None:
        j = self.app.scheduler.get(f"{self.id}:ring")
        return dt.datetime.fromtimestamp(j.next_run) if j else None

    # ------------------------------------------------------------------------------------ the daily alarm
    def skips(self) -> set[dt.date]:
        out = set()
        for d in (jload(self.skip_file, {}) or {}).get("days", []):
            try:
                out.add(dt.date.fromisoformat(d))
            except ValueError:
                pass
        return {d for d in out if d >= now().date()}

    def _skip_add(self, day: dt.date) -> None:
        jsave(self.skip_file, {"days": sorted(x.isoformat() for x in self.skips() | {day})})

    def next_daily(self) -> dt.datetime | None:
        """When the daily alarm rings next: on one of its days, not a day you skipped, not a morning that already
        had an alarm (one in the 6 hours before it, or after; a nap after midnight doesn't count)."""
        try:
            tm = dt.time.fromisoformat(self.setting("daily") or "")
        except ValueError:
            return None
        days, skip, t = self.setting("days") or DAYS, self.skips(), now()
        try:
            rang = dt.datetime.fromisoformat((jload(self.last_file, {}) or {})["at"])
        except (KeyError, ValueError, TypeError):
            rang = None
        for add in range(9):
            day = t.date() + dt.timedelta(days=add)
            at = dt.datetime.combine(day, tm)
            had = rang is not None and rang.date() == day and rang >= at - dt.timedelta(hours=6)
            if at > t and DAYS[day.weekday()] in days and day not in skip and not had:
                return at
        return None

    def _plan(self, ringing: bool = False) -> None:
        """Keep the next daily alarm set (and on your call line). An alarm you set stays; a daily one follows the
        settings (time, days, off). ringing: the alarm's own ring is running now, so it doesn't count as set."""
        pending = None if ringing else self.next()
        if pending and pending <= now():
            return  # due: its ring runs (catching up after sleep) and plans the next one
        info = jload(self.file, {}) or {}
        if pending and not info.get("daily"):
            return
        want = self.next_daily()
        if pending and want == pending:
            return
        if pending and not want:  # the daily alarm was turned off, or has no days left
            self.app.scheduler.cancel(f"{self.id}:ring")
            self.app.scheduler.cancel(f"{self.id}:prep")
            jsave(self.file, {})
            self._poke()
            self.keep_awake()
            return
        if want:
            self.set(want, daily=True)

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
        if self.keep_awake() and first and not self.on_ac():
            return f"Alarm set for {at:%a %d %b, %H:%M}. Plug this computer in: it stays awake until then."
        return f"Alarm set for {at:%a %d %b, %H:%M}."

    def clear(self) -> str:
        """ "Cancel my alarm": the one that's set. With a daily alarm, that morning is skipped (it would come back)."""
        at = self.next()
        had = self.app.scheduler.cancel(f"{self.id}:ring")
        self.app.scheduler.cancel(f"{self.id}:prep")
        jsave(self.file, {})
        if at and at > now() and self.setting("daily"):
            self._skip_add(at.date())
        self._plan()
        self._poke()
        self.keep_awake()
        if not had:
            return "There was no alarm set."
        nxt = self.next()
        if nxt and at:
            return (
                f'Alarm off for {at:%a %d %b}. Your daily alarm is back {nxt:%a %d %b, %H:%M} ("turn my daily '
                'alarm off" stops it).'
            )
        return "Alarm off."

    def skip(self, day: dt.date) -> str:
        """No alarm on that day (the daily one comes back after it)."""
        self._skip_add(day)
        at = self.next()
        if at and at.date() == day and at > now():
            self.app.scheduler.cancel(f"{self.id}:ring")
            self.app.scheduler.cancel(f"{self.id}:prep")
            jsave(self.file, {})
        self._plan()
        self._poke()
        self.keep_awake()
        self.app.events.emit("alarm_skipped", day=day.isoformat())
        nxt = self.next()
        return f"No alarm on {day:%a %d %b}." + (f" Next: {nxt:%a %d %b, %H:%M}." if nxt else "")

    def set_daily(self, hhmm: str | None) -> str:
        """The daily alarm's time, or None to turn it off (a morning's alarm you set yourself stays)."""
        self.app.settings.set("alarm.daily", hhmm)
        self._plan()
        self.app.events.emit("alarm_daily", at=hhmm or "off")
        if not hhmm:
            nxt = self.next()
            return "Daily alarm off." + (f" The one you set stays: {nxt:%a %d %b, %H:%M}." if nxt else "")
        nxt = self.next()
        return f"Daily alarm at {hhmm}." + (f" Next: {nxt:%a %d %b, %H:%M}." if nxt else "")

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
        ck = app.modules.get("checkins")
        deferred = ck.deferred_steps() if ck is not None and app.is_on("checkins") else ""
        if deferred:
            steps.append(deferred)
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
                due = soon() or []  # deadlines.plan_h ahead
            except Exception:
                due = []
            if due:
                steps.append("Due soon: " + "; ".join(f"{d.get('title')} ({d.get('when', '')})" for d in due[:6]) + ".")
        sb = app.modules.get("startby")
        if sb is not None and app.is_on("startby"):
            try:
                start = sb.morning_lines()  # start-by dates that have come (modules/startby.py)
            except Exception:
                start = []
            if start:
                steps.append(
                    "Time to start (an estimate): " + "; ".join(start[:4]) + ". Ask which they'll begin today."
                )
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

    def call_reschedule(self, key: str, at: dt.datetime) -> str:
        """ "Call me back in ten minutes" on the wake-up call: the alarm again then (like a snooze)."""
        return self.set(at.replace(tzinfo=None), first=False)

    def call_transcript(self, key: str, lines: list[dict]) -> None:
        """After the wake-up call: with Chat on, the AI settles today's plan in the daily note from what you said;
        without it, your words go there as they are."""
        ck = self.app.modules.get("checkins")
        if ck is not None and self.app.is_on("checkins"):
            ck.take_deferred(lines)  # last night's check-in, if it was moved to this call
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
            self._plan(ringing=True)  # the next one goes to the line now
            return
        jsave(self.ringing_file, {"tries": p.get("tries", 0)})
        if first:
            self._plan(ringing=True)  # tomorrow's is with the line already (a repeat ring takes its place a while)
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
        tries = (jload(self.ringing_file, {}) or {}).get("tries", 0)
        if outcome == "later":
            self.set(now().replace(tzinfo=None) + dt.timedelta(minutes=self.setting("snooze_min") or 10), first=False)
            return True
        if outcome == "missed" and tries < (self.setting("retries") or 0):
            self.set(now().replace(tzinfo=None) + dt.timedelta(minutes=5), tries=tries + 1, first=False)
            return True
        self.ringing_file.unlink(missing_ok=True)  # this morning's alarm is over: the next one goes to the line
        if outcome in ("answered", "skip", "decline"):
            last = jload(self.last_file, {}) or {}
            if last:
                jsave(self.last_file, {**last, "done": True})  # you're up (or chose not to be): it may sleep again
        nxt = self.next()
        if nxt is None or nxt <= now():
            jsave(self.file, {})
            self._plan(ringing=True)
        self.keep_awake()
        return False

    def call_tools(self):
        return [
            Tool(
                "set_alarm",
                'Set the wake-up alarm (a call that rings like an alarm), e.g. "7:30" or "tomorrow 6:45"; '
                '"off" clears the one that\'s set; "skip tomorrow" or "skip friday": no alarm that day (the daily '
                'one comes back after); "daily 7:00" or "daily off": the daily alarm.',
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
        m = re.fullmatch(r"(?i)daily\s+(.+)", t)
        if m:
            if re.fullmatch(r"(?i)off|none|stop|no", m.group(1).strip()):
                return self.set_daily(None)
            hhmm = _clock_time(m.group(1))
            return self.set_daily(hhmm) if hhmm else f"I couldn't read {m.group(1)!r}."
        m = re.fullmatch(r"(?i)(?:skip|no alarm|none|off)\s+(?:on\s+)?(.+)", t)
        if m:
            day = self._day(m.group(1))
            return self.skip(day) if day else f"I couldn't tell which day {m.group(1)!r} is."
        try:
            return self.set(parse_when(t).replace(tzinfo=None))
        except ValueError:
            return f"I couldn't read {t!r}."

    # -------------------------------------------------------------------------------------- telegram
    def commands(self):
        return [
            Command(
                "alarm",
                "the wake-up call: /alarm 6:45, /alarm tomorrow 7, /alarm off, /alarm skip friday, "
                "/alarm daily 7:00 (or daily off)",
                self._cmd,
            )
        ]

    def _cmd(self, msg: Incoming, arg: str) -> str:
        if not arg:
            at = self.next()
            daily = self.setting("daily")
            tail = f" Daily: {daily}." if daily else ""
            return (f"Alarm: {at:%a %d %b, %H:%M}." if at else "No alarm set. /alarm 6:45 sets one.") + tail
        return self._tool({"time": arg})

    def intents(self):
        set_pat = re.compile(
            r"^(?:please )?(?:wake me(?: up)?|set (?:an |my |the )?alarm(?: for)?) (?:at |for |in )?(.+)$", re.I
        )
        off_pat = re.compile(r"^(?:cancel|turn off|delete|remove|clear|no) (?:my |the )?alarm\b", re.I)
        daily_off = re.compile(
            r"^(?:please )?(?:(?:turn|switch) (?:off )?(?:my |the )?daily alarm(?: off)?|(?:stop|disable|cancel|remove|"
            r"delete) (?:my |the )?daily alarm|no (?:more )?daily alarm)\b",
            re.I,
        )
        skip_pat = re.compile(
            r"^(?:please )?(?:(?:cancel|skip|turn off|delete|remove|clear|no) (?:my |the )?(?:(?P<a>[\w ]+?)'?s )?"
            r"alarm(?: (?:on |for )(?P<d>.+))?|no alarm (?:on |for )?(?P<b>.+)|(?:don'?t|do not) wake me(?: up)? "
            r"(?:on )?(?P<c>.+))$",
            re.I,
        )

        def match(text: str):
            t = text.strip().rstrip(".!")
            if daily_off.match(t):
                return {"daily_off": True}
            m = skip_pat.match(t)
            words = next((g for g in m.group("a", "b", "c", "d") if g), "") if m else ""
            if m and words:
                day = self._day(words)
                return {"skip": day} if day else None
            if off_pat.match(t):
                return {"off": True}
            m = set_pat.match(t)
            if not m:
                return None
            try:
                return {"at": parse_when(m.group(1)).replace(tzinfo=None)}
            except ValueError:
                return None

        def run(msg, sl):
            if sl.get("daily_off"):
                return self.set_daily(None)
            if sl.get("skip"):
                return self.skip(sl["skip"])
            return self.clear() if sl.get("off") else self.set(sl["at"])

        return [Intent("alarm", "wake me at …, no alarm tomorrow, turn my daily alarm off", match, run)]

    def _day(self, words: str) -> dt.date | None:
        """The morning a request names: "tomorrow" said at 2 am is the coming morning; "today", a weekday."""
        w = words.strip().lower()
        if re.fullmatch(r"(?:for )?today|(?:this )?morning", w):
            return now().date()
        if not re.search(r"\b(?:tomorrow|tmrw|tmr|mon|tue|wed|thu|fri|sat|sun)", w):
            return None
        try:
            start = dt.time.fromisoformat(self.app.settings.get("checkins.day_starts") or "05:00")
        except ValueError:
            start = dt.time(5, 0)
        base = now() - dt.timedelta(hours=start.hour, minutes=start.minute)  # still up after midnight
        return a_day(w, base)

"""Morning alarm: Kurooto wakes you with a call. On the Android app it rings with your alarm sound on the alarm
stream (so it rings on silent); answer and it says good morning and goes through your day. The call is placed by
your call line, so it rings even if this computer is asleep or off.

Set it in plain English ("wake me at 6:45", "set my alarm for 7 tomorrow", "cancel my alarm"), with /alarm, on a
call ("set my alarm for 7"), or as a daily default in Settings. Set as many as you like (up to MAX_SET): each one you
set is kept (alarm-set.json) and the soonest is the one that's set, the next taking its place once it has rung; your
call line holds them all. "Cancel my alarm" turns off the next one, "cancel the 10:30 alarm" that one, "cancel all my
alarms" every one you set (the daily alarm stays). Not answered: it rings again 5 minutes later, up to
twice more. "Later" on the ringing call snoozes for 10 minutes.

The daily alarm: the next one is always with your call line well before the night (planned as soon as one has rung,
and again at start and after this computer wakes), so it rings even if this computer sleeps all night. An alarm
you set for a morning replaces the daily one that morning. "No alarm tomorrow" (or "cancel tomorrow's alarm",
"/alarm skip friday") skips one day and the daily alarm is back after it; "cancel my alarm" skips the one that's set;
"turn my daily alarm off" (/alarm daily off) stops it, and "/alarm daily 7:00" sets it.

"I'm awake" (or "I just woke up", "I'm up", even with "call me if you need to …") rings the same morning run-through
now, from the current time: a plain call, not the alarm, and a time you mention about what didn't happen ("I didn't
wake up at 7") is never read as when to call.

While it's set, the night runs from your bedtime until the alarm: no other calls then, and once you're up they can
come. With Chat on, 20 minutes before the alarm the AI drafts the day's plan into today's daily note (the
morning-prep skill); the call goes through it with you, and if this computer is awake it opens the morning page.

No alarm set and your usual bedtime coming (alarm.suggest, on; learned by core/rhythm.py): within the hour before it,
one message, "You usually wake around 16:30; set an alarm?", with Set 16:30 / Not tonight. At most once a day; it never
sets one by itself.

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
from kurooto.modules.text import a_day, up_now

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
        "suggest": True,  # before your usual bedtime with no alarm set: one message suggesting your usual time
        # (0.9.0) up before the alarm (seen at the desk, using the dashboard or the phone app): one question, skip the
        # ring? It rings as set unless you tap Skip
        "skip_if_up": True,
        # (0.9.0, with Brain's sleep) up late before an alarm with a free morning after it: one suggestion of a later
        # ring (set only if you tap it); and after a short night the wake-up call keeps it light ("a short night")
        "sleep_aware": True,
    },
)
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
KEY = "alarm:next"
AWAKE_KEY = "alarm:awake"  # "I'm awake": the morning call, rung now (not the alarm: no snooze, no repeat rings)
PLAN_EVERY = "every 30m"  # the next daily alarm is checked this often too (and caught up after sleep)
AWAKE_AFTER_MIN = 15  # keep_awake holds until this long after the alarm (repeat rings, the plan)
AWAKE_BEFORE_H = 12  # ... from this long before it (a daily alarm set in the morning doesn't hold all day)
MAX_SET = 10  # alarms you set yourself, kept at once (the daily one isn't counted)
SUGGEST_MIN = 60  # the suggestion comes within this long before your usual bedtime
UP_LEAD_MIN = 60  # (skip_if_up) up within this long before the alarm: the question comes
UP_SEEN_MIN = 10  # (skip_if_up) a sign of you this recent counts as you being up
SHORT_H = 6.0  # (sleep_aware) less sleep than this before the alarm is a short night
NIGHT_H = 7.5  # (sleep_aware) a later ring is offered at about this long from now
CLASS_GAP_MIN = 60  # (sleep_aware) and at least this long before your first class
LATE_GAIN_MIN = 30  # (sleep_aware) only when that's at least this much later than the alarm


def _this_minute(at: dt.datetime) -> dt.datetime:
    """ "Alarm at 16:36" said at 16:36:20: that's now (in a few seconds), not tomorrow at 16:36."""
    t = now()
    if dt.timedelta(0) <= t - (at - dt.timedelta(days=1)) < dt.timedelta(minutes=1):
        return t + dt.timedelta(seconds=15)
    return at


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
    def set_file(self):  # the alarms you set yourself that haven't rung: [{"at", "set_at"}], the soonest is the one set
        return self.app.paths.state / "alarm-set.json"

    @property
    def skip_file(self):  # days the daily alarm doesn't ring ("no alarm tomorrow")
        return self.app.paths.state / "alarm-skip.json"

    def start(self):
        self.action("ring", self._ring)
        self.action("prep", self._prep)
        self.action("awake", lambda p: self.keep_awake())
        self.every("plan", PLAN_EVERY, lambda p: self._plan())
        self.every("suggest", "every 30m", lambda p: self.suggest() or self.phone_mismatch())
        self.every("up_ask", "every 5m", lambda p: self.ask_skip() or self.suggest_later())  # (0.9.0)
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

    def mine(self) -> list[dict]:
        """The alarms you set yourself that are still to come, soonest first: {"at": datetime, "set_at": str}."""
        out, t = {}, now()
        for a in (jload(self.set_file, {}) or {}).get("alarms", []):
            try:
                at = dt.datetime.fromisoformat(a["at"])
            except (KeyError, ValueError, TypeError):
                continue
            if at > t:
                out[at] = {"at": at, "set_at": a.get("set_at") or ""}
        return [out[k] for k in sorted(out)]

    def _mine_save(self, alarms: list[dict]) -> None:
        keep = sorted(alarms, key=lambda a: a["at"])[:MAX_SET]
        jsave(self.set_file, {"alarms": [{"at": a["at"].isoformat(), "set_at": a.get("set_at") or ""} for a in keep]})

    def _mine_drop(self, test) -> list[dict]:
        """Take the alarms you set that `test(at)` picks off the list. Returns them."""
        alarms = self.mine()
        gone = [a for a in alarms if test(a["at"])]
        self._mine_save([a for a in alarms if a not in gone])
        return gone

    def upcoming(self) -> list[dt.datetime]:
        """Every alarm still to ring: the one that's set, then the rest you set."""
        at = self.next()
        return sorted({*([at] if at and at > now() else []), *(a["at"] for a in self.mine())})

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
        mine = [a["at"] for a in self.mine()]
        for add in range(9):
            day = t.date() + dt.timedelta(days=add)
            at = dt.datetime.combine(day, tm)
            had = rang is not None and rang.date() == day and rang >= at - dt.timedelta(hours=6)
            had = had or any(m.date() == day and m >= at - dt.timedelta(hours=6) for m in mine)  # one you set
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
        mine = self.mine()
        if pending and not info.get("daily") and not (mine and mine[0]["at"] < pending):
            return  # one you set stays (the rest you set wait their turn)
        want, set_at = self.next_daily(), None
        if mine and (want is None or mine[0]["at"] <= want):
            want, set_at = mine[0]["at"], mine[0]["set_at"]
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
            self.set(want, daily=set_at is None, set_at=set_at)

    def set(
        self, at: dt.datetime, daily: bool = False, tries: int = 0, first: bool = True, set_at: str | None = None
    ) -> str:
        """Set an alarm. One you set joins the others you set; the soonest is the one set. first=False for a snooze
        or a repeat ring: no new plan, no morning page. set_at: when you set it (an alarm's turn coming)."""
        if first and not daily and set_at is None:  # you set it now
            alarms = [a for a in self.mine() if a["at"] != at]
            if len(alarms) >= MAX_SET:
                return f'You have {MAX_SET} alarms set already: /alarm shows them, "cancel the 7:00 alarm" frees one.'
            self._mine_save([*alarms, {"at": at, "set_at": now().isoformat()}])
            pending = self.next()
            info = jload(self.file, {}) or {}
            if pending and now() < pending < at and not info.get("daily"):  # an earlier one stays set
                self._poke()
                self.app.events.emit("alarm_set", at=at.isoformat(), queued=True)
                return f"Alarm set for {at:%a %d %b, %H:%M}. " + self._others(at)
        self.app.scheduler.at(
            at,
            "alarm.ring",
            {"tries": tries, "first": first},
            key=f"{self.id}:ring",
            module=self.id,
            grace_s=1800,
            respect="none",
        )
        jsave(self.file, {"at": at.isoformat(), "daily": daily, "set_at": set_at or now().isoformat()})
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
        more = (" " + self._others(at)) if first and not daily and len(self.upcoming()) > 1 else ""
        if self.keep_awake() and first and not self.on_ac():
            return f"Alarm set for {at:%a %d %b, %H:%M}. Plug this computer in: it stays awake until then.{more}"
        return f"Alarm set for {at:%a %d %b, %H:%M}.{more}"

    def _others(self, at: dt.datetime) -> str:
        rest = [x for x in self.upcoming() if x != at]
        if not rest:
            return ""
        return "Also set: " + ", ".join(f"{x:%a %H:%M}" for x in rest[:5]) + ("…" if len(rest) > 5 else "") + "."

    def clear(self) -> str:
        """ "Cancel my alarm": the one that's set. With a daily alarm, that morning is skipped (it would come back)."""
        at = self.next()
        was_daily = bool((jload(self.file, {}) or {}).get("daily"))
        had = self.app.scheduler.cancel(f"{self.id}:ring")
        self.app.scheduler.cancel(f"{self.id}:prep")
        jsave(self.file, {})
        if at:
            self._mine_drop(lambda x: x == at)
        if at and at > now() and self.setting("daily") and was_daily:
            self._skip_add(at.date())
        self._plan()
        self._poke()
        self.keep_awake()
        if not had:
            return "There was no alarm set."
        nxt = self.next()
        if nxt and at and not (jload(self.file, {}) or {}).get("daily"):  # the next one you set takes its place
            return f"Alarm off for {at:%a %d %b, %H:%M}. Next: {nxt:%a %d %b, %H:%M}. " + self._others(nxt)
        if nxt and at:
            return (
                f'Alarm off for {at:%a %d %b}. Your daily alarm is back {nxt:%a %d %b, %H:%M} ("turn my daily '
                'alarm off" stops it).'
            )
        return "Alarm off."

    def clear_at(self, hhmm: str) -> str:
        """ "Cancel the 10:30 alarm": the soonest alarm at that time of day."""
        at = next((x for x in self.upcoming() if f"{x:%H:%M}" == hhmm), None)
        if at is None:
            have = self.upcoming()
            return f"There's no alarm at {hhmm}." + (
                " Set: " + ", ".join(f"{x:%a %H:%M}" for x in have[:5]) + "." if have else ""
            )
        if at == self.next():
            return self.clear()
        self._mine_drop(lambda x: x == at)
        self._poke()
        self.app.events.emit("alarm_cleared", at=at.isoformat())
        return f"Alarm off for {at:%a %d %b, %H:%M}. " + self._others(at)

    def clear_all(self) -> str:
        """ "Cancel all my alarms": every one you set (the daily alarm stays; "turn my daily alarm off" stops it)."""
        n = len(self._mine_drop(lambda x: True))
        info = jload(self.file, {}) or {}
        if self.next() and not info.get("daily"):
            self.app.scheduler.cancel(f"{self.id}:ring")
            self.app.scheduler.cancel(f"{self.id}:prep")
            jsave(self.file, {})
            n = max(n, 1)
        self._plan()
        self._poke()
        self.keep_awake()
        self.app.events.emit("alarm_cleared", all=True, n=n)
        nxt = self.next()
        out = f"All {n} alarm{'s' if n != 1 else ''} you set are off." if n else "You had no alarms set."
        return out + (f" Your daily alarm stays: {nxt:%a %d %b, %H:%M}." if nxt else "")

    def skip(self, day: dt.date) -> str:
        """No alarm on that day (the daily one comes back after it)."""
        self._skip_add(day)
        self._mine_drop(lambda x: x.date() == day)
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
            lane="bg",  # nobody is waiting on it yet: it never holds up your own requests
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
        app, t = self.app, now()
        today = t.date()
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
            later = [c for c in cls if str(c.get("start") or "") > f"{t:%H:%M}"]
            if later:
                names = ", ".join(f"{c['name']} ({c['start']})" for c in later)
                steps.append(f"Classes still to come today: {names}. Ask which they're skipping, if any (skip_class).")
            elif cls:  # a late wake-up: they can't have gone, so don't ask
                steps.append("Today's classes are over already; don't ask whether they went.")
        es = app.modules.get("exam_season")
        if es is not None and app.is_on("exam_season") and hasattr(es, "call_line"):
            try:  # 0.9.0 (exam_season.in_calls): today's exam, when it starts, when to leave
                line = es.call_line("today")
            except Exception:
                line = ""
            if line:
                steps.append(line + " Say it plainly, once.")
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
                from kurooto.modules.deadlines import due_line  # "ps3 4/7, due Fri" for one with parts

                steps.append("Due soon: " + "; ".join(due_line(d) for d in due[:6]) + ".")
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
        if self.short_night():  # (0.9.0, alarm.sleep_aware) coarse words only: never when they slept
            steps.insert(0, "They had a short night: keep it gentle and brief.")
        steps.append("Wish them a good day.")
        head = (
            "Wake-up call. Say good morning, briefly and warmly; they've just woken up, so keep it light. It's "
            f"{t:%H:%M} now (their local time): plan from now on; anything planned earlier today is past."
        )
        return "\n".join([head] + [f"{i}. {x}" for i, x in enumerate(steps, 1)])

    def call_reschedule(self, key: str, at: dt.datetime) -> str | None:
        """ "Call me back in ten minutes" on the wake-up call: the alarm again then (like a snooze)."""
        if key != KEY:
            return None  # the "I'm awake" call: a plain call later, never the alarm
        return self.set(at.replace(tzinfo=None), first=False)

    def up(self, text: str) -> str:
        """ "I'm awake": the wake-up call's run-through now, from the current time. Forced, since you're up: the night
        before a pending alarm would otherwise hold it. The morning page opens here too."""
        said = re.sub(r"\s+", " ", text).strip()[:200]
        reason = (
            f'Morning call: they just told you they\'re up ("{said}"). First call morning_plan and follow it, planning '
            f"the rest of today from now ({now():%H:%M})."
        )
        self.app.modules["calls"].place(reason, key=AWAKE_KEY, force=True)
        self.app.events.emit("alarm_up_now", page=self.open_morning_page())
        from kurooto.core import persona  # (0.9.0, persona.templates) your card's name and avoid line

        name = persona.address(self.app)
        out = f"Good morning{', ' + name if name else ''}. Calling you now to plan the rest of today."
        at = self.next()
        if at and at - now() < dt.timedelta(hours=AWAKE_BEFORE_H):
            out += f' Your alarm at {at:%a %H:%M} is still set ("cancel my alarm" turns it off).'
        return persona.template(self.app, out)

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
        self._mirror()

    def status(self) -> str:
        """What's set, in a sentence or two: the next alarm, the daily one, the days that are skipped."""
        ups, daily = self.upcoming(), self.setting("daily")
        if len(ups) > 1:
            lines = ["Alarms: " + "; ".join(f"{x:%a %d %b, %H:%M}" for x in ups) + "."]
        else:
            lines = [f"Alarm: {ups[0]:%a %d %b, %H:%M}." if ups else "No alarm set. /alarm 6:45 sets one."]
        if daily:
            days = self.setting("days") or DAYS
            every = "every day" if len(days) == 7 else ", ".join(days)
            lines.append(f"Daily alarm: {daily} ({every}).")
        skips = sorted(self.skips())
        if skips:
            lines.append("No alarm on " + ", ".join(f"{d:%a %d %b}" for d in skips) + ".")
        return " ".join(lines)

    @property
    def mirror_file(self):
        return self.app.paths.state / "reserve" / "alarm.md"

    def _mirror(self) -> None:
        """The same as a Markdown file (alarm.md in the state folder), for programs that read files rather than call
        tools. Never fails what changed the alarm."""
        try:
            self.mirror_file.parent.mkdir(parents=True, exist_ok=True)
            self.mirror_file.write_text(f"# Alarm\n\n{self.status()}\n\n(Updated {now():%Y-%m-%d %H:%M}.)\n", "utf-8")
        except OSError:
            pass

    def _ring(self, p: dict) -> None:
        j = jload(self.file, {}) or {}
        first = p.get("first", True)
        if j.get("at") and first:  # the night this alarm ends (snoozes and repeat rings keep the first one's)
            jsave(self.last_file, {k: j.get(k) for k in ("at", "daily", "set_at")})
        if first:
            self._mine_save(self.mine())  # the one ringing (and any that rang while this computer slept) leave the list
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
        """Every alarm still to ring, so the line rings each one while this computer sleeps."""
        why = self.setting("reason") or "Wake-up call"
        return [{"at": int(at.timestamp()), "reason": why, "alarm": True, "key": KEY} for at in self.upcoming()]

    def call_outcome(self, key: str, outcome: str) -> bool:
        if key != KEY:
            return False  # the "I'm awake" call: Later and missed work like any call's
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
                '"off" clears the next one, "off 10:30" the one at 10:30, "off all" every one set (several can be '
                'set: a new one doesn\'t replace the others); "skip tomorrow" or "skip friday": no alarm that day '
                '(the daily one comes back after); "daily 7:00" or "daily off": the daily alarm.',
                self._tool,
                {"time": arg()},
                ("time",),
                offline="queue",
                hint="set_alarm sets the wake-up call; in an evening call, ask when to wake them and set it.",
                guarded="alarm.set",
            ),
            Tool(
                "get_alarm",
                "Read the alarm: when the next wake-up call rings, the daily alarm, and the days skipped. Use it for "
                '"do I have any alarms?", "when is my alarm?".',
                lambda a: self.status(),
                offline="brief",
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
        if re.fullmatch(r"(?i)(?:off|cancel|clear) all|all off", t):
            return self.clear_all()
        m = re.fullmatch(r"(?i)daily\s+(.+)", t)
        if m:
            if re.fullmatch(r"(?i)off|none|stop|no", m.group(1).strip()):
                return self.set_daily(None)
            hhmm = _clock_time(m.group(1))
            return self.set_daily(hhmm) if hhmm else f"I couldn't read {m.group(1)!r}."
        m = re.fullmatch(r"(?i)(?:skip|no alarm|none|off|cancel|clear)\s+(?:on\s+)?(.+)", t)
        if m:
            day = self._day(m.group(1))
            hhmm = None if day else _clock_time(m.group(1))
            if hhmm:
                return self.clear_at(hhmm)
            return self.skip(day) if day else f"I couldn't tell which day {m.group(1)!r} is."
        try:
            return self.set(_this_minute(parse_when(t).replace(tzinfo=None)))
        except ValueError:
            return f"I couldn't read {t!r}."

    # ------------------------------------------------------------------------------------ the suggestion
    def suggest(self) -> str:
        """Within an hour of your usual bedtime (core/rhythm.py learns it), with no alarm for the coming wake: one
        message suggesting your usual time, at most once a day. It never sets one by itself."""
        rh = getattr(self.app, "rhythm", None)
        u = rh.usual_hours() if rh is not None and self.setting("suggest") else None
        if not u:
            return ""
        t = now()
        try:
            bed_t, wake_t = dt.time.fromisoformat(u["from"]), dt.time.fromisoformat(u["to"])
        except ValueError:
            return ""
        bed = min(b for b in (dt.datetime.combine(t.date() + dt.timedelta(days=k), bed_t) for k in (0, 1)) if b > t)
        if bed - t > dt.timedelta(minutes=SUGGEST_MIN):
            return ""
        wake = dt.datetime.combine(bed.date(), wake_t)
        wake += dt.timedelta(days=1) if wake <= bed else dt.timedelta(0)
        daily_at = self.next_daily()
        if any(t < a <= wake + dt.timedelta(hours=3) for a in [*self.upcoming(), *([daily_at] if daily_at else [])]):
            return ""  # one's set for that wake already
        f = self.app.paths.state / "alarm-suggest.json"
        if (jload(f, {}) or {}).get("day") == bed.date().isoformat():
            return ""
        jsave(f, {"day": bed.date().isoformat()})
        text = f"You usually wake around {wake:%H:%M}; set an alarm?"
        self.app.notify(
            text,
            kind="question",
            why="alarm.suggest",
            buttons=[[(f"Set {wake:%H:%M}", f"alm:{wake:%Y%m%d%H%M}:set"), ("Not tonight", "alm:suggest:no")]],
        )
        self.app.events.emit("alarm_suggested", at=wake.isoformat())
        return text

    def up_signs(self, within_min: float = UP_SEEN_MIN) -> bool:
        """(skip_if_up) A sign you're up in the last minutes: Face presence has you at the desk, or core/here.py's
        owner_here (your voice, the dashboard, the phone app)."""
        t = now().timestamp()
        face = self.app.modules.get("face")
        try:
            seen = face.desk_seen_at() if face is not None and self.app.is_on("face") else None
        except Exception:
            seen = None
        from kurooto.core import here

        last = here.last(self.app)
        return any(x is not None and 0 <= t - x <= within_min * 60 for x in (seen, last))

    def ask_skip(self) -> str:
        """(0.9.0, alarm.skip_if_up) Within UP_LEAD_MIN before the alarm, with a sign you're up: one question, "skip
        the ring?", once per alarm. It never skips by itself: with no answer the alarm rings as set; Skip clears that
        alarm as "cancel my alarm" does (Alarm.clear), Keep leaves it."""
        if not self.setting("skip_if_up"):
            return ""
        at, t = self.next(), now()
        if not at or not (t < at <= t + dt.timedelta(minutes=UP_LEAD_MIN)) or not self.up_signs():
            return ""
        f = self.app.paths.state / "alarm-upask.json"
        if (jload(f, {}) or {}).get("at") == at.isoformat():
            return ""
        jsave(f, {"at": at.isoformat()})
        text = f"You're up already: skip the {at:%H:%M} alarm? It rings as set unless you tap Skip."
        self.app.notify(
            text,
            kind="question",
            why="alarm.skip_if_up",
            buttons=[[("Skip it", f"alm:{at:%Y%m%d%H%M}:skipup"), ("Keep it", "alm:up:keep")]],
        )
        self.app.events.emit("alarm_up_asked")
        return text

    def suggest_later(self) -> str:
        """(0.9.0, alarm.sleep_aware) Still up (a sign of you in the last minutes; Kurooto, with Brain, not asleep)
        with less than SHORT_H hours left before the next alarm: one offer of a later ring, about NIGHT_H hours from
        now (to the quarter hour), at least CLASS_GAP_MIN before the day's first class and LATE_GAIN_MIN later than
        the alarm.
        Once per alarm; it never moves the alarm by itself (the button does, on your tap)."""
        if not self.setting("sleep_aware"):
            return ""
        try:
            from kurooto.mind import sleep
        except ImportError:
            return ""
        at, t = self.next(), now()
        if not at or at <= t or at - t >= dt.timedelta(hours=SHORT_H):
            return ""
        if (sleep.on(self.app) and sleep.state(self.app, t) == "asleep") or not self.up_signs():
            return ""
        f = self.app.paths.state / "alarm-later.json"
        if (jload(f, {}) or {}).get("at") == at.isoformat():
            return ""
        sug = t + dt.timedelta(hours=NIGHT_H)
        sug = sug.replace(minute=sug.minute // 15 * 15, second=0, microsecond=0)
        first, cls = self._first_class(at.date()), ""
        if first is not None:
            sug = min(sug, first - dt.timedelta(minutes=CLASS_GAP_MIN))
            cls = f" Your first class is at {first:%H:%M}."
        elif self.app.is_on("subjects"):
            cls = " No classes that morning."
        else:
            return ""  # nothing says the morning is free
        if sug - at < dt.timedelta(minutes=LATE_GAIN_MIN):
            return ""
        jsave(f, {"at": at.isoformat()})
        text = f"It's {t:%H:%M} and your alarm is at {at:%H:%M}: a short night.{cls} Ring at {sug:%H:%M} instead?"
        self.app.notify(
            text,
            kind="question",
            why="alarm.sleep_aware",
            buttons=[
                [(f"Ring at {sug:%H:%M}", f"alm:{at:%Y%m%d%H%M}-{sug:%Y%m%d%H%M}:later"), ("Keep it", "alm:up:keep")]
            ],
        )
        self.app.events.emit("alarm_later_offered")
        return text

    def _first_class(self, day: dt.date) -> dt.datetime | None:
        sub = self.app.modules.get("subjects")
        if sub is None or not self.app.is_on("subjects"):
            return None
        try:
            starts = [c["start_dt"] for c in sub.classes_on(day) if c.get("start_dt")]
        except Exception:
            return None
        return min(starts) if starts else None

    def short_night(self) -> bool:
        """(alarm.sleep_aware) Kurooto's own sleep (mind/sleep.py) fell asleep less than SHORT_H hours ago."""
        if not self.setting("sleep_aware"):
            return False
        try:
            from kurooto.mind import sleep

            n = sleep.last_night(self.app) if sleep.on(self.app) else None
        except Exception:
            n = None
        return bool(n and now() - n[0] < dt.timedelta(hours=SHORT_H))

    def phone_mismatch(self) -> str:
        """(0.9.0, availability.night.phone_alarm) The phone's own alarm (its alarm sense) and the next one here are
        for the same morning but at different times: ask once per pair whether to keep both. Neither alarm changes
        without your tap; the phone's time is used here only."""
        if not (self.app.settings.get("availability.night") or {}).get("phone_alarm"):
            return ""
        try:
            from kurooto.mind.senses import phone

            at = phone.next_alarm(self.app)
        except Exception:
            return ""
        mine = self.next()
        if at is None or mine is None:
            return ""
        pa, t = dt.datetime.fromtimestamp(at).replace(second=0, microsecond=0), now()
        gap = abs((pa - mine).total_seconds())
        if not (t < pa and t < mine) or gap < 15 * 60 or gap > 4 * 3600 or mine - t > dt.timedelta(hours=18):
            return ""
        f = self.app.paths.state / "alarm-phone.json"
        pair = f"{pa:%Y%m%d%H%M}|{mine:%Y%m%d%H%M}"
        if (jload(f, {}) or {}).get("pair") == pair:
            return ""
        jsave(f, {"pair": pair})
        text = f"Your phone's alarm is at {pa:%H:%M}, mine at {mine:%H:%M}. Keep both?"
        self.app.notify(
            text,
            kind="question",
            why="alarm.phone_mismatch",
            buttons=[[("Keep both", "alm:phone:keep"), (f"Ring me at {pa:%H:%M} too", f"alm:{pa:%Y%m%d%H%M}:set")]],
        )
        self.app.events.emit("alarm_phone_mismatch")
        return text

    def callbacks(self):
        return {"alm": self._suggest_button}

    def _suggest_button(self, ref: str, act: str) -> str:
        if act == "later":  # (sleep_aware) your tap: the alarm moves, if it's still the one set
            try:
                was, to = (dt.datetime.strptime(x, "%Y%m%d%H%M") for x in ref.split("-", 1))
            except ValueError:
                return "That button is out of date."
            nxt = self.next()
            if nxt is None or nxt.replace(second=0, microsecond=0) != was or to <= now():
                return "That alarm isn't the one set any more."
            self.clear()
            return self.set(to)
        if act == "skipup":  # (skip_if_up) your tap: that alarm off, if it's still the one set
            try:
                at = dt.datetime.strptime(ref, "%Y%m%d%H%M")
            except ValueError:
                return "That button is out of date."
            nxt = self.next()
            if nxt is None or nxt.replace(second=0, microsecond=0) != at or at <= now():
                return "That alarm isn't the one set any more."
            self.clear()
            self.app.events.emit("alarm_skipped", day=at.date().isoformat(), up=True)
            return f"OK, the {at:%H:%M} alarm won't ring."
        if ref == "phone":
            return "Both stay as they are."
        if act != "set":
            return "OK, the alarm stays." if ref == "up" else "OK, no alarm."
        try:
            at = dt.datetime.strptime(ref, "%Y%m%d%H%M")
        except ValueError:
            return "That button is out of date."
        return self.set(at) if at > now() else "That time has passed."

    # -------------------------------------------------------------------------------------- telegram
    def commands(self):
        return [
            Command(
                "alarm",
                "the wake-up call: /alarm 6:45, /alarm tomorrow 7, /alarm off, /alarm skip friday, "
                "/alarm daily 7:00 (or daily off), /alarm off 10:30 (that one), /alarm off all",
                self._cmd,
            )
        ]

    def _cmd(self, msg: Incoming, arg: str) -> str:
        if not arg:
            return self.status()
        return self._tool({"time": arg})

    def intents(self):
        set_pat = re.compile(
            r"^(?:please )?(?:wake me(?: up)?|set (?:an |my |the )?alarm(?: for)?) (?:at |for |in )?(.+)$", re.I
        )
        off_pat = re.compile(r"^(?:cancel|turn off|delete|remove|clear|no) (?:my |the )?alarm\b", re.I)
        all_off = re.compile(
            r"^(?:please )?(?:cancel|turn off|delete|remove|clear) (?:all|every(?: one of)?) (?:of )?"
            r"(?:my |the )?alarms?\b",
            re.I,
        )
        off_at = re.compile(
            r"^(?:please )?(?:cancel|turn off|delete|remove|clear) (?:my |the )?(?:alarm (?:at |for )?(?P<t>[\d:.]+"
            r"(?: ?[ap]m)?)|(?P<u>[\d:.]+(?: ?[ap]m)?) alarm)$",
            re.I,
        )
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

        ask_open = re.compile(
            r"^(?:please |hey |so )?(?:do i have|have i got|have i set|did i set|is there|are there|is my|are my|any|"
            r"got any|what'?s?|which|when'?s?|what time|show|list|check|tell me|how many)\b",
            re.I,
        )
        ask_not = re.compile(
            r"\b(?:cancel|turn off|delete|remove|clear|skip|stop|disable|wake me|don'?t|snooze)\b", re.I
        )

        def asking(t: str) -> bool:
            """A question about the alarm ("do I have any alarms?", "when is my alarm?"), not an order."""
            t = t.rstrip("?! .").strip()
            return bool(
                len(t) <= 70 and re.search(r"\balarms?\b", t, re.I) and ask_open.match(t) and not ask_not.search(t)
            )

        def match(text: str):
            t = text.strip().rstrip(".!")
            if daily_off.match(t):
                return {"daily_off": True}
            if all_off.match(t):
                return {"all_off": True}
            m = off_at.match(t)
            hhmm = _clock_time((m.group("t") or m.group("u")).replace(".", ":")) if m else None
            if hhmm:
                return {"off_at": hhmm}
            m = skip_pat.match(t)
            words = next((g for g in m.group("a", "b", "c", "d") if g), "") if m else ""
            if m and words:
                day = self._day(words)
                hhmm = None if day else _clock_time(words.replace(".", ":"))
                if hhmm:
                    return {"off_at": hhmm}
                return {"skip": day} if day else None
            if off_pat.match(t):
                return {"off": True}
            m = set_pat.match(t)
            if not m:
                return None
            try:
                return {"at": _this_minute(parse_when(m.group(1)).replace(tzinfo=None))}
            except ValueError:
                return None

        def run(msg, sl):
            if sl.get("daily_off"):
                return self.set_daily(None)
            if sl.get("all_off"):
                return self.clear_all()
            if sl.get("off_at"):
                return self.clear_at(sl["off_at"])
            if sl.get("skip"):
                return self.skip(sl["skip"])
            return self.clear() if sl.get("off") else self.set(sl["at"])

        return [
            Intent(
                "alarm",
                "wake me at …, cancel the 10:30 alarm, cancel all my alarms, no alarm tomorrow, turn my daily alarm "
                "off",
                match,
                run,
                examples=("wake me at 6:45", "no alarm tomorrow", "cancel all my alarms", "turn my daily alarm off"),
                guarded="alarm.set",
            ),
            Intent(
                "alarm_status",
                "do I have any alarms? when is my alarm?",
                lambda text: {"ask": True} if asking(text) else None,
                lambda msg, sl: self.status(),
                questions=True,
                examples=("when is my alarm?", "do I have any alarms?"),
            ),
            Intent(
                "up_now",
                "I'm awake, I just woke up (the morning call now)",
                lambda text: {"text": text} if up_now(text) else None,
                lambda msg, sl: self.up(sl["text"]),
                examples=("I'm awake", "I just woke up"),
                guarded="call.place",  # the morning call, now
            ),
        ]

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

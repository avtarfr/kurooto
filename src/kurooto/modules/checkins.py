"""Check-ins: at times you choose, Kurooto asks how things are going. Reply to the message and your answer goes
into your journal (notes folder: journal/YYYY-MM-DD.md). Move or skip one in plain English: "move tonight's
check-in to 9:30", "skip the midday check-in", "push the check-in by 30 min", "skip Friday's check-in" (other days
work too: tomorrow, or a weekday). /checkins lists today's, with +30 min and Skip buttons.

Three of them: evening (the day in review), night (goodnight, near bedtime) and an optional midday one.

Once Calls is on, a check-in can be a phone call instead (Settings → Check-ins → by call). The evening one is a
debrief: how the day went, what each class covered, what slipped, open questions, study time, a quiz if an exam is
near. The night one says goodnight: anything more for the journal, study logs still due, tomorrow's priority and
when to wake you (it sets the alarm). Too tired? "Tomorrow morning" (on Telegram, or say so on the call) moves the
rest to the wake-up call. After a call, with Chat on, the AI writes your journal and study logs from what you said;
without Chat your words go into the journal as they are. A call you don't answer, or decline, becomes a message with
Call me now / Tomorrow morning / Skip.

A check-in day runs from 05:00 to 05:00 (checkins.day_starts), so a night check-in at 00:30, or one pushed past
midnight, still belongs to the evening before: its journal and study logs go to that day.

Gone to bed: with the alarm set, a night check-in call that comes after your bedtime (or within a few hours of you
setting the alarm yourself) doesn't ring; it moves to the wake-up call, and a message offers Call me now or Skip
(checkins.asleep_defers).

Lighter days (core/rhythm.py, notify.calm.lighter_after): the day after an exam or a heavy day, its first check-in
comes an hour later; Not today under the morning line puts it back.

Learned times (checkins.learn_times, on): when, over the last two weeks, you answered a check-in on at least 5 days and
on 4 or more of them at a time 30 minutes or more from its setting, all on the same side (you moved it, or replied
late to it), its time moves to when you actually did it (the middle of those times, to the quarter hour). One line
says so, with Undo; a check-in isn't moved again for two weeks, and one you undid is left alone for a month.

The day's reflection (checkins.reflect, on): the evening check-in message lists up to three things the day's records
show you did (a deadline marked done or moved on, a thread closed, study time, a class you logged), never guessed from
what you said, then asks one thing about tomorrow ("What's first tomorrow?"). Nothing recorded: no list. Not tonight
under it ends the check-in for the day. Never a streak, a score or "you missed".
"""

from __future__ import annotations

import datetime as dt
import re
import time

from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave
from kurooto.modules import daily
from kurooto.modules.base import Command, Incoming, Intent, Module
from kurooto.modules.calls.tools import Tool, arg
from kurooto.modules.text import a_day, a_minutes, a_time, as_written

register_defaults(
    "checkins",
    {
        "times": {
            "evening": "22:00",  # the evening check-in, the day in review (None: off)
            "midday": None,  # the midday check-in (None: off; e.g. "13:00")
            "night": None,  # the night check-in before bed (None: off; e.g. "23:15")
        },
        "questions": {
            "evening": "How did today go? What got done, and what slipped?",
            "midday": "How's the morning been? Anything to re-plan for the afternoon?",
            "night": "Before bed: anything else for your journal? What's first tomorrow, and when should I wake you?",
        },
        "journal": True,
        "by_call": False,  # with Phone calls on: the check-in is a call (a missed call falls back to Telegram)
        "ai_notes": True,  # with Chat on: after a check-in call, the AI writes your journal and study logs
        "day_starts": "05:00",  # a check-in day runs from here to here: a night check-in at 00:30 is the evening's
        "asleep_defers": True,  # by call, alarm set and you've gone to bed: the night check-in waits for the morning
        "learn_times": True,  # a check-in you keep moving or answering late moves to when you do it (with Undo)
        "reflect": True,  # the evening check-in lists up to 3 things today's records show you did, asks about tomorrow
    },
)
NAMES = ("evening", "midday", "night")
CALL_REASON = {"evening": "Evening debrief", "midday": "Midday check-in", "night": "Night check-in"}
STUCK_MIN = 15  # a check-in call with no outcome after this long becomes a message
GRACE_S = 2 * 3600  # a check-in this late still asks (past it: "I missed your check-in")
ASLEEP_SET_H = 3  # an alarm you set yourself this recently means you've gone to bed
DONE = ("answered", "skipped", "deferred")  # a check-in that's over for its day
LEARN_DAYS, LEARN_MIN_DAYS, LEARN_OFF_DAYS, LEARN_GAP_MIN = 14, 5, 4, 30  # look back, answered, off, minutes off
LEARN_LATE_H = 3  # a reply later than this after the check-in says nothing about when you'd like it
REFLECT_N, REFLECT_STUDY_MIN = 3, 15  # the evening's "what you did today": at most this many, study this long or more
TOMORROW = "What's first tomorrow?"
OWN_RECORD = {"deadline", "study"}  # threads keyed to these are told from the deadline or the study time itself
WORDS = re.compile(
    r"\b(evening|midday|night|bedtime|tonight'?s?|today'?s?|tomorrow'?s?|afternoon|lunch|(?:mon|tues|wednes|thurs|"
    r"fri|satur|sun)day'?s?)?\s*(check-?in|debrief|call)\b",
    re.I,
)
MOVE = re.compile(r"\b(move|push|postpone|shift|change|make|put|set|reschedule|instead|delay|later)\b", re.I)
SKIP = re.compile(r"\b(skip|cancel|drop|no (?:\w+ )?(?:check-?in|debrief))\b", re.I)


def _label(day: dt.date, today: dt.date) -> str:
    """How to say a day, from the check-in day `today`: still up at 2 am, the coming day is "tomorrow", as you'd say
    it yourself (and as "tomorrow" is read in what you write)."""
    if day == today:
        return "today"
    return "tomorrow" if day == today + dt.timedelta(days=1) else f"on {day:%a %d %b}"


def _span(seconds: float) -> str:
    m = round(seconds / 60)
    return f"{m} min" if m < 60 else f"{m / 60:.1f} h"


def _name_in(low: str) -> str:
    if re.search(r"midday|afternoon|lunch|noon", low):
        return "midday"
    if re.search(r"\b(?:night|bedtime|goodnight)\b", low):  # "tonight's" is the evening one
        return "night"
    return "evening"


class Checkins(Module):
    id = "checkins"
    title = "Check-ins"
    description = "Kurooto asks how your day is going at times you choose; your replies go into your journal."
    requires = ("telegram",)
    privacy = (
        "Replies on Telegram go straight into your journal, on this computer. On a check-in call with Chat on, what "
        "you said goes to the AI you picked, to write your journal and study logs (checkins.ai_notes)."
    )

    def start(self):
        self.action("fire", self._fire)
        self.action("unstick", self._unstick)
        self.action("deferred", self._deferred_message)
        plan_at = dt.datetime.combine(dt.date(2000, 1, 1), self._day_start()) + dt.timedelta(minutes=5)
        self.every("plan", f"daily {plan_at:%H:%M}", self._plan)
        self.app.jobs.then_actions["checkins.notes_done"] = self._notes_done
        self._plan({})
        self.every("learn", "daily 12:00", lambda p: self.learn())

    # ------------------------------------------------------------------------------- the check-in day
    def _day_start(self) -> dt.time:
        try:
            return dt.time.fromisoformat(self.setting("day_starts") or "00:00")
        except ValueError:
            return dt.time(0, 0)

    def _shift(self) -> dt.timedelta:
        s = self._day_start()
        return dt.timedelta(hours=s.hour, minutes=s.minute)

    def _base(self) -> dt.datetime:
        """Now, shifted so the check-in day reads as the date: "today", "tomorrow", "Friday" mean what you mean
        when you're still up after midnight."""
        return now() - self._shift()

    def day_of(self, t: dt.datetime | None = None) -> dt.date:
        """The check-in day a moment belongs to: one runs from checkins.day_starts (05:00) to the next."""
        return ((t or now()) - self._shift()).date()

    def at(self, day: dt.date, hhmm: str) -> dt.datetime:
        """When a check-in at hh:mm on a check-in day is: a time before the day starts is after midnight."""
        t = dt.time.fromisoformat(hhmm)
        return dt.datetime.combine(day + dt.timedelta(days=1 if t < self._day_start() else 0), t)

    def _after_midnight(self, today: dt.date) -> bool:
        """Past midnight but before the check-in day ends (you're still up)."""
        return now().date() != today

    def _file(self, day: dt.date) -> str:
        return str(self.app.paths.state / "checkins" / f"{day.isoformat()}.json")

    def today(self, day: dt.date | None = None) -> dict:
        return jload(self._file(day or self.day_of()), {}) or {}

    def _save(self, plan: dict, day: dt.date | None = None) -> None:
        jsave(self._file(day or self.day_of()), plan)

    def _status(self, name: str, day: dt.date, status: str, **extra) -> None:
        plan = self.today(day)
        plan[name] = {**plan.get(name, {"time": (self.setting("times") or {}).get(name)}), "status": status, **extra}
        self._save(plan, day)

    def _plan(self, p: dict) -> None:
        """Each day (and at startup): schedule today's check-ins from the settings, unless already planned (one moved
        or skipped ahead of time, e.g. "skip Friday's check-in", is already in that day's plan)."""
        day = self.day_of()
        plan = self.today(day)
        new = []
        for name in NAMES:
            t = (self.setting("times") or {}).get(name)
            # not one long over (Kurooto starting at 2 am doesn't say it missed last evening's)
            if t and name not in plan and self.at(day, t) > now() - dt.timedelta(seconds=GRACE_S):
                plan[name] = {"time": t, "status": "planned"}
                new.append(name)
        self._lighter(plan, new, day)
        self._presence(plan, new, day)
        self._save(plan, day)
        for name, c in plan.items():
            if c["status"] == "planned" and c.get("time"):
                self._schedule(name, c["time"], day)

    def _lighter(self, plan: dict, new: list[str], day: dt.date) -> None:
        """A lighter day after an exam or a heavy one (core/rhythm.py): the day's first check-in, if it's just been
        planned, comes LATER_MIN later (its own time kept under "lighter", for Not today)."""
        rh = getattr(self.app, "rhythm", None)
        planned = [n for n, c in plan.items() if c.get("status") == "planned" and c.get("time")]
        if not new or not planned or rh is None or not rh.lighter(day):
            return
        from kurooto.core.rhythm import LATER_MIN

        first = min(planned, key=lambda n: self.at(day, plan[n]["time"]))
        was = self.at(day, plan[first]["time"])
        later = f"{was + dt.timedelta(minutes=LATER_MIN):%H:%M}"
        if first in new and self.at(day, later) > was:  # still the same check-in day
            plan[first] = {"time": later, "status": "planned", "lighter": plan[first]["time"]}

    def _presence(self, plan: dict, new: list[str], day: dt.date) -> None:
        """(Brain, 0.8.16: mind.presence_forecast.prefer) a check-in just planned for an hour Brain forecasts you won't
        be at your desk and free moves to a nearby likelier one (within the setting's minutes, the same check-in day,
        never earlier than now). The night one is for bedtime, so its sleep isn't held against it. Its own time is
        kept under "presence"."""
        try:
            from kurooto.mind import presence_forecast as pf
        except ImportError:
            return
        if not pf.prefer_on(self.app):
            return
        end = dt.datetime.combine(day + dt.timedelta(days=1), self._day_start()) - dt.timedelta(minutes=1)
        for name in new:
            c = plan.get(name) or {}
            if c.get("status") != "planned" or not c.get("time"):
                continue
            was = self.at(day, c["time"])
            skip = ("asleep",) if name == "night" else ()
            to = pf.prefer(self.app, was, earliest=now(), latest=end, skip=skip)
            if to != was and self.day_of(to) == day:
                plan[name] = {**c, "time": f"{to:%H:%M}", "presence": c.get("presence") or c["time"]}
                self.app.events.emit("checkin_presence_moved", name=name, minutes=int((to - was).total_seconds() // 60))

    def unlighten(self, day: dt.date) -> None:
        """Not today: a check-in a lighter day moved goes back to its time (not one you moved since)."""
        plan = self.today(day)
        for name, c in plan.items():
            if c.get("lighter") and c.get("status") == "planned":
                plan[name] = {"time": c["lighter"], "status": "planned"}
                self._save(plan, day)
                self._schedule(name, c["lighter"], day)

    def _schedule(self, name: str, hhmm: str, day: dt.date) -> dt.datetime:
        at = self.at(day, hhmm)
        self.app.scheduler.action("checkins.fire", self._fire)
        self.app.scheduler.at(
            at,
            "checkins.fire",
            {"name": name, "day": day.isoformat()},
            key=f"checkins:{name}",
            module=self.id,
            grace_s=GRACE_S,
            respect="quiet",
        )
        return at

    def _fire(self, p: dict) -> None:
        name, day = p["name"], p.get("day") or self.day_of().isoformat()
        plan = self.today(dt.date.fromisoformat(day))
        if plan.get(name, {}).get("status") != "planned":
            return
        if p.get("missed"):
            self.app.notify(
                f"I missed your {name} check-in (the computer was off). Reply here any time and I'll "
                "put it in your journal.",
                map_kind="checkin",
                map_ref=f"{name}:{day}",
                why="checkins.question",
                setting=f"checkins.times.{name}",
                about=f"your {name} check-in",
            )
        elif self._by_call() and name == "night" and self._asleep(plan[name]):
            self._asleep_defer(name, dt.date.fromisoformat(day))
            return
        elif self._by_call() and (held := self._held(name, day)) != "message":
            if held == "later":
                return
            self._call(name, dt.date.fromisoformat(day))
            return
        else:
            q = (self.setting("questions") or {}).get(name) or "How's it going?"
            if p.get("early"):  # Brain's surprise check-in (0.8.14): the day looks unlike what it expected
                q = "A bit earlier than usual. " + q
            later = [("Tomorrow morning", f"chk:{name}|{day}:defer")] if name == "night" else []
            skip = ("Skip today", f"chk:{name}|{day}:skip")
            if name == "evening" and self.setting("reflect"):  # the day's reflection: what you did, one for tomorrow
                did = self.done_today(dt.date.fromisoformat(day))
                if did:  # nothing recorded: no list, never "you did nothing"
                    q += "\n\nFrom today's records:" + "".join(f"\n- {x}" for x in did)
                q += f"\n\n{TOMORROW}"
                skip = ("Not tonight", f"chk:{name}|{day}:not")
            self.app.notify(
                f"{name.title()} check-in: {q}\n\n(Reply to this message.)",
                kind="question",
                map_kind="checkin",
                map_ref=f"{name}:{day}",
                buttons=[[("In 30 min", f"chk:{name}|{day}:p30"), *later, skip]],
                why="checkins.question",
                setting=f"checkins.times.{name}",
                about=f"your {name} check-in",
            )
        plan[name]["status"] = "asked"
        self._save(plan, dt.date.fromisoformat(day))
        self.app.events.emit("checkin_asked", name=name)

    def _call(self, name: str, day: dt.date, asked: bool = False) -> None:
        """Ring the check-in now. Whatever happens, it doesn't stay "calling": with no outcome after a while it becomes
        a message. Past the day's calls (notify.calm.calls; not when you tapped Call me now), it comes as a message
        right away (call_outcome "held")."""
        ref = f"{name}|{day.isoformat()}"
        extra = [("Tomorrow morning", f"chk:{ref}:defer")] if name == "night" else []
        rang = self.app.modules["calls"].ring(
            self._reason(name),
            key=f"checkins:{name}:{day.isoformat()}",
            buttons=[*extra, ("Skip", f"chk:{ref}:skip")],
            why="calls.own" if asked else "checkins.call",
        )
        if rang == "":  # not placed (core/calm.py): the message went instead
            return
        self._status(name, day, "calling")
        self.app.scheduler.at(
            time.time() + STUCK_MIN * 60,
            "checkins.unstick",
            {"name": name, "day": day.isoformat()},
            key=f"checkins:unstick:{name}",
            module=self.id,
        )
        self.app.events.emit("checkin_called", name=name)

    def _unstick(self, p: dict) -> None:
        day = dt.date.fromisoformat(p["day"])
        if (self.today(day).get(p["name"]) or {}).get("status") == "calling":
            self._fallback(p["name"], day, "no answer")

    def _fallback(self, name: str, day: dt.date, why: str) -> None:
        """The call didn't happen: ask by message, with Call me now / Tomorrow morning / Skip."""
        self.app.scheduler.cancel(f"checkins:unstick:{name}")
        self._status(name, day, "asked")
        q = (self.setting("questions") or {}).get(name) or "How's it going?"
        ref = f"{name}|{day.isoformat()}"
        self.app.notify(
            f"{name.title()} check-in ({why}): {q}\n\n(Reply to this message, or:)",
            kind="question",
            map_kind="checkin",
            map_ref=f"{name}:{day.isoformat()}",
            why="checkins.question",
            setting=f"checkins.times.{name}",
            about=f"your {name} check-in",
            buttons=[
                [
                    ("Call me now", f"chk:{ref}:now"),
                    ("Tomorrow morning", f"chk:{ref}:defer"),
                    ("Skip", f"chk:{ref}:skip"),
                ]
            ],
        )
        self.app.events.emit("checkin_fallback", name=name, why=why)

    @staticmethod
    def _reason(name: str) -> str:
        return CALL_REASON.get(name) or f"{name.title()} check-in"

    def _held(self, name: str, day: str) -> str | None:
        """A check-in call during a no-call time (a class, /hold, focus, a calendar event, night) waits until the
        block ends if that's still today ("later"), or comes as a message instead ("message"). None: call now. The
        night check-in is the goodnight call, so the night itself doesn't hold it."""
        av = self.app.availability
        reason, until = av.call_block()
        hold = None
        if not reason and name != "night":  # 0.9.0 (agent_plan.holds_calls): a block of yours that's running
            calls = self.app.modules.get("calls")
            hold = (
                calls.plan_block_hold("checkins") if calls is not None and hasattr(calls, "plan_block_hold") else None
            )
            reason = hold[1] if hold else None
        if not reason:
            return None
        night = av.night(now())
        if name == "night":
            if night and night[0] == reason:
                return None
            when = until + dt.timedelta(minutes=1)
        else:
            when, _ = av.next_callable(hold[0] if hold else None)
        if self.day_of(when) != dt.date.fromisoformat(day) or (name != "night" and av.night(when)):
            return "message"  # too late for a call today
        self.app.scheduler.at(
            when,
            "checkins.fire",
            {"name": name, "day": day},
            key=f"checkins:{name}",  # one booking: holding it again replaces this
            module=self.id,
            grace_s=2 * 3600,
            respect="quiet",
        )
        self.app.notify(
            f"Your {name} check-in call waits until {when:%H:%M} ({reason}).",
            kind="info",
            why="checkins.moved",
            about=f"your {name} check-in",
        )
        self.app.events.emit("checkin_held", name=name, reason=reason, to_time=f"{when:%H:%M}")
        return "later"

    def _asleep(self, entry: dict) -> bool:
        """Have you gone to bed? The alarm is set and it's past your bedtime, or you set it yourself in the last few
        hours. A check-in you moved after setting the alarm still rings: you asked for it."""
        alarm = self.app.modules.get("alarm")
        if not self.setting("asleep_defers") or alarm is None or not self.app.is_on("alarm"):
            return False
        at = alarm.next()
        if not at or at - now() > dt.timedelta(hours=18):
            return False
        info = jload(alarm.file, {}) or {}
        try:
            set_at = dt.datetime.fromisoformat(info["set_at"])
        except (KeyError, ValueError, TypeError):
            set_at = None
        try:
            if set_at and dt.datetime.fromisoformat(entry["moved"]) >= set_at:
                return False
        except (KeyError, ValueError, TypeError):
            pass
        reason = (self.app.availability.night(now()) or ("", None))[0]
        if reason.startswith("you're asleep"):
            return True
        return bool(set_at and not info.get("daily") and now() - set_at < dt.timedelta(hours=ASLEEP_SET_H))

    def _asleep_defer(self, name: str, day: dt.date) -> None:
        """The night check-in found you asleep: it moves to the wake-up call, and a message says so."""
        self.defer(name, day, via="asleep")
        ref = f"{name}|{day.isoformat()}"
        self.app.notify(
            f"Your alarm is set, so I took it you're asleep: the {name} check-in moves to your wake-up call.",
            kind="info",
            buttons=[[("Call me now", f"chk:{ref}:now"), ("Skip", f"chk:{ref}:skip")]],
            why="checkins.moved",
            about=f"your {name} check-in",
        )

    def replies(self):
        return {"checkin": self._answer}

    def _answer(self, msg: Incoming, ref: str) -> str:
        name, _, day = ref.partition(":")
        day = day or self.day_of().isoformat()
        plan = self.today(dt.date.fromisoformat(day))
        if name in plan:
            plan[name]["status"] = "answered"
            plan[name]["answered_at"] = now().isoformat(timespec="seconds")
            self._save(plan, dt.date.fromisoformat(day))
        self.app.events.emit("checkin_answered", name=name, chars=len(msg.text), via="telegram")
        if not self.setting("journal"):
            return "Thanks."
        j = daily.append(self.app, f"{name.title()} check-in ({now():%H:%M})", msg.text, dt.date.fromisoformat(day))
        return f"Saved to your journal ({j.parent.name}/{j.name})."

    # ------------------------------------------------------------------------- moving and skipping
    def move(self, name: str, hhmm: str, day: dt.date | None = None, via: str = "telegram") -> str:
        """Set a check-in's time on a day (today unless given). Another day's goes into that day's plan and is
        scheduled when the day comes. No day given, after midnight: a time already past means the coming day's."""
        today = self.day_of()
        if day is None and self._after_midnight(today) and self.at(today, hhmm) < now():
            day = today + dt.timedelta(days=1)
        day = day or today
        plan = self.today(day)
        before = (plan.get(name) or {}).get("time") or (self.setting("times") or {}).get(name)
        plan[name] = {"time": hhmm, "status": "planned", "moved": now().isoformat()}
        self._save(plan, day)
        self.app.scheduler.cancel(f"checkins:unstick:{name}")
        if before:
            self.app.events.emit(
                "checkin_moved", name=name, from_time=before, to_time=hhmm, day=day.isoformat(), via=via
            )
        else:  # one that wasn't on (e.g. a midday check-in asked for on the morning call)
            self.app.events.emit("checkin_planned", name=name, time=hhmm, day=day.isoformat(), via=via)
        if day != today:
            return f"{name.title()} check-in {_label(day, today)} at {hhmm}."
        at = self._schedule(name, hhmm, day)
        return f"{name.title()} check-in at {at:%H:%M}."

    def postpone(self, name: str, minutes: int, day: dt.date | None = None, via: str = "telegram") -> str:
        today = self.day_of()
        day = day or today
        t0 = (self.today(day).get(name) or {}).get("time") or (self.setting("times") or {}).get(name)
        planned = self.at(day, t0) if t0 else None
        if day == today:
            base = max(now(), planned) if planned else now()
        elif planned:
            base = planned
        else:
            return f"There's no {name} check-in {_label(day, today)} to push back; give a time instead."
        t = base + dt.timedelta(minutes=minutes)
        if self.day_of(t) != day:
            if name == "night":
                return self.defer(name, day, via)
            return f"That would push the {name} check-in into the next day; skip it instead?"
        return self.move(name, f"{t:%H:%M}", day, via)

    def skip(self, name: str, day: dt.date | None = None, via: str = "telegram") -> str:
        today = self.day_of()
        over = (self.today(today).get(name) or {"status": "answered"}).get("status") in DONE
        if day is None and self._after_midnight(today) and over:
            day = today + dt.timedelta(days=1)  # no day given, after midnight, tonight's is over: the coming one
        day = day or today
        self._status(name, day, "skipped")
        if day == today:
            self.app.scheduler.cancel(f"checkins:{name}")
        self.app.scheduler.cancel(f"checkins:unstick:{name}")
        self._undefer(name, day)
        self.app.events.emit("checkin_skipped", name=name, day=day.isoformat(), via=via)
        return f"No {name} check-in {_label(day, today)}."

    # ----------------------------------------------------------------------------- tomorrow morning
    @property
    def deferred_file(self):
        return self.app.paths.state / "checkins" / "deferred.json"

    def defer(self, name: str, day: dt.date | None = None, via: str = "telegram") -> str:
        """Too tired: what's left of this check-in moves to the wake-up call (or, with no alarm set, a message in the
        morning)."""
        day = day or self.day_of()
        self._status(name, day, "deferred")
        if day == self.day_of():
            self.app.scheduler.cancel(f"checkins:{name}")
        self.app.scheduler.cancel(f"checkins:unstick:{name}")
        jsave(
            self.deferred_file,
            {"day": day.isoformat(), "name": name, "classes": self.logs_due(day), "at": now().isoformat()},
        )
        self.app.events.emit("checkin_deferred", name=name, day=day.isoformat(), via=via)
        alarm = self.app.modules.get("alarm")
        at = alarm.next() if alarm is not None and self.app.is_on("alarm") else None
        if at and at - now() < dt.timedelta(hours=18):
            self.app.scheduler.cancel("checkins:deferred")
            return f"OK, sleep well. The rest of it comes on your wake-up call ({at:%a %H:%M})."
        night = self.app.settings.get("availability.night") or {}
        try:
            wake = dt.time.fromisoformat(night.get("to") or "08:00") if night.get("enabled") else dt.time(8, 0)
        except ValueError:
            wake = dt.time(8, 0)
        morning = dt.datetime.combine(day + dt.timedelta(days=1), wake)
        if morning <= now():
            morning = now() + dt.timedelta(minutes=1)
        self.app.scheduler.at(morning, "checkins.deferred", {}, key="checkins:deferred", module=self.id, grace_s=86400)
        return f"OK, sleep well. I'll ask you the rest tomorrow morning ({morning:%a %H:%M})."

    def _undefer(self, name: str, day: dt.date) -> None:
        """You took this check-in after all (Call me now) or skipped it: the morning doesn't carry it."""
        d = self.deferred()
        if d and d.get("name") == name and d.get("day") == day.isoformat():
            self.deferred_file.unlink(missing_ok=True)
            self.app.scheduler.cancel("checkins:deferred")

    def deferred(self) -> dict | None:
        """A check-in moved to the morning, if it's still fresh (a day and a half)."""
        d = jload(self.deferred_file, {}) or {}
        try:
            fresh = now() - dt.datetime.fromisoformat(d["at"]) < dt.timedelta(hours=36)
        except (KeyError, ValueError, TypeError):
            return None
        return d if fresh else None

    def deferred_steps(self) -> str:
        """For the wake-up call: last night's check-in, first."""
        d = self.deferred()
        if not d:
            return ""
        day = dt.date.fromisoformat(d["day"])
        logs = f" Then what {', '.join(d['classes'])} covered (for the study logs)." if d.get("classes") else ""
        return (
            f"Last night's {d['name']} check-in was moved to this call. Before planning the day, ask: anything for "
            f"the journal of {day:%A}?{logs} Then go on with today."
        )

    def take_deferred(self, lines: list[dict]) -> bool:
        """After the wake-up call: last night's part goes into that day's journal (and study logs)."""
        d = self.deferred()
        if not d:
            return False
        self.deferred_file.unlink(missing_ok=True)
        self.app.scheduler.cancel("checkins:deferred")
        day = dt.date.fromisoformat(d["day"])
        self._status(d["name"], day, "answered")
        said = daily.their_words(self.app, lines)
        if said and self.setting("journal"):
            self._notes(d["name"], day, lines, said, classes=d.get("classes") or [], when="on my wake-up call")
        return True

    def _deferred_message(self, p: dict) -> None:
        """No wake-up call to carry it: ask last night's check-in by message in the morning."""
        d = self.deferred()
        if not d:
            return
        self.deferred_file.unlink(missing_ok=True)
        day = dt.date.fromisoformat(d["day"])
        self._status(d["name"], day, "asked")
        logs = f" What did {', '.join(d['classes'])} cover?" if d.get("classes") else ""
        self.app.notify(
            f"Last night's check-in, as promised: anything for {day:%A}'s journal?{logs} What's first today?"
            "\n\n(Reply to this message.)",
            kind="question",
            map_kind="checkin",
            map_ref=f"{d['name']}:{d['day']}",
            why="asked",  # you put it off to this morning
        )

    # ------------------------------------------------------------------------------- learned times
    def _minutes(self, t: dt.datetime, day: dt.date) -> int:
        """Minutes from the start of a check-in day (so 00:30 after a 22:00 evening counts as later, not earlier)."""
        return int((t - dt.datetime.combine(day, self._day_start())).total_seconds() // 60)

    def learn(self) -> list[str]:
        """Move a check-in you keep doing at another time to that time (with Undo). Returns the lines told."""
        if not self.setting("learn_times"):
            return []
        state_f = self.app.paths.state / "checkins" / "learned.json"
        state = jload(state_f, {}) or {}
        today, told = self.day_of(), []
        times = dict(self.setting("times") or {})
        for name in NAMES:
            cur = times.get(name)
            last = state.get(name) or {}
            wait = dt.timedelta(days=30 if last.get("undone") else LEARN_DAYS)
            if not cur or (last.get("at") and now() - dt.datetime.fromisoformat(last["at"]) < wait):
                continue
            actual = []
            for k in range(1, LEARN_DAYS + 1):
                d = today - dt.timedelta(days=k)
                e = self.today(d).get(name) or {}
                if e.get("status") != "answered" or e.get("lighter"):  # a lighter day's time was mine, not yours
                    continue
                at = self.at(d, e.get("time") or cur)  # moved: the time it was moved to
                if e.get("answered_at") and not e.get("moved"):
                    a = dt.datetime.fromisoformat(e["answered_at"]).replace(tzinfo=None)
                    at = a if dt.timedelta(0) <= a - at <= dt.timedelta(hours=LEARN_LATE_H) else at
                actual.append(self._minutes(at, d))
            if len(actual) < LEARN_MIN_DAYS:
                continue
            base = self._minutes(self.at(today, cur), today)
            off = [m for m in actual if abs(m - base) >= LEARN_GAP_MIN]
            if len(off) < LEARN_OFF_DAYS or not (all(m > base for m in off) or all(m < base for m in off)):
                continue
            mid = int(round(sorted(off)[len(off) // 2] / 15) * 15)
            new = f"{dt.datetime.combine(today, self._day_start()) + dt.timedelta(minutes=mid):%H:%M}"
            if new == cur:
                continue
            times[name] = new
            self.app.settings.set("checkins.times", times)
            state[name] = {"at": now().isoformat(timespec="seconds"), "from": cur, "to": new}
            jsave(state_f, state)
            line = (
                f"Your {name} check-in is at {new} from now on, not {cur}: on {len(off)} of the last "
                f"{len(actual)} days you did it around then."
            )
            self.app.events.emit("checkin_time_learned", name=name, from_time=cur, to_time=new, days=len(off))
            self.app.notify(line, kind="info", why="checkins.learned", buttons=[[("Undo", f"chkl:{name}:undo")]])
            told.append(line)
        return told

    def _learn_button(self, name: str, act: str) -> str:
        state_f = self.app.paths.state / "checkins" / "learned.json"
        state = jload(state_f, {}) or {}
        last = state.get(name)
        if act != "undo" or not last or last.get("undone"):
            return "Nothing to undo."
        times = dict(self.setting("times") or {})
        if times.get(name) == last["to"]:
            times[name] = last["from"]
            self.app.settings.set("checkins.times", times)
        state[name] = {**last, "undone": True, "at": now().isoformat(timespec="seconds")}
        jsave(state_f, state)
        self.app.events.emit("checkin_time_unlearned", name=name)
        return f"Back to {last['from']}; I'll leave the {name} check-in's time alone."

    # ------------------------------------------------------------------------------------- buttons
    def callbacks(self):
        def btn(ref: str, act: str) -> str:
            name, _, day = ref.partition("|")
            d = dt.date.fromisoformat(day) if day else self.day_of()
            if act == "p30":
                return self.postpone(name, 30, d, via="button")
            if act == "defer":
                return self.defer(name, d, via="button")
            if act == "not":  # Not tonight, under the evening's reflection: over for the day, nothing more asked
                self.skip(name, d, via="not_tonight")
                return "OK, not tonight."
            if act == "now":
                if not self._by_call():
                    return "Phone calls aren't on."
                self._undefer(name, d)
                self._call(name, d, asked=True)
                return "Calling you now."
            return self.skip(name, d, via="button")

        return {"chk": btn, "chkl": self._learn_button}

    def commands(self):
        return [
            Command("checkins", "today's check-ins (with +30 min and Skip buttons)", self._list),
            Command("checkin", "move or skip one: /checkin evening 21:30 (or: skip, morning)", self._cmd),
        ]

    def _list(self, msg: Incoming, arg: str) -> str | None:
        plan = self.today()
        rows = [f"{n}: {c.get('time') or '-'} ({c['status']})" for n, c in plan.items()]
        if not rows:
            return "No check-ins today. /checkin evening 22:00 sets one."
        buttons = [
            [
                (f"{n.title()} +30 min", f"chk:{n}:p30"),
                *([("Tomorrow morning", f"chk:{n}:defer")] if n == "night" else []),
                (f"Skip {n}", f"chk:{n}:skip"),
            ]
            for n, c in plan.items()
            if c["status"] == "planned"
        ]
        if not buttons or not msg.respond:
            return "\n".join(rows)
        msg.reply("\n".join(rows), buttons=buttons)
        return None

    def _cmd(self, msg: Incoming, arg: str) -> str:
        m = re.match(r"(\w+)\s+(.+)", arg)
        if not m or m[1].lower() not in NAMES:
            return "Usage: /checkin evening 21:30   (or midday, night; 'skip' drops it today, 'morning' moves it there)"
        name, what = m[1].lower(), m[2].strip().lower()
        if what == "skip":
            return self.skip(name)
        if what in ("morning", "tomorrow morning", "defer"):
            return self.defer(name)
        tm = a_time(f"at {what}")
        return self.move(name, tm) if tm else "What time? e.g. /checkin evening 21:30"

    def intents(self):
        def match(text: str):
            if re.search(r"\b(?:call|ring) me\b", text, re.I):
                return None
            # a check-in named ("the evening call", "tonight's call", "check-in"), not any call: "cancel that call"
            # and "call-me --cancel …" aren't about the evening check-in
            if not any(w.group(1) or w.group(2).lower() != "call" for w in WORDS.finditer(text)):
                return None
            low = text.lower()
            day = a_day(text, self._base())
            if day is None:  # a day it can't pin down ("yesterday", "next week"): the AI works it out
                return None
            name = _name_in(low)
            if re.search(r"\b(?:don'?t|do not|never)\s+(?:skip|cancel)\b", low):
                return None
            if SKIP.search(text):
                return {"name": name, "act": "skip", "day": day}
            mins, tm = a_minutes(text), a_time(text)
            if (
                tm
                and name in ("evening", "night")
                and 6 <= int(tm[:2]) < 12
                and not re.search(r"\bam\b|morning", low)
                and not as_written(text)
            ):
                tm = f"{int(tm[:2]) + 12:02d}{tm[2:]}"  # "move Friday's check-in to 9:30", said in the morning
            if mins and re.search(r"\b(?:push|postpone|later|delay|by|after)\b", low):
                return {"name": name, "act": "postpone", "mins": mins, "day": day}
            if tm and (MOVE.search(text) or re.search(r"\bat\b", low)):
                return {"name": name, "act": "move", "time": tm, "day": day}
            return None

        def run(msg, s):
            day = None if s["day"] == self.day_of() else s["day"]  # no other day named: today, as you mean it
            if s["act"] == "skip":
                return self.skip(s["name"], day, via="intent")
            if s["act"] == "postpone":
                return self.postpone(s["name"], s["mins"], day, via="intent")
            return self.move(s["name"], s["time"], day, via="intent")

        return [
            Intent(
                "move_checkin",
                "move, postpone or skip a check-in",
                match,
                run,
                examples=("move the evening check-in to 21:30", "skip the evening check-in"),
            )
        ]

    # -------------------------------------------------------------------------------------- by call
    def _by_call(self) -> bool:
        calls = self.app.modules.get("calls")
        return bool(self.setting("by_call") and calls and self.app.is_on("calls") and calls.ready()[0])

    def call_schedule(self) -> list[dict]:
        """Today's check-in calls, so the call line can ring them if this computer is off then."""
        if not self._by_call():
            return []
        day, out = self.day_of(), []
        for name, c in self.today(day).items():
            if c.get("status") == "planned" and c.get("time"):
                at = self.at(day, c["time"])
                if at.timestamp() > time.time() - 120:
                    out.append(
                        {
                            "at": int(at.timestamp()),
                            "reason": self._reason(name),
                            "alarm": False,
                            "key": f"checkins:{name}:{day.isoformat()}",
                        }
                    )
        return out

    def call_outcome(self, key: str, outcome: str) -> bool:
        """How a check-in call went. True when this took care of what happens next."""
        _, name, day = (key.split(":") + ["", ""])[:3]
        if not day or name not in self.today(dt.date.fromisoformat(day)):
            return False
        d = dt.date.fromisoformat(day)
        self.app.scheduler.cancel(f"checkins:unstick:{name}")
        if outcome == "answered":
            self._status(name, d, "answered", answered_at=now().isoformat(timespec="seconds"))
        elif outcome == "later":  # "Later" on the ringing phone: the same check-in, half an hour on
            calls = self.app.modules.get("calls")
            self.postpone(name, (calls.setting("later_min") if calls else None) or 30, d, via="call")
        elif outcome == "skip":
            self.skip(name, d, via="call")
        elif outcome in ("missed", "decline"):
            if (self.today(d).get(name) or {}).get("status") == "calling":  # not already asked by message
                self._fallback(name, d, "missed call" if outcome == "missed" else "declined")
        elif outcome == "held":  # past the day's calls (core/calm.py): by message instead
            self._fallback(name, d, "today's call came already")
        else:
            return False
        return True

    def call_reschedule(self, key: str, at: dt.datetime) -> str | None:
        """ "Call me back at …" during a check-in call: the same check-in at that time (or, past tonight, on the
        wake-up call), never a new call without its steps."""
        _, name, day = (key.split(":") + ["", ""])[:3]
        if name not in NAMES or not day:
            return None
        d = dt.date.fromisoformat(day)
        if self.day_of(at) == d:
            return self.move(name, f"{at:%H:%M}", d, via="call")
        if self.day_of(at) > d and (name == "night" or at.hour < 12):
            return self.defer(name, d, via="call")
        return self.move(name, f"{at:%H:%M}", self.day_of(at), via="call")

    def call_transcript(self, key: str, lines: list[dict]) -> None:
        """After a check-in call: with Chat on, the AI writes your journal (and study logs for the classes you talked
        about) from what you said; otherwise your side goes into the journal as it is."""
        _, name, day = (key.split(":") + ["", ""])[:3]
        if not self.setting("journal") or not day:
            return
        d = dt.date.fromisoformat(day)
        if (self.today(d).get(name) or {}).get("status") == "deferred":
            return  # too tired: the wake-up call takes it from here
        said = daily.their_words(self.app, lines)
        if not said:
            return
        self.app.events.emit("checkin_answered", name=name, chars=len(said), via="call")
        classes = self.logs_due(d) if name in ("evening", "night") else []
        self._notes(name, d, lines, said, classes=classes)

    def _notes(self, name: str, d: dt.date, lines: list[dict], said: str, classes: list[str], when: str = "") -> None:
        day = d.isoformat()
        payload = {"name": name, "day": day, "said": said}
        on = when or f"on my {name} check-in call"
        if self.setting("ai_notes") and daily.ai_on(self.app):
            jid = daily.run_skill(
                self.app,
                "journal",
                f"About {day}, {on}, in my words:\n{said}",
                title=f"Journal from your {name} call",
                then="checkins.notes_done",
                then_payload=payload,
                lane="bg",  # nobody waits for it: a request you type meanwhile doesn't queue behind it (0.7.3)
            )
            if jid:
                if classes:
                    daily.run_skill(
                        self.app,
                        "study-log",
                        f"Classes on {day}: {', '.join(classes)}. What I said about them {on} (log only what I "
                        f"said; leave out a class I didn't talk about):\n\n{daily.transcript(self.app, lines)}",
                        title=f"Study logs from your {name} call",
                        lane="bg",
                    )
                    self._status(name, d, (self.today(d).get(name) or {}).get("status", "answered"), logged=classes)
                self.app.events.emit("checkin_notes_started", name=name, study_logs=len(classes))
                return
        self._journal_raw(payload)

    def _journal_raw(self, p: dict) -> None:
        heading = f"{p['name'].title()} check-in, by call ({now():%H:%M})"
        daily.append(self.app, heading, p["said"], dt.date.fromisoformat(p["day"]))

    def _notes_done(self, job, result, payload: dict) -> None:
        """The AI couldn't write the journal: keep your words anyway."""
        if not result.ok:
            self._journal_raw(payload)

    def call_brief(self) -> dict:
        plan = self.today()
        rows = [f"{n} {c.get('time') or '-'} ({c['status']})" for n, c in plan.items()]
        return {"checkins_today": rows} if rows else {}

    def call_tools(self):
        return [
            Tool(
                "change_checkin",
                "Plan, move, postpone, skip or defer a check-in (names: evening, midday, night); today unless a day "
                "is given. defer: they're too tired, the rest goes to tomorrow's wake-up call.",
                self._tool_change,
                {
                    "name": arg(),
                    "action": {"type": "string", "enum": ["move", "postpone", "skip", "defer"]},
                    "when": arg('for move: "21:30"; for postpone: minutes, e.g. "30"'),
                    "day": arg('optional: "tomorrow" or a weekday, e.g. "friday"'),
                },
                ("name", "action"),
                offline="queue",
                hint="change_checkin plans, moves, postpones, skips or defers check-ins (also another day's). To have "
                "a check-in call later, use change_checkin, not schedule_call.",
            ),
            Tool(
                "defer_checkin",
                "They're too tired for this check-in: what's left of it moves to tomorrow's wake-up call.",
                lambda a: self.defer(str(a.get("name") or "night").lower(), via="call"),
                {"name": arg("evening, midday or night (default night)")},
                offline="queue",
                hint="If they're too tired for a check-in call, call defer_checkin and say goodnight.",
            ),
            Tool(
                "checkin_script",
                "The steps for a check-in call (evening debrief, midday or night check-in), with today's details.",
                self._tool_script,
                {"name": arg("evening, midday or night")},
                offline="brief",
                hint="On a check-in call (the reason is Evening debrief, Midday check-in or Night check-in), first "
                "call checkin_script with that name and follow it.",
            ),
        ]

    def _tool_change(self, a: dict) -> str:
        name = str(a.get("name", "evening")).lower()
        if name not in NAMES:
            return f"There's no {name} check-in (evening, midday or night)."
        day = a_day(str(a.get("day") or ""), self._base())
        if day is None:
            return f"I couldn't tell which day {a.get('day')!r} is; say tomorrow or a weekday."
        act, when = a.get("action"), str(a.get("when", "")).strip()
        day = None if day == self.day_of() else day  # no other day named: today, as they mean it
        if act == "skip":
            return self.skip(name, day, via="call")
        if act == "defer":
            return self.defer(name, day, via="call")
        if act == "postpone":
            return self.postpone(name, int(re.sub(r"\D", "", when) or 30), day, via="call")
        tm = a_time(f"at {when}")
        return self.move(name, tm, day, via="call") if tm else f"I couldn't read the time {when!r}."

    def _tool_script(self, a: dict):
        name = str(a.get("name") or "").lower()
        if name in NAMES:
            return self.script(name)
        return {n: self.script(n) for n in NAMES}  # the call line keeps them all for when this computer is off

    # ------------------------------------------------------------------------------------- the scripts
    def _classes(self, day: dt.date) -> list[dict]:
        """The day's classes and what became of each one's after-class question: "" (not asked or no answer yet),
        "later", "answered", "nothing", or "skipped"."""
        if not self.app.is_on("subjects"):
            return []
        subj = self.app.modules["subjects"]
        skip = subj.skipped(day)
        cap = self.app.modules.get("capture")
        status = cap.statuses(day) if cap is not None and self.app.is_on("capture") else {}
        return [
            {
                "name": c["name"],
                "start": c["start"],
                "slug": c["subject"],
                "status": "skipped" if c["subject"] in skip else status.get(c["subject"], ""),
            }
            for c in subj.classes_on(day, include_skipped=True)
        ]

    def logs_due(self, day: dt.date) -> list[str]:
        """Classes of the day with no study log yet: not answered after class, and not talked through on a call."""
        plan = self.today(day)
        done = {n for c in plan.values() for n in c.get("logged", [])}
        return [c["name"] for c in self._classes(day) if c["status"] in ("", "later") and c["name"] not in done]

    def done_today(self, day: dt.date) -> list[str]:
        """Up to three things the check-in day's records show you did, never guessed from your words: deadlines
        marked done, threads closed, deadlines moved on ("ps3: 4 of 7 done"), study time, classes you logged after.
        [] when nothing was recorded."""
        app, out = self.app, []
        lo = dt.datetime.combine(day, self._day_start())
        hi = lo + dt.timedelta(days=1)

        def within(stamp) -> bool:
            try:
                return lo <= dt.datetime.fromisoformat(str(stamp)).replace(tzinfo=None) < hi
            except ValueError:
                return False

        def deadlines(progress: bool) -> list[str]:
            if not app.is_on("deadlines"):
                return []
            items = app.modules["deadlines"].items().values()
            if progress:
                return [
                    f"{it['title']}: {it['parts_done']} of {it['parts']} done"
                    for it in items
                    if it.get("status") == "open" and it.get("parts_done") and within(it.get("progress_at"))
                ]
            return [f"{it['title']}: done" for it in items if it.get("status") == "done" and within(it.get("done_at"))]

        def closed() -> list[str]:
            from kurooto.core import threads

            rows = threads.closed_between(app, lo.timestamp(), hi.timestamp())
            return [f"{r['text']}: done" for r in rows if str(r.get("key") or "").split(":")[0] not in OWN_RECORD]

        def study() -> list[str]:
            st = app.modules.get("study")
            if st is None or not app.is_on("study"):
                return []
            spent = {k: v for k, v in st.totals(1, last=day).items() if v >= REFLECT_STUDY_MIN * 60}
            rows = sorted(spent.items(), key=lambda kv: -kv[1])
            return ["Studied " + ", ".join(f"{st.name_of(k)} {_span(v)}" for k, v in rows)] if rows else []

        def classes() -> list[str]:
            logged = [c["name"] for c in self._classes(day) if c["status"] == "answered"]
            return [f"Logged what {' and '.join(logged)} covered"] if logged else []

        for part, fn in (
            ("done", lambda: deadlines(False)),
            ("threads", closed),
            ("progress", lambda: deadlines(True)),
            ("study", study),
            ("classes", classes),
        ):
            try:
                out += fn()
            except Exception as e:  # one record that can't be read never stops the check-in
                app.events.emit("checkin_reflect_failed", part=part, error=f"{type(e).__name__}: {e}"[:200])
        return out[:REFLECT_N]

    def _night_planned(self, day: dt.date) -> str | None:
        c = self.today(day).get("night") or {}
        return c.get("time") if c.get("status") == "planned" else None

    def script(self, name: str) -> str:
        """What the call goes through, step by step, with today's details filled in."""
        app, today = self.app, self.day_of()
        plan = daily.plan(app, today, 1200)
        notes_by_ai = self.setting("ai_notes") and daily.ai_on(app)
        later = "If they want this call later, use change_checkin (postpone or move), never schedule_call."
        if name == "midday":
            return "\n".join(
                [
                    "Midday check-in, about 5 minutes.",
                    *([f"Today's plan:\n{plan}"] if plan else []),
                    "Ask how the morning went against today's plan.",
                    "Re-plan the afternoon with them in two or three blocks.",
                    "Confirm the evening check-in time, or move or skip it (change_checkin).",
                    later,
                ]
            )
        alarm = " and set it with set_alarm" if app.is_on("alarm") else ""
        if name == "night":
            steps = ["Ask if there's anything more for today's journal; keep their words."]
            due = self.logs_due(today)
            if due:
                steps.append(f"Study logs still due for {', '.join(due)}: ask briefly what each covered.")
            steps.append("Ask tomorrow's top priority.")
            es = app.modules.get("exam_season")
            exam = es.call_line("tomorrow") if es is not None and app.is_on("exam_season") else ""
            if exam:  # 0.9.0 (exam_season.in_calls): tomorrow's exam and a wake time to propose
                steps.append(exam)
            steps.append(f"Ask when they want to wake up{alarm}.")
            steps.append(
                "If they're too tired, call defer_checkin (the rest moves to the wake-up call) and just say goodnight."
            )
            steps.append(
                "Say goodnight. Don't write notes yourself: their journal is written from this call afterwards."
                if notes_by_ai
                else "Say goodnight. What they said goes into their journal after the call."
            )
            head = "Night check-in: goodnight, about 3 to 5 minutes. Keep it gentle; they're about to sleep. " + later
            return "\n".join([head] + [f"{i}. {s}" for i, s in enumerate(steps, 1)])
        steps = ["Ask how today went."]
        did = self.done_today(today) if self.setting("reflect") else []
        if did:
            steps.append(
                f"From today's records they did: {'; '.join(did)}. Say these back in one line, plainly (no praise, "
                "no score, nothing about what they didn't do)."
            )
        classes = [c for c in self._classes(today) if c["status"] != "skipped"]
        if classes:
            names = ", ".join(f"{c['name']} ({c['start']})" for c in classes)
            steps.append(f"Today's classes: {names}. For each, ask what it covered and anything unclear.")
            kept = [c["name"] for c in classes if c["status"] == "later"]
            if kept:
                steps.append(
                    f"They kept the after-class question for this call: {', '.join(kept)}. Once they've said what "
                    "was covered, answer it with answer_question."
                )
        steps.append(
            f"Today's plan said:\n{plan}\nAsk what got done and what slipped." if plan else "Ask what slipped."
        )
        steps.append("If pending_items lists open questions, ask them (answer_question).")
        study = app.modules.get("study")
        if study is not None and app.is_on("study"):
            counted = ", ".join(f"{study.name_of(k)} {v / 3600:.1f} h" for k, v in study.totals(1, last=today).items())
            steps.append(
                (f"Study counted today: {counted}. " if counted else "No study counted on the computer today. ")
                + "Ask about study on paper or away from the computer and log it with log_study."
            )
        exams = self._exams()
        if exams:
            e = exams[0]
            quiz = " (quiz_next, quiz_grade)" if app.is_on("quiz") else ""
            steps.append(
                f"Coming up: {e.get('title')}, {e.get('when') or e.get('due', '')}. Offer a 10-minute quiz now{quiz} "
                "or tomorrow."
            )
        night = self._night_planned(today)
        if night:
            steps.append(f"Tomorrow and the alarm are for the night check-in at {night}; don't ask them now.")
        else:
            steps.append(f"Ask tomorrow's top priority and when they want to wake up{alarm}.")
        notes = "journal" + (" and study logs" if classes else "")
        end = "Wrap up" if night else "Say goodnight"
        steps.append(
            f"{end}. Don't write notes yourself: their {notes} are written from this call afterwards."
            if notes_by_ai
            else f"{end}. What they said goes into their journal after the call."
        )
        head = (
            "Evening debrief, about 5 to 8 minutes: the day in review. One question at a time; let them talk and "
            "keep yours short. " + later
        )
        return "\n".join([head] + [f"{i}. {s}" for i, s in enumerate(steps, 1)])

    def _exams(self) -> list[dict]:
        """Exams and quizzes in the next two weeks (from Deadlines, when it's on), soonest first."""
        dl = self.app.modules.get("deadlines")
        soon = getattr(dl, "exams_soon", None) if dl is not None and self.app.is_on("deadlines") else None
        if not soon:
            return []
        try:
            return list(soon(days=14) or [])
        except Exception as e:
            self.app.events.emit("checkin_script_failed", part="exams", error=str(e)[:200])
            return []

"""Exam season: one card for the whole exam period, on top of exam mode (which works per subject, two weeks ahead).

The period comes from your exam dates and nothing else: the exam periods in Subjects (/term exams 2026-12-07 to
2026-12-18, or the term note) and the exams on your deadline list ("Linear Algebra final exam", "Topology midterm";
quizzes and tests count only inside an exam period, unless exam_season.quizzes is on). Without exam dates it does
nothing. A season runs from the evening before its first exam day to the end of its last; you're told once when one
starts, with what it will do.

Each part has its own switch (Settings, the card on the dashboard's Features tab, or /examseason):
    hold_updates  non-critical updates wait until the exams are over (a release signed as critical still installs,
                  and so does `kurooto update` or an Update tap)
    alarm_check   every night of the period (21:30), the alarm path is checked (Kurooto keeps itself working's
                  alarm check, and the call line's when a leave-by alarm is set): if tomorrow's alarm might not ring,
                  "set your phone's own alarm too"
    eve           the evening before each exam (18:00), once: where is it, which seat, calculator, ID card?
    leave_alarm   on the exam day, an alarm to leave (45 minutes before it starts, or the time you say: "leave 8:10";
                  "no alarm" turns it off): a call that rings like an alarm with Phone calls on, else an urgent
                  message
    debrief       half an hour after each exam: a two-minute debrief (what came up, what went well, what to fix),
                  saved as you said it to the subject's course note under "Exam debriefs" (the daily note when the
                  exam has no subject)
    no_calls      no calls during an exam (from 15 minutes before it, for exam_min, 3 hours)
    budget        the daily message limit (core/calm.py) tightens: during the day only deadlines, quizzes, the alarm
                  and exam season itself come; everything else that comes by itself waits for the evening bundle
    revision      from revision_days (14) before each exam, its course's topics ranked and laid into your free time with
                  what to read; the evening asks whether you covered them (modules/revision.py, /revise)
The quiz call before an exam stays off unless you pick it for that exam (the card, or /examseason): then, with Quiz and
Phone calls on, Kurooto calls you for a quiz the evening before (19:00) instead of offering one, and exam mode's
practice check-ins may call for it (quiz.by_call). For the other exams of the season they stay messages.

budget_during_exams() names the features whose messages still come during a season; Calm (core/calm.py) asks it
before each message and call. State: state/exam_season.json.
"""

from __future__ import annotations

import datetime as dt
import re

from kurooto.core import layout
from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.lock import Lock
from kurooto.core.notinterested import matcher
from kurooto.core.state import jload, jsave
from kurooto.modules import daily
from kurooto.modules.base import Command, Incoming, Intent, Module
from kurooto.modules.revision import REVISE_Q, Revision

register_defaults(
    "exam_season",
    {
        "hold_updates": True,  # non-critical updates wait until the exams are over
        "alarm_check": True,  # every night of the period: will tomorrow's alarm ring?
        "night_at": "21:30",  # ...checked at this time
        "eve": True,  # the evening before each exam: where is it, which seat, calculator, ID card?
        "eve_at": "18:00",  # ...asked from this time
        "leave_alarm": True,  # on the exam day, an alarm to leave (a call with Phone calls on, else a message)
        "leave_min": 45,  # ...this long before the exam starts, unless you say a time ("leave 8:10")
        "debrief": True,  # after each exam: a two-minute debrief, into the subject's course note
        # (0.9.0) the debrief waits for you to be back: at your desk (Face presence or the computer in use) or the
        # phone arriving at a place you saved as "home", at the latest DEBRIEF_WAIT_MIN after the exam
        "debrief_at_desk": False,
        # (0.9.0) the wake-up call and the night check-in name the exam that day or the next, with when to leave and
        # a wake time to propose (the alarm is still set only when you say so)
        "in_calls": True,
        "no_calls": True,  # no calls during an exam
        "budget": True,  # only deadlines, quizzes and the alarm during the day; the rest waits for the evening bundle
        "exam_min": 180,  # how long an exam takes (no calls then; the debrief comes half an hour after)
        "quizzes": False,  # quizzes and tests outside an exam period count as exams too
        "quiz_call_at": "19:00",  # the evening before an exam you picked a quiz call for
        "revision": True,  # before each exam, its course's topics ranked and laid into your free time (/revise)
        "revision_days": 14,  # the revision plan starts this many days before each exam
        "revision_share": 50,  # % of your free time (Start-by's, less commitments) revision blocks may take
        "block_min": 60,  # one revision block, in minutes (one topic each)
        "revision_ask": True,  # the evening: did you cover today's topics? (counts like a quiz answer)
    },
)

PIECES = {
    "hold_updates": "Hold non-critical updates",
    "alarm_check": "Check the alarm every night",
    "eve": "Ask the evening before: venue, seat, calculator, ID",
    "leave_alarm": "Alarm to leave on time",
    "debrief": "Two-minute debrief after each exam",
    "no_calls": "No calls during an exam",
    "budget": "Only deadlines, quizzes and the alarm by day",
    "revision": "Revision plan before each exam",
}
SAID = {  # the season's first message, part by part
    "hold_updates": "updates wait (critical fixes still install)",
    "alarm_check": "your alarm is checked every night",
    "eve": "the evening before each exam I ask where it is",
    "leave_alarm": "an alarm to leave on time",
    "debrief": "a two-minute debrief after each one",
    "no_calls": "no calls during an exam",
    "budget": "during the day only deadlines, quizzes and the alarm message you (the rest waits for the evening)",
    "revision": "a revision plan in your free time before each exam (/revise)",
}
BIG = re.compile(r"\b(exam|exams|midterm|mid-term|finals?|midsem|mid-sem|endsem|end-sem|viva|oral)\b", re.I)
TIME = r"(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm)?\b"
LEAVE = re.compile(r"\bleav(?:e|ing)\s+(?:by\s+|at\s+)?" + TIME, re.I)
START = re.compile(r"\b(?:starts?|starting|begins?)\s+(?:at\s+)?" + TIME, re.I)
NO_ALARM = re.compile(r"\bno\s+(?:leave[- ]?by\s+|leaving\s+)?alarm\b|\bdon'?t\s+ring\b", re.I)
DAY = dt.timedelta(days=1)
MERGE_DAYS = 3  # exam days this close (a weekend between) are one season
SEATED_MIN = 15  # no calls from this long before an exam starts
DEBRIEF_AFTER_MIN = 30  # the debrief comes this long after the exam ends
DEBRIEF_UNTIL_H = 36  # ...and isn't asked later than this after it
DEBRIEF_WAIT_MIN = 90  # (debrief_at_desk) waiting for you to be back: at most this long after the exam ends
WAKE_BEFORE_LEAVE_MIN = 60  # (in_calls) the wake time proposed on the night check-in: this long before leaving
QUIZ_CALL_UNTIL_H = 3  # the picked quiz call isn't placed later than this after quiz_call_at
SNOOZES = 2  # "Later" on the leave-by alarm rings again in 5 minutes, this many times
BUDGET_KEEP = ("deadlines", "quiz", "alarm", "exam_season")  # what still comes by day (core/calm.py)


def _hhmm(h: str, mi: str | None, ap: str | None) -> dt.time | None:
    try:
        hour, minute = int(h), int(mi or 0)
    except (TypeError, ValueError):
        return None
    ap = (ap or "").lower()
    if ap == "pm" and hour < 12:
        hour += 12
    elif ap == "am" and hour == 12:
        hour = 0
    return dt.time(hour, minute) if 0 <= hour < 24 and 0 <= minute < 60 else None


def _day(d: dt.date) -> str:
    return f"{d:%a} {d.day} {d:%b}"


class ExamSeason(Module):
    id = "exam_season"
    title = "Exam season"
    description = (
        "One card for the whole exam period: updates wait, your alarm is checked every night, the evening before each "
        "exam a question about where it is and an alarm to leave, a short debrief after it, and a revision plan "
        "before it. Each part has a switch."
    )
    requires = ("deadlines",)
    extra = True  # an add-on: turned on by hand, never by a preset
    privacy = (
        "Stays on this computer. With Phone calls on, the leave-by alarm (its time, the exam and what you said about "
        "the venue) goes to your call line so it can ring, like any call."
    )

    def __init__(self, app):
        super().__init__(app)
        self.revision = Revision(self)

    @property
    def file(self):
        return self.app.paths.state / "exam_season.json"

    def _load(self) -> dict:
        return jload(self.file, {}) or {}

    def _edit(self, i: str, **fields) -> dict:
        """Change what's kept about one exam (its eve answer, the leave-by alarm, the debrief)."""
        with Lock(self.app.paths.state, "exam_season"):
            st = self._load()
            ex = st.setdefault("exams", {}).setdefault(i, {})
            ex.update(fields)
            jsave(self.file, st)
        return ex

    def _mine(self, i: str) -> dict:
        return (self._load().get("exams") or {}).get(i) or {}

    def _int(self, key: str, default: int) -> int:
        try:
            return int(self.setting(key))
        except (TypeError, ValueError):
            return default

    def _time(self, key: str, default: str) -> dt.time:
        try:
            return dt.time.fromisoformat(str(self.setting(key) or default))
        except ValueError:
            return dt.time.fromisoformat(default)

    def _calls_ok(self) -> bool:
        c = self.app.modules.get("calls")
        return bool(c and self.app.is_on("calls") and c.ready()[0])

    # ------------------------------------------------------------------------------------------ lifecycle
    def deadline_changed(self, j: str, what: str) -> None:
        """(0.9.0) A deadline moved or was done (modules/deadlines.py): the revision plan follows it."""
        if self.setting("revision"):
            self.revision.deadline_changed(j, what)

    def start(self):
        self.every("tick", "every 15m", self._tick)
        self.action("leave", self._leave)
        self.action("night_again", lambda p: self._night(again=True))
        self.app.ask.hooks["exam_season.eve"] = self._eve_answer
        self.app.ask.hooks["exam_season.debrief"] = self._debrief_answer
        self.app.availability.blockers["exam_season:exam"] = self._block
        self.app.updates.holds[self.id] = self.update_hold

    def stop(self):
        super().stop()
        if self.app.scheduler.cancel_prefix(f"calls:ring:{self.id}:") and self.app.is_on("calls"):
            self.app.modules["calls"].connector.poke()  # the call line forgets the leave-by alarms
        self.app.availability.blockers.pop("exam_season:exam", None)
        self.app.updates.holds.pop(self.id, None)
        for h in ("exam_season.eve", "exam_season.debrief"):
            self.app.ask.hooks.pop(h, None)

    # ------------------------------------------------------------------------------------- the exam dates
    def _deadlines(self):
        return self.app.modules.get("deadlines") if self.app.is_on("deadlines") else None

    def periods(self) -> list[tuple[dt.date, dt.date]]:
        """The exam periods in Subjects (/term exams, the term note), first to last."""
        s = self.app.modules.get("subjects")
        if s is None or not self.app.is_on("subjects"):
            return []
        out = []
        for p in s.exam_periods():
            try:
                a, b = sorted(dt.date.fromisoformat(str(x)[:10]) for x in p)
            except (TypeError, ValueError):
                continue
            out.append((a, b))
        return sorted(out)

    def exams(self) -> list[dict]:
        """The exams that make a season, from the deadline list, soonest first: id, title, subject, name, day, start
        (None while the time isn't known), end, and what you told Kurooto (details, leave, quiz_call)."""
        dl = self._deadlines()
        if dl is None:
            return []
        periods, skip, quizzes = self.periods(), matcher(self.app), bool(self.setting("quizzes"))
        mine = self._load().get("exams") or {}
        length = dt.timedelta(minutes=max(1, self._int("exam_min", 180)))
        out = []
        for i, it in dl.items().items():
            title = str(it.get("title") or "")
            if it.get("kind") != "exam" or it.get("status") != "open" or skip(title):
                continue
            try:
                due = dt.datetime.fromisoformat(it["due"]).replace(second=0, microsecond=0)
            except (KeyError, TypeError, ValueError):
                continue
            if not (quizzes or BIG.search(title) or any(a <= due.date() <= b for a, b in periods)):
                continue
            m = mine.get(i) or {}
            start = None if it["due"][11:16] == "23:59" else due
            if m.get("start"):
                try:
                    start = dt.datetime.combine(due.date(), dt.time.fromisoformat(m["start"]))
                except ValueError:
                    pass
            out.append(
                {
                    "id": i,
                    "title": title,
                    "subject": it.get("subject"),
                    "name": dl.subject_name(it.get("subject")),
                    "day": due.date(),
                    "start": start,
                    "end": start + length if start else None,
                    "details": m.get("details") or "",
                    "leave": m.get("leave"),
                    "quiz_call": bool(m.get("quiz_call")),
                }
            )
        return sorted(out, key=lambda e: (e["day"], e["start"] or dt.datetime.combine(e["day"], dt.time.max)))

    def _exam(self, i: str) -> dict | None:
        return next((e for e in self.exams() if e["id"] == i), None)

    def seasons(self, exams: list[dict] | None = None) -> list[tuple[dt.date, dt.date]]:
        """Each exam season, (first exam day, last exam day): exam periods and exam days close together are one."""
        spans = sorted(self.periods() + [(e["day"], e["day"]) for e in (self.exams() if exams is None else exams)])
        out: list[tuple[dt.date, dt.date]] = []
        for a, b in spans:
            if out and a <= out[-1][1] + dt.timedelta(days=MERGE_DAYS):
                out[-1] = (out[-1][0], max(out[-1][1], b))
            else:
                out.append((a, b))
        return out

    def season(self, t: dt.datetime | None = None, exams: list[dict] | None = None) -> tuple[dt.date, dt.date] | None:
        """The season on at t: from the day before its first exam to the end of its last. None outside one."""
        d = (t or now()).date()
        return next(((a, b) for a, b in self.seasons(exams) if a - DAY <= d <= b), None)

    # ------------------------------------------------------------------------------- what others ask it
    def update_hold(self) -> str:
        """For the update service (app.updates.holds): why a non-critical update waits now ("" when it doesn't)."""
        if not self.setting("hold_updates"):
            return ""
        s = self.season()
        return f"your exams (until {_day(s[1])})" if s else ""

    def budget_during_exams(self) -> dict | None:
        """For Calm's daily limit (core/calm.py, which asks before each message and call while the "budget" part is
        on): during an exam season, the features whose messages still come by day ({"keep": feature ids, "until":
        the season's last minute}); None outside a season."""
        s = self.season()
        if not s:
            return None
        return {"keep": BUDGET_KEEP, "until": dt.datetime.combine(s[1], dt.time(23, 59))}

    def quiz_call(self, exam_id: str) -> bool | None:
        """For Quiz: True if you picked the quiz call for this exam (and Phone calls can place it), False for a season
        exam you didn't pick (no quiz call rings for it by itself), None otherwise (Quiz does what it always does)."""
        e = self._exam(exam_id)
        if e is None:
            return None
        if not e["quiz_call"]:
            return False
        return True if self._calls_ok() else None

    def _block(self, t: dt.datetime):
        """No calls during an exam (availability blocker)."""
        if not self.setting("no_calls"):
            return None
        for e in self.exams():
            if e["start"] and e["start"] - dt.timedelta(minutes=SEATED_MIN) <= t < e["end"]:
                return "you're in an exam", e["end"]
        return None

    # -------------------------------------------------------------------------------------------- the tick
    def _tick(self, p: dict | None = None) -> dict:
        """Every 15 minutes: the season's first message, the eve questions, leave-by alarms, debriefs, picked quiz
        calls and the nightly alarm check, each when it's due. Nothing without exam dates."""
        t = now()
        exams = self.exams()
        season = self.season(t, exams)
        did: dict = {}
        if not exams and not season:
            return did
        if season:
            did["announced"] = self._announce(season, exams, t)
        for e in exams:
            if self.setting("eve") and self._eve_due(e, t):
                did.setdefault("eve", []).append(self._ask_eve(e, t))
            self._leave_sync(e, t)
            if self.setting("debrief") and self._debrief_due(e, t):
                did.setdefault("debrief", []).append(self._ask_debrief(e))
            if e["quiz_call"] and self._quiz_call_due(e, t):
                did.setdefault("quiz_call", []).append(self._place_quiz_call(e))
        if self.setting("alarm_check") and self._night_due(t, exams):
            did["night"] = self._night()
        if self.setting("revision"):
            self.revision.today(t)  # the day's blocks, fixed the first time they're worked out
            if self.setting("revision_ask") and self.revision.ask(t):
                did["revision"] = True
        self._prune(t)
        return did

    def _announce(self, season: tuple[dt.date, dt.date], exams: list[dict], t: dt.datetime) -> bool:
        """Once per season: when it is and what it will do."""
        a, b = season
        with Lock(self.app.paths.state, "exam_season"):
            st = self._load()
            told = st.setdefault("told", [])
            if a.isoformat() in told:
                return False
            told.append(a.isoformat())
            st["told"] = told[-20:]
            jsave(self.file, st)
        n = sum(1 for e in exams if a <= e["day"] <= b)
        span = _day(a) if a == b else f"{_day(a)} to {_day(b)}"
        on = [SAID[k] for k in PIECES if self.setting(k)]
        text = f"Exam season: {span}" + (f", {n} exam{'s' if n != 1 else ''}" if n else "") + "."
        text += f" Until it's over: {'; '.join(on)}." if on else " Every part of it is switched off."
        self.app.notify(text + " /examseason shows it and switches parts off.", kind="info", why="exam_season.start")
        self.app.events.emit("exam_season_on", days=(b - a).days + 1, exams=n, parts=len(on))
        return True

    def _prune(self, t: dt.datetime) -> None:
        """Forget what was kept about exams more than 30 days ago."""
        st = self._load()
        old = (t.date() - dt.timedelta(days=30)).isoformat()
        gone = [i for i, x in (st.get("exams") or {}).items() if str(x.get("day") or "9999") < old]
        if gone:
            with Lock(self.app.paths.state, "exam_season"):
                st = self._load()
                for i in gone:
                    (st.get("exams") or {}).pop(i, None)
                jsave(self.file, st)

    # --------------------------------------------------------------------------------------- the eve
    def _eve_moment(self, e: dict) -> dt.datetime:
        return dt.datetime.combine(e["day"] - DAY, self._time("eve_at", "18:00"))

    def _eve_due(self, e: dict, t: dt.datetime) -> bool:
        if self._mine(e["id"]).get("eve_q"):
            return False
        until = e["start"] - dt.timedelta(hours=2) if e["start"] else dt.datetime.combine(e["day"], dt.time(10, 0))
        return self._eve_moment(e) <= t < until

    def _ask_eve(self, e: dict, t: dt.datetime) -> str:
        """Once, the evening before: where, which seat, calculator, ID card (and when, if it isn't known)."""
        self._leave_sync(e, t)  # the default leave-by alarm first, so the question can say when it rings
        when = "Tomorrow" if e["day"] == t.date() + DAY else "Today" if e["day"] == t.date() else _day(e["day"])
        at = f" at {e['start']:%H:%M}" if e["start"] else " (I don't know the time)"
        if e["start"]:
            ask = " Where is it, which seat? Calculator? ID card?"
            like = ' Reply in one line, like "Hall B, seat 34, calculator, ID card".'
        else:
            ask = " Where and when is it, which seat? Calculator? ID card?"
            like = ' Reply in one line, like "Hall B, seat 34, starts 14:00, calculator, ID card".'
        tail = ""
        if self.setting("leave_alarm"):
            how = "ring you" if self._calls_ok() else "message you"
            leave = self._mine(e["id"]).get("leave")
            if leave:
                tail = (
                    f' I\'ll {how} at {dt.datetime.fromisoformat(leave):%H:%M} to leave ("leave 8:00" changes it, '
                    '"no alarm" turns it off).'
                )
            elif not e["start"]:
                tail = f" With the start time I'll {how} {self._int('leave_min', 45)} minutes before it, to leave."
        expires = e["start"] or dt.datetime.combine(e["day"], dt.time(23, 59))
        qid = self.app.ask.ask(
            f"{when}: {e['title']}{at}.{ask}{like}{tail}",
            hook="exam_season.eve",
            hook_payload={"id": e["id"]},
            expires=expires,
            source=self.id,
            title=f"Exam {when.lower() if when in ('Tomorrow', 'Today') else 'coming'}",
            why="exam_season.eve",
            about=e["title"],
        )
        self._edit(e["id"], eve_q=qid, day=e["day"].isoformat())
        self.app.events.emit("exam_eve_asked", timed=bool(e["start"]))
        return qid

    def _eve_answer(self, q: dict, answer: str) -> str:
        """Your answer (Telegram, the phone app or a call): kept for the exam day; it sets the leave-by alarm."""
        i = str((q.get("hook_payload") or {}).get("id") or "")
        e = self._exam(i)
        if e is None:
            return "That exam isn't on your list any more."
        said = "" if q.get("nothing") else str(answer or "").strip()
        fields: dict = {"said": said[:500], "details": said[:300], "day": e["day"].isoformat()}
        m = START.search(said)
        tm = _hhmm(m[1], m[2], m[3]) if m else None
        if tm and not m[3] and 1 <= tm.hour <= 7:  # "starts 2": the afternoon
            tm = tm.replace(hour=tm.hour + 12)
        if tm:
            fields["start"] = f"{tm:%H:%M}"
        fields["leave_off"] = bool(NO_ALARM.search(said))
        self._edit(i, **fields)
        self.app.events.emit("exam_eve_answered", details=bool(said), start=bool(tm), no_alarm=fields["leave_off"])
        e = self._exam(i) or e
        out = "Kept for the exam day." if said else "OK."
        if not self.setting("leave_alarm"):
            return out
        if fields["leave_off"]:
            self._leave_cancel(i)
            return out + " No alarm to leave."
        at = self._leave_sync(e, now())
        if at:
            how = "ring you" if self._mine(i).get("leave_how") == "call" else "message you"
            return out + f" I'll {how} at {at:%H:%M} to leave."
        if not e["start"]:
            return out + " I don't know when it starts, so there's no alarm to leave (\"starts 14:00\" would set one)."
        return out

    # ---------------------------------------------------------------------------------- the leave-by alarm
    def _leave_time(self, e: dict, said: str) -> dt.datetime | None:
        """When to leave: the time you said ("leave 8:10"), else leave_min before the start."""
        start = e["start"]
        m = LEAVE.search(said or "")
        tm = _hhmm(m[1], m[2], m[3]) if m else None
        if tm:
            cands = [dt.datetime.combine(e["day"], tm)]
            if not m[3] and tm.hour < 12:
                cands.append(cands[0] + dt.timedelta(hours=12))
            if not start:
                return cands[0]
            ok = [c for c in cands if start - dt.timedelta(hours=6) <= c < start]
            if ok:
                return max(ok)
        mins = self._int("leave_min", 45)
        return start - dt.timedelta(minutes=mins) if start and mins > 0 else None

    def _leave_text(self, e: dict) -> str:
        at = f" at {e['start']:%H:%M}" if e["start"] else ""
        said = (self._mine(e["id"]).get("details") or "").rstrip(" .!")
        return f"Time to leave for {e['title']}{at}." + (f" You said: {said}." if said else "")

    def _leave_sync(self, e: dict, t: dt.datetime) -> dt.datetime | None:
        """Keep the exam's leave-by alarm as it should be: set from the evening before (default, or your time),
        moved when the start time or what you said changes, gone when it's switched off or you said "no alarm"."""
        mine = self._mine(e["id"])
        want = None
        if self.setting("leave_alarm") and not mine.get("leave_off") and t >= self._eve_moment(e):
            want = self._leave_time(e, mine.get("said") or "")
        have = mine.get("leave")
        if want is None or want <= t:
            if have and want is None and dt.datetime.fromisoformat(have) > t:
                self._leave_cancel(e["id"])
            return None
        reason = self._leave_text(e)
        if have == want.isoformat() and mine.get("leave_reason") == reason:
            return want
        self._leave_cancel(e["id"], poke=False)
        key = f"{self.id}:leave:{e['id']}"
        if self._calls_ok():
            self.app.modules["calls"].schedule(want, reason, key=key, alarm=True, why="exam_season.leave")
            how = "call"
        else:
            self.app.scheduler.at(
                want, f"{self.id}.leave", {"id": e["id"]}, key=key, module=self.id, grace_s=1800, respect="none"
            )
            how = "message"
        self._edit(e["id"], leave=want.isoformat(), leave_reason=reason, leave_how=how, day=e["day"].isoformat())
        self.app.events.emit("exam_leave_set", how=how, said=bool(LEAVE.search(mine.get("said") or "")))
        return want

    def _leave_cancel(self, i: str, poke: bool = True) -> None:
        self.app.scheduler.cancel(f"calls:ring:{self.id}:leave:{i}")
        self.app.scheduler.cancel(f"{self.id}:leave:{i}")
        if self._mine(i).get("leave"):
            self._edit(i, leave=None, leave_reason=None)
        calls = self.app.modules.get("calls")
        if poke and calls is not None and self.app.is_on("calls"):
            calls.connector.poke()  # the call line's copy of the schedule no longer has it

    def _leave(self, p: dict) -> None:
        """The leave-by alarm without Phone calls: an urgent message (not when this computer slept through it)."""
        e = self._exam(str(p.get("id") or ""))
        if e is None or p.get("missed"):
            return
        self.app.notify(
            self._leave_text(e), kind="reminder", title="Time to leave", urgent=True, why="exam_season.leave"
        )
        self.app.events.emit("exam_leave_rang", how="message")

    def call_outcome(self, key: str, outcome: str) -> bool:
        """The leave-by call: "Later" rings again in 5 minutes (twice at most); missed: an urgent message too."""
        parts = key.split(":")
        if len(parts) < 3 or parts[1] != "leave":
            return False
        e = self._exam(parts[2])
        if e is None:
            return False
        self.app.events.emit("exam_leave_rang", how="call", outcome=outcome)
        if outcome == "later":
            n = int(self._mine(e["id"]).get("snoozed") or 0)
            if n < SNOOZES and self._calls_ok():
                at = now() + dt.timedelta(minutes=5)
                self.app.modules["calls"].schedule(
                    at, self._leave_text(e), key=key, alarm=True, why="exam_season.leave"
                )
                self._edit(e["id"], snoozed=n + 1)
                return True
        if outcome in ("missed", "later"):
            self.app.notify(
                self._leave_text(e), kind="reminder", title="Time to leave", urgent=True, why="exam_season.leave"
            )
        return outcome == "later"

    # ------------------------------------------------------------------------------------------ the debrief
    def _debrief_moment(self, e: dict) -> dt.datetime:
        if e["end"]:
            return e["end"] + dt.timedelta(minutes=DEBRIEF_AFTER_MIN)
        return dt.datetime.combine(e["day"], self._time("eve_at", "18:00"))  # the time isn't known: that evening

    def _debrief_due(self, e: dict, t: dt.datetime) -> bool:
        at = self._debrief_moment(e)
        until = at + dt.timedelta(hours=DEBRIEF_UNTIL_H)
        if self._mine(e["id"]).get("debrief_q"):
            return False
        if self.setting("debrief_at_desk") and e["end"]:  # 0.9.0: when you're back, at the latest DEBRIEF_WAIT_MIN
            last = e["end"] + dt.timedelta(minutes=DEBRIEF_WAIT_MIN)
            if e["end"] <= t < last:
                return self._back_since(e["end"])
            return last <= t < until
        return at <= t < until

    def _back_since(self, since: dt.datetime) -> bool:
        """(debrief_at_desk) You're at your desk now (mind/presence_forecast.py:at_desk: Face presence or the computer
        in use), or the phone arrived at "home" since then (mind/senses/phone.py; the label stays here)."""
        try:
            from kurooto.mind import presence_forecast as pf

            if pf.at_desk(self.app):
                return True
        except Exception:
            pass
        home = self._load().get("home_at")
        try:
            return bool(home) and dt.datetime.fromisoformat(home) >= since
        except ValueError:
            return False

    def place_event(self, label: str, event: str, t: dt.datetime | None = None) -> None:
        """(0.9.0) The phone arrived at or left a place you saved (mind/senses/phone.py): arriving "home" is kept as a
        time, for the debrief that waits for you (debrief_at_desk). Nothing else of it is kept."""
        if not self.setting("debrief_at_desk") or event != "arrive" or str(label).strip().lower() != "home":
            return
        with Lock(self.app.paths.state, "exam_season"):
            st = self._load()
            st["home_at"] = (t or now()).isoformat(timespec="seconds")
            jsave(self.file, st)

    # ------------------------------------------------------------------------------------- in the calls
    def call_line(self, when: str = "today", t: dt.datetime | None = None) -> str:
        """(0.9.0, in_calls) For the wake-up call ("today") and the night check-in ("tomorrow"): the exam that day,
        when it starts, when to leave, and on the night check-in a wake time to propose. "" when there's none."""
        if not self.setting("in_calls"):
            return ""
        t = t or now()
        day = t.date() + (DAY if when == "tomorrow" else dt.timedelta(0))
        todays = sorted((e for e in self.exams() if e["day"] == day), key=lambda e: e["start"] or t)
        if not todays:
            return ""
        e = todays[0]
        if when == "today" and e["start"] and e["start"] <= t:
            return ""
        at = f" at {e['start']:%H:%M}" if e["start"] else ""
        leave = self._leave_time(e, self._mine(e["id"]).get("details") or "") if e["start"] else None
        out = f"{'Tomorrow' if when == 'tomorrow' else 'Today'}: {e['title']}{at}"
        out += f", leave by {leave:%H:%M}." if leave else "."
        if when == "tomorrow" and leave:
            wake = leave - dt.timedelta(minutes=WAKE_BEFORE_LEAVE_MIN)
            out += (
                f" Propose waking at {wake:%H:%M} (an hour before leaving); set the alarm only if they agree to a time."
            )
        return out

    def _debrief_note(self, slug: str | None, day: dt.date):
        return layout.path(self.app, "course", subject=slug) if slug else daily.note_path(self.app, day)

    def _ask_debrief(self, e: dict) -> str:
        where = layout.shown(self.app, self._debrief_note(e["subject"], e["day"]))
        qid = self.app.ask.ask(
            f"How did {e['title']} go? Two minutes: what came up, what went well, what to fix before the next one. "
            f"It goes into {where}, as you say it.",
            hook="exam_season.debrief",
            hook_payload={"id": e["id"], "title": e["title"], "subject": e["subject"], "day": e["day"].isoformat()},
            expires=dt.timedelta(days=2),
            source=self.id,
            title="Exam debrief",
            why="exam_season.debrief",
            about=e["title"],
        )
        self._edit(e["id"], debrief_q=qid, day=e["day"].isoformat())
        self.app.events.emit("exam_debrief_asked")
        return qid

    def _debrief_answer(self, q: dict, answer: str) -> str:
        p = q.get("hook_payload") or {}
        if q.get("nothing"):
            self.app.events.emit("exam_debrief_saved", skipped=True)
            return "OK, no debrief this time."
        try:
            day = dt.date.fromisoformat(str(p.get("day") or ""))
        except ValueError:
            day = now().date()
        text = "" if answer == "(files)" else str(answer or "").strip()
        f = self.save_debrief(p.get("subject"), str(p.get("title") or "Exam"), day, text, q.get("files") or [])
        return f"Saved to {layout.shown(self.app, f)}."

    def save_debrief(self, slug: str | None, title: str, day: dt.date, text: str, files: list | None = None):
        """Add the debrief, as you said it, under "Exam debriefs" in the subject's course note (made if missing; what's
        there stays as it is), or to the exam day's daily note when it has no subject. Returns the note."""
        from kurooto.core.tools import add_to_section, write_note_file

        f = self._debrief_note(slug, day)
        links = [layout.file_link(self.app, self.app.workspace / x, f) for x in files or []]
        body = "\n\n".join(x for x in [text, "\n".join(links)] if x) or "(nothing written)"
        if not slug:
            daily.append(self.app, f"Exam debrief: {title}", body, day)
        else:
            dl = self._deadlines()
            name = (dl.subject_name(slug) if dl else "") or slug
            if f.exists():
                old = f.read_text(encoding="utf-8", errors="replace")
            else:
                old = layout.frontmatter(self.app, "course", f, title=name, subject=slug) + f"# {name}\n"
            write_note_file(f, add_to_section(old, "Exam debriefs", f"### {title} ({day.isoformat()})\n\n{body}\n"))
        self.app.events.emit("exam_debrief_saved", skipped=False, files=len(links), subject=bool(slug))
        return f

    # ------------------------------------------------------------------------------------- the quiz call
    def _quiz_call_due(self, e: dict, t: dt.datetime) -> bool:
        at = dt.datetime.combine(e["day"] - DAY, self._time("quiz_call_at", "19:00"))
        return at <= t < at + dt.timedelta(hours=QUIZ_CALL_UNTIL_H) and not self._mine(e["id"]).get("quiz_called")

    def _place_quiz_call(self, e: dict) -> str:
        """The quiz call you picked for this exam, the evening before (it waits out no-call times)."""
        quiz = self.app.modules.get("quiz")
        if quiz is None or not self.app.is_on("quiz") or not self._calls_ok():
            return ""
        self._edit(e["id"], quiz_called=now().isoformat(), day=e["day"].isoformat())
        self.app.events.emit("exam_quiz_call")
        return quiz.call_quiz(e["subject"], why="quiz.call")

    def pick(self, i: str, on: bool) -> str:
        """Pick (or unpick) the quiz call the evening before one exam."""
        e = self._exam(i)
        if e is None:
            return "That exam isn't on your list any more."
        self._edit(i, quiz_call=bool(on), day=e["day"].isoformat())
        self.app.events.emit("exam_quiz_call_pick", on=bool(on))
        if not on:
            return f"No quiz call before {e['title']}."
        need = [t for m, t in (("quiz", "Quiz"), ("calls", "Phone calls")) if not self.app.is_on(m)]
        at = f"{self._time('quiz_call_at', '19:00'):%H:%M}"
        if need:
            return (
                f"Picked, but it needs {' and '.join(need)} on; then I'll call you for a quiz at {at} the day before."
            )
        return f"I'll call you for a quiz at {at} the evening before {e['title']}."

    # -------------------------------------------------------------------------------- the nightly alarm check
    def _night_due(self, t: dt.datetime, exams: list[dict]) -> bool:
        """Every night of the period (the nights before its exam days), from night_at, once."""
        s = self.season(t, exams)
        if not s or not (s[0] - DAY <= t.date() <= s[1] - DAY):
            return False
        if t < dt.datetime.combine(t.date(), self._time("night_at", "21:30")):
            return False
        return self._load().get("night") != t.date().isoformat()

    def _night(self, again: bool = False) -> dict:
        """Kurooto keeps itself working's alarm-path check for tomorrow (core/health.py): the alarm's check with the
        Morning alarm on, the call line's when a leave-by alarm will ring through it. A safe fix is tried first and
        it looks again ten minutes later; what's still wrong is said the health pass's way (once per problem)."""
        from kurooto.core.health import AUTO, RECHECK_S

        t = now()
        if not again:
            with Lock(self.app.paths.state, "exam_season"):
                st = self._load()
                st["night"] = t.date().isoformat()
                jsave(self.file, st)
        h = self.app.health
        tomorrow = [e for e in self.exams() if e["day"] == t.date() + DAY]
        ids = ["alarm"] if self.app.is_on("alarm") else []
        rings = [self._mine(e["id"]).get("leave_how") for e in tomorrow]
        if "call" in rings and self.app.is_on("calls"):
            ids.append("calls")
        results = [r for cid in ids for r in h.evaluate(net=True, only=cid)]
        bad = [r for r in results if r.ok is False]
        self.app.events.emit("exam_alarm_checked", checks=len(results), problems=len(bad), again=again)
        out: dict = {}
        if not again and not any(r.id == "alarm" for r in bad) and self._no_alarm_before(tomorrow):
            e = min((e for e in tomorrow if e["start"]), key=lambda e: e["start"])
            self.app.notify(
                f"No alarm is set for tomorrow, and {e['title']} is at {e['start']:%H:%M}. /alarm 7:00 sets one (or "
                "set your phone's own).",
                kind="reminder",
                why="exam_season.alarm_check",
                about=e["title"],
            )
            out["no_alarm"] = True
        if bad and not again and self.app.settings.get("health.auto_fix"):
            go = [r for r in bad if r.fix.partition(":")[0] in AUTO]
            for r in go:
                h.fix(r.id, auto=True, result=r)
            if go:
                self.app.scheduler.at(
                    h.clock() + RECHECK_S, f"{self.id}.night_again", key=f"{self.id}:night_again", grace_s=3600
                )
                return {**out, "fixing": [r.id for r in go]}
        return {**out, **(h.decide(results) if results else {})}

    def _no_alarm_before(self, tomorrow: list[dict]) -> bool:
        """With the Morning alarm on: tomorrow has a morning exam and no alarm rings before it."""
        alarm = self.app.modules.get("alarm")
        starts = [e["start"] for e in tomorrow if e["start"] and e["start"].hour < 12]
        if alarm is None or not self.app.is_on("alarm") or not starts:
            return False
        nxt = alarm.next()
        return nxt is None or not (nxt.date() == min(starts).date() and nxt < min(starts))

    # ----------------------------------------------------------------------------------------- the card
    def _shown_season(self, t: dt.datetime, exams: list[dict]) -> tuple[tuple[dt.date, dt.date] | None, bool]:
        """The season on now (True), else the next one (False)."""
        s = self.season(t, exams)
        if s:
            return s, True
        return next((x for x in self.seasons(exams) if x[0] - DAY > t.date()), None), False

    def _line(self, e: dict) -> str:
        when = _day(e["day"]) + (f" {e['start']:%H:%M}" if e["start"] else " (time not known yet)")
        out = f"{e['title']}: {when}"
        if e["details"]:
            out += f". {e['details']}"
        if e["leave"]:
            out += f". Leave {dt.datetime.fromisoformat(e['leave']):%H:%M}"
        return out

    def _ahead(self) -> list[dict]:
        """The exams still to come in the season shown (on now, else the next one)."""
        t = now()
        exams = self.exams()
        s, _ = self._shown_season(t, exams)
        if s is None:
            return []
        return [e for e in exams if s[0] <= e["day"] <= s[1] and (not e["end"] or e["end"] > t)][:12]

    def card(self) -> dict:
        """The dashboard's card: the season, its exams, a switch for each part, and a quiz-call pick for each exam."""
        s, on_now = self._shown_season(now(), self.exams())
        ahead = self._ahead()
        if s is None:
            lines = [
                "No exam dates yet, so nothing happens. Add an exam period (Subjects: /term exams 2026-12-07 to "
                "2026-12-18) or an exam (/due 2026-12-08 09:00 Linear Algebra final exam)."
            ]
        else:
            span = _day(s[0]) if s[0] == s[1] else f"{_day(s[0])} to {_day(s[1])}"
            lines = [f"{'On now' if on_now else 'Next'}: {span}.", *[self._line(e) for e in ahead]]
            today = self.revision.today() if self.setting("revision") else []
            if today:
                lines.append("Revision today: " + "; ".join(f"{b['name']} {b['start']:%H:%M}" for b in today) + ".")
        can = self.app.is_on("quiz") and self.app.is_on("calls")
        toggles = [{"id": k, "label": label, "on": bool(self.setting(k))} for k, label in PIECES.items()]
        for e in ahead:
            toggles.append(
                {
                    "id": f"quiz:{e['id']}",
                    "label": f"Quiz call the evening before {e['title']}"
                    + ("" if can else " (needs Quiz and Phone calls)"),
                    "on": e["quiz_call"],
                    "disabled": not can and not e["quiz_call"],
                }
            )
        return {"lines": lines, "toggles": toggles}

    def card_action(self, act: str, value) -> str:
        """A switch on the card: a part (its setting), or "quiz:<exam id>" (the quiz-call pick)."""
        if act.startswith("quiz:"):
            return self.pick(act[5:], bool(value))
        if act not in PIECES:
            return "There's no such part."
        self.app.settings.set(f"exam_season.{act}", bool(value))
        self.app.events.emit("exam_season_part", part=act, on=bool(value))
        if act == "leave_alarm":
            for e in self.exams():
                self._leave_sync(e, now())
        return f"{PIECES[act]}: {'on' if value else 'off'}."

    def summary(self) -> tuple[str, list]:
        """/examseason: the card as a message, with a button per part and per exam's quiz call."""
        c = self.card()
        on = [PIECES[k] for k in PIECES if self.setting(k)]
        off = [PIECES[k] for k in PIECES if not self.setting(k)]
        head, rows = c["lines"][0], c["lines"][1:]
        text = "Exam season. " + head
        if rows:
            text += "\n" + "\n".join(f"- {r}" for r in rows)
        text += (
            "\nOn: " + ("; ".join(on) if on else "nothing") + "." + ("\nOff: " + "; ".join(off) + "." if off else "")
        )
        text += "\nQuiz calls the evening before stay off unless you pick them for an exam. Tap to switch."
        buttons = [[(f"{label}: {'on' if self.setting(k) else 'off'}", f"es:{k}:t")] for k, label in PIECES.items()]
        if self.app.is_on("quiz") and self.app.is_on("calls"):
            for e in self._ahead():
                state = "on" if e["quiz_call"] else "off"
                buttons.append([(f"Quiz call before {e['title'][:28]}: {state}", f"es:{e['id']}:q")])
        return text, buttons

    def commands(self):
        return [
            Command("examseason", "exam season: its dates, exams and parts (tap to switch)", self._cmd),
            Command(
                "revise", "the revision plan before your exams: /revise, /revise <subject>, /revise undo", self._revise
            ),
        ]

    def _revise(self, msg: Incoming, arg: str) -> str:
        a = arg.strip()
        if a.lower() == "undo":
            return self.revision.undo()
        if not a:
            return self.revision.overview()
        subj = self.app.modules.get("subjects")
        slug = subj.resolve(a) if subj is not None and self.app.is_on("subjects") else None
        return self.revision.course(slug) if slug else f"I don't know a subject called {a!r}."

    def _cmd(self, msg: Incoming, arg: str) -> str | None:
        text, buttons = self.summary()
        msg.reply(text, buttons=buttons or None)
        return None

    def callbacks(self):
        return {"es": self._button, "rv": self.revision.answer}

    def _button(self, ref: str, act: str) -> str:
        if act == "q":
            return self.pick(ref, not self._mine(ref).get("quiz_call"))
        if act == "t" and ref in PIECES:
            return self.card_action(ref, not self.setting(ref))
        return "That button is from an older card: /examseason."

    def intents(self):
        pat = re.compile(r"^(?:show |what'?s |how'?s )?(?:my |the )?exam season\??$", re.I)
        return [
            Intent(
                "exam_season",
                "exam season: what it does now",
                lambda t: {} if pat.match(t.strip().rstrip(".!")) else None,
                lambda m, s: self.summary()[0],
                questions=True,
                examples=("exam season", "what's my exam season?"),
            ),
            Intent(
                "revise_today",
                "what should I revise today",
                lambda t: {} if REVISE_Q.match(t.strip().rstrip(".!")) else None,
                lambda m, s: self._revise_today(),
                questions=True,
                examples=("what should I revise today?",),
            ),
        ]

    def _revise_today(self) -> str:
        if not self.setting("revision"):
            return "The revision plan is off (/examseason switches it on)."
        today = self.revision.today()
        if not today:
            return "No revision blocks today. /revise shows the plan."
        return "Revise today:\n" + "\n".join(f"- {self.revision.line(b)}" for b in today)

    def call_brief(self) -> dict:
        """On calls: exams today and tomorrow, with what you said about them."""
        t = now()
        soon = [e for e in self.exams() if t.date() <= e["day"] <= t.date() + DAY and (not e["end"] or e["end"] > t)]
        return {"exam_season": [self._line(e) for e in soon]} if soon else {}

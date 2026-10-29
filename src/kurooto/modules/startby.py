"""Start-by dates and crunch weeks: when to start each deadline, worked back from your free time.

Each deadline gets a size, guessed from what it is: a problem set or homework is an evening (3 h), a report, essay,
project or presentation 2-3 days (12 h), a quiz 2 h, an exam what you set for its subject (10 h until you do).
Correct it with one tap: the "Time to start" message and /startby offer the other sizes. A size you tap for an exam
counts for that subject's exams from then on, and the first exam of a subject asks you once.

Free time is each day's window (startby.window, 09:00-22:00) less your classes (Subjects: the timetable, holidays,
exam periods, the classes you skip), your commitments (Commitments), your calendar's timed events (Calendar) and the
blocks already in your Agent plan calendar, in gaps of at least half an hour, and only a share of that
(startby.share, 40%): the rest is meals, rest, going over lectures and everything else. Working back from the due
times, latest first, each deadline's hours go into the latest free time before it that nothing due later has taken;
the day its first hour lands on is its start-by date. Two big deadlines in one week push each other earlier.

From its start-by date until it's due, a deadline is in the morning plan (the morning page, the wake-up call, the
plan drafted before the alarm). On the day itself you get one message, only when that's two days or more before it's
due (otherwise the deadline's own day-before nudge says it). The Sunday summary flags crunch weeks, where the work due
adds up to more than the free time: "week of 9 Nov: about 14 h of work, about 9 h free".

The window learns your day (startby.learn_window, on): once a week it looks at when your messages came in over the
last three weeks (days with 3 or more), and when the middle of your first ones and of your last ones is an hour or more
from the window's ends, the window moves there (to the half hour), with one line and Undo. A window you set yourself
is never changed.

All of it is an estimate, local arithmetic only: no AI, and nothing leaves this computer.

    /startby                         what to start when, with sizes to tap
    /startby exam la 2-3 days        how long a subject's exams take to prepare for
"""

from __future__ import annotations

import datetime as dt
import re
import time

from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.lock import Lock
from kurooto.core.notinterested import matcher
from kurooto.core.state import jload, jsave
from kurooto.modules.base import Command, Incoming, Intent, Module
from kurooto.modules.calls.tools import Tool, arg
from kurooto.modules.deadlines import similar, when_text

register_defaults(
    "startby",
    {
        # hours of work each kind of deadline takes: a guess, corrected per deadline with a tap
        "sizes": {"problem_set": 3, "report": 12, "quiz": 2, "exam": 10, "other": 2},
        "exam_by_subject": {},  # {"linear-algebra": 25}: hours to prepare for that subject's exams (else sizes.exam)
        "window": "09:00-22:00",  # the part of each day free time is counted in
        "learn_window": True,  # once a week, move the window to when you're actually up (unless you set it)
        "share": 40,  # % of the free time in that window that goes to deadlines
        "min_gap_min": 30,  # shorter gaps between classes and events don't count
        "horizon_days": 35,  # deadlines due this far ahead get a start-by date
        "when": "daily 08:00",  # the day's "Time to start" messages (they wait out quiet hours)
        "tell": True,  # a message on a start-by day (only two days or more before the due date)
        "ask_exams": True,  # ask once per subject how long its exams take to prepare for
        "crunch_weeks": 4,  # the Sunday summary looks this many weeks ahead (0: no crunch weeks)
        "negotiate": True,  # a reminder that would repeat for a slipping deadline: a reshaped plan instead, once a day
        # (0.9.0) "Time to start" says the study the tracker counted for it (sessions tied to it, else its subject's
        # week when it's that subject's only deadline) and offers "Count it", which sets the size to what's left. The
        # size changes only on that tap
        "count_study": True,
        # (0.9.0) once a week, when your pace (Brain's plans) says a different share of free time goes to deadlines,
        # an offer to use it (Yes, then Undo); never a share you set yourself
        "learn_share": False,
        # (0.9.0) "Time to start" and the Sunday summary say Brain's chance of missing a deadline (Brain's plans)
        "miss_risk": True,
        # (0.9.1) a deadline's hours, and the study push's time, go first into the hours you usually work on its
        # subject (an add-on's reading, e.g. "works on Topology at night"); the free time itself is never changed
        "learn_from_model": False,
        # (0.9.1) "Time to start" says how long the subject's last deadlines of the kind really took (the study
        # tracker's time between their start-by and done), with a button to use it; the size changes only on a tap
        "learned_line": True,
        # (0.9.1) a size it guessed is replaced by that learned time by itself (never a size you set)
        "learned_estimates": False,
    },
)
HABIT_W = 1.0  # (learn_from_model) how much an hour you usually work on it counts, beside the presence forecast's 0-1
LEARN_MIN_DONE, LEARN_LOOK_DAYS, LEARN_OFF = 2, 120, 0.3  # (learned_line) deadlines needed, look back, how far off
DAY_H = 5  # "a day" of work, for sizes given in days
WEEK_H = 25
TASK_SIZES = [(1, "An hour"), (3, "An evening"), (5, "A day"), (12, "2-3 days"), (25, "A week")]
EXAM_SIZES = [(3, "An evening"), (5, "A day"), (12, "2-3 days"), (25, "A week"), (50, "Two weeks")]
NAMES = {h: label for h, label in TASK_SIZES + EXAM_SIZES}
LEARN_DAYS, LEARN_ACTIVE_DAYS, LEARN_MSGS, LEARN_GAP_MIN = 21, 7, 3, 60  # look back, days needed, a day's, off by
SHARE_GAP, SHARE_LO, SHARE_HI = 10, 10, 90  # (learn_share) % off before offering; the range offered
COUNTED_MIN_H = 0.5  # (count_study) less study than this isn't said
RISK_SAY = 0.2  # (miss_risk) a chance of missing at least this is said
DAY_TURNS = 4  # your day, for this: from 04:00 (a message at 01:00 ends the day before)
WORDS = {"an hour": 1, "one hour": 1, "an evening": 3, "one evening": 3, "a day": DAY_H, "one day": DAY_H,
         "two days": 2 * DAY_H, "three days": 3 * DAY_H, "a couple of days": 12, "a few days": 12, "a week": WEEK_H,
         "one week": WEEK_H, "two weeks": 2 * WEEK_H}  # fmt: skip
UNITS = {"h": 1, "e": 3, "d": DAY_H, "w": WEEK_H}
SIZE = re.compile(
    r"(?:about |around |roughly |~)?(\d+(?:\.\d+)?)(?:\s*-\s*\d+(?:\.\d+)?)?\s*"
    r"(h|hrs?|hours?|e|evenings?|d|days?|w|wks?|weeks?)?(?: of work)?"
)
KINDS = {
    "problem_set": "a problem set",
    "report": "a report",
    "quiz": "a quiz",
    "exam": "an exam",
    "other": "a deadline like this",
}
EXAM = re.compile(r"\b(exams?|midterms?|mid-terms?|finals?|midsem|mid-sem|endsem|end-sem)\b", re.I)
REPORT = re.compile(
    r"\b(report|essay|term paper|write-?up|thesis|dissertation|proposal|project|presentation|poster)\b", re.I
)
PSET = re.compile(
    r"\b(problem sets?|psets?|homework|hw|assignments?|worksheets?|exercises?|sheets?|tutorials?|labs?)\b", re.I
)
WHEN_START = re.compile(
    r"^\s*when (?:should|do|must|shall|can) i (?:start|begin)(?: (?:on|with|working on))?(?P<what> .+?)?\s*\??\s*$",
    re.I,
)
CRUNCH = re.compile(r"\bcrunch weeks?\b|\bhow busy (?:are|is) (?:the |my )?(?:next|coming)\b|\bbusy weeks\b", re.I)


# ------------------------------------------------------------------------------------------- sizes
def kind_of(title: str, kind: str = "task") -> str:
    """What sort of work a deadline is: exam, quiz, report, problem_set or other."""
    if kind == "exam":
        return "exam" if EXAM.search(title) else "quiz"
    if REPORT.search(title):
        return "report"
    if PSET.search(title):
        return "problem_set"
    return "other"


def hours(h: float) -> str:
    return f"{h:.0f}" if h >= 2 or h == int(h) else f"{h:.1f}"


def size_text(h: float) -> str:
    """12 -> "about 12 h (2-3 days)"; 7 -> "about 7 h"."""
    name = NAMES.get(h)
    return f"about {hours(h)} h ({name.lower()})" if name else f"about {hours(h)} h"


def parse_size(text: str) -> float | None:
    """ "2-3 days", "an evening", "10h", "3 days", "a week" -> hours of work (None if it isn't a size)."""
    t = re.sub(r"\s+", " ", str(text or "").strip().lower().rstrip(".!"))
    for h, label in TASK_SIZES + EXAM_SIZES:
        if t == label.lower():
            return float(h)
    if t in WORDS:
        return float(WORDS[t])
    m = SIZE.fullmatch(t)
    if not m:
        return None
    n = float(m[1])
    return n * UNITS[(m[2] or "h")[0]] if n > 0 else None


def ladder(kind: str) -> list[tuple[int, str]]:
    return EXAM_SIZES if kind == "exam" else TASK_SIZES


# ----------------------------------------------------------------------------------- the arithmetic
def parse_window(spec: str) -> tuple[dt.time, dt.time]:
    """ "09:00-22:00" -> (09:00, 22:00); anything it can't read is 09:00-22:00. An end before the start runs past
    midnight ("18:00-01:00")."""
    m = re.fullmatch(r"\s*(\d{1,2})[:.](\d{2})\s*(?:-|–|to)\s*(\d{1,2})[:.](\d{2})\s*", str(spec or ""))
    try:
        return dt.time(int(m[1]) % 24, int(m[2])), dt.time(int(m[3]) % 24, int(m[4]))
    except (TypeError, ValueError):
        return dt.time(9), dt.time(22)


def _register_undo() -> None:
    """Brain's Undo for a plan it reshaped by itself (mind/act.py, mind.act.more)."""
    try:
        from kurooto.mind import act
    except ImportError:
        return
    act.register("deadline.reshape", undoer=lambda app, p: app.modules["startby"].reshape_undo(p))


def free_slots(
    day: dt.date,
    window: tuple[dt.time, dt.time],
    busy: list[tuple[dt.datetime, dt.datetime]],
    after: dt.datetime | None = None,
    min_gap: int = 30,
) -> list[tuple[dt.datetime, dt.datetime]]:
    """One day's free time: its window less the busy times, from `after` on, in gaps of at least min_gap minutes."""
    start, end = dt.datetime.combine(day, window[0]), dt.datetime.combine(day, window[1])
    if end <= start:
        end += dt.timedelta(days=1)
    cur = max(start, after) if after else start
    out = []
    for s, e in sorted(busy):
        if e <= cur:
            continue
        if s >= end:
            break
        if s > cur:
            out.append((cur, s))
        cur = max(cur, e)
    if cur < end:
        out.append((cur, end))
    gap = dt.timedelta(minutes=max(0, min_gap))
    return [(s, e) for s, e in out if e - s >= gap and e > s]


def by_hour(slots: list[tuple[dt.datetime, dt.datetime]]) -> list[tuple[dt.datetime, dt.datetime]]:
    """The same free time cut at each whole hour (for a ranking by hour; nothing is added or lost)."""
    out = []
    for s, e in sorted(slots):
        cur = s
        while cur < e:
            nxt = min(e, cur.replace(minute=0, second=0, microsecond=0) + dt.timedelta(hours=1))
            out.append((cur, nxt))
            cur = nxt
    return out


def allocate(
    items: list[dict],
    slots: list[tuple[dt.datetime, dt.datetime]],
    share: float,
    pieces: dict | None = None,
    rank=None,
    habits: dict | None = None,
) -> dict[str, tuple[dt.datetime | None, float]]:
    """As late as possible: latest due first, each item's hours (items: {"id", "due", "hours"}) go into the latest
    free time before its due time that a later one hasn't taken; `share` (0-1) of each free hour counts. Returns
    {id: (where its work starts, or None if no time at all; the hours that didn't fit)}. `pieces`, when given, gets
    where each item's hours went: {id: [(from, to, hours of work), ...]}. `rank` (0.9.0, a time -> a score, the
    presence forecast's): the free hours with the higher score are taken first, later ones first among equals.
    `habits` (0.9.1, startby.learn_from_model): {id: {hour of the day: 0-1}}, the hours you usually work on that one,
    added (HABIT_W) to its own ranking."""
    share = min(1.0, max(0.01, share))
    habits = {k: v for k, v in (habits or {}).items() if v}
    if rank is not None or habits:
        return _allocate_ranked(items, by_hour(slots), share, pieces, rank, habits)
    free = [[s, e] for s, e in sorted(slots)]
    out: dict[str, tuple[dt.datetime | None, float]] = {}
    for it in sorted(items, key=lambda x: x["due"], reverse=True):
        need, first = float(it["hours"]), None
        for k in range(len(free) - 1, -1, -1):
            if need <= 1e-6:
                break
            s, e = free[k]
            top = min(e, it["due"])
            if top <= s:
                continue
            take = min(need, (top - s).total_seconds() / 3600 * share)
            lo = top - dt.timedelta(hours=take / share)
            free[k] = [s, lo]
            if top < e:
                free.insert(k + 1, [top, e])
            need -= take
            if pieces is not None and take > 0:
                pieces.setdefault(it["id"], []).append((lo, top, take))
            first = lo
        out[it["id"]] = (first, max(0.0, need))
    return out


def _allocate_ranked(items, slots, share, pieces, rank, habits=None) -> dict[str, tuple[dt.datetime | None, float]]:
    """allocate() with the free hours taken best-ranked first (each item still only before its due time)."""
    free = [[s, e] for s, e in slots]
    out: dict[str, tuple[dt.datetime | None, float]] = {}
    for it in sorted(items, key=lambda x: x["due"], reverse=True):
        need, first, extra = float(it["hours"]), None, []
        mine = (habits or {}).get(it["id"]) or {}

        def score(t: dt.datetime, mine=mine) -> float:
            return (rank(t) if rank is not None else 0.0) + HABIT_W * float(mine.get(t.hour, 0.0))

        for k in sorted(range(len(free)), key=lambda k: (-score(free[k][0]), -free[k][0].timestamp())):
            if need <= 1e-6:
                break
            s, e = free[k]
            top = min(e, it["due"])
            if top <= s:
                continue
            take = min(need, (top - s).total_seconds() / 3600 * share)
            lo = top - dt.timedelta(hours=take / share)
            free[k] = [s, lo]
            if top < e:
                extra.append([top, e])
            need -= take
            if pieces is not None and take > 0:
                pieces.setdefault(it["id"], []).append((lo, top, take))
            first = lo if first is None else min(first, lo)
        free = sorted([f for f in free + extra if f[1] > f[0]])
        out[it["id"]] = (first, max(0.0, need))
    return out


def overlap_h(slots: list[tuple[dt.datetime, dt.datetime]], a: dt.datetime, b: dt.datetime) -> float:
    return sum(max(0.0, (min(e, b) - max(s, a)).total_seconds()) for s, e in slots) / 3600


class StartBy(Module):
    id = "startby"
    title = "Start-by dates"
    description = (
        "When to start each deadline, worked back from a guess of its size (one tap corrects it) and your free time "
        "between classes and events; crunch weeks in the Sunday summary. An estimate."
    )
    requires = ("deadlines",)
    privacy = "Stays on this computer: arithmetic on your deadlines, timetable and calendar. No AI."

    @property
    def file(self):
        return self.app.paths.state / "startby.json"

    def _state(self) -> dict:
        return jload(self.file, {}) or {}

    def start(self):
        spec = self.setting("when") or "daily 08:00"
        self.every("morning", spec, self._morning, {"what": "start-by dates"}, respect="quiet")
        self.app.ask.hooks["startby.exam_size"] = lambda q, a: self._exam_answer(q.get("hook_payload") or {}, a)
        self.every("learn_window", "weekly sun 12:00", lambda p: (self.learn_window(), self.learn_share()))
        self.action("moved", self._moved)  # (negotiate) the part you moved to tomorrow, at its time
        _register_undo()  # 0.8.16: Undo under a plan Brain reshaped by itself works after a restart too

    # ------------------------------------------------------------------------------ the learned window
    def learn_window(self) -> str:
        """Move startby.window to when your messages come in (not one you set yourself). Returns the line told."""
        if not self.setting("learn_window"):
            return ""
        st = self._state().get("window_learned") or {}
        mine = (self.app.settings.user().get("startby") or {}).get("window")
        if mine is not None and mine != st.get("to"):
            return ""  # yours
        if st.get("at") and now() - dt.datetime.fromisoformat(st["at"]) < dt.timedelta(
            days=30 if st.get("undone") else 7
        ):
            return ""
        since = now() - dt.timedelta(days=LEARN_DAYS)
        days: dict[dt.date, list[int]] = {}
        for e in self.app.events.tail(50000, kinds={"message_in"}):
            try:
                t = dt.datetime.fromisoformat(e["ts"]).replace(tzinfo=None)
            except (KeyError, ValueError):
                continue
            if t < since:
                continue
            shifted = t - dt.timedelta(hours=DAY_TURNS)
            days.setdefault(shifted.date(), []).append(shifted.hour * 60 + shifted.minute + DAY_TURNS * 60)
        active = [sorted(v) for v in days.values() if len(v) >= LEARN_MSGS]
        if len(active) >= LEARN_ACTIVE_DAYS:
            first = sorted(v[0] for v in active)[len(active) // 2]
            last = sorted(v[-1] for v in active)[len(active) // 2]
            said = f"that's when your messages came in on {len(active)} days of the last three weeks"
        else:  # 0.9.0 (mind.presence_forecast.plan): too few messages; your usual quiet hours (core/rhythm.py)
            usual = self._usual_hours()
            if usual is None:
                return ""
            first, last, said = usual
        first = max(5 * 60, min(13 * 60, first // 30 * 30))  # 05:00 to 13:00
        last = max(17 * 60, min(27 * 60, -(-last // 30) * 30))  # 17:00 to 03:00 the next morning
        cur = self.setting("window") or "09:00-22:00"
        a, b = parse_window(cur)
        a_m, b_m = a.hour * 60 + a.minute, b.hour * 60 + b.minute + (24 * 60 if b <= a else 0)
        if abs(first - a_m) < LEARN_GAP_MIN and abs(last - b_m) < LEARN_GAP_MIN:
            return ""
        hm = lambda m: f"{m // 60 % 24:02d}:{m % 60:02d}"  # noqa: E731
        new = f"{hm(first)}-{hm(last)}"
        self.app.settings.set("startby.window", new)
        self._put_state(window_learned={"at": now().isoformat(timespec="seconds"), "from": cur, "to": new})
        line = (
            f"Start-by dates now count your free time from {hm(first)} to {hm(last)}, not {cur.replace('-', ' to ')}: "
            f"{said}."
        )
        self.app.events.emit("startby_window_learned", from_window=cur, to_window=new, days=len(active))
        self.app.notify(line, kind="info", why="startby.window", buttons=[[("Undo", "sby:window:undo")]])
        return line

    def _usual_hours(self) -> tuple[int, int, str] | None:
        """(0.9.0) The window from your usual quiet hours (core/rhythm.py, learned from when you're around) as minutes
        from midnight (the end may run past it), when mind.presence_forecast.plan is on; else None."""
        if not self.prefer_free():
            return None
        rh = getattr(self.app, "rhythm", None)
        u = rh.usual_hours() if rh is not None else None
        if not u:
            return None
        try:
            bed, wake = parse_window(f"{u['from']}-{u['to']}")
        except (KeyError, TypeError):
            return None
        first, last = wake.hour * 60 + wake.minute, bed.hour * 60 + bed.minute
        if last <= first:
            last += 24 * 60
        return first, last, f"you're usually around from {u['to']} to {u['from']}"

    def _put_state(self, **kw) -> None:
        with Lock(self.app.paths.state, "startby", timeout=5):
            st = self._state()
            st.update(kw)
            jsave(self.file, st)

    def _window_undo(self) -> str:
        st = self._state().get("window_learned") or {}
        if not st or st.get("undone"):
            return "Nothing to undo."
        if self.setting("window") == st["to"]:
            self.app.settings.set("startby.window", st["from"])
        self._put_state(window_learned={**st, "undone": True, "at": now().isoformat(timespec="seconds")})
        return f"Back to {st['from']}; I'll leave the window alone."

    def health_check(self):
        from kurooto.core.health import Check

        return Check(
            "startby",
            "Start-by dates",
            module=self.id,
            every_h=30,
            events=("startby_planned",),
            help="/startby works them out now.",
        )

    # ------------------------------------------------------------------------------------------ inputs
    def _dl(self):
        return self.app.modules["deadlines"]

    def _on(self, mid: str):
        m = self.app.modules.get(mid)
        return m if m is not None and self.app.is_on(mid) else None

    def _share(self) -> float:
        try:
            return min(100.0, max(1.0, float(self.setting("share") or 40))) / 100
        except (TypeError, ValueError):
            return 0.4

    def size_of(self, i: str, it: dict, st: dict | None = None) -> tuple[float, str, bool]:
        """(hours of work left, what kind it is, whether that's a guess). Parts done ("ps3 4/7") take their share."""
        h, kind, guessed = self._whole_size(i, it, st)
        total, done = it.get("parts") or 0, it.get("parts_done") or 0
        if total and 0 < done <= total:
            h = max(0.25, h * (total - done) / total) if done < total else 0.25
        return h, kind, guessed

    def _whole_size(self, i: str, it: dict, st: dict | None = None) -> tuple[float, str, bool]:
        kind = kind_of(it["title"], it.get("kind", "task"))
        mine = ((st if st is not None else self._state()).get("sizes") or {}).get(i)
        if mine:
            return float(mine), kind, False
        if kind == "exam" and it.get("subject"):
            by = (self.setting("exam_by_subject") or {}).get(it["subject"])
            if by:
                return float(by), kind, False
        if self.setting("learned_estimates") and it.get("subject"):  # (0.9.1) what this kind really took
            got = self.learned_h(it["subject"], kind)
            if got:
                return got[0], kind, True
        sizes = self.setting("sizes") or {}
        try:
            h = float(sizes.get(kind, sizes.get("other", 2)))
        except (TypeError, ValueError):
            h = 2.0
        return max(0.25, h), kind, True

    # ------------------------------------------------------------- (0.9.1) what a kind of deadline really took
    def took_h(self, i: str, it: dict) -> float | None:
        """Hours the study tracker counted for a done deadline: sessions tied to it (Study push's Start, the plan's
        focus); else its subject's whole time (timed, typed and seen on screen: modules/study.py) from its start-by
        date (else a week before) to the day it was done, when no other deadline of the subject was due then.
        None when it can't tell."""
        study = self._on("study")
        try:
            done = dt.datetime.fromisoformat(str(it.get("done_at") or "")).replace(tzinfo=None)
        except ValueError:
            return None
        if study is None or not it.get("subject"):
            return None
        told = (self._state().get("told") or {}).get(i)
        start = dt.datetime.fromisoformat(told) if told else done - dt.timedelta(days=7)
        exact = 0.0
        for e in self.app.events.tail(5000, kinds={"study_session_end"}):
            if e.get("deadline") == i:
                try:
                    exact += float(e.get("minutes") or 0) / 60
                except (TypeError, ValueError):
                    continue
        if exact > 0:
            return exact
        for j, other in self._dl().items().items():
            if j == i or other.get("subject") != it["subject"]:
                continue
            due = str(other.get("due") or "")
            if start.isoformat() <= due <= (done + dt.timedelta(days=1)).isoformat():
                return None  # two in the subject at once: which got the time can't be told
        days = (done.date() - start.date()).days + 1
        try:
            secs = float(study.totals(max(1, days), last=done.date()).get(it["subject"], 0))
        except Exception:
            return None
        return secs / 3600 if secs > 0 else None

    def learned_h(self, subject: str, kind: str) -> tuple[float, int] | None:
        """(startby.learned_line / learned_estimates) The middle of what the subject's last done deadlines of this
        kind took (took_h), with how many: at least LEARN_MIN_DONE done in the last LEARN_LOOK_DAYS. Kept a few
        minutes (one read for a whole plan). None when there aren't enough."""
        key = (subject, kind)
        memo = getattr(self, "_learned_memo", None) or {}
        if key in memo and time.monotonic() - memo[key][0] < 300:
            return memo[key][1]
        since = (now() - dt.timedelta(days=LEARN_LOOK_DAYS)).isoformat()
        got = []
        for i, it in self._dl().items().items():
            if it.get("status") != "done" or it.get("subject") != subject or str(it.get("done_at") or "") < since:
                continue
            if kind_of(it.get("title") or "", it.get("kind", "task")) != kind:
                continue
            h = self.took_h(i, it)
            if h and h >= 0.25:
                got.append(h)
        got.sort()
        out = None
        if len(got) >= LEARN_MIN_DONE:
            mid = got[len(got) // 2] if len(got) % 2 else (got[len(got) // 2 - 1] + got[len(got) // 2]) / 2
            out = (max(0.5, round(mid * 2) / 2), len(got))
        memo[key] = (time.monotonic(), out)
        self._learned_memo = memo
        return out

    def learned_note(self, r: dict) -> tuple[str, tuple[str, str]] | None:
        """(startby.learned_line) A line and a button when the subject's past deadlines of this kind took a different
        time from the size used now (LEARN_OFF or more apart), for a size it guessed; else None."""
        if not self.setting("learned_line") or not r.get("guessed") or not r.get("subject"):
            return None
        got = self.learned_h(r["subject"], r["kind"])
        if not got or abs(got[0] - r["hours"]) < max(0.5, LEARN_OFF * r["hours"]):
            return None
        h, n = got
        what = {"exam": "exams", "quiz": "quizzes", "report": "reports", "problem_set": "problem sets"}.get(
            r["kind"], "deadlines like it"
        )
        name = self._dl().subject_name(r["subject"]) if hasattr(self._dl(), "subject_name") else r["subject"]
        return (
            f"Your last {n} {what} in {name} took about {h:g} h of study each.",
            (f"Use {h:g} h", f"sby:{r['id']}:{h:g}"),
        )

    def _events(self, t0: dt.datetime, until: dt.datetime) -> list[tuple[dt.datetime, dt.datetime]]:
        """Your calendar's timed events (all-day ones don't take time), as local times."""
        cal = self._on("calendar")
        if cal is None:
            return []
        out = []
        for e in cal.events(t0.astimezone(), until.astimezone()):
            if e.get("all_day"):
                continue
            s, f = (x.astimezone().replace(tzinfo=None) for x in (e["start_dt"], e["end_dt"]))
            if f > s:
                out.append((s, f))
        return out

    def _plan_blocks(self, t0: dt.datetime, until: dt.datetime) -> list[tuple[dt.datetime, dt.datetime]]:
        """(0.9.0) The blocks already in your Agent plan calendar: time you planned is busy (modules/google_plan.py's
        ledger; none when it's off, signed out or offline)."""
        plan = self._on("agent_plan")
        if plan is None or not hasattr(plan, "busy"):
            return []
        try:
            return plan.busy(t0, until)
        except Exception:
            return []

    def slots(self, t0: dt.datetime, until: dt.datetime) -> list[tuple[dt.datetime, dt.datetime]]:
        """The free time from t0 until `until`: each day's window less classes, commitments, calendar events and the
        blocks already in your Agent plan calendar."""
        window = parse_window(self.setting("window"))
        try:
            gap = int(self.setting("min_gap_min") or 0)
        except (TypeError, ValueError):
            gap = 30
        events = self._events(t0 - dt.timedelta(days=1), until) + self._plan_blocks(t0 - dt.timedelta(days=1), until)
        subj = self._on("subjects")
        com = self._on("commitments")  # 0.9.0: commitments are busy here too, not only in Revision's plan
        out = []
        day = t0.date() - dt.timedelta(days=1)  # a window past midnight starts the day before
        while day <= until.date():
            busy = list(events)
            if subj is not None:
                busy += [(c["start_dt"], c["end_dt"]) for c in subj.classes_on(day)]
            if com is not None:
                for d in (day - dt.timedelta(days=1), day):  # last night's shift may run into this window
                    busy += [(c["start_dt"], c["end_dt"]) for c in com.on(d)]
            out += [(s, min(e, until)) for s, e in free_slots(day, window, busy, t0, gap) if s < until]
            day += dt.timedelta(days=1)
        return out

    def prefer_free(self) -> bool:
        """(0.9.0, mind.presence_forecast.plan) Brain's presence forecast orders the free hours: the deadline work and
        the study push's time go first into hours you're usually at your desk and free. Hours are never taken away."""
        try:
            from kurooto.mind import presence_forecast as pf
        except ImportError:
            return False
        return pf.on(self.app) and bool(self.app.settings.get("mind.presence_forecast.plan"))

    def rank(self):
        """The presence forecast's chance you're free at a time (mind/presence_forecast.py:p_free, local arithmetic),
        when mind.presence_forecast.plan is on; else None."""
        if not self.prefer_free():
            return None
        from kurooto.mind import presence_forecast as pf

        st, seen = pf._load(self.app), {}  # noqa: SLF001 (one read for the whole plan)

        def p(t: dt.datetime) -> float:
            k = t.replace(minute=0, second=0, microsecond=0)
            if k not in seen:
                seen[k] = pf.p_free(self.app, k, st)
            return seen[k]

        return p

    def habit_hours(self, subject: str, title: str = "") -> dict[int, float]:
        """(0.9.1, startby.learn_from_model, off) The hours of the day you usually work on this subject, {hour: 0-1},
        from any feature that knows (an add-on's `work_hours(subject, title)`: Brain's model rows like "works on
        Topology at night" turned into hours by the add-on that wrote them). The strongest reading per hour wins;
        a feature that fails or answers nonsense adds nothing. {} with the switch off."""
        if not self.setting("learn_from_model"):
            return {}
        out: dict[int, float] = {}
        for m in self.app.enabled():
            fn = getattr(m, "work_hours", None)
            if not callable(fn) or m.id == self.id:
                continue
            try:
                got = fn(str(subject or ""), str(title or ""))
            except Exception as e:
                self.app.events.emit("startby_habit_failed", module=m.id, error=type(e).__name__)
                continue
            for h, w in (got or {}).items() if isinstance(got, dict) else ():
                if isinstance(h, int) and not isinstance(h, bool) and 0 <= h <= 23 and isinstance(w, (int, float)):
                    if not isinstance(w, bool) and w == w:
                        out[h] = max(out.get(h, 0.0), min(1.0, max(0.0, float(w))))
        return {h: w for h, w in out.items() if w > 0}

    def _rows(self, t0: dt.datetime, days: float, st: dict) -> list[dict]:
        """Open deadlines due between t0 and `days` ahead, with their sizes."""
        skip = matcher(self.app)
        end = t0 + dt.timedelta(days=days)
        rows = []
        for i, it in self._dl().items().items():
            try:
                due = dt.datetime.fromisoformat(it["due"])
            except (KeyError, ValueError):
                continue
            if it.get("status") != "open" or not t0 < due <= end or skip(it["title"]):
                continue
            h, kind, guessed = self.size_of(i, it, st)
            row = {"id": i, "title": it["title"], "subject": it.get("subject"), "due": due, "kind": kind}
            row["parts"] = f" ({it.get('parts_done', 0)}/{it['parts']})" if it.get("parts") else ""
            rows.append({**row, "hours": h, "guessed": guessed})
        return rows

    # -------------------------------------------------------------------------------------- the plan
    def compute(
        self, t0: dt.datetime | None = None, days: float | None = None, pieces: dict | None = None
    ) -> tuple[list[dict], list]:
        """(every deadline in the next `days` with its size and start-by date, soonest due first; the free time).
        `pieces` gets where each one's hours went (allocate)."""
        t0 = t0 or now()
        days = days or max(1, int(self.setting("horizon_days") or 35))
        st = self._state()
        rows = self._rows(t0, days, st)
        if not rows:
            return [], []
        slots = self.slots(t0, max(r["due"] for r in rows))
        told = st.get("told") or {}
        work = []
        for r in rows:
            since = told.get(r["id"])
            r["since"] = dt.date.fromisoformat(since) if since else None
            left = r["hours"]
            if r["since"] and r["since"] < t0.date():  # under way: what's left if it went to plan since then
                began = dt.datetime.combine(r["since"], dt.time(0))
                left *= max(0.0, min(1.0, (r["due"] - t0) / (r["due"] - began))) if r["due"] > began else 0
            work.append({"id": r["id"], "due": r["due"], "hours": left})
        habits = {r["id"]: self.habit_hours(r.get("subject") or "", r["title"]) for r in rows}
        fits = allocate(work, slots, self._share(), pieces, rank=self.rank(), habits=habits)
        for r, w in zip(rows, work, strict=True):
            first, short = fits[r["id"]]
            r["start"] = first.date() if first else t0.date()
            r["short"] = round(short, 1) if not r["since"] else 0.0
            r["free"] = round(w["hours"] - short, 1)
        return sorted(rows, key=lambda r: r["due"]), slots

    def plan(self, t0: dt.datetime | None = None) -> list[dict]:
        return self.compute(t0)[0]

    def to_start(self, t0: dt.datetime | None = None) -> list[dict]:
        """Deadlines whose start-by date has come, soonest due first (the morning plan's "time to start")."""
        t0 = t0 or now()
        return [r for r in self.plan(t0) if r["start"] <= t0.date()]

    def crunch(self, t0: dt.datetime | None = None, weeks: int | None = None) -> list[dict]:
        """Weeks ahead (from the one tomorrow is in) where the work due adds up to more than the free time:
        [{"week": its Monday, "work": hours, "free": hours}]."""
        t0 = t0 or now()
        try:
            n = int(self.setting("crunch_weeks") if weeks is None else weeks)
        except (TypeError, ValueError):
            n = 4
        if n <= 0:
            return []
        tomorrow = t0.date() + dt.timedelta(days=1)
        monday = dt.datetime.combine(tomorrow - dt.timedelta(days=tomorrow.weekday()), dt.time(0))
        end = monday + dt.timedelta(weeks=n)
        rows = self._rows(t0, (end - t0).total_seconds() / 86400, self._state())
        slots = self.slots(t0, end) if rows else []
        out = []
        for k in range(n):
            a = monday + dt.timedelta(weeks=k)
            b = a + dt.timedelta(weeks=1)
            work = sum(r["hours"] for r in rows if a <= r["due"] < b)
            free = overlap_h(slots, a, b) * self._share()
            if work >= 1 and work > free:
                out.append({"week": a.date(), "work": round(work, 1), "free": round(free, 1)})
        return out

    # ------------------------------------------------------------------------------------- in words
    def when_words(self, r: dict, today: dt.date) -> str:
        if r["start"] > today:
            return f"start by {r['start']:%a %d %b}"
        if r["since"] and r["since"] < today:
            return f"start-by was {r['since']:%a %d %b}"
        return "start now, it may not fit" if r["short"] else "start today"

    def line(self, r: dict, today: dt.date) -> str:
        """ "Lab report (due Fri 06 Nov): start working on it today, about 12 h (2-3 days) of work". The date comes
        first and "working on it" is said, so a call doesn't turn "start today" into "the quiz is today"."""
        due = when_text(r["due"].isoformat())
        on = "on" if r.get("kind") == "exam" else "due"
        work = self.when_words(r, today).replace("start ", "start working on it ", 1)
        return f"{r['title']}{r.get('parts', '')} ({on} {due}): {work}, {size_text(r['hours'])} of work"

    def morning_rows(self) -> list[dict]:
        """For the morning page: what to start, {"title", "when"}, then the day's revision blocks."""
        today = now().date()
        return [
            {
                "title": r["title"] + r.get("parts", ""),
                "when": f"{self.when_words(r, today)} · due {when_text(r['due'].isoformat())}",
            }
            for r in self.to_start()[:6]
        ] + self._revision("morning_rows")

    def morning_lines(self) -> list[str]:
        """For the wake-up call and the drafted plan."""
        today = now().date()
        return [self.line(r, today) for r in self.to_start()[:6]] + self._revision("morning_lines")

    def _revision(self, what: str) -> list:
        """Exam season's revision blocks for today (modules/revision.py), when it and its revision plan are on."""
        es = self._on("exam_season")
        return getattr(es.revision, what)() if es is not None and es.setting("revision") else []

    def crunch_text(self, weeks: list[dict]) -> str:
        parts = [
            f"week of {w['week'].day} {w['week']:%b}: about {w['work']:.0f} h of work, about {w['free']:.0f} h free"
            for w in weeks
        ]
        return "Crunch weeks (an estimate): " + "; ".join(parts) + ". Start some of it the week before."

    def weekly_lines(self) -> list[str]:
        """The Sunday summary: crunch weeks ahead, and what to start in the coming week."""
        t0 = now()
        out = []
        weeks = self.crunch(t0)
        if weeks:
            out.append(self.crunch_text(weeks))
            risky = self._risky(t0, weeks)
            if risky:  # 0.9.0 (startby.miss_risk)
                out.append("Likeliest to slip at your usual pace: " + ", ".join(risky[:3]) + ".")
        nxt = [r for r in self.plan(t0) if t0.date() < r["start"] <= t0.date() + dt.timedelta(days=7)]
        if nxt:
            out.append("To start this week: " + ", ".join(f"{r['title']} ({r['start']:%a})" for r in nxt[:5]))
        return out

    def overview(self) -> str:
        """Everything in a few lines, with ids (for the AI and calls)."""
        t0 = now()
        rows = self.plan(t0)
        if not rows:
            return "Nothing due in the next few weeks that I know of."
        today = t0.date()
        now_rows = [r for r in rows if r["start"] <= today]
        soon = sorted((r for r in rows if r["start"] > today), key=lambda r: r["start"])
        out = ["Start-by dates (an estimate from their timetable, calendar and each deadline's size):"]
        out += [f"- [{r['id']}] {self.line(r, today)}" for r in now_rows[:8]]
        out += [f"- [{r['id']}] {self.line(r, today)}" for r in soon[:6]]
        weeks = self.crunch(t0)
        if weeks:
            out.append(self.crunch_text(weeks))
        return "\n".join(out)

    def _buttons(self, i: str, h: float, kind: str) -> list:
        row = [(label, f"sby:{i}:{n}") for n, label in ladder(kind) if n != h]
        return [row[:3], row[3:]] if len(row) > 3 else [row]

    # ------------------------------------------------------------------------------ the morning pass
    def _morning(self, p: dict | None = None) -> None:
        """Once a day: note the deadlines whose start-by date has come; tell you about the big ones (up to three a
        day); ask once per subject how long its exams take."""
        t0 = now()
        today = t0.date()
        rows = self.plan(t0)
        tell = []
        with Lock(self.app.paths.state, "startby"):
            st = self._state()
            told = st.setdefault("told", {})
            first = not st.get("on_since")
            st.setdefault("on_since", today.isoformat())
            for r in rows:
                if r["start"] > today or r["id"] in told:
                    continue
                big = (r["due"].date() - today).days >= 2  # else the deadline's own day-before nudge says it
                if not first and big and self.setting("tell") and len(tell) >= 3:
                    continue  # tomorrow
                told[r["id"]] = today.isoformat()
                if not first and big and self.setting("tell") and not self._folded(r):
                    tell.append(r)
            live = set(self._dl().items())
            for k in ("told", "sizes"):
                st[k] = {i: v for i, v in (st.get(k) or {}).items() if i in live}
            jsave(self.file, st)
        if first and self.setting("tell"):
            self._hello(rows, today)
        for r in tell:
            self._tell(r)
        self._ask_exams(rows)
        self.app.events.emit("startby_planned", deadlines=len(rows), told=len(tell))

    # ------------------------------------------------------------------- what else knows about it (0.9.0)
    def studied_h(self, r: dict) -> float:
        """(startby.count_study) Hours the study tracker counted for this deadline: sessions tied to it (Study push's
        Start, modules/study.py) in the last 30 days; else, when it's the only open deadline in its subject due in
        the horizon, that subject's last 7 days. 0 when it can't tell."""
        study = self._on("study")
        if study is None or not self.setting("count_study"):
            return 0.0
        since = now() - dt.timedelta(days=30)
        exact = 0.0
        for e in self.app.events.tail(5000, kinds={"study_session_end"}):
            try:
                if e.get("deadline") == r["id"] and dt.datetime.fromisoformat(e["ts"]).replace(tzinfo=None) >= since:
                    exact += float(e.get("minutes") or 0) / 60
            except (KeyError, TypeError, ValueError):
                continue
        if exact > 0 or not r.get("subject"):
            return exact
        end = now() + dt.timedelta(days=max(1, int(self.setting("horizon_days") or 35)))
        same = [
            i
            for i, it in self._dl().items().items()
            if it.get("status") == "open" and it.get("subject") == r["subject"] and it.get("due", "") <= end.isoformat()
        ]
        if same != [r["id"]]:
            return 0.0
        try:
            return float(study.totals(7).get(r["subject"], 0)) / 3600
        except Exception:
            return 0.0

    def _risks(self) -> dict:
        """Brain's plans' last chances of missing each deadline (mind/plans: mind-plan-last.json), {deadline id: p}."""
        if not self.setting("miss_risk"):
            return {}
        try:
            from kurooto.mind import plans

            if not plans.on(self.app):
                return {}
        except ImportError:
            return {}
        risks = (jload(self.app.paths.state / "mind-plan-last.json", {}) or {}).get("risks") or {}
        return {k[2:]: float(v) for k, v in risks.items() if str(k).startswith("d:") and isinstance(v, (int, float))}

    def miss_risk(self, i: str) -> float:
        return self._risks().get(i, 0.0)

    def _risky(self, t0: dt.datetime, weeks: list[dict]) -> list[str]:
        """The deadlines due in the crunch weeks that Brain's plans think may slip, likeliest first: "Essay (40%)"."""
        risks = self._risks()
        if not risks:
            return []
        lo, hi = weeks[0]["week"], weeks[-1]["week"] + dt.timedelta(days=7)
        rows = [
            (risks[i], it["title"])
            for i, it in self._dl().items().items()
            if risks.get(i, 0) >= RISK_SAY
            and it.get("status") == "open"
            and lo.isoformat() <= it["due"][:10] < hi.isoformat()
        ]
        return [f"{title} ({round(p * 100)}%)" for p, title in sorted(rows, reverse=True)]

    def learn_share(self) -> str:
        """(startby.learn_share) Once a week: your pace (mind/plans/pace.py, the hours a day you really get done) as a
        share of your free time; when it's SHARE_GAP points or more from startby.share, an offer to use it. Never a
        share you set yourself; a No or an Undo leaves it alone for a month. Returns the line offered."""
        if not self.setting("learn_share"):
            return ""
        st = self._state().get("share_learned") or {}
        mine = (self.app.settings.user().get("startby") or {}).get("share")
        if mine is not None and mine != st.get("to"):
            return ""  # yours
        if st.get("at") and now() - dt.datetime.fromisoformat(st["at"]) < dt.timedelta(
            days=30 if st.get("state") in ("no", "undone") else 7
        ):
            return ""
        try:
            from kurooto.mind.plans import pace

            pool = pace.samples(self.app, now().date())
        except Exception:
            return ""
        per_day = sum(sum(v) / len(v) for v in pool.values() if v) / 7
        t0 = dt.datetime.combine(now().date() + dt.timedelta(days=1), dt.time(0))
        free = overlap_h(self.slots(t0, t0 + dt.timedelta(days=14)), t0, t0 + dt.timedelta(days=14)) / 14
        if free < 1 or per_day <= 0:
            return ""
        new = int(max(SHARE_LO, min(SHARE_HI, round(per_day / free * 100 / 5) * 5)))
        cur = round(self._share() * 100)
        if abs(new - cur) < SHARE_GAP:
            return ""
        self._put_state(share_learned={"at": now().isoformat(timespec="seconds"), "from": cur, "to": new,
                                       "state": "offered"})  # fmt: skip
        line = (
            f"Your pace says about {per_day:.1f} h a day of work, out of about {free:.1f} h free. Start-by dates "
            f"count {cur}% of your free time for deadlines; use {new}% instead? It moves start-by dates."
        )
        self.app.notify(
            line, kind="info", why="startby.share", buttons=[[("Yes", "sby:share:yes"), ("No", "sby:share:no")]]
        )
        self.app.events.emit("startby_share_offered", from_share=cur, to_share=new)
        return line

    def _share_answer(self, act: str) -> str:
        st = self._state().get("share_learned") or {}
        if act == "undo":
            if st.get("state") != "yes":
                return "Nothing to undo."
            if round(self._share() * 100) == st["to"]:
                self.app.settings.set("startby.share", st["from"])
            self._put_state(share_learned={**st, "state": "undone", "at": now().isoformat(timespec="seconds")})
            return f"Back to {st['from']}%; I'll leave it alone for a month."
        if st.get("state") != "offered":
            return "Already answered."
        if act == "no":
            self._put_state(share_learned={**st, "state": "no", "at": now().isoformat(timespec="seconds")})
            return f"OK, it stays at {st['from']}%."
        self.app.settings.set("startby.share", st["to"])
        self._put_state(share_learned={**st, "state": "yes", "at": now().isoformat(timespec="seconds")})
        self.app.notify(
            f"Start-by dates now count {st['to']}% of your free time.",
            kind="result",
            why="asked",
            buttons=[[("Undo", "sby:share:undo")]],
        )
        return f"Done: {st['to']}%."

    def _folded(self, r: dict) -> bool:
        """Brain's morning line about the subject it's most uneasy about took this message's place today (0.8.14,
        mind/study_push.py; mind.study_push.on)."""
        try:
            from kurooto.mind import study_push

            return study_push.folded(self.app, r.get("subject"), "startby")
        except Exception:
            return False

    def start_today(self, i: str) -> bool:
        """Count a deadline as started today (Yes under Brain's morning line, when Reminders is off)."""
        with Lock(self.app.paths.state, "startby"):
            st = self._state()
            if i not in self._dl().items():
                return False
            st.setdefault("told", {})[i] = now().date().isoformat()
            jsave(self.file, st)
        return True

    def _hello(self, rows: list[dict], today: dt.date) -> None:
        start = [r for r in rows if r["start"] <= today]
        if not start:
            return
        listed = "; ".join(self.line(r, today) for r in start[:5])
        self.app.notify(
            f"Start-by dates are on. Time to start now: {listed}. /startby shows them all, with sizes to correct "
            "(they're estimates).",
            kind="info",
            title="Start-by dates",
            why="startby.tell",
        )

    def _tell(self, r: dict) -> None:
        what = f"{r['title']}, due {when_text(r['due'].isoformat())}"
        why = f"my guess for {KINDS[r['kind']]}" if r["guessed"] else "the size you gave"
        if r["short"]:
            left = f"only about {hours(r['free'])} h" if r["free"] >= 0.5 else "hardly any"
            text = (
                f"Time to start: {what}. It's {size_text(r['hours'])} of work ({why}), and there's {left} free time "
                "for it before then. Start today, or ask for more time early."
            )
        else:
            text = (
                f"Time to start: {what}. It's {size_text(r['hours'])} of work ({why}); started today it fits around "
                "your classes and other deadlines."
            )
        buttons = self._buttons(r["id"], r["hours"], r["kind"])
        done = self.studied_h(r)
        if done >= COUNTED_MIN_H:  # 0.9.0 (startby.count_study): what the study tracker counted, and a tap to use it
            left = max(0.25, round((r["hours"] - done) * 2) / 2)
            text += f" You've put about {hours(done)} h into it already; about {hours(left)} h left if that counts."
            buttons = [[("Count it", f"sby:{r['id']}:{left:g}")], *buttons]
        learned = self.learned_note(r)
        if learned:  # 0.9.1 (startby.learned_line): what this kind really took, a tap to use it
            text += f" {learned[0]}"
            buttons = [[learned[1]], *buttons]
        risk = self.miss_risk(r["id"])
        if risk >= RISK_SAY:  # 0.9.0 (startby.miss_risk): Brain's plans, at your real pace
            text += f" At your usual pace there's about a {round(risk * 100)}% chance of missing it."
        try:  # (0.9.0, mind.presence_forecast.busy_hint) an add-on's usual busy times, as a hint only
            from kurooto.mind import presence_forecast as pf

            hint = pf.busy_hint(self.app) if pf.on(self.app) else ""
        except Exception:
            hint = ""
        if hint:
            text += f" {hint}"
        self.app.notify(
            text + " (An estimate. Wrong size? Tap the right one.)",
            kind="deadline",
            title="Start-by date",
            buttons=buttons,
            why="startby.tell",
            about=what,
        )
        self.app.events.emit("startby_told", kind=r["kind"], short=bool(r["short"]))

    def _ask_exams(self, rows: list[dict]) -> None:
        """The first exam of a subject with no exam size yet: ask once how long its exams take (one question a day)."""
        if not self.setting("ask_exams"):
            return
        by = self.setting("exam_by_subject") or {}
        with Lock(self.app.paths.state, "startby"):
            st = self._state()
            asked = st.setdefault("asked", [])
            new = [r for r in rows if r["kind"] == "exam" and r["subject"] and r["subject"] not in by]
            r = next((r for r in new if r["subject"] not in asked), None)
            if r is None:
                return
            asked.append(r["subject"])
            jsave(self.file, st)
        name = self._dl().subject_name(r["subject"])
        self.app.ask.ask(
            f"How long do you usually need to prepare for a {name} exam? {r['title']} is "
            f"{when_text(r['due'].isoformat())}; I'll work back from it to when you should start.",
            choices=[label for _, label in EXAM_SIZES],
            hook="startby.exam_size",
            hook_payload={"subject": r["subject"]},
            source=self.id,
            title="Exam preparation",
            expires="7d",
            why="startby.ask_exams",
            about=name,
            item=r["subject"],
        )
        self.app.events.emit("startby_asked")

    def _exam_answer(self, payload: dict, answer: str) -> str:
        h = parse_size(answer)
        slug = str(payload.get("subject") or "")
        if not h or not slug:
            return "I couldn't read that as a size. /startby exam <subject> 2-3 days sets it."
        return self.set_exam(slug, h)

    # ------------------------------------------------------------------------ negotiate, don't repeat
    def reshape(self, i: str, t0: dt.datetime | None = None) -> dict | None:
        """A reshaped plan for a deadline that's slipping, from your own Start-by plan: the hours this morning's plan
        put in today that no longer fit in what's left of today's free time, as some now and the rest tomorrow. None
        when it isn't slipping, it's outside today's window, or there's no free time tomorrow before it's due."""
        t0 = t0 or now()
        today = t0.date()
        a, b = parse_window(self.setting("window"))
        morning, end = dt.datetime.combine(today, a), dt.datetime.combine(today, b)
        if end <= morning:
            end += dt.timedelta(days=1)
        if not morning < t0 < end:
            return None
        pieces: dict = {}
        rows, _ = self.compute(morning, pieces=pieces)
        r = next((x for x in rows if x["id"] == i), None)
        if r is None:
            return None
        planned = sum(h for lo, _, h in pieces.get(i, []) if morning <= lo < end)
        free = overlap_h(self.slots(t0, end), t0, end) * self._share()
        if planned < 0.5 or free >= planned - 0.25:
            return None  # nothing planned today, or what's left of today still fits it
        now_h = min(planned, int(free * 2) / 2)
        later = -int(-(planned - now_h) * 2) / 2  # to the half hour, up
        nxt = morning + dt.timedelta(days=1)
        after = [s for s in self.slots(nxt, r["due"]) if s[0] >= nxt and s[0].date() == nxt.date()]
        if not after or after[0][0] + dt.timedelta(hours=later) > r["due"]:
            return None
        return {**r, "planned": planned, "now": now_h, "later": later, "at": after[0][0]}

    def reshape_text(self, x: dict) -> str:
        """ "Topology quiz (on Tue 10 Nov 10:00): your Start-by plan has 2 h of it today, and about 1 h of today's
        free time is left. 1 h now, 1 h tomorrow?" Plain, from your plan's numbers; no urgency added."""
        on = "on" if x["kind"] == "exam" else "due"
        head = f"{x['title']} ({on} {when_text(x['due'].isoformat())}): your Start-by plan has {hours(x['planned'])} h"
        if x["now"] >= 0.5:
            return (
                f"{head} of it today, and about {hours(x['now'])} h of today's free time is left. "
                f"{hours(x['now'])} h now, {hours(x['later'])} h tomorrow?"
            )
        return f"{head} of it today, and today's free time is used up. {hours(x['later'])} h tomorrow instead?"

    def _take_offer(self, i: str) -> dict | None:
        """The reshaped plan for today, noted as offered; None if there's none or one was offered today already."""
        today = now().date().isoformat()
        if ((self._state().get("reshape") or {}).get(i) or {}).get("day") == today:
            return None
        x = self.reshape(i)
        if x is None:
            return None
        with Lock(self.app.paths.state, "startby", timeout=5):
            st = self._state()
            offers = {k: v for k, v in (st.get("reshape") or {}).items() if v.get("day") == today}
            if i in offers:
                return None
            offers[i] = {"day": today, "state": "offered", "now": x["now"], "later": x["later"]}
            offers[i]["at"] = x["at"].isoformat(timespec="minutes")
            st["reshape"] = offers
            jsave(self.file, st)
        self.app.events.emit("startby_reshape_offered", now=x["now"], later=x["later"])
        return x

    def offer_reshape(self, i: str, again: bool = False) -> bool:
        """(negotiate) Instead of a reminder that would repeat for a slipping deadline (modules/deadlines.py): the
        reshaped plan, once a day per deadline, with [Do that] [Not today]. It repeats when that reminder came
        before (`again`) or Start-by said "time to start" on an earlier day. True when it was offered."""
        if not self.setting("negotiate"):
            return False
        since = (self._state().get("told") or {}).get(i)
        if not again and not (since and since < now().date().isoformat()):
            return False
        x = self._take_offer(i)
        if x is None:
            return False
        did = self._reshape_auto(i)  # 0.8.16 (mind.act.more): trusted with this, it moves the hours and says so
        if did is not None:
            self.app.notify(
                f"{x['title']} ({'on' if x['kind'] == 'exam' else 'due'} {when_text(x['due'].isoformat())}): today's "
                f"free time doesn't fit your Start-by plan's {hours(x['planned'])} h of it. {did['out']['said']}",
                kind="deadline",
                title="Plan reshaped",
                buttons=did["buttons"] or None,
                why="startby.negotiate",
                about=x["title"],
                item=i,
                ws_item=f"deadline:{i}",
                due=x["due"].isoformat(),
            )
            return True
        self.app.notify(
            self.reshape_text(x),
            kind="deadline",
            title="Reshape the plan?",
            buttons=[[("Do that", f"neg:{i}:yes"), ("Not today", f"neg:{i}:no")]],
            why="startby.negotiate",
            about=x["title"],
            item=i,
            ws_item=f"deadline:{i}",
            due=x["due"].isoformat(),
        )
        return True

    def reshape_answer(self, i: str, yes: bool) -> str:
        """Do that: tomorrow's part gets a reminder at its time (and blocks in the Agent plan calendar when that's
        on). Not today: nothing more about it today."""
        today = now().date().isoformat()
        with Lock(self.app.paths.state, "startby", timeout=5):
            st = self._state()
            rec = (st.get("reshape") or {}).get(i)
            if not rec or rec.get("day") != today:
                return "That offer was for another day."
            if rec.get("state") != "offered":
                return "Already answered."
            if not yes:
                rec["state"] = "declined"
                jsave(self.file, st)
        self.app.events.emit("startby_reshape_" + ("done" if yes else "declined"))
        if not yes:
            return "OK, not today. I won't bring it up again today."
        out = self._reshape_do(i, "done")
        if out is None:
            return "Already answered."
        try:  # 0.8.16: a yes to a reshaped plan is an OK for its kind (mind.act.more), so trust can grow
            from kurooto.mind import act

            act.answered(self.app, "deadline.reshape", True)
        except ImportError:
            pass
        return out["said"]

    def _reshape_auto(self, i: str) -> dict | None:
        try:
            from kurooto.mind import act
        except ImportError:
            return None
        _register_undo()
        return act.attempt(
            self.app,
            "deadline.reshape",
            lambda _: self._reshape_do(i, "auto"),
            summary="moved part of a slipping deadline's work to tomorrow",
            undo_from=lambda out: out.get("undo"),
        )

    def _reshape_do(self, i: str, how: str) -> dict | None:
        """The reshaped plan, done (Do that, or Kurooto by itself once trusted): tomorrow's part gets a reminder at its
        time (and blocks in the Agent plan calendar when that's on). {"said", "undo"}; None when it isn't on offer."""
        today = now().date().isoformat()
        with Lock(self.app.paths.state, "startby", timeout=5):
            st = self._state()
            rec = (st.get("reshape") or {}).get(i)
            if not rec or rec.get("day") != today or rec.get("state") != "offered":
                return None
            rec["state"] = how
            jsave(self.file, st)
        it = self._dl().items().get(i) or {}
        at, later, now_h = dt.datetime.fromisoformat(rec["at"]), float(rec["later"]), float(rec["now"])
        if later > 0:
            self.app.scheduler.at(
                at, "startby.moved", {"id": i, "hours": later}, key=f"startby:moved:{i}", module=self.id
            )
        said = (f"{hours(now_h)} h now, " if now_h >= 0.5 else "") + f"{hours(later)} h tomorrow from {at:%H:%M}"
        blocks = []
        plan = self.app.modules.get("agent_plan")
        if plan is not None and self.app.is_on("agent_plan") and getattr(plan, "plan_ready", lambda: False)():
            try:  # blocks in Kurooto's own calendar when you use it (modules/google_plan.py)
                t = now()
                title = it.get("title") or "Deadline"
                if now_h >= 0.5:
                    plan.plan_block(t, t + dt.timedelta(hours=now_h), title, i)
                    blocks.append([t.replace(second=0, microsecond=0).isoformat(), title])
                plan.plan_block(at, at + dt.timedelta(hours=later), title, i)
                blocks.append([at.replace(second=0, microsecond=0).isoformat(), title])
                said += "; blocks are in your Agent plan calendar"
            except Exception as e:
                self.app.events.emit("startby_failed", error=f"blocks: {type(e).__name__}: {e}"[:200])
        lead = "OK:" if how == "done" else "I've moved it:"
        return {"said": f"{lead} {said}. I'll remind you then.", "undo": {"id": i, "day": today, "blocks": blocks}}

    def reshape_undo(self, p: dict | None) -> str:
        """Undo under a plan Kurooto reshaped by itself: tomorrow's reminder and its Agent plan blocks go."""
        p = p or {}
        i = str(p.get("id") or "")
        self.app.scheduler.cancel(f"startby:moved:{i}")
        with Lock(self.app.paths.state, "startby", timeout=5):
            st = self._state()
            rec = (st.get("reshape") or {}).get(i)
            if rec and rec.get("day") == p.get("day") and rec.get("state") == "auto":
                rec["state"] = "undone"
                jsave(self.file, st)
        plan = self.app.modules.get("agent_plan")
        left = 0
        for start, title in p.get("blocks") or []:
            try:  # only Kurooto's own calendar, only the blocks this reshape put there
                t = dt.datetime.fromisoformat(start)
                cid = plan.calendar_id(create=False)
                b = next(
                    (b for b in plan.plan_blocks(t.date()) if b["title"] == title and b["start"] == t and b.get("id")),
                    None,
                )
                if cid and b:
                    plan._delete(cid, b["id"])  # noqa: SLF001
                else:
                    left += 1
            except Exception:
                left += 1
        self.app.events.emit("startby_reshape_undone", blocks=len(p.get("blocks") or []), left=left)
        tail = f" {left} block{'s' if left != 1 else ''} stayed in your Agent plan calendar (/blocks clear)."
        return "Taken back: the plan is as it was, with no reminder tomorrow." + (tail if left else "")

    def _moved(self, p: dict) -> None:
        """Tomorrow's part of a reshaped plan, at its time (a reminder of what you agreed to)."""
        i = str((p or {}).get("id") or "")
        it = self._dl().items().get(i)
        if not it or it.get("status") != "open":
            return
        self.app.notify(
            f"{it['title']}: the {hours(float(p.get('hours') or 0))} h you moved to today. Due {when_text(it['due'])}.",
            kind="deadline",
            why="startby.moved",
            about=it["title"],
            item=i,
            ws_item=f"deadline:{i}",
            due=it["due"],
        )

    def _tool_reshape(self, a: dict) -> str:
        i = self._dl()._resolve(self._dl().items(), str(a.get("id", ""))) or str(a.get("id", ""))
        x = self._take_offer(i) if self.setting("negotiate") else None
        if x is None:
            return (
                "Nothing to reshape for that one now: it still fits today, it was offered today already, or there's "
                "no free time before it's due."
            )
        return self.reshape_text(x) + " (Offer it once; if they say yes call reshape_answer with yes, if no with no.)"

    def _tool_reshape_answer(self, a: dict) -> str:
        i = self._dl()._resolve(self._dl().items(), str(a.get("id", ""))) or str(a.get("id", ""))
        return self.reshape_answer(i, str(a.get("answer", "")).strip().lower() in ("yes", "y", "do that", "ok"))

    # ------------------------------------------------------------------------------- your corrections
    def set_exam(self, slug: str, h: float) -> str:
        h = max(0.5, min(200.0, h))
        self.app.settings.set(f"startby.exam_by_subject.{slug}", h)
        self.app.events.emit("startby_exam_size", hours=h)
        name = self._dl().subject_name(slug) or slug
        return f"{name} exams: {size_text(h)} to prepare. Start-by dates follow it."

    def set_size(self, i: str, h: float) -> str:
        """A deadline's size, in hours (a tap, a call, /startby). For an exam, its subject's exams too."""
        items = self._dl().items()
        j = i if i in items else next((k for k, it in items.items() if i in it.get("aliases", [])), None)
        if not j or items[j].get("status") != "open":
            return "That one is gone."
        it = items[j]
        h = max(0.25, min(200.0, h))
        with Lock(self.app.paths.state, "startby"):
            st = self._state()
            st.setdefault("sizes", {})[j] = h
            jsave(self.file, st)
        kind = kind_of(it["title"], it.get("kind", "task"))
        extra = ""
        if kind == "exam" and it.get("subject"):
            self.app.settings.set(f"startby.exam_by_subject.{it['subject']}", h)
            extra = f" {self._dl().subject_name(it['subject'])} exams count as that from now on."
        self.app.events.emit("startby_size_set", kind=kind, hours=h)
        today = now().date()
        r = next((r for r in self.plan() if r["id"] == j), None)
        when = self.when_words(r, today) if r else ""
        when = f" {when[:1].upper()}{when[1:]}." if when else ""
        return f"{it['title']}: {size_text(h)} of work.{when}{extra}"

    def callbacks(self):
        return {"sby": self._button, "neg": lambda ref, act: self.reshape_answer(ref, act == "yes")}

    def _button(self, ref: str, act: str) -> str:
        if ref == "window" and act == "undo":
            return self._window_undo()
        if ref == "share" and act in ("yes", "no", "undo"):
            return self._share_answer(act)
        try:
            h = float(act)
        except ValueError:
            return "That button is out of date."
        return self.set_size(ref, h)

    # ------------------------------------------------------------------------------------ commands
    def commands(self):
        return [Command("startby", "when to start each deadline: /startby, /startby exam la 2-3 days", self._cmd)]

    def _cmd(self, msg: Incoming, arg: str) -> str | None:
        a = arg.strip()
        if re.match(r"(?i)exams?\b", a):
            return self._exam_cmd(re.sub(r"(?i)^exams?\s*", "", a))
        t0 = now()
        rows = self.plan(t0)
        if not rows:
            return f"Nothing due in the next {self.setting('horizon_days') or 35} days that I know of."
        head = "Start-by dates, worked back from each deadline's size and your free time (an estimate)."
        weeks = self.crunch(t0)
        msg.reply(head + ("\n" + self.crunch_text(weeks) if weeks else "") + "\nTap a size to correct one.")
        for r in sorted(rows, key=lambda r: (r["start"], r["due"]))[:10]:
            msg.reply(self.line(r, t0.date()), buttons=self._buttons(r["id"], r["hours"], r["kind"]))
        return None

    def _exam_cmd(self, a: str) -> str:
        by = self.setting("exam_by_subject") or {}
        if not a:
            default = (self.setting("sizes") or {}).get("exam", 10)
            rows = [f"{self._dl().subject_name(s) or s}: {size_text(float(h))}" for s, h in sorted(by.items())]
            return "\n".join(
                ["Exam preparation per subject:", *rows, f"Any other subject: {size_text(float(default))}."]
                if rows
                else [f"Every subject's exams: {size_text(float(default))} to prepare (/startby exam la 2-3 days)."]
            )
        m = re.match(r"(\S+)\s+(.+)$", a)
        h = parse_size(m[2]) if m else None
        subj = self._on("subjects")
        slug = subj.resolve(m[1]) if m and subj is not None else None
        if not m or not h:
            return "Usage: /startby exam <subject> <size>, e.g. /startby exam la 2-3 days (or 15h, a week)"
        if not slug:
            return f"I don't know a subject called {m[1]!r} (/subject add, with Subjects on)."
        return self.set_exam(slug, h)

    def intents(self):
        def when_start(text: str):
            m = WHEN_START.match(text)
            return {"what": (m["what"] or "").strip().removeprefix("the ").strip()} if m else None

        def run_when(msg, s):
            today = now().date()
            rows = self.plan()
            if s["what"]:
                hit = [r for r in rows if similar(s["what"], r["title"])]
                if hit:
                    return "\n".join(self.line(r, today) for r in hit[:3]) + " (an estimate)"
                return f"I don't have {s['what']!r} on the deadline list. /startby shows them all."
            start = [r for r in rows if r["start"] <= today]
            return "\n".join(self.line(r, today) for r in start[:8]) or "Nothing needs starting today. /startby"

        def run_crunch(msg, s):
            weeks = self.crunch()
            return self.crunch_text(weeks) if weeks else "No crunch weeks ahead that I can see (an estimate)."

        return [
            Intent(
                "start_by",
                "when should I start X",
                when_start,
                run_when,
                questions=True,
                examples=("when should I start the essay?",),
            ),
            Intent(
                "crunch_weeks",
                "crunch weeks ahead",
                lambda t: {} if CRUNCH.search(t) else None,
                run_crunch,
                questions=True,
                examples=("any crunch weeks ahead?",),
            ),
        ]

    # -------------------------------------------------------------------------------------- on calls
    def call_brief(self) -> dict:
        lines = self.morning_lines()
        return {"time_to_start": lines} if lines else {}

    def call_tools(self):
        return [
            Tool(
                "start_by",
                "When to start each deadline (worked back from its size and their free time; an estimate), with ids, "
                "and crunch weeks ahead.",
                lambda a: self.overview(),
                offline="brief",
                writes=False,
                hint="start_by lists what to start now; set_work_size when they say how long something takes.",
            ),
            Tool(
                "set_work_size",
                "How much work a deadline is (its id from start_by): '3h', 'an evening', 'a day', '2-3 days', "
                "'a week'.",
                self._tool_size,
                {"id": arg(), "size": arg()},
                ("id", "size"),
                offline="queue",
                writes=True,
            ),
            Tool(
                "reshape_plan",
                "For a deadline they're behind on (its id from start_by): a reshaped plan from their own Start-by "
                "plan, e.g. '1 h now, 1 h tomorrow', to offer once. Says so when there's none.",
                self._tool_reshape,
                {"id": arg()},
                ("id",),
                offline="needs",
                writes=False,
                hint="On a deadline call, if they're behind, offer reshape_plan's plan once, calmly; never press or "
                "repeat it. Then reshape_answer with yes or no.",
            ),
            Tool(
                "reshape_answer",
                "Their answer to the reshaped plan (id from start_by): 'yes' (tomorrow's part gets a reminder) or "
                "'no' (not today).",
                self._tool_reshape_answer,
                {"id": arg(), "answer": arg()},
                ("id", "answer"),
                offline="queue",
                writes=True,
            ),
        ]

    def _tool_size(self, a: dict) -> str:
        h = parse_size(str(a.get("size", "")))
        if not h:
            return f"I couldn't read {a.get('size')!r} as a size (e.g. 3h, an evening, 2-3 days)."
        return self.set_size(str(a.get("id", "")), h)

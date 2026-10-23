"""Start-by dates and crunch weeks: when to start each deadline, worked back from your free time.

Each deadline gets a size, guessed from what it is: a problem set or homework is an evening (3 h), a report, essay,
project or presentation 2-3 days (12 h), a quiz 2 h, an exam what you set for its subject (10 h until you do).
Correct it with one tap: the "Time to start" message and /startby offer the other sizes. A size you tap for an exam
counts for that subject's exams from then on, and the first exam of a subject asks you once.

Free time is each day's window (startby.window, 09:00-22:00) less your classes (Subjects: the timetable, holidays,
exam periods, the classes you skip) and your calendar's timed events (Calendar), in gaps of at least half an hour,
and only a share of that (startby.share, 40%): the rest is meals, rest, going over lectures and everything else.
Working back from the due times, latest first, each deadline's hours go into the latest free time before it that
nothing due later has taken; the day its first hour lands on is its start-by date. Two big deadlines in one week push
each other earlier.

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
    },
)
DAY_H = 5  # "a day" of work, for sizes given in days
WEEK_H = 25
TASK_SIZES = [(1, "An hour"), (3, "An evening"), (5, "A day"), (12, "2-3 days"), (25, "A week")]
EXAM_SIZES = [(3, "An evening"), (5, "A day"), (12, "2-3 days"), (25, "A week"), (50, "Two weeks")]
NAMES = {h: label for h, label in TASK_SIZES + EXAM_SIZES}
LEARN_DAYS, LEARN_ACTIVE_DAYS, LEARN_MSGS, LEARN_GAP_MIN = 21, 7, 3, 60  # look back, days needed, a day's, off by
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


def allocate(
    items: list[dict], slots: list[tuple[dt.datetime, dt.datetime]], share: float, pieces: dict | None = None
) -> dict[str, tuple[dt.datetime | None, float]]:
    """As late as possible: latest due first, each item's hours (items: {"id", "due", "hours"}) go into the latest
    free time before its due time that a later one hasn't taken; `share` (0-1) of each free hour counts. Returns
    {id: (where its work starts, or None if no time at all; the hours that didn't fit)}. `pieces`, when given, gets
    where each item's hours went: {id: [(from, to, hours of work), ...]}."""
    free = [[s, e] for s, e in sorted(slots)]
    share = min(1.0, max(0.01, share))
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
        self.every("learn_window", "weekly sun 12:00", lambda p: self.learn_window())
        self.action("moved", self._moved)  # (negotiate) the part you moved to tomorrow, at its time

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
        if len(active) < LEARN_ACTIVE_DAYS:
            return ""
        first = sorted(v[0] for v in active)[len(active) // 2]
        last = sorted(v[-1] for v in active)[len(active) // 2]
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
            f"that's when your messages came in on {len(active)} days of the last three weeks."
        )
        self.app.events.emit("startby_window_learned", from_window=cur, to_window=new, days=len(active))
        self.app.notify(line, kind="info", why="startby.window", buttons=[[("Undo", "sby:window:undo")]])
        return line

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
        sizes = self.setting("sizes") or {}
        try:
            h = float(sizes.get(kind, sizes.get("other", 2)))
        except (TypeError, ValueError):
            h = 2.0
        return max(0.25, h), kind, True

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

    def slots(self, t0: dt.datetime, until: dt.datetime) -> list[tuple[dt.datetime, dt.datetime]]:
        """The free time from t0 until `until`: each day's window less classes and calendar events."""
        window = parse_window(self.setting("window"))
        try:
            gap = int(self.setting("min_gap_min") or 0)
        except (TypeError, ValueError):
            gap = 30
        events = self._events(t0 - dt.timedelta(days=1), until)
        subj = self._on("subjects")
        out = []
        day = t0.date() - dt.timedelta(days=1)  # a window past midnight starts the day before
        while day <= until.date():
            busy = list(events)
            if subj is not None:
                busy += [(c["start_dt"], c["end_dt"]) for c in subj.classes_on(day)]
            out += [(s, min(e, until)) for s, e in free_slots(day, window, busy, t0, gap) if s < until]
            day += dt.timedelta(days=1)
        return out

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
        fits = allocate(work, slots, self._share(), pieces)
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
                if not first and big and self.setting("tell"):
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
        self.app.notify(
            text + " (An estimate. Wrong size? Tap the right one.)",
            kind="deadline",
            title="Start-by date",
            buttons=self._buttons(r["id"], r["hours"], r["kind"]),
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
        self.app.notify(
            self.reshape_text(x),
            kind="deadline",
            title="Reshape the plan?",
            buttons=[[("Do that", f"neg:{i}:yes"), ("Not today", f"neg:{i}:no")]],
            why="startby.negotiate",
            about=x["title"],
            item=i,
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
            rec["state"] = "done" if yes else "declined"
            jsave(self.file, st)
        self.app.events.emit("startby_reshape_" + ("done" if yes else "declined"))
        if not yes:
            return "OK, not today. I won't bring it up again today."
        it = self._dl().items().get(i) or {}
        at, later, now_h = dt.datetime.fromisoformat(rec["at"]), float(rec["later"]), float(rec["now"])
        if later > 0:
            self.app.scheduler.at(
                at, "startby.moved", {"id": i, "hours": later}, key=f"startby:moved:{i}", module=self.id
            )
        said = (f"{hours(now_h)} h now, " if now_h >= 0.5 else "") + f"{hours(later)} h tomorrow from {at:%H:%M}"
        plan = self.app.modules.get("agent_plan")
        if plan is not None and self.app.is_on("agent_plan") and getattr(plan, "plan_ready", lambda: False)():
            try:  # blocks in Kurooto's own calendar when you use it (modules/google_plan.py)
                t = now()
                if now_h >= 0.5:
                    plan.plan_block(t, t + dt.timedelta(hours=now_h), it.get("title") or "Deadline")
                plan.plan_block(at, at + dt.timedelta(hours=later), it.get("title") or "Deadline")
                said += "; blocks are in your Agent plan calendar"
            except Exception as e:
                self.app.events.emit("startby_failed", error=f"blocks: {type(e).__name__}: {e}"[:200])
        return f"OK: {said}. I'll remind you then."

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

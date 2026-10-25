"""The day's numbers (Brain, 0.8.0 stage 04): what the read and the forecast are made from, collected from what Kurooto
already sees of your day and handed to the scorekeeper as plain facts (`signal`). Numbers only: no words of any message.

    wake_min          when you were first up (Subjects.woke_at; else your first sign of life with Kurooto), minutes
    after midnight
    sleep_min         your last sign of life before the night (once the day is over), minutes after midnight; past
    midnight counts on
    study_min         minutes in finished study sessions
    reply_band        how fast you answered a check-in, banded 0-4 (under 2 min, 10, 60, 240, longer); never used for
    reward (I-3)
    deadline_moves    deadlines you moved
    tone_mean         the day's tone, from mind/tone.py (-1 stretched ... +1 upbeat), when that's on
    load_*            what the calendar asked that day: deadlines due within 72 h (weighted: exam 3, other 1, and
    plain count),
                      class hours, exam season. These are what the other numbers are explained by.

Not collected yet: snoozes (the alarm doesn't say it) and classes attended (only skips are known). Kept 30 days by the
scorekeeper. A day is 04:00 to 04:00.
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

from kurooto import mind
from kurooto.core.clock import now

if TYPE_CHECKING:
    from kurooto.app import App

PART = "read"  # its switch: mind.read.on

DAY_STARTS = 4  # hours: the day turns at 04:00
# a sign that you're up and about, with Kurooto (not something it did by itself)
ACTIVE = frozenset(
    {
        "checkin_answered", "capture_answered", "button_tapped", "call_answered", "phone_answered", "revision_answered",
        "exam_eve_answered", "study_session_start", "study_session_end", "deadline_done", "deadline_moved",
        "message_in",
    }
)  # fmt: skip
BANDS_MIN = (2, 10, 60, 240)  # minutes: under 2 is band 0 ... 240 and more is band 4
LOAD_NAMES = ("load_deadlines_w", "load_deadlines_n", "load_class_h", "load_exam")


def span(day: dt.date) -> tuple[float, float]:
    lo = dt.datetime.combine(day, dt.time(DAY_STARTS)).timestamp()
    return lo, lo + 86400


def _ts(rec: dict) -> float | None:
    try:
        return dt.datetime.fromisoformat(str(rec.get("ts"))).timestamp()
    except ValueError:
        return None


def _events(app: App, lo: float, hi: float, kinds) -> list[tuple[float, dict]]:
    out = []
    for rec in app.events.tail(20000, set(kinds)):
        t = _ts(rec)
        if t is not None and lo <= t < hi:
            out.append((t, rec))
    return out


def band(minutes: float) -> int:
    return sum(1 for b in BANDS_MIN if minutes >= b)


def _minutes_after_midnight(t: float, day: dt.date) -> float:
    return (t - dt.datetime.combine(day, dt.time(0)).timestamp()) / 60.0


def load(app: App, day: dt.date) -> dict[str, float]:
    """What the calendar asked of that day (the 72 hours from its midnight, its class hours, exam season)."""
    out: dict[str, float] = {"load_deadlines_w": 0.0, "load_deadlines_n": 0.0, "load_class_h": 0.0, "load_exam": 0.0}
    t0 = dt.datetime.combine(day, dt.time(0)).timestamp()
    dl = app.modules.get("deadlines")
    if dl is not None and app.is_on("deadlines"):
        try:
            for it in dl.items().values():
                due = dt.datetime.fromisoformat(str(it.get("due"))).timestamp()
                if t0 <= due < t0 + 72 * 3600:
                    out["load_deadlines_n"] += 1
                    out["load_deadlines_w"] += 3 if it.get("kind") == "exam" else 1
        except Exception:
            pass
    sub = app.modules.get("subjects")
    if sub is not None and app.is_on("subjects"):
        try:
            out["load_class_h"] = round(
                sum((c["end_dt"] - c["start_dt"]).total_seconds() for c in sub.classes_on(day)) / 3600, 2
            )
        except Exception:
            pass
    ex = app.modules.get("exam_season")
    if ex is not None and app.is_on("exam_season"):
        try:
            out["load_exam"] = 1.0 if ex.season(dt.datetime.combine(day, dt.time(12))) else 0.0
        except Exception:
            pass
    return out


def collect(app: App, day: dt.date, final: bool = False) -> dict[str, float]:
    """The day's numbers so far (final: the day is over, so sleep is known too). Only what could be measured."""
    lo, hi = span(day)
    out: dict[str, float] = dict(load(app, day))
    act = sorted(t for t, _ in _events(app, lo, hi, ACTIVE))
    woke = None
    sub = app.modules.get("subjects")
    if sub is not None and app.is_on("subjects"):
        try:
            woke = sub.woke_at(day)
        except Exception:
            woke = None
    if woke is not None:
        out["wake_min"] = round(_minutes_after_midnight(woke.timestamp(), day), 1)
    elif act:
        out["wake_min"] = round(_minutes_after_midnight(act[0], day), 1)
    if final and len(act) >= 3:
        out["sleep_min"] = round(_minutes_after_midnight(act[-1], day), 1)
    ends = _events(app, lo, hi, {"study_session_end"})
    if ends:
        out["study_min"] = float(sum(float(r.get("minutes") or 0) for _, r in ends))
    moved = _events(app, lo, hi, {"deadline_moved"})
    out["deadline_moves"] = float(len(moved))
    asked = _events(app, lo, hi, {"checkin_asked"})
    answered = _events(app, lo, hi, {"checkin_answered"})
    gaps = []
    for t, r in asked:
        nxt = next((t2 for t2, r2 in answered if t2 >= t and r2.get("name") == r.get("name")), None)
        if nxt is not None:
            gaps.append((nxt - t) / 60.0)
    if gaps:
        gaps.sort()
        out["reply_band"] = float(band(gaps[len(gaps) // 2]))
    from kurooto.mind import tone

    tm = tone.daily_mean(app, day)
    if tm is not None:
        out["tone_mean"] = tm
    return out


def report(app: App, day: dt.date, final: bool = False) -> int:
    """Collect the day and hand each number to the scorekeeper. How many were sent."""
    if not mind.on(app):
        return 0
    c = mind.connect(app)
    n = 0
    for name, value in collect(app, day, final).items():
        c.report("signal", {"day": day.isoformat(), "name": name, "value": value})
        n += 1
    return n


def run(app: App, payload: dict | None = None) -> int:
    """The hourly job: today so far, and yesterday once more with its night (the day is over)."""
    if not (mind.part_on(app, "read") or mind.part_on(app, "forecast")):
        return 0
    today = now().date()
    if now().hour < DAY_STARTS:  # between midnight and 04:00 it's still yesterday's day
        today -= dt.timedelta(days=1)
    n = report(app, today)
    n += report(app, today - dt.timedelta(days=1), final=True)
    return n

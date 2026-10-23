"""Time helpers: the user's local time, and reading times people type ("21:30", "in 20 min", "tomorrow 7am")."""

from __future__ import annotations

import datetime as dt
import re

_UNITS = {
    "m": "minutes",
    "min": "minutes",
    "mins": "minutes",
    "minute": "minutes",
    "minutes": "minutes",
    "h": "hours",
    "hr": "hours",
    "hrs": "hours",
    "hour": "hours",
    "hours": "hours",
    "d": "days",
    "day": "days",
    "days": "days",
    "w": "weeks",
    "week": "weeks",
    "weeks": "weeks",
}
_DAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
_TIME = r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?"


def now() -> dt.datetime:
    """Local wall-clock time without microseconds."""
    return dt.datetime.now().replace(microsecond=0)


def _hm(h: str, mi: str | None, ampm: str | None) -> tuple[int, int]:
    hour, minute = int(h), int(mi or 0)
    if ampm == "pm" and hour < 12:
        hour += 12
    if ampm == "am" and hour == 12:
        hour = 0
    if not (0 <= hour < 24 and 0 <= minute < 60):
        raise ValueError("no such time")
    return hour, minute


def parse_when(text: str, base: dt.datetime | None = None) -> dt.datetime:
    """'21:30', '9pm', 'in 20 minutes', '30m', '2h', '+45', 'in 3 days', 'tomorrow 7:00', 'mon 9am',
    '2026-11-02 14:00', '2026-11-02' (09:00) -> a local datetime in the future (times today roll to tomorrow).
    A bare number is minutes from now ('20' is in 20 minutes, not 20:00). Raises ValueError if it can't read it."""
    base = base or now()
    s = re.sub(r"\s+", " ", (text or "").strip().lower())
    s = re.sub(r"^(at|on|by) ", "", s)

    m = re.fullmatch(r"(?:in )?\+?(\d+) ?([a-z]+)?", s)
    if m and (m[2] is None or m[2] in _UNITS):
        unit = _UNITS.get(m[2] or "m")
        return base + dt.timedelta(**{unit: int(m[1])})

    m = re.fullmatch(_TIME, s)
    if m and (m[2] or m[3] or len(m[1]) <= 2):
        h, mi = _hm(m[1], m[2], m[3])
        t = base.replace(hour=h, minute=mi, second=0)
        return t if t > base else t + dt.timedelta(days=1)

    m = re.fullmatch(r"(?:at )?" + _TIME + r" (today|tonight|tomorrow|tmrw|tmr)", s)
    if m:
        day = base.date() + dt.timedelta(days=0 if m[4] in ("today", "tonight") else 1)
        h, mi = _hm(m[1], m[2], m[3])
        return dt.datetime.combine(day, dt.time(h, mi))

    m = re.fullmatch(r"(today|tonight|tomorrow|tmrw|tmr)(?: (?:at )?" + _TIME + ")?", s)
    if m:
        day = base.date() + dt.timedelta(days=0 if m[1] in ("today", "tonight") else 1)
        h, mi = _hm(m[2], m[3], m[4]) if m[2] else ((21, 0) if m[1] == "tonight" else (9, 0))
        return dt.datetime.combine(day, dt.time(h, mi))

    days = "mon(?:day)?|tue(?:s|sday)?|wed(?:nesday)?|thu(?:r|rs|rsday)?|fri(?:day)?|sat(?:urday)?|sun(?:day)?"
    m = re.fullmatch(r"(?:(next) )?(" + days + r")(?: (?:at )?" + _TIME + ")?", s)
    if m:
        is_next = bool(m[1])
        target_day = _DAYS[m[2][:3]]
        h, mi = _hm(m[3], m[4], m[5]) if m[3] else (9, 0)
        diff = (target_day - base.weekday()) % 7
        if diff == 0:
            if is_next:
                ahead = 7
            else:
                target_dt = dt.datetime.combine(base.date(), dt.time(h, mi))
                ahead = 0 if target_dt > base else 7
        else:
            ahead = diff
        return dt.datetime.combine(base.date() + dt.timedelta(days=ahead), dt.time(h, mi))

    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})(?:[ t]" + _TIME + ")?", s)
    if m:
        h, mi = _hm(m[4], m[5], m[6]) if m[4] else (9, 0)
        return dt.datetime(int(m[1]), int(m[2]), int(m[3]), h, mi)

    raise ValueError(f"can't read the time {text!r}")

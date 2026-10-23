"""Reading plain English: times ("at 9:30", "till 6"), durations ("for 50 min", "half an hour"), and guards that
send anything unclear to the AI instead of acting on a guess."""

from __future__ import annotations

import datetime as dt
import re

from kurooto.core.clock import now

TIME = re.compile(r"\b(?:at\s+|till\s+|until\s+|by\s+)?(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm)?\b", re.I)
DUR = re.compile(r"\b(\d+(?:\.\d+)?)\s*(h|hr|hrs|hour|hours|m|min|mins|minute|minutes)\b", re.I)
QUESTION = re.compile(
    r"^\s*(?:what|when|why|how|who|where|which|was|were|is|are|summari[sz]e|tell me|show me|explain)\b", re.I
)
MULTI = re.compile(
    r"\b(?:also|plus|and then|after that|btw|by the way)\b|[.?!;]\s+\S|,\s*and\b"
    r"|\band\s+(?:skip|move|push|cancel|call|remind|start|stop|ignore|log)\b",
    re.I,
)
OTHER_DAY = re.compile(
    r"\b(?:mon|tues|wednes|thurs|fri|satur|sun)day\b|\b(?:yesterday|day after)\b|\bnext (?:week|month)\b"
    r"|\blast (?:week|night)\b|\b\d{1,2}(?:st|nd|rd|th)?\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b"
    r"|\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2}\b|\b\d{1,2}/\d{1,2}\b",
    re.I,
)
NEG = re.compile(r"\b(?:don'?t|do not|never|no need to|stop)\b", re.I)
THANKS = re.compile(r"[\s,.!]*\b(?:thanks|thank you|thx|ty|pls|please)\b[\s.!]*$", re.I)
# A clause about the past or a plan that didn't happen: "since I didn't wake up at 12", "as I said I would", "was
# supposed to at 9". Its time is never the time of a call, reminder or check-in.
CLAUSE = re.compile(
    r"[,;!?()]|[.:](?!\d)|\s[-–—]\s|\b(?:since|because|cause|cuz|coz|as|but|though|although|so|and|or)\b", re.I
)
STALE = re.compile(
    r"\b(?:didn'?t|did not|couldn'?t|could not|wasn'?t|was not|weren'?t|haven'?t|hadn'?t|was|were|supposed to|meant to"
    r"|planned|promised|(?:would|should|could)(?:'ve| have)|said (?:i|i'd|i'll|that)|woke|overslept|slept|got up|missed"
    r"|yesterday|last night|ago)\b",
    re.I,
)
# "I'm awake", "I just woke up", "I'm up": up now (not "I'm still up", "I'm up for it", "I didn't wake up")
AWAKE = re.compile(
    r"\b(?:i'?m|i am|im)\s+(?:(?:now|finally|already|just|wide)\s+)?(?:awake|up)\b"
    r"(?!\s+(?:for|to|at|late|till|until|with|against|all)\b)"
    r"|\b(?:just|finally)\s+(?:woke|got)\s+up\b|\bi(?:'ve| have)\s+(?:just\s+)?(?:woken|got)\s+up\b",
    re.I,
)
STILL_UP = re.compile(r"\b(?:still|can'?t sleep|cannot sleep|couldn'?t sleep|not (?:yet )?(?:awake|up))\b", re.I)
ALSO = re.compile(r"\b(?:also|plus|and then|after that|btw|by the way)\b", re.I)
REPLAN = re.compile(r"\b(?:re-?schedule|re-?plan|shift|push|move)\b.*\b(?:day|plan|schedule|blocks?)\b", re.I)


WEEKDAY = re.compile(r"\b(mon|tues|wednes|thurs|fri|satur|sun)day\b", re.I)
WEEKDAYS = ["mon", "tues", "wednes", "thurs", "fri", "satur", "sun"]
# A weekday that says when ("friday at 5pm", "on friday", "this friday", "next friday": first, after on/this/next, or
# just before a time), not one in what it's about ("to revise for friday's quiz").
WHEN_DAY = re.compile(
    r"(?:^\s*|\b(?:on|this|(?P<next>next))\s+)(?P<d1>mon|tues|wednes|thurs|fri|satur|sun)day\b(?!')"
    r"|\b(?P<d2>mon|tues|wednes|thurs|fri|satur|sun)day(?=\s+(?:at\s+|by\s+)?\d)",
    re.I,
)


def tidy(text: str) -> str:
    return THANKS.sub("", text.strip())


def a_day(text: str, base: dt.datetime | None = None) -> dt.date | None:
    """The day a request is about: today unless it names another. "tomorrow", "day after tomorrow" or one weekday
    ("skip Friday's check-in": the coming Friday, today if it's Friday) give that date; a day it can't pin down
    ("yesterday", "next week", "on the 25th", "next Friday") gives None, so the request goes to the AI instead."""
    base = base or now()
    low = text.lower()
    if re.search(r"\bday after tomorrow\b", low):
        return base.date() + dt.timedelta(days=2)
    if OTHER_DAY.search(text):
        days = {m.lower() for m in WEEKDAY.findall(text)}
        if len(days) != 1 or OTHER_DAY.search(WEEKDAY.sub("", text)) or re.search(r"\b(?:next|last|tomorrow)\b", low):
            return None
        return base.date() + dt.timedelta(days=(WEEKDAYS.index(days.pop()) - base.weekday()) % 7)
    if re.search(r"\b(?:tomorrow|tmrw|tmr)\b", low):
        return base.date() + dt.timedelta(days=1)
    return base.date()


def another_day(text: str, base: dt.datetime | None = None) -> bool:
    """True when a request is about a day other than today (or a day that can't be pinned down)."""
    return a_day(text, base) != (base or now()).date()


def too_complex(text: str) -> bool:
    """Long, or several requests in one message: the AI should read the whole thing."""
    return not text or len(text) > 300 or text.startswith("/") or bool(MULTI.search(text))


def stale(text: str, pos: int) -> bool:
    """Is the time at pos in a clause about the past or about what didn't happen ("didn't wake up at 12")?"""
    cuts = [(c.start(), c.end()) for c in CLAUSE.finditer(text)]
    start = max([e for s, e in cuts if e <= pos], default=0)
    end = min([s for s, e in cuts if s >= pos], default=len(text))
    return bool(STALE.search(text[start:end]))


def _time_match(text: str, past: bool = False) -> re.Match | None:
    """The first time in the text (not a duration, not a bare number) that isn't in a past or negated clause; with
    past=True, the first one that is."""
    for m in TIME.finditer(text):
        h, mi, ap = int(m[1]), int(m[2] or 0), (m[3] or "").lower()
        if h > 23 or mi > 59:
            continue
        if not m[2] and DUR.match(text[m.start(1) :]):
            continue  # "2 hours" is a duration
        if not m[2] and not ap and not re.match(r"(?:at|till|until|by)\s", m[0], re.I):
            continue  # a bare number isn't a time
        if stale(text, m.start(1)) != past:
            continue  # "since I didn't wake up at 12": not when you want anything
        return m
    return None


def stale_time(text: str) -> str | None:
    """The time only a past or negated clause mentions ("12" in "I didn't wake up at 12"), or None. A request whose
    only time is one of these asks when, instead of acting on it."""
    m = _time_match(text, past=True)
    return re.sub(r"^(?:at|till|until|by)\s+", "", m[0].strip(), flags=re.I) if m else None


def up_now(text: str) -> bool:
    """ "I'm awake", "I just woke up", "I'm up" (also with "call me if you need to …"): up now, nothing else asked
    for at a time, not "I'm still up" or "don't call", and not "I just woke up, reschedule my day" (Agent plan)."""
    if not AWAKE.search(text) or STILL_UP.search(text) or NEG.search(text) or ALSO.search(text) or REPLAN.search(text):
        return False
    return not (another_day(text) or _time_match(text) or re.search(r"\bin\s+(?:\d|an?\b|half\b)", text, re.I))


def _written_24h(m: re.Match) -> bool:
    """'04:30', '09', '10:15', '21:00': a leading zero, or a two-digit hour with minutes, and no am/pm."""
    return not m[3] and len(m[1]) == 2 and (m[1].startswith("0") or bool(m[2]))


def as_written(text: str) -> bool:
    """The time in the text is a 24-hour time ('04:30', '10:15'), taken as written (never moved to pm)."""
    m = _time_match(text)
    return bool(m) and _written_24h(m)


def a_time(text: str, base: dt.datetime | None = None) -> str | None:
    """'at 9:30', 'till 6', '9 pm', 'at 21:00' -> 'HH:MM'. A 24-hour time ('04:30', '10:15') is as written.
    Otherwise, without am/pm: 1-5 and evening words mean pm; morning, midday and 'tomorrow' keep the hour as said;
    otherwise it's the next time the clock shows it."""
    base = base or now()
    m = _time_match(text)
    if m:
        h, mi, ap = int(m[1]), int(m[2] or 0), (m[3] or "").lower()
        if ap == "pm" and h < 12:
            h += 12
        elif ap == "am" and h == 12:
            h = 0
        elif not ap and 1 <= h < 12 and not _written_24h(m):
            if h <= 5 or re.search(r"\b(tonight|evening|night|afternoon|pm)\b", text, re.I):
                h += 12
            elif not re.search(r"\b(morning|tomorrow|midday|noon|lunch)\b", text, re.I):
                if (h, mi) <= (base.hour, base.minute) < (h + 12, mi):
                    h += 12
        return f"{h:02d}:{mi:02d}"
    return None


def a_minutes(text: str) -> int | None:
    low = text.lower()
    if re.search(r"\bhour and a half\b", low):
        return 90
    if re.search(r"\bhalf an? hour\b", low):
        return 30
    if re.search(r"\b(an|one) hour\b", low):
        return 60
    m = DUR.search(text)
    if not m:
        return None
    n = float(m[1])
    return int(n * 60) if m[2].lower().startswith("h") else int(n)


def when_from(text: str, base: dt.datetime | None = None) -> dt.datetime | None:
    """A moment from plain English: "in 20 min", "at 9", "tomorrow at 7", "tonight", "friday at 5pm" (the coming
    Friday; today's if that time is still ahead, else a week on). None if there isn't one, or for "next Friday" (this
    week's or the one after: left to the AI)."""
    base = base or now()
    low = text.lower()
    mins = a_minutes(text)
    if mins and re.search(r"\bin\s+(?:\d|an?\b|half\b|one\b)", low):
        return base + dt.timedelta(minutes=mins)
    tm = a_time(text, base)
    wd = WHEN_DAY.search(text)
    if wd or re.search(r"\bday after tomorrow\b", low):
        if wd and wd["next"]:
            return None
        day = (
            base.date() + dt.timedelta(days=(WEEKDAYS.index((wd["d1"] or wd["d2"]).lower()) - base.weekday()) % 7)
            if wd
            else base.date() + dt.timedelta(days=2)
        )
        h, mi = map(int, tm.split(":")) if tm else (9, 0)
        t = dt.datetime.combine(day, dt.time(h, mi))
        return t if t > base else t + dt.timedelta(days=7)
    if tm:
        h, mi = map(int, tm.split(":"))
        if "tomorrow" in low:
            return dt.datetime.combine(base.date() + dt.timedelta(days=1), dt.time(h, mi))
        t = base.replace(hour=h, minute=mi, second=0, microsecond=0)
        return t if t > base else t + dt.timedelta(days=1)
    if "tomorrow" in low:
        return dt.datetime.combine(base.date() + dt.timedelta(days=1), dt.time(9, 0))
    if "tonight" in low:
        return dt.datetime.combine(base.date(), dt.time(21, 0))
    return None

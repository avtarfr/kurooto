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


def tidy(text: str) -> str:
    return THANKS.sub("", text.strip())


def too_complex(text: str) -> bool:
    """Long, or several requests in one message: the AI should read the whole thing."""
    return not text or len(text) > 300 or text.startswith("/") or bool(MULTI.search(text))


def a_time(text: str, base: dt.datetime | None = None) -> str | None:
    """'at 9:30', 'till 6', '9 pm', 'at 21:00' -> 'HH:MM'. Without am/pm: 1-5 and evening words mean pm; morning,
    midday and 'tomorrow' keep the hour as said; otherwise it's the next time the clock shows it."""
    base = base or now()
    for m in TIME.finditer(text):
        h, mi, ap = int(m[1]), int(m[2] or 0), (m[3] or "").lower()
        if h > 23 or mi > 59:
            continue
        if not m[2] and DUR.match(text[m.start(1) :]):
            continue  # "2 hours" is a duration
        if not m[2] and not ap and not re.match(r"(?:at|till|until|by)\s", m[0], re.I):
            continue  # a bare number isn't a time
        if ap == "pm" and h < 12:
            h += 12
        elif ap == "am" and h == 12:
            h = 0
        elif not ap and 1 <= h < 12:
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
    """A moment from plain English: "in 20 min", "at 9", "tomorrow at 7", "tonight". None if there isn't one."""
    base = base or now()
    low = text.lower()
    mins = a_minutes(text)
    if mins and re.search(r"\bin\s+(?:\d|an?\b|half\b|one\b)", low):
        return base + dt.timedelta(minutes=mins)
    tm = a_time(text, base)
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

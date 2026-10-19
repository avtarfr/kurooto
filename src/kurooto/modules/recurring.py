"""Recurring quizzes and tests: a small table in your notes (kurooto/recurring.md) that you can edit like any note.
Each row is something that repeats: "Linear Algebra, Quiz, every week, Thursday 10:00". The deadline radar turns the
rows into dated items, so exam mode, quiz offers and reminders follow from them.

| Subject | What | Every (weeks) | Day | Time | Next | Until |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| linear-algebra | Quiz | 1 | Thu | 10:00 | 2026-10-22 | |

"Every" is in weeks (1, 2, or words like "weekly", "every other week"). "Next" is any date it happens on (needed when
it's every two weeks, so Kurooto knows which week); "Until" is optional. Empty Day or Time: Kurooto uses the subject's
class from your timetable, or asks you.

This file only reads and writes the table; the Deadlines feature uses it.
"""

from __future__ import annotations

import datetime as dt
import re

NOTE = "kurooto/recurring.md"
HEAD = "| Subject | What | Every (weeks) | Day | Time | Next | Until |"
SEP = "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DAY_WORDS = re.compile(r"\b(mon|tue|wed|thu|fri|sat|sun)(?:day|sday|nesday|rsday|urday|rs|r|s)?s?\b", re.I)
TWO = re.compile(
    r"\b(?:every (?:other|second|alternate|2(?:nd)?|two)\b|every 2 ?weeks|fortnight(?:ly)?|bi-?weekly|alternate)", re.I
)
ONE = re.compile(r"\b(?:every|weekly|each)\b", re.I)
WHAT = re.compile(
    r"\b(quiz(?:zes)?|class tests?|tests?|assessments?|exams?|vivas?|lab tests?|worksheets?|problem sheets?|"
    r"homeworks?|assignments?|problem sets?)\b",
    re.I,
)


def weeks(text: str) -> int:
    """'1', '2', 'weekly', 'every other week', 'fortnightly' -> weeks between occurrences (1 if unreadable)."""
    t = (text or "").strip().lower()
    m = re.search(r"\d+", t)
    if m:
        return max(1, min(8, int(m[0])))
    return 2 if TWO.search(t) or re.search(r"\b(other|second|biweekly|fortnight)", t) else 1


def day_of(text: str) -> str:
    m = DAY_WORDS.search(text or "")
    return m[1].lower() if m else ""


def hhmm(text: str) -> str:
    m = re.fullmatch(r"\s*(\d{1,2}):(\d{2})\s*", text or "")
    return f"{int(m[1]):02d}:{m[2]}" if m and int(m[1]) < 24 and int(m[2]) < 60 else ""


def parse(text: str) -> list[dict]:
    """The table's rows: subject, what, every, day, time, next, until (empty strings when not given), line."""
    out = []
    for ln in (text or "").splitlines():
        s = ln.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) < 2 or cells[0].lower() == "subject" or not "".join(cells).strip(":- "):
            continue
        cells += [""] * (7 - len(cells))
        if not cells[0]:
            continue
        nxt = cells[5] if re.fullmatch(r"\d{4}-\d{2}-\d{2}", cells[5]) else ""
        out.append(
            {
                "subject": cells[0],
                "what": cells[1] or "Quiz",
                "every": weeks(cells[2]),
                "day": day_of(cells[3]) or (DAYS[dt.date.fromisoformat(nxt).weekday()] if nxt else ""),
                "time": hhmm(cells[4]),
                "next": nxt,
                "until": cells[6] if re.fullmatch(r"\d{4}-\d{2}-\d{2}", cells[6]) else "",
                "line": ln,
            }
        )
    return out


def first_on(day: str, start: dt.date) -> dt.date:
    """The first date on or after `start` that falls on `day` ("thu")."""
    return start + dt.timedelta(days=(DAYS.index(day) - start.weekday()) % 7)


def dates(row: dict, today: dt.date, horizon_days: int, holidays: list[str] | None = None) -> list[dt.date]:
    """The row's dates from today up to the horizon (or its Until), holidays left out. [] when the day isn't known
    (or it's every few weeks with no Next date: then which week is unknown)."""
    if not row.get("day") and not row.get("next"):
        return []
    step = dt.timedelta(weeks=row.get("every") or 1)
    if row.get("next"):
        d = dt.date.fromisoformat(row["next"])
    elif (row.get("every") or 1) == 1:
        d = first_on(row["day"], today)
    else:
        return []
    if d < today:
        d += step * -(-(today - d).days // step.days)  # the first one on or after today
    end = today + dt.timedelta(days=horizon_days)
    if row.get("until"):
        end = min(end, dt.date.fromisoformat(row["until"]))
    out, skip = [], set(holidays or [])
    while d <= end:
        if d.isoformat() not in skip:
            out.append(d)
        d += step
    return out


def line(row: dict) -> str:
    day = row.get("day", "")
    return (
        f"| {row['subject']} | {row.get('what') or 'Quiz'} | {row.get('every') or 1} | {day.title()} | "
        f"{row.get('time', '')} | {row.get('next', '')} | {row.get('until', '')} |"
    )


def new_note(made_by: str, today: dt.date) -> str:
    return (
        f"---\nmade_by: {made_by}\ndate: {today.isoformat()}\n---\n\n# Recurring quizzes and tests\n\n"
        f"Things that repeat. {made_by} turns each row into dated deadlines (exam mode, quiz offers and reminders "
        'follow). Edit freely: "Every" is in weeks; "Next" is any date it happens on (needed for every two weeks); '
        '"Until" is optional.\n\n' + HEAD + "\n" + SEP + "\n"
    )


def insert(text: str, row_line: str) -> str:
    """The note with a row added at the end of its table (a table is added at the end if there isn't one). Nothing
    else in the note changes."""
    lines = text.split("\n")
    head = next((k for k, ln in enumerate(lines) if ln.strip().lower().startswith("| subject")), None)
    if head is None:
        return text.rstrip("\n") + "\n\n" + HEAD + "\n" + SEP + "\n" + row_line + "\n"
    end = head
    while end + 1 < len(lines) and lines[end + 1].strip().startswith("|"):
        end += 1
    lines.insert(end + 1, row_line)
    return "\n".join(lines)


def remove(text: str, row_line: str) -> str:
    """The note without that one row."""
    lines = text.split("\n")
    for k, ln in enumerate(lines):
        if ln == row_line:
            del lines[k]
            break
    return "\n".join(lines)


def read_rule(text: str) -> dict | None:
    """'a quiz every other thursday at 10', 'weekly test on fridays' -> {what, every, day, time} (day and time may be
    empty), or None if nothing in it repeats."""
    if TWO.search(text):
        every = 2
    elif ONE.search(text):
        every = 1
    else:
        return None
    m = WHAT.search(text)
    what = m[1] if m else "Quiz"
    what = what[:1].upper() + what[1:].lower()
    what = what[:-3] if what.endswith("zes") else what[:-1] if what.endswith("s") else what
    tm = re.search(
        r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b|\bat\s+(\d{1,2})(?::(\d{2}))?\b|\b(\d{1,2}):(\d{2})\b", text, re.I
    )
    time = ""
    if tm:
        h, mi, ap = (tm[1], tm[2], tm[3]) if tm[1] else (tm[4], tm[5], "") if tm[4] else (tm[6], tm[7], "")
        hour = int(h) % 12 + (12 if (ap or "").lower() == "pm" else 0) if ap else int(h)
        if not ap and tm[4] and 1 <= hour <= 7:
            hour += 12  # "at 3" for a class: the afternoon
        if hour < 24 and int(mi or 0) < 60:
            time = f"{hour:02d}:{int(mi or 0):02d}"
    nxt = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
    return {"what": what, "every": every, "day": day_of(text), "time": time, "next": nxt[1] if nxt else ""}

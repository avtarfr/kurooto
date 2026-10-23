"""Dates offered with a button each: what Photo to dates (modules/photodates.py), Email in (modules/google_mail.py),
a shared class calendar (modules/calendar.py) and a project's repository (core/repoproject.py, its dated milestones)
found. Nothing is added until you tap:

- a deadline or an exam goes into Deadlines (its source: photo, mail or shared-calendar);
- an event becomes a reminder, date_offers.remind_min before it (08:00 that day when it has no time);
- a timetable's classes go into your timetable (Subjects), with subjects added for courses you don't have yet.

    batch = dateoffers.make(app, "photo", items, classes)        # None when there's nothing to offer
    text, buttons = dateoffers.message(app, batch, "In that photo:")

Buttons: "dof:<batch>:<n>" adds item n, ":all" every open one, ":none" leaves them, ":tt" adds the classes.
"""

from __future__ import annotations

import datetime as dt
import re
import uuid
from typing import TYPE_CHECKING

from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.lock import Lock
from kurooto.core.state import jload, jsave

if TYPE_CHECKING:
    from kurooto.app import App

register_defaults(
    "date_offers",
    {
        "remind_min": 60,  # an event you tap Add on (a photo, mail, a shared calendar): reminded this long before
    },
)
TYPES = ("deadline", "exam", "event")
DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
KEEP = 100  # batches kept (the newest)
SHOWN = 10  # items with a button each, at most
SOURCES = {"photo": "photo", "mail": "mail", "calendar": "shared-calendar", "repo": "repository"}  # repo: milestones


def _dir(app: App):
    return app.paths.state / "date-offers"


def _hm(v) -> str:
    m = re.fullmatch(r"\s*(\d{1,2})[:.](\d{2})\s*", str(v or ""))
    if not m or int(m[1]) > 23 or int(m[2]) > 59:
        return ""
    return f"{int(m[1]):02d}:{m[2]}"


def clean_items(raw, today: dt.date | None = None) -> list[dict]:
    """The dated items an AI (or a calendar) found, checked: a title, a real date (not before yesterday), a time or
    "", a type (deadline, exam or event). Repeats are dropped."""
    today = today or now().date()
    out, seen = [], set()
    for r in raw if isinstance(raw, list) else []:
        if not isinstance(r, dict):
            continue
        title = re.sub(r"\s+", " ", str(r.get("title") or "")).strip()[:120]
        try:
            day = dt.date.fromisoformat(str(r.get("date") or "").strip()[:10])
        except ValueError:
            continue
        if not title or day < today - dt.timedelta(days=1):
            continue
        kind = str(r.get("type") or "").lower().strip()
        kind = kind if kind in TYPES else "deadline"
        item = {"title": title, "date": day.isoformat(), "time": _hm(r.get("time")), "type": kind}
        where = re.sub(r"\s+", " ", str(r.get("where") or "")).strip()[:80]
        if where:
            item["where"] = where
        key = (title.lower(), item["date"])
        if key not in seen:
            seen.add(key)
            out.append(item)
    return sorted(out, key=lambda x: (x["date"], x["time"] or "99"))


def clean_classes(raw) -> list[dict]:
    """A timetable's weekly classes, checked: a course name, a day (mon..sun), a start before its end."""
    out, seen = [], set()
    for r in raw if isinstance(raw, list) else []:
        if not isinstance(r, dict):
            continue
        name = re.sub(r"\s+", " ", str(r.get("subject") or "")).strip()[:80]
        day = str(r.get("day") or "").lower().strip()[:3]
        start, end = _hm(r.get("start")), _hm(r.get("end"))
        if not name or day not in DAYS or not start or not end or end <= start:
            continue
        if (day, start) not in seen:
            seen.add((day, start))
            out.append({"subject": name, "day": day, "start": start, "end": end})
    return sorted(out, key=lambda c: (DAYS.index(c["day"]), c["start"]))


def make(app: App, source: str, items: list[dict], classes: list[dict] | None = None, about: str = "") -> str | None:
    """Keep what was found, to be offered; its id, or None when there's nothing. source: photo, mail or calendar.
    about: where it came from, shown in the message (a mail's subject, a calendar's name)."""
    if not items and not classes:
        return None
    bid = uuid.uuid4().hex[:8]
    d = _dir(app)
    with Lock(app.paths.state, "date-offers"):
        jsave(
            d / f"{bid}.json",
            {
                "id": bid,
                "source": source,
                "about": about[:120],
                "at": now().isoformat(),
                "items": [{**it, "status": "open"} for it in items],
                "classes": list(classes or []),
                "classes_status": "open" if classes else "",
            },
        )
        for old in sorted(d.glob("*.json"), key=lambda p: p.stat().st_mtime)[:-KEEP]:
            old.unlink(missing_ok=True)
    app.events.emit("dates_offered", source=source, items=len(items), classes=len(classes or []))
    return bid


def load(app: App, bid: str) -> dict | None:
    return jload(_dir(app) / f"{re.sub(r'[^a-f0-9]', '', bid)}.json", None)


def when_text(it: dict) -> str:
    d = dt.date.fromisoformat(it["date"])
    return f"{d:%a %d %b}" + (f" {it['time']}" if it.get("time") else "")


def label(it: dict) -> str:
    """A button's words: "Add: Quiz 2 · Fri 31 Oct" (Telegram shows about 40 characters)."""
    t = it["title"] if len(it["title"]) <= 26 else it["title"][:25] + "…"
    return f"Add: {t} · {when_text(it)}"


def message(app: App, bid: str, intro: str) -> tuple[str, list]:
    """The message offering a batch: one line and one Add button per item (at most SHOWN), Add all and None of these
    when there are several, and one button for a timetable's classes."""
    b = load(app, bid) or {}
    items = b.get("items") or []
    lines = [intro]
    buttons: list = []
    for n, it in enumerate(items[:SHOWN]):
        kind = {"exam": " (exam)", "event": " (event)"}.get(it["type"], "")
        where = f", {it['where']}" if it.get("where") else ""
        lines.append(f"- {it['title']}: {when_text(it)}{where}{kind}")
        buttons.append([(label(it), f"dof:{bid}:{n}")])
    if len(items) > SHOWN:
        lines.append(f"(and {len(items) - SHOWN} more; Add all takes them too)")
    classes = b.get("classes") or []
    if classes:
        lines.append(f"A weekly timetable: {len(classes)} classes.")
        lines += [f"- {c['day'].title()} {c['start']}–{c['end']} {c['subject']}" for c in classes[:30]]
        buttons.append([(f"Add {len(classes)} classes to my timetable", f"dof:{bid}:tt")])
    if len(items) > 1:
        buttons.append([("Add all", f"dof:{bid}:all"), ("None of these", f"dof:{bid}:none")])
    elif items or classes:
        buttons.append([("None of these", f"dof:{bid}:none")])
    lines.append("Nothing is added until you tap.")
    return "\n".join(lines), buttons


# ------------------------------------------------------------------------------------------------ the buttons
def button(app: App, ref: str, act: str) -> str:
    with Lock(app.paths.state, "date-offers"):
        b = load(app, ref)
        if b is None:
            return "Those dates are gone (only the newest 100 are kept)."
        items = b.get("items") or []
        if act == "none":
            for it in items:
                if it["status"] == "open":
                    it["status"] = "left"
            if b.get("classes_status") == "open":
                b["classes_status"] = "left"
            out = "Left out."
        elif act == "tt":
            if b.get("classes_status") != "open":
                return "Those classes are settled already."
            out, ok = add_classes(app, b.get("classes") or [])
            if ok:
                b["classes_status"] = "added"
        elif act == "all":
            said = []
            for it in items:
                if it["status"] == "open":
                    msg, ok = add_item(app, it, b.get("source", ""))
                    said.append(msg)
                    if ok:
                        it["status"] = "added"
            out = "\n".join(said) or "They're all settled already."
        elif act.isdigit() and int(act) < len(items):
            it = items[int(act)]
            if it["status"] != "open":
                return f"{it['title']}: settled already."
            out, ok = add_item(app, it, b.get("source", ""))
            if ok:
                it["status"] = "added"
        else:
            return "That button is out of date."
        jsave(_dir(app) / f"{b['id']}.json", b)
    app.events.emit("dates_tapped", source=b.get("source", ""), act=act if not act.isdigit() else "one")
    return out


def add_item(app: App, it: dict, source: str) -> tuple[str, bool]:
    """Add one tapped item: a deadline or exam into Deadlines, an event as a reminder. (what was said, added?)"""
    day = dt.date.fromisoformat(it["date"])
    hm = it.get("time") or ""
    at = dt.datetime.combine(day, dt.time(int(hm[:2]), int(hm[3:]))) if hm else None
    if it["type"] == "event":
        rem = app.modules.get("reminders") if app.is_on("reminders") else None
        if rem is None:
            return f"{it['title']}: Reminders is off, so I can't remind you of it (Features → Reminders).", False
        start = at or dt.datetime.combine(day, dt.time(8, 0))
        if start < now():
            return f"{it['title']}: that's already past.", False
        when = start - dt.timedelta(minutes=int(app.settings.get("date_offers.remind_min") or 0)) if at else start
        when = max(when, now() + dt.timedelta(minutes=1))
        what = it["title"] + (f" at {hm}" if hm else "") + (f" ({it['where']})" if it.get("where") else "")
        return rem.add(when, what), True
    dl = app.modules.get("deadlines") if app.is_on("deadlines") else None
    if dl is None:
        return f"{it['title']}: Deadlines is off; turn it on to add dates (Features → Deadlines).", False
    due = at or dt.datetime.combine(day, dt.time(23, 59))
    kind = "exam" if it["type"] == "exam" else "task"
    return dl.add(it["title"], due, source=SOURCES.get(source, source or "photo"), kind=kind), True


def add_classes(app: App, classes: list[dict]) -> tuple[str, bool]:
    """A timetable's classes into yours: each course found by name (a new subject when there's none), each class
    added unless one already starts then. (what was said, added?)"""
    subj = app.modules.get("subjects") if app.is_on("subjects") else None
    if subj is None:
        return "Subjects is off; turn it on to keep a timetable (Features → Subjects).", False
    from kurooto.modules.subjects import slugify

    mine = list(app.settings.get("subjects.timetable") or [])
    have = {(c["day"], c["start"]) for c in subj.timetable()}
    listed = list(app.settings.get("subjects.list") or [])
    added, kept, new_subjects = 0, 0, []
    for c in classes:
        slug = subj.resolve(c["subject"])
        if not slug:
            slug = slugify(c["subject"])
            if slug and not any(s.get("slug") == slug for s in listed):
                listed.append({"name": c["subject"], "slug": slug, "aliases": []})
                new_subjects.append(c["subject"])
                app.settings.set("subjects.list", listed)
        if not slug:
            continue
        if (c["day"], c["start"]) in have:
            kept += 1
            continue
        have.add((c["day"], c["start"]))
        mine.append({"day": c["day"], "start": c["start"], "end": c["end"], "subject": slug})
        added += 1
    app.settings.set("subjects.timetable", mine)
    app.events.emit("timetable_from_photo", added=added, subjects=len(new_subjects))
    out = f"Added {added} classes to your timetable (/classes lists it)."
    if kept:
        out += f" {kept} were left out: a class already starts then."
    if new_subjects:
        out += f" New subjects: {', '.join(new_subjects)} (/subject add Name (short) gives one a short name)."
    return out, True

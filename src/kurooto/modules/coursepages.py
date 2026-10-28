"""Course pages for the notes brain (gbrain.course_pages, on, with Notes brain on): each night every subject's course
page gets one block of Kurooto's own (<!-- kurooto:course-overview -->), so the brain (and your AI through it) sees a
course as one page, with its timeline:

    Classes      the weekly timetable's slots for it
    Key concepts the concept notes the course's own notes link to most (and the ones in its folder), up to 10
    Timeline     dated lines in the brain's timeline format ("- **2026-10-20** | lecture — [[...]]"): its lecture
                 notes, its deadlines (done ones too, 120 days back and ahead) and the term note's key dates for it;
                 with gbrain.course_announcements (0.9.0), its Classroom posts (what Classroom keeps of them: the
                 time and title) and the dated lines under "## Announcements" in the course page (the mail digest
                 writes those, after its own filters: confidential mail is never read, personal mail only counted)

Rules only, nothing leaves the computer. Only the block is written (core/graphwrite.py: a write that would change any
text outside it is refused); a course page that isn't there yet is made (the same header the other features give
it). A subject with nothing to show gets no page. /timeline <course page> shows the timeline after the brain's next
nightly timelines pass.
"""

from __future__ import annotations

import datetime as dt
import re
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto.core import conceptgraph as cg
from kurooto.core import graphwrite as gw
from kurooto.core import layout
from kurooto.core.clock import now

if TYPE_CHECKING:
    from kurooto.app import App

KEY = "course-overview"
CONCEPTS_MAX = 10
EVENTS_MAX = 40
WINDOW_DAYS = 120
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
LECTURE = re.compile(r"^(\d{4}-\d{2}-\d{2})-.+\.md$")
ANNOUNCED = re.compile(r"^\s*[-*]\s+(\d{4}-\d{2}-\d{2})\s*[:—-]\s*(\S.*)$")  # "- 2026-10-20: lab moved to Friday"


def _rel(root: Path, f: Path) -> str:
    return f.relative_to(root).with_suffix("").as_posix()


def own_pages(app: App, slug: str) -> set[Path]:
    """A subject's own pages, which aren't concepts: its course page, class log, exam prep and doubts."""
    lay = layout.of(app)
    return {lay.path(k, subject=slug) for k in ("course", "class_log", "exam_prep", "doubts")}


def key_concepts(app: App, slug: str, notes: list[Path], concepts: dict[str, cg.Note], folder: Path) -> list[str]:
    """The concept notes the course's notes link to most; a concept note in the course's own folder counts once."""
    root = Path(app.workspace)
    mine = own_pages(app, slug)
    concepts = {k: c for k, c in concepts.items() if c.path not in mine and not LECTURE.match(c.path.name)}
    count: Counter = Counter()
    for f in notes:
        n = cg.read_note(root, f)
        if n is None:
            continue
        for t in n.links:
            if t in concepts and t != n.slug:
                count[t] += 1
    for c in concepts.values():
        if folder in c.path.parents:
            count[c.slug] += 1
    ranked = sorted(count.items(), key=lambda kv: (-kv[1], concepts[kv[0]].title.lower()))
    return [f"- [[{s}|{concepts[s].title}]]" for s, _n in ranked[:CONCEPTS_MAX]]


def events(app: App, slug: str, lectures: list[Path]) -> list[tuple[str, str]]:
    """(date, line) for the timeline, oldest first."""
    root = Path(app.workspace)
    today = now().date()
    lo, hi = today - dt.timedelta(days=WINDOW_DAYS), today + dt.timedelta(days=WINDOW_DAYS)
    out: list[tuple[str, str]] = []
    for f in lectures:
        day = LECTURE.match(f.name)[1]
        n = cg.read_note(root, f)
        title = n.title if n else f.stem[11:].replace("-", " ")
        out.append((day, f"- **{day}** | lecture — [[{_rel(root, f)}|{title}]]"))
    due_days = set()
    dl = app.modules.get("deadlines")
    if dl is not None and app.is_on("deadlines"):
        for it in dl.items().values():
            if it.get("subject") != slug:
                continue
            try:
                due = dt.datetime.fromisoformat(str(it["due"])[:19])
            except (KeyError, ValueError):
                continue
            if not lo <= due.date() <= hi:
                continue
            what = {"exam": "exam"}.get(it.get("kind"), "deadline")
            done = " (done)" if it.get("status") == "done" else ""
            at = f" at {due:%H:%M}" if due.time() != dt.time(0) else ""
            title = re.sub(r"\s+", " ", str(it.get("title") or "")).strip()
            out.append((due.date().isoformat(), f"- **{due.date().isoformat()}** | {what} — {title}{at}{done}"))
            due_days.add(due.date().isoformat())
    subj = app.modules.get("subjects")
    for d in subj.key_dates() if subj is not None else []:
        if d.get("subject") != slug or d.get("kind") in ("holiday", "term_end") or d.get("from") in due_days:
            continue
        try:
            day = dt.date.fromisoformat(str(d["from"]))
        except (KeyError, ValueError):
            continue
        if lo <= day <= hi:
            what = re.sub(r"\s+", " ", str(d.get("what") or "")).strip()
            out.append((day.isoformat(), f"- **{day.isoformat()}** | term note — {what}"))
    if app.settings.get("gbrain.course_announcements"):
        out += [x for x in announcements(app, slug) if lo.isoformat() <= x[0] <= hi.isoformat()]
    out.sort(key=lambda x: x[0])
    if len(out) > EVENTS_MAX:  # the ones nearest today
        out = sorted(out, key=lambda x: abs((dt.date.fromisoformat(x[0]) - today).days))[:EVENTS_MAX]
        out.sort(key=lambda x: x[0])
    return out


def announcements(app: App, slug: str) -> list[tuple[str, str]]:
    """(date, line) for the course's Classroom posts and its course page's "## Announcements" lines (outside
    Kurooto's own blocks), each once a day and title."""
    out, seen = [], set()
    try:
        from kurooto.modules.google_classroom import _local_day, posts_of

        for p in posts_of(app, slug):
            day = _local_day(str(p.get("at") or ""))
            title = re.sub(r"\s+", " ", str(p.get("title") or "")).strip()[:120]
            if day and title and (day.isoformat(), title.lower()) not in seen:
                seen.add((day.isoformat(), title.lower()))
                out.append((day.isoformat(), f"- **{day.isoformat()}** | announcement — {title}"))
    except Exception as e:  # Classroom's file unreadable: the rest of the page still comes
        app.events.emit("course_pages_failed", error=f"posts: {type(e).__name__}"[:60])
    f = layout.path(app, "course", subject=slug)
    try:
        text = gw.outside(f.read_text(encoding="utf-8")) if f.is_file() else ""
    except (OSError, UnicodeDecodeError):
        text = ""
    section = False
    for line in text.splitlines():
        if line.startswith("## "):
            section = line[3:].strip().lower() == "announcements"
            continue
        m = ANNOUNCED.match(line) if section else None
        if m and (m[1], m[2].strip().lower()) not in seen:
            seen.add((m[1], m[2].strip().lower()))
            out.append((m[1], f"- **{m[1]}** | announcement — {m[2].strip()[:120]}"))
    return out


def body(app: App, s: dict, concepts: dict[str, cg.Note]) -> str:
    slug = s["slug"]
    lay = layout.of(app)
    course = lay.path("course", subject=slug)
    folder = lay.path("subject", subject=slug)
    probe = lay.path("lecture", subject=slug, date="2000-01-01", slug="x")
    lectures = sorted(f for f in probe.parent.glob("*.md") if LECTURE.match(f.name)) if probe.parent.is_dir() else []
    notes = [f for f in folder.rglob("*.md") if f != course] if folder.is_dir() else []
    subj = app.modules["subjects"]
    slots = [c for c in subj.timetable() if c.get("subject") == slug]
    slots.sort(key=lambda c: (DAYS.index(str(c.get("day", "mon"))[:3].lower()) if c.get("day") else 0, c["start"]))
    classes = ", ".join(f"{str(c['day'])[:3].title()} {c['start']}-{c['end']}" for c in slots)
    key = key_concepts(app, slug, [*notes, *([course] if course.is_file() else [])], concepts, folder)
    dated = events(app, slug, lectures)
    if not slots and not key and not dated:
        return ""
    parts = [f"## {s['name']} at a glance", f"Kept up to date by {app.name} each night; the rest of the page is yours."]
    if classes:
        parts.append(f"Classes: {classes}.")
    if key:
        parts.append("### Key concepts\n" + "\n".join(key))
    if dated:
        parts.append("### Timeline\n" + "\n".join(line for _d, line in dated))
    return "\n\n".join(parts)


def write_one(app: App, s: dict, concepts: dict[str, cg.Note]) -> bool:
    """One course page's block; True when the page changed."""
    from kurooto.core.tools import write_note_file

    text = body(app, s, concepts)
    if not text:
        return False
    f = layout.path(app, "course", subject=s["slug"])
    if f.is_file():
        old = f.read_text(encoding="utf-8")
    else:
        old = layout.frontmatter(app, "course", f, title=s["name"], subject=s["slug"]) + f"# {s['name']}\n"
        f.parent.mkdir(parents=True, exist_ok=True)
    new = gw.put_block(old, KEY, text)
    if new == old or (f.is_file() and not gw.guarded(old, new).ok):
        return False
    write_note_file(f, new)
    return True


def write_all(app: App) -> int:
    """Every subject's course page; how many changed."""
    subj = app.modules.get("subjects")
    if subj is None or not app.is_on("subjects"):
        return 0
    concepts = cg.scan(app)
    n = 0
    for s in subj.subjects():
        try:
            n += bool(write_one(app, s, concepts))
        except (OSError, ValueError) as e:  # one page that can't be written never stops the others
            app.events.emit("course_pages_failed", error=f"{type(e).__name__}"[:60])
    app.events.emit("course_pages", changed=n)
    return n


__all__ = ["write_all", "write_one", "body", "KEY"]

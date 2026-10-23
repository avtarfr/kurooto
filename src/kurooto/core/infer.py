"""Setting itself up from what you say: a line in the chat or the journal that states a fact about your work sets up
what it implies, so nothing waits for a settings page. Rules only (no AI, nothing leaves the computer); each change
comes in one line with Undo, and /inferred lists them (/inferred undo <id>).

    "I got a project under Prof Lena Ortiz" / "I've started a project on glacier flow with Dr Okafor"
        -> a project note (research/<slug>/index.md) with "With: Prof Lena Ortiz (supervisor)" and a Meetings section
    "met Ortiz today, we fixed the forcing" (someone a project is With, said in the first person)
        -> a dated line under that project's ## Meetings; a meeting ahead ("meeting with Ortiz friday at 4")
           also becomes a deadline ("Meeting: Prof Lena Ortiz"), so it's planned around and reminded
    "every Monday at 9 I have a Linear Algebra lab" / "I have an LA tutorial every wed at 14:00"
        -> a class in the timetable (for a subject you have; it holds calls), 55 minutes unless the end is said

Never by itself: alarms, calls, mail, anything outward, or a code repository (a project gets code only by /repos add).
Each line is looked at once, wherever it was said (a check-in answer reaches both the chat and the journal).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import re
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.lock import Lock
from kurooto.core.state import jload, jsave

if TYPE_CHECKING:
    from kurooto.app import App

register_defaults(
    "infer",
    {
        "on": True,  # set things up from what you say in the chat and the journal (one line each, with Undo)
        "projects": True,  # "I got a project under Prof X": a project note with them, and a Meetings section
        "meetings": True,  # "met X today": a dated line in that project's Meetings; a meeting ahead: a deadline
        "classes": True,  # "every Monday at 9 I have a <subject> lab": a class in the timetable
    },
)

FILE = "inferred.json"
KEEP = 200  # changes remembered (for /inferred and Undo)
DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
TITLE = r"(?i:prof(?:essor)?\.?|dr\.?|sir|ma'?am|mr\.?|mrs\.?|ms\.?)"
NAME = r"[A-Z][\w'-]+(?:\s+[A-Z][\w'-]+){0,3}"
FIRST = re.compile(r"(?i)\b(?:i|i've|i'd|i'm|we|we've|we're)\b")
NOT = re.compile(r"(?i)\b(?:not|didn't|don't|never|no longer|haven't|hasn't|won't|wasn't|isn't|if|maybe|might)\b")
PROJECT = re.compile(
    r"(?i)\b(?:i|i've|i have|i'm|i am|we|we've)\b[^.!?\n]{0,40}?\b(?:got|get|getting|started|starting|joined|"
    r"joining|took|taken|taking|doing|begun|began|been given|working on|will do|will be doing|have)\b[^.!?\n]{0,40}?"
    r"\bproject\b(?P<rest>[^.!?\n]{0,140})"
)
WITH = re.compile(
    r"\b(?P<how>(?i:under|with|supervised by|guided by|advised by))\s+(?P<title>"
    + TITLE
    + r")?\s*(?P<name>"
    + NAME
    + ")"
)
TOPIC = re.compile(
    r"(?i)^\s*(?:on|about|in)\s+(?P<topic>[^,;]{3,60}?)\s*(?=\b(?:under|with|supervised|guided|advised)\b|$)"
)
TOPIC_AFTER = re.compile(r"(?i)\b(?:on|about)\s+(?P<topic>[^,;]{3,60}?)\s*$")
WITH_LINE = re.compile(r"(?m)^With:\s*(?P<who>.+?)\s*\((?P<role>[^)]+)\)\s*$")
MEET = re.compile(
    r"(?i)\b(?:met|meeting|meet|meets|talked to|talk to|spoke to|spoke with|speak to|discussed with|call with|"
    r"caught up with|catch up with|catching up with)\b"
)
TIME = r"(?:\d{1,2}(?::\d{2})?\s*(?:am|pm)?)"
DAY = r"(?P<day>(?i:mon|tue|wed|thu|fri|sat|sun))[a-z]*s?"
KIND = r"(?P<kind>(?i:class|classes|lab|lecture|tutorial|section|seminar))"
WHAT = r"(?:a\s+|an\s+|my\s+|the\s+|our\s+)?(?P<what>[^.,;!?\n]{2,60}?)"
CLASS = (
    re.compile(
        r"(?i)\bevery\s+" + DAY + r"(?:\s+at)?\s+(?P<s>" + TIME + r")(?:\s*(?:-|–|to)\s*(?P<e>" + TIME + r"))?\s*,?\s*"
        r"(?:i|we)\s+have\s+" + WHAT + r"\s+" + KIND + r"\b"
    ),
    re.compile(
        r"(?i)\b(?:i|we)\s+have\s+" + WHAT + r"\s+" + KIND + r"\s+(?:on\s+)?every\s+" + DAY + r"(?:\s+at)?\s+"
        r"(?P<s>" + TIME + r")(?:\s*(?:-|–|to)\s*(?P<e>" + TIME + r"))?"
    ),
)


def _on(app: App, part: str) -> bool:
    return bool(app.settings.get("infer.on")) and bool(app.settings.get(f"infer.{part}"))


def _load(app: App) -> dict:
    return jload(Path(app.paths.state) / FILE, {"items": [], "seen": []}) or {"items": [], "seen": []}


def _save(app: App, data: dict) -> None:
    data["items"] = data["items"][-KEEP:]
    data["seen"] = data["seen"][-KEEP:]
    jsave(Path(app.paths.state) / FILE, data)


def _key(text: str) -> str:
    return hashlib.sha256(" ".join(text.lower().split()).encode()).hexdigest()[:16]


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]


def _hm(s: str, assume_pm_below: int = 8) -> str | None:
    """'9' -> '09:00', '2pm' -> '14:00', '14:30' -> '14:30'; a bare 1-7 is the afternoon (classes are rarely at 3am)."""
    m = re.fullmatch(r"\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*", s or "", re.I)
    if not m:
        return None
    h, mi, ap = int(m[1]), int(m[2] or 0), (m[3] or "").lower()
    if ap == "pm" and h < 12:
        h += 12
    elif ap == "am" and h == 12:
        h = 0
    elif not ap and 1 <= h < assume_pm_below:
        h += 12
    return f"{h:02d}:{mi:02d}" if 0 <= h < 24 and 0 <= mi < 60 else None


# ------------------------------------------------------------------------------------------- projects
def _person(m: re.Match) -> tuple[str, str]:
    title = (m["title"] or "").strip().rstrip(".")
    title = {"prof": "Prof", "professor": "Prof", "dr": "Dr", "sir": "", "maam": "", "ma'am": "", "mr": "Mr",
             "mrs": "Mrs", "ms": "Ms"}.get(title.lower(), title)  # fmt: skip
    who = f"{title} {m['name']}".strip()
    role = "supervisor" if m["how"].lower() != "with" or title in ("Prof", "Dr") else "with"
    return who, role


def projects_with(app: App) -> list[tuple[Path, str, str]]:
    """Every project note's "With:" people: (note, person, role)."""
    from kurooto.core import layout

    lay = layout.of(app)
    sample = lay.path("project", project="x")
    root = sample.parent.parent
    out = []
    for f in sorted(root.glob("*/" + sample.name)) if root.is_dir() else []:
        try:
            text = f.read_text(encoding="utf-8")
        except OSError:
            continue
        out += [(f, m["who"], m["role"]) for m in WITH_LINE.finditer(text)]
    return out


def _project(app: App, sentence: str) -> dict | None:
    m = PROJECT.search(sentence)
    if not m or NOT.search(sentence[: m.end()]):
        return None
    w = WITH.search(m["rest"])
    if not w:
        return None
    who, role = _person(w)
    if any(who.split()[-1].lower() == p.split()[-1].lower() for _, p, _ in projects_with(app)):
        return None  # already with them
    t = TOPIC.search(m["rest"][: w.start()]) or TOPIC_AFTER.search(m["rest"][w.end() :])
    topic = (t["topic"].strip() if t else "").rstrip(" .")
    name = topic[:1].upper() + topic[1:] if topic else f"Project with {who}"
    from kurooto.modules import research

    note = research.project_note(app, name)
    made = not note.exists()
    research.ensure_project(app, name, assistant=app.name)
    text = note.read_text(encoding="utf-8")
    head = f"# {name}\n"
    line = f"With: {who} ({role})\n"
    if head in text:
        text = text.replace(head, head + "\n" + line, 1)
    else:
        text = line + text
    if "## Meetings" not in text:
        text = (
            text.replace("## Log\n", "## Meetings\n\n## Log\n", 1) if "## Log\n" in text else text + "\n## Meetings\n"
        )
    note.write_text(text, encoding="utf-8")
    from kurooto.core import layout

    return {
        "kind": "project",
        "line": f"Started the project note {name} with {who} ({layout.shown(app, note)}); meetings with them go in it.",
        "undo": {"file": str(note), "made": made, "with": line.strip(), "hash": _key(text)},
    }


# ------------------------------------------------------------------------------------------- meetings
def _meeting(app: App, sentence: str) -> dict | None:
    if not MEET.search(sentence) or not FIRST.search(sentence) or NOT.search(sentence):
        return None
    for note, who, _role in projects_with(app):
        last = who.split()[-1]
        if not re.search(rf"(?i)\b{re.escape(last)}\b", sentence):
            continue
        from kurooto.modules.text import when_from

        when = when_from(sentence)
        if when and when > now() + dt.timedelta(minutes=30):  # a meeting ahead: planned around and reminded
            dl = app.modules.get("deadlines")
            if dl is None or not app.is_on("deadlines"):
                return None
            title = f"Meeting: {who}"
            dl.add(title, when, source="inferred", kind="task")
            return {
                "kind": "meeting_ahead",
                "line": f"Added {title} on {when:%a %d %b %H:%M} to your deadlines.",
                "undo": {"deadline": title, "due": when.isoformat()},
            }
        line = f"- {now():%Y-%m-%d}: {' '.join(sentence.split())[:300]}"
        text = note.read_text(encoding="utf-8")
        if line in text:
            return None
        if "## Meetings\n" in text:
            text = text.replace("## Meetings\n", f"## Meetings\n{line}\n", 1)
        else:
            text = text.rstrip() + f"\n\n## Meetings\n{line}\n"
        note.write_text(text, encoding="utf-8")
        from kurooto.core import layout

        return {
            "kind": "meeting",
            "line": f"Logged a meeting with {who} in {layout.shown(app, note)}.",
            "undo": {"file": str(note), "remove": line},
        }
    return None


# -------------------------------------------------------------------------------------------- classes
def _class(app: App, sentence: str) -> dict | None:
    subj = app.modules.get("subjects")
    if subj is None or not app.is_on("subjects") or NOT.search(sentence):
        return None
    for rx in CLASS:
        m = rx.search(sentence)
        if not m:
            continue
        slug = subj.resolve(m["what"].strip()) or next(iter(subj.find_in(m["what"])), None)
        start = _hm(m["s"])
        if not slug or not start:
            return None
        day = m["day"].lower()[:3]
        end = _hm(m["e"]) if m["e"] else None
        if not end:
            t = dt.datetime.combine(dt.date.today(), dt.time.fromisoformat(start)) + dt.timedelta(minutes=55)
            end = f"{t:%H:%M}"
        if any(c["day"] == day and c["start"] == start for c in subj.timetable()):
            return None  # that slot is known already
        row = {"day": day, "start": start, "end": end, "subject": slug}
        app.settings.set("subjects.timetable", [*(subj.setting("timetable") or []), row])
        kind = m["kind"].lower().rstrip("es") if m["kind"].lower() == "classes" else m["kind"].lower()
        return {
            "kind": "class",
            "line": f"Added {subj.name_of(slug)} {kind} on {day.title()} {start}–{end} to your timetable.",
            "undo": {"class": row},
        }
    return None


# ----------------------------------------------------------------------------------------------- run
def observe(app: App, text: str, via: str = "chat") -> list[str]:
    """Look at something you said (a message, a journal line) once; set up what it states. Returns the lines told."""
    if not text or not app.settings.get("infer.on"):
        return []
    told = []
    with Lock(app.paths.state, "infer", timeout=5):
        data = _load(app)
        for sentence in _sentences(text):
            k = _key(sentence)
            if k in data["seen"] or len(sentence) < 12:
                continue
            data["seen"].append(k)
            for part, fn in (("projects", _project), ("meetings", _meeting), ("classes", _class)):
                if not _on(app, part):
                    continue
                try:
                    got = fn(app, sentence)
                except Exception as e:  # one rule failing must never stop the message it came with
                    app.events.emit("infer_failed", part=part, error=f"{type(e).__name__}: {e}"[:200])
                    continue
                if got:
                    got.update(id=uuid.uuid4().hex[:6], at=time.time(), via=via, undone=False)
                    data["items"].append(got)
                    told.append(got)
                    break
        _save(app, data)
    for got in told:
        app.events.emit("inferred", kind=got["kind"], via=via)
        app.notify(got["line"], kind="info", why="infer.done", buttons=[[("Undo", f"inf:{got['id']}:undo")]])
    return [g["line"] for g in told]


def undo(app: App, iid: str) -> str:
    with Lock(app.paths.state, "infer", timeout=5):
        data = _load(app)
        it = next((x for x in data["items"] if x["id"] == iid), None)
        if it is None:
            return "That change isn't remembered any more."
        if it.get("undone"):
            return "Undone already."
        u = it["undo"]
        if "file" in u and "remove" in u:  # a meeting line
            f = Path(u["file"])
            if f.is_file():
                f.write_text(f.read_text(encoding="utf-8").replace(u["remove"] + "\n", "", 1), encoding="utf-8")
        elif "file" in u:  # a project note
            f = Path(u["file"])
            if f.is_file():
                text = f.read_text(encoding="utf-8")
                if u.get("made") and _key(text) == u.get("hash"):
                    f.unlink()
                else:
                    f.write_text(text.replace(u["with"] + "\n", "", 1), encoding="utf-8")
        elif "class" in u:
            row = u["class"]
            tt = app.settings.get("subjects.timetable") or []
            app.settings.set("subjects.timetable", [c for c in tt if c != row])
        elif "deadline" in u:
            dl = app.modules.get("deadlines")
            if dl is not None:
                for i, d in dl.items().items():
                    if d["title"] == u["deadline"] and d["due"][:16] == u["due"][:16] and d["status"] == "open":
                        dl._button(i, "drop")
        it["undone"] = True
        _save(app, data)
    app.events.emit("inferred_undone", kind=it["kind"])
    return "Undone: " + it["line"]


def command(app: App, arg: str) -> str:
    """/inferred: what was set up from what you said (newest first); /inferred undo <id>."""
    m = re.fullmatch(r"\s*undo\s+(\w+)\s*", arg or "", re.I)
    if m:
        return undo(app, m[1])
    items = [x for x in _load(app)["items"] if not x.get("undone")][-15:]
    if not items:
        on = "on" if app.settings.get("infer.on") else "off (infer.on)"
        return f'Nothing set up from what you said yet ({on}). Say "I got a project under Prof X" and it starts one.'
    rows = [f"[{x['id']}] {dt.datetime.fromtimestamp(x['at']):%d %b} {x['line']}" for x in reversed(items)]
    return "Set up from what you said:\n" + "\n".join(rows) + "\n\n/inferred undo <id> takes one back."

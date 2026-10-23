"""Setting itself up from what you say: a line in the chat or the journal that states a fact about your work sets up
what it implies, so nothing waits for a settings page. Rules only (no AI, nothing leaves the computer); each change
comes in one line with Undo, and /inferred lists them (/inferred undo <id>).

    "I got a project under Prof Lena Ortiz" / "I've started a project on glacier flow with Dr Okafor"
        -> a project note (research/<slug>/index.md) with "With: Prof Lena Ortiz (supervisor)" and a Meetings section
    "met Ortiz today, we fixed the forcing" (someone a project is With, said in the first person)
        -> a dated line under that project's ## Meetings; a meeting ahead ("meeting with Ortiz friday at 4")
           also becomes a deadline ("Meeting: Prof Lena Ortiz"), so it's planned around and reminded
    "I meet my manager Mira Castell every Monday at 10 about onboarding" (any role, in your word)
        -> "With: Mira Castell (manager)" and "Meets: every Mon 10:00" in Kurooto's block of that project's note: a
           brief the evening before each one, and minutes from what you send after it (core/meetings.py)
    "every Monday at 9 I have a Linear Algebra lab" / "I have an LA tutorial every wed at 14:00"
        -> a class in the timetable (for a subject you have; it holds calls), 55 minutes unless the end is said
    "every Tuesday and Thursday at 7pm I go to the gym" / "I work a shift every weekend from 9 to 5"
        -> a commitment (Commitments, turned on if it was off; it holds calls), an hour unless the end is said
    "by POTA I mean Physics of the Atmosphere" / "LA is short for linear algebra" / "I call stochastic calculus stoch"
        -> a short name for that subject, so "POTA quiz friday" lands on it

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
        "aliases": True,  # "by POTA I mean Physics of the Atmosphere": a short name for that subject
        "commitments": True,  # "every Tuesday at 7pm I go to the gym": a commitment (it holds calls like a class)
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
MINUTES = re.compile(r"<!-- kurooto:minutes-(\d{4}-\d{2}-\d{2}) -->\n(.*?)\n<!-- /kurooto:minutes-", re.S)
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
WD = r"(?:mon|tue|wed|thu|fri|sat|sun)[a-z]*"
DAYSET = (
    r"(?P<days>(?i:week\s?days?|weekends?|day|morning|evening|night|" + WD + r"(?:\s*(?:,|and|&|-|to)\s*" + WD + r")*))"
)
SPAN = r"(?:at|from)?\s*(?P<s>" + TIME + r")(?:\s*(?:-|–|to|till|until)\s*(?P<e>" + TIME + r"))?"
ACT = r"(?P<verb>(?i:go to|go for|have|do|attend|work|teach|play|train at|train|volunteer at|volunteer))"
RWHAT = r"(?:\s+(?:a|an|my|the|our)\b)?(?:\s+(?P<what>[A-Za-z][\w' -]{1,30}?))?"
REGULAR = (
    re.compile(
        r"(?i)\bevery\s+"
        + DAYSET
        + r"\s*,?\s*"
        + SPAN
        + r"\s*,?\s*(?:i|we)\s+"
        + ACT
        + RWHAT
        + r"\s*(?=$|[.,;!?]|\b(?:and|but|so|then|ugh)\b)"
    ),
    re.compile(r"(?i)\b(?:i|we)\s+" + ACT + RWHAT + r"\s+(?:on\s+)?every\s+" + DAYSET + r"\s*,?\s*" + SPAN),
)
NOT_REGULAR = re.compile(r"(?i)\b(?:class|classes|lab|lecture|tutorial|seminar|section|exam|quiz|test|deadline)\b")
ABBR = r"[\"'“]?(?P<a>[A-Za-z][\w.&+-]{1,19})[\"'”]?"
SUBJ = r"(?P<n>[^.,;!?\n\"”]{2,60}?)"
ALIAS = (
    re.compile(r"(?i)\bby\s+" + ABBR + r"\s+(?:i|we)\s+mean\s+(?:the\s+)?" + SUBJ + r"\s*(?=$|[.,;!?\"”])"),
    re.compile(
        r"(?i)(?:^|\s)"
        + ABBR
        + r"\s+(?:is short for|stands for|is what i call|is my name for)\s+(?:the\s+)?"
        + SUBJ
        + r"\s*(?=$|[.,;!?\"”])"
    ),
    re.compile(r"(?i)\bi\s+call\s+(?:the\s+)?" + SUBJ + r"\s+" + ABBR + r"\s*(?=$|[.,;!?])"),
)
NOT_ALIAS = {"it", "this", "that", "what", "which", "who", "he", "she", "they", "we", "i", "you", "the", "a", "an"}


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
    from kurooto.core import meetings

    text = meetings.set_fields(note.read_text(encoding="utf-8"), who=who, role=role)  # in Kurooto's block
    line = f"With: {who} ({role})\n"
    if "## Meetings" not in text:
        text = add_section(text, "Meetings")
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
    got = _recurring(app, sentence)
    if got is not None:
        return got or None
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
        from kurooto.core import layout, meetings

        block_before = meetings.block_body(text, meetings.BLOCK)
        text = meetings.set_fields(text, met=f"{now():%Y-%m-%d}")  # "Last met:" in Kurooto's block
        note.write_text(text, encoding="utf-8")
        return {
            "kind": "meeting",
            "line": f"Logged a meeting with {who} in {layout.shown(app, note)}.",
            "undo": {"file": str(note), "remove": line, "block_before": block_before},
        }
    return None


ROLE = r"(?P<role>(?:[A-Za-z]+\s+)?[a-z][a-z-]+)"
PERSON = re.compile(
    r"^(?:(?i:my|our)\s+" + ROLE + r"\s*,?\s+)?(?:(?P<title>" + TITLE + r")\s*)?(?P<name>" + NAME + r")"
    r"(?:\s*,?\s+(?i:about|on|for|to discuss)\s+(?P<topic>[^,;]{3,60}?))?\s*$"
)
TOPIC_REST = re.compile(r"(?i)^\s*,?\s*(?:about|on|for|to discuss)\s+(?P<topic>[^,;]{3,60}?)\s*$")
MDAY = r"(?:mon|tue|wed|thu|fri|sat|sun)[a-z]*"
MDAYS = r"(?P<days>" + MDAY + r"(?:\s*(?:,|and|&)\s*" + MDAY + r")*)"
MSPAN = r"(?:at\s+)?(?P<s>" + TIME + r")"
MVERB = (
    r"(?:meet(?:\s+with)?|see|have\s+(?:a\s+|my\s+|our\s+)?(?:weekly\s+)?(?:meeting|call|catch[- ]up|check[- ]in|"
    r"one[- ]on[- ]one|1:1|sync)\s+with)"
)
RECURRING = (
    re.compile(
        r"(?i:\b(?:i|we)\s+"
        + MVERB
        + r")\s+(?P<person>.+?)\s+(?i:(?:on\s+)?every\s+"
        + MDAYS
        + r"\s*,?\s*"
        + MSPAN
        + r")(?P<rest>[^.!?;]*)"
    ),
    re.compile(
        r"(?i:\bevery\s+" + MDAYS + r"\s*,?\s*" + MSPAN + r"\s*,?\s*(?:i|we)\s+" + MVERB + r")\s+"
        r"(?P<person>[^.,;!?]+)"
    ),
    re.compile(
        r"(?i:\b(?:i|we)\s+have\s+(?:a\s+|my\s+|our\s+)?weekly\s+(?:meeting|call|catch[- ]up|check[- ]in|"
        r"one[- ]on[- ]one|1:1|sync)\s+with)\s+(?P<person>.+?)\s+(?i:on\s+" + MDAYS + r"\s*,?\s*" + MSPAN + r")"
        r"(?P<rest>[^.!?;]*)"
    ),
)


def _recurring(app: App, sentence: str) -> dict | bool | None:
    """ "I meet my manager Priya Rao every Monday at 10": "Meets: every Mon 10:00" (and their "With:" line, when no
    project note has them yet: a new one, "Meetings with Priya Rao") in Kurooto's block of the project note, so the
    evening before each one a brief comes and notes after it become minutes (core/meetings.py). None: not a weekly
    meeting; False: one, but nothing to set up (someone unknown said without a role or title, or known already)."""
    from kurooto.core import layout, meetings
    from kurooto.modules import commitments as rt

    for rx in RECURRING:
        m = rx.search(sentence)
        if not m:
            continue
        days, start = rt.parse_days(m["days"].replace(",", " ")), _hm(m["s"])
        p = PERSON.match(m["person"].strip())
        if not days or not start or not p:
            return False
        title = (p["title"] or "").strip().rstrip(".")
        title = {"prof": "Prof", "professor": "Prof", "dr": "Dr", "mr": "Mr", "mrs": "Mrs", "ms": "Ms"}.get(
            title.lower(), ""
        )
        who = f"{title} {p['name']}".strip()
        role = (p["role"] or "").strip().lower() or None
        hit = next((x for x in projects_with(app) if x[1].split()[-1].lower() == who.split()[-1].lower()), None)
        made = False
        if hit is None:
            if not role and not title:
                return False  # someone you meet, but nothing says who they are to you
            from kurooto.modules import research

            t = p["topic"] or (TOPIC_REST.match(m.groupdict().get("rest") or "") or {"topic": ""})["topic"]
            topic = t.strip().rstrip(" .")
            name = topic[:1].upper() + topic[1:] if topic else f"Meetings with {who}"
            note = research.project_note(app, name)
            made = not note.exists()
            research.ensure_project(app, name, assistant=app.name)
        else:
            note, who = hit[0], hit[1]
        before = note.read_text(encoding="utf-8")
        meets = meetings.meets_text(days, start)
        text = meetings.set_fields(before, who=who, role=role, meets=meets)
        if "## Meetings" not in text:
            text = add_section(text, "Meetings")
        if text == before:
            return False
        note.write_text(text, encoding="utf-8")
        return {
            "kind": "meetings",
            "line": f"You meet {who} {meets}: it's in {layout.shown(app, note)}. The evening before each meeting a "
            "brief comes from it, and notes you send after one become its minutes.",
            "undo": {"file": str(note), "made": made, "note_before": before, "hash": _key(text)},
        }
    return None


def add_section(text: str, name: str) -> str:
    """An empty "## <name>" before "## Log" (else at the end)."""
    return text.replace("## Log\n", f"## {name}\n\n## Log\n", 1) if "## Log\n" in text else text + f"\n## {name}\n"


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


def brief(note: Path, who: str, due: dt.datetime) -> str:
    """A meeting brief from a project note: since the "Last met" date (else two weeks), the Log's dated lines, the
    open "## Next steps" items (yours and the action items from minutes), the last Meetings line and the last
    minutes' summary."""
    from kurooto.core import meetings

    full = note.read_text(encoding="utf-8")
    m = meetings.last_met(full)
    since = m or f"{now().date() - dt.timedelta(days=14):%Y-%m-%d}"
    text = meetings.outside(full)  # the Meetings lines are yours; minutes come from their own blocks below

    def section(name: str) -> list[str]:
        s = re.search(rf"(?ms)^## {name}\n(.*?)(?=^## |\Z)", text)
        return [ln.strip() for ln in s[1].splitlines() if ln.strip().startswith(("-", "*"))] if s else []

    logged = []
    for ln in section("Log"):
        d = re.search(r"\d{4}-\d{2}-\d{2}", ln)
        if d and d[0] >= since:
            logged.append("- " + re.sub(r"\*\*|^[-*]\s*", "", ln)[:200])
    open_steps = re.search(r"(?ms)^## Next steps\n(.*?)(?=^## |\Z)", full)
    steps = [
        "- " + ln.strip()[5:].strip()[:200]
        for ln in (open_steps[1].splitlines() if open_steps else [])
        if ln.strip().startswith(("- [ ]", "* [ ]"))
    ]
    met = section("Meetings")
    minutes = sorted(re.findall(MINUTES, full))
    title = re.search(r"(?m)^# (.+)$", text)
    out = [f"Tomorrow at {due:%H:%M}: meeting with {who}" + (f" ({title[1].strip()})." if title else ".")]
    when = "since you last met" if m else "in the last two weeks"
    out.append(f"Logged {when} ({since}):" if logged else f"Nothing logged {when} ({since}).")
    out += logged[-8:]
    if steps:
        out += ["Open next steps:", *steps[:5]]
    if met:
        out.append("Last time: " + re.sub(r"^[-*]\s*", "", met[0])[:200])
    if minutes:
        day, body = minutes[-1]
        points = [ln[2:].strip() for ln in body.split("\n") if ln.startswith("- ")][:3]
        if points:
            out += [f"From the minutes of {day}:", *("- " + p[:200] for p in points)]
    return "\n".join(out)


# --------------------------------------------------------------------------------------------- aliases
def _alias(app: App, sentence: str) -> dict | None:
    subj = app.modules.get("subjects")
    if subj is None or not app.is_on("subjects") or NOT.search(sentence):
        return None
    for rx in ALIAS:
        m = rx.search(sentence)
        if not m:
            continue
        alias, said = m["a"].strip(".").lower(), m["n"].strip()
        taken = {n.lower() for x in subj.subjects() for n in (x["slug"], x["name"], *x.get("aliases", []))}
        if alias in NOT_ALIAS or alias in taken:
            return None  # a word, or a name that's taken already
        found = subj.find_in(said)
        slug = subj.resolve(said) or (found[0] if len(found) == 1 else None)
        if not slug:
            return None
        items = [dict(x) for x in subj.setting("list") or []]
        mine = next((x for x in items if x["slug"] == slug), None)
        made = mine is None
        if made:  # a subject from the term note or a class pack: yours now holds its short names
            mine = {"name": subj.name_of(slug), "slug": slug, "aliases": []}
            items.append(mine)
        mine["aliases"] = [*mine.get("aliases", []), alias]
        app.settings.set("subjects.list", items)
        return {
            "kind": "alias",
            "line": f'Took "{m["a"].strip(".")}" as {subj.name_of(slug)} from now on.',
            "undo": {"alias": alias, "slug": slug, "made": made},
        }
    return None


# ---------------------------------------------------------------------------------------- commitments
def _commitment(app: App, sentence: str) -> dict | None:
    if NOT.search(sentence) or "commitments" not in app.modules:
        return None
    from kurooto.modules import commitments as rt

    for rx in REGULAR:
        m = rx.search(sentence)
        if not m:
            continue
        what = (m["what"] or "").strip(" -")
        if NOT_REGULAR.search(what):
            return None  # a class or a test: the classes rule or the deadlines, not a commitment
        name = what.lower() or {"work": "work", "train": "training", "volunteer": "volunteering"}.get(
            m["verb"].lower(), ""
        )
        d = re.sub(r"s\b", "", m["days"].lower().replace("week ", "week"))
        days = list(rt.DAYS) if d in ("day", "morning", "evening", "night") else rt.parse_days(d)
        start = _hm(m["s"])
        if not name or not days or not start:
            return None
        end = _hm(m["e"]) if m["e"] else None
        if not end:
            t = dt.datetime.combine(dt.date.today(), dt.time.fromisoformat(start)) + dt.timedelta(hours=1)
            end = f"{t:%H:%M}"
        mod = app.modules["commitments"]
        if any(r["name"].lower() == name for r in mod.items()):
            return None  # known already
        enabled = False
        if not app.is_on("commitments"):
            ok, _why = app.enable("commitments")
            if not ok:
                return None
            enabled = True
        row = mod.add(name, days, start, end)
        return {
            "kind": "commitment",
            "line": f"Added {name} to your commitments: {rt.days_text(days)} {start}–{end}; calls wait while it's on.",
            "undo": {"commitment": row, "enabled": enabled},
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
            if k in data["seen"] or len(sentence) < 12 or sentence.endswith("?"):  # a question states nothing
                continue
            data["seen"].append(k)
            parts = (("projects", _project), ("meetings", _meeting), ("classes", _class), ("aliases", _alias),
                     ("commitments", _commitment))  # fmt: skip
            for part, fn in parts:
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
        if "note_before" in u:  # a weekly meeting: the note as it was, unless it changed since
            f = Path(u["file"])
            if f.is_file():
                if _key(f.read_text(encoding="utf-8")) != u["hash"]:
                    return "That note changed since, so it's left as it is: edit its Meets line yourself."
                if u.get("made"):
                    f.unlink()
                else:
                    f.write_text(u["note_before"], encoding="utf-8")
        elif "file" in u and "remove" in u:  # a meeting line (and the "Last met" it set)
            from kurooto.core import meetings

            f = Path(u["file"])
            if f.is_file():
                text = f.read_text(encoding="utf-8").replace(u["remove"] + "\n", "", 1)
                if "block_before" in u:  # Kurooto's block as it was (0.5.20 on)
                    old = u["block_before"]
                    text = meetings.put(text, meetings.BLOCK, old) if old else meetings.drop(text, meetings.BLOCK)
                if u.get("met"):
                    old = u.get("met_before")
                    text = text.replace(u["met"], old, 1) if old else text.replace(u["met"] + "\n", "", 1)
                f.write_text(text, encoding="utf-8")
        elif "file" in u:  # a project note
            f = Path(u["file"])
            if f.is_file():
                text = f.read_text(encoding="utf-8")
                if u.get("made") and _key(text) == u.get("hash"):
                    f.unlink()
                else:
                    from kurooto.core import meetings

                    text = text.replace(u["with"] + "\n", "", 1)
                    if meetings.block_body(text, meetings.BLOCK) == "":  # the block held only that line
                        text = meetings.drop(text, meetings.BLOCK)
                    f.write_text(text, encoding="utf-8")
        elif "class" in u:
            row = u["class"]
            tt = app.settings.get("subjects.timetable") or []
            app.settings.set("subjects.timetable", [c for c in tt if c != row])
        elif "alias" in u:
            items = []
            for x in app.settings.get("subjects.list") or []:
                if x["slug"] == u["slug"]:
                    x = dict(x, aliases=[a for a in x.get("aliases", []) if a != u["alias"]])
                    if u.get("made") and not x["aliases"]:
                        continue
                items.append(x)
            app.settings.set("subjects.list", items)
        elif "commitment" in u:
            mod = app.modules.get("commitments")
            if mod is not None:
                row = u["commitment"]
                app.settings.set("commitments.items", [r for r in mod.setting("items") or [] if r != row])
                if u.get("enabled") and not mod.items():
                    app.disable("commitments")
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

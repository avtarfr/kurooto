"""Setting itself up from what you say: a line in the chat or the journal that states a fact about your work sets up
what it implies, so nothing waits for a settings page. Rules only (no AI, nothing leaves the computer); each change
comes in one line with Undo, and /inferred lists them (/inferred undo <id>).

    "I got a project under Prof Lena Ortiz" / "I've started a project on glacier flow with Dr Okafor" / "I'm doing my
    thesis under Prof Ana Ruiz" / "I started working with Prof Cole on a project about sea ice" / "my supervisor is
    Dr Ken Ito"
        -> a project note (research/<slug>/index.md) with "With: Prof Lena Ortiz (supervisor)" and a Meetings section
    "met Ortiz today, we fixed the forcing" (someone a project is With, said in the first person)
        -> a dated line under that project's ## Meetings; a meeting ahead ("meeting with Ortiz friday at 4")
           also becomes a deadline ("Meeting: Prof Lena Ortiz"), so it's planned around and reminded
    "I meet my manager Mira Castell every Monday at 10 about onboarding" (any role, in your word)
        -> "With: Mira Castell (manager)" and "Meets: every Mon 10:00" in Kurooto's block of that project's note: a
           brief the evening before each one, and minutes from what you send after it (core/meetings.py)
    "every Monday at 9 I have a Linear Algebra lab" / "I have an LA tutorial every wed at 14:00"
        -> a class in the timetable (for a subject you have; it holds calls), 55 minutes unless the end is said
    "every Tuesday and Thursday at 7pm I go to the gym" / "I work a shift every weekend from 9 to 5" / "gym Tue Thu
    7am" / "I have lab every Thursday 2-5" / "I've got a lab on Mondays at 9" / "I go running every morning at 6"
    (a lab, tutorial or class with no course named; never a meeting or a call with someone)
        -> a commitment (Commitments, turned on if it was off; it holds calls), an hour unless the end is said
    "there's a quiz on Linear Algebra every Monday" / "LA has a test every other Friday from 2026-10-30"
        -> a row in the recurring quizzes table (Deadlines), when the course, the day and (every other week) the date
           are all said; a message that is only that request is the add_recurring request's (it asks what's missing)
    "by POTA I mean Physics of the Atmosphere" / "LA is short for linear algebra" / "I call stochastic calculus stoch"
        -> a short name for that subject, so "POTA quiz friday" lands on it
    "LA problem set" in two messages, when Linear Algebra is the only subject with those initials
        -> "LA" as Linear Algebra's short name (modules/subjects.py counts the uses)

Never by itself: alarms, calls, mail, anything outward, or a code repository (a project gets code only by /repos add).
Each line is looked at once, wherever it was said (a check-in answer reaches both the chat and the journal). A question
("is there a quiz every Monday?", "do I have lab on Thursdays") sets up nothing.

The one pass (infer.sweep, on): what you say is read as it arrives; the pass also reads what didn't come through a
message, your chats with Kurooto and your journal and daily notes as they are in your notes folder. It runs once when
it's first on (the last infer.sweep_days, 30) and then nightly (04:20) on what's new since. Rules first; a line the
rules can't read but that looks like one of these (first person, a project, a supervisor, "every ...", a lab, a short
name) gets one more try with infer.sweep_ai: "local" (the default) asks the model on this computer, when there is one,
to restate it in one of the forms above, using only words from the line itself, and the rules read that; "main" asks
your own AI (only that line goes to it); "off" leaves it to the rules. Everything one pass sets up is told in one line
with Undo all; /inferred lists each with its Undo, /inferred scan runs the pass now.
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
        "quizzes": True,  # "there's a quiz on Linear Algebra every Monday": a row in the recurring quizzes table
        "short_names": True,  # "LA" for Linear Algebra after two messages call it that (it fits only that one)
        "sweep": True,  # one pass over your chats and journal: once when first on, then nightly on what's new
        "sweep_days": 30,  # how far back that first pass reads
        "sweep_ai": "local",  # a line the rules can't read: local (this computer) restates it, main (your AI), off
    },
)

FILE = "inferred.json"
KEEP = 200  # changes remembered (for /inferred and Undo)
SEEN = 5000  # lines remembered as looked at already (a hash each), so a pass never sets up the same thing twice
SWEEP_WHEN = "daily 04:20"
SWEEP_AI_MAX = 10  # lines one pass may ask the AI about
DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
TITLE = r"(?i:prof(?:essor)?\.?|dr\.?|sir|ma'?am|mr\.?|mrs\.?|ms\.?)"
NAME = r"[A-Z][\w'-]+(?:\s+[A-Z][\w'-]+){0,3}"
FIRST = re.compile(r"(?i)\b(?:i|i've|i'd|i'm|we|we've|we're)\b")
ASKS = re.compile(
    r"(?i)^\s*(?:what|when|why|how|who|where|which|(?:do|does|did|can|could|should|would|will|shall|am|is|are|was|"
    r"were|have|has)\s+(?:i|we|you|he|she|they|it|there|my|our|the|a|an)\b)"
)  # a question, with or without its "?" ("do I have lab every Thursday"; not "did 3 LA problems")
NOT = re.compile(r"(?i)\b(?:not|didn't|don't|never|no longer|haven't|hasn't|won't|wasn't|isn't|if|maybe|might)\b")
PROJECT = re.compile(
    r"(?i)\b(?:i|i've|i have|i'm|i am|we|we've)\b[^.!?\n]{0,40}?\b(?:got|get|getting|started|starting|joined|"
    r"joining|took|taken|taking|doing|begun|began|been given|working on|will do|will be doing|have)\b[^.!?\n]{0,40}?"
    r"\b(?P<noun>project|thesis|dissertation)\b(?P<rest>[^.!?\n]{0,140})"
)
SUPERVISOR = re.compile(  # "my supervisor is Dr Ana Ruiz", "my thesis advisor is Prof Ken Ito"
    r"(?i:\bmy\s+(?:(?:project|thesis|phd|research)\s+)?(?P<role>supervisor|guide|advisor|adviser|mentor|pi)\s+"
    r"(?:is|will be)\s+)(?P<title>" + TITLE + r")?\s*(?P<name>" + NAME + ")"
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
ACT = r"(?P<verb>(?i:go to|go for|go|have|do|attend|work|teach|play|train at|train|volunteer at|volunteer))"
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
BARE = {"lab": "lab", "labs": "lab", "tutorial": "tutorial", "tutorials": "tutorial", "seminar": "seminar",
        "seminars": "seminar", "lecture": "lecture", "lectures": "lecture", "section": "section"}  # fmt: skip
AMPM = r"(?:\d{1,2}(?::\d{2})?\s*(?:am|pm)|\d{1,2}:\d{2})"  # a time said plainly enough to stand on its own
TERSE = re.compile(  # "gym Tue Thu 7am", "swimming on saturdays 8am-9am", "standup every weekday 10:00"
    r"(?i)^\s*(?P<what>[a-z][\w' -]{1,30}?)\s+(?P<every>on\s+|every\s+)?(?P<days>week\s?days?|weekends?|"
    + WD
    + r"(?:\s*(?:,|and|&|/)?\s*"
    + WD
    + r")*)\s*,?\s+(?:at\s+|from\s+)?(?P<s>"
    + AMPM
    + r")(?:\s*(?:-|–|to|till|until)\s*(?P<e>"
    + AMPM
    + r"))?\s*[.!]?\s*$"
)
NOT_TERSE = re.compile(
    r"(?i)\b(?:remind|call|ring|wake|alarm|skip|skipping|move|cancel|meet|meeting|due|deadline|exam|quiz|test|"
    r"mail|email|text|send|book|buy|pay)\b"
)  # a request, a deadline or a one-off: not a routine
TERSE_NOT_FIRST = {"every", "each", "on", "at", "from", "i", "we", "you", "he", "she", "they", "my", "our", "and",
                   "also", "so", "it", "this", "that", "next", "last", "see", "till", "until"}  # fmt: skip
QUIZ = re.compile(r"(?i)\b(?:quiz(?:zes)?|class tests?|tests?|vivas?|assessments?|worksheets?)\b")
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
    data["seen"] = data["seen"][-SEEN:]
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
    noun, topic, who = "project", "", ""
    if m and not NOT.search(sentence[: m.end()]):
        noun = m["noun"].lower()
        w = WITH.search(m["rest"])
        t = None
        if w:
            t = TOPIC.search(m["rest"][: w.start()]) or TOPIC_AFTER.search(m["rest"][w.end() :])
        else:  # "I started working with Prof Mira Cole on a project about sea ice": the person before the noun
            w = WITH.search(sentence[m.start() : m.start("noun")])
            t = TOPIC.search(m["rest"]) or TOPIC_AFTER.search(m["rest"])
        if w:
            who, role = _person(w)
            topic = (t["topic"].strip() if t else "").rstrip(" .")
    if not who:  # "my supervisor is Dr Ana Ruiz": a project with them, named after them
        sv = SUPERVISOR.search(sentence)
        if not sv or NOT.search(sentence):
            return None
        title = (sv["title"] or "").strip().rstrip(".")
        title = {"prof": "Prof", "professor": "Prof", "dr": "Dr"}.get(title.lower(), title)
        who = f"{title} {sv['name']}".strip()
        role = {"pi": "supervisor", "guide": "supervisor", "adviser": "advisor"}.get(
            sv["role"].lower(), sv["role"].lower()
        )
    if any(who.split()[-1].lower() == p.split()[-1].lower() for _, p, _ in projects_with(app)):
        return None  # already with them
    name = topic[:1].upper() + topic[1:] if topic else f"{noun.title()} with {who}"
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
def _weekly(sentence: str) -> str:
    """The same sentence said the way the rules read it: "on Mondays" is "every Mondays", "I've got" is "I have"."""
    s = re.sub(r"(?i)\bon\s+(?=(?:mon|tue|wed|thu|fri|sat|sun)[a-z]*s\b)", "every ", sentence)
    return re.sub(r"(?i)\b(i|we)(?:'ve|\s+have)\s+got\b", r"\1 have", s)


def _class(app: App, sentence: str) -> dict | None:
    subj = app.modules.get("subjects")
    if subj is None or not app.is_on("subjects") or NOT.search(sentence):
        return None
    sentence = _weekly(sentence)
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
        return {
            "kind": "alias",
            "line": f'Took "{m["a"].strip(".")}" as {subj.name_of(slug)} from now on.',
            "undo": _add_alias(app, subj, alias, slug),
        }
    return None


def _add_alias(app: App, subj, alias: str, slug: str) -> dict:
    """Add a short name to a subject (a term note's or a class pack's becomes yours to hold it). Returns its undo."""
    items = [dict(x) for x in subj.setting("list") or []]
    mine = next((x for x in items if x["slug"] == slug), None)
    made = mine is None
    if made:  # a subject from the term note or a class pack: yours now holds its short names
        mine = {"name": subj.name_of(slug), "slug": slug, "aliases": []}
        items.append(mine)
    mine["aliases"] = [*mine.get("aliases", []), alias]
    app.settings.set("subjects.list", items)
    return {"alias": alias, "slug": slug, "made": made}


def _short_names(app: App, text: str) -> list[dict]:
    """Short names you've used in two messages for the one subject they fit (modules/subjects.py counts them)."""
    subj = app.modules.get("subjects")
    if subj is None or not app.is_on("subjects"):
        return []
    out = []
    for short, slug in subj.short_names_used(text):
        out.append(
            {
                "kind": "alias",
                "line": f'Took "{short}" as {subj.name_of(slug)} from now on (you\'ve called it that twice).',
                "undo": _add_alias(app, subj, short.lower(), slug),
            }
        )
    return out


# -------------------------------------------------------------------------------------- recurring quizzes
def _request(app: App, text: str) -> bool:
    """Is the whole message a "<subject> has a quiz every <day>" request? Then that request answers it (it asks for
    what's missing), not this."""
    from kurooto.modules.text import tidy, too_complex

    dl = app.modules.get("deadlines")
    plain = tidy(text)
    if dl is None or not app.is_on("deadlines") or too_complex(plain):
        return False
    return any(i.name == "add_recurring" and i.match(plain) is not None for i in dl.intents())


def _quiz(app: App, sentence: str) -> dict | None:
    dl, subj = app.modules.get("deadlines"), app.modules.get("subjects")
    if dl is None or subj is None or not app.is_on("deadlines") or not app.is_on("subjects"):
        return None
    if NOT.search(sentence) or not QUIZ.search(sentence) or re.search(r"(?i)\b(?:remind|call|skip)\b", sentence):
        return None
    from kurooto.modules import recurring

    rule = recurring.read_rule(sentence)
    found = subj.find_in(sentence)
    if not rule or not rule["day"] or (rule["every"] > 1 and not rule["next"]) or len(found) != 1:
        return None  # not sure of the course, the day or the week: the request asks, a passing line doesn't
    if any(r["key"] == f"{found[0]}|{rule['what'].lower()}" for r in dl.recurring_rows()):
        return None  # known already
    out = dl.add_recurring(found[0], rule["what"], rule["every"], rule["day"], rule["time"], rule["next"])
    if out.startswith("One question") or " already in " in out:
        return None
    return {
        "kind": "quiz",
        "line": f"Added to your recurring quizzes ({recurring.note_rel(app)}): {out}",
        "undo": {"recurring": {"subject": found[0], "what": rule["what"]}},
    }


# ---------------------------------------------------------------------------------------- commitments
def _commitment(app: App, sentence: str) -> dict | None:
    if NOT.search(sentence) or MEET.search(sentence) or "commitments" not in app.modules:
        return None  # a meeting or a call with someone is the meetings rule's (a person it knows), never a routine
    sentence = _weekly(sentence)
    from kurooto.modules import commitments as rt

    subj = app.modules.get("subjects") if app.is_on("subjects") else None
    t = TERSE.match(sentence)
    if t:  # "gym Tue Thu 7am": a routine only with two days or more, "every" or "on Tuesdays" (else a one-off)
        what, days = t["what"].strip(" -"), t["days"].lower()
        many = len(re.findall(WD, days)) > 1 or "every" in (t["every"] or "").lower() or re.search(r"days\b", days)
        if not many and "week" not in days or NOT_TERSE.search(what) or len(what.split()) > 3:
            t = None
        elif what.split()[0].lower() in TERSE_NOT_FIRST:
            t = None
        elif subj is not None and subj.find_in(what):
            t = None  # a course's name: a class, said this way it isn't sure enough
    for m in [t] if t else [rx.search(sentence) for rx in REGULAR]:
        if not m:
            continue
        what = (m["what"] or "").strip(" -")
        bare = BARE.get(what.lower()) if not (subj is not None and subj.find_in(sentence)) else None
        if NOT_REGULAR.search(what) and not bare:
            return None  # a class or a test: the classes rule or the deadlines, not a commitment
        verb = m["verb"].lower() if "verb" in m.groupdict() and m["verb"] else ""
        name = bare or what.lower() or {"work": "work", "train": "training", "volunteer": "volunteering"}.get(verb, "")
        d = re.sub(r"s\b", "", m["days"].lower().replace("week ", "week").replace("/", " "))
        days = list(rt.DAYS) if d in ("day", "morning", "evening", "night") else rt.parse_days(d)
        start = _hm(m["s"])
        if not name or not days or not start:
            return None
        end = _hm(m["e"]) if m["e"] else None
        if not end:
            later = dt.datetime.combine(dt.date.today(), dt.time.fromisoformat(start)) + dt.timedelta(hours=1)
            end = f"{later:%H:%M}"
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
        line = f"Added {name} to your commitments: {rt.days_text(days)} {start}–{end}; calls wait while it's on."
        if bare:  # "I have lab every Thursday 2-5": no course named, so a routine
            line += f" No course was named; /class {days[0]} {start}-{end} <course> makes it a class."
        return {"kind": "commitment", "line": line, "undo": {"commitment": row, "enabled": enabled}}
    return None


# ----------------------------------------------------------------------------------------------- run
def observe(app: App, text: str, via: str = "chat") -> list[str]:
    """Look at something you said (a message, a journal line) once; set up what it states. Returns the lines told."""
    return [g["line"] for g in _observe(app, text, via)]


def _observe(app: App, text: str, via: str = "chat", quiet: bool = False, misses: list | None = None, tag: str = ""):
    """observe(), returning what was set up; quiet: not told one by one (the pass tells them in one line); misses
    gets the new lines nothing was set up from; tag marks each change as part of one pass."""
    if not text or not app.settings.get("infer.on"):
        return []
    told = []
    with Lock(app.paths.state, "infer", timeout=5):
        data = _load(app)
        asked = via != "journal" and _request(app, text)  # "LA has a quiz every thursday": the request does it
        heard = []
        for sentence in _sentences(text):
            k = _key(sentence)
            if k in data["seen"] or len(sentence) < 12 or sentence.endswith("?") or ASKS.match(sentence):
                continue  # seen already, or a question: a question states nothing
            data["seen"].append(k)
            heard.append(sentence)
            parts = (("projects", _project), ("meetings", _meeting), ("classes", _class), ("aliases", _alias),
                     ("quizzes", _quiz), ("commitments", _commitment))  # fmt: skip
            for part, fn in parts:
                if not _on(app, part) or (part == "quizzes" and asked):
                    continue
                try:
                    got = fn(app, sentence)
                except Exception as e:  # one rule failing must never stop the message it came with
                    app.events.emit("infer_failed", part=part, error=f"{type(e).__name__}: {e}"[:200])
                    continue
                if got:
                    got.update(id=uuid.uuid4().hex[:6], at=time.time(), via=via, undone=False)
                    if tag:
                        got["pass"] = tag
                    data["items"].append(got)
                    told.append(got)
                    break
            else:
                if misses is not None:
                    misses.append(sentence)
        if heard and _on(app, "short_names"):  # once per message, after what it states is set up
            try:
                for got in _short_names(app, " ".join(heard)):
                    got.update(id=uuid.uuid4().hex[:6], at=time.time(), via=via, undone=False)
                    if tag:
                        got["pass"] = tag
                    data["items"].append(got)
                    told.append(got)
            except Exception as e:
                app.events.emit("infer_failed", part="short_names", error=f"{type(e).__name__}: {e}"[:200])
        _save(app, data)
    for got in told:
        app.events.emit("inferred", kind=got["kind"], via=via)
        if not quiet:
            app.notify(got["line"], kind="info", why="infer.done", buttons=[[("Undo", f"inf:{got['id']}:undo")]])
    return told


# ------------------------------------------------------------------------------------------------ the one pass
HINT = re.compile(
    r"(?i)\b(?:project|thesis|dissertation|supervis\w*|advis\w*|guide|mentor|every|each|weekly|fortnightly|"
    r"(?:mon|tues|wednes|thurs|fri|satur|sun)days|weekdays|weekends|lab|labs|tutorial|lecture|seminar|quiz|"
    r"short for|stands for|i mean|i call)\b"
)
SWEEP_PROMPT = """Someone wrote this line to their assistant. If it states one of the following about them, rewrite it
as exactly one line in that form, using only names, subjects, days and times that are in the line itself. Otherwise
answer NONE. Output only the line or NONE.

I got a project under <title and name> on <topic>
every <weekday> at <time> I have a <subject> <class|lab|tutorial|lecture>
every <weekday> at <time> I go to <activity>
there's a quiz on <subject> every <weekday>
by <short name> I mean <subject>

Line: {line}
"""
FORM_WORDS = set(
    "i got a an the project under on every at have go to there's there s quiz on by mean class lab tutorial lecture "
    "prof professor dr am pm and from till until".split()
)


def faithful(line: str, restated: str) -> bool:
    """Does the restatement use only what the line says? Every name, subject, day and number in it must be there."""
    low = line.lower()
    for w in re.findall(r"[a-z]+|\d+", restated.lower()):
        if w in FORM_WORDS:
            continue
        if w[:3] in DAYS:  # a weekday: the line has to name it
            if w[:3] not in low:
                return False
            continue
        if w not in low:
            return False
    return True


def _restate(app: App, misses: list[str]) -> list[str]:
    """The lines the rules couldn't read but that look like something to set up, restated by the AI in a form the
    rules read (infer.sweep_ai); a restatement that brings in anything the line doesn't say is dropped."""
    how = str(app.settings.get("infer.sweep_ai") or "off").strip().lower()
    hits = [s for s in misses if FIRST.search(s) and HINT.search(s) and not NOT.search(s)][:SWEEP_AI_MAX]
    if how not in ("local", "main") or not hits:
        return []
    from kurooto.modules.consolidate import _brain

    brain = _brain(app, how)
    if brain is None:
        return []
    out = []
    for s in hits:
        try:
            r = brain.complete(SWEEP_PROMPT.format(line=s[:400]), effort="low", timeout=60)
        except Exception as e:
            app.events.emit("infer_failed", part="sweep_ai", error=f"{type(e).__name__}"[:200])
            break
        said = ((getattr(r, "text", "") or "").strip().splitlines() or [""])[0].strip().strip('"')
        if getattr(r, "ok", False) and said and not said.upper().startswith("NONE") and faithful(s, said):
            out.append(said)
    app.events.emit("infer_restated", asked=len(hits), used=len(out), how=how)
    return out


def recent_text(app: App, since: float) -> list[tuple[str, str]]:
    """(via, text) said since then that a message may not have brought: your chat turns with Kurooto, and your
    journal and daily notes as they are in your notes folder (your own lines, not Kurooto's blocks)."""
    from kurooto.core import layout, nightread
    from kurooto.core.graphwrite import outside

    out: list[tuple[str, str]] = [("chat", text[:4000]) for _at, text in nightread.said_since(app, since)]
    day = dt.date.fromtimestamp(since) if since > 0 else now().date()
    while day <= now().date():
        f = layout.path(app, "daily", date=day.isoformat())
        day += dt.timedelta(days=1)
        try:
            if not f.is_file() or f.stat().st_mtime <= since:
                continue
            text = re.sub(
                r"\A---\n.*?\n---\n", "", outside(f.read_text(encoding="utf-8", errors="replace")), flags=re.S
            )
        except OSError:
            continue
        lines = [re.sub(r"^\s*[-*+]\s+(?:\[[ xX]\]\s+)?", "", ln) for ln in text.splitlines()]
        out.append(("journal", "\n".join(ln for ln in lines if ln.strip() and not ln.lstrip().startswith(("#", "|")))))
    return out


LABEL = {"project": "project", "meeting": "meeting", "meeting_ahead": "upcoming meeting", "meetings": "weekly meeting",
         "class": "class", "alias": "short name", "commitment": "routine", "quiz": "recurring quiz"}  # fmt: skip


def sweep(app: App, first: bool | None = None, tell: bool = True) -> list[dict]:
    """The one pass: your recent chats and journal, rules first, the AI only on a line that looks like something the
    rules couldn't read. The first pass reads infer.sweep_days back; later ones only what's new. One line says what
    it set up, with Undo all. What was set up."""
    if not app.settings.get("infer.on") or not app.settings.get("infer.sweep"):
        return []
    data = _load(app)
    if first is None:
        first = not data.get("swept")
    try:
        days = max(1.0, float(app.settings.get("infer.sweep_days") or 30))
    except (TypeError, ValueError):
        days = 30.0
    since = time.time() - days * 86400 if first else float(data.get("swept") or 0)
    started = time.time()
    tag = uuid.uuid4().hex[:6]
    told: list[dict] = []
    misses: list[tuple[str, str]] = []
    for via, text in recent_text(app, since):
        miss: list[str] = []
        told += _observe(app, text, via=via, quiet=True, misses=miss, tag=tag)
        misses += [(via, m) for m in miss]
    for via in ("chat", "journal"):
        for said in _restate(app, [m for v, m in misses if v == via]):
            told += _observe(app, said, via=via, quiet=True, tag=tag)
    with Lock(app.paths.state, "infer", timeout=5):
        data = _load(app)
        data["swept"] = started
        _save(app, data)
    app.events.emit("infer_swept", first=first, set_up=len(told))
    if told and tell:
        app.notify(said_line(told), kind="info", why="infer.done", buttons=[[("Undo all", f"inf:pass-{tag}:undo")]])
    return told


def said_line(told: list[dict]) -> str:
    """One line for everything a pass set up."""
    from collections import Counter

    n = len(told)
    kinds = Counter(LABEL.get(g["kind"], g["kind"]) for g in told)
    what = ", ".join(f"{c} {k}{'es' if c > 1 and k.endswith('s') else 's' if c > 1 else ''}" for k, c in kinds.items())
    return (
        f"Set up {n} thing{'s' if n != 1 else ''} from your recent chats and journal ({what}). /inferred shows each, "
        "with its Undo."
    )


def start(app: App) -> None:
    """Nightly: the pass on what's new; the first one soon after it's first on."""
    import asyncio

    async def run(payload: dict | None = None) -> str:
        got = await asyncio.to_thread(sweep, app)
        return f"set up {len(got)}"

    app.scheduler.action("infer.sweep", run)
    app.scheduler.every("infer:sweep", SWEEP_WHEN, "infer.sweep", module="infer", misfire="coalesce")
    if app.settings.get("infer.on") and app.settings.get("infer.sweep") and not _load(app).get("swept"):
        app.scheduler.at(time.time() + 180, "infer.sweep", key="infer:first", module="infer", replace=False)


def undo(app: App, iid: str) -> str:
    if iid.startswith("pass-"):  # Undo all, under the pass's one line
        ids = [x["id"] for x in _load(app)["items"] if x.get("pass") == iid[5:] and not x.get("undone")]
        if not ids:
            return "Undone already."
        for i in ids:
            undo(app, i)
        return f"Undone: {len(ids)} thing{'s' if len(ids) != 1 else ''} set up from your chats and journal."
    with Lock(app.paths.state, "infer", timeout=5):
        data = _load(app)
        it = next((x for x in data["items"] if x["id"] == iid), None)
        if it is None:
            return "That change isn't remembered any more."
        if it.get("undone"):
            return "Undone already."
        u = it["undo"]
        if "repo" in u:  # a piece set up from a repository (core/repoproject.py)
            from kurooto.core import repoproject

            said = repoproject.undo_piece(app, u)
            if said:
                return said
        elif "note_before" in u:  # a weekly meeting: the note as it was, unless it changed since
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
        elif "recurring" in u:
            dl = app.modules.get("deadlines")
            if dl is not None:
                dl.remove_recurring(u["recurring"]["subject"], u["recurring"]["what"])
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
    m = re.fullmatch(r"\s*undo\s+([\w-]+)\s*", arg or "", re.I)
    if m:
        return undo(app, m[1])
    if (arg or "").strip().lower() in ("scan", "look", "now"):
        if not app.settings.get("infer.on") or not app.settings.get("infer.sweep"):
            return "The pass over your chats and journal is off (infer.on, infer.sweep)."
        got = sweep(app, tell=False)
        return said_line(got) if got else "Looked over your recent chats and journal: nothing new to set up."
    items = [x for x in _load(app)["items"] if not x.get("undone")][-15:]
    if not items:
        on = "on" if app.settings.get("infer.on") else "off (infer.on)"
        return f'Nothing set up from what you said yet ({on}). Say "I got a project under Prof X" and it starts one.'
    rows = [f"[{x['id']}] {dt.datetime.fromtimestamp(x['at']):%d %b} {x['line']}" for x in reversed(items)]
    return "Set up from what you said:\n" + "\n".join(rows) + "\n\n/inferred undo <id> takes one back."

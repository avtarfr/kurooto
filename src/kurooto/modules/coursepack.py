"""A class pack, the file: one section's term setup in a small, strict JSON file, `<name>.kurooto-course`.

A pack carries these and nothing else. An unknown field anywhere makes the whole file invalid:

    {
      "format": "kurooto-course", "version": 1,
      "title": "Year 2 section B",                     what the section calls itself (optional)
      "checked": "2026-10-18",                         checked against the official timetable on this day
      "made": "2026-10-20",                            the day it was made
      "term": {"name": "Autumn 2026", "starts": "2026-08-03", "classes_end": "2026-12-04",
               "holidays": [{"from": "2026-10-02", "to": "2026-10-02", "what": "Holiday"}],
               "exam_periods": [{"from": "2026-12-07", "to": "2026-12-18", "what": "End-term exams"}]},
      "courses": [{"id": "linear-algebra", "name": "Linear Algebra", "short": ["la", "ma101"], "elective": false}],
      "classes": [{"course": "linear-algebra", "day": "mon", "start": "09:00", "end": "09:55",
                   "kind": "lecture", "batch": ""}],                kind: lecture, lab or tutorial; batch: "" or "A"
      "quizzes": [{"course": "linear-algebra", "what": "Quiz", "every_weeks": 1, "day": "thu", "time": "10:00",
                   "next": "", "until": "", "batch": ""}],
      "exams": [{"course": "linear-algebra", "date": "2026-11-12", "time": "10:00", "what": "Midterm"}]
    }

What a pack never carries: people's names, keys or tokens, notes, skills, links, anyone's skips or anything else
personal. The schema has no place for them, and every piece of text in it is checked: short plain words only, with no
email address, phone number, web or notes link, @handle, file path or long code. A file that breaks any rule is
refused whole, with the reason. Packs made before 0.5.8 may also carry attendance rules ("attendance", for the
section and in a course): they still read, and the rules are left out.

Pure functions, used by Class packs (modules/classpacks.py):
    validate / load / read / dumps    the schema, both ways (what Kurooto writes always reads back)
    build                             a pack from what Kurooto knows (or from a term note: source_from_note)
    choose                            one student's electives, lab batch and changes -> what counts for them, in the
                                      term note's shape (termnote.parse) plus their quizzes and exams
    under                             a term note's data over a pack's (the note wins)
    diff                              what changes for a student between two packs (a re-import)
    read_change                       "la quiz off", "la quiz fri 11:00", "batch B": what someone typed
"""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

from kurooto.modules import recurring, termnote

FORMAT = "kurooto-course"
VERSION = 1
EXT = ".kurooto-course"
MAX_BYTES = 200_000
DAYS = recurring.DAYS
KINDS = ("lecture", "lab", "tutorial")
LIMITS = {"courses": 40, "classes": 250, "quizzes": 80, "exams": 150, "holidays": 80, "exam_periods": 12, "short": 6}

# The fields there are, and only these (a field that isn't here makes the file invalid; "attendance" is an older
# pack's rule, read and left out)
TOP = {"format", "version", "title", "checked", "made", "term", "attendance", "courses", "classes", "quizzes", "exams"}
TERM = {"name", "starts", "classes_end", "holidays", "exam_periods"}
SPAN = {"from", "to", "what"}
COURSE = {"id", "name", "short", "elective", "attendance"}
CLASS = {"course", "day", "start", "end", "kind", "batch"}
QUIZ = {"course", "what", "every_weeks", "day", "time", "next", "until", "batch"}
EXAM = {"course", "date", "time", "what"}

ISO = re.compile(r"\d{4}-\d{2}-\d{2}")
HHMM = re.compile(r"(?:[01]\d|2[0-3]):[0-5]\d")
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
SHORT = re.compile(r"[a-z0-9][a-z0-9 .+#-]{0,19}")
BATCH = re.compile(r"[A-Za-z0-9][A-Za-z0-9 -]{0,11}")
TEXT_OK = re.compile(r"[\w ,.:;&()'+#/%!?–—-]+")
# what text in a pack may never look like (checked after dates and times are taken out)
PERSONAL = (
    ("an email address", re.compile(r"[^\s@]@[^\s@]")),
    ("an @handle", re.compile(r"(?:^|[\s(])@\w")),
    ("a link", re.compile(r"(?i)://|\bwww\.|\[\[|\]\]|\]\(|\b\w+\.(?:com|org|net|io|edu|dev|app|ly|gl)\b")),
    ("a file path", re.compile(r"(?:^|\s)[/~]|\\|\b[A-Za-z]:/|\w/\w+/\w|\.(?:md|json|txt|pdf|png|jpg)\b", re.I)),
    ("a phone number", re.compile(r"(?<!\w)\+?\d(?:[ -]?\d){7,}(?!\w)")),
    ("a key or token", re.compile(r"(?<![A-Za-z0-9_])(?=[A-Za-z_]*\d)(?=\d*[A-Za-z_])[A-Za-z0-9_]{20,}")),
)


class PackError(ValueError):
    """Why a file isn't a class pack Kurooto can use, in plain words."""


def title(text: str) -> str:
    """A pack's title, checked like any text in it (PackError if it can't be one)."""
    return _text(text, "the title", 80)


def personal(text: str) -> str | None:
    """What personal-looking thing a piece of text has in it ("an email address"), or None."""
    t = re.sub(r"\d{4}-\d{2}-\d{2}|\b\d{1,2}:\d{2}\b", " ", text or "")
    for what, rx in PERSONAL:
        if rx.search(t):
            return what
    return None


# --------------------------------------------------------------------------------------------- checking
def _obj(v, keys: set, where: str, need: tuple = ()) -> dict:
    if not isinstance(v, dict):
        raise PackError(f"{where} isn't laid out the way a class pack's is")
    extra = [k for k in v if k not in keys]
    if extra:
        raise PackError(f'{where} carries "{str(extra[0])[:40]}", which a class pack never has')
    for k in need:
        if v.get(k) in ("", None):
            raise PackError(f'{where} needs "{k}"')
    return v


def _list(v, where: str, cap: int) -> list:
    if v is None:
        return []
    if not isinstance(v, list):
        raise PackError(f"{where} should be a list")
    if len(v) > cap:
        raise PackError(f"{where} has {len(v)} entries; a class pack has at most {cap}")
    return v


def _date(v, where: str, empty_ok: bool = False) -> str:
    if empty_ok and v in ("", None):
        return ""
    if not isinstance(v, str) or not ISO.fullmatch(v):
        raise PackError(f"{where} should be a date like 2026-12-04")
    try:
        dt.date.fromisoformat(v)
    except ValueError:
        raise PackError(f"{where}: {v} isn't a real date") from None
    return v


def _time(v, where: str) -> str:
    if v in ("", None):
        return ""
    if not isinstance(v, str) or not HHMM.fullmatch(v):
        raise PackError(f"{where} should be a time like 09:00")
    return v


def _text(v, where: str, cap: int, empty_ok: bool = False) -> str:
    if v is None and empty_ok:
        return ""
    if not isinstance(v, str):
        raise PackError(f"{where} should be text")
    t = " ".join(v.split())
    if not t:
        if empty_ok:
            return ""
        raise PackError(f"{where} is empty")
    if len(t) > cap:
        raise PackError(f"{where} is longer than {cap} characters")
    why = personal(t)
    if why:
        raise PackError(f"{where} looks like it has {why} in it; a class pack carries none")
    if not TEXT_OK.fullmatch(t):
        raise PackError(f"{where} has characters a class pack doesn't use")
    return t


def _int(v, where: str, lo: int, hi: int, default: int | None = None) -> int:
    if v is None and default is not None:
        return default
    if type(v) is not int or not lo <= v <= hi:
        raise PackError(f"{where} should be a whole number from {lo} to {hi}")
    return v


def _batch(v, where: str) -> str:
    if v in ("", None):
        return ""
    if not isinstance(v, str) or not BATCH.fullmatch(v.strip()) or personal(v):
        raise PackError(f'{where} should be a short batch name like "A" or "B1"')
    return v.strip()


def _span(v, where: str) -> dict:
    s = _obj(v, SPAN, where, ("from",))
    a = _date(s["from"], f"{where}'s first day")
    b = _date(s.get("to"), f"{where}'s last day", empty_ok=True) or a
    if b < a:
        raise PackError(f"{where} ends before it starts")
    return {"from": a, "to": b, "what": _text(s.get("what"), f"{where}'s name", 60, empty_ok=True)}


def _course(v, where: str) -> dict:
    c = _obj(v, COURSE, where, ("id", "name"))
    cid = c["id"]
    if not isinstance(cid, str) or len(cid) > 48 or not SLUG.fullmatch(cid) or personal(cid):
        raise PackError(f"{where}'s id should look like linear-algebra")
    short = []
    for s in _list(c.get("short"), f"{where}'s short names", LIMITS["short"]):
        s2 = " ".join(str(s).lower().split()) if isinstance(s, str) else ""
        if not SHORT.fullmatch(s2) or personal(s2):
            raise PackError(f'{where}\'s short names should be like "la" or "ma101"')
        if s2 not in short and s2 != cid:
            short.append(s2)
    elective = c.get("elective", False)
    if not isinstance(elective, bool):
        raise PackError(f"{where}: elective should be true or false")
    return {"id": cid, "name": _text(c["name"], f"{where}'s name", 80), "short": short, "elective": elective}


def _course_ref(v, where: str, ids: set) -> str:
    if v not in ids:
        raise PackError(f"{where} names a course that isn't in the pack")
    return v


def _class(v, where: str, ids: set) -> dict:
    k = _obj(v, CLASS, where, ("course", "day", "start", "end"))
    if k["day"] not in DAYS:
        raise PackError(f"{where}'s day should be one of {', '.join(DAYS)}")
    start, end = _time(k["start"], f"{where}'s start"), _time(k["end"], f"{where}'s end")
    if end <= start:
        raise PackError(f"{where} ends before it starts")
    kind = k.get("kind") or "lecture"
    if kind not in KINDS:
        raise PackError(f"{where}'s kind should be lecture, lab or tutorial")
    return {
        "course": _course_ref(k["course"], where, ids),
        "day": k["day"],
        "start": start,
        "end": end,
        "kind": kind,
        "batch": _batch(k.get("batch"), f"{where}'s batch"),
    }


def _quiz(v, where: str, ids: set) -> dict:
    q = _obj(v, QUIZ, where, ("course", "day"))
    if q["day"] not in DAYS:
        raise PackError(f"{where}'s day should be one of {', '.join(DAYS)}")
    every = _int(q.get("every_weeks"), f"{where}'s weeks between", 1, 8, 1)
    nxt = _date(q.get("next"), f"{where}'s next date", empty_ok=True)
    if every > 1 and not nxt:
        raise PackError(f"{where} is every {every} weeks, so it needs a next date (which week)")
    return {
        "course": _course_ref(q["course"], where, ids),
        "what": _text(q.get("what") or "Quiz", f"{where}'s name", 60),
        "every_weeks": every,
        "day": q["day"],
        "time": _time(q.get("time"), f"{where}'s time"),
        "next": nxt,
        "until": _date(q.get("until"), f"{where}'s last date", empty_ok=True),
        "batch": _batch(q.get("batch"), f"{where}'s batch"),
    }


def _exam(v, where: str, ids: set) -> dict:
    e = _obj(v, EXAM, where, ("course", "date", "what"))
    return {
        "course": _course_ref(e["course"], where, ids),
        "date": _date(e["date"], f"{where}'s date"),
        "time": _time(e.get("time"), f"{where}'s time"),
        "what": _text(e["what"], f"{where}'s name", 60),
    }


def validate(data) -> dict:
    """A clean copy of a class pack (defaults filled in), or PackError saying what's wrong with it."""
    d = _obj(data, TOP, "the file", ("format", "version", "checked", "courses"))
    if d["format"] != FORMAT:
        raise PackError('it isn\'t a class pack (it has no "format": "kurooto-course")')
    if type(d["version"]) is not int or d["version"] != VERSION:
        raise PackError(f"it's a class pack of a format this Kurooto doesn't read (version {d['version']!s:.10})")
    out = {"format": FORMAT, "version": VERSION, "title": _text(d.get("title"), "the title", 80, empty_ok=True)}
    out["checked"] = _date(d["checked"], 'the "checked against the official timetable" date')
    out["made"] = _date(d.get("made"), "the day it was made", empty_ok=True)
    if out["made"] and out["checked"] > out["made"]:
        raise PackError("it says it was checked after it was made")
    t = _obj(d.get("term") or {}, TERM, "the term")
    hols = _list(t.get("holidays"), "holidays", LIMITS["holidays"])
    pers = _list(t.get("exam_periods"), "exam periods", LIMITS["exam_periods"])
    out["term"] = {
        "name": _text(t.get("name"), "the term's name", 40, empty_ok=True),
        "starts": _date(t.get("starts"), "the term's first day", empty_ok=True),
        "classes_end": _date(t.get("classes_end"), "the last day of classes", empty_ok=True),
        "holidays": [_span(x, f"holiday {i + 1}") for i, x in enumerate(hols)],
        "exam_periods": [_span(x, f"exam period {i + 1}") for i, x in enumerate(pers)],
    }
    out["courses"] = []
    for i, c in enumerate(_list(d["courses"], "courses", LIMITS["courses"])):
        c = _course(c, f"course {i + 1}")
        if c["id"] in {x["id"] for x in out["courses"]}:
            raise PackError(f"course {i + 1}: {c['id']} is in it twice")
        out["courses"].append(c)
    if not out["courses"]:
        raise PackError("it has no courses")
    ids = {c["id"] for c in out["courses"]}
    for key, one, word in (("classes", _class, "class"), ("quizzes", _quiz, "quiz"), ("exams", _exam, "exam")):
        rows = _list(d.get(key), key, LIMITS[key])
        out[key] = [one(x, f"{word} {i + 1}", ids) for i, x in enumerate(rows)]
    return out


def load(raw: bytes | str) -> dict:
    """A pack from a file's bytes, checked (PackError if it isn't one Kurooto can use)."""
    raw = raw.encode("utf-8") if isinstance(raw, str) else raw
    if len(raw) > MAX_BYTES:
        raise PackError(f"it's {len(raw) // 1000} KB, and a class pack is at most {MAX_BYTES // 1000} KB")
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError):
        raise PackError("it isn't a class pack (Kurooto can't read it as one)") from None
    return validate(data)


def read(path: Path) -> dict:
    p = Path(path)
    try:
        if p.stat().st_size > MAX_BYTES:
            raise PackError(f"it's {p.stat().st_size // 1000} KB, and a class pack is at most {MAX_BYTES // 1000} KB")
        return load(p.read_bytes())
    except OSError as e:
        raise PackError(f"Kurooto can't open it ({e.strerror or e})") from None


def dumps(pack: dict) -> str:
    """The file's text, checked again on the way out, so a pack Kurooto writes always reads back."""
    return json.dumps(validate(pack), ensure_ascii=False, indent=1) + "\n"


def looks_like(path: Path) -> bool:
    """Is this file a class pack (by its name, or a small JSON file that says so)?"""
    p = Path(path)
    if EXT in p.name.lower():
        return True
    if p.suffix.lower() not in ("", ".json", ".txt"):
        return False
    try:
        if p.stat().st_size > MAX_BYTES:
            return False
        with open(p, "rb") as f:
            head = f.read(600)
    except OSError:
        return False
    return re.search(rb'"format"\s*:\s*"kurooto-course"', head) is not None


def file_name(pack: dict) -> str:
    base = termnote.slugify(pack.get("title") or "")[:40].strip("-") or "class-pack"
    return f"{base}-{pack.get('made') or pack['checked']}{EXT}"


def same(a: dict, b: dict) -> bool:
    """The same pack (what's in it, whenever it was made)."""
    strip = lambda p: {k: v for k, v in validate(p).items() if k != "made"}  # noqa: E731
    return strip(a) == strip(b)


# ---------------------------------------------------------------------------------------- one student
def qkey(course: str, what: str) -> str:
    return f"{course}|{what.strip().lower()}"


def electives(pack: dict) -> list[dict]:
    return [c for c in pack["courses"] if c["elective"]]


def batches(pack: dict) -> list[str]:
    found = {x["batch"] for x in pack["classes"] + pack["quizzes"] if x["batch"]}
    return sorted(found, key=termnote.natural)


def named(course: dict, what: str) -> str:
    """An exam's title with its course in it: "Midterm" -> "Linear Algebra Midterm"."""
    low = f" {what.lower()} "
    for n in [course["name"], course["id"], *course["short"]]:
        if n and re.search(r"(?<![a-z0-9])" + re.escape(n.lower()) + r"(?![a-z0-9])", low):
            return what
    return f"{course['name']} {what}"


def _row(a: str, b: str, time: str, what: str, kind: str) -> dict:
    return {"from": a, "to": b, "time": time, "what": what, "text": what, "kind": kind, "explicit": True}


def moved_next(nxt: str, day: str) -> str:
    """A quiz moved to another weekday: its next date moves within the same week."""
    if not nxt:
        return ""
    d = dt.date.fromisoformat(nxt)
    return (d + dt.timedelta(days=DAYS.index(day) - d.weekday())).isoformat()


def choose(pack: dict, chosen_electives=(), batch: str = "", changes: dict | None = None) -> dict:
    """What counts for one student: the courses everyone takes and the electives they ticked; the classes and quizzes
    of their lab batch (and those without a batch); the term's dates; the quizzes and exams they didn't turn off, at
    the times they moved them to. In the term note's shape (termnote.parse) plus "quizzes" and "exams"."""
    ch = changes or {}
    off, moved = set(ch.get("off") or []), ch.get("moved") or {}
    picked = set(chosen_electives or ())
    courses = [c for c in pack["courses"] if not c["elective"] or c["id"] in picked]
    ids = {c["id"]: c for c in courses}
    mine = (batch or "").strip().lower()

    def ours(b: str) -> bool:
        return not b or b.lower() == mine

    out = {**termnote.empty(), "quizzes": [], "exams": []}
    out["subjects"] = [{"name": c["name"], "slug": c["id"], "aliases": list(c["short"])} for c in courses]
    for k in pack["classes"]:
        if k["course"] in ids and ours(k["batch"]):
            c = ids[k["course"]]
            one = {"day": k["day"], "start": k["start"], "end": k["end"], "name": c["name"], "slug": c["id"]}
            out["classes"].append({**one, "code": "", "kind": k["kind"], "batch": k["batch"]})
    term = pack["term"]
    days: set[str] = set()
    for h in term["holidays"]:
        days.update(termnote.days(h["from"], h["to"]))
        out["dates"].append(_row(h["from"], h["to"], "", h["what"] or "Holiday", "holiday"))
    out["holidays"] = sorted(days)
    for p in term["exam_periods"]:
        out["exam_periods"].append([p["from"], p["to"]])
        out["dates"].append(_row(p["from"], p["to"], "", p["what"] or "Exams", "exams"))
    if term["classes_end"]:
        out["term_ends"] = term["classes_end"]
        out["dates"].append(_row(term["classes_end"], term["classes_end"], "", "Last day of classes", "term_end"))
    for e in pack["exams"]:
        if e["course"] in ids and qkey(e["course"], e["what"]) not in off:
            title = named(ids[e["course"]], e["what"])
            out["exams"].append({"course": e["course"], "what": e["what"], "date": e["date"], "time": e["time"]})
            out["dates"].append(_row(e["date"], e["date"], e["time"], title, "exam"))
    out["dates"].sort(key=lambda d: (d["from"], d["time"]))
    for q in pack["quizzes"]:
        key = qkey(q["course"], q["what"])
        if q["course"] not in ids or not ours(q["batch"]) or key in off:
            continue
        m = moved.get(key) or {}
        day = m.get("day") or q["day"]
        out["quizzes"].append(
            {
                "course": q["course"],
                "what": q["what"],
                "every": q["every_weeks"],
                "day": day,
                "time": m.get("time", q["time"]),
                "next": moved_next(q["next"], day) if m.get("day") else q["next"],
                "until": q["until"],
            }
        )
    return out


def _match(a: dict, b: dict) -> bool:
    na = {a["slug"], a["name"].lower(), *a.get("aliases", [])}
    nb = {b["slug"], b["name"].lower(), *b.get("aliases", [])}
    return bool(na & nb)


def under(note: dict, pack: dict | None) -> dict:
    """A term note's data (termnote.parse) laid over a pack's (choose): the note wins where both say something
    (a class at the same time, the last day of classes, the same key date)."""
    if not pack:
        return note
    out = {k: list(v) if isinstance(v, list) else v for k, v in note.items()}
    have = {(c["day"], c["start"]) for c in note["classes"]}
    out["classes"] += [c for c in pack["classes"] if (c["day"], c["start"]) not in have]
    out["subjects"] += [s for s in pack["subjects"] if not any(_match(s, n) for n in note["subjects"])]
    out["holidays"] = sorted({*note["holidays"], *pack["holidays"]})
    out["exam_periods"] += [p for p in pack["exam_periods"] if p not in note["exam_periods"]]
    out["term_ends"] = note["term_ends"] or pack["term_ends"]
    seen = {(d["from"], d["what"].lower()) for d in note["dates"]}
    out["dates"] = sorted(
        note["dates"] + [d for d in pack["dates"] if (d["from"], d["what"].lower()) not in seen],
        key=lambda d: (d["from"], d["time"]),
    )
    return out


# ------------------------------------------------------------------------------------------- telling you
def n(k: int, word: str, plural: str = "") -> str:
    return f"{k} {word if k == 1 else plural or word + 's'}"


def week(layer_or_pack: dict) -> int:
    return len(layer_or_pack["classes"])


def overview(pack: dict) -> str:
    """'6 courses (2 electives), 21 classes a week (batches A, B), term ends 2026-12-04, ...'"""
    el, bs, t = electives(pack), batches(pack), pack["term"]
    out = [n(len(pack["courses"]), "course") + (f" ({n(len(el), 'elective')})" if el else "")]
    out.append(f"{n(week(pack), 'class', 'classes')} a week" + (f" (lab batches {', '.join(bs)})" if bs else ""))
    if t["classes_end"]:
        out.append(f"classes end {t['classes_end']}")
    out += [n(len(t["exam_periods"]), "exam period"), n(len(t["holidays"]), "holiday")]
    out += [n(len(pack["quizzes"]), "recurring quiz", "recurring quizzes"), n(len(pack["exams"]), "dated exam")]
    return ", ".join(out)


def counts(layer: dict) -> str:
    out = [n(len(layer["subjects"]), "course"), f"{n(week(layer), 'class', 'classes')} a week"]
    out += [n(len(layer["quizzes"]), "recurring quiz", "recurring quizzes"), n(len(layer["exams"]), "dated exam")]
    return ", ".join(out)


def span_text(a: str, b: str) -> str:
    return a if a == b else f"{a} to {b}"


def _cls(c: dict, names: dict) -> str:
    kind = "" if c["kind"] == "lecture" else f" ({c['kind']}" + (f", batch {c['batch']})" if c["batch"] else ")")
    return f"{c['day'].title()} {c['start']}-{c['end']} {names.get(c['slug'], c['slug'])}{kind}"


def diff(old: dict, new: dict) -> list[str]:
    """What changes for you between two of choose()'s answers, in plain lines ("+" new, "-" gone)."""
    out: list[str] = []
    on = {s["slug"]: s["name"] for s in old["subjects"]}
    nn = {s["slug"]: s["name"] for s in new["subjects"]}
    names = {**on, **nn}
    out += [f"+ {nn[s]} (a new course for you)" for s in nn if s not in on]
    out += [f"- {on[s]} (not in it any more)" for s in on if s not in nn]
    if old["term_ends"] != new["term_ends"]:
        out.append(f"Last day of classes: {old['term_ends'] or 'none'} -> {new['term_ends'] or 'none'}")
    for kind, label in (("holiday", "Holiday"), ("exams", "Exam period")):
        o = {(d["from"], d["to"]): d["what"] for d in old["dates"] if d["kind"] == kind}
        w = {(d["from"], d["to"]): d["what"] for d in new["dates"] if d["kind"] == kind}
        out += [f"+ {label} {span_text(*k)}: {w[k]}" for k in sorted(w.keys() - o.keys())]
        out += [f"- {label} {span_text(*k)}: {o[k]}" for k in sorted(o.keys() - w.keys())]

    def key(c: dict) -> tuple:
        return (c["slug"], c["kind"], c["batch"], DAYS.index(c["day"]), c["start"], c["end"])

    o = {key(c): c for c in old["classes"]}
    w = {key(c): c for c in new["classes"]}
    gone = [o[k] for k in sorted(o.keys() - w.keys())]
    came = [w[k] for k in sorted(w.keys() - o.keys())]
    for c in list(gone):  # one class of a course moved: one line
        same_ = [x for x in came if (x["slug"], x["kind"], x["batch"]) == (c["slug"], c["kind"], c["batch"])]
        were = [x for x in gone if (x["slug"], x["kind"], x["batch"]) == (c["slug"], c["kind"], c["batch"])]
        if len(same_) == 1 and len(were) == 1:
            out.append(f"{_cls(c, names)} -> {same_[0]['day'].title()} {same_[0]['start']}-{same_[0]['end']}")
            gone.remove(c)
            came.remove(same_[0])
    out += [f"+ {_cls(c, names)}" for c in came] + [f"- {_cls(c, names)}" for c in gone]

    def quiz(q: dict) -> str:
        every = "every week" if q["every"] == 1 else f"every {q['every']} weeks"
        return f"{every}, {q['day'].title()} {q['time']}".strip()

    o = {qkey(q["course"], q["what"]): q for q in old["quizzes"]}
    w = {qkey(q["course"], q["what"]): q for q in new["quizzes"]}
    for k in w:
        q = w[k]
        label = f"{names.get(q['course'], q['course'])} {q['what']}"
        if k not in o:
            out.append(f"+ {label}: {quiz(q)}")
        elif (quiz(o[k]), o[k]["next"], o[k]["until"]) != (quiz(q), q["next"], q["until"]):
            out.append(f"{label}: {quiz(o[k])} -> {quiz(q)}")
    out += [f"- {names.get(o[k]['course'], o[k]['course'])} {o[k]['what']}" for k in o if k not in w]
    o = {qkey(e["course"], e["what"]): e for e in old["exams"]}
    w = {qkey(e["course"], e["what"]): e for e in new["exams"]}
    for k in w:
        e = w[k]
        label = f"{names.get(e['course'], e['course'])} {e['what']}"
        when = f"{e['date']} {e['time']}".strip()
        if k not in o:
            out.append(f"+ {label} on {when}")
        elif (o[k]["date"], o[k]["time"]) != (e["date"], e["time"]):
            out.append(f"{label}: {o[k]['date']} {o[k]['time']}".rstrip() + f" -> {when}")
    out += [f"- {names.get(o[k]['course'], o[k]['course'])} {o[k]['what']}" for k in o if k not in w]
    return out


# --------------------------------------------------------------------------------------- making a pack
LAB = re.compile(r"\b(?:labs?|laborator(?:y|ies)|practicals?|workshop)\b", re.I)
TUT = re.compile(r"\b(?:tutorials?|tut|recitation|problem class|section)\b", re.I)
ALL = re.compile(r"^(?:all|every(?:one| course)?|default|section|everything|\*)$", re.I)


def kind_of(text: str) -> str:
    """'Physics Lab', 'lab', 'Tutorial' -> lab, tutorial or lecture."""
    return "lab" if LAB.search(text or "") else "tutorial" if TUT.search(text or "") else "lecture"


def _clean(text: str) -> str:
    """Key-date text made fit for a pack: no bracketed asides, dates or times, links as their labels."""
    t = termnote.plain(text or "")
    t = re.sub(r"\([^)]*\)|\d{4}-\d{2}-\d{2}|\b\d{1,2}[:.]\d{2}\s*(?:[ap]\.?m\.?)?", " ", t, flags=re.I)
    return " ".join(t.split()).strip(" -:,")[:60]


def _ranges(days: list[str]) -> list[tuple[str, str]]:
    """['2026-10-19', '2026-10-20', '2026-11-02'] -> [('2026-10-19', '2026-10-20'), ('2026-11-02', '2026-11-02')]."""
    out: list[list[str]] = []
    for d in sorted(set(days)):
        if out and dt.date.fromisoformat(out[-1][1]) + dt.timedelta(days=1) == dt.date.fromisoformat(d):
            out[-1][1] = d
        else:
            out.append([d, d])
    return [(a, b) for a, b in out]


def build(src: dict, today: dt.date) -> tuple[dict, list[str]]:
    """A pack (not yet checked against the official timetable: "checked" is empty) from a source, and what was left
    out and why. The source, in the term note's words:
        subjects [{name, slug, aliases, elective?}], classes [{day, start, end, slug, kind?, batch?, name?}],
        holidays [days], exam_periods [[a, b]], term_ends, dates [{from, to, time, what, kind, subject}],
        quizzes [{subject, what, every, day, time, next, until, batch?}], title.
    Each piece goes through the same checks a pack gets on import; one that fails is left out (and said)."""
    left: list[str] = []
    courses = []
    for s in src.get("subjects") or []:
        slug = termnote.slugify(s.get("slug") or s.get("name") or "")
        if not slug or slug in {c["id"] for c in courses}:
            continue
        short = []
        for a in s.get("aliases") or []:
            a2 = " ".join(str(a).lower().split())
            if SHORT.fullmatch(a2) and not personal(a2) and a2 != slug and a2 not in short:
                short.append(a2)
            else:
                left.append(f"a short name of {s.get('name') or slug} (it isn't a plain short name)")
        name = " ".join(str(s.get("name") or slug).split())[:80]
        one = {"id": slug[:48].strip("-"), "name": name, "short": short[: LIMITS["short"]]}
        try:
            c = _course({**one, "elective": bool(s.get("elective"))}, "the course")
        except PackError as e:
            left.append(f"the course {name[:40]} ({e})")
            continue
        courses.append(c)
    ids = {c["id"] for c in courses}
    classes = []
    for k in src.get("classes") or []:
        slug = termnote.slugify(k.get("slug") or "")
        kind = k.get("kind") if k.get("kind") in KINDS else kind_of(f"{k.get('kind') or ''} {k.get('name') or ''}")
        one = {"course": slug, "day": k.get("day"), "start": k.get("start"), "end": k.get("end"), "kind": kind}
        try:
            row = _class({**one, "batch": k.get("batch") or ""}, "a class", ids)
        except PackError as e:
            left.append(f"{str(k.get('day', '')).title()} {k.get('start', '')} {k.get('name') or slug} ({e})")
            continue
        if row not in classes:
            classes.append(row)
    names = {c["id"]: c["name"] for c in courses}
    hol_what = {}
    per = []
    for d in src.get("dates") or []:
        if d.get("kind") == "holiday":
            for day in termnote.days(d["from"], d["to"]):
                hol_what.setdefault(day, _clean(d.get("what") or ""))
        if d.get("kind") == "exams":
            per.append((d["from"], d["to"], _clean(d.get("what") or "")))
    holidays = []
    for a, b in _ranges(list(src.get("holidays") or [])):
        what = hol_what.get(a, "") or "Holiday"
        try:
            holidays.append(_span({"from": a, "to": b, "what": what}, "a holiday"))
        except PackError:
            holidays.append({"from": a, "to": b, "what": "Holiday"})
    exam_periods = []
    for p in src.get("exam_periods") or []:
        what = next((w for a, b, w in per if [a, b] == list(p)), "") or "Exams"
        try:
            exam_periods.append(_span({"from": p[0], "to": p[1], "what": what}, "an exam period"))
        except PackError:
            exam_periods.append({"from": p[0], "to": p[1], "what": "Exams"})
    exams = []
    for d in src.get("dates") or []:
        if d.get("kind") != "exam":
            continue
        slug = d.get("subject")
        if slug not in ids:
            left.append(
                f"the key date {_clean(d.get('what') or '')[:40] or d['from']} (no course of the pack is named in it)"
            )
            continue
        what = _clean(d.get("what") or "") or "Exam"
        one = {"course": slug, "date": d["from"], "time": d.get("time") or "", "what": what}
        try:
            exams.append(_exam(one, "an exam", ids))
        except PackError as e:
            left.append(f"the key date {d['from']} ({e})")
    quizzes = []
    for q in src.get("quizzes") or []:
        slug = q.get("subject")
        one = {"course": slug, "what": q.get("what") or "Quiz", "day": q.get("day") or "", "time": q.get("time")}
        more = {"next": q.get("next") or "", "until": q.get("until") or "", "batch": q.get("batch") or ""}
        try:
            row = _quiz({**one, **more, "every_weeks": int(q.get("every") or 1)}, "a quiz", ids)
        except (PackError, ValueError) as e:
            left.append(f"the recurring {q.get('what') or 'quiz'} of {names.get(slug, slug)} ({e})")
            continue
        if qkey(row["course"], row["what"]) not in {qkey(x["course"], x["what"]) for x in quizzes}:
            quizzes.append(row)
    ends = src.get("term_ends") or ""
    pack = {
        "format": FORMAT,
        "version": VERSION,
        "title": "",
        "checked": "",
        "made": today.isoformat(),
        "term": {
            "name": "",
            "starts": "",
            "classes_end": ends if ISO.fullmatch(ends) else "",
            "holidays": holidays,
            "exam_periods": exam_periods,
        },
        "courses": courses[: LIMITS["courses"]],
        "classes": classes[: LIMITS["classes"]],
        "quizzes": quizzes[: LIMITS["quizzes"]],
        "exams": exams[: LIMITS["exams"]],
    }
    title = src.get("title") or ""
    if title:
        try:
            pack["title"] = _text(title, "the title", 80)
        except PackError as e:
            left.append(f"the title ({e})")
    return pack, left


def section(text: str, heading: re.Pattern) -> str:
    """The lines under every heading that matches, up to the next heading."""
    out, inside = [], False
    for ln in (text or "").splitlines():
        m = re.match(r"^\s*#{1,6}\s+(.*?)\s*#*\s*$", ln)
        if m:
            inside = bool(heading.search(m[1]))
            continue
        if inside:
            out.append(ln)
    return "\n".join(out)


RECURRING_H = re.compile(r"\brecurring\b|\bquizzes\b", re.I)


def _which(text: str, subjects: list[dict]) -> str | None:
    """The subject a cell or a sentence names (by slug, name or short name), when it names exactly one."""
    t = termnote.plain(text or "").lower().strip()
    for s in subjects:
        if t and t in {s["slug"], s["name"].lower(), *s.get("aliases", [])}:
            return s["slug"]
    low, found = f" {t} ", []
    for s in subjects:
        for name in [s["name"], s["slug"], *s.get("aliases", [])]:
            if name and re.search(r"(?<![a-z0-9])" + re.escape(name.lower()) + r"(?![a-z0-9])", low):
                found.append(s["slug"])
                break
    return found[0] if len(found) == 1 else None


def source_from_note(text: str) -> dict:
    """A term note (termnote.py) as a pack's source. Besides its timetable and key dates it may have: a Batch column
    in the timetable (a lab batch: "A", "B1"); a Type column (lecture, lab, tutorial; "elective" marks a course not
    everyone takes); and a "## Recurring quizzes" table in the recurring table's shape."""
    t = termnote.parse(text)
    subjects = [dict(s) for s in t["subjects"]]
    elective = {c["slug"] for c in t["classes"] if "elective" in (c.get("kind") or "")}
    for s in subjects:
        s["elective"] = s["slug"] in elective
    classes = [
        {**c, "kind": kind_of(f"{c.get('kind') or ''} {c['name']}"), "batch": c.get("batch") or ""}
        for c in t["classes"]
    ]
    dates = [{**d, "subject": _which(d["text"], subjects)} for d in t["dates"]]
    quizzes = []
    for r in recurring.parse(section(text, RECURRING_H)):
        slug = _which(r["subject"], subjects) or termnote.slugify(r["subject"])
        quizzes.append({**r, "subject": slug})
    return {
        "subjects": subjects,
        "classes": classes,
        "holidays": t["holidays"],
        "exam_periods": t["exam_periods"],
        "term_ends": t["term_ends"],
        "dates": dates,
        "quizzes": quizzes,
    }


# ------------------------------------------------------------------------------------ what someone typed
DAY = re.compile(r"^(mon|tue|wed|thu|fri|sat|sun)[a-z]*$", re.I)


def course_in(pack: dict, words: str) -> str | None:
    """A course of the pack by its id, name or a short name ("la", "linear algebra"); "*" for all of them."""
    w = " ".join((words or "").lower().split())
    if ALL.match(w):
        return "*"
    for c in pack["courses"]:
        if w in {c["id"], c["name"].lower(), *c["short"]}:
            return c["id"]
    return None


def read_change(text: str, pack: dict) -> tuple[str, dict] | None:
    """One change someone typed, or None:
    title Year 2 section B        ("title", {text})
    checked 2026-10-18 / today    ("checked", {date})
    electives ml, topology / none ("electives", {ids})       batch B / none  ("batch", {batch})
    la reset                      ("reset", {course})
    la elective / la core         ("elective", {course, on})
    la quiz off / la quiz on      ("off" / "on", {key})
    la quiz fri 11:00             ("move", {key, day, time})"""
    t = " ".join((text or "").strip().rstrip(".").split())
    low = t.lower()
    if m := re.match(r"^title\s*:?\s+(.+)$", t, re.I):
        return "title", {"text": m[1].strip()}
    if m := re.match(r"^checked\s*(?:on\s+)?(\d{4}-\d{2}-\d{2}|today|yesterday)$", low):
        return "checked", {"date": m[1]}
    if m := re.match(r"^electives?\s*:?\s*(.*)$", low):
        if m[1] in ("none", "no", "nothing", ""):
            return "electives", {"ids": []}
        ids = [course_in(pack, x) for x in re.split(r"\s*(?:,|;|\band\b|&)\s*", m[1]) if x.strip()]
        return ("electives", {"ids": ids}) if ids and all(i and i != "*" for i in ids) else None
    if m := re.match(r"^(?:lab\s+)?batch\s*:?\s*(.+)$", low):
        b = "" if m[1] in ("none", "no", "nothing") else m[1].strip()
        found = next((x for x in batches(pack) if x.lower() == b), None)
        return ("batch", {"batch": found or ""}) if found or not b else None
    words = low.split()
    for cut in range(len(words) - 1, 0, -1):  # the longest run of words that names a course
        course = course_in(pack, " ".join(words[:cut]))
        if course:
            rest = " ".join(words[cut:])
            break
    else:
        return None
    if rest in ("reset", "back", "as the pack says"):
        return "reset", {"course": course}
    if rest in ("elective", "is elective", "is an elective", "core", "not elective", "everyone"):
        return (
            ("elective", {"course": course, "on": "elective" in rest and "not" not in rest}) if course != "*" else None
        )
    if course == "*":
        return None
    named_ = [x for x in pack["quizzes"] + pack["exams"] if x["course"] == course]
    if m := re.fullmatch(r"(.+?)\s+(off|on|out|in|skip|drop)", rest):
        what = m[1].strip()
        hit = next((x for x in named_ if x["what"].lower() == what), None)
        hit = hit or next((x for x in named_ if x["what"].lower().startswith(what)), None)
        if hit:
            kind = "off" if m[2] in ("off", "out", "skip", "drop") else "on"
            return kind, {"key": qkey(course, hit["what"])}
        return None
    if m := re.fullmatch(r"(.+?)\s+([a-z]+)\s+(\d{1,2})[:.](\d{2})", rest):
        hit = next((x for x in pack["quizzes"] if x["course"] == course and x["what"].lower() == m[1].strip()), None)
        d = DAY.match(m[2])
        if hit and d and int(m[3]) < 24 and int(m[4]) < 60:
            return "move", {"key": qkey(course, hit["what"]), "day": d[1].lower(), "time": f"{int(m[3]):02d}:{m[4]}"}
    return None

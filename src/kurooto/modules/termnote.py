"""The term note: your term's timetable and key dates in one note, read live (Subjects: `subjects.term_note`).
Edit the note and Kurooto follows it: classes, holidays, exam periods, the last day of classes, and dated quizzes,
exams and deadlines all come from it. /term-setup writes one; any note in this shape works.

    ## Weekly timetable
    | Day | Time | Subject | Code |
    | :--- | :--- | :--- | :--- |
    | Mon | 09:00-09:55 | [[linear-algebra/course|Linear Algebra]] | MA101 |
    |     | 11:00-11:55 | Statistics | |
    | Tue, Thu | 14:00-15:25 | Statistics | |

    ## Key dates
    | Date | What |
    | :--- | :--- |
    | 2026-10-02 | Holiday |
    | 2026-10-19 – 2026-10-23 | Mid-term break |
    | 2026-11-12 | Linear Algebra midterm (10:00-11:00) |
    | 2026-11-20 17:00 | Statistics project due |
    | 2026-12-04 | Last day of classes |
    | 2026-12-07 – 2026-12-18 | End-term exams |

Weekly timetable: under a heading with "timetable" in it. Columns are found by their names (Day, Time or Start and
End, Subject or Course or Class, an optional Code), else by position (day, time, subject). An empty Day cell
continues the day above; "Mon, Wed" means both days. The subject is plain text or a link to its notes
([[maps/courses/linear-algebra|...]], [[linear-algebra/course|...]], [Name](path)); a Code cell becomes a short name
for it. Lunch and break rows are skipped.

Key dates: under a heading with "dates" in it (Key dates, Important dates). Dates are YYYY-MM-DD; a range is "A – B"
(or "A - B", "A to B"); a time can follow the date or sit in the text ("(10:00-11:00)", "5 pm"). An optional Kind
column says what a row is (holiday, break, exams, last day, exam, quiz, due...); otherwise its words do:
- holiday, break, vacation, recess, no classes: no classes on those days;
- last day of classes (or of instruction, teaching, lectures), "classes end": the term's last day of classes;
- an exam period (a range of days, or "exams", "examinations", "exam week"): no classes then;
- a quiz, test, exam, midterm, viva...: a dated exam (Deadlines: exam mode and quiz offers follow);
- due, deadline, submission, assignment, report...: a deadline, when it names one of your subjects or its Kind
  column says "due" (so "last date for grade submission" for teachers isn't chased);
- anything else is a key date /term shows, and nothing more.

This file only reads the note (pure functions); Subjects and Deadlines use what it finds.
"""

from __future__ import annotations

import datetime as dt
import re

from kurooto.modules.deadlines import DUEISH, NOT_EXAM
from kurooto.modules.recurring import DAY_WORDS

TIMETABLE = re.compile(r"timetable|class schedule|weekly schedule|^classes$", re.I)
KEY_DATES = re.compile(r"\bdates\b|academic calendar|^calendar$", re.I)
ISO = r"\d{4}-\d{2}-\d{2}"
DATE_CELL = re.compile(
    rf"(?P<a>{ISO})(?:[ T]+(?P<t>\d{{1,2}}[:.]\d{{2}}(?:\s*[ap]m)?))?"
    rf"(?:\s*(?:–|—|-|to|until|till|\.\.)\s*(?P<b>{ISO}))?",
    re.I,
)
CLOCK = r"(\d{1,2})[:.](\d{2})\s*([ap]\.?m\.?)?"
RANGE = re.compile(rf"{CLOCK}\s*(?:–|—|-|to)\s*{CLOCK}", re.I)
ONE_TIME = re.compile(rf"{CLOCK}|\b(\d{{1,2}})\s*([ap]\.?m\.?)", re.I)
BREAK = re.compile(r"^(?:lunch|break|free|recess|tea|gap|none|-+|–|—|…|\.\.\.)(?: break| period| time)?$", re.I)
HOLIDAY = re.compile(r"\b(?:holidays?|break|vacation|recess|no classes|closed|day off)\b", re.I)
TERM_END = re.compile(
    r"\blast (?:day|date) of (?:classes|instruction|teaching|lectures|term|semester)\b"
    r"|\b(?:classes|instruction|teaching|lectures) (?:end|ends|stop)\b|\bend of (?:classes|instruction|teaching)\b",
    re.I,
)
EXAM = re.compile(
    r"\b(?:quiz(?:zes)?|exams?|examinations?|mid-?terms?|finals|mid-?sems?|end-?sems?|vivas?|tests?|assessments?)\b",
    re.I,
)
EXAM_PERIOD = re.compile(r"\b(?:exams|examinations|exam (?:week|period|window|season)s?|window)\b", re.I)
NOTE_FILES = {"course", "index", "exam-prep", "class-log", "readme", "overview"}

# Column names (lower case, as written in a header row)
DAY_H = {"day", "days", "weekday"}
TIME_H = {"time", "times", "slot", "when", "hours", "timing"}
START_H = {"start", "starts", "from", "begins"}
END_H = {"end", "ends", "to", "until", "till"}
SUBJ_H = {"subject", "course", "class", "module", "paper", "lecture", "what", "title", "name"}
CODE_H = {"code", "course code", "short", "short name", "alias", "aliases", "id"}
DATE_H = {"date", "dates", "when", "day", "from", "start"}
TO_H = {"to", "until", "till", "end", "ends"}
WHAT_H = {"what", "event", "description", "item", "title", "name", "details", "note", "notes"}
KIND_H = {"kind", "type", "category"}


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")


def cells_of(line: str) -> list[str]:
    """A table row's cells. A pipe inside a [[target|label]] link, or escaped as \\|, stays inside its cell."""
    s = line.strip()
    s = s[1:] if s.startswith("|") else s
    s = s[:-1] if s.endswith("|") and not s.endswith("\\|") else s
    out, cur, depth, i = [], "", 0, 0
    while i < len(s):
        two = s[i : i + 2]
        if two in ("[[", "]]"):
            depth = depth + 1 if two == "[[" else max(0, depth - 1)
            cur, i = cur + two, i + 2
        elif two == "\\|":
            cur, i = cur + "|", i + 2
        elif s[i] == "|" and not depth:
            out.append(cur.strip())
            cur, i = "", i + 1
        else:
            cur, i = cur + s[i], i + 1
    return [*out, cur.strip()]


def is_rule(cells: list[str]) -> bool:
    return any(cells) and all(re.fullmatch(r":?-{2,}:?", c.replace(" ", "")) for c in cells if c)


def tables(text: str, heading: re.Pattern) -> list[tuple[list[str] | None, list[list[str]]]]:
    """Every table under a heading that matches: (its header cells or None, its rows)."""
    out: list[tuple[list[str] | None, list[list[str]]]] = []
    inside, block = False, []

    def flush():
        if block:
            head = block[0] if len(block) > 1 and is_rule(block[1]) else None
            rows = block[2:] if head is not None else block
            out.append((head, [r for r in rows if not is_rule(r)]))
        block.clear()

    for ln in (text or "").splitlines():
        m = re.match(r"^\s*#{1,6}\s+(.*?)\s*#*\s*$", ln)
        if m:
            flush()
            inside = bool(heading.search(m[1].strip()))
            continue
        if inside and ln.strip().startswith("|"):
            block.append(cells_of(ln))
        else:
            flush()
    flush()
    return out


def column(head: list[str] | None, names: set[str]) -> int | None:
    if not head:
        return None
    for k, c in enumerate(head):
        if c.lower().strip("*_` :") in names:
            return k
    return None


def cell(row: list[str], k: int | None) -> str:
    return row[k].strip() if k is not None and k < len(row) else ""


def plain(text: str) -> str:
    """Links to their labels, without Markdown emphasis and code marks."""
    t = re.sub(r"\[\[([^\]|]*)\|([^\]]*)\]\]", r"\2", text or "")
    t = re.sub(r"\[\[([^\]]*)\]\]", lambda m: m[1].rsplit("/", 1)[-1], t)
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)
    return re.sub(r"[*_`]+", "", t).strip()


def _hm(h: str, m: str, ap: str | None) -> tuple[int, int] | None:
    hour, minute = int(h), int(m or 0)
    ap = (ap or "").lower().replace(".", "")
    if ap == "pm" and hour < 12:
        hour += 12
    elif ap == "am" and hour == 12:
        hour = 0
    return (hour, minute) if hour < 24 and minute < 60 else None


def span(text: str) -> tuple[str, str] | None:
    """'09:00-09:55', '2:00 – 2:50 pm' -> ('14:00', '14:50'); None when there's no time range."""
    m = RANGE.search(text or "")
    if not m:
        return None
    a, b = _hm(m[1], m[2], m[3]), _hm(m[4], m[5], m[6])
    if not a or not b:
        return None
    if not m[3] and m[6] and m[6].lower().startswith("p") and a[0] < 12 and (a[0] + 12, a[1]) <= b:
        a = (a[0] + 12, a[1])  # "2:00-2:50 pm": both afternoon
    return f"{a[0]:02d}:{a[1]:02d}", f"{b[0]:02d}:{b[1]:02d}"


def time_in(text: str) -> str:
    """The first time written in the text ('(10:00-11:00)', '5 pm', '17:00'), as HH:MM, or ''."""
    s = span(text)
    if s:
        return s[0]
    m = ONE_TIME.search(text or "")
    if not m:
        return ""
    hm = _hm(m[1], m[2], m[3]) if m[1] else _hm(m[4], "0", m[5])
    return f"{hm[0]:02d}:{hm[1]:02d}" if hm else ""


def subject_of(text: str) -> tuple[str, str]:
    """A timetable's subject cell -> (name, slug). Links give the slug from their target (a subject's folder or
    its course page), and the name from their label."""
    t = (text or "").strip()
    wiki = re.search(r"\[\[([^\]|]*)(?:\|([^\]]*))?\]\]", t)
    md = re.search(r"\[([^\]]*)\]\(([^)]*)\)", t)
    if wiki:
        target, label = wiki[1], wiki[2] or ""
    elif md:
        label, target = md[1], md[2]
    else:
        name = plain(t)
        return name, slugify(name)
    parts = [p for p in re.sub(r"\.md$|#.*$", "", target.strip()).split("/") if p]
    if len(parts) > 1 and parts[-1].lower() in NOTE_FILES:
        parts = parts[:-1]
    slug = slugify(parts[-1]) if parts else slugify(label)
    name = plain(label) or (parts[-1].replace("-", " ").replace("_", " ").title() if parts else slug)
    return name, slug


def kind_of(what: str, kind: str = "", many_days: bool = False) -> str:
    """What a key date is: holiday, term_end, exams (a period with no classes), exam, due or date."""
    k = (kind or "").lower()
    if k:
        if re.search(r"holiday|break|vacation|recess|off", k):
            return "holiday"
        if re.search(r"last|end of classes|term end|classes end", k):
            return "term_end"
        if re.search(r"exams|examinations|period|window|exam week", k):
            return "exams"
        if EXAM.search(k):
            return "exam"
        if DUEISH.search(k):
            return "due"
        return "date"
    if TERM_END.search(what):
        return "term_end"
    if HOLIDAY.search(what):
        return "holiday"
    exam = EXAM.search(what) and not NOT_EXAM.search(what)
    if exam and (many_days or EXAM_PERIOD.search(what)):
        return "exams"
    if exam:
        return "exam"
    if DUEISH.search(what):
        return "due"
    return "date"


def days(a: str, b: str) -> list[str]:
    try:
        d, end = dt.date.fromisoformat(a), dt.date.fromisoformat(b)
    except ValueError:
        return []
    out = []
    while d <= end and len(out) < 400:
        out.append(d.isoformat())
        d += dt.timedelta(days=1)
    return out


def empty() -> dict:
    return {"classes": [], "subjects": [], "holidays": [], "exam_periods": [], "term_ends": "", "dates": []}


def parse(text: str) -> dict:
    """Read a term note: {classes, subjects, holidays, exam_periods, term_ends, dates}.
    classes: {day, start, end, name, slug, code}; subjects: {name, slug, aliases}; dates: {from, to, time, what,
    text, kind, explicit} (kind as kind_of; explicit: a Kind column gave it)."""
    out = empty()
    seen_subjects: dict[str, dict] = {}
    for head, rows in tables(text, TIMETABLE):
        dc, tc = column(head, DAY_H), column(head, TIME_H)
        sc, ec = column(head, START_H), column(head, END_H)
        uc, cc = column(head, SUBJ_H), column(head, CODE_H)
        if head is None or dc is None and uc is None:
            dc, tc, uc = 0, 1, 2
        taken = {dc, tc, sc, ec, cc}
        dc = dc if dc is not None else next(j for j in range(9) if j not in taken)
        uc = uc if uc is not None else next(j for j in range(9) if j not in taken | {dc})
        cur: list[str] = []
        for row in rows:
            dcell = plain(cell(row, dc))
            if dcell:
                cur = [m[1].lower() for m in DAY_WORDS.finditer(dcell)]
            if not cur:
                continue
            when = span(cell(row, tc)) if tc is not None else None
            if when is None and sc is not None:
                a, b = time_in(cell(row, sc)), time_in(cell(row, ec))
                when = (a, b) if a and b else None
            if when is None:
                when = next((s for s in (span(c) for c in row) if s), None)
            raw = cell(row, uc)
            name, slug = subject_of(raw)
            if not when or not slug or BREAK.match(name):
                continue
            code = plain(cell(row, cc)).strip()
            for day in dict.fromkeys(cur):
                out["classes"].append(
                    {"day": day, "start": when[0], "end": when[1], "name": name, "slug": slug, "code": code}
                )
            s = seen_subjects.setdefault(slug, {"name": name, "slug": slug, "aliases": []})
            if code and code.lower() not in s["aliases"] and code.lower() != slug:
                s["aliases"].append(code.lower())
    out["subjects"] = list(seen_subjects.values())
    holidays: set[str] = set()
    for head, rows in tables(text, KEY_DATES):
        dc, toc = column(head, DATE_H), column(head, TO_H)
        wc, kc, tc = column(head, WHAT_H), column(head, KIND_H), column(head, TIME_H)
        for row in rows:
            k = dc if dc is not None and re.search(ISO, cell(row, dc)) else None
            if k is None:
                k = next((j for j, c in enumerate(row) if re.search(ISO, c)), None)
            if k is None:
                continue
            m = DATE_CELL.search(row[k])
            if not m:
                continue
            a, b = m["a"], m["b"] or ""
            if not b and toc is not None and toc != k:
                b = (re.search(ISO, cell(row, toc)) or [""])[0]
            b = b or a
            try:
                if dt.date.fromisoformat(b) < dt.date.fromisoformat(a):
                    a, b = b, a
            except ValueError:
                continue
            raw = cell(row, wc) if wc is not None and wc != k else ""
            if not raw:
                raw = next((c for j, c in enumerate(row) if j != k and c and not re.search(ISO, c)), "")
            text_ = plain(raw)
            if not text_:
                continue
            others = " ".join(plain(c) for j, c in enumerate(row) if j not in (k, wc, kc) and c)
            tm = time_in(cell(row, tc)) if tc is not None else ""
            tm = tm or (time_in(m["t"]) if m["t"] else "") or time_in(text_)
            said = plain(cell(row, kc)) if kc is not None else ""
            kind = kind_of(text_, said, many_days=b != a)
            what = re.sub(r"\s*\([^)]*\)\s*$", "", text_).strip() or text_
            out["dates"].append(
                {
                    "from": a,
                    "to": b,
                    "time": tm,
                    "what": what,
                    "text": f"{text_} {others}".strip(),
                    "kind": kind,
                    "explicit": bool(said),  # a Kind column said what it is
                }
            )
            if kind == "holiday":
                holidays.update(days(a, b))
            elif kind == "exams":
                if [a, b] not in out["exam_periods"]:
                    out["exam_periods"].append([a, b])
            elif kind == "term_end":
                out["term_ends"] = max(out["term_ends"], a)
    out["holidays"] = sorted(holidays)
    out["dates"].sort(key=lambda d: (d["from"], d["time"]))
    return out


def natural(name: str) -> list:
    """Sort key: semester-10 after semester-9."""
    return [int(p) if p.isdigit() else p.lower() for p in re.split(r"(\d+)", name)]


def bounds(data: dict) -> tuple[str, str] | None:
    """The first and last of the note's key dates (None without any)."""
    ds = [x["from"] for x in data.get("dates", [])] + [x["to"] for x in data.get("dates", [])]
    return (min(ds), max(ds)) if ds else None


def pick(notes: list[tuple[str, dict]], today: dt.date) -> str | None:
    """Which of several term notes (name, what it says) is the one to follow: the earliest that isn't over yet
    (this term's, before next term's), else the newest name (semester-10 after semester-9)."""
    if not notes:
        return None
    t = today.isoformat()
    live = [(b[0], natural(n), n) for n, data in notes if (b := bounds(data)) and b[1] >= t]
    if live:
        return min(live)[2]
    return max(notes, key=lambda x: natural(x[0]))[0]

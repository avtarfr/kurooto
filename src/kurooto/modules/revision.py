"""Revision plan, a part of Exam season (modules/exam_season.py): before each exam, its course's topics are ranked and
laid into your free time with what to read, and the evening asks whether you covered them.

Topics come from your notes: the course's exam prep note (its "Covered so far" lines, then the short lines under
"Gaps"; "Topics" or "Syllabus" work too), else its lecture notes, else its concept notes (the concept graph's for the
subject, and the other notes in its folder). They're ranked by plain arithmetic in four tiers: no note yet, a stub
(under 50 words of your own), weak recall (its quiz grades and your answers here average under 3 of 5), the rest; in
a tier the weakest recall comes first, then the course's order. A topic you said Yes to isn't laid again for
revision_days.

The blocks: from revision_days (14) before an exam, each day's free time as Start-by counts it (its window less your
classes and calendar events; here also your commitments and the exams), revision_share (50%) of it, in blocks of
block_min (60) minutes, one topic each. Each block goes to the soonest exam still ahead with topics left, ending before
you leave for it (exam_season.leave_min), and an exam gets at most as many blocks as Start-by's size for it (10 h
until you say). With each topic: its own note, the pages of class material (Classroom's files, your files folder) and
of books (what Books read) that name it, and the book pages the concept graph found it on. Class material first.

The day's blocks are fixed the first time they're worked out that day (the morning plan, /revise); the days after are
worked out again as your notes and answers change. They're in the morning plan with Start-by's lines. At the evening
check-in's time (exam_season.night_at without Check-ins) one message asks about the day's topics, Yes / Partly / No
each: an answer grades the topic's quiz items as Quiz's own buttons would (Yes 4, Partly 2, No 1 of 5) and keeps the
topic's own grade. Tapping another answer replaces it; /revise undo takes the last one back.

Local arithmetic only: no AI, and nothing leaves this computer. State: state/revision.json.

    /revise              today's blocks, then the next days
    /revise la           one course's topics, ranked
    /revise undo         take back the last answer
"""

from __future__ import annotations

import copy
import datetime as dt
import math
import re
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto.core import layout, studypack
from kurooto.core.clock import now
from kurooto.core.lock import Lock
from kurooto.core.state import jload, jsave

if TYPE_CHECKING:
    from kurooto.modules.exam_season import ExamSeason

STUB_WORDS = 50  # fewer of your own words than this: a stub
WEAK = 3.0  # recall under this (of 5): weak
UNKNOWN = 3.0  # a topic never graded sorts here among the rest: ahead of what you know well
GRADES = {"y": 4, "p": 2, "n": 1}  # an answer, as a quiz grade (Quiz's buttons: Forgot 0, Hard 3, Good 4, Easy 5)
SAID = {"y": "Yes", "p": "Partly", "n": "No"}
TIERS = ("no note yet", "a stub", "weak recall", "")
MAX_TOPICS = 60  # a course's topics, at most
MAX_ITEMS = 6  # quiz items one answer grades, at most
MAX_READ = 4  # things to read with a topic
MAX_PAGES = 8  # pages of one source for a topic
MAX_NOTES = 4000  # notes looked at to find a linked note by name
KEEP_DAYS = 14  # days kept in state
PREP = re.compile(r"^##\s+(covered so far|topics|syllabus|gaps)\b", re.I)
LINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]+))?\]\]")
DATED = re.compile(r"^\d{4}-\d{2}-\d{2}-.+\.md$")
OWN_KINDS = ("course", "class_log", "exam_prep", "doubts")  # a subject folder's notes that aren't topics
LABEL = re.compile(  # "Lecture 5: Eigenvalues", "Week 3 - Groups", "2026-10-05: Rings": the topic is what follows
    r"^(?:(?:lecture|lec|week|class|session|chapter|ch|unit|module|part|topic|l)\.?\s*\d+|\d{4}-\d{2}-\d{2}|\d+)"
    r"\s*(?::|\s[-–—]\s|\.)\s*(.+)$",
    re.I,
)
REVISE_Q = re.compile(r"^what (?:should|shall|do|must) i (?:revise|study)(?: today)?\??$", re.I)


def key_of(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:48] or "topic"


# ------------------------------------------------------------------------------------------- the notes
def body_words(text: str) -> int:
    """Your own words in a note: not its header, headings, lists of links or a catch-up stub's opening line."""
    text = re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.S)
    n = 0
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith(("#", "- [", "* [", "You missed this class", "Source: ")):
            continue
        s = re.sub(r"\[([^\]]*)\]\([^)]*\)|https?://\S+", " ", LINK.sub(" ", s))
        n += len(re.findall(r"[A-Za-z0-9]+", s))
    return n


def title_of(text: str, path: Path) -> str:
    m = re.search(r"(?m)^title:\s*\"?([^\"\n]+)\"?\s*$", text[:2000]) or re.search(r"(?m)^#\s+(.+)$", text)
    if m:
        return m[1].strip()
    stem = path.stem
    return (stem[11:] if DATED.match(path.name) else stem).replace("-", " ").strip().capitalize()


def topic_name(line: str) -> str:
    """A line of an exam prep note as a topic: links as their labels, what follows "Lecture 5:" when there is."""
    s = LINK.sub(lambda m: m[2] or re.sub(r"^\d{4}-\d{2}-\d{2}-", "", Path(m[1]).name).replace("-", " "), line)
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"[*_`]+", "", s).strip(" .;")
    m = LABEL.match(s)
    if m and m[1].strip():
        s = m[1]
    return s[:60].strip(" .;")


def rank_key(t: dict) -> tuple:
    """Tier, then recall (weakest first; Brain's mastery, as 0-5, stands in for a topic never graded when
    exam_season.use_mastery is on), then a concept at your frontier first, then the course's order."""
    r = t["recall"] if t["recall"] is not None else t.get("mastery5")
    return (t["tier"], r if r is not None else UNKNOWN, 0 if t.get("frontier") else 1, t["order"])


def tier_of(has_note: bool, stub: bool, recall: float | None) -> int:
    if not has_note:
        return 0
    if stub:
        return 1
    return 2 if recall is not None and recall < WEAK else 3


def why_of(t: dict) -> str:
    if t["tier"] == 2 and t.get("doubt") and (t["recall"] is None or t["recall"] >= WEAK):
        return "an open doubt"
    if t["tier"] == 2:
        return f"weak recall, {t['recall']:.1f} of 5"
    return TIERS[t["tier"]]


# ---------------------------------------------------------------------------------------- the arithmetic
def minus(
    slots: list[tuple[dt.datetime, dt.datetime]], busy: list[tuple[dt.datetime, dt.datetime]], min_gap: int
) -> list[tuple[dt.datetime, dt.datetime]]:
    """Free time less more busy times, in gaps of at least min_gap minutes."""
    out = []
    for s, e in slots:
        cur = s
        for bs, be in sorted(busy):
            if be <= cur or bs >= e:
                continue
            if bs > cur:
                out.append((cur, bs))
            cur = max(cur, be)
        if cur < e:
            out.append((cur, e))
    gap = dt.timedelta(minutes=max(0, min_gap))
    return [(s, e) for s, e in out if e - s >= gap]


def lay(slots: list[tuple[dt.datetime, dt.datetime]], exams: list[dict], block_min: int, share: float) -> list[dict]:
    """Revision blocks: each day, `share` (0-1) of its free time in blocks of block_min, each in one free gap, earliest
    first; each block to the soonest exam (exams: {"id", "until": the latest a block may end, "topics": ranked, "n":
    blocks at most}) it ends before that still has topics. Returns [{"start", "end", "exam", "topic"}]."""
    blk = dt.timedelta(minutes=max(15, block_min))
    free: dict[dt.date, float] = {}
    for s, e in slots:
        free[s.date()] = free.get(s.date(), 0.0) + (e - s).total_seconds() / 60
    used: dict[dt.date, float] = {}
    left = {x["id"]: list(x["topics"][: max(0, x["n"])]) for x in exams}
    order = sorted(exams, key=lambda x: x["until"])
    out = []
    for s, e in sorted(slots):
        cur = s
        while cur + blk <= e:
            d = s.date()
            if used.get(d, 0.0) + blk.total_seconds() / 60 > free[d] * share + 1e-6:
                break
            x = next((x for x in order if cur + blk <= x["until"] and left[x["id"]]), None)
            if x is None:
                break
            out.append({"start": cur, "end": cur + blk, "exam": x["id"], "topic": left[x["id"]].pop(0)})
            used[d] = used.get(d, 0.0) + blk.total_seconds() / 60
            cur += blk
    return out


class Revision:
    """The revision plan for one Exam season module (its settings, its exams)."""

    def __init__(self, es: ExamSeason):
        self.es = es
        self.app = es.app

    @property
    def file(self) -> Path:
        return self.app.paths.state / "revision.json"

    def _state(self) -> dict:
        return jload(self.file, {}) or {}

    def _put(self, fn) -> dict:
        with Lock(self.app.paths.state, "revision"):
            st = self._state()
            fn(st)
            jsave(self.file, st)
        return st

    def on(self) -> bool:
        return bool(self.es.setting("revision"))

    def _quiz(self):
        return self.app.modules.get("quiz")

    # ------------------------------------------------------------------------------------------ topics
    def topics(self, slug: str, index: dict | None = None) -> tuple[list[dict], str]:
        """A course's topics in course order ({"name", "key", "note": Path or None}), and where they came from."""
        root, index = Path(self.app.workspace), {} if index is None else index
        prep = layout.path(self.app, "exam_prep", subject=slug)
        if prep.is_file():
            got = self._from_prep(prep.read_text(encoding="utf-8", errors="replace"), root, slug, index)
            if got:
                return got, layout.shown(self.app, prep)
        folder = layout.path(self.app, "lecture", subject=slug, date="2000-01-01", slug="x").parent
        if folder.is_dir():
            got = []
            for f in sorted(folder.glob("*.md")):
                if DATED.match(f.name):
                    text = f.read_text(encoding="utf-8", errors="replace")
                    got.append(self._topic(title_of(text, f), f))
            if got:
                return self._unique(got), "lecture notes"
        return self._unique(self._concepts(slug, root)), "concept notes"

    @staticmethod
    def _topic(name: str, note: Path | None) -> dict:
        return {"name": name, "key": key_of(name), "note": note}

    @staticmethod
    def _unique(got: list[dict]) -> list[dict]:
        seen, out = set(), []
        for t in got:
            if t["key"] not in seen:
                seen.add(t["key"])
                out.append(t)
        return out[:MAX_TOPICS]

    def _from_prep(self, text: str, root: Path, slug: str, index: dict) -> list[dict]:
        got, section = [], None
        for line in text.splitlines():
            if line.startswith("## "):
                m = PREP.match(line)
                section = m[1].lower() if m else None
                continue
            m = re.match(r"^\s*(?:[-*]|\d+[.)])\s+(.+)$", line)
            if not section or not m:
                continue
            links = [x[0] for x in LINK.findall(m[1])]
            name = topic_name(m[1])
            if not name or (section == "gaps" and (links == [] and len(name.split()) > 8)):
                continue  # a gap that's a sentence (sources that disagree), not a topic
            note = next((p for p in (self._find(x, root, slug, index) for x in links) if p), None)
            got.append(self._topic(name, note))
        return self._unique(got)

    def _find(self, target: str, root: Path, slug: str, index: dict) -> Path | None:
        """A [[link]]'s note: by its path in the notes folder, else by name in the subject's folder, else anywhere."""
        target = target.strip().removesuffix(".md")
        for p in (root / f"{target}.md", layout.path(self.app, "subject", subject=slug) / f"{Path(target).name}.md"):
            if p.is_file():
                return p
        if not index:
            for f in root.rglob("*.md"):
                if len(index) >= MAX_NOTES:
                    break
                if not any(x.startswith(".") for x in f.relative_to(root).parts):
                    index.setdefault(f.stem, f)
        return index.get(Path(target).name)

    def _concepts(self, slug: str, root: Path) -> list[dict]:
        """The concept graph's notes for the subject (by its books), then the other notes in the subject's folder."""
        got: list[dict] = []
        integ = self.app.modules.get("integrate")
        chap = integ.load("chapters.json", {}) if integ is not None else {}
        for key, rec in (chap or {}).items():
            if key.split("/")[0] != slug:
                continue
            for batch in rec.values():
                for rel in batch.get("concepts") or []:
                    f = root / f"{rel}.md"
                    if f.is_file():
                        got.append(self._topic(title_of(f.read_text(encoding="utf-8", errors="replace"), f), f))
        folder = layout.path(self.app, "subject", subject=slug)
        if layout.path(self.app, "concept", subject=slug, slug="x").parent == folder and folder.is_dir():
            own = {layout.path(self.app, k, subject=slug) for k in OWN_KINDS}
            for f in sorted(folder.glob("*.md")):
                if f not in own and not DATED.match(f.name) and not f.name.startswith("revision-pack"):
                    got.append(self._topic(title_of(f.read_text(encoding="utf-8", errors="replace"), f), f))
        return got

    # -------------------------------------------------------------------------------------- recall
    def _items(self, slug: str, t: dict) -> list[str]:
        """The topic's quiz items: ones that link to its note or name it."""
        quiz = self._quiz()
        if quiz is None:
            return []
        rx = studypack.pattern(studypack.topics_of(t["name"]))
        rel = self._rel(t["note"]) if t["note"] else ""
        out = []
        for iid, it in quiz.load(slug)["items"].items():
            text = str(it.get("text") or "")
            if (rel and (f"[[{rel}" in text or rel in layout.link_targets(text))) or studypack.hits(rx, text):
                out.append(iid)
        return out[:MAX_ITEMS]

    def recall(self, slug: str, t: dict, st: dict | None = None) -> float | None:
        """The topic's recall (0-5): the last grade of each of its quiz items and its own last answer, averaged."""
        grades = []
        quiz = self._quiz()
        if quiz is not None:
            items = quiz.load(slug)["items"]
            grades = [items[i]["history"][-1]["q"] for i in self._items(slug, t) if items[i].get("history")]
        own = ((st if st is not None else self._state()).get("recall") or {}).get(f"{slug}|{t['key']}")
        if own:
            grades.append(own["q"])
        return sum(grades) / len(grades) if grades else None

    def _rel(self, p: Path) -> str:
        try:
            return p.relative_to(Path(self.app.workspace)).with_suffix("").as_posix()
        except ValueError:
            return str(p)

    def ranked(self, slug: str, st: dict | None = None, index: dict | None = None) -> tuple[list[dict], str]:
        """A course's topics, ranked (each with tier, recall, why, covered: you said Yes lately)."""
        st = self._state() if st is None else st
        topics, where = self.topics(slug, index)
        since = (now().date() - dt.timedelta(days=self._int("revision_days", 14))).isoformat()
        ps, front = self._mastery()
        doubts = self._doubts(slug)
        out = []
        for i, t in enumerate(topics):
            text = t["note"].read_text(encoding="utf-8", errors="replace") if t["note"] else ""
            r = self.recall(slug, t, st)
            own = (st.get("recall") or {}).get(f"{slug}|{t['key']}") or {}
            row = {**t, "order": i, "recall": r, "tier": tier_of(bool(t["note"]), body_words(text) < STUB_WORDS, r)}
            concept = self._rel(t["note"]) if t["note"] else ""
            if concept in ps:  # exam_season.use_mastery: never moves a topic out of its tier, only within it
                row["mastery5"], row["frontier"] = round(ps[concept] * 5, 2), concept in front
            if doubts and row["tier"] == 3:  # doubts.to_revision: an open doubt about it ranks it with weak recall
                rx = studypack.pattern(studypack.topics_of(t["name"]))
                if rx and any(studypack.hits(rx, d) for d in doubts):
                    row["tier"], row["doubt"] = 2, True
            row["why"] = why_of(row)
            row["covered"] = own.get("act") == "y" and own.get("on", "") >= since
            out.append(row)
        return sorted(out, key=rank_key), where

    def _mastery(self) -> tuple[dict[str, float], set[str]]:
        """Brain's mastery of each concept with evidence, and the concepts at the frontier (mind/frontier.py), when
        exam_season.use_mastery is on and Brain's model of what you know is; else nothing. Local arithmetic only."""
        if not self.es.setting("use_mastery"):
            return {}, set()
        try:
            from kurooto.mind import frontier

            grades = frontier.grades(self.app)
            if not grades:
                return {}, set()
            return frontier.masteries(self.app), {s for s, g in grades.items() if g == frontier.FRONTIER}
        except Exception:
            return {}, set()

    def _doubts(self, slug: str) -> list[str]:
        """The subject's open doubts (the Doubt queue's note, read only), when doubts.to_revision is on."""
        d = self.app.modules.get("doubts")
        if d is None or not self.app.is_on("doubts") or not d.setting("to_revision"):
            return []
        try:
            return d.open(slug)
        except Exception:
            return []

    # ---------------------------------------------------------------------------------- what to read
    def reading(self, slug: str, t: dict, cache: dict) -> list[str]:
        """The topic's note, then class material's and books' pages that name it (the concept graph's pages too)."""
        out = [f"[[{self._rel(t['note'])}]]"] if t["note"] else []
        rx = studypack.pattern(studypack.topics_of(t["name"]))
        if "sources" not in cache:
            cache["sources"] = {}
        if slug not in cache["sources"]:
            try:
                cache["sources"][slug] = studypack.sources(self.app, slug)
            except OSError:
                cache["sources"][slug] = []
        graph = []
        integ = self.app.modules.get("integrate")
        if t["note"] and integ is not None:
            seen = cache.setdefault("seen", integ.load("seen.json", {}) or {})
            for r in seen.get(self._rel(t["note"])) or []:
                a, z = r["pages"]
                if r.get("unit") in ("parts", "slides"):  # a class file or handwritten notes (integrate.sources)
                    graph.append(r["title"] if r["unit"] == "parts" else f"{r['title']}, slides {a}-{z}")
                    continue
                graph.append(f"{r['title']}, p. {a}" if a == z else f"{r['title']}, pp. {a}-{z}")
        books = []
        for s in cache["sources"][slug] if rx else []:
            if ("texts", id(s)) not in cache:
                cache[("texts", id(s))] = s.page_texts()
            texts = cache[("texts", id(s))]
            label = s.path.name if s.is_class and s.path else s.title
            if texts:
                hit = sorted(
                    (i for i, x in enumerate(texts, 1) if studypack.hits(rx, x) >= 2),
                    key=lambda i: -studypack.hits(rx, texts[i - 1]),
                )[:MAX_PAGES]
                if hit:
                    pages = studypack.ranges(sorted(hit))
                    (out if s.is_class else books).append(f"{label}, {'p.' if len(hit) == 1 else 'pp.'} {pages}")
            elif s.path and s.is_class and studypack.hits(rx, s.path.stem.replace("-", " ").replace("_", " ")):
                out.append(label)
        return (out + graph + books)[:MAX_READ]

    # --------------------------------------------------------------------------------------- the plan
    def _int(self, key: str, default: int) -> int:
        try:
            return int(self.es.setting(key))
        except (TypeError, ValueError):
            return default

    def exams(self, t0: dt.datetime) -> list[dict]:
        """The exams the plan is for: still ahead, within revision_days, soonest first."""
        end = t0.date() + dt.timedelta(days=self._int("revision_days", 14))
        out = []
        for e in self.es.exams():
            start = e["start"] or dt.datetime.combine(e["day"], dt.time(9))
            if start > t0 and e["day"] <= end:
                out.append({**e, "at": start})
        return out

    def _free(self, t0: dt.datetime, until: dt.datetime, exams: list[dict]) -> list:
        """Start-by's free time (its window less classes and calendar events), less commitments and the exams."""
        sb = self.app.modules["startby"]
        busy = [(e["at"], e["end"] or e["at"] + dt.timedelta(hours=3)) for e in exams]
        com = self.app.modules.get("commitments")
        if com is not None and self.app.is_on("commitments"):
            day = t0.date() - dt.timedelta(days=1)
            while day <= until.date():
                busy += [(c["start_dt"], c["end_dt"]) for c in com.on(day)]
                day += dt.timedelta(days=1)
        try:
            gap = int(sb.setting("min_gap_min") or 0)
        except (TypeError, ValueError):
            gap = 30
        return minus(sb.slots(t0, until), busy, gap)

    def _blocks_for(self, e: dict) -> int:
        sb = self.app.modules["startby"]
        it = self.app.modules["deadlines"].items().get(e["id"]) or {"title": e["title"], "kind": "exam"}
        try:
            hours = sb.size_of(e["id"], {**it, "kind": it.get("kind") or "exam"})[0]
        except (KeyError, TypeError, ValueError):
            hours = 10.0
        return max(1, math.ceil(hours * 60 / max(15, self._int("block_min", 60))))

    def plan(self, t0: dt.datetime | None = None) -> tuple[list[dict], list[str]]:
        """(the blocks from now to the last exam: today's as fixed this morning, then the rest worked out now; what
        couldn't be planned, in words)."""
        t0 = t0 or now()
        exams = self.exams(t0)
        if not self.on() or not exams:
            return [], []
        st = self._state()
        day = (st.get("days") or {}).get(t0.date().isoformat())
        fixed = [self._load_block(b) for b in day["blocks"]] if day is not None else None
        start = t0 if fixed is None else max(t0, dt.datetime.combine(t0.date() + dt.timedelta(days=1), dt.time(0)))
        taken = {(b["subject"], b["key"]) for b in fixed or []}
        notes, rows, index = [], [], {}
        for e in exams:
            if not e["subject"]:
                notes.append(f"{e['title']} has no course, so no topics.")
                continue
            ranked, _ = self.ranked(e["subject"], st, index)
            todo = [t for t in ranked if not t["covered"] and (e["subject"], t["key"]) not in taken]
            if not ranked:
                notes.append(
                    f"No topics for {e['name'] or e['title']} yet: an exam prep note or lecture notes give them."
                )
            taken |= {(e["subject"], t["key"]) for t in todo}
            until = e["at"] - dt.timedelta(minutes=max(0, self._int("leave_min", 45)))
            rows.append({"id": e["id"], "until": until, "topics": todo, "n": self._blocks_for(e), "exam": e})
        if not rows:
            return fixed or [], notes
        slots = self._free(start, max(r["until"] for r in rows), exams)
        try:
            share = min(100.0, max(1.0, float(self.es.setting("revision_share") or 50))) / 100
        except (TypeError, ValueError):
            share = 0.5
        laid = lay(slots, rows, self._int("block_min", 60), share)
        by = {r["id"]: r for r in rows}
        blocks = []
        for b in laid:
            e, t = by[b["exam"]]["exam"], b["topic"]
            blocks.append(
                {
                    "start": b["start"],
                    "end": b["end"],
                    "exam": e["id"],
                    "title": e["title"],
                    "subject": e["subject"],
                    "course": e["name"] or e["subject"],
                    "key": t["key"],
                    "name": t["name"],
                    "why": t["why"],
                    "note": self._rel(t["note"]) if t["note"] else "",
                    "_topic": t,
                }
            )
        for r in rows:
            short = len(r["topics"]) - sum(1 for b in laid if b["exam"] == r["id"])
            if short > 0:
                notes.append(
                    f"{r['exam']['title']}: {short} more topic{'s' if short != 1 else ''} didn't fit (the free time "
                    "before it, or its size in Start-by)."
                )
        if fixed is None:
            today = [b for b in blocks if b["start"].date() == t0.date()]
            cache: dict = {}
            for b in today:
                b["read"] = self.reading(b["subject"], b["_topic"], cache)
            self._put(lambda s: self._keep_day(s, t0.date(), today))
            fixed = today
            blocks = [b for b in blocks if b["start"].date() != t0.date()]
        return fixed + blocks, notes

    @staticmethod
    def _save_block(b: dict) -> dict:
        return {k: (v.isoformat() if isinstance(v, dt.datetime) else v) for k, v in b.items() if not k.startswith("_")}

    @staticmethod
    def _load_block(b: dict) -> dict:
        return {**b, "start": dt.datetime.fromisoformat(b["start"]), "end": dt.datetime.fromisoformat(b["end"])}

    def _keep_day(self, st: dict, day: dt.date, blocks: list[dict]) -> None:
        days = st.setdefault("days", {})
        days[day.isoformat()] = {"blocks": [self._save_block(b) for b in blocks], "asked": False}
        old = (day - dt.timedelta(days=KEEP_DAYS)).isoformat()
        st["days"] = {k: v for k, v in days.items() if k >= old}

    def today(self, t0: dt.datetime | None = None) -> list[dict]:
        """Today's blocks (fixed the first time they're worked out today)."""
        t0 = t0 or now()
        if not self.on():
            return []
        day = (self._state().get("days") or {}).get(t0.date().isoformat())
        if day is not None:
            return [self._load_block(b) for b in day["blocks"]]
        return [b for b in self.plan(t0)[0] if b["start"].date() == t0.date()]

    # ---------------------------------------------------------------------------------------- in words
    @staticmethod
    def line(b: dict, read: bool = True) -> str:
        why = f", {b['why']}" if b.get("why") else ""
        out = f"{b['start']:%H:%M}-{b['end']:%H:%M} {b['name']} ({b['title']}{why})"
        if read and b.get("read"):
            out += ". Read: " + "; ".join(b["read"])
        return out

    def morning_rows(self) -> list[dict]:
        """For the morning page (with Start-by's): {"title", "when"}."""
        return [
            {"title": f"Revise {b['name']}", "when": f"{b['start']:%H:%M}-{b['end']:%H:%M} · for {b['title']}"}
            for b in self.today()
        ]

    def morning_lines(self) -> list[str]:
        """For the wake-up call and the drafted plan."""
        return [f"Revise {self.line(b)}" for b in self.today()]

    def overview(self) -> str:
        """/revise: today's blocks, then the next days', with what couldn't be planned."""
        if not self.on():
            return "The revision plan is off (/examseason switches it on)."
        t0 = now()
        blocks, notes = self.plan(t0)
        if not blocks and not notes:
            days = self._int("revision_days", 14)
            return f"No exam in the next {days} days, so no revision plan yet."
        out = ["Revision plan (an estimate, from your notes and free time):"] if blocks else []
        cache: dict = {}
        shown, day = 0, None
        for b in blocks:
            if shown >= 12:
                out.append(f"... and {len(blocks) - shown} more blocks.")
                break
            if b["start"].date() != day:
                day = b["start"].date()
                out.append("Today:" if day == t0.date() else f"{day:%a} {day.day} {day:%b}:")
            if "read" not in b and "_topic" in b:
                b["read"] = self.reading(b["subject"], b["_topic"], cache)
            out.append(f"- {self.line(b)}")
            shown += 1
        if not blocks:
            out.append("No free time for revision before the exams.")
        out += notes
        return "\n".join(out)

    def course(self, slug: str) -> str:
        """/revise <course>: its topics, ranked."""
        ranked, where = self.ranked(slug)
        name = self.app.modules["deadlines"].subject_name(slug) or slug
        if not ranked:
            return f"No topics for {name} yet: an exam prep note or lecture notes give them."
        rows = []
        for t in ranked[:20]:
            tags = [t["why"]] if t["why"] else []
            if t["recall"] is not None and t["tier"] != 2:
                tags.append(f"recall {t['recall']:.1f} of 5")
            if t["covered"]:
                tags.append("covered")
            rows.append(f"- {t['name']}" + (f" ({', '.join(tags)})" if tags else ""))
        more = f"\n... and {len(ranked) - 20} more." if len(ranked) > 20 else ""
        return f"{name}: {len(ranked)} topics from {where}, weakest first:\n" + "\n".join(rows) + more

    # ------------------------------------------------------------------------------- the evening question
    def ask_at(self, day: dt.date) -> dt.datetime:
        """The evening check-in's time when Check-ins is on, else night_at."""
        ev = None
        if self.app.is_on("checkins"):
            ev = ((self.app.modules["checkins"].today().get("evening") or {}).get("time")) or (
                self.app.settings.get("checkins.times") or {}
            ).get("evening")
        try:
            tm = dt.time.fromisoformat(str(ev or self.es.setting("night_at") or "21:30"))
        except ValueError:
            tm = dt.time(21, 30)
        return dt.datetime.combine(day, tm)

    def ask(self, t: dt.datetime) -> int:
        """Once a day, from ask_at: did you cover the day's topics? (Only the blocks that are over.)"""
        if not self.on() or not self.es.setting("revision_ask") or t < self.ask_at(t.date()):
            return 0
        day = (self._state().get("days") or {}).get(t.date().isoformat())
        if not day or day.get("asked"):
            return 0
        done = [(i, b) for i, b in enumerate(map(self._load_block, day["blocks"])) if b["end"] <= t]
        if not done:
            return 0
        self._put(lambda s: s["days"][t.date().isoformat()].update(asked=True))
        ref = f"{t:%Y%m%d}"
        if len(done) == 1:
            b = done[0][1]
            text = f"Revision: did you cover {b['name']} ({b['course']}) today?"
            rows = [[(SAID[a], f"rv:{ref}-{done[0][0]}:{a}") for a in SAID]]
        else:
            text = "Revision today: did you cover these?\n" + "\n".join(
                f"- {b['name']} ({b['course']}, {b['start']:%H:%M})" for _, b in done
            )
            rows = [
                [(f"{b['name'][:20]}: {SAID[a]}" if a == "y" else SAID[a], f"rv:{ref}-{i}:{a}") for a in SAID]
                for i, b in done[:8]
            ]
        self.app.notify(
            text + "\n(It counts like a quiz answer for the topic.)",
            kind="question",
            buttons=rows,
            why="exam_season.revise",
            about="revision",
        )
        self.app.events.emit("revision_asked", topics=len(done))
        return len(done)

    def answer(self, ref: str, act: str) -> str:
        """A tap: the topic's quiz items graded and its own grade kept, as a quiz answer would be (Undo kept)."""
        if act not in GRADES:
            return "That button is from an older message: /revise."
        try:
            d, i = ref.split("-")
            day = dt.datetime.strptime(d, "%Y%m%d").date().isoformat()
            b = self._state()["days"][day]["blocks"][int(i)]
        except (KeyError, ValueError, IndexError, TypeError):
            return "That revision block is gone."
        if any(u["ref"] == ref for u in self._state().get("undo") or []):
            self.undo(ref)  # another answer for the same topic replaces the first
        slug, q = b["subject"], GRADES[act]
        note = Path(self.app.workspace) / f"{b['note']}.md" if b["note"] else None
        t = {"name": b["name"], "key": b["key"], "note": note}
        quiz, before = self._quiz(), {}
        if quiz is not None:
            items = quiz.load(slug)["items"]
            for iid in self._items(slug, t):
                before[iid] = copy.deepcopy(items[iid])
                quiz.grade(slug, iid, q)
        k = f"{slug}|{b['key']}"

        def put(st: dict) -> None:
            rec = st.setdefault("recall", {})
            st["undo"] = [*(st.get("undo") or [])[-19:], {"ref": ref, "key": k, "own": rec.get(k), "items": before}]
            rec[k] = {"q": q, "act": act, "on": now().date().isoformat()}

        self._put(put)
        self.app.events.emit("revision_answered", act=act, items=len(before))
        n = f" and {len(before)} quiz item{'s' if len(before) != 1 else ''}" if before else ""
        return f"{SAID[act]}: {b['name']}. Counted like a quiz answer for the topic{n}. /revise undo takes it back."

    def undo(self, ref: str = "") -> str:
        """Take back an answer (the last one, or the one for that block): its grades go back as they were."""
        st = self._state()
        rows = st.get("undo") or []
        u = next((u for u in reversed(rows) if not ref or u["ref"] == ref), None)
        if u is None:
            return "Nothing to undo."
        slug = u["key"].split("|")[0]
        quiz = self._quiz()
        if quiz is not None and u["items"]:
            quiz.restore(slug, u["items"])

        def put(s: dict) -> None:
            rec = s.setdefault("recall", {})
            if u["own"]:
                rec[u["key"]] = u["own"]
            else:
                rec.pop(u["key"], None)
            s["undo"] = [x for x in s.get("undo") or [] if x != u]

        self._put(put)
        self.app.events.emit("revision_undone")
        return "Taken back: the topic's grades are as they were."

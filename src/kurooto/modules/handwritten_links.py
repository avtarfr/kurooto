"""Handwritten notes, linked like any other note (0.5.8). After a scan is written out (modules/handwritten.py), and once
for older transcriptions with /handwritten link, the note gets:

    a real title      from what's written, when its heading is still the scan's file name ("21 October 2026_261021_
                      105812"); the old name stays as an alias
    its subject       from when the pages were written (the PDF's dates, a time stamp in the file's name, the file's
                      time) against the timetable: during a class, or later that day, it's that class; otherwise from
                      what the pages say, against your subjects' course pages. The subject's tag and `course: <slug>`
                      go in the header.
    a ## Links list   in Kurooto's own block right after the transcription (`<!-- kurooto:linked -->`): that day's
                      lecture note, the course page, and the concept notes the pages cover, each `- [[path]]: reason`
    a ## Doubts list  what you marked "DOUBT: ..." or "???", with the page, so it can be found
    the course page   lists it under its lecture (or under "Handwritten notes"), in a block of Kurooto's own
    the graph         with "handwritten" in integrate.sources, the transcription is then read into the concept graph
                      like a book (modules/integrate.py)

Candidates come from the concept graph's own search (core/conceptgraph.py, no AI); one request to the check AI (the
concept graph's second-look AI when that's on, else your main AI) gives the title, the subject when the time doesn't
settle it, and which candidates really relate, with reasons. Every link is checked to point at a note that exists.
Nothing you wrote is changed (a write that would is refused); a before-copy of every file it changes is kept
(<state>/handwritten-undo/), and /handwritten undo puts the last linking back.

State: <state>/handwritten-links.json (what was linked to what, the course lists, requests waiting).
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import threading
import time
import uuid
from pathlib import Path

from kurooto.core import conceptgraph as cg
from kurooto.core import graphwrite as gw
from kurooto.core import integrate_ai as ai
from kurooto.core import layout
from kurooto.core.clock import now
from kurooto.core.state import jload, jsave
from kurooto.core.tools import write_note_file

# ruff: noqa: E501  (the prompt is text, not code)
PROMPT = """You are linking a student's handwritten notes (written out from a scan) into their notes. Use only what \
the notes and the cards below say.

1. A title of 3 to 8 words that says what the pages are about, in the language of the notes.
2. The subject they belong to: one slug from the subjects below, or null when none fits.
3. Which of the candidate notes the pages really cover or use, each with one specific sentence naming what connects \
them (a definition, a formula, a step). Fewer, real links beat many weak ones; none is fine.

When the pages were written: {when}

Subjects (slug, name, the opening of its course page):
{subjects}

Candidate notes:
{cards}

The handwritten notes:
{text}

Answer with ONE JSON object and nothing else: {{"title": "...", "subject": "slug or null", "links": [{{"target": \
"slug", "reason": "one specific sentence", "confidence": 0.0}}]}}
"""
KEY = "linked"  # the block after the transcription
COURSE_KEY = "handwritten-notes"  # the block on the course page
MAX_LINKS = 12
TEXT_CHARS = 12000
SLACK = dt.timedelta(minutes=10)  # a note started just before a class, or finished just after, is that class's
DOUBT = re.compile(r"\bdoubts?\b\s*[:\-–]|\?{3,}", re.I)
PAGE = re.compile(r"^## Page (\d+)\s*$")
H1 = re.compile(r"^# (.+?)\s*$", re.M)
MONTHS = "jan feb mar apr may jun jul aug sep oct nov dec".split()


# --------------------------------------------------------------------------------------- when it was written
def pdf_date(raw: str) -> dt.datetime | None:
    """A PDF date ("D:20261021105812+05'30'") as local time, or None."""
    m = re.match(r"(?:D:)?(\d{4})(\d{2})?(\d{2})?(\d{2})?(\d{2})?(\d{2})?\s*(Z|[+-])?(\d{2})?'?(\d{2})?", raw or "")
    if not m:
        return None
    try:
        t = dt.datetime(*(int(m[i] or d) for i, d in zip(range(1, 7), (0, 1, 1, 0, 0, 0), strict=True)))
    except ValueError:
        return None
    if m[7]:
        off = dt.timedelta(hours=int(m[8] or 0), minutes=int(m[9] or 0)) * (-1 if m[7] == "-" else 1)
        t = t.replace(tzinfo=dt.timezone(off)).astimezone().replace(tzinfo=None)
    return t


def name_time(name: str) -> dt.datetime | dt.date | None:
    """A time stamp in a file's name: "..._261021_105812" (a notes app's), "2026-10-21 10.58", "21 October 2026"."""
    for m in re.finditer(r"(?<!\d)(\d{2})(\d{2})(\d{2})[_-](\d{2})(\d{2})(\d{2})(?!\d)", name):
        try:
            return dt.datetime(2000 + int(m[1]), int(m[2]), int(m[3]), int(m[4]), int(m[5]), int(m[6]))
        except ValueError:
            continue
    pat = r"(?<!\d)(20\d{2})[-_.]?(\d{2})[-_.]?(\d{2})(?:[ _T-]+(\d{2})[-_.:h]?(\d{2})(?:[-_.:]?(\d{2}))?)?(?!\d)"
    for m in re.finditer(pat, name):
        try:
            if m[4]:
                return dt.datetime(int(m[1]), int(m[2]), int(m[3]), int(m[4]), int(m[5]), int(m[6] or 0))
            return dt.date(int(m[1]), int(m[2]), int(m[3]))
        except ValueError:
            continue
    for m in re.finditer(r"(?<!\d)(\d{1,2})\s+([A-Za-z]{3,9})\s+(20\d{2})", name):
        mon = m[2][:3].lower()
        if mon in MONTHS:
            try:
                return dt.date(int(m[3]), MONTHS.index(mon) + 1, int(m[1]))
            except ValueError:
                continue
    return None


def written_times(f: Path | None, names: list[str] = ()) -> list[dt.datetime | dt.date]:
    """When the pages were written, best guess first: the PDF's own dates, a stamp in the scan's name (`names`: the
    names it came in with; a copy's own name starts with the day it was written out, so it isn't asked), the file's
    time."""
    out: list[dt.datetime | dt.date] = []
    if f is None:
        return out
    if f.suffix.lower() == ".pdf" and f.is_file():
        try:
            from kurooto.core.pdfread import Pdf, text_string

            pdf = Pdf(f)
            info = pdf.get(pdf.trailer.get("Info"))
            for k in ("CreationDate", "ModDate"):
                t = pdf_date(text_string(pdf.get(info.get(k)))) if isinstance(info, dict) else None
                if t and t not in out:
                    out.append(t)
        except Exception:  # an unusual PDF: its dates are only a hint
            pass
    for name in names or [f.name]:
        t = name_time(name)
        if t and t not in out:
            out.append(t)
    try:
        out.append(dt.datetime.fromtimestamp(int(f.stat().st_mtime)))
    except OSError:
        pass
    return out


def class_for(sub, times: list) -> dict | None:
    """The class the pages belong to by time: one they were written during (any of the times), else the last one that
    ended earlier that day (by the first time). {subject, name, how: during | after, date, start, end} or None."""
    if sub is None:
        return None

    def row(c: dict, how: str) -> dict:
        return {
            "subject": c["subject"],
            "name": c["name"],
            "how": how,
            "date": c["start_dt"].date().isoformat(),
            "start": f"{c['start_dt']:%H:%M}",
            "end": f"{c['end_dt']:%H:%M}",
        }

    stamps = [t for t in times if isinstance(t, dt.datetime)]
    for t in stamps:
        for c in sub.classes_on(t.date()):
            if c["start_dt"] - SLACK <= t <= c["end_dt"] + SLACK:
                return row(c, "during")
    if stamps:
        t = stamps[0]
        before = [c for c in sub.classes_on(t.date()) if c["end_dt"] <= t]
        if before:
            return row(max(before, key=lambda c: c["end_dt"]), "after")
    return None


# ------------------------------------------------------------------------------------------------ the note
MARKED = re.compile(
    r"^((?:#{1,6}[ \t]|\*\*).*?)[ \t]+\(already in (?:\[\[[^\]]*\]\]|\[[^\]]*\]\([^)]*\))\)[ \t]*$", re.M
)


def unmark(text: str) -> str:
    """The text without the "(already in [[note]])" marks on its headings (modules/handwritten_overlap.py)."""
    return MARKED.sub(r"\1", text)


def parts(text: str, marks: bool = False) -> tuple[str, str, str] | None:
    """(head, transcription, tail): the text before Kurooto's handwritten block, the block's own text (without the
    marker lines and the "Original:" line, and without the overlap marks on its headings unless `marks`), and
    everything after its end marker. None without the block."""
    from kurooto.modules.handwritten import END, START

    i = text.find(START)
    j = text.find(END, i + 1) if i >= 0 else -1
    if i < 0 or j < 0:
        return None
    inner = text[i:j].split("\n", 1)[1] if "\n" in text[i:j] else ""
    inner = re.sub(r"\n---\nOriginal: .*\s*\Z", "", inner.rstrip(), flags=re.S).strip()
    return text[:i], inner if marks else unmark(inner), text[j + len(END) :]


def heading(head: str) -> str:
    m = H1.search(cg.FRONT.sub("", head, count=1))
    return m[1].strip() if m else ""


def head_is_ours(head: str) -> bool:
    """Is what's above the transcription only the header and the heading Kurooto wrote (nothing of yours)?"""
    rest = cg.FRONT.sub("", head, count=1).strip()
    return bool(re.fullmatch(r"# .+", rest))


def looks_like_a_file_name(title: str, names: list[str] = ()) -> bool:
    """Is this heading the scan's name rather than what it's about?"""
    from kurooto.modules.handwritten import _title

    t = (title or "").strip()
    if not t or any(t == _title(Path(n)) for n in names):
        return True
    return bool(re.search(r"\d{5,}|^(?:img|scan|untitled|document|note|page|handwritten notes)\b", t, re.I))


def doubts(transcription: str) -> list[tuple[int, str]]:
    """[(page, line)] for what you marked as a doubt ("DOUBT: ...", "???")."""
    out, page = [], 1
    for ln in transcription.splitlines():
        m = PAGE.match(ln)
        if m:
            page = int(m[1])
            continue
        if DOUBT.search(ln):
            t = re.sub(r"^\s*(?:[-*>]\s+|\d+[.)]\s+)*", "", ln).strip()
            if t:
                out.append((page, t[:300]))
    return out


def set_front(text: str, aliases: list[str], tags: list[str], course: str) -> str:
    """The note with these aliases and tags in its header (added, never removed) and `course:` set; a header is made
    when it has none."""

    def add(values: list[str], new: list[str]) -> list[str]:
        out, have = list(values), {cg.normalise(v) for v in values}
        for n in new:
            if n and cg.normalise(n) not in have:
                out.append(n)
                have.add(cg.normalise(n))
        return out

    def listed(line: str | None) -> list[str]:
        m = re.match(r"^\w+:\s*\[(.*)\]\s*$", line or "")
        return [x.strip().strip("\"'") for x in m[1].split(",") if x.strip()] if m else []

    m = cg.FRONT.match(text)
    lines = m[1].split("\n") if m else []
    body = text[m.end() :] if m else text

    def put(key: str, value: str | None) -> None:
        i = next((n for n, ln in enumerate(lines) if ln.startswith(f"{key}:")), None)
        if value is None:
            return
        if i is None:
            lines.append(f"{key}: {value}")
        elif lines[i] != f"{key}: {value}":
            lines[i] = f"{key}: {value}"

    al_line = next((ln for ln in lines if ln.startswith("aliases:")), None)
    tg_line = next((ln for ln in lines if ln.startswith("tags:")), None)
    al = add(listed(al_line), aliases)
    tg = add(listed(tg_line), tags)
    if al != listed(al_line):
        put("aliases", "[" + ", ".join(json.dumps(a, ensure_ascii=False) for a in al) + "]")
    if tg != listed(tg_line) and tg:
        put("tags", "[" + ", ".join(tg) + "]")
    if course:
        put("course", course)
    if not lines:
        return text
    return "---\n" + "\n".join(lines) + "\n---\n" + (body if m else "\n" + body)


def put_after(text: str, body: str) -> str:
    """The note with Kurooto's links block replaced, or put right after the transcription's end marker."""
    from kurooto.modules.handwritten import END

    new = gw.block(KEY, body)
    pat = re.compile(rf"<!-- kurooto:{KEY} -->.*?<!-- /kurooto:{KEY} -->", re.S)
    if pat.search(text):
        return pat.sub(lambda _: new, text, count=1)
    j = text.find(END)
    k = j + len(END)
    return text[:k] + "\n\n" + new + (text[k:] if text[k:].startswith("\n") else "\n" + text[k:])


def yours(text: str) -> str:
    """What's yours in a handwritten note: everything but its header, its heading and Kurooto's blocks."""
    p = parts(text)
    head, tail = (p[0], p[2]) if p else (text, "")
    if head_is_ours(head):
        head = ""
    else:
        head = cg.FRONT.sub("", head, count=1)
    rest = gw.BLOCK_ANY.sub("", head + "\n" + tail)
    return re.sub(r"\s+", " ", rest).strip()


def has_links(text: str) -> bool:
    return f"<!-- kurooto:{KEY} -->" in text or bool(re.search(r"^##\s+Links\s*$", text, re.M))


# ---------------------------------------------------------------------------------------------- the linker
class Linker:
    """Linking for one Handwritten module: asks the AI (through the job queue), writes what comes back."""

    def __init__(self, hw):
        self.hw = hw
        self.lock = threading.RLock()
        hw.app.jobs.then_actions["handwritten.linked"] = self.done

    @property
    def app(self):
        return self.hw.app

    @property
    def root(self) -> Path:
        return Path(self.app.workspace)

    def load(self) -> dict:
        d = jload(self.app.paths.state / "handwritten-links.json", {}) or {}
        for k in ("notes", "pending", "batches"):
            d.setdefault(k, {})
        return d

    def save(self, d: dict) -> None:
        jsave(self.app.paths.state / "handwritten-links.json", d)

    def rel(self, p: Path) -> str:
        s = layout.shown(self.app, p)
        return s[:-3] if s.endswith(".md") else s

    def brain(self) -> str:
        """The AI for linking: the concept graph's second-look AI when that's on, else your main AI ("" for none)."""
        integ = self.app.modules.get("integrate")
        if integ is not None and self.app.is_on("integrate"):
            return integ.roles()[1] or ""
        return str(self.app.settings.get("brain.main") or "")

    def index(self) -> cg.Index:
        integ = self.app.modules.get("integrate")
        if integ is not None and self.app.is_on("integrate"):
            return integ.index()  # with its embeddings and reranker, where this computer has them
        return cg.Index(cg.scan(self.app))

    def subjects(self):
        return self.app.modules.get("subjects") if self.app.is_on("subjects") else None

    # ------------------------------------------------------------------------------------------- which notes
    def transcriptions(self) -> list[Path]:
        """Every written-out note (it has Kurooto's handwritten block) in the handwritten folder."""
        into = self.hw.setting("into")
        folder = self.app.workspace / into if into else layout.path(self.app, "handwritten")
        out = []
        for f in sorted(folder.rglob("*.md")) if folder.is_dir() else []:
            try:
                if parts(f.read_text(encoding="utf-8", errors="replace")) is not None:
                    out.append(f)
            except OSError:
                continue
        return out

    def waiting(self, rel: str, st: dict) -> bool:
        """Is a linking request for this note still queued or running?"""
        jid = (st["pending"].get(rel) or {}).get("job")
        job = self.app.jobs.get(jid) if jid else None
        return job is not None and job.status in ("queued", "running")

    def unlinked(self) -> list[Path]:
        st = self.load()
        out = []
        for f in self.transcriptions():
            if has_links(f.read_text(encoding="utf-8", errors="replace")) or self.waiting(self.rel(f), st):
                continue
            out.append(f)
        return out

    def originals(self, note: Path) -> tuple[list[str], Path | None]:
        """(the names the scan had, where the original is now) for a note, from Handwritten's own records."""
        known = jload(self.app.paths.state / "handwritten-notes.json", {}) or {}
        names, where = [], None
        for name, rec in known.items():
            if Path(rec.get("note") or "") == note:
                names.append(name)
                for p in (rec.get("copy"), str(self.hw.folder() / name)):
                    if p and Path(p).is_file():
                        where = where or Path(p)
        return names, where

    # ------------------------------------------------------------------------------------------- asking
    def submit(self, note: Path, src: Path | None = None, batch: str | None = None) -> str | None:
        """Ask the AI how to link this note. The job's id, or None (linking off, no AI, not a transcription)."""
        brain = self.brain()
        if not self.hw.setting("link") or not brain:
            return None
        try:
            text = note.read_text(encoding="utf-8")
        except OSError:
            return None
        p = parts(text)
        if p is None or not p[1].strip():
            return None
        head, body, _ = p
        names, where = self.originals(note)
        if src is not None and src.name not in names:
            names.append(src.name)
        times = written_times(src if src is not None and src.is_file() else where, names)
        if not times:
            m = re.match(r"(\d{4}-\d{2}-\d{2})", note.name)
            times = [dt.date.fromisoformat(m[1])] if m else []
        sub = self.subjects()
        guess = class_for(sub, times)
        day = guess["date"] if guess else (times[0].isoformat()[:10] if times else "")
        me = self.rel(note)
        index = self.index()
        title = heading(head)
        query = "" if looks_like_a_file_name(title, names) else title
        fixed = {self.rel(x) for x in self.fixed_targets(guess["subject"] if guess else "", day)}
        cands = [
            c.slug
            for c in index.candidates(body[:4000], query, limit=MAX_LINKS + 4)
            if c.slug != me and c.slug not in fixed
        ][:MAX_LINKS]
        prompt = PROMPT.format(
            when=self.when_text(times, guess, sub),
            subjects=self.subjects_text(sub),
            cards=ai.cards_text(index, cands),
            text=body[:TEXT_CHARS],
        )
        jid = self.app.jobs.submit(
            prompt,
            title=f"Linking handwritten notes: {title[:40]}",
            effort="low",
            background=True,
            text_only=True,
            quiet=True,
            lane="chk",
            brain=brain,
            then="handwritten.linked",
            then_payload={"note": str(note), "names": names, "guess": guess, "day": day, "batch": batch or ""},
        )
        with self.lock:
            st = self.load()
            st["pending"][me] = {"job": jid, "batch": batch or ""}
            self.save(st)
        return jid

    def when_text(self, times: list, guess: dict | None, sub) -> str:
        if not times:
            return "unknown."
        t = times[0]
        out = f"{t:%A %Y-%m-%d %H:%M}" if isinstance(t, dt.datetime) else f"{t:%A %Y-%m-%d}"
        if guess:
            out += (
                f"; that is {'during' if guess['how'] == 'during' else 'after'} the {guess['name']} class "
                f"({guess['start']}-{guess['end']})"
            )
        if sub is not None:
            day = t if not isinstance(t, dt.datetime) else t.date()
            cls = [f"{c['start']}-{c['end']} {c['name']}" for c in sub.classes_on(day)]
            out += f". Classes that day: {', '.join(cls) if cls else 'none'}"
        return out + "."

    def subjects_text(self, sub) -> str:
        if sub is None:
            return "(none)"
        lay = layout.of(self.app)
        rows = []
        for s in sub.subjects()[:20]:
            course = lay.path("course", subject=s["slug"])
            n = cg.read_note(self.root, course) if course.is_file() else None
            rows.append(json.dumps({"slug": s["slug"], "name": s["name"], "course": n.summary[:200] if n else ""}))
        return "\n".join(rows) or "(none)"

    def fixed_targets(self, subject: str, day: str) -> list[Path]:
        lec = self.lecture(subject, day)
        course = self.course(subject)
        return [p for p in (lec, course) if p is not None]

    def lecture(self, subject: str, day: str) -> Path | None:
        """That day's lecture note for the subject, when there is one."""
        if not subject or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day or ""):
            return None
        probe = layout.path(self.app, "lecture", subject=subject, date=day, slug="QQSLUGQQ")
        if not probe.parent.is_dir():
            return None
        hits = sorted(probe.parent.glob(probe.name.replace("QQSLUGQQ", "*")))
        return hits[0] if hits else None

    def course(self, subject: str) -> Path | None:
        if not subject:
            return None
        p = layout.path(self.app, "course", subject=subject)
        return p if p.is_file() else None

    # ------------------------------------------------------------------------------------------- the answer
    def done(self, job, result, payload: dict) -> None:
        note = Path(payload.get("note") or "")
        batch = payload.get("batch") or ""
        data = ai.parse_json(result.text) if result.ok else None
        got = None
        if data is not None and note.is_file():
            try:
                got = self.apply(note, data, payload)
            except OSError as e:
                self.app.events.emit("handwritten_link_failed", error=str(e)[:200])
        elif data is None:
            self.app.events.emit("handwritten_link_failed", error="no usable answer")
        with self.lock:
            st = self.load()
            st["pending"].pop(self.rel(note), None)
            if got and batch:
                b = st["batches"].setdefault(batch, {"notes": 0, "lectures": 0, "concepts": 0, "titles": []})
                b["notes"] += 1
                b["lectures"] += 1 if got["lecture"] else 0
                b["concepts"] += got["concepts"]
                b["titles"].append(got["title"])
            self.save(st)
        if got:
            self.to_graph(note, got)
        if got and not batch:
            self.app.notify(got["line"], kind="result", why="handwritten.linked", about=note.name)
        elif batch:
            self.finish(batch)
        ov = getattr(self.hw, "overlap", None)
        if ov is not None:  # then what's already in your notes (modules/handwritten_overlap.py), one undo with this
            try:
                ov.after_link(note, batch=batch, undo=(got or {}).get("undo") or "")
            except Exception as e:
                self.app.events.emit("handwritten_overlap_failed", error=str(e)[:200])

    def to_graph(self, note: Path, got: dict) -> None:
        """After linking, the transcription is read into the concept graph like a book when integrate.sources has
        "handwritten" (modules/integrate.py); never fails the linking."""
        ig = self.app.modules.get("integrate")
        if ig is None or not self.app.is_on("integrate") or not got.get("subject"):
            return
        try:
            ig.take_handwritten(note, got["subject"], got["title"], got.get("day") or "")
        except Exception as e:
            self.app.events.emit("integrate_queue_failed", source="handwritten", error=str(e)[:200])

    def finish(self, batch: str) -> None:
        """When the last note of a /handwritten link run is done: one message for them all."""
        with self.lock:
            st = self.load()
            b = st["batches"].get(batch)
            if b is None or b.get("open") or any(v.get("batch") == batch for v in st["pending"].values()):
                return
            st["batches"].pop(batch, None)
            self.save(st)
        if not b["notes"]:
            return
        names = ", ".join(f"'{t}'" for t in b["titles"][:4]) + (" …" if len(b["titles"]) > 4 else "")
        self.app.notify(
            f"Linked {b['notes']} handwritten note{'s' if b['notes'] != 1 else ''} ({names}) to "
            f"{b['lectures']} lecture{'s' if b['lectures'] != 1 else ''} and {b['concepts']} concept "
            f"note{'s' if b['concepts'] != 1 else ''}. /handwritten undo takes them back.",
            kind="result",
            why="handwritten.linked",
        )

    def apply(self, note: Path, data: dict, payload: dict) -> dict | None:
        """Write the links, title and subject into the note and the course page. What was done, or None (refused)."""
        old = note.read_text(encoding="utf-8")
        p = parts(old)
        if p is None:
            return None
        head, body, _ = p
        me = self.rel(note)
        guess = payload.get("guess") or None
        sub = self.subjects()
        slugs = {s["slug"]: s for s in sub.subjects()} if sub is not None else {}
        # the subject: a class it was written in settles it; otherwise what the pages say, then the class before
        said = str(data.get("subject") or "").strip()
        said = said if said in slugs else ""
        if guess and guess.get("how") == "during" and guess.get("subject") in slugs:
            subject = guess["subject"]
        else:
            subject = said or (guess["subject"] if guess and guess.get("subject") in slugs else "")
        day = payload.get("day") or ""
        lec = self.lecture(subject, day)
        course = self.course(subject)
        # the title
        cur = heading(head)
        new_title = re.sub(r"\s+", " ", str(data.get("title") or "")).strip().lstrip("#").strip()[:80]
        title = cur
        text = old
        if (
            new_title
            and len(re.findall(r"[^\W\d_]", new_title)) >= 3
            and not looks_like_a_file_name(new_title)
            and looks_like_a_file_name(cur, payload.get("names") or [])
            and head_is_ours(head)
        ):
            title = new_title
            front = cg.FRONT.match(text)
            m = H1.search(text, front.end() if front else 0)
            text = text[: m.start()] + f"# {title}" + text[m.end() :]
        aliases = [title, cur] if title != cur else []
        text = set_front(text, aliases, ["handwritten", subject] if subject else [], subject)
        # the links
        lines: list[str] = []
        name = slugs[subject]["name"] if subject else ""
        lay = layout.of(self.app)

        def to(target: str) -> str:  # a link from this note, in your link style (notes.links)
            return lay.note_link(target, None, from_note=note)

        if lec is not None:
            on = dt.date.fromisoformat(day)
            if guess and guess.get("subject") == subject:
                how = "during" if guess["how"] == "during" else "after"
                why = f"written {how} the {name} class on {on:%a %d %b}, the lecture these pages go with"
            else:
                why = f"the {name} lecture of {on:%a %d %b}, the day these pages were written"
            lines.append(f"- {to(self.rel(lec))}: {why}")
        if course is not None:
            lines.append(f"- {to(self.rel(course))}: the course page of {name}, the subject these pages belong to")
        index_slugs = {self.rel(x) for x in (lec, course) if x is not None} | {me}
        concepts = 0
        seen: set[str] = set()
        for lk in data.get("links") or []:
            if not isinstance(lk, dict):
                continue
            t = str(lk.get("target") or "").strip().removesuffix(".md").strip("[]")
            reason = re.sub(r"\s+", " ", str(lk.get("reason") or "")).strip().rstrip(".")
            try:
                conf = float(lk.get("confidence", 0.5))
            except (TypeError, ValueError):
                conf = 0.5
            if t in index_slugs or t in seen or not (self.root / f"{t}.md").is_file() or os.path.isabs(t):
                continue
            if ".." in Path(t).parts or gw.lint_reason(reason) or conf < 0.5 or concepts >= MAX_LINKS:
                continue
            seen.add(t)
            lines.append(f"- {to(t)}: {reason}")
            concepts += 1
        qs = doubts(body)
        block = "## Links\n" + ("\n".join(lines) if lines else "(nothing in your notes matched yet)")
        if qs:
            block += "\n\n## Doubts\n" + "\n".join(f"- p. {pg}: {q}" for pg, q in qs)
        text = put_after(text, block)
        if yours(text) != yours(old):  # never: but if it would change what you wrote, nothing is written
            self.app.events.emit("handwritten_link_refused", note=note.name)
            return None
        journal: dict[str, dict] = {}
        if text != old:
            write_note_file(note, text)
            journal[str(note)] = {"old": old, "new": text}
        with self.lock:
            st = self.load()
            st["notes"][me] = {
                "title": title,
                "subject": subject,
                "lecture": self.rel(lec) if lec is not None else "",
                "day": day,
            }
            self.save(st)
            if course is not None:
                c_old = course.read_text(encoding="utf-8")
                c_new = gw.put_block(c_old, COURSE_KEY, self.course_body(subject, st))
                if c_new != c_old and gw.guarded(c_old, c_new).ok:
                    write_note_file(course, c_new)
                    journal[str(course)] = {"old": c_old, "new": c_new}
        batch = payload.get("batch") or ""
        undo_key = batch or uuid.uuid4().hex[:10]
        self.keep_undo(undo_key, journal, title)
        what = []
        if lec is not None:
            lt = cg.read_note(self.root, lec)
            short = (slugs[subject].get("aliases") or [""])[0].upper() or name
            lt_title = lt.title if lt else lec.stem
            what.append(
                f"{short} {lt_title[:1].lower() + lt_title[1:]}"
                if lt_title.lower().startswith("lecture")
                else f"the {short} lecture '{lt_title}'"
            )
        elif subject:
            what.append(f"{name}")
        what.append(f"{concepts} concept{'s' if concepts != 1 else ''}")
        line = f"Linked your handwritten notes '{title}' to {' and '.join(what)}"
        if qs:
            line += f"; {len(qs)} doubt{'s' if len(qs) != 1 else ''} listed"
        line += ". /handwritten undo takes it back."
        self.app.events.emit("handwritten_linked", concepts=concepts, lecture=lec is not None, doubts=len(qs))
        return {
            "title": title,
            "lecture": lec is not None,
            "concepts": concepts,
            "line": line,
            "subject": subject,
            "day": day,
            "undo": undo_key,
        }

    def course_body(self, subject: str, st: dict) -> str:
        """The course page's list: notes under the lecture they belong to, then the rest."""
        by_lec: dict[str, list[str]] = {}
        loose: list[str] = []
        lay = layout.of(self.app)
        course = lay.path("course", subject=subject)

        def to(target: str, label: str) -> str:  # a link from the course page, in your link style
            return lay.note_link(target, label, from_note=course)

        for rel, rec in sorted(st["notes"].items(), key=lambda kv: (kv[1].get("day") or "", kv[0])):
            if rec.get("subject") != subject or not (self.root / f"{rel}.md").is_file():
                continue
            item = to(rel, rec.get("title") or Path(rel).name)
            lec = rec.get("lecture") or ""
            if lec and (self.root / f"{lec}.md").is_file():
                by_lec.setdefault(lec, []).append(item)
            else:
                loose.append(item)
        out = ["## Handwritten notes"]
        for lec, items in by_lec.items():
            n = cg.read_note(self.root, self.root / f"{lec}.md")
            out.append(f"- {to(lec, n.title if n else Path(lec).name)}: {', '.join(items)}")
        out += [f"- {x}" for x in loose]
        return "\n".join(out)

    # ------------------------------------------------------------------------------------------------ undo
    @property
    def undo_dir(self) -> Path:
        return self.app.paths.state / "handwritten-undo"

    def keep_undo(self, key: str, journal: dict, title: str) -> None:
        """A before-copy of each file, by linking (a /handwritten link run is one): the first "old" stays."""
        if not journal:
            return
        self.undo_dir.mkdir(parents=True, exist_ok=True)
        f = self.undo_dir / f"{key}.json"
        with self.lock:
            cur = jload(f, {}) or {"files": {}, "titles": []}
            for path, rec in journal.items():
                prev = cur["files"].get(path)
                cur["files"][path] = {"old": prev["old"] if prev else rec["old"], "new": rec["new"]}
            if title not in cur["titles"]:  # the overlap marks join the linking's before-copy
                cur["titles"].append(title)
            cur["at"] = time.time()
            jsave(f, cur)
        for old in sorted(self.undo_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)[:-60]:
            old.unlink(missing_ok=True)

    def undo(self) -> str:
        """Put back the files the last linking changed (one you edited since is left as it is)."""
        files = sorted(self.undo_dir.glob("*.json"), key=lambda p: (jload(p, {}) or {}).get("at", 0))
        if not files:
            return "Nothing to undo."
        last = files[-1]
        rec = jload(last, {}) or {}
        back = kept = 0
        with self.lock:
            st = self.load()
            for path, r in (rec.get("files") or {}).items():
                p = Path(path)
                try:
                    cur = p.read_text(encoding="utf-8")
                except OSError:
                    continue
                if cur != r["new"]:
                    kept += 1
                    continue
                write_note_file(p, r["old"])
                if f"<!-- kurooto:{KEY} -->" not in r["old"]:  # (an undo of the overlap marks alone keeps the linking)
                    st["notes"].pop(self.rel(p), None)
                back += 1
                if getattr(self.hw, "overlap", None) is not None:
                    self.hw.overlap.forget(p)
            self.save(st)
        last.unlink(missing_ok=True)
        titles = ", ".join(f"'{t}'" for t in (rec.get("titles") or [])[:4])
        out = f"Took back the linking of {titles or 'your handwritten notes'} ({back} file{'s' if back != 1 else ''})."
        if kept:
            out += f" {kept} file{'s' if kept != 1 else ''} you changed since stayed as {'they are' if kept != 1 else 'it is'}."
        self.app.events.emit("handwritten_link_undone", files=back, kept=kept)
        return out

    # --------------------------------------------------------------------------------------------- command
    def link_all(self) -> str:
        """/handwritten link: every written-out note without a Links section yet, one request each."""
        if not self.hw.setting("link"):
            return "Linking is off (handwritten.link)."
        if not self.brain():
            return "Linking needs an AI: set one up under AI model."
        todo = self.unlinked()
        if not todo:
            st = self.load()
            busy = sum(1 for rel in st["pending"] if self.waiting(rel, st))
            if busy:
                return f"Already linking {busy} handwritten note{'s' if busy != 1 else ''}; nothing else to link."
            return "Every handwritten note is linked already."
        batch = f"b{now():%Y%m%d%H%M%S}-{uuid.uuid4().hex[:4]}"
        with self.lock:  # open while requests go in, so an early answer doesn't close it
            st = self.load()
            st["batches"][batch] = {"notes": 0, "lectures": 0, "concepts": 0, "titles": [], "open": True}
            self.save(st)
        n = 0
        try:
            n = sum(1 for f in todo if self.submit(f, batch=batch))
        finally:
            with self.lock:
                st = self.load()
                st["batches"].get(batch, {}).pop("open", None)
                self.save(st)
            self.finish(batch)
        if not n:
            return "Nothing to link."
        return (
            f"Linking {n} handwritten note{'s' if n != 1 else ''} to their lectures, course pages and concepts; "
            "you'll get one message when it's done."
        )

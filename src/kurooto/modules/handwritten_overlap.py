"""Handwritten notes that repeat what you have (0.9.0). Someone sends you full lecture notes for a course you already
keep notes for, again and again: after each written-out note is linked (modules/handwritten_links.py), one request to
your AI says which of its sections your notes for that course already cover, and Kurooto marks them:

    in the transcription   a covered section's heading ends "(already in [[note]])"; the text under it stays
    its own block          `<!-- kurooto:overlap -->` after the links: "## Already in your notes" (each section, the
                           note that has it and why) and "## New here" (the sections nothing else has)

The notes it compares with: the course's folder, the earlier handwritten notes of that course, and the concept notes the
concept graph's search finds for each section (no AI). Only the transcription's text and those notes' titles, openings
and headings go to the AI (the same AI linking uses).

"Only from <topic>": a text file next to the scan with its name (`notes.pdf` and `notes.txt` saying "only from Functions
of Several Variables"), a scan named "... from <topic>.pdf", or /handwritten only <file or course> from <topic>, puts the
part of the transcription from that heading on (found by a loose match) in `<!-- kurooto:only-from -->`, with the marks.
The full transcription always stays.

Switches: handwritten.overlap (the marking), handwritten.overlap_courses (only these courses; empty: every course),
handwritten.only_from (the "only from" part). Only Kurooto's parts of the new note change, never the text around them and
never another note; a write that would change yours is refused. Every write keeps a before-copy with the linking's, so
/handwritten undo takes the linking and the marks back together.

State: <state>/handwritten-overlap.json (each note's covered sections, its "only from" topic, scans waiting for one,
requests waiting).
"""

from __future__ import annotations

import difflib
import json
import re
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path

from kurooto.core import conceptgraph as cg
from kurooto.core import graphwrite as gw
from kurooto.core import integrate_ai as ai
from kurooto.core import layout
from kurooto.core.clock import now
from kurooto.core.state import jload, jsave
from kurooto.core.tools import write_note_file
from kurooto.modules import handwritten_links as hl

# ruff: noqa: E501  (the prompt is text, not code)
PROMPT = """You are comparing a student's new handwritten notes (written out from a scan) with the notes they already \
have, to mark the parts that repeat what they have. Use only what the sections and the cards below say.

For each numbered section, say whether one of the candidate notes already covers the same material: the same \
definitions, results, derivations or worked examples, not merely the same subject. A section is covered only when \
someone who has that note would learn nothing essential from the section. Give one note per covered section, with one \
specific sentence naming what both have. Leave out every section that isn't covered.

Candidate notes (slug, title, opening, headings):
{cards}

Sections of the new notes:
{sections}

Answer with ONE JSON object and nothing else: {{"covered": [{{"section": 1, "target": "slug", "reason": "one specific \
sentence", "confidence": 0.0}}]}}
"""
KEY = "overlap"  # the block with the two lists
ONLY_KEY = "only-from"  # the block with the part from a topic on
STATE = "handwritten-overlap.json"
MAX_SECTIONS = 40  # sections sent
SEARCHED = 20  # sections the candidate search runs for
MAX_CARDS = 30
SECTION_CHARS = 900
TEXT_CHARS = 12000
HEAD = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
BOLD = re.compile(r"^\*\*([^*]+)\*\*:?$")  # a line that is only bold text: how an underlined title often comes out
PAGE_TITLE = re.compile(r"^page\s+\d+$", re.I)
FENCE = re.compile(r"^\s*(```|~~~)")
STAMP = re.compile(
    r"[\s_-]*(?:\d{6}[_-]\d{6}|(?:19|20)\d{2}[-_.]?\d{2}[-_.]?\d{2}(?:[ _T-]+\d{2}[-_.:h]?\d{2}(?:[-_.:]?\d{2})?)?)\s*$"
)


@dataclass
class Section:
    title: str  # "" for the whole note, "(before the first heading)" for what comes before it
    key: str  # the title as compared (lowercase letters and digits), "#2" on a repeat; "" when it has no heading
    line: int  # its heading's line in the text, -1 without one
    text: str
    page: int  # the page it starts on (PDFs read page by page), 0 when unknown


# --------------------------------------------------------------------------------------------- reading the text
def heading_lines(text: str) -> list[tuple[int, str, str]]:
    """[(line, title, kind)]: Markdown headings ("page" for "## Page N") and lines that are only bold, outside code;
    the marks taken off."""
    out: list[tuple[int, str, str]] = []
    fence = False
    for i, ln in enumerate(text.split("\n")):
        if FENCE.match(ln):
            fence = not fence
            continue
        if fence:
            continue
        s = hl.unmark(ln).strip()
        m = HEAD.match(s)
        if m:
            t = m[2].strip().strip("*").strip()
            if t:
                out.append((i, t, "page" if PAGE_TITLE.match(t) else "head"))
            continue
        b = BOLD.match(s)
        if b and 2 <= len(b[1].strip()) <= 80:
            out.append((i, b[1].strip().rstrip(":."), "bold"))
    return out


def page_of(marks: list[tuple[int, str, str]], i: int) -> int:
    """The page line `i` is on: the last "## Page N" at or above it (0 without one)."""
    return max((int(re.sub(r"\D", "", t) or 0) for j, t, k in marks if k == "page" and j <= i), default=0)


def sections(text: str) -> list[Section]:
    """The note's sections: its headings (else its bold title lines, else its pages, else the whole note)."""
    lines = text.split("\n")
    marks = heading_lines(text)

    def page_at(i: int) -> int:
        return page_of(marks, i)

    use = (
        [m for m in marks if m[2] == "head"]
        or [m for m in marks if m[2] == "bold"]
        or [m for m in marks if m[2] == "page"]
    )
    if not use:
        return [Section("", "", -1, text.strip(), page_at(0))]
    out: list[Section] = []
    first = use[0][0]
    before = "\n".join(ln for ln in lines[:first] if not HEAD.match(ln.strip())).strip()
    if len(before) >= 80:
        out.append(Section("(before the first heading)", "", -1, before, page_at(0)))
    seen: dict[str, int] = {}
    for n, (i, t, _) in enumerate(use):
        end = use[n + 1][0] if n + 1 < len(use) else len(lines)
        k = cg.normalise(t) or f"h{n}"
        seen[k] = seen.get(k, 0) + 1
        key = k if seen[k] == 1 else f"{k}#{seen[k]}"
        out.append(Section(t, key, i, "\n".join(lines[i + 1 : end]).strip(), page_at(i)))
    return out


def mark(text: str, links: dict[str, str]) -> str:
    """The text with each section heading's mark set: "(already in <link>)" for the keys in `links`, none for the
    rest. Nothing else changes."""
    lines = text.split("\n")
    for s in sections(text):
        if s.line < 0:
            continue
        bare = hl.unmark(lines[s.line]).rstrip()
        lines[s.line] = f"{bare} (already in {links[s.key]})" if s.key in links else bare
    return "\n".join(lines)


def find_topic(text: str, topic: str) -> tuple[int, str] | None:
    """(line, heading) where `topic` starts: the heading that matches it best (the same words, one inside the other,
    or close in spelling), any kind of heading; the first one on a tie. None when nothing is close."""
    want, words = cg.normalise(topic), set(cg.words(topic))
    if not want:
        return None
    best, score = None, 0.0
    for i, t, _ in heading_lines(text):
        k = cg.normalise(t)
        if not k:
            continue
        if k == want:
            sc = 2.0
        elif min(len(k), len(want)) >= 4 and (want in k or k in want):
            sc = 1.5
        else:  # close: never as good as the same name ("page 2" is not "Page 1", though the words are the same)
            ws = set(cg.words(t))
            jac = len(ws & words) / len(ws | words) if ws | words else 0.0
            sc = min(0.99, max(difflib.SequenceMatcher(None, k, want).ratio(), jac))
        if sc > score:
            best, score = (i, t), sc
    return best if score >= 0.7 else None


def topic_in(text: str, sidecar: bool = False) -> str:
    """The topic in "only from <topic>" (or "from <topic>"); a sidecar file may say just the topic."""
    line = next((ln.strip() for ln in (text or "").splitlines() if ln.strip()), "")
    m = re.search(r"(?i)(?:^|\s)(?:only\s+)?from\s*[:\-–]?\s+(.+)$", line)
    t = m[1] if m else (line if sidecar and len(line) <= 120 else "")
    return t.strip().strip("\"'“”‘’").strip().rstrip(".").strip()


def topic_of(src: Path) -> str:
    """The "only from" a scan came with: its text file (`notes.txt`, or `notes.pdf.txt`), else its name."""
    for side in (src.with_suffix(".txt"), src.with_name(src.name + ".txt")):
        try:
            if side.is_file():
                got = topic_in(side.read_text(encoding="utf-8", errors="replace"), sidecar=True)
                if got:
                    return got
        except OSError:
            continue
    name = re.sub(r"\s+", " ", re.sub(r"_+|(?<=\w)-(?=\w)", " ", STAMP.sub("", src.stem))).strip()
    return topic_in(name)


def demote(text: str) -> str:
    """Headings one level down (under the part's own heading), outside code."""
    out, fence = [], False
    for ln in text.split("\n"):
        if FENCE.match(ln):
            fence = not fence
        elif not fence and re.match(r"^#{1,5}\s", ln):
            ln = "#" + ln
        out.append(ln)
    return "\n".join(out)


def put_after(text: str, key: str, body: str) -> str:
    """The note with this block of Kurooto's replaced, or put after the transcription and the blocks of Kurooto's
    that follow it."""
    from kurooto.modules.handwritten import END

    new = gw.block(key, body)
    pat = re.compile(rf"<!-- kurooto:{re.escape(key)}\b[^>]*-->.*?<!-- /kurooto:{re.escape(key)} -->", re.S)
    if pat.search(text):
        return pat.sub(lambda _: new, text, count=1)
    k = text.find(END) + len(END)
    while True:
        m = re.match(r"\s*<!-- kurooto:([\w.-]+)\b[^>]*-->.*?<!-- /kurooto:\1 -->", text[k:], re.S)
        if not m:
            break
        k += m.end()
    return text[:k] + "\n\n" + new + (text[k:] if text[k:].startswith("\n") else "\n" + text[k:])


def where(s: Section, paged: bool) -> str:
    return f"{s.title} (p. {s.page})" if paged and s.page else s.title


# -------------------------------------------------------------------------------------------------- the work
class Overlap:
    """Overlap marking and "only from" for one Handwritten module."""

    def __init__(self, hw):
        self.hw = hw
        self.lock = threading.RLock()
        hw.app.jobs.then_actions["handwritten.overlap"] = self.done

    @property
    def app(self):
        return self.hw.app

    @property
    def root(self) -> Path:
        return Path(self.app.workspace)

    def load(self) -> dict:
        d = jload(self.app.paths.state / STATE, {}) or {}
        for k in ("notes", "only", "scans", "pending"):
            d.setdefault(k, {})
        return d

    def save(self, d: dict) -> None:
        jsave(self.app.paths.state / STATE, d)

    def rel(self, p: Path) -> str:
        return self.hw.linker.rel(p)

    def to(self, note: Path, target: str) -> str:
        return layout.of(self.app).note_link(target, None, from_note=note)

    # ------------------------------------------------------------------------------------------- which courses
    def course_of(self, note: Path, text: str) -> str:
        """The note's course: what linking found, else `course:` in its header."""
        rec = self.hw.linker.load()["notes"].get(self.rel(note)) or {}
        front, _ = cg.parse_front(text)
        c = rec.get("subject") or front.get("course") or ""
        return c if isinstance(c, str) else ""

    def course_allowed(self, course: str) -> bool:
        """handwritten.overlap_courses: empty for every course, else only the ones named (slug, name or short name)."""
        want = self.hw.setting("overlap_courses") or []
        if isinstance(want, str):
            want = [w for w in re.split(r"[,;\n]", want)]
        want = {cg.normalise(str(w)) for w in want if str(w).strip()}
        if not want:
            return True
        if not course:
            return False
        names = {course}
        sub = self.hw.linker.subjects()
        for s in sub.subjects() if sub is not None else []:
            if s.get("slug") == course:
                names |= {s.get("name") or "", *(s.get("aliases") or [])}
        return bool({cg.normalise(n) for n in names if n} & want)

    # ------------------------------------------------------------------------------------- what it may repeat
    def notes_of(self, note: Path, course: str) -> tuple[dict[str, cg.Note], list[str]]:
        """({slug: note} for the course's folder and its earlier handwritten notes, the handwritten ones newest
        first). With no course: every other handwritten note."""
        root, me = self.root, self.rel(note)
        out: dict[str, cg.Note] = {}
        if course:
            folder = layout.path(self.app, "subject", subject=course)
            page = layout.path(self.app, "course", subject=course)
            if folder.is_dir() and root in folder.parents:
                for f in sorted(folder.rglob("*.md"))[:400]:
                    rel = f.relative_to(root)
                    if f in (page, note) or any(p.startswith(".") for p in rel.parts):
                        continue
                    n = cg.read_note(root, f)
                    if n:
                        out[n.slug] = n
        linked = self.hw.linker.load()["notes"]
        if course:
            mine = [r for r, rec in linked.items() if rec.get("subject") == course]
            mine.sort(key=lambda r: (linked[r].get("day") or "", r), reverse=True)
        else:
            mine = [self.rel(f) for f in reversed(self.hw.linker.transcriptions())]
        hand = []
        for r in mine[:400]:
            f = root / f"{r}.md"
            if r == me or not f.is_file():
                continue
            n = cg.read_note(root, f)
            if n:
                out[n.slug] = n
                hand.append(n.slug)
        return out, hand

    def candidates(self, note: Path, course: str, secs: list[Section]) -> tuple[list[str], dict[str, cg.Note]]:
        """The notes a section may repeat: per section, the best of the course's notes and of the concept notes (the
        concept graph's own search, no AI), and the newest handwritten notes of the course."""
        me = self.rel(note)
        local, hand = self.notes_of(note, course)
        indexes = []
        if local:
            indexes.append(cg.Index(local))
        try:
            indexes.append(self.hw.linker.index())
        except Exception as e:  # the concept notes are a help, not a need
            self.app.events.emit("handwritten_overlap_failed", error=str(e)[:200])
        picked: list[str] = []
        for s in secs[:SEARCHED]:
            for ix in indexes:
                for c in ix.candidates(s.text[:1500], s.title, limit=3, rerank=False):
                    if c.slug != me and c.slug not in picked:
                        picked.append(c.slug)
        for slug in hand[:6]:
            if slug not in picked:
                picked.append(slug)
        notes = dict(local)
        for ix in indexes:  # the concept notes' cards (the course's are in `local`)
            notes.update({s: ix.notes[s] for s in picked if s in ix.notes and s not in notes})
        return [s for s in picked if s in notes][:MAX_CARDS], notes

    def card(self, n: cg.Note) -> dict:
        try:
            text = n.path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        p = hl.parts(text)
        body = p[1] if p else gw.BLOCK_ANY.sub("", cg.FRONT.sub("", text, count=1))
        heads = list(dict.fromkeys(t[:80] for _, t, k in heading_lines(body) if k != "page"))
        if heads and heads[0] == n.title:
            heads = heads[1:]
        return {"slug": n.slug, "title": n.title, "opening": n.summary[:200], "headings": heads[:20]}

    # ------------------------------------------------------------------------------------------------ asking
    def submit(self, note: Path, batch: str = "", undo: str = "") -> str | None:
        """Ask the AI which sections the notes already have. The job's id, or None (off, not this course, no AI,
        nothing to compare with)."""
        if not self.hw.setting("overlap"):
            return None
        brain = self.hw.linker.brain()
        if not brain:
            return None
        try:
            text = note.read_text(encoding="utf-8")
        except OSError:
            return None
        p = hl.parts(text)
        if p is None or not p[1].strip():
            return None
        course = self.course_of(note, text)
        if not self.course_allowed(course):
            return None
        secs = sections(p[1])[:MAX_SECTIONS]
        cands, notes = self.candidates(note, course, secs)
        if not cands:
            return None
        paged = any(s.page for s in secs)
        per = max(300, min(SECTION_CHARS, TEXT_CHARS // max(1, len(secs))))
        rows = [f"[{n}] {where(s, paged) or 'the whole note'}\n{s.text[:per]}" for n, s in enumerate(secs, 1)]
        prompt = PROMPT.format(
            cards="\n".join(json.dumps(self.card(notes[s]), ensure_ascii=False, separators=(",", ":")) for s in cands),
            sections="\n\n".join(rows),
        )
        title = hl.heading(p[0]) or note.stem
        jid = self.app.jobs.submit(
            prompt,
            title=f"Handwritten notes, what's new: {title[:40]}",
            effort="low",
            background=True,
            text_only=True,
            quiet=True,
            lane="chk",
            brain=brain,
            then="handwritten.overlap",
            then_payload={
                "note": str(note),
                "keys": [s.key for s in secs],
                "cands": cands,
                "course": course,
                "batch": batch,
                "undo": undo,
            },
        )
        with self.lock:
            st = self.load()
            st["pending"][self.rel(note)] = jid
            self.save(st)
        return jid

    def waiting(self, note: Path) -> bool:
        jid = self.load()["pending"].get(self.rel(note))
        job = self.app.jobs.get(jid) if jid else None
        return job is not None and job.status in ("queued", "running")

    # ------------------------------------------------------------------------------------------------ the answer
    def done(self, job, result, payload: dict) -> None:
        note = Path(payload.get("note") or "")
        data = ai.parse_json(result.text) if result.ok else None
        with self.lock:
            st = self.load()
            st["pending"].pop(self.rel(note), None)
            self.save(st)
        if data is None:
            self.app.events.emit("handwritten_overlap_failed", error="no usable answer")
            return
        if not self.hw.setting("overlap") or not note.is_file():  # turned off meanwhile, or the note is gone
            return
        p = hl.parts(note.read_text(encoding="utf-8"))
        if p is None:
            return
        secs = sections(p[1])[:MAX_SECTIONS]
        keys = payload.get("keys") or []
        allowed = set(payload.get("cands") or [])
        me = self.rel(note)
        covered: list[dict] = []
        taken: set[int] = set()
        for c in data.get("covered") or []:
            if not isinstance(c, dict):
                continue
            try:
                n = int(c.get("section"))
                conf = float(c.get("confidence", 0.5))
            except (TypeError, ValueError):
                continue
            t = str(c.get("target") or "").strip().removesuffix(".md").strip("[]")
            reason = re.sub(r"\s+", " ", str(c.get("reason") or "")).strip().rstrip(".")
            if not 1 <= n <= len(secs) or n in taken or n > len(keys) or keys[n - 1] != secs[n - 1].key:
                continue  # a section the transcription no longer has where it was
            if t not in allowed or t == me or not (self.root / f"{t}.md").is_file() or conf < 0.5:
                continue
            if gw.lint_reason(reason):
                continue
            s = secs[n - 1]
            taken.add(n)
            covered.append({"key": s.key, "title": s.title, "page": s.page, "target": t, "reason": reason})
        rec = {
            "covered": covered,
            "sections": [{"key": s.key, "title": s.title, "page": s.page} for s in secs],
            "course": payload.get("course") or "",
            "at": f"{now():%Y-%m-%d %H:%M}",
        }
        with self.lock:
            st = self.load()
            st["notes"][me] = rec
            self.save(st)
        batch = payload.get("batch") or ""
        self.refresh(note, undo=payload.get("undo") or batch)
        self.app.events.emit("handwritten_overlap", sections=len(secs), covered=len(covered))
        if covered and not batch:
            title = hl.heading(p[0]) or note.stem
            new = [s.title for s in secs if s.key not in {c["key"] for c in covered} and s.title]
            line = (
                f"'{title}': {len(covered)} of {len(secs)} section{'s' if len(secs) != 1 else ''} "
                f"{'are' if len(covered) != 1 else 'is'} already in your notes (marked in the note)"
            )
            if new:
                line += "; new here: " + ", ".join(new[:4]) + (" …" if len(new) > 4 else "")
            self.app.notify(
                line + ". /handwritten undo takes it back.", kind="result", why="handwritten.overlap", about=note.name
            )

    # ------------------------------------------------------------------------------------------------ writing
    def overlap_body(self, note: Path, secs: list[Section], rec: dict) -> str:
        paged = any(s.page for s in secs)
        cov = {c["key"]: c for c in rec.get("covered") or []}
        have = [s for s in secs if s.key in cov]
        rest = [s for s in secs if s.key not in cov]
        out = ["## Already in your notes"]
        out += [
            f"- {where(s, paged)} → {self.to(note, cov[s.key]['target'])}: {cov[s.key]['reason']}" for s in have
        ] or ["(none of its sections)"]
        out += ["", "## New here"]
        out += [f"- {where(s, paged) or 'the whole note'}" for s in rest] or [
            "(nothing: every section is in your notes)"
        ]
        return "\n".join(out)

    def only_body(self, inner: str, topic: str) -> str:
        found = find_topic(inner, topic)
        if found is None:
            heads = [t for _, t, k in heading_lines(inner) if k != "page"][:12]
            return (
                f'## From "{topic}" on\nNo heading in these notes matches "{topic}"'
                + (f". Its headings: {'; '.join(heads)}" if heads else "")
                + ". Ask again with one of them: /handwritten only <file> from <heading>."
            )
        i, t = found
        lines = inner.split("\n")
        marks = heading_lines(inner)
        page, last = page_of(marks, i), page_of(marks, len(lines))
        where_ = f", page {page} of {last}" if page else ""
        return (
            f'## From "{t}" on\n*Only the part from this heading on{where_}; the whole transcription is above.*\n\n'
            + demote("\n".join(lines[i:]).strip())
        )

    def refresh(self, note: Path, undo: str = "") -> bool:
        """Write the marks, the lists and the "only from" part into the note's own blocks, from what's kept. True when
        the note is as it should be (written, or nothing to change)."""
        from kurooto.modules.handwritten import END, START

        with self.lock:
            try:
                old = note.read_text(encoding="utf-8")
            except OSError:
                return False
            if hl.parts(old) is None:
                return False
            rel = self.rel(note)
            st = self.load()
            rec = st["notes"].get(rel)
            topic = st["only"].get(rel, "") if self.hw.setting("only_from") else ""
            text = old
            if rec is not None and self.hw.setting("overlap"):
                i = text.find(START)
                j = text.find(END, i + 1)
                links = {c["key"]: self.to(note, c["target"]) for c in rec.get("covered") or []}
                text = text[:i] + mark(text[i:j], links) + text[j:]
                p = hl.parts(text)
                text = put_after(text, KEY, self.overlap_body(note, sections(p[1])[:MAX_SECTIONS], rec))
            if topic:
                text = put_after(text, ONLY_KEY, self.only_body(hl.parts(text, marks=True)[1], topic))
            if hl.yours(text) != hl.yours(old):  # never: but if it would change what you wrote, nothing is written
                self.app.events.emit("handwritten_overlap_refused", note=note.name)
                return False
            if text != old:
                write_note_file(note, text)
                title = hl.heading(hl.parts(text)[0]) or note.stem
                self.hw.linker.keep_undo(undo or uuid.uuid4().hex[:10], {str(note): {"old": old, "new": text}}, title)
            return True

    def forget(self, note: Path) -> None:
        """After /handwritten undo put a note back: what it no longer has isn't written again."""
        try:
            text = note.read_text(encoding="utf-8")
        except OSError:
            text = ""
        with self.lock:
            st = self.load()
            rel = self.rel(note)
            if f"<!-- kurooto:{KEY} -->" not in text:
                st["notes"].pop(rel, None)
            m = re.search(rf'<!-- kurooto:{ONLY_KEY} -->\n## From "(.+?)" on\n', text)
            if m:  # the part as it was put back
                st["only"][rel] = m[1]
            else:
                st["only"].pop(rel, None)
            self.save(st)

    # ------------------------------------------------------------------------------------------ from Handwritten
    def after_file(self, note: Path, src: Path, linking: bool) -> None:
        """A note was written out (or written again): its "only from" (a waiting /handwritten only, the text file
        next to the scan, the scan's name), the marks it had put back, and with no linking to wait for, the request."""
        rel = self.rel(note)
        with self.lock:
            st = self.load()
            topic = st["scans"].pop(src.name, "")
            if self.hw.setting("only_from"):
                topic = topic or topic_of(src)
                if topic:
                    st["only"][rel] = topic
            self.save(st)
            if rel in st["only"] or rel in st["notes"]:
                self.refresh(note)
        if not linking:
            self.submit(note)

    def after_link(self, note: Path, batch: str = "", undo: str = "") -> None:
        """Linking is done (or failed): now the overlap, with the same before-copy as the linking's."""
        if note.is_file():
            self.submit(note, batch=batch, undo=undo)

    # --------------------------------------------------------------------------------------------- the command
    def find(self, target: str) -> tuple[Path | None, str, str]:
        """(note, scan waiting to be written out, why not) for "/handwritten only <target> from ..."."""
        from kurooto.modules.handwritten import KINDS

        known = jload(self.app.paths.state / "handwritten-notes.json", {}) or {}
        notes = [
            (name, Path(rec["note"])) for name, rec in known.items() if rec.get("note") and Path(rec["note"]).is_file()
        ]
        if not target:
            return (notes[-1][1], "", "") if notes else (None, "", "There are no handwritten notes yet.")
        want = cg.normalise(target)
        for name, p in reversed(notes):
            title = hl.heading((hl.parts(p.read_text(encoding="utf-8", errors="replace")) or ("", "", ""))[0])
            if want in {cg.normalise(name), cg.normalise(Path(name).stem), cg.normalise(p.stem), cg.normalise(title)}:
                return p, "", ""
        for f in sorted(self.hw.folder().iterdir()):
            if f.suffix.lower() not in KINDS or not f.is_file() or f.name in known:
                continue
            if want in {cg.normalise(f.name), cg.normalise(f.stem)}:
                return None, f.name, ""
        sub = self.hw.linker.subjects()
        for s in sub.subjects() if sub is not None else []:
            if want in {cg.normalise(x) for x in [s["slug"], s.get("name") or "", *(s.get("aliases") or [])] if x}:
                linked = self.hw.linker.load()["notes"]
                mine = [
                    r
                    for r, rec in linked.items()
                    if rec.get("subject") == s["slug"] and (self.root / f"{r}.md").is_file()
                ]
                if not mine:
                    return None, "", f"There are no handwritten notes for {s.get('name') or s['slug']} yet."
                last = max(mine, key=lambda r: (linked[r].get("day") or "", (self.root / f"{r}.md").stat().st_mtime))
                return self.root / f"{last}.md", "", ""
        for name, p in reversed(notes):  # a part of a name, last
            if len(want) >= 4 and (want in cg.normalise(name) or want in cg.normalise(p.stem)):
                return p, "", ""
        return None, "", f"I can't find a handwritten note, a scan or a course called '{target}'."

    def only(self, rest: str) -> str:
        """/handwritten only <file or course> from <topic>."""
        if not self.hw.setting("only_from"):
            return "That's off (handwritten.only_from)."
        m = re.match(r"(?is)^(.*?)\s*\bfrom\s+(.+)$", rest.strip())
        topic = m[2].strip().strip("\"'“”‘’").strip() if m else ""
        if not topic:
            return (
                "Say which part: /handwritten only <file or course> from <topic>, for example "
                "/handwritten only calculus from Functions of Several Variables."
            )
        target = m[1].strip().strip("\"'“”‘’").strip()
        note, scan, why = self.find(target)
        if scan:
            with self.lock:
                st = self.load()
                st["scans"][scan] = topic
                self.save(st)
            return f"When {scan} is written out, its note gets the part from '{topic}' on."
        if note is None:
            return why
        p = hl.parts(note.read_text(encoding="utf-8"), marks=True)
        found = find_topic(p[1], topic) if p else None
        shown = layout.shown(self.app, note)
        if found is None:
            heads = [t for _, t, k in heading_lines(p[1] if p else "") if k != "page"][:12]
            return f"No heading in {shown} matches '{topic}'." + (
                f" Its headings: {'; '.join(heads)}." if heads else ""
            )
        with self.lock:
            st = self.load()
            st["only"][self.rel(note)] = topic
            self.save(st)
        if not self.refresh(note):
            return f"Couldn't add it to {shown}: it would have changed your own text there."
        out = f"Added the part from '{found[1]}' on to {shown}"
        rel = self.rel(note)
        if self.load()["notes"].get(rel) is None and not self.waiting(note) and self.submit(note):
            out += "; marking what's already in your notes now"
        return out + ". /handwritten undo takes it back."

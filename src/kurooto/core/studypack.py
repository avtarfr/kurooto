"""A study pack: one subject's notes and course material in a zip, with a prompt to give another AI (Claude, ChatGPT, …)
so it can write deeper notes from them. Nothing here uses your AI: it only collects files and fills in a template.

    class/         what the class gave out: lecture slides and notes, cheat sheets, problem sets, exam papers
    books/         with a topic, only each book's pages about it, as text (a whole book never goes in: it would
                   flood the other AI's context)
    notes/         your notes for the subject: its source and course notes, and any note that links to them
    PROMPT.md      what to say to the other AI, with the aim you gave ("quiz on Thursday")
    INDEX.md       every file in the pack, and what was left out and why

The material is the course's files (Classroom's copies, your files folder) and everything Books has read for the
subject. Class material and books are told apart by size, since professors post books on Classroom too: a book is long
(over 80 pages, or a title that says so: "Ch 8", "2nd edition", a download site's name), class material is short (40
pages or less, or a lecture, notes, slides, cheat sheet, quiz, assignment or exam paper). Unread files go by bytes.

With a topic (/studypack pota on thermodynamics, or an aim that names one: "quiz thermodynamics"), only what's about it
goes in: class files that mention it, the pages of each book that do (with a page either side), the notes about it
(by name, headings and text, and what the notes brain finds when it's on). Class material always comes first, in the
pack and in the prompt; books fill the gaps.

Limits: the zip stays under Telegram's 50 MB (notes first, then class material, newest first, then books; the rest is
listed in INDEX.md as left out); notes over 400 KB and files over 40 MB are left out; hidden files and folders never go
in.
"""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto.core.config import register_defaults
from kurooto.core.state import jload

if TYPE_CHECKING:
    from kurooto.app import App

MAX_ZIP = 48 * 1024 * 1024  # under Telegram's 50 MB, leaving room for the notes and the index
MAX_NOTE = 400 * 1024
MAX_FILE = 40 * 1024 * 1024
MAX_NOTES = 600  # notes read to find the ones that link to the subject
MAX_BOOK_PAGES = 200  # a topic's pages from one book, at most (its matching chapters first)
MAX_PACK_BOOK_PAGES = 250  # and from all the books together (about 900 KB of text), readings the class cites first
FILE_TYPES = {".pdf", ".pptx", ".ppt", ".docx", ".doc", ".ipynb", ".txt", ".md", ".tex", ".py", ".csv", ".png", ".jpg"}

CLASS_PAGES, BOOK_PAGES = 40, 80  # at most this long: class material; longer than this: a book
CLASS_BYTES = 8 * 1024 * 1024  # a file Books hasn't read: class material up to this size
BOOK_WORDS = re.compile(
    r"pdf ?drive|libgen|z-?lib|edition|\bed\.|isbn|textbook|handbook|\bch(?:apter)?[\s_.-]*\d|\(.*\bseries\b.*\)", re.I
)
CLASS_WORDS = re.compile(
    r"lecture|\blec[\s_-]*\d|slides?|notes|cheat|mid-?sem|end-?sem|quiz|assignment|\bhw[\s_-]*\d|homework|tutorial"
    r"|problem|worksheet|sheet|question|solution|\blab\b|handout|syllabus|exam",
    re.I,
)
# words in an aim that aren't a topic: "upcoming quiz on thursday" names none
FILLER = set(
    """a an the my our this that next upcoming coming soon quiz quizzes test tests exam exams midsem endsem mid end sem
    semester final finals viva for on in of about and or to prep prepare preparation revise revision study pack notes
    week weeks day days today tonight tomorrow morning evening monday tuesday wednesday thursday friday saturday sunday
    mon tue wed thu fri sat sun am pm at by due jan feb mar apr may jun jul aug sep sept oct nov dec class lecture
    please me i need want pdf markdown md only too also zip file files without no""".split()
)

register_defaults(
    "studypack",
    {
        "instructions": True,  # your own extra lines (studypack.extra) and a format phrase ("pdf too") go in the prompt
        "extra": "",  # your own rules for the AI, one per line, added to the end of every pack's PROMPT.md
    },
)

PROMPT = """# Study pack: {name}

{aim}I'm a university student. This zip has my own notes and the course material for **{name}**{topic}:

- `class/`: what the class gave out (lecture slides and notes, problem sets, exam papers). **This comes first**: its
  scope, emphasis, notation and conventions decide what matters.
- `books/`: books for the course{book_note}. Use them to fill gaps and go deeper, never to override the class.
- `notes/`: my notes in Markdown (`[[double brackets]]` are links between my notes).
- `INDEX.md`: every file here, and anything that didn't fit.

## What I'd like

Write advanced, rigorous study notes{scope} from these files, going beyond what my own notes say:

1. For each topic (follow the order of the lectures): the definitions, the main results with proofs or proof sketches,
   the intuition, and two worked examples.
2. The usual mistakes and the questions examiners like, on that topic (the class's own problem sets and past papers
   show what they ask).
3. Five practice problems per topic, easy to hard, with full solutions.
4. How the topics connect (what each one is needed for later), and a one-page summary of formulas.

## Rules

- Use the files. Where they leave a gap or look wrong, say so instead of guessing, and name the file for each claim.
- Where a book and the class disagree (notation, sign conventions, definitions), follow the class and point out the
  difference.
- Maths in LaTeX (`$...$`). One Markdown section per topic, so I can drop them into my notes as separate files.
- Tell me first what you plan to cover and in what order, then write it, a few topics at a time.
"""


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-") or "subject"


def _hidden(rel: Path) -> bool:
    return any(p.startswith(".") for p in rel.parts)


# ------------------------------------------------------------------------------------------- topics
def topics_of(aim: str) -> list[str]:
    """The topics an aim names: what follows "on" ("quiz on thermodynamics and radiation"), else its words that aren't
    filler ("quiz thermodynamics"). None for "quiz on thursday"."""
    aim = (aim or "").strip()
    m = re.search(r"\b(?:on|about|covering|syllabus:?|topics?:?)\s+(.+?)(?:\s+(?:for|by|before|due)\b.*)?$", aim, re.I)
    part = m.group(1) if m else aim
    out = []
    for piece in re.split(r",|;|\band\b|&|\+|/", part, flags=re.I):
        words = [w for w in re.findall(r"[A-Za-z][A-Za-z'-]*", piece) if w.lower() not in FILLER]
        if words and not all(re.fullmatch(r"\d+", w) for w in words):
            out.append(" ".join(words).lower())
    return list(dict.fromkeys(out))


def _stem(word: str) -> str:
    w = word.lower()
    return w if len(w) <= 5 else w[: max(5, len(w) - 3)]


def pattern(topics: list[str]) -> re.Pattern | None:
    """One regex for every topic: each word by its stem ("thermodynamics" finds "thermodynamic", "radiation" finds
    "radiative"), a phrase's words in order."""
    alts = []
    for t in topics:
        words = re.findall(r"[a-z][a-z'-]*", t.lower())
        if words:
            alts.append(r"\b" + r"[\s-]+".join(re.escape(_stem(w)) + r"\w*" for w in words))
    return re.compile("|".join(alts), re.I) if alts else None


def hits(rx: re.Pattern | None, text: str) -> int:
    return len(rx.findall(text)) if rx else 0


# -------------------------------------------------------------------------------------------- notes
def _other_owners(app: App, subject: str) -> set[str]:
    """The folder names of your other subjects and projects (their slugs, the subjects your books are under, the
    folders in projects/): a note kept in one of those belongs there, so a link from it to this subject doesn't bring
    it into this subject's pack (a project's book note linking the course it relates to)."""
    out: set[str] = set()
    subj = app.modules.get("subjects")
    if subj is not None:
        out |= {str(s.get("slug") or "") for s in subj.subjects()}
    books = app.modules.get("books")
    if books is not None:
        try:
            out |= {str(b.get("subject") or "") for b in books.library()}
        except Exception:  # noqa: BLE001 - a pack without this filter beats no pack
            pass
    projects = Path(app.workspace) / "projects"
    if projects.is_dir():
        out |= {p.name for p in projects.iterdir() if p.is_dir()}
    out.discard("")
    out.discard(subject)
    return out


def note_files(app: App, subject: str, rx: re.Pattern | None = None) -> list[Path]:
    """The notes for a subject: anything in a folder named for it, its course map, and notes that link to those. With
    a topic: of those, the ones about it, and any other note about it (its name, a heading or a link names it, or its
    text does three times)."""
    root = Path(app.workspace)
    found: dict[Path, None] = {}
    every = sorted(root.rglob("*.md"))
    for f in every:
        try:
            rel = f.relative_to(root)
        except ValueError:
            continue
        if _hidden(rel) or f.stat().st_size > MAX_NOTE:
            continue
        if subject in rel.parts[:-1] or rel.stem == subject:
            found[f] = None
    key = re.compile(r"\[\[[^\]]*" + re.escape(subject) + r"[^\]]*\]\]", re.I)
    others = _other_owners(app, subject)
    for f in every[: MAX_NOTES * 4]:
        if f in found or len(found) >= MAX_NOTES:
            continue
        try:
            rel = f.relative_to(root)
            if _hidden(rel) or f.stat().st_size > MAX_NOTE:
                continue
            if others & set(rel.parts[:-1]):  # another course's or project's note that mentions this one (0.6.1)
                continue
            if key.search(f.read_text(encoding="utf-8", errors="ignore")):
                found[f] = None
        except OSError:
            continue
    if rx is None:
        return list(found)
    about: dict[Path, None] = {}
    for f in [*found, *every]:
        if f in about or len(about) >= MAX_NOTES:
            continue
        try:
            rel = f.relative_to(root)
            if _hidden(rel) or f.stat().st_size > MAX_NOTE:
                continue
            text = f.read_text(encoding="utf-8", errors="ignore")
        except (OSError, ValueError):
            continue
        heads = " ".join(
            [
                rel.stem.replace("-", " "),
                *re.findall(r"(?m)^(?:#+ .*|aliases:.*|title:.*)$", text),
                *(x.replace("-", " ") for x in re.findall(r"\[\[([^\]|#]+)", text)),  # a link to a note about it
            ]
        )
        if hits(rx, heads) or hits(rx, text) >= (1 if f in found else 3):
            about[f] = None
    return list(about)


def brain_notes(app: App, topics: list[str]) -> list[Path]:
    """What the notes brain (GBrain) finds for the topics, when it's on: its answer names notes by their paths."""
    gb = app.modules.get("gbrain")
    if gb is None or not app.is_on("gbrain") or not topics:
        return []
    root, out = Path(app.workspace), []
    for t in topics[:4]:
        try:
            said = gb.search(t, n=10) or ""
        except Exception as e:  # the notes brain busy or broken: the rest of the pack doesn't need it
            app.events.emit("studypack_brain_failed", error=f"{type(e).__name__}: {e}"[:200])
            continue
        for m in re.finditer(r"[\w.-]+(?:/[\w.-]+)+", said):
            p = root / (m.group(0).removesuffix(".md") + ".md")
            try:
                if p.is_file() and not _hidden(p.relative_to(root)) and p.stat().st_size <= MAX_NOTE:
                    out.append(p)
            except (OSError, ValueError):
                continue
    return list(dict.fromkeys(out))


# ---------------------------------------------------------------------------------- course material
@dataclass
class Source:
    """A file of the course's: where it is, what Books read of it (its pages' text), and whether it's from class."""

    path: Path | None
    title: str
    pages: int = 0
    text_dir: Path | None = None  # Books' copy: pages/00001.md …
    base: Path | None = None  # the folder it came from (its place in the zip)
    is_class: bool = True
    chapters: list = field(default_factory=list)  # Books' bookmarks: [level, title, first page, last page]
    text_file: Path | None = None  # or Classroom's text of it (<file>.txt; a PDF's pages split by form feeds)

    def page_texts(self) -> list[str]:
        d = self.text_dir / "pages" if self.text_dir else None
        if d and d.is_dir():
            return [p.read_text(encoding="utf-8", errors="replace") for p in sorted(d.glob("*.md"))]
        if self.text_file and self.text_file.is_file():
            text = self.text_file.read_text(encoding="utf-8", errors="replace")
            pages = text.split("\f") if "\f" in text else [text]
            return pages[:-1] if len(pages) > 1 and not pages[-1].strip() else pages  # pdftotext ends with one
        return []


def sidecar(f: Path) -> Path | None:
    """Classroom's text of a downloaded file, kept next to it as <name>.txt."""
    s = f.with_name(f.name + ".txt")
    return s if s.is_file() else None


def words_of(name: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+\d*|\d+", name.lower()) if len(w) > 2 and not w.isdigit()}


def same_doc(a: Source, b: Source) -> bool:
    """Two copies of one file (Books' and Classroom's, maybe one a PDF of the other's slides): most of the name in
    common, and the same number of pages where both are known."""
    if a.pages and b.pages and a.pages != b.pages:
        return False
    wa, wb = words_of(f"{a.title} {a.path.name if a.path else ''}"), words_of(b.path.stem if b.path else b.title)
    return len(wa & wb) >= 3 or (bool(wa & wb) and (wa <= wb or wb <= wa))


def is_class(name: str, pages: int = 0, size: int = 0) -> bool:
    """Class material or a book, by length first (class notes are short), then what the title says, then bytes."""
    if pages > BOOK_PAGES or BOOK_WORDS.search(name):
        return False
    if CLASS_WORDS.search(name) or 0 < pages <= CLASS_PAGES:
        return True
    if pages:
        return False  # 41 to 80 pages and the title doesn't say: a book chapter more likely than a handout
    return 0 < size <= CLASS_BYTES


def course_folders(app: App, subject: str) -> list[Path]:
    from kurooto.core import layout

    out: list[Path] = []
    for p in (layout.file_dir(app, "classroom", subject=subject),):
        if p.is_dir():
            out.append(p)
    root = layout.files_root(app)
    if root and (Path(root) / subject).is_dir():
        out.append(Path(root) / subject)
    return list(dict.fromkeys(out))


def course_files(app: App, subject: str) -> list[Path]:
    """The course's files, newest first."""
    files = []
    for d in course_folders(app, subject):
        for f in d.rglob("*"):
            try:
                if (
                    f.is_file()
                    and f.suffix.lower() in FILE_TYPES
                    and not _hidden(f.relative_to(d))
                    and 0 < f.stat().st_size <= MAX_FILE
                ):
                    files.append(f)
            except OSError:
                continue
    return sorted(files, key=lambda f: (-f.stat().st_mtime, str(f)))


def sources(app: App, subject: str) -> list[Source]:
    """The course's files and what Books has read for the subject, once each, class material first, newest first."""
    read: dict[str, Source] = {}
    store = Path(app.paths.data) / "book-text" / subject
    for meta_f in sorted(store.glob("*/meta.json")) if store.is_dir() else []:
        m = jload(meta_f, {}) or {}
        f = Path(m["file"]) if m.get("file") else None
        title = str(m.get("title") or meta_f.parent.name)
        name = f.name if f else title
        s = Source(
            f if f and f.is_file() else None, title, int(m.get("pages") or 0), meta_f.parent, f.parent if f else None
        )
        s.is_class = is_class(f"{name} {title}", s.pages)
        s.chapters = [c for c in m.get("chapters") or [] if isinstance(c, list) and len(c) >= 4]
        read[str(f.resolve()) if f else meta_f.parent.name] = s
    out = list(read.values())
    files = course_files(app, subject)
    base_of = {f: d for d in course_folders(app, subject) for f in files if d in f.parents}
    texts = {sidecar(f) for f in files} - {None}
    for f in files:
        if str(f.resolve()) in read or f in texts:  # a file's text (<name>.txt) belongs to the file, not a source
            continue
        s = Source(f, f.stem, base=base_of.get(f, f.parent), text_file=sidecar(f))
        s.pages = len(s.page_texts()) if f.suffix.lower() == ".pdf" and s.text_file else 0
        s.is_class = is_class(f.name, s.pages, f.stat().st_size)
        if any(same_doc(r, s) for r in read.values()):  # Books has it already (with better text)
            continue
        out.append(s)

    def newest(s: Source) -> float:
        try:
            return -(s.path.stat().st_mtime if s.path else 0)
        except OSError:
            return 0

    return sorted(out, key=lambda s: (not s.is_class, newest(s), s.title))


NUMBER_WORDS = (
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen".split()
)
STOP = {"and", "the", "for", "with", "from", "chapter", "section", "sections", "reference", "references", "reading"}
# words that name what a book is about, not which book it is: a citation matches a book by a name (Salby, Hobbs)
GENERIC = set(
    """physics atmosphere atmospheric climate science sciences introduction introductory survey relevant potential
    temperature mass stratification notes lecture lectures course text textbook book books edition vol volume part
    advanced theory principles fundamentals thermal dynamics thermodynamics weather ocean earth planetary""".split()
)
CITE = re.compile(
    r"(?P<book>[A-Za-z][A-Za-z.&' -]{1,40}?)[\s,:]+(?:chapter|ch\.?)\s*(?P<ch>\d{1,2})\b"
    r"(?P<rest>(?:[\s,;:]*(?:and\s+)?(?:sections?|sec\.?|§)?\s*\d{1,2}(?:\.\d{1,2})+)*)",
    re.I,
)


def citations(texts: list[str]) -> list[tuple[set[str], int, list[str]]]:
    """The readings class material cites ("Reference: Salby Chapter 2", "Wallace and Hobbs Chapter 3 Section 3.2,
    3.3"): (the book's name words, chapter, sections), once each."""
    out: dict[tuple, tuple] = {}
    for text in texts:
        for m in CITE.finditer(" ".join(text.split())):
            name = {w for w in words_of(m["book"]) if w not in STOP and w not in GENERIC}
            if not name:
                continue
            secs = re.findall(r"\d{1,2}(?:\.\d{1,2})+", m["rest"] or "")
            key = (frozenset(name), int(m["ch"]))
            old = out.get(key, (name, int(m["ch"]), []))
            out[key] = (name, int(m["ch"]), sorted(set(old[2]) | set(secs)))
    return list(out.values())


def chapter_span(s: Source, ch: int, secs: list[str]) -> list[int]:
    """The pages of a chapter (or of just those sections) of a book: from its bookmarks when Books kept them, else
    from the section numbers ("3.2 The hydrostatic equation") at the top of its pages."""
    want = secs or [str(ch)]
    pages: set[int] = set()
    word = NUMBER_WORDS[ch] if ch < len(NUMBER_WORDS) else str(ch)

    def marked(x: str) -> set[int]:
        out: set[int] = set()
        for _lvl, title, first, last, *_ in s.chapters:
            tt = str(title).strip().lower()
            whole = not secs and re.match(rf"chapter\s+({ch}|{word})\b", tt)
            if whole or (secs and re.match(rf"{re.escape(x)}(\.|\s|$)", tt)):
                try:
                    out |= set(range(int(first), int(last) + 1))
                except (TypeError, ValueError):
                    continue
        return out

    for x in want:
        got = marked(x)
        while not got and secs and x.count(".") > 1:  # 1.2.1 isn't bookmarked: its section 1.2 is
            x = x.rsplit(".", 1)[0]
            got = marked(x)
        pages |= got
    if pages or s.chapters:
        return sorted(pages)
    texts = s.page_texts()
    # a section heading at the top of a page: "3.2 The hydrostatic equation" (a chapter: any "3.x Title")
    want = [x if secs else f"{x}\\.\\d+" for x in (re.escape(y) for y in want)]
    head = re.compile(r"(?m)^\s*(" + "|".join(want) + r")(\.\d+)*\s+[A-Z][a-z]")
    tops = [i for i, t in enumerate(texts, 1) if head.search(t[:600])]
    if not tops:
        return []
    lo, hi = min(tops), max(tops)
    return list(range(lo, min(hi + 1, lo + 80)))  # a chapter, not the book: a cited span stays under 80 pages


def book_tiers(s: Source, rx: re.Pattern, cited: list[tuple[set[str], int, list[str]]]) -> list[list[int]]:
    """A book's pages on the topic in three tiers, most wanted first: [what class material cites from it, its chapters
    or sections whose title names the topic (whole, from Books' bookmarks), other pages that name it twice or in a
    heading (with a page either side), those naming it most first]."""
    texts = s.page_texts()
    n = len(texts)
    mine = words_of(f"{s.title} {s.path.name if s.path else ''}")
    tier0: list[int] = []
    for name, ch, secs in cited:
        if name & mine:
            tier0 += chapter_span(s, ch, secs)
    tier0 = [p for p in dict.fromkeys(tier0) if 1 <= p <= n]
    seen = set(tier0)
    covered: list[tuple[int, int]] = []
    tier1: list[int] = []
    for _lvl, title, first, last, *_ in sorted(s.chapters, key=lambda c: c[0]):  # chapters before their sections
        try:
            first, last = int(first), int(last)
        except (TypeError, ValueError):
            continue
        if not hits(rx, str(title)) or any(a <= first and last <= b for a, b in covered):
            continue
        covered.append((first, last))
        tier1 += [p for p in range(max(1, first), min(n, last) + 1) if p not in seen]
    tier1 = list(dict.fromkeys(tier1))
    seen |= set(tier1)
    keep: set[int] = set()
    for i, t in enumerate(texts, 1):
        if hits(rx, t) >= 2 or hits(rx, " ".join(re.findall(r"(?m)^#+ .*$|^[A-Z0-9 .:-]{6,}$", t))):
            keep |= {i - 1, i, i + 1}
    tier2 = sorted((p for p in keep if 1 <= p <= n and p not in seen), key=lambda p: -hits(rx, texts[p - 1]))
    return [tier0, tier1, tier2]


def book_pages(s: Source, rx: re.Pattern, cited: list | None = None) -> list[int]:
    """The pages of a book about the topic, most wanted first (book_tiers); at most MAX_BOOK_PAGES."""
    t0, t1, t2 = book_tiers(s, rx, cited or [])
    return (t0 + t1 + t2)[:MAX_BOOK_PAGES]


def book_share(books: list[Source], rx: re.Pattern, cited: list | None = None) -> dict[int, tuple[list[int], int]]:
    """Each book's pages within MAX_PACK_BOOK_PAGES for all of them, tier by tier across the books: first what class
    material cites, then the chapters named for the topic, then an even share of the other pages (what a short book
    doesn't need going to the longer ones). {id(book): (pages, how many on the topic didn't fit)}."""
    tiers = {id(s): book_tiers(s, rx, cited or []) for s in books if s.page_texts()}
    for k, (a, b, c) in tiers.items():  # one book's own limit
        room = MAX_BOOK_PAGES
        tiers[k] = [a[:room], b[: max(0, room - len(a))], c[: max(0, room - len(a) - len(b))]]
    left = MAX_PACK_BOOK_PAGES
    chosen: dict[int, list[int]] = {k: [] for k in tiers}
    for tier in (0, 1):
        for k in sorted(tiers, key=lambda k: len(tiers[k][tier])):
            take = tiers[k][tier][:left]
            chosen[k] += take
            left -= len(take)
    rest = sorted(tiers, key=lambda k: len(tiers[k][2]))
    for i, k in enumerate(rest):
        take = tiers[k][2][: left // max(1, len(rest) - i)]
        chosen[k] += take
        left -= len(take)
    return {k: (sorted(chosen[k]), sum(len(x) for x in tiers[k]) - len(chosen[k])) for k in tiers}


def ranges(pages: list[int]) -> str:
    out, start, prev = [], None, None
    for p in pages:
        if start is None:
            start = prev = p
        elif p == prev + 1:
            prev = p
        else:
            out.append(f"{start}-{prev}" if prev != start else f"{start}")
            start = prev = p
    if start is not None:
        out.append(f"{start}-{prev}" if prev != start else f"{start}")
    return ", ".join(out)


# --------------------------------------------------------------------------------------------- pack
PLACEHOLDERS = """<!--
The prompt every study pack gives another AI, as it goes in PROMPT.md and in the message next to the zip. Edit it
freely: packs use this file from now on (/studypack prompt reset puts the default back). These words are filled in:
  {name}       the subject, e.g. Physics of the Atmosphere
  {aim}        "What it's for: <your aim>." and a blank line, or nothing
  {aim_text}   just your aim, e.g. quiz on thermodynamics
  {topic}      ", narrowed to **<topics>**", or nothing
  {topics}     the topics, e.g. thermodynamics, lapse rate (or nothing)
  {book_note}  what the books/ folder holds
  {scope}      " on <topics>", or " for this course"
Your own rules (studypack.extra) and a format phrase in what you type ("pdf too", "markdown only") are added at the end.
Lines inside these comment markers are left out.
-->
"""


def prompt_file(app: App) -> Path:
    from kurooto.core import layout

    return layout.path(app, "study_pack_prompt")


def prompt_template(app: App | None) -> str:
    """Your own prompt (the study_pack_prompt note) when you made one, else Kurooto's."""
    if app is not None:
        try:
            f = prompt_file(app)
            if f.is_file():
                text = re.sub(r"<!--.*?-->\s*", "", f.read_text(encoding="utf-8"), flags=re.S).strip()
                if text:
                    return text + "\n"
        except OSError:
            pass
    return PROMPT


FORMAT_MD = re.compile(r"\b(?:markdown|md)\s+only\b|\bno\s+pdf\b|\bwithout\s+(?:a\s+)?pdf\b", re.I)
FORMAT_PDF = re.compile(r"\bpdf\b", re.I)
FORMAT_ONE = re.compile(r"\b(?:one|single)\s+(?:markdown\s+)?file\b", re.I)


def run_extra(aim: str) -> list[str]:
    """Rules for this one pack from how you phrased it: "pdf too", "markdown only", "one file"."""
    out = []
    if FORMAT_MD.search(aim or ""):
        out.append("Reply with Markdown only: one section per topic; no PDF and no zip.")
    elif FORMAT_PDF.search(aim or ""):
        out.append("Also give me the finished notes as a PDF, besides the Markdown.")
    if FORMAT_ONE.search(aim or ""):
        out.append("Put everything in one Markdown file.")
    return out


def extra_lines(app: App | None, aim: str = "") -> list[str]:
    """Your own lines (studypack.extra) and this pack's format phrase, when studypack.instructions is on."""
    if app is not None and not app.settings.get("studypack.instructions"):
        return []
    mine = str((app.settings.get("studypack.extra") if app is not None else "") or "")
    return [ln.strip(" -*\t") for ln in mine.splitlines() if ln.strip(" -*\t")] + run_extra(aim)


def prompt_text(name: str, aim: str = "", topics: list[str] | None = None, app: App | None = None) -> str:
    """The prompt for another AI, as it goes in PROMPT.md (and, on its own, in the chat next to the zip): your own
    (prompt_file) when you made one."""
    if topics is None:
        topics = topics_of(aim)
    aim_text = aim.strip().rstrip(".")
    shown = ", ".join(topics)
    words = {
        "name": name,
        "aim": f"What it's for: {aim_text}.\n\n" if aim_text else "",
        "aim_text": aim_text,
        "topic": f", narrowed to **{shown}**" if topics else "",
        "topics": shown,
        "book_note": " (only their pages on the topic, as text, with the page numbers)"
        if topics
        else " (none: name a topic)",
        "scope": f" on {shown}" if topics else " for this course",
    }
    text = prompt_template(app)
    for k, v in words.items():  # plain replacing: a LaTeX {x} in your prompt stays as it is
        text = text.replace("{" + k + "}", v)
    more = extra_lines(app, aim)
    if more:  # your own rules, at the end of the prompt, whatever template it is
        text = text.rstrip("\n") + "\n\n## My extra instructions\n\n" + "\n".join(f"- {ln}" for ln in more) + "\n"
    return text


def make_prompt_file(app: App, reset: bool = False) -> tuple[Path, bool]:
    """Write Kurooto's prompt as your study_pack_prompt note to edit (unless it's there and not reset). Returns (its
    path, whether it was written now)."""
    f = prompt_file(app)
    if f.is_file() and not reset:
        return f, False
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(PLACEHOLDERS + "\n" + PROMPT, encoding="utf-8")
    return f, True


def build(
    app: App,
    subject: str,
    name: str = "",
    aim: str = "",
    dest: Path | None = None,
    limit: int | None = -1,
    topics: list[str] | None = None,
) -> tuple[Path, dict]:
    """Write the zip. topics: what to narrow it to (None: from the aim; []: everything). Returns (its path, {"notes",
    "files", "class", "books", "topics", "left_out": [(name, why)]}); ValueError if there's nothing to put in it."""
    subject = slug(subject)
    limit = MAX_ZIP if limit == -1 else limit  # -1: Telegram's size; None: no limit (it goes to Drive)
    name = name or subject.replace("-", " ").title()
    topics = topics_of(aim) if topics is None else [t for t in topics if t.strip()]
    rx = pattern(topics)
    notes = note_files(app, subject, rx)
    notes += [n for n in brain_notes(app, topics) if n not in notes]
    srcs = sources(app, subject)
    if not notes and not srcs:
        raise ValueError(f"I found no notes or course files for {name}.")
    dest = dest or Path(app.paths.cache) / "study-packs" / f"{subject}-study-pack.zip"
    dest.parent.mkdir(parents=True, exist_ok=True)
    root = Path(app.workspace)
    used: set[str] = set()
    index: dict[str, list[str]] = {"class": [], "books": [], "notes": []}
    out: list[tuple[str, str]] = []
    whole: list[str] = []  # books not packed: a whole book would flood the other AI's context

    def arc(prefix: str, name_in: str) -> str:
        a = f"{prefix}/{name_in}"
        stem, dot, ext = name_in.rpartition(".")
        n = 2
        while a.lower() in used:
            a = f"{prefix}/{stem or name_in}-{n}{dot}{ext}" if dot else f"{prefix}/{name_in}-{n}"
            n += 1
        used.add(a.lower())
        return a

    def rel_in(s: Source) -> str:
        try:
            return s.path.relative_to(s.base).as_posix() if s.base else s.path.name
        except ValueError:
            return s.path.name

    total = 0
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED, compresslevel=6, strict_timestamps=False) as z:
        for f in notes:
            a = arc("notes", f.relative_to(root).as_posix())
            z.write(f, a)
            total += f.stat().st_size
            index["notes"].append(f"- {a}")
        cited = citations([x for s in srcs if s.is_class for x in s.page_texts()]) if rx else []
        share = book_share([s for s in srcs if not s.is_class], rx, cited) if rx else {}
        for s in srcs:
            where = "class" if s.is_class else "books"
            texts = s.page_texts() if rx else []
            if rx and not s.is_class and texts:  # a book: only its pages on the topic, as text
                pages, cut = share.get(id(s), ([], 0))
                if cut:
                    out.append(
                        (
                            s.title,
                            f"{cut} more pages on the topic: the books together keep to "
                            f"{MAX_PACK_BOOK_PAGES} pages, what the other AI can hold at once",
                        )
                    )
                if not pages:
                    continue
                body = f"# {s.title}: pages {ranges(pages)}\n\n" + "\n\n".join(
                    f"<!-- page {p} -->\n{texts[p - 1].strip()}" for p in pages
                )
                data = body.encode("utf-8")
                if limit and total + len(data) > limit:
                    out.append((s.title, "the zip would pass Telegram's 50 MB"))
                    continue
                a = arc("books", f"{slug(s.title)}-pages.md")
                z.writestr(a, data)
                total += len(data)
                index["books"].append(f"- {a}: pages {ranges(pages)} of {s.pages}")
                continue
            if not s.is_class:  # a whole book would flood the other AI's context: never in, only its pages above
                why = "not read by Books yet, so its pages on the topic can't be picked" if rx else "name a topic"
                whole.append(f"- {s.title}" + (f" ({s.pages} pages)" if s.pages else "") + f": {why}")
                continue
            if rx:  # class material: in if its title names the topic, or its text does twice
                named = hits(rx, f"{s.title} {s.path.name if s.path else ''}")
                if not named and (sum(hits(rx, t) for t in texts) if texts else 0) < 2:
                    continue
            if s.path is None:
                continue
            try:
                size = s.path.stat().st_size
            except OSError:
                continue
            if size > MAX_FILE:
                out.append((s.path.name, "over 40 MB"))
                continue
            if limit and total + size > limit:
                out.append((s.path.name, "the zip would pass Telegram's 50 MB"))
                continue
            a = arc(where, rel_in(s))
            z.write(s.path, a)
            total += size
            index[where].append(f"- {a} ({size // 1024} KB" + (f", {s.pages} pages)" if s.pages else ")"))
        head = f"# Index: {name}" + (f", narrowed to {', '.join(topics)}" if topics else "")
        text = [head + "\n"]
        for part, title in (("class", "Class material (first)"), ("books", "Books"), ("notes", "Your notes")):
            text += ["", f"## {title}\n", *(index[part] or ["(none)"])]
        if whole:
            text += ["", "## Books not packed whole (they'd flood the AI's context; name a topic for their pages)\n"]
            text += whole
        if out:
            text += ["", "## Left out\n", *(f"- {n}: {why}" for n, why in out)]
        z.writestr("INDEX.md", "\n".join(text) + "\n")
        z.writestr("PROMPT.md", prompt_text(name, aim, topics, app))
    n_class, n_books = len(index["class"]), len(index["books"])
    if rx and not (index["notes"] or n_class or n_books):
        dest.unlink(missing_ok=True)
        raise ValueError(f"I found nothing about {', '.join(topics)} in {name}'s notes or course material.")
    return dest, {
        "notes": len(index["notes"]),
        "files": n_class + n_books,
        "class": n_class,
        "books": n_books,
        "topics": topics,
        "left_out": out,
    }

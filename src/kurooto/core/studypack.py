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

What the class material cites comes first among a book's pages, topic or not: "Salby Chapter 2", or a syllabus's
abbreviated readings ("B&D S2.3", or a table with a column per book), matched to a book by its authors and turned into
its pages (citations(), cited_pages()); up to studypack.cited_pages, past the books' usual 250 pages. INDEX.md lists
each citation and what it became. An aim that's a whole syllabus picks book pages by citation only (broad()).

Limits: the zip stays under Telegram's 50 MB (notes first, then class material, newest first, then books; the rest is
listed in INDEX.md as left out) and files over 40 MB are left out, unless the pack goes to Drive (build(limit=None)),
where nothing is left out for size; notes over 400 KB are always left out; hidden files and folders never go in.
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
# why a file was left out for size (build's left_out), so a reply can count them by reason
OVER_ZIP = "the zip would pass Telegram's 50 MB"
OVER_FILE = "over 40 MB"
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
        # pages of the readings class material cites (a syllabus's "B&D S2.3"), taken whole before other book pages,
        # past the usual 250; 0: off (cited pages share the 250 and need a topic, as before 0.8.13)
        "cited_pages": 400,
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


def _course(text: str) -> str:
    """The subject a note's header gives it (`course: linear-algebra`, or a link to its course page), as a slug."""
    m = re.match(r"---\n(.*?)\n---", text, re.S)
    course = re.search(r"(?m)^course:[ \t]*(.+)$", m[1]) if m else None
    return slug(course[1].strip(" \t[]\"'").split("|")[0].split("/")[-1]) if course else ""


def _elsewhere(rel: Path, text: str, subject: str, others: set[str]) -> bool:
    """A note that belongs to another subject or project: kept in its folder, or its header says so (`course: <it>`,
    as handwritten notes get, or tags naming another subject and not this one). It doesn't come into this subject's
    pack because its words or the notes brain match the topic."""
    if others & set(rel.parts[:-1]):
        return True
    m = re.match(r"---\n(.*?)\n---", text, re.S)
    if not m:
        return False
    name = _course(text)
    if name == subject:
        return False
    if name in others:
        return True
    tags = re.search(r"(?m)^tags:[ \t]*(.+)$", m[1])
    named = {slug(t.split("/")[-1]) for t in re.findall(r"[\w/-]+", tags[1])} if tags else set()
    return subject not in named and bool(others & named)


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
            text = f.read_text(encoding="utf-8", errors="ignore")
            if (key.search(text) or _course(text) == subject) and not _elsewhere(rel, text, subject, others):
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
        if f not in found and _elsewhere(rel, text, subject, others):  # another subject's note on the same words
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


def brain_notes(app: App, topics: list[str], subject: str = "") -> list[Path]:
    """What the notes brain (GBrain) finds for the topics, when it's on: its answer names notes by their paths. With a
    subject, not the notes that belong to another one (_elsewhere)."""
    gb = app.modules.get("gbrain")
    if gb is None or not app.is_on("gbrain") or not topics:
        return []
    root, out = Path(app.workspace), []
    others = _other_owners(app, subject) if subject else set()
    for t in topics[:4]:
        try:
            said = gb.search(t, n=10) or ""
        except Exception as e:  # the notes brain busy or broken: the rest of the pack doesn't need it
            app.events.emit("studypack_brain_failed", error=f"{type(e).__name__}: {e}"[:200])
            continue
        for m in re.finditer(r"[\w.-]+(?:/[\w.-]+)+", said):
            p = root / (m.group(0).removesuffix(".md") + ".md")
            try:
                rel = p.relative_to(root)
                if not p.is_file() or _hidden(rel) or p.stat().st_size > MAX_NOTE:
                    continue
                if subject and _elsewhere(rel, p.read_text(encoding="utf-8", errors="ignore"), subject, others):
                    continue
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
    _texts: list[str] | None = field(default=None, init=False, repr=False, compare=False)  # read once

    def page_texts(self) -> list[str]:
        if self._texts is None:
            self._texts = self._read()
        return self._texts

    def _read(self) -> list[str]:
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


def course_files(app: App, subject: str, any_size: bool = False) -> list[Path]:
    """The course's files, newest first. any_size: files over MAX_FILE too (a pack takes them when it goes to Drive,
    and says it left them out when it doesn't)."""
    files = []
    for d in course_folders(app, subject):
        for f in d.rglob("*"):
            try:
                if (
                    f.is_file()
                    and f.suffix.lower() in FILE_TYPES
                    and not _hidden(f.relative_to(d))
                    and 0 < f.stat().st_size
                    and (any_size or f.stat().st_size <= MAX_FILE)
                ):
                    files.append(f)
            except OSError:
                continue
    return sorted(files, key=lambda f: (-f.stat().st_mtime, str(f)))


def sources(app: App, subject: str, any_size: bool = False) -> list[Source]:
    """The course's files and what Books has read for the subject, once each, class material first, newest first.
    any_size: course files over MAX_FILE too."""
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
    files = course_files(app, subject, any_size)
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
# a syllabus's abbreviations: "B&D: Brockwell & Davis (Third Ed., 2016)." and its code legend: "C: Chapter, S: Section,
# D: Definition, P: Paragraph, E: Example", "SA = section in appendix A"
ABBREV = re.compile(r"(?<![\w&])([A-Z][A-Z&]{1,9})\s*[:=]\s*([A-Z][^():;=]{2,80}?)\s*\(")
NOT_NAMES = {"and", "the", "ed", "eds", "et", "al", "with"}
ITEMS = "definition example theorem lemma proposition corollary remark exercise problem figure table equation"
LEGEND = re.compile(
    r"(?<![A-Za-z&])([A-Z]{1,2})\s*[:=]\s*(?i:(chapter|section|paragraph|" + ITEMS.replace(" ", "|") + r")s?"
    r"(?:\s+(?:in|of)\s+appendix\s+([A-Za-z])\b)?)"
)
DEFAULT_LEGEND = {
    "C": ("chapter", "", ""),
    "S": ("section", "", ""),
    "D": ("item", "Definition", ""),
    "E": ("item", "Example", ""),
    "P": ("opening", "", ""),
}
AMP_ABBR = r"[A-Z]{1,4}(?:&[A-Z]{1,4})+"  # B&D, S&S, BJR&L: an abbreviation even without its block
SEP = re.compile(r"[\s,;]*(?:(?:and|&)\s+)?")
MAX_CHAPTER, MAX_SECTION = 80, 40  # a cited chapter or section stays under this many pages
BROAD_TOPICS, BROAD_AIM = 8, 300  # an aim past these is a whole syllabus: citations pick the books' pages


@dataclass(frozen=True)
class Cite:
    """One reading class material cites: a chapter, a section, an item (Definition 1.11, Example 3.2.2) or a chapter's
    opening (its first paragraph), of the book its names (authors' surnames, or a name like Salby) point to."""

    names: frozenset
    kind: str  # chapter | section | item | opening
    num: str  # "3", "2.3", "A.3", "1.11"
    code: str  # as the class wrote it: "S2.3", "C3 P1", "Chapter 2"
    label: str = ""  # an item's word: "Definition"
    abbr: str = ""  # the syllabus's short name for the book: "B&D"

    @property
    def book(self) -> str:
        return self.abbr or " ".join(sorted(self.names)).title()

    def __str__(self) -> str:
        return f"{self.book} {self.code}"


def _abbreviations(flat: str) -> dict[str, frozenset]:
    """{"B&D": {"brockwell", "davis"}}: an abbreviation counts when its letters are its authors' initials."""
    out: dict[str, frozenset] = {}
    for m in ABBREV.finditer(flat):
        names = [w.lower() for w in re.findall(r"[A-Z][A-Za-z'’-]+", m[2]) if w.lower() not in NOT_NAMES]
        letters = [c.lower() for c in m[1] if c.isalpha()]
        if names and len(letters) >= 2 and all(any(n.startswith(c) for n in names) for c in letters):
            out.setdefault(m[1], frozenset(names))
    return out


def _legend(flat: str) -> dict[str, tuple[str, str, str]]:
    """The code letters: {"S": ("section", "", ""), "D": ("item", "Definition", ""), "SA": ("section", "", "A")}."""
    out = dict(DEFAULT_LEGEND)
    for m in LEGEND.finditer(flat):
        word, app = m[2].lower(), (m[3] or "").upper()
        if word in ("chapter", "section"):
            out[m[1]] = (word, "", app)
        elif word == "paragraph":
            out[m[1]] = ("opening", "", "")
        else:
            out[m[1]] = ("item", word.title(), "")
    return out


def _token_rx(legend: dict) -> re.Pattern:
    letters = "|".join(sorted(legend, key=lambda x: (-len(x), x)))
    return re.compile(
        rf"(?<![\w.&])(?P<code>{letters})(?P<num>(?:[A-Z]\.?)?\d{{1,2}}(?:\.\d{{1,3}})*|\.\d{{1,2}}(?:\.\d{{1,3}})*)"
        r"(?![\w&])"
        r"|(?i:chapter|ch\.?)\s*(?P<ch>\d{1,2})(?![\w]|\.\d)"
        r"|(?i:sections?|sec\.?|§)\s*(?P<sec>(?:[A-Z]\.)?\d{1,2}(?:\.\d{1,3})*)(?![\w]|\.\d)"
        r"|(?<![\w.])(?P<bare>\d{1,2}(?:\.\d{1,3})*)(?![\w]|\.\d)"
    )


def _run(text: str, pos: int, tok: re.Pattern) -> tuple[list[re.Match], int]:
    """The codes one after another from pos ("S2.3, C3", "3.5 and 3.6"), and where they end."""
    got: list[re.Match] = []
    while True:
        t = tok.match(text, SEP.match(text, pos).end())
        if not t:
            return got, pos
        got.append(t)
        pos = t.end()


def _cites_of(toks: list[re.Match], abbr: str, names: frozenset, legend: dict) -> list[Cite]:
    """The codes in one table cell or after one book's name ("C3 P1": chapter 3 and its opening)."""
    out: list[Cite] = []
    chapter = ""
    for t in toks:
        if t["code"]:
            kind, label, app = legend[t["code"]]
            num = t["num"].lstrip(".")
            if re.fullmatch(r"[A-Z]\d.*", num):  # SA3: appendix A, section 3
                num = num[0] + "." + num[1:]
            if app and not num.startswith(app):
                num = f"{app}.{num}"
            code = t[0]
        elif t["ch"]:
            kind, label, num, code = "chapter", "", t["ch"], f"Chapter {t['ch']}"
        elif t["sec"]:
            kind, label, num, code = "section", "", t["sec"], f"Section {t['sec']}"
        else:  # a bare number after a book's name: 3.5 a section, 3 a chapter
            num = t["bare"]
            kind, label, code = ("section" if "." in num else "chapter"), "", num
        if num.split(".")[0] in ("0", "00"):  # no chapter 0 or section 0.x: a number from a table of marks
            continue
        if kind == "chapter":
            if not num.isdigit():
                continue
            chapter = num
        if kind == "opening":
            out.append(Cite(names, kind, chapter, f"C{chapter} {code}" if chapter else code, "", abbr))
            continue
        out.append(Cite(names, kind, num, code, label, abbr))
    return out


def _table_row(line: str, cols: list[tuple[int, str]], tok: re.Pattern) -> list[tuple[str, list[re.Match]]]:
    """A table row's cells of codes, each under its column's book: in layout text, the column whose heading starts
    where the cell does (the rightmost one starting at or before it); in plain text, cells in order when there are as
    many as columns."""
    out = []
    left = cols[0][0] - 6
    for cell in re.finditer(r"\S+(?: \S+)*", line):  # cells: text runs two spaces apart
        if cell.start() < left:
            continue
        toks, end = _run(cell[0], 0, tok)
        if not toks or cell[0][end:].strip(" .,;"):
            continue
        at = [c for c in cols if c[0] <= cell.start() + 3]
        col = at[-1] if at else min(cols, key=lambda c: abs(c[0] - cell.start()))
        out.append((col[1], toks))
    if out:
        return out
    groups: list[list[re.Match]] = []
    words = line.split()
    while words:  # plain text: the codes at the end of the row, a cell each ("S2.3, C3" one cell)
        toks, end = _run(words[-1], 0, tok)
        if not toks or words[-1][end:].strip(".,;"):
            break
        if words[-1].endswith(",") and groups:
            groups[0] = toks + groups[0]
        else:
            groups.insert(0, toks)
        words.pop()
    if groups and len(groups) == len(cols) and words:
        return [(c[1], g) for c, g in zip(cols, groups, strict=True)]
    return []


def citations(texts: list[str]) -> list[Cite]:
    """The readings class material cites, once each: "Reference: Salby Chapter 2", "Wallace and Hobbs Chapter 3
    Section 3.2, 3.4", and a syllabus's abbreviated ones, inline ("B&D S2.3", "S&S 3.5") or as a table with a column
    per book (a heading row naming the abbreviations, codes under them: C3 a chapter, S2.3 a section, D1.11 a
    definition, E3.2.2 an example, C3 P1 chapter 3's opening, SA.3 section A.3 of the appendix), the abbreviations and
    code letters read from the syllabus's own legend ("B&D: Brockwell & Davis (Third Ed., 2016)", "C: Chapter")."""
    flat = " ".join(" ".join(texts).split())
    abbrs = _abbreviations(flat)
    legend = _legend(flat)
    tok = _token_rx(legend)
    known = "|".join(re.escape(a) for a in sorted(abbrs, key=len, reverse=True))
    # a book's abbreviation: those the syllabus spells out, and any "X&Y" (matched to a book by its letters, if any)
    head = re.compile(rf"(?<![\w&])(?:{known + '|' if known else ''}{AMP_ABBR})(?![\w&])(?!\s*[:=])")
    out: dict[tuple, Cite] = {}

    def add(cs: list[Cite]) -> None:
        for c in cs:
            out.setdefault((c.abbr, c.names, c.kind, c.num, c.label), c)

    for text in texts:
        cols: list[tuple[int, str]] = []  # a table's columns end with its document (an exam's numbers aren't cells)
        rest = []
        for line in text.split("\n"):
            heads = [(m.start(), m[0]) for m in head.finditer(line)]
            if len(heads) >= 2 and not any(_run(line, m.end(), tok)[0] for m in head.finditer(line)):
                cols = heads  # a table's heading row: a column per book
                continue
            row = _table_row(line, cols, tok) if cols else []
            if row:
                for abbr, toks in row:  # in a table only coded cells count: a bare "0.5" is a number, not a reading
                    add(_cites_of([t for t in toks if not t["bare"]], abbr, abbrs.get(abbr, frozenset()), legend))
                continue
            rest.append(line)
        joined = " ".join(" ".join(rest).split())
        for m in head.finditer(joined):  # inline: "B&D S2.3, C3", "S&S 3.5"
            toks, _ = _run(joined, m.end(), tok)
            add(_cites_of(toks, m[0], abbrs.get(m[0], frozenset()), legend))
        for m in CITE.finditer(joined):  # by name: "Salby Chapter 2"
            name = frozenset(w for w in words_of(m["book"]) if w not in STOP and w not in GENERIC)
            if not name:
                continue
            secs = re.findall(r"\d{1,2}(?:\.\d{1,2})+", m["rest"] or "")
            if secs:
                add([Cite(name, "section", x, f"Section {x}") for x in secs])
            else:
                add([Cite(name, "chapter", m["ch"], f"Chapter {m['ch']}")])
    return list(out.values())


# --------------------------------------------------------------------------------- a cited book's pages
def _key(num: str) -> tuple:
    return tuple((1, ord(x)) if x.isalpha() else (0, int(x)) for x in num.split(".") if x)


def _under(num: str, x: str) -> bool:
    return num == x or num.startswith(x + ".")


def _next(num: str, x: str) -> bool:
    """A heading that can end x: after it and not under it, in its chapter or the next one (or an appendix): a stray
    "5.2 Mar" in a table of chapter 3 doesn't end section 3.2."""
    if _under(num, x) or _key(num) <= _key(x):
        return False
    a, b = _key(num)[0], _key(x)[0]
    return a == b or a[0] > b[0] or a[1] == b[1] + 1


SEC_HEAD = re.compile(r"(?m)^[ \t]*(?:§[ \t]*)?((?:[A-Z]\.)?\d{1,2}(?:\.\d{1,3})+|[A-Z]\.\d{1,2})\.?[ \t]+(?=[A-Z(*])")
CHAPTER_HEAD = re.compile(
    r"(?m)^[ \t]*(?:\d{1,4}[ \t]+)?(?i:chapter)[ \t]+(\d{1,2}|(?i:"
    + "|".join(NUMBER_WORDS[1:])
    + r"))\b[.:]?[ \t]*(?:$|[A-Z])"
)
# a contents page: lines with dot leaders, or numbered headings ending in a page number ("2.3 ARMA Processes 45")
TOC_LINE = re.compile(
    r"(?m)^.*\S(?:[ \t]*\.){3,}[ \t]*\d{1,4}[ \t]*$"
    r"|^[ \t]*(?i:chapter[ \t]+)?(?:[A-Z]\.)?\d{1,2}(?:\.\d{1,3})*\.?[ \t]+\S.*\S[ \t]+\d{1,4}[ \t]*$"
)


def _not_listed(t: str) -> list[tuple[int, str]]:
    """A page's section headings, without a list of them (a chapter's opening page listing its sections: three or
    more headings a line or two apart, numbers rising)."""
    found = [(m.start(), m[1], t.count("\n", 0, m.start())) for m in SEC_HEAD.finditer(t)]
    out, run = [], []
    for h in [*found, None]:
        if h and run and h[2] - run[-1][2] <= 2 and _key(h[1]) > _key(run[-1][1]):
            run.append(h)
            continue
        if len(run) < 3:
            out += [(pos, x) for pos, x, _ in run]
        run = [h] if h else []
    return out


class _Book:
    """A book's page texts with what citations need found once: its section headings ("2.3 ARMA Processes", also a
    running head), its "Chapter 3" headings, and which pages are its contents (skipped)."""

    def __init__(self, s: Source, texts: list[str] | None = None):
        self.s = s
        self.texts = texts if texts is not None else s.page_texts()
        self.n = len(self.texts)
        self.heads: list[tuple[int, int, str]] = []  # (page, place on it, "2.3")
        self.chapter_heads: list[tuple[int, str]] = []
        for p, t in enumerate(self.texts, 1):
            if re.search(r"(?im)^\s*(?:table of )?contents\b", t[:400]) or len(TOC_LINE.findall(t)) >= 6:
                continue
            self.heads += [(p, pos, x) for pos, x in _not_listed(t)]
            here = {
                str(NUMBER_WORDS.index(x)) if x in NUMBER_WORDS else x
                for x in (m[1].lower() for m in CHAPTER_HEAD.finditer(t[:400]))
            }
            if len(here) == 1:  # one chapter's heading (a page naming several is a preface or a list)
                self.chapter_heads.append((p, here.pop()))

    def marked(self, x: str, whole: bool) -> list[int]:
        """From Books' bookmarks: chapter x ("Chapter 3 …", "3 ARIMA Models"), or section x and what's under it."""
        out: set[int] = set()
        word = NUMBER_WORDS[int(x)] if whole and x.isdigit() and int(x) < len(NUMBER_WORDS) else x
        for _lvl, title, first, last, *_ in self.s.chapters:
            tt = str(title).strip().lower()
            if whole:
                hit = re.match(rf"(?:chapter\s+)?(?:{re.escape(x)}|{word})(?:[.:]?\s|$)", tt)
            else:
                hit = re.match(rf"{re.escape(x.lower())}(?:\.|\s|$)", tt)
            if hit:
                try:
                    out |= set(range(int(first), int(last) + 1))
                except (TypeError, ValueError):
                    continue
        return sorted(p for p in out if 1 <= p <= self.n)

    def section(self, x: str) -> list[int]:
        """Section x: from its heading to the next heading after it that isn't under it (that page too: the next one
        often starts mid-page)."""
        got = self.marked(x, whole=False)
        if got:
            return got[:MAX_SECTION]
        start = next((i for i, h in enumerate(self.heads) if h[2] == x), None)
        if start is None:
            start = next((i for i, h in enumerate(self.heads) if _under(h[2], x)), None)
        if start is None:
            return []
        first = self.heads[start][0]
        last = min(self.n, first + 15)  # the last section before the index: a guess
        for p, _pos, num in self.heads[start + 1 :]:
            if _next(num, x):
                last = p
                break
        return list(range(first, min(last, first + MAX_SECTION - 1) + 1))

    def chapter(self, x: str) -> list[int]:
        """Chapter x: its bookmark, else from its "Chapter x" heading to the next chapter's, else from its first
        section heading (x.1 …) to the page before the next chapter's."""
        got = self.marked(x, whole=True)
        if got:
            return got[:MAX_CHAPTER]
        first = next((p for p, c in self.chapter_heads if c == x), None)
        if first is not None:
            last = next((p - 1 for p, c in self.chapter_heads if p > first and c != x), None)
            if last is None:
                last = next((p - 1 for p, _pos, n in self.heads if p > first and _next(n.split(".")[0], x)), self.n)
            return list(range(first, min(max(first, last), first + MAX_CHAPTER - 1) + 1))
        start = next((i for i, h in enumerate(self.heads) if h[2].split(".")[0] == x), None)
        if start is None:
            return []
        first = self.heads[start][0]
        last = next((p - 1 for p, _pos, n in self.heads[start + 1 :] if p > first and _next(n.split(".")[0], x)), None)
        if last is None:
            last = min(self.n, first + 30)
        return list(range(first, min(last, first + MAX_CHAPTER - 1) + 1))

    def item(self, label: str, num: str) -> list[int]:
        """The page where "Definition 1.11" is (where it starts a line, if anywhere), and the next page."""
        rx = re.compile(rf"(?<![\w.]){re.escape(label)}\.?[ \t]*{re.escape(num)}(?![\w]|\.\d)", re.I)
        own = re.compile(r"(?m)^[ \t]*" + rx.pattern, re.I)
        p = next((i for i, t in enumerate(self.texts, 1) if own.search(t)), None)
        p = p or next((i for i, t in enumerate(self.texts, 1) if rx.search(t)), None)
        return [x for x in (p, p + 1) if x <= self.n] if p else []

    def resolve(self, c: Cite) -> tuple[list[int], str]:
        """The pages a citation names, and a note when it's found another way ("as 1.5.1")."""
        if c.kind == "chapter":
            return self.chapter(c.num), ""
        if c.kind == "opening":
            return (self.chapter(c.num)[:2], "") if c.num else ([], "it doesn't say which chapter")
        if c.kind == "item":
            return self.item(c.label, c.num), ""
        x = c.num
        while True:
            got = self.section(x)
            if got or x.count(".") < 2:
                return got, (f"as {x}: {c.num} has no heading of its own" if got and x != c.num else "")
            x = x.rsplit(".", 1)[0]

    def chapters_of(self, cites: list[Cite]) -> set[int]:
        """The chapters these citations are in, whole: where pages about the topic may come from as well."""
        out: set[int] = set()
        for x in {c.num.split(".")[0] for c in cites if c.num}:
            if x.isdigit():
                out |= set(self.chapter(x))
        return out


def _initials(abbr: str) -> str:
    return "".join(c for c in abbr.lower() if c.isalpha())


def _book_score(s: Source, texts: list[str], abbr: str, names: frozenset) -> int:
    """How surely a book is the one a citation means: its authors' surnames in its title, even misspelt ("Brockfield"
    for Brockwell: the first five letters), the abbreviation's letters as a word of it ("Tsa Ss" for S&S), or at
    least two of the surnames on its first pages. 0: not this book."""
    toks = set(re.findall(r"[a-z]+", f"{s.title} {s.path.name if s.path else ''}".lower()))
    t = sum(any(w == n or (len(n) >= 5 and len(w) >= 5 and w[:5] == n[:5]) for w in toks) for n in names)
    i = int(len(_initials(abbr)) >= 2 and _initials(abbr) in toks)
    front = " ".join(texts[:8]).lower()
    x = sum(bool(re.search(rf"\b{re.escape(n)}\b", front)) for n in names) if names else 0
    if not (t or i or x >= max(2, -(-len(names) // 2))):
        return 0
    return 3 * t + 3 * i + x


def _match(books: list[_Book], cited: list[Cite]) -> dict[tuple, list[_Book]]:
    """Which book each cited name means: a syllabus's abbreviations one book each, the surest first (a book's preface
    naming another book's authors doesn't take it); a name in a lecture ("Salby") every book with it in the title."""
    keys = list(dict.fromkeys((c.abbr, c.names) for c in cited))
    out: dict[tuple, list[_Book]] = {k: [] for k in keys}
    pairs = []
    for k in keys:
        for b in books:
            score = _book_score(b.s, b.texts, *k)
            if score and k[0]:
                pairs.append((score, keys.index(k), b))
            elif score:
                out[k].append(b)  # by name: every book it names
    taken: set[int] = set()
    for _score, ki, b in sorted(pairs, key=lambda x: -x[0]):
        if not out[keys[ki]] and id(b) not in taken:
            out[keys[ki]].append(b)
            taken.add(id(b))
    return out


@dataclass
class CitedPlan:
    """What the class cites, read against the books: each book's cited pages, a line per citation for INDEX.md, and
    the chapters each cited book's other pages may come from."""

    pages: dict[int, list[int]] = field(default_factory=dict)
    lines: list[str] = field(default_factory=list)
    within: dict[int, set[int]] = field(default_factory=dict)

    @property
    def found(self) -> bool:
        return any(self.pages.values())


def cited_pages(books: list[Source], cited: list[Cite]) -> CitedPlan:
    """Each citation's pages in the book it means, in the order the class gives them; and for each, a line saying
    what it resolved to, or why it couldn't be ("B&D E3.2.2 (…): not found in the book's text")."""
    plan = CitedPlan()
    if not cited:
        return plan
    read = [_Book(s) for s in books]
    match = _match(read, cited)
    mine: dict[int, list[Cite]] = {}
    for c in cited:
        found = match.get((c.abbr, c.names)) or []
        if not found:
            if c.names:  # an "X&Y" no syllabus spells out and no book's title has is likely not a book ("Q&A 2")
                who = ", ".join(n.title() for n in sorted(c.names))
                plan.lines.append(f"- {c}: no book in Books matches it ({who})")
            continue
        for b in found:
            if not b.texts:
                plan.lines.append(f"- {c} ({b.s.title}): not read by Books yet, so its pages can't be found")
                continue
            pages, note = b.resolve(c)
            mine.setdefault(id(b.s), []).append(c)
            if not pages:
                why = f"not found in the book's text ({note})" if note else "not found in the book's text"
                plan.lines.append(f"- {c} ({b.s.title}): {why}")
                continue
            have = plan.pages.setdefault(id(b.s), [])
            have += [p for p in pages if p not in have]
            plan.lines.append(f"- {c} → {b.s.title}: pages {ranges(pages)}" + (f" ({note})" if note else ""))
    for b in read:
        if plan.pages.get(id(b.s)):
            plan.within[id(b.s)] = b.chapters_of(mine.get(id(b.s), [])) | set(plan.pages[id(b.s)])
    return plan


def book_tiers(
    s: Source,
    rx: re.Pattern | None,
    cited: list[Cite],
    tier0: list[int] | None = None,
    within: set[int] | None = None,
    scattered: bool = True,
) -> list[list[int]]:
    """A book's pages in three tiers, most wanted first: [what class material cites from it, its chapters or sections
    whose title names the topic (whole, from Books' bookmarks), other pages that name it twice or in a heading (with a
    page either side), those naming it most first]. within: the topic's pages only from these (a book the syllabus
    cites: its cited chapters). scattered=False: no third tier."""
    texts = s.page_texts()
    n = len(texts)
    if tier0 is None:
        tier0 = cited_pages([s], cited).pages.get(id(s), [])
    tier0 = [p for p in dict.fromkeys(tier0) if 1 <= p <= n]
    if rx is None:
        return [tier0, [], []]
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
    tier1 = [p for p in dict.fromkeys(tier1) if within is None or p in within]
    seen |= set(tier1)
    keep: set[int] = set()
    for i, t in enumerate(texts, 1) if scattered else ():
        if hits(rx, t) >= 2 or hits(rx, " ".join(re.findall(r"(?m)^#+ .*$|^[A-Z0-9 .:-]{6,}$", t))):
            keep |= {i - 1, i, i + 1}
    tier2 = sorted(
        (p for p in keep if 1 <= p <= n and p not in seen and (within is None or p in within)),
        key=lambda p: -hits(rx, texts[p - 1]),
    )
    return [tier0, tier1, tier2]


def book_pages(s: Source, rx: re.Pattern, cited: list | None = None) -> list[int]:
    """The pages of a book about the topic, most wanted first (book_tiers); at most MAX_BOOK_PAGES."""
    t0, t1, t2 = book_tiers(s, rx, cited or [])
    return (t0 + t1 + t2)[:MAX_BOOK_PAGES]


def book_share(
    books: list[Source],
    rx: re.Pattern | None,
    cited: list | None = None,
    cap: int = 0,
    plan: CitedPlan | None = None,
    scattered: bool = True,
) -> dict[int, tuple[list[int], int, int]]:
    """Each book's pages, tier by tier across the books. cap (studypack.cited_pages): what class material cites goes in
    whole first, up to cap pages for all the books, past MAX_PACK_BOOK_PAGES; then the chapters named for the topic and
    an even share of the other pages fill what's left of MAX_PACK_BOOK_PAGES (what a short book doesn't need going to
    the longer ones). A book the syllabus cites gives its other pages only from the chapters it cites. cap 0: cited
    pages share MAX_PACK_BOOK_PAGES with the rest (before 0.8.13). {id(book): (pages, how many on the topic didn't
    fit, how many of those were cited)}."""
    plan = plan if plan is not None else cited_pages(books, cited or [])
    tiers = {
        id(s): book_tiers(s, rx, [], plan.pages.get(id(s), []), plan.within.get(id(s)), scattered)
        for s in books
        if s.page_texts()
    }
    for k, (a, b, c) in tiers.items():  # one book's own limit: cited pages past it when cap is set
        room = MAX_BOOK_PAGES
        a = a if cap else a[:room]
        tiers[k] = [a, b[: max(0, room - len(a))], c[: max(0, room - len(a) - len(b))]]
    chosen: dict[int, list[int]] = {k: [] for k in tiers}
    if cap:
        left = cap
        for k in sorted(tiers, key=lambda k: len(tiers[k][0])):
            take = tiers[k][0][:left]
            chosen[k] += take
            left -= len(take)
        left = max(0, MAX_PACK_BOOK_PAGES - sum(len(v) for v in chosen.values()))
        order = (1,)
    else:
        left = MAX_PACK_BOOK_PAGES
        order = (0, 1)
    for tier in order:
        for k in sorted(tiers, key=lambda k: len(tiers[k][tier])):
            take = tiers[k][tier][:left]
            chosen[k] += take
            left -= len(take)
    rest = sorted(tiers, key=lambda k: len(tiers[k][2]))
    for i, k in enumerate(rest):
        take = tiers[k][2][: left // max(1, len(rest) - i)]
        chosen[k] += take
        left -= len(take)
    out = {}
    for k in tiers:
        got = set(chosen[k])
        out[k] = (
            sorted(got),
            sum(len(x) for x in tiers[k]) - len(chosen[k]),
            len([p for p in tiers[k][0] if p not in got]),
        )
    return out


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


def broad(topics: list[str], aim: str = "") -> bool:
    """An aim that's a whole syllabus pasted in: too many topics to pick pages by their words."""
    return len(topics) > BROAD_TOPICS or len(aim or "") > BROAD_AIM


def shown_topics(topics: list[str]) -> str:
    """The topics as a pack names them: a whole syllabus's by its first few."""
    if len(topics) > BROAD_TOPICS:
        return ", ".join(topics[:6]) + f" and {len(topics) - 6} more"
    return ", ".join(topics)


def prompt_text(
    name: str, aim: str = "", topics: list[str] | None = None, app: App | None = None, cited: bool = False
) -> str:
    """The prompt for another AI, as it goes in PROMPT.md (and, on its own, in the chat next to the zip): your own
    (prompt_file) when you made one. cited: the books/ folder holds the readings class material cites."""
    if topics is None:
        topics = topics_of(aim)
    aim_text = aim.strip().rstrip(".")
    shown = shown_topics(topics)
    if cited and topics and not broad(topics, aim):
        book_note = (
            " (the sections the class material cites, then their pages on the topic, as text, with the page numbers)"
        )
    elif cited:
        book_note = " (the sections the class material cites, as text, with the page numbers)"
    elif topics:
        book_note = " (only their pages on the topic, as text, with the page numbers)"
    else:
        book_note = " (none: name a topic)"
    words = {
        "name": name,
        "aim": f"What it's for: {aim_text}.\n\n" if aim_text else "",
        "aim_text": aim_text,
        "topic": f", narrowed to **{shown}**" if topics else "",
        "topics": shown,
        "book_note": book_note,
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
    wide = broad(topics, aim)  # a whole syllabus: its words only rank class files and notes; citations pick pages
    rank = pattern(topics)
    rx = None if wide else rank

    def rank_of(text: str) -> int:
        return -hits(rank, text)

    if wide:  # all the subject's notes, those naming the most topics first
        notes = note_files(app, subject)
        notes.sort(key=lambda f: rank_of(f.read_text(encoding="utf-8", errors="ignore")))
    else:
        notes = note_files(app, subject, rx)
        notes += [n for n in brain_notes(app, topics, subject) if n not in notes]
    srcs = sources(app, subject, any_size=True)  # a file over MAX_FILE is left out below, and INDEX.md says so
    if wide:
        srcs.sort(key=lambda s: (not s.is_class, rank_of(" ".join(s.page_texts())) if s.is_class else 0))
    cap = max(0, int(app.settings.get("studypack.cited_pages") or 0))
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
        books = [s for s in srcs if not s.is_class]
        cited = citations([x for s in srcs if s.is_class for x in s.page_texts()])
        plan = cited_pages(books, cited) if cited and books else CitedPlan()
        # the books' pages: by citation, and by the topic's words unless the aim is a whole syllabus (then only the
        # chapters named for it, and only when the class cites nothing that could be found)
        book_rx = rank if wide and not plan.found else rx
        use_books = bool(book_rx) or bool(cap and plan.found)
        share = book_share(books, book_rx, cited, cap, plan, scattered=not wide) if use_books else {}
        for s in srcs:
            where = "class" if s.is_class else "books"
            texts = s.page_texts() if (rx or use_books) else []
            if use_books and not s.is_class and texts:  # a book: only its pages cited or on the topic, as text
                pages, cut, cut0 = share.get(id(s), ([], 0, 0))
                why = []
                if cut0:
                    why.append(f"{cut0} cited pages past studypack.cited_pages ({cap})")
                if cut - cut0:
                    why.append(
                        f"{cut - cut0} more pages on the topic: the books together keep to "
                        f"{MAX_PACK_BOOK_PAGES} pages, what the other AI can hold at once"
                    )
                if why:
                    out.append((s.title, "; ".join(why)))
                if not pages:
                    if not rx:  # no topic, and the class cites nothing in it
                        whole.append(
                            f"- {s.title}" + (f" ({s.pages} pages)" if s.pages else "") + ": the class cites nothing "
                            "in it that could be found; name a topic for its pages"
                        )
                    continue
                body = f"# {s.title}: pages {ranges(pages)}\n\n" + "\n\n".join(
                    f"<!-- page {p} -->\n{texts[p - 1].strip()}" for p in pages
                )
                data = body.encode("utf-8")
                if limit and total + len(data) > limit:
                    out.append((s.title, OVER_ZIP))
                    continue
                a = arc("books", f"{slug(s.title)}-pages.md")
                z.writestr(a, data)
                total += len(data)
                index["books"].append(f"- {a}: pages {ranges(pages)} of {s.pages}")
                continue
            if not s.is_class:  # a whole book would flood the other AI's context: never in, only its pages above
                why = "not read by Books yet, so its pages can't be picked" if rx or use_books else "name a topic"
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
            if limit and size > MAX_FILE:  # Drive (no limit) takes any size
                out.append((s.path.name, OVER_FILE))
                continue
            if limit and total + size > limit:
                out.append((s.path.name, OVER_ZIP))
                continue
            a = arc(where, rel_in(s))
            z.write(s.path, a)
            total += size
            index[where].append(f"- {a} ({size // 1024} KB" + (f", {s.pages} pages)" if s.pages else ")"))
        head = f"# Index: {name}" + (f", narrowed to {shown_topics(topics)}" if topics else "")
        text = [head + "\n"]
        for part, title in (("class", "Class material (first)"), ("books", "Books"), ("notes", "Your notes")):
            text += ["", f"## {title}\n", *(index[part] or ["(none)"])]
        if cited:
            text += ["", "## Readings the class cites\n", *(plan.lines or ["- (no book in Books matches them)"])]
            if not use_books and not cap:
                text += ["", "(Their pages aren't in this pack: studypack.cited_pages is 0 and no topic was named.)"]
        if whole:
            text += ["", "## Books not packed whole (they'd flood the AI's context; name a topic for their pages)\n"]
            text += whole
        if out:
            text += ["", "## Left out\n", *(f"- {n}: {why}" for n, why in out)]
        z.writestr("INDEX.md", "\n".join(text) + "\n")
        z.writestr("PROMPT.md", prompt_text(name, aim, topics, app, cited=bool(index["books"]) and plan.found))
    n_class, n_books = len(index["class"]), len(index["books"])
    if rx and not (index["notes"] or n_class or n_books):
        dest.unlink(missing_ok=True)
        raise ValueError(f"I found nothing about {shown_topics(topics)} in {name}'s notes or course material.")
    return dest, {
        "notes": len(index["notes"]),
        "files": n_class + n_books,
        "class": n_class,
        "books": n_books,
        "topics": topics,
        "left_out": out,
        "cited": bool(index["books"]) and plan.found,  # the books/ folder holds what the class cites
        "broad": wide,
    }

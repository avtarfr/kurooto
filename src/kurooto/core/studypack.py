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
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto.core.state import jload

if TYPE_CHECKING:
    from kurooto.app import App

MAX_ZIP = 48 * 1024 * 1024  # under Telegram's 50 MB, leaving room for the notes and the index
MAX_NOTE = 400 * 1024
MAX_FILE = 40 * 1024 * 1024
MAX_NOTES = 600  # notes read to find the ones that link to the subject
MAX_BOOK_PAGES = 150  # a topic's pages from one book, at most
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
    please me i need want""".split()
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
    for f in every[: MAX_NOTES * 4]:
        if f in found or len(found) >= MAX_NOTES:
            continue
        try:
            rel = f.relative_to(root)
            if _hidden(rel) or f.stat().st_size > MAX_NOTE:
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

    def page_texts(self) -> list[str]:
        d = self.text_dir / "pages" if self.text_dir else None
        if not d or not d.is_dir():
            return []
        return [p.read_text(encoding="utf-8", errors="replace") for p in sorted(d.glob("*.md"))]


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
        read[str(f.resolve()) if f else meta_f.parent.name] = s
    out = list(read.values())
    base_of = {f: d for d in course_folders(app, subject) for f in course_files(app, subject) if d in f.parents}
    for f in course_files(app, subject):
        if str(f.resolve()) in read:
            continue
        out.append(Source(f, f.stem, base=base_of.get(f, f.parent), is_class=is_class(f.name, size=f.stat().st_size)))

    def newest(s: Source) -> float:
        try:
            return -(s.path.stat().st_mtime if s.path else 0)
        except OSError:
            return 0

    return sorted(out, key=lambda s: (not s.is_class, newest(s), s.title))


def book_pages(s: Source, rx: re.Pattern) -> list[int]:
    """The pages of a book about the topic (1-based): a page that names it twice, or once in a heading, with the page
    either side; at most MAX_BOOK_PAGES."""
    texts = s.page_texts()
    keep: set[int] = set()
    for i, t in enumerate(texts, 1):
        if hits(rx, t) >= 2 or hits(rx, " ".join(re.findall(r"(?m)^#+ .*$|^[A-Z0-9 .:-]{6,}$", t))):
            keep |= {i - 1, i, i + 1}
    return sorted(p for p in keep if 1 <= p <= len(texts))[:MAX_BOOK_PAGES]


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
def prompt_text(name: str, aim: str = "", topics: list[str] | None = None) -> str:
    """The prompt for another AI, as it goes in PROMPT.md (and, on its own, in the chat next to the zip)."""
    if topics is None:
        topics = topics_of(aim)
    aim = (aim.strip().rstrip(".") + ".\n\n") if aim.strip() else ""
    shown = ", ".join(topics)
    return PROMPT.format(
        name=name,
        aim=f"What it's for: {aim}" if aim else "",
        topic=f", narrowed to **{shown}**" if topics else "",
        book_note=" (only their pages on the topic, as text, with the page numbers)"
        if topics
        else " (none: name a topic)",
        scope=f" on {shown}" if topics else " for this course",
    )


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
        for s in srcs:
            where = "class" if s.is_class else "books"
            texts = s.page_texts() if rx else []
            if rx and not s.is_class and texts:  # a book: only its pages on the topic, as text
                pages = book_pages(s, rx)
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
            if rx:  # class material: in if it's about the topic at all
                about = hits(rx, s.title) or (sum(hits(rx, t) for t in texts) if texts else 0)
                if not about:
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
        z.writestr("PROMPT.md", prompt_text(name, aim, topics))
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

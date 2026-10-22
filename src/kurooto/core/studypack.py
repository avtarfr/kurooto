"""A study pack: one subject's notes and course files in a zip, with a prompt to give another AI (Claude, ChatGPT, …)
so it can write deeper notes from them. Nothing here uses your AI: it only collects files and fills in a template.

    notes/         your notes for the subject: its source and course notes, and any note that links to them
    course-files/  the slides, assignments and papers Classroom (or your files folder) holds for it
    PROMPT.md      what to say to the other AI, with the aim you gave ("quiz on Thursday")
    INDEX.md       every file in the pack, and what was left out and why

Limits: the zip stays under Telegram's 50 MB (newest course files go in first, the rest are listed in INDEX.md as left
out); notes over 400 KB and files over 40 MB are left out; hidden files and folders never go in.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kurooto.app import App

MAX_ZIP = 48 * 1024 * 1024  # under Telegram's 50 MB, leaving room for the notes and the index
MAX_NOTE = 400 * 1024
MAX_FILE = 40 * 1024 * 1024
MAX_NOTES = 600  # notes read to find the ones that link to the subject
FILE_TYPES = {".pdf", ".pptx", ".ppt", ".docx", ".doc", ".ipynb", ".txt", ".md", ".tex", ".py", ".csv", ".png", ".jpg"}

PROMPT = """# Study pack: {name}

{aim}I'm a university student. This zip has my own notes and the course files for **{name}**:

- `notes/`: my notes in Markdown (`[[double brackets]]` are links between my notes).
- `course-files/`: the slides, assignments and papers the course gave out.
- `INDEX.md`: every file here, and anything that didn't fit.

## What I'd like

Write advanced, rigorous study notes for this course from these files, going beyond what my own notes say:

1. For each topic (follow the order of the lectures): the definitions, the main results with proofs or proof sketches,
   the intuition, and two worked examples.
2. The usual mistakes and the questions examiners like, on that topic.
3. Five practice problems per topic, easy to hard, with full solutions.
4. How the topics connect (what each one is needed for later), and a one-page summary of formulas.

## Rules

- Use the files. Where they leave a gap or look wrong, say so instead of guessing, and name the file for each claim.
- Maths in LaTeX (`$...$`). One Markdown section per topic, so I can drop them into my notes as separate files.
- Tell me first what you plan to cover and in what order, then write it, a few topics at a time.
"""


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-") or "subject"


def _hidden(rel: Path) -> bool:
    return any(p.startswith(".") for p in rel.parts)


def note_files(app: App, subject: str) -> list[Path]:
    """The notes for a subject: anything in a folder named for it, its course map, and notes that link to those."""
    root = Path(app.workspace)
    found: dict[Path, None] = {}
    for f in sorted(root.rglob("*.md")):
        try:
            rel = f.relative_to(root)
        except ValueError:
            continue
        if _hidden(rel) or f.stat().st_size > MAX_NOTE:
            continue
        if subject in rel.parts[:-1] or rel.stem == subject:
            found[f] = None
    key = re.compile(r"\[\[[^\]]*" + re.escape(subject) + r"[^\]]*\]\]", re.I)
    for f in sorted(root.rglob("*.md"))[: MAX_NOTES * 4]:
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
    return list(found)


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


def build(app: App, subject: str, name: str = "", aim: str = "", dest: Path | None = None) -> tuple[Path, dict]:
    """Write the zip. Returns (its path, {"notes": n, "files": n, "left_out": [(name, why)]}); ValueError if there's
    nothing to put in it."""
    subject = slug(subject)
    name = name or subject.replace("-", " ").title()
    notes = note_files(app, subject)
    files = course_files(app, subject)
    if not notes and not files:
        raise ValueError(f"I found no notes or course files for {name}.")
    dest = dest or Path(app.paths.cache) / "study-packs" / f"{subject}-study-pack.zip"
    dest.parent.mkdir(parents=True, exist_ok=True)
    root = Path(app.workspace)
    used: set[str] = set()
    index: list[str] = []
    out: list[tuple[str, str]] = []

    def arc(prefix: str, f: Path, base: Path) -> str:
        a = f"{prefix}/" + f.relative_to(base).as_posix()
        n = 2
        while a.lower() in used:
            a = f"{prefix}/{f.stem}-{n}{f.suffix}"
            n += 1
        used.add(a.lower())
        return a

    total = 0
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED, compresslevel=6, strict_timestamps=False) as z:
        for f in notes:
            a = arc("notes", f, root)
            z.write(f, a)
            total += f.stat().st_size
            index.append(f"- {a}")
        n_notes = len(index)
        base_of = {f: d for d in course_folders(app, subject) for f in files if d in f.parents}
        for f in files:
            size = f.stat().st_size
            if total + size > MAX_ZIP:
                out.append((f.name, "the zip would pass Telegram's 50 MB"))
                continue
            a = arc("course-files", f, base_of.get(f, f.parent))
            z.write(f, a)
            total += size
            index.append(f"- {a} ({size // 1024} KB)")
        text = [f"# Index: {name}\n", "## In this pack\n", *(index or ["(nothing)"])]
        if out:
            text += ["", "## Left out\n", *(f"- {n}: {why}" for n, why in out)]
        z.writestr("INDEX.md", "\n".join(text) + "\n")
        aim = (aim.strip().rstrip(".") + ".\n\n") if aim.strip() else ""
        z.writestr("PROMPT.md", PROMPT.format(name=name, aim=f"What it's for: {aim}" if aim else ""))
    return dest, {"notes": n_notes, "files": len(index) - n_notes, "left_out": out}

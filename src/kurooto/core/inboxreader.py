"""Reading what you drop into the scratch folder (0.8.0, opt-in: `sorter.read_files`): handouts, "topics covered" lists,
slides, anything
you want Kurooto to know about but that isn't a book.

A PDF, Word document, slide deck, notebook or plain text file in the scratch folder (inbox/ by default) is turned into
a Markdown note
next to it: the text, read on this computer (no AI), under a short header saying where it came from and that Kurooto
wrote it. The
original stays where it is, untouched. The note then goes the way any note does: the sorter files it where it belongs,
the concept graph
reads it, and it's there when you ask what was covered in class. Nothing is sent anywhere by this.

    read_new(app)     the files not read yet (settled, not hidden, not a key or password file): [(file, note)]
    Skipped           a scanned PDF with no text in it is left as it is and said (a handwriting or vision pass can
    read it)
    Limits            `sorter.read_mb` MB a file; text beyond MAX_CHARS is cut with a line saying so; each file is
    read once (by its hash)

State: `<state>/sorter/read.json`.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import re
import time
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto.core import scratch, sorting
from kurooto.core.state import jload, jsave

if TYPE_CHECKING:
    from kurooto.app import App

EXTS = {".pdf", ".docx", ".pptx", ".ipynb", ".txt", ".rtf", ".csv"}
MAX_CHARS = 150_000
MIN_CHARS = 40


def _state(app: App) -> dict:
    d = jload(app.paths.state / "sorter" / "read.json", {}) or {}
    d.setdefault("done", {})
    d.setdefault("skipped", {})
    return d


def _save(app: App, d: dict) -> None:
    (app.paths.state / "sorter").mkdir(parents=True, exist_ok=True)
    jsave(app.paths.state / "sorter" / "read.json", d)


def extract(f: Path) -> str | None:
    """The file's text, or None when it has none this computer can read."""
    if f.suffix.lower() == ".pdf":
        from kurooto.core.tools import pdf_text

        return pdf_text(f)
    from kurooto.modules.google_classroom import extract_text

    if f.suffix.lower() == ".rtf":
        raw = f.read_text(encoding="utf-8", errors="replace")
        return re.sub(r"\\[a-z]+-?\d* ?|[{}]", "", raw)
    return extract_text(f)


def tidy(text: str) -> str:
    """Whitespace made readable: no runs of blank lines, no trailing spaces, no form feeds."""
    t = text.replace("\f", "\n\n").replace("\r\n", "\n")
    t = "\n".join(line.rstrip() for line in t.split("\n"))
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def title_of(f: Path, text: str) -> str:
    first = next((ln.strip() for ln in text.splitlines() if len(ln.strip()) >= 6), "")
    return (first[:90] if first and len(first) < 90 else f.stem.replace("-", " ").replace("_", " ")).strip()


def note_text(f: Path, rel: str, body: str, title: str) -> str:
    cut = len(body) > MAX_CHARS
    body = body[:MAX_CHARS] + (
        "\n\n[… the rest of the file is cut here; it is long. The original is " + rel + ".]" if cut else ""
    )
    safe = title.replace('"', "'")
    return (
        f'---\ntitle: "{safe}"\nkind: reference\nsource_file: "{rel}"\nread_on: {dt.date.today().isoformat()}\n'
        "trust_tier: agent_written\n---\n\n"
        f"# {title}\n\n> Read from `{rel}` by Kurooto: general information you gave it (what was covered, a handout), "
        "not a book. "
        "The original is untouched.\n\n" + body + "\n"
    )


def read_new(app: App, limit: int = 8, force: bool = False) -> list[tuple[str, str]]:
    """Read the files in the scratch folder that haven't been; returns [(file, its note)] (paths in your notes)."""
    if not app.settings.get("sorter.read_files"):
        return []
    d = sorting.scratch_dir(app)
    if not d.is_dir():
        return []
    root = Path(app.workspace)
    st = _state(app)
    settle = 0.0 if force else float(sorting.setting(app, "settle_min", 10) or 0) * 60
    max_b = float(app.settings.get("sorter.read_mb") or 25) * 1_000_000
    out = []
    for f in sorted(d.rglob("*")):
        rel_parts = f.relative_to(root).parts
        if len(out) >= limit:
            break
        if (
            not f.is_file()
            or f.suffix.lower() not in EXTS
            or any(x.startswith(".") for x in rel_parts)
            or scratch.secret(f.name)
        ):
            continue
        try:
            stt = f.stat()
        except OSError:
            continue
        if time.time() - stt.st_mtime < settle or stt.st_size > max_b:
            continue
        rel = f.relative_to(root).as_posix()
        h = hashlib.sha256(f.read_bytes()).hexdigest()[:16]
        if h in st["done"] or st["skipped"].get(rel) == h:
            continue
        text = extract(f)
        body = tidy(text or "")
        if len(body) < MIN_CHARS:
            st["skipped"][rel] = h
            app.events.emit("inbox_read_skipped", ext=f.suffix.lower())
            continue
        title = title_of(f, body)
        note = f.with_suffix(".md")
        n = 1
        while note.exists():
            n += 1
            note = f.with_name(f"{f.stem}-{n}.md")
        note.write_text(note_text(f, rel, body, title), encoding="utf-8")
        st["done"][h] = {"file": rel, "note": note.relative_to(root).as_posix(), "at": time.time(), "chars": len(body)}
        ig = app.modules.get("integrate")
        if ig is not None:  # into the concept graph too, like class material (integrate.sources: reference)
            try:
                ig.take_reference(note, title, body)
            except Exception as e:  # reading it into the graph never stops the note being made
                app.events.emit("inbox_graph_failed", error=type(e).__name__)
        out.append((rel, note.relative_to(root).as_posix()))
        app.events.emit("inbox_read", ext=f.suffix.lower(), chars=len(body))
    _save(app, st)
    return out


def skipped(app: App) -> list[str]:
    root = Path(app.workspace)
    return [r for r in _state(app)["skipped"] if (root / r).exists()]

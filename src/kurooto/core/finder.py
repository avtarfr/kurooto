"""Find a file, and send it (0.8.0): a local index of the folders you choose, with no AI.

`/find <words>` looks through the names and the text of the files in your chosen folders and offers each hit with a
Send button (the file goes
to your own Telegram, up to 50 MB; bigger ones to Drive when that's on). The index is a SQLite full-text table in
`<state>/finder/index.db`:
a name, the text where the file has any (PDFs by pdftotext, Word and slides from their XML, notebooks, plain text and
code directly), and the
path, size and date of everything. It's rebuilt incrementally (a file is read again only when its size or time
changed) and never leaves this
computer. Keys, passwords and hidden folders are never read or listed.

    index(app)            bring the index up to date: {added, changed, removed, scanned}
    search(app, words)    [{path, name, size, mtime, snippet}], best first
    folders(app)          the folders being indexed (finder.folders)
"""

from __future__ import annotations

import os
import re
import sqlite3
import time
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto.core import inboxreader, scratch
from kurooto.core.config import register_defaults

if TYPE_CHECKING:
    from kurooto.app import App

register_defaults(
    "finder",
    {
        "folders": [],  # the folders to index and search (full paths, ~ allowed): /find add <folder>
        "read_mb": 20,  # a file bigger than this has its name indexed but its text isn't read
        "max_files": 60000,  # the most files indexed
    },
)

TEXT_EXT = {
    ".txt",
    ".md",
    ".tex",
    ".py",
    ".r",
    ".js",
    ".ts",
    ".c",
    ".cpp",
    ".h",
    ".java",
    ".rs",
    ".go",
    ".csv",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".html",
    ".css",
    ".sh",
    ".ipynb",
    ".rtf",
}
DOC_EXT = {".pdf", ".docx", ".pptx"}
SKIP_DIRS = {"node_modules", "__pycache__", ".git", "venv", ".venv", "site-packages", "build", "dist", "target"}
TEXT_MAX = 200_000
SEND_MAX = 50 * 1024 * 1024


def db_path(app: App) -> Path:
    return app.paths.state / "finder" / "index.db"


def _db(app: App) -> sqlite3.Connection:
    p = db_path(app)
    p.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(p, timeout=30)
    db.executescript(
        "create table if not exists files(path text primary key, name text, ext text, size integer, mtime real);"
        "create virtual table if not exists docs using fts5("
        "name, body, path unindexed, tokenize='unicode61 remove_diacritics 2');"
    )
    return db


def folders(app: App) -> list[Path]:
    out = []
    for f in app.settings.get("finder.folders") or []:
        p = Path(os.path.expanduser(str(f)))
        if p.is_dir():
            out.append(p.resolve())
    return out


def _body(f: Path, ext: str, size: int, limit: float) -> str:
    if size > limit or ext not in TEXT_EXT | DOC_EXT:
        return ""
    try:
        if ext in TEXT_EXT and ext not in (".ipynb", ".rtf"):
            return f.read_text(encoding="utf-8", errors="replace")[:TEXT_MAX]
        return (inboxreader.extract(f) or "")[:TEXT_MAX]
    except Exception:  # an unreadable file is still found by its name
        return ""


def index(app: App, budget_s: float | None = None) -> dict:
    """Bring the index up to date. budget_s: stop after this long (the rest is done next time)."""
    t0 = time.monotonic()
    db = _db(app)
    have = {p: (s, m) for p, s, m in db.execute("select path, size, mtime from files")}
    seen: set[str] = set()
    out = {"added": 0, "changed": 0, "removed": 0, "scanned": 0}
    limit = float(app.settings.get("finder.read_mb") or 20) * 1_000_000
    cap = int(app.settings.get("finder.max_files") or 60000)
    done = True
    for root in folders(app):
        for dp, dn, fn in os.walk(root):
            dn[:] = [d for d in dn if not d.startswith(".") and d not in SKIP_DIRS]
            for name in fn:
                if name.startswith(".") or scratch.secret(name):
                    continue
                f = Path(dp) / name
                try:
                    st = f.stat()
                except OSError:
                    continue
                key = str(f)
                seen.add(key)
                out["scanned"] += 1
                if len(seen) > cap or (budget_s is not None and time.monotonic() - t0 > budget_s):
                    done = False
                    break
                if have.get(key) == (st.st_size, st.st_mtime):
                    continue
                ext = f.suffix.lower()
                body = _body(f, ext, st.st_size, limit)
                db.execute("delete from docs where path=?", (key,))
                db.execute(
                    "insert into docs(name, body, path) values (?,?,?)", (re.sub(r"[_\-.]+", " ", f.stem), body, key)
                )
                db.execute("insert or replace into files values (?,?,?,?,?)", (key, name, ext, st.st_size, st.st_mtime))
                out["changed" if key in have else "added"] += 1
            if not done:
                break
        if not done:
            break
    if done:  # only a finished pass can say what's gone
        for key in set(have) - seen:
            db.execute("delete from docs where path=?", (key,))
            db.execute("delete from files where path=?", (key,))
            out["removed"] += 1
    db.commit()
    db.close()
    out["finished"] = done
    return out


def _query(words: str) -> str:
    terms = [w for w in re.findall(r"[\w]+", words.lower()) if len(w) >= 2]
    return " ".join(f'"{t}"*' for t in terms[:8])


def search(app: App, words: str, limit: int = 8) -> list[dict]:
    q = _query(words)
    if not q or not db_path(app).exists():
        return []
    db = _db(app)
    try:
        rows = db.execute(
            "select d.path, f.name, f.size, f.mtime, snippet(docs, 1, '[', ']', ' … ', 12) "
            "from docs d join files f on f.path = d.path where docs match ? order by bm25(docs, 8.0, 1.0) limit ?",
            (q, limit),
        ).fetchall()
    except sqlite3.OperationalError:
        rows = []
    db.close()
    return [
        {"path": p, "name": n, "size": s, "mtime": m, "snippet": " ".join((sn or "").split())[:160]}
        for p, n, s, m, sn in rows
    ]


def inside(app: App, path: str) -> bool:
    """Is it in one of the chosen folders? (Only those may be sent.)"""
    try:
        p = Path(path).resolve()
    except OSError:
        return False
    return any(p.is_relative_to(r) for r in folders(app))

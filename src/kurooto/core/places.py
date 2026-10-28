"""Where the AI may look on this computer, the same for Kurooto's own tools and for agy's allow-list.

A change request (Help with your project, a change to your notes you asked for, a fix Dreaming proposes) is different:
it may write in its own scratch folder only (core/scratch.py; write_roots(app, scratch=...)), and read as always plus
the original. What it wrote reaches your files only as a proposal you apply (core/proposals.py).

Reading: your notes folder, Kurooto's copies of Classroom and mail (its data folders), your Documents and Downloads,
your Screenshots folder if there is one, and (0.9.0) the files you attached on the dashboard's Chat page once there are
any (chat_files below). Writing: your notes folder (all of it), your files folder (files.folder,
if you set one), the folder Classroom's course files go to, and your add-ons' skills/ when "Your add-ons" is on (never
the skills Kurooto ships, which updates replace). Documents and Downloads stay read-only. Each is the real folder on
this OS (Windows' known folders, which OneDrive may have moved; Linux's XDG user dirs), as an absolute path.
"""

from __future__ import annotations

import os
import re
import sys
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kurooto.app import App

KNOWN = {  # Windows known-folder ids
    "documents": "FDD39AD0-238F-46AF-ADB4-6C85480369C7",
    "downloads": "374DE290-123F-4565-9164-39C4925E467B",
    "pictures": "33E28130-4E1E-4676-835A-98395C3BC3BB",
}
XDG = {"documents": "XDG_DOCUMENTS_DIR", "downloads": "XDG_DOWNLOAD_DIR", "pictures": "XDG_PICTURES_DIR"}


def user_folder(kind: str) -> Path | None:
    """This user's Documents, Downloads or Pictures folder (kind "documents" / "downloads" / "pictures") where this OS
    keeps it, if it exists."""
    home = Path.home()
    p = None
    try:
        if sys.platform == "win32":
            p = _known_folder(kind)
        elif sys.platform.startswith("linux"):
            p = _xdg_user_dir(kind, home)
    except Exception:
        p = None
    p = p or home / kind.capitalize()
    return p if p.is_dir() else None


def screenshots() -> Path | None:
    pictures = user_folder("pictures")
    for p in ([pictures / "Screenshots"] if pictures else []) + [Path.home() / "Screenshots"]:
        if p.is_dir():
            return p
    return None


def _xdg_user_dir(kind: str, home: Path) -> Path | None:
    cfg = Path(os.environ.get("XDG_CONFIG_HOME") or home / ".config") / "user-dirs.dirs"
    for line in cfg.read_text(encoding="utf-8").splitlines() if cfg.is_file() else []:
        m = re.match(rf'^\s*{XDG[kind]}="(.*)"\s*$', line)
        if m:
            v = Path(m.group(1).replace("$HOME", str(home)))
            return v if v.is_absolute() else None
    return None


def _known_folder(kind: str) -> Path | None:  # pragma: no cover (Windows)
    import ctypes
    from ctypes import wintypes

    class GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", wintypes.DWORD),
            ("Data2", wintypes.WORD),
            ("Data3", wintypes.WORD),
            ("Data4", ctypes.c_ubyte * 8),
        ]

    u = uuid.UUID(KNOWN[kind])
    g = GUID(u.time_low, u.time_mid, u.time_hi_version, (ctypes.c_ubyte * 8)(*u.bytes[8:]))
    out = ctypes.c_wchar_p()
    try:
        if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(g), 0, None, ctypes.byref(out)) != 0:
            return None
        return Path(out.value) if out.value else None
    finally:
        ctypes.windll.ole32.CoTaskMemFree(out)


def notes_root(app: App) -> Path:
    return Path(os.path.abspath(app.workspace))


def course_files(app: App) -> Path:
    """Where Classroom's course files are saved (google_classroom.files_dir)."""
    from kurooto.core import layout

    return Path(os.path.abspath(layout.file_dir(app, "classroom", subject="x").parent))


def files_folder(app: App) -> Path | None:
    """Your files folder outside the notes (files.folder, core/layout.py), if you set one."""
    from kurooto.core import layout

    root = layout.files_root(app)
    return Path(os.path.abspath(root)) if root else None


def chat_files(app: App) -> Path:
    """(0.9.0) Where files you attach on the dashboard's Chat page are kept: Kurooto's own state, never your notes
    (web/chat_api.py)."""
    return Path(os.path.abspath(app.paths.state / "chat-files"))


def _attached(app: App) -> list[Path]:
    """The Chat page's attachments folder, while dashboard.chat_attach is on and once something was attached: agy's
    allow-list is agreed once (providers/agy.py), so it isn't asked again of everyone who never attaches a file."""
    d = chat_files(app)
    return [d] if app.settings.get("dashboard.chat_attach") is not False and d.is_dir() else []


def write_roots(app: App, scratch: Path | None = None) -> list[Path]:
    """Every folder the AI may write in, absolute, without repeats. A change request (core/scratch.py) may write in
    its scratch folder and nowhere else: then that's the one folder."""
    from kurooto.core import overlay

    if scratch is not None:
        return [Path(os.path.abspath(scratch))]

    roots = [
        notes_root(app),
        course_files(app),
        *([f] if (f := files_folder(app)) else []),
        *overlay.dirs(app, "skills", linked=False),  # an add-on by link's files stay as you agreed to them
    ]
    return list(dict.fromkeys(Path(os.path.abspath(p)) for p in roots))


def read_roots(app: App, extra: list[Path] | tuple = ()) -> list[Path]:
    """Every folder the AI may read, absolute, without repeats (some may not exist yet). extra: a change request's
    original and scratch folder (core/scratch.py)."""
    roots = [
        notes_root(app),
        course_files(app),  # Classroom's course files (google_classroom)
        app.paths.data / "classroom",  # older ones, from before files.folder was set
        app.paths.state / "classroom-notes",  # Classroom batches for the AI
        app.paths.state / "mail-digest",  # mail batches for the digest (google_mail)
        app.paths.state
        / "reserve",  # Markdown copies of alarms, deadlines, settings, what an AI may do (core/reserve.py)
        user_folder("documents"),
        user_folder("downloads"),
        screenshots(),
        *_attached(app),  # (0.9.0) files you attached on the dashboard's Chat page, for the AI you sent them to
    ]
    roots += write_roots(app)  # what it may write, it may read
    roots += list(extra)
    return list(dict.fromkeys(Path(os.path.abspath(p)) for p in roots if p))


def inside(path: Path, roots: list[Path]) -> bool:
    """Is the real path (links followed) inside one of the roots (also resolved)?"""
    real = path.resolve()
    for r in roots:
        rr = r.resolve()
        if real == rr or rr in real.parents:
            return True
    return False

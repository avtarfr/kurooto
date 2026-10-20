"""Opening one of your notes in your own program (the dashboard's notes map: double-click a note).

notes.open_with: empty (the default) opens the note in this computer's default app for Markdown files (Linux:
xdg-open, macOS: open, Windows: the file's default program). Or a command that opens its own window, for example
`kitty nvim {path}`, `code {path}`, `kurooto term -e nvim {path}` or `wezterm start -- hx {path}`. It runs as a program
with its arguments, never through a shell: {path} is the note's full path ({folder}: your notes folder) and stays one
argument even with spaces in it; without {path} the note's path goes at the end. If the program isn't there, the
default app opens the note and the dashboard says why.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path

from kurooto.core.config import register_defaults
from kurooto.core.proc import which

register_defaults("notes", {"open_with": ""})


def argv_for(template: str, path, folder="") -> list[str]:
    """The command for one note ([] when the template is empty or can't be read, e.g. an unclosed quote)."""
    t = (template or "").strip()
    if not t:
        return []
    windows = os.name == "nt"
    try:
        parts = shlex.split(t, posix=not windows)
    except ValueError:
        return []
    if windows:  # non-POSIX splitting keeps the quotes: "C:\Program Files\x.exe" -> C:\Program Files\x.exe
        parts = [p[1:-1] if len(p) >= 2 and p[0] == p[-1] and p[0] in "\"'" else p for p in parts]
    if not parts:
        return []
    out, used = [], False
    for p in parts:
        used = used or "{path}" in p
        out.append(p.replace("{path}", str(path)).replace("{folder}", str(folder)))
    out[0] = os.path.expanduser(out[0])
    return out if used else [*out, str(path)]


def spawn(argv: list[str]) -> None:
    """Start a program on its own (it outlives Kurooto; no console window on Windows)."""
    kw: dict = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if sys.platform == "win32":
        kw["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        kw["close_fds"] = True
    else:
        kw["start_new_session"] = True
    p = subprocess.Popen(argv, **kw)  # noqa: S603 (argv, no shell; the command is the user's own setting)
    from kurooto.core import children

    children.keep(p.pid)  # yours: it stays open when Kurooto stops


def open_default(path) -> bool:
    """The note in the default app for its type."""
    try:
        if sys.platform == "win32":
            os.startfile(str(path))  # noqa: S606 (the user's own note in their default app)
        else:
            spawn(["open" if sys.platform == "darwin" else "xdg-open", str(path)])
        return True
    except OSError:
        return False


def open_note(settings, path, folder="") -> tuple[bool, str]:
    """Open a note with notes.open_with, else the default app. Returns (opened, a note when the setting didn't
    work and the default app was used instead)."""
    template = str(settings.get("notes.open_with") or "").strip()
    argv = argv_for(template, Path(path), folder)
    note = ""
    if argv:
        exe = which(argv[0])
        if exe:
            try:
                spawn([exe, *argv[1:]])
                return True, ""
            except OSError as e:
                note = f"{argv[0]} didn't start ({e}), so the note opened in the default app."
        else:
            note = f"{argv[0]} isn't on this computer, so the note opened in the default app (Settings: notes)."
    elif template:
        note = "Settings: notes.open_with couldn't be read (an unclosed quote?), so the default app opened it."
    return open_default(path), note

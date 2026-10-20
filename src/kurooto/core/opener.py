"""Opening one of your notes in your own program (the dashboard's notes map: double-click a note), and the dashboard's
links to other sites in your default browser (open_url, at the end).

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
import threading
import urllib.parse
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
    subprocess.Popen(argv, **kw)  # noqa: S603 (argv, no shell; the command is the user's own setting)


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


# ------------------------------------------------------------------------------------------------ web addresses
# The dashboard's links to other sites (Google sign-in, a token page, docs) open in this computer's default browser
# (look.links_in = "default"), not in the window showing the dashboard, which may be another browser's app window
# (`google-chrome --app=...`). POST /api/open-url; the pages fall back to opening the link themselves when it fails.
def safe_url(url) -> str | None:
    """A web address that may go to the browser: http or https with a host, at most 4,000 characters, no spaces or
    control characters. Anything else (file:, javascript:, data:) is None."""
    if not isinstance(url, str) or not url or len(url) > 4000 or any(ord(c) <= 32 or ord(c) == 127 for c in url):
        return None
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError:
        return None
    return url if parts.scheme.lower() in ("http", "https") and parts.hostname else None


def open_url(url, wait: float = 2.0) -> tuple[bool, str]:
    """Open a web address in the default browser: Windows through os.startfile, Linux and macOS through webbrowser
    (xdg-open or open, or $BROWSER when it's set). A $BROWSER command may not return until that browser closes, so
    this waits at most `wait` seconds and counts one still going as opened. Returns (opened, why not)."""
    u = safe_url(url)
    if not u:
        return False, "Only http and https addresses open in the browser."
    if sys.platform == "win32":
        try:
            os.startfile(u)  # noqa: S606 (an http(s) address: the default browser)
            return True, ""
        except OSError as e:
            return False, str(e)
    import webbrowser

    got: dict = {}

    def go() -> None:
        try:
            got["ok"] = bool(webbrowser.open(u, new=2))
        except Exception as e:  # no browser, a broken $BROWSER: the page opens it itself
            got["why"] = str(e)

    t = threading.Thread(target=go, name="open-url", daemon=True)
    t.start()
    t.join(wait)
    if t.is_alive() or got.get("ok"):
        return True, ""
    return False, got.get("why") or "No browser answered on this computer."

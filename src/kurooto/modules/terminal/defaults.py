"""Opt-in: Kurooto Terminal as your default terminal, and its undo. Off unless you turn it on (Settings → Kurooto
Terminal → default, or `kurooto term --default on`).

    Linux    puts Kurooto Shell (one window, your shell in Kurooto's colours), or Kurooto Terminal (the whole
             window) when terminal.default_opens is "layout", first in xdg-terminal-exec's list
             (~/.config/xdg-terminals.list), which desktops and apps that follow it use to open "a terminal". Your
             desktop's or window manager's own keys and settings aren't changed: `kurooto term --default on` says
             how to bind a key yourself.
    Windows  sets Windows Terminal's default profile to Kurooto's (your shell in Kurooto's colours), after a backup
             of Windows Terminal's settings.json.
    macOS    has no default-terminal setting: Kurooto Terminal is in your Applications folder.

Undo puts back what was there: the whole file from the backup when nothing else has changed it since, otherwise
only the one line or value Kurooto changed. Backups stay in Kurooto's state folder (terminal/backups).
"""

from __future__ import annotations

import hashlib
import os
import shutil
import time
from pathlib import Path

from kurooto.core.state import jload, jsave
from kurooto.modules.terminal import launchers, wt

RECORD = "default.json"
LIST = "xdg-terminals.list"
OURS = (launchers.SHELL_DESKTOP, launchers.DESKTOP)


def entry(opens: str) -> str:
    """The desktop entry a default-terminal launch opens: Kurooto Shell, or the whole window ("layout")."""
    return launchers.DESKTOP if opens == "layout" else launchers.SHELL_DESKTOP


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp{os.getpid()}")
    with open(tmp, "w", encoding="utf-8", newline="") as f:  # keep the file's own line endings
        f.write(text)
    os.replace(tmp, path)


def _backup(state_dir: Path, f: Path) -> Path:
    d = state_dir / "backups"
    d.mkdir(parents=True, exist_ok=True)
    stamp, n = time.strftime("%Y%m%d-%H%M%S"), 1
    dest = d / f"{f.name}.{stamp}"
    while dest.exists():  # never over an earlier backup
        n += 1
        dest = d / f"{f.name}.{stamp}-{n}"
    shutil.copy2(f, dest)
    return dest


def status(state_dir: Path) -> dict | None:
    """What "default terminal" changed, or None."""
    return jload(Path(state_dir) / RECORD, None)


def bind_hint() -> str:
    return (
        "To open it with a key, bind one to `kurooto term --shell` (your shell) or `kurooto term` (the whole window) "
        "in your desktop's keyboard settings (GNOME: Settings → Keyboard → Custom Shortcuts; KDE: System Settings → "
        "Default Applications → Terminal Emulator → Kurooto Shell), or in your window manager's own config."
    )


def apply(
    os_: str,
    state_dir: Path,
    home: Path | None = None,
    env: dict | None = None,
    has_xdg_exec: bool | None = None,
    opens: str = "shell",
) -> tuple[bool, str]:
    state_dir = Path(state_dir)
    if os_ == "macos":
        jsave(state_dir / RECORD, {"os": "macos", "since": time.time()})
        return True, (
            "macOS has no default-terminal setting. Kurooto Terminal is in your Applications folder: open it from "
            "Launchpad or Spotlight, and keep it in the Dock."
        )
    if os_ == "windows":
        return _apply_windows(state_dir, home, env)
    return _apply_linux(state_dir, home, env, has_xdg_exec, entry(opens))


def undo(state_dir: Path, home: Path | None = None, env: dict | None = None) -> tuple[bool, str]:
    state_dir = Path(state_dir)
    rec = status(state_dir)
    if not rec:
        return True, "Kurooto Terminal isn't your default terminal."
    if rec.get("os") == "windows":
        msg = _undo_windows(rec)
    elif rec.get("os") == "linux":
        msg = _undo_linux(rec)
    else:
        msg = "Kurooto Terminal is no longer your default terminal."
    (state_dir / RECORD).unlink(missing_ok=True)
    return True, msg


# ----------------------------------------------------------------------------------------------- Linux
def _apply_linux(state_dir: Path, home, env, has_xdg_exec, first: str) -> tuple[bool, str]:
    f = launchers.config_home(home, env) / LIST
    old = f.read_text(encoding="utf-8", errors="replace") if f.is_file() else None
    rec = status(state_dir) or {}
    lines = [ln for ln in (old or "").splitlines() if ln.strip() not in OURS]
    new = "\n".join([first, *lines]).rstrip("\n") + "\n"
    if old != new:
        if rec.get("os") != "linux":  # the first time: keep how it was before Kurooto
            backup = _backup(state_dir, f) if old is not None else None
            rec = {"os": "linux", "file": str(f), "existed": old is not None, "backup": str(backup or "")}
        _write(f, new)
        rec.update(wrote=_sha(new), entry=first, since=time.time())
        jsave(state_dir / RECORD, rec)
    elif rec.get("os") != "linux":
        rec = {"os": "linux", "file": str(f), "existed": True, "backup": "", "wrote": _sha(new), "entry": first}
        jsave(state_dir / RECORD, rec)
    if has_xdg_exec is None:
        has_xdg_exec = bool(shutil.which("xdg-terminal-exec"))
    name = launchers.SHELL_NAME if first == launchers.SHELL_DESKTOP else launchers.NAME
    msg = f"{name} is now first in {f}."
    if not has_xdg_exec:
        msg += " That list is read by xdg-terminal-exec, which isn't installed here, so it may not take effect."
    return True, f"{msg} {bind_hint()}"


def _undo_linux(rec: dict) -> str:
    f = Path(rec.get("file", ""))
    if not f.is_file():
        return "Kurooto Terminal is no longer your default terminal."
    text = f.read_text(encoding="utf-8", errors="replace")
    backup = Path(rec["backup"]) if rec.get("backup") else None
    if _sha(text) == rec.get("wrote"):  # nothing else changed it: exactly as it was
        if rec.get("existed") and backup and backup.is_file():
            shutil.copy2(backup, f)
            return f"Put {f} back as it was."
        if not rec.get("existed"):
            f.unlink()
            return f"Removed {f} (Kurooto had made it)."
    lines = [ln for ln in text.splitlines() if ln.strip() not in OURS]
    if not any(ln.strip() for ln in lines) and not rec.get("existed"):
        f.unlink()
    else:
        _write(f, "\n".join(lines).rstrip("\n") + "\n")
    return f"Took Kurooto Terminal out of {f} (the rest of it is as you left it)."


# --------------------------------------------------------------------------------------------- Windows
def _apply_windows(state_dir: Path, home, env) -> tuple[bool, str]:
    files = [f for f in wt.settings_files(home, env) if f.is_file()]
    if not files:
        return False, "Open Windows Terminal once (so it makes its settings), then try again."
    if not wt.has_fragment(home, env):
        return False, "Turn on Kurooto Terminal first (it adds Kurooto's profile to Windows Terminal)."
    f, ours = files[0], wt.guid(wt.APP)
    raw = f.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig", errors="replace")
    if wt.current_default(text) == ours:
        return True, "Kurooto is already Windows Terminal's default profile."
    new, previous = wt.with_default(text, ours)
    backup = _backup(state_dir, f)
    _write(f, ("﻿" if bom else "") + new)
    jsave(
        state_dir / RECORD,
        {
            "os": "windows",
            "file": str(f),
            "backup": str(backup),
            "guid": ours,
            "previous": previous,
            "wrote": _sha(("﻿" if bom else "") + new),
            "since": time.time(),
        },
    )
    return True, (
        "New Windows Terminal windows and tabs now open Kurooto (your shell in Kurooto's colours). "
        f"Windows Terminal's settings were backed up to {backup}."
    )


def _undo_windows(rec: dict) -> str:
    f = Path(rec.get("file", ""))
    if not f.is_file():
        return "Windows Terminal's settings are gone; nothing to put back."
    text = f.read_bytes().decode("utf-8", errors="replace")
    backup = Path(rec.get("backup", ""))
    if _sha(text) == rec.get("wrote") and backup.is_file():  # nothing else changed it: the backup, exactly
        shutil.copy2(backup, f)
        return "Windows Terminal's settings are back as they were."
    if wt.current_default(text.lstrip("﻿")) != rec.get("guid"):
        return "You've picked another default profile since, so Windows Terminal's settings were left alone."
    _write(f, wt.without_default(text, rec.get("guid", ""), rec.get("previous")))
    return "Windows Terminal's default profile is back to the one you had (the rest is as you left it)."

"""Make the `kurooto` command work in new terminals: put its folder (~/.local/bin) on the PATH.

uv's installer does this when it installs uv itself, but not when uv was already there, and then `kurooto` is an
"unknown command". So Kurooto checks at install and whenever it starts, and changes only what's missing:
    Windows   your user PATH (new windows pick it up)
    fish      ~/.config/fish/conf.d/kurooto.fish
    bash/zsh  one marked line at the end of ~/.bashrc, ~/.zshrc or ~/.profile
Undo: delete the kurooto.fish file, or the two lines marked "added by Kurooto"; on Windows, remove the folder from
your user PATH (Settings → System → About → Advanced system settings → Environment Variables).
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

MARK = "# added by Kurooto: its command lives here"


def _shell_dir(bin_dir: Path, home: Path) -> str:
    try:
        return "$HOME/" + bin_dir.relative_to(home).as_posix()
    except ValueError:
        return bin_dir.as_posix()


def ensure_on_path(bin_dir: Path, home: Path | None = None, platform: str | None = None) -> list[str]:
    """Add bin_dir to the PATH of new terminals where it's missing. Returns what was changed (empty: nothing)."""
    home = home or Path.home()
    platform = platform or sys.platform
    if platform == "win32":
        return _windows(bin_dir)
    done: list[str] = []
    d = _shell_dir(bin_dir, home)
    fish_dir = home / ".config" / "fish"
    if shutil.which("fish") or fish_dir.is_dir():
        f = fish_dir / "conf.d" / "kurooto.fish"
        if not f.exists():
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(f'{MARK}\nif not contains -- "{d}" $PATH\n    set -gx PATH "{d}" $PATH\nend\n', "utf-8")
            done.append(str(f))
    line = f'{MARK}\ncase ":$PATH:" in *":{d}:"*) ;; *) export PATH="{d}:$PATH" ;; esac\n'
    rcs = [home / n for n in (".bashrc", ".zshrc") if (home / n).exists()]
    if not rcs:  # a shell that only reads its login profile; a Mac's zsh without a ~/.zshrc yet
        rcs = [home / (".zshrc" if platform == "darwin" else ".profile")]
    for rc in rcs:
        text = rc.read_text("utf-8", errors="replace") if rc.exists() else ""
        if MARK in text or bin_dir.name and f"/{bin_dir.parent.name}/{bin_dir.name}" in text:
            continue  # ours already, or the person put ~/.local/bin on their PATH themselves
        with open(rc, "a", encoding="utf-8") as fh:
            fh.write(("\n" if text and not text.endswith("\n") else "") + "\n" + line)
        done.append(str(rc))
    return done


def _windows(bin_dir: Path) -> list[str]:
    try:
        import winreg
    except ImportError:
        return []
    want = os.path.normcase(str(bin_dir)).rstrip("\\")
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_READ | winreg.KEY_SET_VALUE) as k:
            try:
                cur, kind = winreg.QueryValueEx(k, "Path")
            except FileNotFoundError:
                cur, kind = "", winreg.REG_EXPAND_SZ
            parts = [p for p in str(cur).split(";") if p]
            if any(os.path.normcase(os.path.expandvars(p)).rstrip("\\") == want for p in parts):
                return []
            winreg.SetValueEx(k, "Path", 0, kind, ";".join([*parts, str(bin_dir)]))
            return ["your user PATH"]
    except OSError:
        return []


def allowed() -> bool:
    """Not for tests, rehearsals and portable copies (they set these), which must leave the computer alone."""
    return os.environ.get("KUROOTO_NO_AUTOSTART") != "1" and not os.environ.get("KUROOTO_HOME")

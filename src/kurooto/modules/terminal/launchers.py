"""A "Kurooto Terminal" entry in your app menu, made when you turn Kurooto Terminal on and removed when you turn it
off (or uninstall Kurooto):

    Linux    ~/.local/share/applications/kurooto-terminal.desktop (a terminal emulator entry: desktops list it with
             your terminals, and xdg-terminal-exec can pick it as the default)
    macOS    ~/Applications/Kurooto Terminal.app (Launchpad, Spotlight, the Dock)
    Windows  Start menu → Kurooto Terminal (opens Windows Terminal with Kurooto's tabs)
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
from collections.abc import Callable
from pathlib import Path

APP_ID = "kurooto-terminal"
DESKTOP = f"{APP_ID}.desktop"
NAME = "Kurooto Terminal"
COMMENT = "Your AI, your shell, Kurooto chat and its log, in one window"
BUNDLE = "io.github.avtarfr.kurooto.terminal"

_PS = r"""
$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:KUROOTO_LNK)
$s.TargetPath = $env:KUROOTO_TARGET
$s.Arguments = $env:KUROOTO_ARGS
$s.WorkingDirectory = $env:USERPROFILE
$s.Description = 'Kurooto Terminal: your AI, your shell, Kurooto chat and its log'
$s.Save()
"""


def outside(env: dict | None = None) -> tuple[Path, dict]:
    """The home folder and environment that launchers and other programs' settings go by: yours, or with
    KUROOTO_HOME set (tests, portable installs) a home/ folder inside it, so nothing outside that folder changes."""
    env = os.environ if env is None else env
    if env.get("KUROOTO_HOME"):
        return Path(env["KUROOTO_HOME"]) / "home", {}
    return Path.home(), dict(env)


def _xdg(env: dict, name: str, default: Path) -> Path:
    v = env.get(name)
    return Path(v) if v and v.startswith("/") else default


def data_home(home: Path | None = None, env: dict | None = None) -> Path:
    home, env = home or Path.home(), os.environ if env is None else env
    return _xdg(env, "XDG_DATA_HOME", home / ".local" / "share")


def config_home(home: Path | None = None, env: dict | None = None) -> Path:
    home, env = home or Path.home(), os.environ if env is None else env
    return _xdg(env, "XDG_CONFIG_HOME", home / ".config")


def where(os_: str, home: Path | None = None, env: dict | None = None) -> Path:
    home, env = home or Path.home(), os.environ if env is None else env
    if os_ == "windows":
        appdata = Path(env.get("APPDATA") or home / "AppData" / "Roaming")
        return appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs" / f"{NAME}.lnk"
    if os_ == "macos":
        return home / "Applications" / f"{NAME}.app"
    return data_home(home, env) / "applications" / DESKTOP


# ----------------------------------------------------------------------------------------------- Linux
def exec_quote(arg: str) -> str:
    """One argument for a desktop entry's Exec line (the Desktop Entry spec's quoting, then its string escapes)."""
    arg = arg.replace("%", "%%")
    if arg and not re.search(r"[\s\"'\\><~|&;$*?#()`]", arg):
        return arg
    quoted = '"' + re.sub(r'(["`$\\])', r"\\\1", arg) + '"'
    return quoted.replace("\\", "\\\\")


def desktop_entry(cmd: list[str]) -> str:
    """A terminal emulator entry. The X-TerminalArg keys tell xdg-terminal-exec how to hand it a command, a title
    and a folder (`kurooto term -e CMD`, --title, --dir)."""
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={NAME}\n"
        "GenericName=Terminal\n"
        f"Comment={COMMENT}\n"
        f"Exec={' '.join(exec_quote(c) for c in cmd)}\n"
        "Icon=utilities-terminal\n"
        "Terminal=false\n"
        "Categories=System;TerminalEmulator;\n"
        "Keywords=shell;prompt;command;terminal;kurooto;\n"
        "StartupWMClass=kurooto\n"
        "X-TerminalArgExec=-e\n"
        "X-TerminalArgTitle=--title\n"
        "X-TerminalArgDir=--dir\n"
        "X-TerminalArgHold=--hold\n"
    )


# ----------------------------------------------------------------------------------------------- macOS
def mac_files(cmd: list[str]) -> dict[str, str]:
    """The app's files (path inside the .app → text): a script that runs `kurooto term`, and its Info.plist."""
    return {
        "Contents/MacOS/kurooto-terminal": "#!/bin/sh\nexec " + shlex.join(cmd) + ' "$@"\n',
        "Contents/Info.plist": (
            '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
            '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n<plist version="1.0"><dict>'
            f"<key>CFBundleName</key><string>{NAME}</string>"
            f"<key>CFBundleDisplayName</key><string>{NAME}</string>"
            "<key>CFBundleExecutable</key><string>kurooto-terminal</string>"
            f"<key>CFBundleIdentifier</key><string>{BUNDLE}</string>"
            "<key>CFBundlePackageType</key><string>APPL</string><key>LSUIElement</key><true/></dict></plist>\n"
        ),
    }


# --------------------------------------------------------------------------------------------- install
def install(
    os_: str,
    cmd: list[str],
    home: Path | None = None,
    env: dict | None = None,
    wt: str | None = None,
    wt_args: list[str] | None = None,
    run: Callable | None = None,
) -> Path:
    """Make (or refresh) the launcher. cmd runs `kurooto term`; on Windows the shortcut opens Windows Terminal
    straight away (wt, wt_args) when it's installed, so no console window flashes first."""
    path = where(os_, home, env)
    path.parent.mkdir(parents=True, exist_ok=True)
    if os_ == "windows":
        import base64
        import subprocess

        from kurooto.core import proc

        target, rest = (wt, wt_args or []) if wt else (cmd[0], cmd[1:])
        script = base64.b64encode(_PS.encode("utf-16-le")).decode()
        e = {**os.environ, "KUROOTO_LNK": str(path), "KUROOTO_TARGET": target}
        e["KUROOTO_ARGS"] = subprocess.list2cmdline(rest)
        (run or proc.run)(["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", script], timeout=30, env=e)
    elif os_ == "macos":
        for rel, text in mac_files(cmd).items():
            f = path / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(text, encoding="utf-8")
            if "/MacOS/" in rel:
                f.chmod(0o755)
    else:
        path.write_text(desktop_entry(cmd), encoding="utf-8")
    return path


def remove(os_: str, home: Path | None = None, env: dict | None = None) -> Path | None:
    path = where(os_, home, env)
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
        return path
    if path.exists():
        path.unlink(missing_ok=True)
        return path
    return None

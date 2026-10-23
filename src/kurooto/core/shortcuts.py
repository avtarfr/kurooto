"""A "Kurooto" entry in your app menu (Windows Start menu, macOS Applications, Linux app launcher). Opening it turns
Kurooto on (if it was turned off) and opens the dashboard. Made by the installer, removed by `kurooto uninstall`.

"Kurooto Quick ask" (`kurooto ask --shortcut` makes it; uninstall removes it): opens the Quick ask window
(`kurooto ask --popup`, kurooto/popup.py). On Windows its Properties take a shortcut key: that's the hotkey.
quick_ask_steps() says, for each system, how to bind the command to a key."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from kurooto.core import proc
from kurooto.core.autostart import app_dir, command

_PS = r"""
$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:KUROOTO_LNK)
$s.TargetPath = $env:KUROOTO_TARGET
$s.Arguments = $env:KUROOTO_ARGS
$s.Description = $env:KUROOTO_DESC
$s.Save()
"""
QUICK = "Kurooto Quick ask"


def on_command(app: Path | None = None) -> list[str]:
    """`kurooto on`, through the launcher when installed (so it's the current version)."""
    cmd = command(app)
    return [*cmd, "cli", "on"] if cmd[-1].endswith("launcher.py") else [cmd[0], "-m", "kurooto", "on"]


def popup_command(app: Path | None = None) -> list[str]:
    """`kurooto ask --popup`, through the launcher when installed (no console window on Windows)."""
    cmd = command(app)
    if cmd[-1].endswith("launcher.py"):
        return [*cmd, "cli", "ask", "--popup"]
    return [cmd[0], "-m", "kurooto", "ask", "--popup"]


def shown(cmd: list[str]) -> str:
    """A command as one line to paste (quoted where a part has spaces)."""
    return " ".join(f'"{c}"' if " " in c else c for c in cmd)


def _menu(home: Path | None = None) -> tuple[dict, Path]:
    env = os.environ if home is None else {}  # a home given (tests): everything under it
    return env, home or Path.home()


def where(home: Path | None = None) -> Path:
    env, home = _menu(home)
    if sys.platform == "win32":
        appdata = Path(env.get("APPDATA") or home / "AppData" / "Roaming")
        return appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Kurooto.lnk"
    if sys.platform == "darwin":
        return home / "Applications" / "Kurooto.app"
    data = Path(env.get("XDG_DATA_HOME") or home / ".local" / "share")
    return data / "applications" / "kurooto.desktop"


def quick_ask_where(home: Path | None = None) -> Path:
    main = where(home)
    if sys.platform == "win32":
        return main.with_name(f"{QUICK}.lnk")
    if sys.platform == "darwin":
        return main.with_name(f"{QUICK}.app")
    return main.with_name("kurooto-quick-ask.desktop")


def create(home: Path | None = None) -> Path:
    return _write(where(home), on_command(app_dir(home)), "Kurooto", "Turn Kurooto on and open its dashboard")


def create_quick_ask(home: Path | None = None) -> Path:
    """The Quick ask entry in your app menu: it opens the Quick ask window."""
    return _write(quick_ask_where(home), popup_command(app_dir(home)), QUICK, "Ask Kurooto one thing")


def _write(path: Path, cmd: list[str], name: str, comment: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        import base64

        script = base64.b64encode(_PS.encode("utf-16-le")).decode()
        env = {
            **os.environ,
            "KUROOTO_LNK": str(path),
            "KUROOTO_TARGET": cmd[0],
            "KUROOTO_ARGS": " ".join(f'"{c}"' for c in cmd[1:]),
            "KUROOTO_DESC": comment,
        }
        proc.run(["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", script], timeout=30, env=env)
    elif sys.platform == "darwin":
        (path / "Contents" / "MacOS").mkdir(parents=True, exist_ok=True)
        exe = path / "Contents" / "MacOS" / "Kurooto"
        exe.write_text("#!/bin/sh\nexec " + " ".join(f'"{c}"' for c in cmd) + "\n", encoding="utf-8")
        exe.chmod(0o755)
        ident = "launcher" if name == "Kurooto" else "quickask"
        (path / "Contents" / "Info.plist").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
            '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n<plist version="1.0"><dict>'
            f"<key>CFBundleName</key><string>{name}</string><key>CFBundleExecutable</key><string>Kurooto</string>"
            f"<key>CFBundleIdentifier</key><string>io.github.avtarfr.kurooto.{ident}</string>"
            "<key>CFBundlePackageType</key><string>APPL</string><key>LSUIElement</key><true/></dict></plist>\n",
            encoding="utf-8",
        )
    else:
        path.write_text(
            f"[Desktop Entry]\nType=Application\nName={name}\nComment={comment}\n"
            f"Exec={shown(cmd)}\nTerminal=false\nCategories=Utility;\n",
            encoding="utf-8",
        )
    return path


def quick_ask_steps(platform: str | None = None, wayland: bool | None = None) -> str:
    """How to bind the Quick ask command to a key on this system, in a few plain steps."""
    platform = platform or sys.platform
    if wayland is None:
        wayland = bool(os.environ.get("WAYLAND_DISPLAY")) or os.environ.get("XDG_SESSION_TYPE") == "wayland"
    if platform == "win32":
        return (
            "Windows: run `kurooto ask --shortcut` once (it adds Kurooto Quick ask to the Start menu), then Start → "
            "find Kurooto Quick ask → right-click → Open file location → right-click it → Properties → Shortcut key: "
            "press the keys (Ctrl+Alt+K, say) → OK."
        )
    if platform == "darwin":
        return (
            "macOS: open Shortcuts → New Shortcut → add Run Shell Script and paste the command → the shortcut's "
            "details (i) → Add Keyboard Shortcut → press the keys. The first time, allow Shortcuts to run scripts "
            "(Shortcuts → Settings → Advanced)."
        )
    gnome = (
        "Linux: Settings → Keyboard → Keyboard Shortcuts → Custom Shortcuts → + : any name, the command, the keys "
        "(GNOME). KDE: System Settings → Shortcuts → Add New → Command or Script. Hyprland: "
        "bind = SUPER, K, exec, <the command> in hyprland.conf; sway: bindsym $mod+k exec <the command>."
    )
    if wayland:
        return gnome + (
            " On Wayland no program can take a key for itself, so Kurooto doesn't pretend to: your desktop runs "
            "the command when you press the key."
        )
    return gnome


def quick_ask_help(path: Path) -> str:
    return f"Made {path}.\nThe command: {shown(popup_command())}\n" + quick_ask_steps()


def remove(home: Path | None = None) -> None:
    import shutil

    for path in (where(home), quick_ask_where(home)):
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        else:
            path.unlink(missing_ok=True)

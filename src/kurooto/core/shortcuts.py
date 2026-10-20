"""A "Kurooto" entry in your app menu (Windows Start menu, macOS Applications, Linux app launcher). Opening it turns
Kurooto on (if it was turned off) and opens the dashboard. Made by the installer, removed by `kurooto uninstall`."""

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
$s.Description = 'Turn Kurooto on and open its dashboard'
$s.Save()
"""


def on_command(app: Path | None = None) -> list[str]:
    """`kurooto on`, through the launcher when installed (so it's the current version)."""
    cmd = command(app)
    return [*cmd, "cli", "on"] if cmd[-1].endswith("launcher.py") else [cmd[0], "-m", "kurooto", "on"]


def where(home: Path | None = None) -> Path:
    env = os.environ if home is None else {}  # a home given (tests): everything under it
    home = home or Path.home()
    if sys.platform == "win32":
        appdata = Path(env.get("APPDATA") or home / "AppData" / "Roaming")
        return appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Kurooto.lnk"
    if sys.platform == "darwin":
        return home / "Applications" / "Kurooto.app"
    data = Path(env.get("XDG_DATA_HOME") or home / ".local" / "share")
    return data / "applications" / "kurooto.desktop"


def create(home: Path | None = None) -> Path:
    path, cmd = where(home), on_command(app_dir(home))
    path.parent.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        import base64

        script = base64.b64encode(_PS.encode("utf-16-le")).decode()
        env = {
            **os.environ,
            "KUROOTO_LNK": str(path),
            "KUROOTO_TARGET": cmd[0],
            "KUROOTO_ARGS": " ".join(f'"{c}"' for c in cmd[1:]),
        }
        proc.run(["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", script], timeout=30, env=env)
    elif sys.platform == "darwin":
        (path / "Contents" / "MacOS").mkdir(parents=True, exist_ok=True)
        exe = path / "Contents" / "MacOS" / "Kurooto"
        exe.write_text("#!/bin/sh\nexec " + " ".join(f'"{c}"' for c in cmd) + "\n", encoding="utf-8")
        exe.chmod(0o755)
        (path / "Contents" / "Info.plist").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
            '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n<plist version="1.0"><dict>'
            "<key>CFBundleName</key><string>Kurooto</string><key>CFBundleExecutable</key><string>Kurooto</string>"
            "<key>CFBundleIdentifier</key><string>io.github.avtarfr.kurooto.launcher</string>"
            "<key>CFBundlePackageType</key><string>APPL</string><key>LSUIElement</key><true/></dict></plist>\n",
            encoding="utf-8",
        )
    else:
        exec_line = " ".join(f'"{c}"' if " " in c else c for c in cmd)
        path.write_text(
            "[Desktop Entry]\nType=Application\nName=Kurooto\nComment=Turn Kurooto on and open its dashboard\n"
            f"Exec={exec_line}\nTerminal=false\nCategories=Utility;\n",
            encoding="utf-8",
        )
    return path


def remove(home: Path | None = None) -> None:
    import shutil

    path = where(home)
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
    else:
        path.unlink(missing_ok=True)

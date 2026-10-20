"""Start Kurooto when you log in. No admin rights anywhere.

Windows  a value under HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run (runs pythonw: no window)
macOS    a LaunchAgent in ~/Library/LaunchAgents (starts at login, restarted if it dies)
Linux    a systemd user unit (restarted if it dies); an XDG autostart entry when systemd isn't there

At boot or at login (autostart.when, `kurooto autostart boot|login`): on Linux with systemd, "boot" turns on lingering
for your account (`loginctl enable-linger`), so Kurooto starts when the computer does, before anyone logs in: Telegram
and calls work after a power cut or a remote reboot. The keychain stays locked until you log in, so Kurooto's keys
are then kept in its owner-only settings file instead. Back to "login" turns lingering off again, only if Kurooto
turned it on. Windows and macOS start it at sign-in only: before it would need admin rights.
"""

from __future__ import annotations

import getpass
import os
import shutil
import sys
from pathlib import Path

from kurooto.core import proc
from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave

register_defaults("autostart", {"when": "login"})  # login | boot (Linux with systemd: before anyone logs in)

NAME = "Kurooto"
LABEL = "io.github.avtarfr.kurooto"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def command() -> list[str]:
    """How to start Kurooto at sign-in: the launcher when installed by the Kurooto installer (so updates and
    rollback work), otherwise this Python's supervisor. No console window on Windows."""
    from kurooto.core.paths import paths
    from kurooto.core.state import jload

    app = paths().app
    info = jload(app / "install.json", {}) or {}
    exe = Path(info.get("python") or sys.executable)
    if sys.platform == "win32":
        w = exe.with_name("pythonw.exe")
        exe = w if w.exists() else exe
    if (app / "launcher.py").exists() and info.get("python"):
        return [str(exe), str(app / "launcher.py")]
    return [str(exe), "-m", "kurooto", "supervise"]


def _env_lines() -> dict:
    keep = {k: os.environ[k] for k in ("KUROOTO_HOME",) if k in os.environ}
    return keep


def enable(home: Path | None = None) -> str:
    home = home or Path.home()
    cmd = command()
    if sys.platform == "win32":
        import winreg

        line = " ".join(f'"{c}"' for c in cmd)
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:  # may not exist yet
            winreg.SetValueEx(k, NAME, 0, winreg.REG_SZ, line)
        return "Kurooto starts when you sign in to Windows."
    if sys.platform == "darwin":
        plist = home / "Library" / "LaunchAgents" / f"{LABEL}.plist"
        plist.parent.mkdir(parents=True, exist_ok=True)
        args = "".join(f"<string>{c}</string>" for c in cmd)
        env = "".join(f"<key>{k}</key><string>{v}</string>" for k, v in _env_lines().items())
        plist.write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
            '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n<plist version="1.0"><dict>'
            f"<key>Label</key><string>{LABEL}</string><key>ProgramArguments</key><array>{args}</array>"
            f"<key>RunAtLoad</key><true/><key>KeepAlive</key><dict><key>SuccessfulExit</key><false/></dict>"
            + (f"<key>EnvironmentVariables</key><dict>{env}</dict>" if env else "")
            + "</dict></plist>\n",
            encoding="utf-8",
        )
        proc.run(["launchctl", "unload", str(plist)], timeout=15)
        proc.run(["launchctl", "load", "-w", str(plist)], timeout=15)
        return "Kurooto starts when you log in to your Mac."
    unit_dir = home / ".config" / "systemd" / "user"
    if shutil.which("systemctl"):
        unit_dir.mkdir(parents=True, exist_ok=True)
        env = "".join(f"Environment={k}={v}\n" for k, v in _env_lines().items())
        (unit_dir / "kurooto.service").write_text(
            "[Unit]\nDescription=Kurooto, your assistant\nAfter=network-online.target\n\n"
            f"[Service]\nExecStart={' '.join(cmd)}\n{env}Restart=on-failure\nRestartSec=10\n\n"
            "[Install]\nWantedBy=default.target\n",
            encoding="utf-8",
        )
        proc.run(["systemctl", "--user", "daemon-reload"], timeout=30)
        r = proc.run(["systemctl", "--user", "enable", "--now", "kurooto.service"], timeout=30)
        if r.ok:
            return "Kurooto starts when you log in (systemd user service)."
    desk = home / ".config" / "autostart" / "kurooto.desktop"
    desk.parent.mkdir(parents=True, exist_ok=True)
    desk.write_text(
        f"[Desktop Entry]\nType=Application\nName=Kurooto\nExec={' '.join(cmd)}\nX-GNOME-Autostart-enabled=true\n",
        encoding="utf-8",
    )
    return "Kurooto starts when you log in (desktop autostart)."


def disable(home: Path | None = None) -> str:
    home = home or Path.home()
    if sys.platform == "win32":
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
                winreg.DeleteValue(k, NAME)
        except FileNotFoundError:
            pass
        return "Kurooto no longer starts at sign-in."
    if sys.platform == "darwin":
        plist = home / "Library" / "LaunchAgents" / f"{LABEL}.plist"
        if plist.exists():
            proc.run(["launchctl", "unload", "-w", str(plist)], timeout=15)
            plist.unlink()
        return "Kurooto no longer starts at login."
    if shutil.which("systemctl"):
        proc.run(["systemctl", "--user", "disable", "--now", "kurooto.service"], timeout=30)
    for f in (
        home / ".config" / "systemd" / "user" / "kurooto.service",
        home / ".config" / "autostart" / "kurooto.desktop",
    ):
        f.unlink(missing_ok=True)
    return "Kurooto no longer starts at login."


def managed(home: Path | None = None) -> str | None:
    """Which service manager runs Kurooto here: "systemd", "launchd", or None (it runs on its own)."""
    home = home or Path.home()
    if sys.platform == "darwin" and (home / "Library" / "LaunchAgents" / f"{LABEL}.plist").exists():
        return "launchd"
    if (
        sys.platform.startswith("linux")
        and shutil.which("systemctl")
        and (home / ".config" / "systemd" / "user" / "kurooto.service").exists()
    ):
        return "systemd"
    return None


def service(action: str, home: Path | None = None) -> bool:
    """Stop or start Kurooto through its service manager, so `kurooto stop` isn't undone by a restart 10 s later
    and `kurooto start` doesn't run a second copy beside the managed one. False: not managed here."""
    home = home or Path.home()
    how = managed(home)
    if how == "systemd":  # where the user session doesn't work (WSL, containers) this fails: callers fall back
        return proc.run(["systemctl", "--user", action, "kurooto.service"], timeout=30).ok
    if how == "launchd":  # unload (without -w) holds it until the next login; load starts it again
        plist = home / "Library" / "LaunchAgents" / f"{LABEL}.plist"
        return proc.run(["launchctl", "unload" if action == "stop" else "load", str(plist)], timeout=15).ok
    return False


def status(home: Path | None = None) -> bool:
    home = home or Path.home()
    if sys.platform == "win32":
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
                winreg.QueryValueEx(k, NAME)
            return True
        except FileNotFoundError:
            return False
    if sys.platform == "darwin":
        return (home / "Library" / "LaunchAgents" / f"{LABEL}.plist").exists()
    return (home / ".config" / "systemd" / "user" / "kurooto.service").exists() or (
        home / ".config" / "autostart" / "kurooto.desktop"
    ).exists()


# --------------------------------------------------------------------------------------- at boot or at login
LINGER_DIR = Path("/var/lib/systemd/linger")  # systemd keeps one empty file per lingering account here


def lingering(user: str | None = None) -> bool:
    """Does this account's service manager start at boot (systemd's linger)?"""
    return (LINGER_DIR / (user or getpass.getuser())).exists()


def boot_possible(home: Path | None = None) -> tuple[bool, str]:
    if sys.platform == "win32":
        return False, (
            "Windows starts Kurooto when you sign in. Starting it before would need admin rights and your password "
            "kept in a scheduled task, so Kurooto doesn't."
        )
    if sys.platform == "darwin":
        return False, (
            "A Mac starts Kurooto when you log in; before that would need admin rights. If this Mac restarts on its "
            "own, automatic login (System Settings → Users & Groups) brings Kurooto back."
        )
    if not shutil.which("loginctl") or managed(home) != "systemd":
        return False, "Starting from boot needs systemd, with Kurooto as a user service (`kurooto autostart on`)."
    return True, ""


def when(settings) -> str:
    """ "boot" or "login": what you chose, and what's in effect."""
    return "boot" if settings.get("autostart.when") == "boot" else "login"


def set_when(choice: str, settings, secrets, state_dir: Path, home: Path | None = None) -> tuple[bool, str]:
    """Start at boot or at login. Turns lingering on (or off, if Kurooto turned it on) and moves Kurooto's keys to its
    file (or back to the keychain)."""
    from kurooto.modules.backups import known_secret_names

    mark = Path(state_dir) / "autostart.json"
    if choice == "boot":
        ok, why = boot_possible(home)
        if not ok:
            return False, why
        if not lingering():
            r = proc.run(["loginctl", "enable-linger"], timeout=30)
            if not r.ok or not lingering():
                return False, (
                    "Linux didn't allow that from here. In a terminal run `loginctl enable-linger` (it may ask for "
                    "your password), then `kurooto autostart boot` again."
                )
            jsave(mark, {"linger_by_kurooto": True})
        moved = secrets.keep_in_file(True, known_secret_names(secrets))
        settings.set("autostart.when", "boot")
        keys = (
            f" Its keys ({moved}) are kept in its owner-only settings file now: the keychain is locked until you log "
            "in."
            if moved
            else ""
        )
        return True, "Kurooto now starts when this computer starts, before anyone logs in." + keys
    if choice != "login":
        return False, "Say boot or login."
    note = ""
    if lingering():
        if (jload(mark, {}) or {}).get("linger_by_kurooto"):
            if proc.run(["loginctl", "disable-linger"], timeout=30).ok and not lingering():
                mark.unlink(missing_ok=True)
            else:
                note = " Linux kept lingering on: run `loginctl disable-linger` in a terminal."
        else:
            note = (
                " Your account's services were already set to start at boot (lingering, not by Kurooto), so it "
                "still starts then."
            )
    moved = secrets.keep_in_file(False, known_secret_names(secrets))
    settings.set("autostart.when", "login")
    keys = f" Its keys ({moved}) are back in the keychain." if moved else ""
    return True, "Kurooto starts when you log in." + keys + note


def forget_boot(state_dir: Path) -> None:
    """Uninstalling: turn lingering off again if Kurooto turned it on."""
    mark = Path(state_dir) / "autostart.json"
    if (jload(mark, {}) or {}).get("linger_by_kurooto") and shutil.which("loginctl"):
        proc.run(["loginctl", "disable-linger"], timeout=30)
        mark.unlink(missing_ok=True)

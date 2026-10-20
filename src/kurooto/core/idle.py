"""Are you at this computer? How long since your last keyboard or mouse input, and whether the screen is locked.
Nothing you type is read: only whether there was input, and when.

Windows  GetLastInputInfo; locked while the lock screen is in front.
macOS    the HID system's idle time (ioreg); locked from the console session's lock flag.
Linux    in order, the first that answers:
         - your idle tool's hook: `kurooto idle away` / `kurooto idle back` (hypridle, swayidle and xidlehook can run
           these on their timeout and resume; see the manual);
         - X11: xprintidle;
         - GNOME: Mutter's idle monitor; KDE and others: org.freedesktop.ScreenSaver's idle time;
         - logind's IdleHint, when the desktop sets it;
         - otherwise (Hyprland, Sway and other Wayland desktops): watching for change between samples: the
           keyboard and touchpad interrupt counts, the cursor (Hyprland) and the focused window.
         Locked: logind's LockedHint, the screensaver saying it's active, or a screen locker running (hyprlock,
         swaylock, ...).
"""

from __future__ import annotations

import getpass
import os
import re
import shutil
import sys
import time
from collections.abc import Callable
from pathlib import Path

from kurooto.core import proc
from kurooto.core.state import jload, jsave

LOCKERS = {
    "hyprlock",
    "swaylock",
    "gtklock",
    "waylock",
    "i3lock",
    "i3lock-color",
    "xsecurelock",
    "slock",
    "physlock",
    "kscreenlocker_greet",
    "xlock",
    "loginlockd",
}
INPUT_IRQ = re.compile(r"i8042|i2c|hid|elan|synaptics|keyboard|touchpad|mouse|kbd", re.I)
AWAY_FILE = "away.json"
RETRY_S = 600  # a desktop API that didn't answer is asked again after this long


def _run(args: list[str], timeout: float = 3) -> str:
    try:
        r = proc.run(args, timeout=timeout)
    except OSError:
        return ""
    return r.out.strip() if r.ok else ""


def _procs() -> set[str]:
    import psutil

    names = set()
    for p in psutil.process_iter(["name"]):
        n = (p.info.get("name") or "").lower()
        if n:
            names.add(n)
    return names


def _read(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def set_away(state_dir: Path, away: bool, clock: Callable[[], float] = time.time) -> str:
    """`kurooto idle away|back`: what an idle tool's timeout and resume hooks call."""
    f = Path(state_dir) / AWAY_FILE
    if away:
        if not (jload(f, {}) or {}).get("since"):
            jsave(f, {"since": clock()})
        return "away"
    f.unlink(missing_ok=True)
    return "back"


class IdleProbe:
    """One per watcher: the Wayland fallback remembers what it saw last time. The arguments exist for tests."""

    def __init__(
        self,
        state_dir: Path | None = None,
        *,
        platform: str | None = None,
        env: dict | None = None,
        run: Callable[[list[str]], str] = _run,
        which: Callable[[str], str | None] = shutil.which,
        procs: Callable[[], set[str]] = _procs,
        read: Callable[[str], str] = _read,
        clock: Callable[[], float] = time.time,
    ):
        self.state_dir = Path(state_dir) if state_dir else None
        self.platform = platform or sys.platform
        self.env = os.environ if env is None else env
        self.run, self.which, self.procs, self.read, self.clock = run, which, procs, read, clock
        self.how = ""  # which way answered last (for health lines and tests)
        self._last: tuple | None = None  # the Wayland fallback: what it saw, and since when
        self._changed = clock()
        self._ss: tuple[int, float] | None = None  # the screensaver's last idle reading, to learn its unit
        self._ss_unit = 0.001  # KDE answers in milliseconds; learned from readings if it's seconds
        self._session: str | None = None
        self._quiet: dict[str, float] = {}  # bus calls that got no answer, and when

    # ------------------------------------------------------------------------------------------ idle
    def idle_seconds(self, title: str | None = None) -> float | None:
        """Seconds since the last input, or None if this computer can't say. `title` is the focused window's (for the
        Wayland fallback)."""
        if self.platform == "win32":
            self.how = "windows"
            return self._windows_idle()
        if self.platform == "darwin":
            m = re.search(r'"HIDIdleTime" = (\d+)', self.run(["ioreg", "-c", "IOHIDSystem"]))
            self.how = "ioreg"
            return int(m.group(1)) / 1e9 if m else None
        for how in ("hook", "x11", "gnome", "screensaver", "logind"):
            v = getattr(self, f"_{how}")()
            if v is not None:
                self.how = how
                return v
        self.how = "watch"
        return self._watch(title)

    def _windows_idle(self) -> float | None:
        import ctypes

        class LastInput(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

        li = LastInput()
        li.cbSize = ctypes.sizeof(li)
        if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(li)):
            return ((ctypes.windll.kernel32.GetTickCount() - li.dwTime) & 0xFFFFFFFF) / 1000
        return None

    def _hook(self) -> float | None:
        if not self.state_dir:
            return None
        since = (jload(self.state_dir / AWAY_FILE, {}) or {}).get("since")
        return max(0.0, self.clock() - float(since)) if since else None

    def _x11(self) -> float | None:
        if self.env.get("WAYLAND_DISPLAY") or not self.env.get("DISPLAY") or not self.which("xprintidle"):
            return None
        v = self.run(["xprintidle"])
        return int(v) / 1000 if v.isdigit() else None

    def _dbus(self, dest: str, path: str, iface: str, method: str) -> str:
        """A call on your session bus (busctl, or gdbus): its answer, or "" if nothing answered. One that didn't
        answer isn't asked again for a while (this desktop doesn't have it)."""
        key = f"{dest} {method}"
        if self.clock() - self._quiet.get(key, -RETRY_S) < RETRY_S:
            return ""
        out = ""
        if self.which("busctl"):
            out = self.run(["busctl", "--user", "--auto-start=no", "--timeout=2", "call", dest, path, iface, method])
        elif self.which("gdbus"):
            out = self.run(
                ["gdbus", "call", "--session", "--dest", dest, "--object-path", path, "--method", f"{iface}.{method}"]
            )
        if out:
            self._quiet.pop(key, None)
        else:
            self._quiet[key] = self.clock()
        return out

    def _gnome(self) -> float | None:
        out = self._dbus(
            "org.gnome.Mutter.IdleMonitor",
            "/org/gnome/Mutter/IdleMonitor/Core",
            "org.gnome.Mutter.IdleMonitor",
            "GetIdletime",
        )
        m = re.search(r"(\d+)\D*$", out)
        return int(m.group(1)) / 1000 if m else None

    def _screensaver(self) -> float | None:
        out = self._dbus(
            "org.freedesktop.ScreenSaver",
            "/org/freedesktop/ScreenSaver",
            "org.freedesktop.ScreenSaver",
            "GetSessionIdleTime",
        )
        m = re.search(r"(\d+)\D*$", out)
        if not m:
            return None
        v, t = int(m.group(1)), self.clock()
        if self._ss is not None:  # learn the unit: idle time grows by the time between readings
            dv, dt = v - self._ss[0], t - self._ss[1]
            if dt >= 10 and dv > 0:
                rate = dv / dt
                if 0.5 <= rate <= 2:
                    self._ss_unit = 1.0
                elif rate >= 200:
                    self._ss_unit = 0.001
        self._ss = (v, t)
        return v * self._ss_unit

    def _logind_props(self) -> dict:
        if not self.which("loginctl"):
            return {}
        if self._session is None:
            sid = self.env.get("XDG_SESSION_ID") or self.run(
                ["loginctl", "show-user", self.env.get("USER") or getpass.getuser(), "-p", "Display", "--value"]
            )
            self._session = sid.strip()
        if not self._session:
            return {}
        out = self.run(
            ["loginctl", "show-session", self._session, "-p", "IdleHint", "-p", "IdleSinceHint", "-p", "LockedHint"]
        )
        return dict(line.split("=", 1) for line in out.splitlines() if "=" in line)

    def _logind(self) -> float | None:
        """Only "idle" counts: a desktop that never sets IdleHint always says no."""
        p = self._logind_props()
        if p.get("IdleHint") != "yes":
            return None
        try:
            since = int(p.get("IdleSinceHint") or 0) / 1e6
        except ValueError:
            since = 0
        return max(0.0, self.clock() - since) if since else 0.0

    def _watch(self, title: str | None) -> float | None:
        """No idle API: the time since anything changed (input interrupts, the cursor, the focused window)."""
        irq = 0
        for line in self.read("/proc/interrupts").splitlines():
            if INPUT_IRQ.search(line):
                irq += sum(int(x) for x in line.split()[1:] if x.isdigit())
        cursor = self.run(["hyprctl", "cursorpos"]) if self.env.get("HYPRLAND_INSTANCE_SIGNATURE") else ""
        seen = (irq, cursor, title)
        if not irq and not cursor and title is None:
            return None  # nothing to watch
        now = self.clock()
        if seen != self._last:
            self._last, self._changed = seen, now
        return now - self._changed

    # ---------------------------------------------------------------------------------------- locked
    def locked(self) -> bool:
        """Is the screen locked?"""
        try:
            if self.platform == "win32":
                return self._windows_locked()
            if self.platform == "darwin":
                return bool(
                    re.search(r'"CGSSessionScreenIsLocked"\s*=\s*Yes', self.run(["ioreg", "-n", "Root", "-d1"]))
                )
            if self._logind_props().get("LockedHint") == "yes":
                return True
            for dest, path in (
                ("org.freedesktop.ScreenSaver", "/org/freedesktop/ScreenSaver"),
                ("org.gnome.ScreenSaver", "/org/gnome/ScreenSaver"),
            ):
                out = self._dbus(dest, path, dest, "GetActive")
                if re.search(r"\btrue\b", out):
                    return True
            return bool(LOCKERS & self.procs())
        except Exception:
            return False

    def _windows_locked(self) -> bool:
        import ctypes

        import psutil

        user32 = ctypes.windll.user32
        h = user32.GetForegroundWindow()
        if not h:
            return False
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
        try:
            return psutil.Process(pid.value).name().lower() == "lockapp.exe"
        except psutil.Error:
            return False

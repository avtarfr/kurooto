"""Keeping this computer awake for a while, on every OS. Stay awake on charger holds it while plugged in; the morning
alarm can hold it until the alarm, so the day's plan is drafted before it rings.

Linux    systemd-inhibit (sleep, and with lid=True the lid switch too); with idle=True, also idle (the screen stays
         on under some desktops). Some systems don't let a background program hold the lid switch: then it holds
         the rest and says so.
macOS    caffeinate (-i: no idle sleep; with ac_only, -s: only while plugged in). Closing the lid still sleeps a Mac
         unless an external display is attached; no app can change that without admin rights.
Windows  SetThreadExecutionState from a thread that holds it. The lid follows Power Options ("Choose what closing the
         lid does"); no app can change that without admin rights.

A hold given a length ends by itself; one without a length ends when Kurooto stops, even if it crashes.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Callable

from kurooto.core import proc

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001


def _same_end(a: float | None, b: float | None) -> bool:
    """Two hold lengths that end within a minute of each other are the same hold."""
    return (a is None and b is None) or (a is not None and b is not None and abs(a - b) < 60)


def _set_state(flags: int) -> int:
    import ctypes

    return ctypes.windll.kernel32.SetThreadExecutionState(flags)


class Inhibitor:
    """One hold: hold() starts it (or keeps it), release() ends it. The arguments after `why` exist for tests."""

    def __init__(
        self,
        who: str = "Kurooto",
        why: str = "",
        *,
        platform: str | None = None,
        popen: Callable[..., subprocess.Popen] = subprocess.Popen,
        which: Callable[[str], str | None] = shutil.which,
        set_state: Callable[[int], int] | None = None,
        clock: Callable[[], float] = time.time,
    ):
        self.who, self.why = who, why
        self.platform = platform or sys.platform
        self.popen, self.which, self.clock = popen, which, clock
        self.set_state = set_state or _set_state
        self.proc: subprocess.Popen | None = None
        self.what = ""  # what the running hold covers (Linux): "sleep", "sleep:handle-lid-switch", ...
        self.until: float | None = None  # when it ends by itself; None = until released
        self.lid_refused = False  # this system wouldn't let us hold the lid switch
        self._started = 0.0
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    # ------------------------------------------------------------------------------------------ what
    def supported(self) -> tuple[bool, str]:
        if self.platform == "win32":
            return True, ""
        if self.platform == "darwin":
            return (True, "") if self.which("caffeinate") else (False, "needs caffeinate, which this Mac doesn't have")
        if self.which("systemd-inhibit"):
            return True, ""
        return False, "needs systemd-inhibit (systemd), which this computer doesn't have"

    def held(self) -> bool:
        if self.until is not None and self.clock() >= self.until:
            return False
        if self.platform == "win32":
            return self._thread is not None and self._thread.is_alive()
        return self.proc is not None and self.proc.poll() is None

    # ------------------------------------------------------------------------------------------ hold
    def hold(
        self, seconds: float | None = None, *, lid: bool = False, idle: bool = False, ac_only: bool = False
    ) -> bool:
        """Hold it for `seconds` (None: until released). Already held the same way: kept (a new length restarts it).
        True when it's held now."""
        until = None if seconds is None else self.clock() + max(1.0, float(seconds))
        if self.platform == "win32":
            return self._hold_windows(until)
        if self.platform == "darwin":
            args = ["caffeinate", "-s" if ac_only else "-is", "-w", str(os.getpid())]
            if until is not None:
                args += ["-t", str(int(until - self.clock()))]
            return self._hold_proc(args, f"caffeinate {args[1]}", until)
        self._notice_refusal()
        parts = ["sleep"] + (["idle"] if idle else []) + (["handle-lid-switch"] if lid and not self.lid_refused else [])
        what = ":".join(parts)
        if until is not None:
            wait = ["sleep", str(int(until - self.clock()))]
        elif self.which("tail"):  # until released, or until Kurooto stops (even if it crashes)
            wait = ["tail", f"--pid={os.getpid()}", "-f", "/dev/null"]
        else:
            wait = ["sleep", "infinity"]
        args = [
            "systemd-inhibit",
            f"--what={what}",
            f"--who={self.who}",
            f"--why={self.why or 'Kurooto keeps this computer awake'}",
            "--mode=block",
            *wait,
        ]
        return self._hold_proc(args, what, until)

    def _hold_proc(self, args: list[str], what: str, until: float | None) -> bool:
        if self.held() and what == self.what and _same_end(until, self.until):
            return True
        exe = self.which(args[0])
        if not exe:
            return False
        self.release()
        try:
            self.proc = self.popen(
                [exe, *args[1:]],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError:
            self.proc = None
            return False
        self.what, self.until, self._started = what, until, self.clock()
        return True

    def _notice_refusal(self) -> None:
        """A lid hold that ended at once was refused (the system's policy): hold without the lid from now on."""
        p = self.proc
        if p is None or "handle-lid-switch" not in self.what:
            return
        code = p.poll()
        if code not in (None, 0) and self.clock() - self._started < 120:
            self.lid_refused = True
            self.proc = None

    def _hold_windows(self, until: float | None) -> bool:
        if self.held() and _same_end(until, self.until):
            return True
        self.release()
        self._stop = threading.Event()
        stop, set_state = self._stop, self.set_state
        wait = None if until is None else max(0.0, until - self.clock())

        def run():  # the flag belongs to this thread: it holds while the thread waits
            try:
                set_state(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
                stop.wait(wait)
            finally:
                set_state(ES_CONTINUOUS)

        self._thread = threading.Thread(target=run, name="stay-awake", daemon=True)
        self._thread.start()
        self.until = until
        return True

    def release(self) -> None:
        if self._thread is not None:
            self._stop.set()
            self._thread.join(timeout=5)
            self._thread = None
        p, self.proc = self.proc, None
        if p is not None and p.poll() is None:
            proc.kill_tree(p.pid)
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
        self.what, self.until = "", None

    def describe(self) -> str:
        """What it holds, in words (for health lines)."""
        if not self.held():
            return ""
        lid = "handle-lid-switch" in self.what
        end = "" if self.until is None else f" until {time.strftime('%H:%M', time.localtime(self.until))}"
        return ("awake, lid closed too" if lid else "awake") + end

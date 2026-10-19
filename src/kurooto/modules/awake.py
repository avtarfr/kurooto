"""Stay awake on charger: while this computer is plugged in, it doesn't go to sleep by itself, so Kurooto keeps
answering (Telegram, calls, your schedule). On battery it sleeps as usual. Your screen can still turn off.

Closing a laptop's lid usually still puts it to sleep: if you want it to keep running with the lid closed, change
the lid setting (Windows: Control Panel → Power Options → "Choose what closing the lid does" → "Do nothing" when
plugged in; macOS: only with an external display; Linux: your desktop's power settings).
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import sys

import psutil

from kurooto.core import proc
from kurooto.modules.base import Module

ES_SYSTEM_REQUIRED = 0x00000001


def on_ac() -> bool:
    try:
        b = psutil.sensors_battery()
    except Exception:
        b = None
    return True if b is None else bool(b.power_plugged)  # no battery: a desktop, always plugged in


class Awake(Module):
    id = "awake"
    title = "Stay awake on charger"
    description = "While plugged in, this computer doesn't sleep by itself, so Kurooto stays reachable."
    privacy = "Stays on this computer."

    def __init__(self, app):
        super().__init__(app)
        self.holder: subprocess.Popen | None = None
        self.holding = False

    def ready(self):
        if sys.platform.startswith("linux") and not shutil.which("systemd-inhibit"):
            return False, "needs systemd-inhibit (systemd), which this computer doesn't have"
        return True, ""

    def health(self):
        ok, why = self.ready()
        if not ok:
            return ok, why
        return True, ("keeping it awake (plugged in)" if self.holding else "on battery: sleeping as usual")

    async def background(self, stop: asyncio.Event) -> None:
        try:
            while not stop.is_set():
                await asyncio.to_thread(self.tick)
                try:
                    await asyncio.wait_for(stop.wait(), timeout=30)
                except TimeoutError:
                    pass
        finally:
            self.release()

    def tick(self) -> None:
        plugged = on_ac()
        if sys.platform == "win32":
            if plugged:  # resets the sleep timer; doesn't keep the screen on
                import ctypes

                ctypes.windll.kernel32.SetThreadExecutionState(ES_SYSTEM_REQUIRED)
            self._mark(plugged)
        elif sys.platform == "darwin":
            # caffeinate -s holds off sleep only while on AC by itself, and quits when Kurooto does
            if self.holder is None or self.holder.poll() is not None:
                self.holder = subprocess.Popen(
                    ["caffeinate", "-s", "-w", str(os.getpid())],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            self._mark(plugged)
        else:
            alive = self.holder is not None and self.holder.poll() is None
            if plugged and not alive and shutil.which("systemd-inhibit"):
                self.holder = subprocess.Popen(
                    [
                        "systemd-inhibit",
                        "--what=sleep:idle",
                        "--who=Kurooto",
                        "--mode=block",
                        "--why=Stay awake on charger (turn it off in Kurooto's settings)",
                        "sleep",
                        "infinity",
                    ],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
            elif not plugged and alive:
                self.release()
            self._mark(plugged and self.holder is not None and self.holder.poll() is None)

    def _mark(self, holding: bool) -> None:
        if holding != self.holding:
            self.holding = holding
            self.app.events.emit("awake_" + ("holding" if holding else "released"))

    def release(self) -> None:
        if self.holder is not None and self.holder.poll() is None:
            proc.kill_tree(self.holder.pid)
            try:
                self.holder.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
        self.holder = None
        self._mark(False)

    def stop(self):
        super().stop()
        self.release()

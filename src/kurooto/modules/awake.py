"""Stay awake on charger: while this computer is plugged in, it doesn't go to sleep by itself, so Kurooto keeps
answering (Telegram, calls, your schedule). On battery it sleeps as usual. Your screen can still turn off.

Closing a laptop's lid usually still puts it to sleep. On Linux, turn on awake.lid (Settings) and it keeps running
with the lid closed while plugged in. Elsewhere it's the system's own setting (Windows: Control Panel → Power Options
→ "Choose what closing the lid does" → "Do nothing" when plugged in; macOS: only with an external display).
"""

from __future__ import annotations

import asyncio
import sys

import psutil

from kurooto.core.config import register_defaults
from kurooto.core.inhibit import Inhibitor
from kurooto.modules.base import Module

register_defaults("awake", {"lid": False})  # Linux: also keep running with the lid closed while plugged in


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
        self.inhibitor = Inhibitor(why="Stay awake on charger (turn it off in Kurooto's settings)")
        self.holding = False

    @property
    def holder(self):
        """The process holding it (Linux, macOS), or None."""
        return self.inhibitor.proc

    def ready(self):
        return self.inhibitor.supported()

    def health(self):
        ok, why = self.ready()
        if not ok:
            return ok, why
        if not self.holding:
            return True, "on battery: sleeping as usual"
        lid = ""
        if self.setting("lid"):
            if not sys.platform.startswith("linux"):
                lid = "; the lid follows your system's own setting"
            elif self.inhibitor.lid_refused:
                lid = "; this system doesn't let it hold the lid switch, so closing the lid still sleeps"
            else:
                lid = ", lid closed too"
        return True, f"keeping it awake (plugged in{lid})"

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
        if on_ac():  # idle too: some desktops put it to sleep by their own idle timer otherwise
            self._mark(self.inhibitor.hold(lid=bool(self.setting("lid")), idle=True, ac_only=True))
        else:
            self.release()

    def _mark(self, holding: bool) -> None:
        if holding != self.holding:
            self.holding = holding
            self.app.events.emit("awake_" + ("holding" if holding else "released"))

    def release(self) -> None:
        self.inhibitor.release()
        self._mark(False)

    def stop(self):
        super().stop()
        self.release()

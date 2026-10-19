"""Taking your laptop with you: what Kurooto does on battery, pausing it by hand, and turning it off completely.

Modes, worked out every 30 seconds:
    normal  everything runs
    saver   on battery with power.on_battery = "saver" (the default): everything that leans on the laptop waits for
            the charger. Local AI models are unloaded; the notes index, handwriting, research, notes sync, the
            nightly look back and AI work you didn't ask for are put off, and run the moment it's plugged in.
            Telegram keeps working: messages, commands, reminders, and answers to what you ask.
    paused  /pause (or `kurooto pause`), or on battery with power.on_battery = "pause": nothing runs. Telegram keeps
            what you send and answers "paused" (so /resume still works); your call line keeps placing scheduled
            calls (the alarm still rings); everything catches up when it resumes.

Off (`kurooto off`, or the dashboard) is different: Kurooto stops completely and doesn't start at sign-in until you
turn it on again (`kurooto on`, or the Kurooto shortcut in your app menu).
"""

from __future__ import annotations

import asyncio
import datetime as dt
import threading
import time
from typing import TYPE_CHECKING

import psutil

from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave

if TYPE_CHECKING:
    from kurooto.app import App
    from kurooto.core.scheduler import Job

register_defaults("power", {"on_battery": "saver"})  # saver | normal | pause
MODES = ("normal", "saver", "paused")


def on_ac() -> bool:
    try:
        b = psutil.sensors_battery()
    except Exception:
        b = None
    return True if b is None else bool(b.power_plugged)  # no battery: a desktop, always plugged in


class Power:
    def __init__(self, app: App, on_ac=on_ac):
        self.app = app
        self.on_ac = on_ac
        self.file = app.paths.state / "pause.json"
        self.held_file = app.paths.state / "power-held.json"
        self._lock = threading.Lock()
        self.current = self.mode()

    # ------------------------------------------------------------------------------------- the mode
    def paused_until(self) -> float | None:
        """A pause you asked for: its end (a timestamp; inf = until you resume), or None."""
        p = jload(self.file, {}) or {}
        if not p.get("paused"):
            return None
        until = p.get("until")
        if until is not None and until <= time.time():
            self.file.unlink(missing_ok=True)
            return None
        return float("inf") if until is None else float(until)

    def mode(self) -> str:
        if self.paused_until():
            return "paused"
        if not self.on_ac():
            setting = self.app.settings.get("power.on_battery") or "saver"
            return {"pause": "paused", "saver": "saver"}.get(setting, "normal")
        return "normal"

    def why(self) -> str:
        until = self.paused_until()
        if until:
            if until == float("inf"):
                return "until you resume me"
            return f"until {dt.datetime.fromtimestamp(until):%a %H:%M}"
        if self.mode() != "normal":
            return "while this laptop is on battery"
        return ""

    def pause(self, minutes: float | None = None) -> str:
        until = None if minutes is None else time.time() + minutes * 60
        jsave(self.file, {"paused": True, "until": until, "at": time.time()})
        self.app.events.emit("power_pause", minutes=minutes)
        self.apply()
        return f"Paused {self.why()}. /resume wakes me."

    def resume(self) -> str:
        self.file.unlink(missing_ok=True)
        self.app.events.emit("power_resume")
        self.apply()
        if self.current == "normal":
            return "Back on."
        return "Back on; this laptop is on battery, so heavy work still waits for the charger."

    def may_run(self, m) -> bool:
        """May this feature's work run now? (Telegram always may: it answers even when paused.)"""
        if self.current == "paused":
            return m.id == "telegram"
        return not (self.current == "saver" and getattr(m, "heavy", False))

    # ------------------------------------------------------------------------------------- effects
    def hold(self, job: Job) -> float | None:
        """The scheduler asks before running a job: None to run it now, or when to look again. Held jobs are
        released the moment the mode allows them (release()); the time returned is only a backstop."""
        if self.current == "normal":
            return None
        m = self.app.modules.get(job.module)
        if m is not None and self.may_run(m):
            return None
        if m is None and self.current != "paused":
            return None
        with self._lock:
            held = jload(self.held_file, {}) or {}
            held[job.key] = job.module
            jsave(self.held_file, held)
        return time.time() + 3600

    def release(self) -> int:
        """Run, at once, the held jobs that the current mode allows."""
        with self._lock:
            held = jload(self.held_file, {}) or {}
            go = []
            for key, mid in list(held.items()):
                m = self.app.modules.get(mid)
                if self.current == "normal" or (m is not None and self.may_run(m)):
                    go.append(key)
                    held.pop(key)
            jsave(self.held_file, held)
        for key in go:
            if self.app.scheduler.get(key):
                self.app.scheduler._set_next(key, time.time())
        return len(go)

    def apply(self) -> str:
        """Bring Kurooto in line with the mode, if it changed."""
        new = self.mode()
        if new == self.current:
            return new
        old, self.current = self.current, new
        app = self.app
        for m in app.enabled():
            if not hasattr(m, "background") or m.id == "telegram":
                continue
            if not self.may_run(m):
                app.stop_background(m)
            elif old != "normal":
                app.start_background(m)
        for m in app.enabled():
            rest = getattr(m, "rest", None)  # e.g. Local models: unload the models, stop the server we started
            if rest and not self.may_run(m):
                try:
                    rest()
                except Exception as e:
                    app.events.emit("power_rest_failed", module=m.id, error=str(e)[:200])
        app.jobs.poke()
        self.release()
        app.scheduler._poke()
        if old == "paused":  # what you sent on Telegram meanwhile
            tg = app.modules.get("telegram")
            if tg and app.is_on("telegram"):
                threading.Thread(target=tg.replay_paused, name="replay", daemon=True).start()
        app.events.emit("power_mode", mode=new, was=old)
        return new

    async def watch(self, stop: asyncio.Event) -> None:
        while not stop.is_set():
            try:
                await asyncio.to_thread(self.apply)
            except Exception as e:
                self.app.events.emit("power_failed", error=str(e)[:200])
            try:
                await asyncio.wait_for(stop.wait(), timeout=30)
            except TimeoutError:
                pass

    # ------------------------------------------------------------------------------------------ off
    @property
    def off_file(self):
        return self.app.paths.state / "off.json"

    def off(self, keep_calls: bool = False) -> None:
        """Turn Kurooto off completely (runs inside the assistant). It stops, and doesn't start at sign-in until
        `kurooto on`. Unless keep_calls, your call line is told not to place scheduled calls meanwhile."""
        from kurooto.core import autostart

        app = self.app
        jsave(self.off_file, {"at": time.time(), "keep_calls": keep_calls})
        app.events.emit("power_off", keep_calls=keep_calls)
        calls = app.modules.get("calls")
        if calls and app.is_on("calls") and not keep_calls:
            calls.silence_line()
        for m in app.enabled():
            rest = getattr(m, "rest", None)
            if rest:
                try:
                    rest()
                except Exception:
                    pass
        try:
            autostart.disable()  # under systemd or launchd this also stops us, which is the point
        finally:
            app.request_stop()

"""Updates while Kurooto runs. Settings → updates.mode:
    night (default)  download and prepare when one appears; switch over between 03:00 and 05:00 when you're not
                     on a call and nothing is running
    ask              a Telegram message with Update / Later / Skip this version
    off              only a note in the dashboard
After switching, the new version is on probation for 5 minutes; if it keeps crashing, the launcher goes back.
A feature can hold back non-critical updates for a while (Exam season, during your exams: `holds`); a release signed
as critical installs anyway.

Staged updates (updates.staged, off until you turn it on): a new version installs only once it has been out
updates.wait_hours (48) without being withdrawn, and never during your exams (an exam period in Subjects, or a quiz
or exam within a day in Deadlines; updates.exam_hold). A release signed as critical skips both. Whatever the setting,
a version on the maintainer's signed yank list is never installed, even one already downloaded and waiting for the
night.

With Phone calls on, the Android app named in the running version's signed manifest is downloaded after an update
(update/phone_app.py: a couple of minutes after a start, then every 6 hours, which costs nothing once it's here); the
call line serves it and its next redeploy (05:10) takes it.
"""

from __future__ import annotations

import datetime as dt
import os
import random
import threading
import time
from collections.abc import Callable
from typing import TYPE_CHECKING

from kurooto import __version__
from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave
from kurooto.update import phone_app
from kurooto.update.updater import PAGES, UpdateError, Updater, vtuple

if TYPE_CHECKING:
    from kurooto.app import App

register_defaults(
    "updates",
    {
        "mode": "night",
        "channel": "stable",
        "window": ["03:00", "05:00"],
        "staged": False,  # wait until a release has been out wait_hours, and not during exams (critical ones don't)
        "wait_hours": 48,
        "exam_hold": True,  # with staged on: nothing installs in an exam period or within a day of a quiz or exam
    },
)


class Updates:
    def __init__(self, app: App):
        self.app = app
        extra = os.environ.get("KUROOTO_EXTRA_UPDATE_KEY")  # for testing a release pipeline; never set by Kurooto
        from kurooto.update import signing

        keys = list(signing.PUBLIC_KEYS) + ([extra] if extra else [])
        self.u = Updater(app.paths.app, app.paths.state, os.environ.get("KUROOTO_UPDATE_BASE") or PAGES, keys)
        self.ready_file = app.paths.state / "update-ready.json"
        self._busy = threading.Lock()
        # features that hold back non-critical updates for a while: name -> fn() giving the reason ("" = no hold);
        # exam season holds them during your exams (modules/exam_season.py)
        self.holds: dict[str, Callable[[], str]] = {}
        self.clock = time.time  # what hold() reads as now (tests move it)

    def held(self) -> str:
        """Why a non-critical update waits now ("" when it doesn't). A release signed as critical never waits, and
        neither do `kurooto update` and an Update tap."""
        for fn in list(self.holds.values()):
            try:
                why = fn()
            except Exception:
                why = ""
            if why:
                return str(why)
        return ""

    def start(self) -> None:
        s = self.app.scheduler
        s.action("updates.check", lambda p: self.check())
        s.action("updates.apply", lambda p: self.apply_if_quiet())
        s.action("updates.probation", lambda p: self.end_probation())
        s.action("updates.rolled_back", lambda p: self.tell_rolled_back())
        s.action("updates.phone_app", lambda p: self.phone_app())
        s.every("updates:check", "every 6h", "updates.check")
        s.every("updates:phone_app", "every 6h", "updates.phone_app")
        s.at(now() + dt.timedelta(minutes=2), "updates.phone_app", key="updates:phone_app:start")
        ready = str((jload(self.ready_file, None) or {}).get("version") or "")
        if ready and (vtuple(ready) <= vtuple(__version__) or ready in self.u.bad() or ready in self.u.yanked(False)):
            self.ready_file.unlink(missing_ok=True)  # installed (`kurooto update --now` leaves it), or rolled back
        u = jload(self.app.paths.app / "update.json", {}) or {}
        if u.get("phase") == "trial" and u.get("to") == __version__:
            s.at(now() + dt.timedelta(minutes=5, seconds=10), "updates.probation", key="updates:probation")
        if u.get("phase") == "rolled_back" and u.get("to") == __version__ and not u.get("told"):
            s.at(now() + dt.timedelta(seconds=30), "updates.rolled_back", key="updates:rolled_back")

    def status(self) -> dict:
        return {
            "version": __version__,
            "managed": self.u.managed(),
            "mode": self.app.settings.get("updates.mode"),
            "ready": jload(self.ready_file, None),
            "update": jload(self.app.paths.app / "update.json", None),
        }

    # ------------------------------------------------------------------------------------- the steps
    def check(self) -> str:
        if not self.u.managed():
            return "updates are handled by however Kurooto was installed here"
        mode = self.app.settings.get("updates.mode") or "night"
        try:
            rel = self.u.check(self.app.settings.get("updates.channel") or "stable")
        except (UpdateError, OSError, ValueError) as e:
            self.app.events.emit("update_check_failed", error=str(e)[:200])
            return f"check failed: {e}"
        if not rel:
            if self.u.withdrawn:  # on the maintainer's signed yank list
                v, why = next(iter(self.u.withdrawn.items()))
                self.app.events.emit("update_yanked", version=v)
                return f"{v} was withdrawn ({why}); not installing it"
            return "up to date"
        self.app.events.emit("update_found", version=rel.version)
        wait = self.hold(rel.issued, rel.critical)
        if wait:
            jsave(self.ready_file, {"version": rel.version, "staged": False, "notes": rel.notes, "waiting": wait})
            self.app.events.emit("update_waiting", version=rel.version, why=wait)
            return f"{rel.version} waits: {wait}"
        if mode == "off":
            jsave(self.ready_file, {"version": rel.version, "staged": False, "notes": rel.notes})
            return f"{rel.version} available (updates are off)"
        why = "" if rel.critical else self.held()
        if why:
            jsave(self.ready_file, {"version": rel.version, "staged": False, "notes": rel.notes, "held": why})
            self.app.events.emit("update_held", version=rel.version)
            return f"{rel.version} is held back: {why}"
        if mode == "ask":
            self.app.notify(
                f"Kurooto {rel.version} is available.\n\n{rel.notes[:1500]}".strip(),
                kind="update",
                buttons=[
                    [
                        ("Update", f"upd:{rel.version}:now"),
                        ("Later", f"upd:{rel.version}:later"),
                        ("Skip this version", f"upd:{rel.version}:skip"),
                    ]
                ],
                why="updates.available",
                about=rel.version,
            )
            jsave(self.ready_file, {"version": rel.version, "staged": False, "notes": rel.notes})
            return f"asked about {rel.version}"
        threading.Thread(target=self._stage_then_wait, args=(rel,), daemon=True).start()
        return f"preparing {rel.version}"

    def phone_app(self) -> str:
        """The Android app for the version that runs, from its signed release, for the call line to serve
        (update/phone_app.py). Only with Phone calls on and updates not off."""
        if not self.app.is_on("calls") or (self.app.settings.get("updates.mode") or "night") == "off":
            return "skipped"
        try:
            got = phone_app.ensure(self.u, self.app.paths.data, __version__)
        except (UpdateError, OSError, ValueError) as e:
            self.app.events.emit("phone_app_failed", error=str(e)[:200])
            return f"failed: {e}"
        if got == "fetched":
            self.app.events.emit("phone_app_fetched", version=__version__)
        return got

    def _install_info(self) -> tuple[str, str]:
        info = jload(self.app.paths.app / "install.json", {}) or {}
        if not info.get("uv") or not info.get("python"):
            raise UpdateError("install.json is missing; run the installer again to repair")
        return info["uv"], info["python"]

    def _stage(self, rel) -> bool:
        with self._busy:
            try:
                uv, py = self._install_info()
                self.u.stage(rel, uv, py, progress=lambda line: self.app.events.emit("update_progress", line=line))
            except Exception as e:
                self.app.events.emit("update_failed", version=rel.version, error=str(e)[:300])
                self.app.notify(
                    f"Couldn't prepare Kurooto {rel.version}: {str(e)[:300]}. I'll try again later.",
                    kind="update",
                    why="updates.failed",
                    about=rel.version,
                )
                return False
            jsave(
                self.ready_file,
                {
                    "version": rel.version,
                    "staged": True,
                    "notes": rel.notes,
                    "issued": rel.issued,
                    "critical": rel.critical,
                },
            )
            return True

    def _stage_then_wait(self, rel) -> None:
        if self._stage(rel):
            start, end = self.app.settings.get("updates.window") or ["03:00", "05:00"]
            t = now()
            at = dt.datetime.combine(t.date(), dt.time.fromisoformat(start))
            if at <= t:
                at += dt.timedelta(days=1)
            span = (dt.datetime.combine(at.date(), dt.time.fromisoformat(end)) - at).total_seconds()
            at += dt.timedelta(seconds=random.randint(0, max(0, int(span) - 600)))  # noqa: S311 (spreading load)
            self.app.scheduler.at(at, "updates.apply", key="updates:apply", grace_s=6 * 3600)

    def apply_if_quiet(self) -> str:
        ready = jload(self.ready_file, None)
        if not ready or not ready.get("staged"):
            return "nothing staged"
        why = "" if ready.get("critical") else self.held()
        if why:  # prepared before the hold began: the same window tomorrow night
            self.app.scheduler.at(now() + dt.timedelta(days=1), "updates.apply", key="updates:apply", grace_s=6 * 3600)
            return f"held back: {why}"
        busy = self.app.jobs._read("select 1 from jobs where status in ('queued','running') limit 1")
        on_call = self.app.availability.call_block()[0] == "you're on a call"
        if busy or on_call:
            self.app.scheduler.at(now() + dt.timedelta(minutes=20), "updates.apply", key="updates:apply")
            return "busy; trying again in 20 min"
        version = str(ready["version"])
        try:
            yanked = self.u.yanked()  # withdrawn since it was downloaded? (offline: the last list seen)
        except UpdateError as e:
            self.app.events.emit("update_check_failed", error=str(e)[:200])
            self.app.scheduler.at(now() + dt.timedelta(days=1), "updates.apply", key="updates:apply", grace_s=6 * 3600)
            return f"not switching: {e}"
        if version in yanked:
            self.ready_file.unlink(missing_ok=True)
            self.app.events.emit("update_yanked", version=version)
            return f"{version} was withdrawn ({yanked[version]}); not installing it"
        wait = self.hold(float(ready.get("issued") or 0), bool(ready.get("critical")))
        if wait:
            self.app.events.emit("update_waiting", version=version, why=wait)
            self.app.scheduler.at(now() + dt.timedelta(days=1), "updates.apply", key="updates:apply", grace_s=6 * 3600)
            return f"{version} waits: {wait}"
        return self.switch_to(version)

    def hold(self, issued: float, critical: bool = False) -> str:
        """Why a release waits (updates.staged), or "" when it may install now. A critical release never waits."""
        s = self.app.settings
        if critical or not s.get("updates.staged"):
            return ""
        hours = float(s.get("updates.wait_hours") or 0)
        if issued and self.clock() < issued + hours * 3600:
            until = dt.datetime.fromtimestamp(issued + hours * 3600)
            return f"it has been out less than {hours:g} h (until {until:%a %d %b %H:%M})"
        return self.exams() if s.get("updates.exam_hold") else ""

    def exams(self) -> str:
        """Your exams, if they're now: an exam period (Subjects), or a quiz or exam within a day (Deadlines)."""
        sub = self.app.modules.get("subjects")
        if sub is not None and self.app.is_on("subjects") and sub.no_classes(now().date()) == "exams":
            return "you're in an exam period"
        dl = self.app.modules.get("deadlines")
        if dl is not None and self.app.is_on("deadlines"):
            soon = dl.exams_soon(1)
            if soon:
                return f"{soon[0]['title']} is within a day"
        return ""

    def switch_to(self, version: str) -> str:
        self.u.switch(version)
        (self.ready_file).unlink(missing_ok=True)
        self.app.events.emit("update_switch", to=version, previous=__version__)
        self.app.request_restart()
        return f"switching to {version}"

    def end_probation(self) -> None:
        if self.u.probation_passed(__version__):
            self.u.prune()
            self.app.notify(f"Kurooto updated to {__version__}.", kind="update", why="updates.done")

    def tell_rolled_back(self) -> None:
        """The launcher went back to this version because the new one kept crashing: say so, once."""
        f = self.app.paths.app / "update.json"
        u = jload(f, {}) or {}
        if u.get("phase") != "rolled_back" or u.get("to") != __version__ or u.get("told"):
            return
        jsave(f, {**u, "told": time.time()})
        self.app.notify(
            f"Kurooto {u.get('from')} didn't start properly, so I went back to {__version__}. "
            "It won't be installed again; a later version will be.",
            kind="update",
            why="updates.rolled_back",
        )

    def button(self, version: str, act: str) -> str:
        if act == "skip":
            bad = self.u.bad()
            if version not in bad:
                jsave(self.app.paths.app / "bad.json", [*bad, version])
            return f"Skipping {version}."
        if act == "later":
            return "OK, I'll ask again later."
        rel = self.u.check(self.app.settings.get("updates.channel") or "stable")
        if not rel:
            if self.u.withdrawn:
                return f"{next(iter(self.u.withdrawn))} was withdrawn by its maintainer, so I'm not installing it."
            return "Already up to date."

        def go():
            if self._stage(rel):
                self.switch_to(rel.version)

        threading.Thread(target=go, daemon=True).start()
        return f"Updating to {rel.version}; I'll be back in a minute."

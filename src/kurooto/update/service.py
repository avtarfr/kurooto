"""Updates while Kurooto runs. Settings → updates.mode:
    night (default)  download and prepare when one appears; switch over between 03:00 and 05:00 when you're not
                     on a call and nothing is running
    ask              a Telegram message with Update / Later / Skip this version
    off              only a note in the dashboard
After switching, the new version is on probation for 5 minutes; if it keeps crashing, the launcher goes back.
"""

from __future__ import annotations

import datetime as dt
import os
import random
import threading
import time
from typing import TYPE_CHECKING

from kurooto import __version__
from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave
from kurooto.update.updater import PAGES, UpdateError, Updater, vtuple

if TYPE_CHECKING:
    from kurooto.app import App

register_defaults("updates", {"mode": "night", "channel": "stable", "window": ["03:00", "05:00"]})


class Updates:
    def __init__(self, app: App):
        self.app = app
        extra = os.environ.get("KUROOTO_EXTRA_UPDATE_KEY")  # for testing a release pipeline; never set by Kurooto
        from kurooto.update import signing

        keys = list(signing.PUBLIC_KEYS) + ([extra] if extra else [])
        self.u = Updater(app.paths.app, app.paths.state, os.environ.get("KUROOTO_UPDATE_BASE") or PAGES, keys)
        self.ready_file = app.paths.state / "update-ready.json"
        self._busy = threading.Lock()

    def start(self) -> None:
        s = self.app.scheduler
        s.action("updates.check", lambda p: self.check())
        s.action("updates.apply", lambda p: self.apply_if_quiet())
        s.action("updates.probation", lambda p: self.end_probation())
        s.action("updates.rolled_back", lambda p: self.tell_rolled_back())
        s.every("updates:check", "every 6h", "updates.check")
        ready = str((jload(self.ready_file, None) or {}).get("version") or "")
        if ready and (vtuple(ready) <= vtuple(__version__) or ready in self.u.bad()):
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
            return "up to date"
        self.app.events.emit("update_found", version=rel.version)
        if mode == "off":
            jsave(self.ready_file, {"version": rel.version, "staged": False, "notes": rel.notes})
            return f"{rel.version} available (updates are off)"
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
            )
            jsave(self.ready_file, {"version": rel.version, "staged": False, "notes": rel.notes})
            return f"asked about {rel.version}"
        threading.Thread(target=self._stage_then_wait, args=(rel,), daemon=True).start()
        return f"preparing {rel.version}"

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
                    f"Couldn't prepare Kurooto {rel.version}: {str(e)[:300]}. I'll try again later.", kind="update"
                )
                return False
            jsave(self.ready_file, {"version": rel.version, "staged": True, "notes": rel.notes})
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
        busy = self.app.jobs._db.execute("select 1 from jobs where status in ('queued','running') limit 1").fetchone()
        on_call = self.app.availability.call_block()[0] == "you're on a call"
        if busy or on_call:
            self.app.scheduler.at(now() + dt.timedelta(minutes=20), "updates.apply", key="updates:apply")
            return "busy; trying again in 20 min"
        return self.switch_to(ready["version"])

    def switch_to(self, version: str) -> str:
        self.u.switch(version)
        (self.ready_file).unlink(missing_ok=True)
        self.app.events.emit("update_switch", to=version, previous=__version__)
        self.app.request_restart()
        return f"switching to {version}"

    def end_probation(self) -> None:
        if self.u.probation_passed(__version__):
            self.u.prune()
            self.app.notify(f"Kurooto updated to {__version__}.", kind="update")

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
            return "Already up to date."

        def go():
            if self._stage(rel):
                self.switch_to(rel.version)

        threading.Thread(target=go, daemon=True).start()
        return f"Updating to {rel.version}; I'll be back in a minute."

"""Profile sync: your Kurooto setup (settings, passwords and keys, deadlines, quiz progress, routines and the rest of
what's worth keeping) saved ENCRYPTED in your own private GitHub repository, so a new computer or a reinstall is set
up again in a minute: "I've used Kurooto before" on the setup page, or `kurooto profile restore`.

It uses the repository Notes sync uses (on a branch of its own, kurooto-profile, so your notes folder never sees it),
or another private repository of yours with the same kind of token. You pick a passphrase: it locks the profile and
is never stored. It's saved once a day, and ten minutes after you change a setting or turn a feature on or off; a
profile is small, so this also runs on battery. /profile shows what's saved; /profile save saves now.

What's in it and how it's encrypted: core/profile.py. A local backup zip (Backups) is the other half: everything,
including history, on a drive you pick.
"""

from __future__ import annotations

import threading
import time

from kurooto.core import profile as core
from kurooto.core.config import register_defaults
from kurooto.core.state import jload
from kurooto.modules.base import Command, Incoming, Module

register_defaults(
    "profile",
    {
        "repo": "",  # owner/name of a private GitHub repository; empty: the one Notes sync uses
        "branch": core.BRANCH,
        "remote": "",  # tests: a local repository instead of GitHub
        "after_changes": 10,  # minutes after you change a setting (or turn a feature on or off), it's saved
        "when": "daily 04:40",
    },
)
WATCH = {"setting_changed", "module_enabled", "module_disabled"}


class Profile(Module):
    id = "profile"
    title = "Profile sync"
    description = (
        "Your setup saved, encrypted, in your private GitHub repository: a new computer is set up again in a minute."
    )
    privacy = (
        "Your settings, passwords and keys and saved state go to your own private GitHub repository, encrypted with a "
        "passphrase only you know. Your notes and AI history aren't in it."
    )

    def __init__(self, app):
        super().__init__(app)
        self._unsub = None
        self._busy = threading.Lock()

    # ------------------------------------------------------------------------------------------ setup
    def ready(self):
        try:
            core.target(self.app)
        except core.ProfileError as e:
            return False, str(e)
        if not core.git_exe(self.app):
            return False, "needs Git (Notes sync's Set up installs it)"
        if not core.cached_key(self.app):
            return False, "pick the passphrase that locks your profile (Set up)"
        return True, ""

    def setup_form(self) -> dict:
        return {
            "intro": "Your profile goes, encrypted, to the private repository Notes sync uses (leave the first two "
            "empty), or to another private repository of yours: make one and a fine-grained token for it with "
            "Contents: Read and write, as for Notes sync. Then pick a passphrase of a few words: you need it on a new "
            "computer, and if you forget it the profile can't be opened (your notes are still fine). It's never "
            "stored.",
            "links": [
                ["New repository", "https://github.com/new"],
                ["New fine-grained token", "https://github.com/settings/personal-access-tokens/new"],
            ],
            "fields": [
                {"name": "repo", "label": "Repository (owner/name; empty: Notes sync's)", "type": "text"},
                {"name": "token", "label": "Token (empty: Notes sync's)", "type": "password"},
                {"name": "passphrase", "label": "Passphrase", "type": "password"},
                {"name": "again", "label": "The passphrase again", "type": "password"},
            ],
        }

    def configure(self, values: dict) -> dict:
        repo, token = str(values.get("repo") or "").strip(), str(values.get("token") or "").strip()
        passphrase, again = str(values.get("passphrase") or ""), str(values.get("again") or "")
        try:
            core.check_passphrase(passphrase, again)
            if repo and repo != (self.app.settings.get("notes_sync.repo") or ""):
                if not token:
                    return {"ok": False, "message": "That repository needs a token of its own."}
                ok, why = self.app.modules["notes_sync"].check_repo(repo, token)
                if not ok:
                    return {"ok": False, "message": why}
                self.app.settings.set("profile.repo", repo)
                self.app.secrets.set(core.TOKEN, token)
            elif not self.setting("remote"):
                self.app.settings.set("profile.repo", "")
                if not (self.app.settings.get("notes_sync.repo") or self.app.settings.get("notes_sync.remote")):
                    return {
                        "ok": False,
                        "message": "Notes sync isn't set up: set it up first, or give your profile a repository.",
                    }
            ok, msg = core.connect(self.app, passphrase, again, progress=lambda line: None)
        except core.ProfileError as e:
            return {"ok": False, "message": str(e)}
        if ok and self.app.is_on(self.id):
            self.start()
        return {"ok": ok, "message": msg}

    # -------------------------------------------------------------------------------------------- running
    def start(self):
        self.every("daily", self.setting("when") or "daily 04:40", lambda p: self._in_background("daily"))
        self.action("soon", lambda p: self._in_background("changed"))
        if self._unsub is None:
            from kurooto.core.events import subscribe

            self._unsub = subscribe(self._on_event)

    def stop(self):
        unsub, self._unsub = self._unsub, None
        if unsub:
            unsub()
        super().stop()

    def _on_event(self, rec: dict) -> None:
        """A setting changed or a feature went on or off: save in a few minutes (each change moves it later, so a
        burst of changes is one save)."""
        if rec.get("kind") not in WATCH or not self.app.is_on(self.id):
            return
        minutes = float(self.setting("after_changes") or 10)
        self.app.scheduler.at(time.time() + minutes * 60, "profile.soon", key="profile:soon", module=self.id)

    def _in_background(self, reason: str) -> str:
        """Saving talks to GitHub (seconds, sometimes more): off the scheduler's thread, so nothing else waits."""
        threading.Thread(target=self.save, args=(reason,), name="profile-save", daemon=True).start()
        return "started"

    def save(self, reason: str = "now", force: bool = False) -> tuple[bool, str]:
        if not self._busy.acquire(blocking=False):
            return False, "a save is already running"
        try:
            ok, msg = core.save(self.app, force=force)
        except core.ProfileError as e:
            return self._fail(str(e))
        except Exception as e:
            return self._fail(f"{type(e).__name__}: {e}"[:300])
        finally:
            self._busy.release()
        if not ok:  # held: another computer saved since; say so now and then, not every time
            st = core.local(self.app)
            if time.time() - st.get("told_held", 0) > 7 * 86400:
                self.app.notify(f"Profile sync: {msg}.", kind="info")
                core.record(self.app, told_held=time.time())
        self.app.events.emit("profile_save", reason=reason, ok=ok)
        return ok, msg

    def _fail(self, why: str) -> tuple[bool, str]:
        st = core.local(self.app)
        changes = {"ok": False, "failed_at": time.time(), "error": why}
        if time.time() - st.get("told", 0) > 20 * 3600:  # at most once a day
            self.app.notify(f"Profile sync didn't work: {why}", kind="info")
            changes["told"] = time.time()
        core.record(self.app, **changes)
        self.app.events.emit("profile_failed", error=why[:200])
        return False, why

    def health(self):
        ok, why = self.ready()
        if not ok:
            return ok, why
        st = jload(core.state_file(self.app), {}) or {}
        if st.get("held"):
            return False, "another computer saved your profile since this one did: restore it here or save over it"
        if st.get("ok") is False:
            return False, f"the last save failed: {st.get('error', '')}"
        if not st.get("at"):
            return None, "not saved yet"
        age = time.time() - st["at"]
        detail = f"saved {_ago(age)} ago"
        return (True, detail) if age < 3 * 86400 else (False, detail + "; it can't reach your repository?")

    # ------------------------------------------------------------------------------------------- telegram
    def commands(self):
        return [Command("profile", "what your saved profile holds; /profile save saves it now", self._cmd)]

    def _cmd(self, msg: Incoming, arg: str) -> str:
        if arg.strip().lower() in ("save", "save now", "now"):
            ok, text = self.save("command", force=True)
            return text if ok else f"Couldn't save: {text}"
        return describe(core.status(self.app))


def describe(st: dict) -> str:
    """The status in a few lines (Telegram and `kurooto profile status`)."""
    lines = [f"Profile sync: {'on' if st['on'] else 'off'}. Where: {st['where']} (branch {st['branch']})."]
    if st.get("saved"):
        c = st.get("counts") or {}
        lines.append(f"Last saved: {core._when(st['saved'])}.")
        if c:
            lines.append(
                f"Holds {c.get('settings', 0)} settings, {c.get('features', 0)} features, {c.get('secrets', 0)} "
                f"passwords and keys, {c.get('files', 0)} saved items, {c.get('scheduled', 0)} things scheduled."
            )
    else:
        lines.append("Nothing saved from this computer yet.")
    if st.get("held"):
        lines.append(
            f"Another computer saved it ({core._when(st['held'])}) since this one did, so this one waits: restore "
            "it here (kurooto profile restore), or /profile save to save over it."
        )
    if st.get("ok") is False and st.get("error"):
        lines.append(f"The last save failed: {st['error']}")
    if not st.get("has_key"):
        lines.append("This computer doesn't have the profile's key yet: Set up asks for your passphrase.")
    return "\n".join(lines)


def _ago(seconds: float) -> str:
    if seconds < 3600:
        return f"{max(1, int(seconds // 60))} min"
    if seconds < 2 * 86400:
        return f"{int(seconds // 3600)} h"
    return f"{int(seconds // 86400)} days"


# ---------------------------------------------------------------------------------- the setup page and dashboard
def web(api, path: str, b: dict, post: bool) -> tuple[int, dict]:
    """GET profile: the status (and the last restore's report). POST profile/restore {repo, token, passphrase}:
    restore in the background (the page follows /api/progress, then GET profile). POST profile/save {replace}."""
    app = api.app
    if not post and path == "profile":
        return 200, core.status(app)
    if post and path == "profile/save":
        m = app.modules["profile"]
        if not app.is_on("profile"):
            return 200, {"ok": False, "message": "Profile sync is off."}
        ok, msg = m.save("dashboard", force=bool(b.get("replace")))
        return 200, {"ok": ok, "message": msg}
    if post and path == "profile/restore":
        repo, token = str(b.get("repo") or "").strip(), str(b.get("token") or "").strip()
        passphrase = str(b.get("passphrase") or "")
        if not passphrase:
            return 200, {"started": False, "message": "Type your profile's passphrase."}

        def work(note):
            try:
                remote = str(app.settings.get("profile.remote") or "")  # tests: a local repository
                report = core.restore(app, passphrase, repo=repo, token=token, remote=remote, progress=note)
            except core.ProfileError as e:
                core.record(app, report={"error": str(e)})
                return False, str(e)
            left = len(report["left"])
            return True, "Restored." + (f" {left} feature(s) still need setting up here." if left else "")

        core.record(app, report=None)
        return 200, api._background(work)
    return 404, {"error": "not found"}

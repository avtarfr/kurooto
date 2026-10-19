"""Notes sync: your notes folder is kept in a private GitHub repository of yours. Every 10 minutes Kurooto saves
what changed, takes in what changed elsewhere (another computer, or GitHub's own editor), and sends it up. Every
version stays in the repository's history, so nothing written is ever lost. With Phone calls on, your call line
can read whole notes from there while this computer is off.

Setup: make an empty PRIVATE repository on GitHub, then a fine-grained token for just that repository with
"Contents: Read and write" (github.com → Settings → Developer settings → Fine-grained tokens). Paste both. Kurooto
refuses a public repository. Git is installed for you if it's missing (MinGit on Windows; Apple's tools on a Mac).

If the same note was changed in two places at once, your computer's version wins for the clashing lines; the other
version is still in the history.
"""

from __future__ import annotations

import base64
import json
import os
import re
import time
import urllib.error
import urllib.request

from kurooto.core import proc
from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.lock import Lock
from kurooto.core.prereqs import Prereqs
from kurooto.core.state import jload, jsave
from kurooto.modules.base import Command, Incoming, Module

register_defaults(
    "notes_sync",
    {
        "repo": "",  # owner/name
        "branch": "main",
        "every": "every 10m",
        "share_with_calls": True,  # your call line may read notes from the repository while this computer is off
        "api": "https://api.github.com",
        "remote": "",  # tests: a local repository instead of GitHub
    },
)
TOKEN = "notes_sync.token"  # noqa: S105 (the secret's name)
IGNORE = """# made by Kurooto's Notes sync
.DS_Store
Thumbs.db
desktop.ini
.trash/
.obsidian/workspace*.json
*.part
inbox/.part-*
"""


class NotesSync(Module):
    id = "notes_sync"
    heavy = True  # waits for the charger on battery (saver mode, core/power.py)
    title = "Notes sync"
    description = "Keeps your notes in your own private GitHub repository: history of every change, other devices."
    privacy = (
        "Your notes go to your own private GitHub repository (and, if Phone calls is on, your call line can read them)."
    )

    def __init__(self, app):
        super().__init__(app)
        self.prereqs = Prereqs(app.paths.app, app.paths.cache)
        self.state_file = app.paths.state / "notes-sync.json"

    # ------------------------------------------------------------------------------------- git
    def git_exe(self) -> str | None:
        return self.prereqs.items["git"].find()

    def remote_url(self) -> str:
        return self.setting("remote") or f"https://github.com/{self.setting('repo')}.git"

    def _env(self) -> dict:
        env = {
            **os.environ,
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_AUTHOR_NAME": self.app.name,
            "GIT_COMMITTER_NAME": self.app.name,
            "GIT_AUTHOR_EMAIL": "kurooto@localhost",
            "GIT_COMMITTER_EMAIL": "kurooto@localhost",
            "LC_ALL": "C",
        }
        tok = self.app.secrets.get(TOKEN)
        if tok and not self.setting("remote"):
            # The token goes to git as an HTTP header through environment-only config: never in a URL, a file or argv.
            basic = base64.b64encode(f"x-access-token:{tok}".encode()).decode()
            env.update(
                GIT_CONFIG_COUNT="1",
                GIT_CONFIG_KEY_0="http.https://github.com/.extraheader",
                GIT_CONFIG_VALUE_0=f"AUTHORIZATION: basic {basic}",
            )
        return env

    def git(self, *args: str, timeout: float = 120) -> proc.Result:
        exe = self.git_exe()
        if not exe:
            raise RuntimeError("Git isn't installed")
        return proc.run([exe, "-C", str(self.app.workspace), *args], timeout=timeout, env=self._env())

    # ----------------------------------------------------------------------------------- setup
    def ready(self):
        if not self.git_exe():
            return False, "needs Git (Set up installs it)"
        if not self.setting("repo") and not self.setting("remote"):
            return False, "connect your private GitHub repository (Set up)"
        if not self.setting("remote") and not self.app.secrets.get(TOKEN):
            return False, "paste a token for your repository (Set up)"
        return True, ""

    def setup(self, progress=print) -> tuple[bool, str]:
        if not self.git_exe():
            ok, msg = self.prereqs.install("git", progress)
            if not ok:
                return False, msg
        if not self.setting("repo") and not self.setting("remote"):
            return False, "Git is ready. Now connect your private repository: paste its name (owner/name) and a token."
        return self.first_sync(progress)

    def check_repo(self, repo: str, token: str) -> tuple[bool, str]:
        """Is it a private repository this token can write to?"""
        if not re.fullmatch(r"[A-Za-z0-9-]{1,39}/[A-Za-z0-9._-]{1,100}", repo or ""):
            return False, "Write the repository as owner/name, e.g. sam/notes."
        req = urllib.request.Request(  # noqa: S310 (GitHub's API, https)
            f"{self.setting('api')}/repos/{repo}",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": "kurooto",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as r:  # noqa: S310
                info = json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                return False, "GitHub didn't accept that token."
            if e.code == 404:
                return (
                    False,
                    "GitHub says there's no such repository, or the token can't see it (pick it under "
                    "Repository access).",
                )
            return False, f"GitHub answered {e.code}."
        except OSError as e:
            return False, f"Couldn't reach GitHub: {e}"[:200]
        if not info.get("private"):
            return (
                False,
                "That repository is public: anyone could read your notes. Make it private (or use another one).",
            )
        if not (info.get("permissions") or {}).get("push"):
            return False, "That token can only read the repository; it needs Contents: Read and write."
        return True, info.get("default_branch") or "main"

    def connect(self, repo: str, token: str, progress=print) -> tuple[bool, str]:
        ok, branch_or_msg = self.check_repo(repo.strip(), token.strip())
        if not ok:
            return False, branch_or_msg
        self.app.secrets.set(TOKEN, token.strip())
        self.app.settings.set("notes_sync.repo", repo.strip())
        self.app.settings.set("notes_sync.branch", branch_or_msg)
        if self.setting("share_with_calls"):
            self.app.settings.set("calls.notes_repo", repo.strip())
            self.app.secrets.set("calls.github_token", token.strip())
            calls = self.app.modules.get("calls")
            if calls and self.app.is_on("calls"):
                calls._line_update()  # the line learns where your notes are (in the background)
        if not self.git_exe():
            return True, "Saved. Set up Notes sync to install Git and make the first sync."
        return self.first_sync(progress)

    def first_sync(self, progress=print) -> tuple[bool, str]:
        ws = self.app.workspace
        if not (ws / ".git").exists():
            progress("Making your notes folder a Git repository…")
            r = self.git("init", "-b", self.setting("branch") or "main")
            if not r.ok:
                return False, f"git init failed: {r.err[-200:]}"
        if not (ws / ".gitignore").exists():
            (ws / ".gitignore").write_text(IGNORE, encoding="utf-8")
        have = self.git("remote").out.split()
        self.git("remote", "set-url" if "origin" in have else "add", "origin", self.remote_url())
        progress("First sync with your repository…")
        ok, msg = self.sync()
        return ok, ("Your notes are synced with your private repository." if ok else msg)

    # ------------------------------------------------------------------------------------ syncing
    def start(self):
        self.every("sync", self.setting("every") or "every 10m", lambda p: self.sync())

    def sync(self) -> tuple[bool, str]:
        """Save what changed, take in what changed elsewhere, send it up. Safe to run any time."""
        branch = self.setting("branch") or "main"
        with Lock(self.app.paths.state, "notes-sync", timeout=60):
            try:
                self.git("add", "-A")
                committed = False
                if self.git("diff", "--cached", "--quiet").code == 1:
                    r = self.git("commit", "-q", "-m", f"notes: {now():%Y-%m-%d %H:%M}")
                    committed = r.ok
                f = self.git("fetch", "-q", "origin", timeout=300)
                if not f.ok:
                    return self._fail(f"couldn't reach your repository: {(f.err or f.out).strip()[-200:]}")
                remote_has = self.git("rev-parse", "--verify", "-q", f"origin/{branch}").ok
                if remote_has:
                    local_has = self.git("rev-parse", "--verify", "-q", "HEAD").ok
                    if not local_has:
                        self.git("reset", "-q", f"origin/{branch}")
                        self.git("checkout", "-q", "--", ".")
                    elif self.git("merge-base", "--is-ancestor", f"origin/{branch}", "HEAD").code != 0:
                        if not self.git("rebase", "-q", f"origin/{branch}").ok:
                            self.git("rebase", "--abort")
                            m = self.git(
                                "merge",
                                "-q",
                                "--no-edit",
                                "--allow-unrelated-histories",
                                "-X",
                                "ours",
                                f"origin/{branch}",
                            )
                            if not m.ok:
                                self.git("merge", "--abort")
                                return self._fail(
                                    "a change elsewhere clashes with yours and couldn't be merged; "
                                    "nothing was lost (both are kept), but sync is paused until it's sorted"
                                )
                if self.git("rev-parse", "--verify", "-q", "HEAD").ok:
                    p = self.git("push", "-q", "origin", f"HEAD:refs/heads/{branch}", timeout=300)
                    if not p.ok:
                        return self._fail(f"couldn't send to your repository: {(p.err or p.out).strip()[-200:]}")
            except RuntimeError as e:
                return self._fail(str(e))
        jsave(self.state_file, {"ok": True, "at": time.time(), "error": ""})
        self.app.events.emit("notes_synced", committed=committed)
        return True, "Synced."

    def _fail(self, why: str) -> tuple[bool, str]:
        prev = jload(self.state_file, {}) or {}
        jsave(self.state_file, {"ok": False, "at": time.time(), "error": why, "told": prev.get("told", 0)})
        if time.time() - prev.get("told", 0) > 6 * 3600:  # at most every 6 hours
            self.app.notify(f"Notes sync: {why}.", kind="info")
            jsave(self.state_file, {"ok": False, "at": time.time(), "error": why, "told": time.time()})
        self.app.events.emit("notes_sync_failed", error=why[:200])
        return False, why

    def health(self):
        ok, why = self.ready()
        if not ok:
            return ok, why
        st = jload(self.state_file, {}) or {}
        return (True, "") if st.get("ok", True) else (False, st.get("error", ""))

    def commands(self):
        return [Command("sync", "sync your notes with your repository now", self._cmd)]

    def _cmd(self, msg: Incoming, arg: str) -> str:
        ok, why = self.sync()
        return "Notes synced." if ok else f"Couldn't sync: {why}"

    # ------------------------------------------------------------------------------------- setup
    def setup_form(self) -> dict:
        return {
            "intro": "1. Make a new repository on GitHub: any name, set to Private, nothing else ticked. 2. Make a "
            "fine-grained token: Repository access → Only select repositories → that one; Permissions → Contents → "
            "Read and write. 3. Paste both here.",
            "links": [
                ["New repository", "https://github.com/new"],
                ["New fine-grained token", "https://github.com/settings/personal-access-tokens/new"],
            ],
            "fields": [
                {"name": "repo", "label": "Repository (owner/name)", "type": "text", "placeholder": "you/notes"},
                {"name": "token", "label": "Token", "type": "password", "placeholder": "github_pat_…"},
            ],
        }

    def configure(self, values: dict) -> dict:
        ok, msg = self.connect(str(values.get("repo", "")), str(values.get("token", "")))
        return {"ok": ok, "message": msg}

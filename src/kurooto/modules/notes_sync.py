"""Notes sync: your notes folder is kept in a private GitHub repository of yours. Every 10 minutes Kurooto saves
what changed, takes in what changed elsewhere (another computer, or GitHub's own editor), and sends it up. Every
version stays in the repository's history, so nothing written is ever lost. What an AI request writes is sent up a
couple of minutes after it finishes, and whatever is left when Kurooto stops (a shutdown, an update) goes up then. With
Phone calls on, your call line can read whole notes from there while this computer is off.

Setup: make an empty PRIVATE repository on GitHub, then a fine-grained token for just that repository with
"Contents: Read and write" (github.com → Settings → Developer settings → Fine-grained tokens). Paste both. Kurooto
refuses a public repository. Git is installed for you if it's missing (MinGit on Windows; Apple's tools on a Mac).

If the same note was changed in two places at once (say, on your phone and here), nothing is lost. By default
(notes_sync.on_conflict = "keep both") the version from elsewhere stays in the note and this computer's goes next to it
as "<note> (conflict, this computer, <date>).md"; you get a message naming both, and merge them when you like. With
"stop", sync stops instead, changes nothing, and tells you (once) until you've sorted it out yourself; it never
forces anything. A notes folder that's already a Git repository keeps its own remote ("origin") when that's the same
repository, e.g. over SSH; another repository's origin is left alone and Kurooto uses a remote of its own.
"""

from __future__ import annotations

import base64
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

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
        "after_jobs": 2,  # minutes after an AI request finishes, its notes are sent up (0: wait for the timer)
        "on_conflict": "keep both",  # "keep both": a clashing note keeps both versions; "stop": sync waits for you
    },
)
OWN_REMOTE = "kurooto"  # the remote used when the folder's origin is another repository
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
        self._unsub = None  # the listener for finished AI requests, while it's on

    # ------------------------------------------------------------------------------------- git
    def git_exe(self) -> str | None:
        return self.prereqs.items["git"].find()

    def remote_url(self) -> str:
        return self.setting("remote") or f"https://github.com/{self.setting('repo')}.git"

    def same_repo(self, url: str) -> bool:
        """Is this remote URL your notes repository (https or SSH, with or without .git)?"""
        url = (url or "").strip()
        if self.setting("remote"):
            return url == self.setting("remote")
        m = re.search(r"github\.com[:/]+([^/\s]+/[^/\s]+?)(?:\.git)?/?$", url)
        return bool(m) and m.group(1).lower() == (self.setting("repo") or "").lower()

    def remote(self) -> str:
        """The remote sync uses: origin, unless that's another repository (then a remote of Kurooto's own)."""
        return OWN_REMOTE if OWN_REMOTE in self.git("remote").out.split() else "origin"

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
        if "origin" not in have:
            self.git("remote", "add", "origin", self.remote_url())
        elif not self.same_repo(self.git("remote", "get-url", "origin").out):  # theirs: leave it be
            self.git("remote", "set-url" if OWN_REMOTE in have else "add", OWN_REMOTE, self.remote_url())
        elif OWN_REMOTE in have:  # origin is ours again
            self.git("remote", "remove", OWN_REMOTE)
        progress("First sync with your repository…")
        ok, msg = self.sync()
        return ok, ("Your notes are synced with your private repository." if ok else msg)

    # ------------------------------------------------------------------------------------ syncing
    def start(self):
        self.every("sync", self.setting("every") or "every 10m", lambda p: self.sync())
        self.action("soon", lambda p: self.sync())
        if self._unsub is None:
            from kurooto.core.events import subscribe

            self._unsub = subscribe(self._on_event)

    def stop(self):
        unsub, self._unsub = self._unsub, None
        if unsub:
            unsub()
        super().stop()

    def _on_event(self, rec: dict) -> None:
        """An AI request finished: send its notes up in a couple of minutes (one push for a burst of requests)."""
        minutes = self.setting("after_jobs")
        if rec.get("kind") != "job_done" or not minutes or not self.app.is_on(self.id):
            return
        self.app.scheduler.at(
            time.time() + float(minutes) * 60, "notes_sync.soon", key="notes_sync:soon", module=self.id, replace=False
        )

    def shutdown(self) -> None:
        """Kurooto is stopping: send up what's left (quickly; a shutdown doesn't wait long)."""
        unsub, self._unsub = self._unsub, None
        if unsub:
            unsub()
        if self.app.power.current == "paused" or not self.ready()[0]:
            return
        try:
            self.sync(quick=True)
        except Exception as e:
            self.app.events.emit("notes_sync_failed", error=f"at shutdown: {e}"[:200])

    def sync(self, quick: bool = False) -> tuple[bool, str]:
        """Save what changed, take in what changed elsewhere, send it up. Safe to run any time. quick: short
        timeouts (at shutdown)."""
        branch = self.setting("branch") or "main"
        net = 45 if quick else 300
        kept: list[tuple[str, str]] = []
        with Lock(self.app.paths.state, "notes-sync", timeout=20 if quick else 60):
            try:
                busy = self._unfinished()
                if busy:
                    return self._fail(busy)
                origin = self.remote()
                self.git("add", "-A")
                committed = False
                if self.git("diff", "--cached", "--quiet").code == 1:
                    r = self.git("commit", "-q", "-m", f"notes: {now():%Y-%m-%d %H:%M}")
                    committed = r.ok
                f = self.git("fetch", "-q", origin, timeout=net)
                if not f.ok:
                    return self._fail(f"couldn't reach your repository: {(f.err or f.out).strip()[-200:]}")
                theirs = f"{origin}/{branch}"
                remote_has = self.git("rev-parse", "--verify", "-q", theirs).ok
                if remote_has:
                    local_has = self.git("rev-parse", "--verify", "-q", "HEAD").ok
                    if not local_has:
                        self.git("reset", "-q", theirs)
                        self.git("checkout", "-q", "--", ".")
                    elif self.git("merge-base", "--is-ancestor", theirs, "HEAD").code != 0:
                        if not self.git("rebase", "-q", theirs).ok:
                            self.git("rebase", "--abort")
                            if self.setting("on_conflict") == "stop":
                                return self._fail(
                                    "a note was changed here and elsewhere at once; nothing was changed. Merge it "
                                    f"yourself (in the notes folder: git pull --rebase {origin} {branch}), or set "
                                    'notes_sync.on_conflict to "keep both"; sync waits until then'
                                )
                            ok, kept = self._merge_keeping_both(theirs)
                            if not ok:
                                return self._fail(
                                    "a change elsewhere clashes with yours and couldn't be merged; nothing was "
                                    "changed, and sync is paused until it's sorted"
                                )
                if self.git("rev-parse", "--verify", "-q", "HEAD").ok:
                    p = self.git("push", "-q", origin, f"HEAD:refs/heads/{branch}", timeout=net)
                    if not p.ok:
                        return self._fail(f"couldn't send to your repository: {(p.err or p.out).strip()[-200:]}")
            except RuntimeError as e:
                return self._fail(str(e))
        jsave(self.state_file, {"ok": True, "at": time.time(), "error": ""})
        self.app.events.emit("notes_synced", committed=committed, conflicts=len(kept))
        if kept:
            rows = "\n".join(f"- {note}: this computer's version is in {copy}" for note, copy in kept)
            self.app.notify(
                f"Notes sync: {len(kept)} note(s) changed here and elsewhere at once. Both versions are kept; the "
                f"note has the one from elsewhere:\n{rows}\nMerge them when you like, then delete the copy.",
                kind="info",
            )
        return True, "Synced." if not kept else f"Synced; {len(kept)} clash(es) kept as copies."

    def _unfinished(self) -> str:
        """A merge or rebase someone left half done (perhaps you, sorting out a clash): sync keeps out of it."""
        gd = self.git("rev-parse", "--git-dir")
        if not gd.ok:
            return ""
        d = Path(gd.out.strip())
        d = d if d.is_absolute() else self.app.workspace / d
        if any((d / x).exists() for x in ("rebase-merge", "rebase-apply", "MERGE_HEAD")):
            return (
                "a merge or rebase is unfinished in your notes folder; finish it (git status says how) and sync "
                "goes on by itself"
            )
        if self.git("rev-parse", "--verify", "-q", "HEAD").ok and not self.git("symbolic-ref", "-q", "HEAD").ok:
            return "your notes folder isn't on a branch (a detached HEAD); check out your branch again"
        return ""

    def _merge_keeping_both(self, theirs: str) -> tuple[bool, list[tuple[str, str]]]:
        """Merge, and for each clashing note keep both whole versions: elsewhere's in the note, this computer's in a
        copy beside it. Notes changed on one side only merge as usual. False (and nothing changed): it couldn't."""
        m = self.git("merge", "-q", "--no-edit", "--allow-unrelated-histories", theirs)
        if m.ok:
            return True, []
        ws = self.app.workspace
        kept: list[tuple[str, str]] = []
        stamp = f"{now():%Y-%m-%d %H%M}"
        clashing = [x for x in self.git("diff", "--name-only", "--diff-filter=U", "-z").out.split("\0") if x]
        if not clashing:
            self.git("merge", "--abort")
            return False, []
        for path in clashing:
            stages = {
                line.split()[2]
                for line in self.git("ls-files", "-u", "-z", "--", path).out.split("\0")
                if line.strip() and len(line.split()) >= 3
            }
            target = ws / path
            # deleted on one side and changed on the other, the changed one stays: a deletion can't lose anything
            side = "--theirs" if "3" in stages else "--ours"
            if {"2", "3"} <= stages:  # changed on both: this computer's version into a copy first
                if self.git("checkout", "--ours", "--", path).ok and target.is_file():
                    copy = self._copy_name(target, stamp)
                    copy.write_bytes(target.read_bytes())
                    kept.append((path, str(copy.relative_to(ws)).replace("\\", "/")))
                    self.git("add", "--", str(copy.relative_to(ws)))
            if not self.git("checkout", side, "--", path).ok:
                self.git("merge", "--abort")
                return False, []
            self.git("add", "--", path)
        if self.git("diff", "--name-only", "--diff-filter=U").out.strip():
            self.git("merge", "--abort")
            return False, []
        c = self.git(
            "commit", "-q", "--no-edit", "-m", f"notes: merged changes from elsewhere; {len(kept)} clash(es) kept"
        )
        if not c.ok:
            self.git("merge", "--abort")
            return False, []
        return True, kept

    @staticmethod
    def _copy_name(target: Path, stamp: str) -> Path:
        base = f"{target.stem} (conflict, this computer, {stamp})"
        copy = target.with_name(base + target.suffix)
        n = 2
        while copy.exists():
            copy = target.with_name(f"{base} {n}{target.suffix}")
            n += 1
        return copy

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
        return [Command("sync", "sync your notes now (/sync all: everything that syncs)", self._cmd)]

    def _cmd(self, msg: Incoming, arg: str) -> str:
        if arg.strip().lower() in ("all", "everything"):
            from kurooto.core import syncall

            return syncall.start(self.app)[1]
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

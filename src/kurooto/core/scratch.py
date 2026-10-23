"""Kurooto's scratch folders: where the AI may think, draft and write freely, and never in your real files.

An AI request that may change your files (Help with your project, a change to your notes you asked for, a fix Dreaming
proposes, Change under a proposal) gets a folder of its own, `<state>/scratch/<id>/work`:
- a git repository: a git worktree of it on a new branch (`kurooto/<id>`), from your current commit, so the AI sees
  the whole project as it's committed (your uncommitted changes aren't in it);
- anything else (your notes, a project folder that isn't git, a skill): a mirror that starts empty. A file is copied in
  the first time the AI changes it (Kurooto's own tools do that; an agent program copies it itself), and the original
  as it was then is kept beside it (`base/`), to see what changed and whether you changed the original since.

For that request the AI may write in that folder and nowhere else (core/places.py: write_roots(scratch=...)): Kurooto's
own tools write only there (tools() below), Claude Code gets per-run permissions that allow editing only there
(providers/claude.py), agy runs in it with Kurooto's tools confined the same way (agy's own allow-list is one file for
every run, so its built-in file tools keep the folders it was given; audit() below reports anything outside that
changed while it worked). Reading is as always, plus the original. Keys and passwords (.env, *.pem, id_rsa ...) are
never copied in, read through these tools, or part of a proposal (secret()).

Checks (the project's tests, a LaTeX build) run only when you turned them on for that project (projects.checks), in
the scratch folder, with a time limit and no network, inside a sandbox that can write only there: bubblewrap (`bwrap`)
on Linux, sandbox-exec on macOS. Without one of those, checks don't run, and the proposal says so.

When the request ends, core/proposals.py compares the folder with the original (changes()) and makes a proposal; Apply
writes it, Discard deletes the folder. A folder is removed after Apply or Discard, or after proposals.keep_days.
"""

from __future__ import annotations

import difflib
import fnmatch
import hashlib
import os
import re
import shutil
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto.core import proc
from kurooto.core.state import jload, jsave

if TYPE_CHECKING:
    from kurooto.app import App
    from kurooto.modules.calls.tools import Tool

# never read, copied or proposed: keys, passwords, tokens (a name, any folder)
SECRETS = (
    ".env", ".env.*", "*.env", "*.pem", "*.key", "*.p12", "*.pfx", "*.keystore", "*.jks", "id_rsa*", "id_dsa*",
    "id_ecdsa*", "id_ed25519*", ".netrc", ".npmrc", ".pypirc", "credentials*.json", "credentials", "secrets*.json",
    "secrets*.yaml", "secrets*.yml", "client_secret*.json", "service-account*.json", "token*.json", "*.gpg",
)  # fmt: skip
NEVER = {".git", ".kurooto"}  # folders that are never part of a scratch folder's changes
MAX_TEXT = 2_000_000  # bytes: a bigger file is shown as "binary or too big", never as a diff
WALK_MAX = 20000  # files looked at by audit() in one folder
CHECK_OUT = 4000  # characters of a check's output kept


def secret(rel: str) -> bool:
    """Is this a file of keys or passwords (by its name, in any folder)?"""
    name = Path(str(rel).replace("\\", "/")).name.lower()
    return any(fnmatch.fnmatch(name, p) for p in SECRETS)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha(p: Path) -> str | None:
    try:
        return sha(p.read_bytes()) if p.is_file() else None
    except OSError:
        return None


@dataclass
class Scratch:
    id: str
    kind: str  # "git" (a worktree) or "files" (a mirror that fills as files change)
    origin: str  # the real folder: a repository's top, the notes folder, a project folder, the skills folder
    label: str = ""  # what it's a copy of, in words ("thesis", "your notes", "/journal")
    project: str = ""  # the project's name (Help with your project), "" otherwise
    branch: str = ""  # git: the worktree's branch
    base_commit: str = ""  # git: the commit it started from
    created: float = 0.0
    lazy: bool = False  # made by edit_note in an ordinary request (only that tool writes here)
    checks: str = ""  # the project's check command when its checks are on, else ""
    seeded: dict = field(default_factory=dict)  # files: path -> the original's sha256 when first copied (None: new)
    blocked: list = field(default_factory=list)  # writes outside the scratch folder that were refused
    outside: list = field(default_factory=list)  # files of the original that changed while the AI worked
    jobs: list = field(default_factory=list)  # the AI requests that worked here
    dir: str = ""

    @property
    def root(self) -> Path:
        return Path(self.dir)

    @property
    def work(self) -> Path:
        return self.root / "work"

    @property
    def base(self) -> Path:
        return self.root / "base"

    @property
    def src(self) -> Path:
        return Path(self.origin)

    def save(self) -> None:
        jsave(self.root / "scratch.json", asdict(self))


# ------------------------------------------------------------------------------------------- where they are
def home(app: App) -> Path:
    return app.paths.state / "scratch"


def get(app: App, sid: str | None) -> Scratch | None:
    if not sid or not re.fullmatch(r"s[0-9a-f]{8}", str(sid)):
        return None
    d = home(app) / sid
    data = jload(d / "scratch.json", None)
    if not isinstance(data, dict):
        return None
    known = {f for f in Scratch.__dataclass_fields__}
    sc = Scratch(**{k: v for k, v in data.items() if k in known})
    sc.dir = str(d)
    return sc


def every(app: App) -> list[Scratch]:
    d = home(app)
    out = [get(app, p.name) for p in sorted(d.iterdir())] if d.is_dir() else []
    return [s for s in out if s is not None]


def for_job(app: App, jid: str | None) -> Scratch | None:
    """The scratch folder an AI request works in, or None."""
    if not jid:
        return None
    jobs = getattr(app, "jobs", None)
    sid = jobs.scratch_of(jid) if jobs is not None and hasattr(jobs, "scratch_of") else None
    return get(app, sid)


def busy(app: App, origin: Path) -> str | None:
    """The AI request already working on this folder (one at a time per repository or folder), or None."""
    jobs = getattr(app, "jobs", None)
    if jobs is None:
        return None
    want = os.path.normcase(os.path.abspath(origin))
    for j in jobs.active():
        sc = for_job(app, j.id)
        if sc is not None and not sc.lazy and os.path.normcase(os.path.abspath(sc.origin)) == want:
            return j.id
    return None


# ----------------------------------------------------------------------------------------------- git helpers
def git_exe(app: App) -> str | None:
    ns = app.modules.get("notes_sync") if hasattr(app, "modules") else None
    return (ns.git_exe() if ns is not None and hasattr(ns, "git_exe") else None) or proc.which("git")


def git(app: App, repo: Path, *args: str, env: dict | None = None, timeout: float = 120, nohooks: Path | None = None):
    """Run git in `repo` with no hooks, no fsmonitor and no signing prompts: what Kurooto runs here never starts a
    program of the repository's."""
    exe = git_exe(app)
    if not exe:
        return proc.Result(127, "", "git isn't installed")
    hooks = nohooks or (home(app) / ".nohooks")
    hooks.mkdir(parents=True, exist_ok=True)
    base = [exe, "-c", f"core.hooksPath={hooks}", "-c", "core.fsmonitor=false", "-c", "commit.gpgSign=false"]
    full = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0", **(env or {})}
    return proc.run([*base, "-C", str(repo), *args], env=full, timeout=timeout)


def repo_top(app: App, folder: Path) -> Path | None:
    """The repository's top folder, when `folder` is one (its top, not a folder inside one)."""
    if not (Path(folder) / ".git").exists():
        return None
    r = git(app, Path(folder), "rev-parse", "--show-toplevel")
    if not r.ok or not r.out.strip():
        return None
    top = Path(r.out.strip())
    return top if os.path.normcase(str(top.resolve())) == os.path.normcase(str(Path(folder).resolve())) else None


# ------------------------------------------------------------------------------------------------ making one
def create(
    app: App,
    origin: Path,
    label: str = "",
    project: str = "",
    checks: str = "",
    lazy: bool = False,
    git_ok: bool = True,
) -> Scratch:
    """A fresh scratch folder for `origin`: a worktree when it's a git repository (and git_ok), else a mirror."""
    origin = Path(os.path.abspath(origin))
    sid = "s" + uuid.uuid4().hex[:8]
    d = home(app) / sid
    d.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        os.chmod(d, 0o700)
    sc = Scratch(sid, "files", str(origin), label or origin.name, project, created=time.time(), lazy=lazy,
                 checks=checks, dir=str(d))  # fmt: skip
    top = repo_top(app, origin) if git_ok else None
    head = git(app, origin, "rev-parse", "--verify", "-q", "HEAD") if top else None
    if top and head is not None and head.ok and head.out.strip():
        sc.kind, sc.branch, sc.base_commit = "git", f"kurooto/{sid}", head.out.strip()
        r = git(app, top, "worktree", "add", "-q", "-b", sc.branch, str(sc.work), sc.base_commit, timeout=300)
        if not r.ok:
            shutil.rmtree(d, ignore_errors=True)
            raise RuntimeError(f"couldn't make a worktree: {(r.err or r.out).strip()[-200:]}")
    else:
        sc.work.mkdir(parents=True, exist_ok=True)
        sc.base.mkdir(parents=True, exist_ok=True)
    sc.save()
    app.events.emit("scratch_made", id=sid, kind=sc.kind, lazy=lazy)
    return sc


def attach(app: App, sc: Scratch, jid: str) -> None:
    """This AI request works in this scratch folder."""
    sc.jobs = [*sc.jobs, jid][-20:]
    sc.save()
    jobs = getattr(app, "jobs", None)
    if jobs is not None and hasattr(jobs, "set_scratch"):
        jobs.set_scratch(jid, sc.id)


def seed(sc: Scratch, rel: str, new_text: str | None, old_text: str | None) -> None:
    """A mirror's file set by Kurooto itself (a skill Dreaming rewrote): the original as `old_text` (None: a new file)
    and the change as `new_text` (None: deleted)."""
    rel = clean_rel(rel) or ""
    if not rel:
        raise ValueError("unusable path")
    if old_text is not None:
        b = sc.base / rel
        b.parent.mkdir(parents=True, exist_ok=True)
        b.write_bytes(old_text.encode("utf-8"))
    sc.seeded[rel] = sha(old_text.encode("utf-8")) if old_text is not None else None
    w = sc.work / rel
    if new_text is not None:
        w.parent.mkdir(parents=True, exist_ok=True)
        w.write_bytes(new_text.encode("utf-8"))
    sc.save()


def remove(app: App, sc: Scratch) -> None:
    """Delete the scratch folder (and its worktree and branch). The original is never touched."""
    if sc.kind == "git":
        git(app, sc.src, "worktree", "remove", "--force", str(sc.work), timeout=120)
        if sc.branch.startswith("kurooto/"):
            git(app, sc.src, "branch", "-q", "-D", sc.branch)
        git(app, sc.src, "worktree", "prune")
    shutil.rmtree(sc.root, ignore_errors=True)
    app.events.emit("scratch_removed", id=sc.id)


def cleanup(app: App, keep_days: float, keep: set[str] | None = None) -> int:
    """Scratch folders older than keep_days (and not `keep`: ones a waiting proposal or a running request needs)."""
    keep = keep or set()
    cutoff = time.time() - keep_days * 86400
    n = 0
    for sc in every(app):
        if sc.id in keep or sc.created > cutoff:
            continue
        remove(app, sc)
        n += 1
    return n


# ------------------------------------------------------------------------------------------- paths inside it
def clean_rel(raw: str) -> str | None:
    """A relative path as posix, or None when it's unusable (absolute, .., empty parts)."""
    s = str(raw or "").strip().replace("\\", "/").strip("/")
    if not s or re.match(r"^[A-Za-z]:", s):
        return None
    parts = s.split("/")
    if any(p in ("", ".", "..") for p in parts):
        return None
    return "/".join(parts)


def locate(sc: Scratch, raw: str, note: bool = False) -> tuple[str | None, str]:
    """Where a path the AI named is, relative to the original (and to the scratch folder): an absolute path inside
    either, or a path relative to them; for the notes, a note slug ("inbox/an-idea"). (rel, "") or (None, why)."""
    s = str(raw or "").strip().replace("\\", "/")
    if not s:
        return None, "Which file?"
    p = Path(s).expanduser()
    if p.is_absolute():
        real = p.resolve()
        rel = None
        for root in (sc.work, sc.src):
            rr = root.resolve()
            if real == rr or rr in real.parents:
                rel = real.relative_to(rr).as_posix()
                break
        if rel is None:
            return None, "outside"
    else:
        rel = clean_rel(s)
        if rel is None:
            return None, "outside"
    if note and not Path(rel).suffix:
        rel += ".md"
    parts = rel.split("/")
    if any(x in NEVER for x in parts):
        return None, "outside"
    if secret(rel):
        return None, "That's a file of keys or passwords: never read or changed."
    if sc.kind == "files" and any(x.startswith(".") for x in parts):
        return None, "Hidden files and folders are left alone."
    # a link inside either copy must not lead out of it
    for root in (sc.work, sc.src):
        target = (root / rel).resolve()
        rr = root.resolve()
        if (root / rel).exists() and target != rr and rr not in target.parents:
            return None, "outside"
    return rel, ""


def pull(sc: Scratch, rel: str) -> None:
    """A mirror: copy the original's file in (and keep it as it was in base/) before the first change to it."""
    if sc.kind != "files" or rel in sc.seeded:
        return
    o = sc.src / rel
    if o.is_file():
        data = o.read_bytes()
        for d in (sc.work, sc.base):
            f = d / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(data)
        sc.seeded[rel] = sha(data)
    else:
        sc.seeded[rel] = None
    sc.save()


def read(sc: Scratch, rel: str) -> str | None:
    """The file as the AI left it: its scratch copy if there is one, else the original (None: neither)."""
    w = sc.work / rel
    if w.is_file():
        return w.read_text(encoding="utf-8", errors="replace")
    if sc.kind == "files" and rel in sc.seeded:  # copied in, then deleted here
        return None
    o = sc.src / rel
    return o.read_text(encoding="utf-8", errors="replace") if o.is_file() else None


def write(sc: Scratch, rel: str, text: str) -> None:
    pull(sc, rel)
    f = sc.work / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    with open(f, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def delete(sc: Scratch, rel: str) -> bool:
    pull(sc, rel)
    f = sc.work / rel
    if f.is_file():
        f.unlink()
        return True
    return False


def block(app: App, sc: Scratch, raw: str, tool: str) -> str:
    """A write outside the scratch folder: refused, kept for the proposal and the log."""
    sc.blocked = [*sc.blocked, str(raw)[:200]][-20:]
    sc.save()
    app.events.emit("scratch_blocked", id=sc.id, tool=tool)
    return (
        f"Refused: {raw} is outside your scratch folder ({sc.work}). In this request you may write only there; "
        "the user sees your changes as a proposal and applies them."
    )


# --------------------------------------------------------------------------------------------------- changes
@dataclass
class Change:
    path: str
    status: str  # "added", "changed", "deleted"
    added: int = 0
    removed: int = 0
    binary: bool = False
    old_sha: str | None = None  # what the original must still be at Apply (None: must not exist)
    new_sha: str | None = None


@dataclass
class Changes:
    files: list = field(default_factory=list)  # [Change]
    patch: str = ""  # the unified diff (git: with binary parts)
    dropped: list = field(default_factory=list)  # changed paths left out (keys, hidden, Kurooto's own)

    @property
    def size(self) -> int:
        return len(self.patch.encode("utf-8"))

    @property
    def deletes(self) -> list[str]:
        return [c.path for c in self.files if c.status == "deleted"]


def _text(data: bytes | None) -> str | None:
    if data is None or len(data) > MAX_TEXT or b"\x00" in data[:8192]:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _walk(root: Path, hidden_ok: bool, limit: int = WALK_MAX):
    n = 0
    for dirpath, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in NEVER and (hidden_ok or not d.startswith("."))]
        for name in names:
            if not hidden_ok and name.startswith("."):
                continue
            yield Path(dirpath) / name
            n += 1
            if n >= limit:
                return


def changes(app: App, sc: Scratch) -> Changes:
    """What the AI changed: the scratch folder against the original (a mirror: against the original as it was when
    each file was first copied in; files it made itself: against the original now)."""
    return _git_changes(app, sc) if sc.kind == "git" else _file_changes(sc)


def _file_changes(sc: Scratch) -> Changes:
    out = Changes()
    rels = set(sc.seeded)
    for f in _walk(sc.work, hidden_ok=True):
        rel = f.relative_to(sc.work).as_posix()
        if any(x.startswith(".") for x in rel.split("/")) or secret(rel):
            out.dropped.append(rel)
            continue
        rels.add(rel)
    hunks = []
    for rel in sorted(rels):
        w = sc.work / rel
        new = w.read_bytes() if w.is_file() else None
        if rel in sc.seeded:
            b = sc.base / rel
            old = b.read_bytes() if sc.seeded[rel] is not None and b.is_file() else None
            old_sha = sc.seeded[rel]
        else:  # made in the scratch folder by the AI's own tools: compared with the original now
            o = sc.src / rel
            old = o.read_bytes() if o.is_file() else None
            old_sha = sha(old) if old is not None else None
            if old is not None:
                b = sc.base / rel
                b.parent.mkdir(parents=True, exist_ok=True)
                b.write_bytes(old)
            sc.seeded[rel] = old_sha
        if new == old:
            continue
        status = "added" if old is None else "deleted" if new is None else "changed"
        c = Change(rel, status, old_sha=old_sha, new_sha=sha(new) if new is not None else None)
        a, b2 = _text(old) if old is not None else "", _text(new) if new is not None else ""
        if a is None or b2 is None:
            c.binary = True
            hunks.append(f"diff --kurooto a/{rel} b/{rel}\nBinary file {status}: {rel}\n")
        else:
            lines = list(
                difflib.unified_diff(
                    a.splitlines(keepends=True),
                    b2.splitlines(keepends=True),
                    "/dev/null" if old is None else f"a/{rel}",
                    "/dev/null" if new is None else f"b/{rel}",
                    n=3,
                )
            )
            c.added = sum(1 for ln in lines if ln.startswith("+") and not ln.startswith("+++"))
            c.removed = sum(1 for ln in lines if ln.startswith("-") and not ln.startswith("---"))
            body = "".join(ln if ln.endswith("\n") else ln + "\n\\ No newline at end of file\n" for ln in lines)
            hunks.append(f"diff --kurooto a/{rel} b/{rel}\n{body}")
        out.files.append(c)
    sc.save()
    out.patch = "".join(hunks)
    return out


def _git_changes(app: App, sc: Scratch) -> Changes:
    out = Changes()
    w = sc.work
    r = git(app, w, "add", "-A", "--", ".")
    if not r.ok:
        raise RuntimeError(f"git add failed: {(r.err or r.out).strip()[-200:]}")
    ns = git(app, w, "diff", "--cached", "--no-renames", "--name-status", "-z", sc.base_commit)
    if not ns.ok:
        raise RuntimeError(f"git diff failed: {(ns.err or ns.out).strip()[-200:]}")
    bits = [b for b in ns.out.split("\0") if b]
    keep: list[tuple[str, str]] = []
    for code, path in zip(bits[0::2], bits[1::2], strict=False):
        parts = path.split("/")
        if secret(path) or any(x in NEVER for x in parts):
            out.dropped.append(path)
            continue
        keep.append((code[:1], path))
    if not keep:
        return out
    paths = [p for _c, p in keep]
    num = git(app, w, "diff", "--cached", "--no-renames", "--numstat", "-z", sc.base_commit, "--", *paths)
    stats = {}
    for row in [x for x in num.out.split("\0") if x]:
        m = re.match(r"^(-|\d+)\t(-|\d+)\t(.*)$", row)
        if m:
            stats[m[3]] = (m[1], m[2])
    for code, path in keep:
        a, d = stats.get(path, ("0", "0"))
        status = {"A": "added", "D": "deleted"}.get(code, "changed")
        old = git(app, w, "rev-parse", "-q", "--verify", f"{sc.base_commit}:{path}")
        c = Change(path, status, binary=a == "-", old_sha=old.out.strip() or None if status != "added" else None)
        c.added, c.removed = (0, 0) if a == "-" else (int(a), int(d))
        out.files.append(c)
    patch = git(app, w, "diff", "--cached", "--no-renames", "--binary", "--full-index", sc.base_commit, "--", *paths)
    out.patch = patch.out
    return out


# ---------------------------------------------------------------------------------- what changed outside it
def fingerprint(app: App, sc: Scratch) -> dict:
    """The original as it is now, cheaply: a repository's commit and status; a folder's files' sizes and times."""
    if sc.kind == "git":
        head = git(app, sc.src, "rev-parse", "-q", "--verify", "HEAD")
        st = git(app, sc.src, "status", "--porcelain=v1", "-z", "--untracked-files=all")
        return {"head": head.out.strip(), "status": st.out}
    out = {}
    for f in _walk(sc.src, hidden_ok=False):
        try:
            s = f.stat()
        except OSError:
            continue
        out[f.relative_to(sc.src).as_posix()] = (s.st_size, s.st_mtime_ns)
    return {"files": out}


def audit(app: App, sc: Scratch, before: dict) -> list[str]:
    """Files of the original that changed while the AI worked (it may have been you, a sync, or the AI writing where it
    shouldn't): kept on the scratch folder for the proposal to say. [] when nothing changed."""
    after = fingerprint(app, sc)
    if sc.kind == "git":
        changed = []
        if before.get("head") != after.get("head"):
            changed.append("(the branch moved: a new commit)")
        b = set(x for x in (before.get("status") or "").split("\0") if x)
        a = set(x for x in (after.get("status") or "").split("\0") if x)
        changed += sorted(x[3:] for x in a - b)
    else:
        b, a = before.get("files") or {}, after.get("files") or {}
        changed = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
    if changed:
        sc.outside = [*sc.outside, *changed][-50:]
        sc.save()
        app.events.emit("scratch_outside", id=sc.id, n=len(changed))
    return changed


# -------------------------------------------------------------------------------------------------- checks
def sandbox(work: Path, hide: list[Path]) -> list[str] | None:
    """The command prefix that keeps a check inside `work` with no network, or None when this computer has none."""
    if sys.platform.startswith("linux"):
        bwrap = shutil.which("bwrap")
        if not bwrap:
            return None
        args = [bwrap, "--ro-bind", "/", "/", "--dev", "/dev", "--proc", "/proc", "--tmpfs", "/tmp"]  # noqa: S108
        for h in hide:  # what a check never needs: Kurooto's settings and keys, your keys
            if h.is_dir():
                args += ["--tmpfs", str(h)]
        args += ["--bind", str(work), str(work), "--unshare-net", "--unshare-pid", "--die-with-parent",
                 "--new-session", "--chdir", str(work), "--"]  # fmt: skip
        return args
    if sys.platform == "darwin" and shutil.which("sandbox-exec"):  # pragma: no cover (macOS)
        w = str(work.resolve()).replace('"', "")
        profile = (
            "(version 1)(allow default)(deny network*)"
            f'(deny file-write* (require-not (require-any (subpath "{w}") (subpath "/private/tmp") '
            '(subpath "/private/var/folders") (literal "/dev/null") (literal "/dev/tty"))))'
        )
        return ["sandbox-exec", "-p", profile]
    return None


def run_checks(app: App, sc: Scratch, timeout: float = 300) -> dict:
    """The project's checks in the scratch folder: {"ran", "ok", "code", "out", "seconds", "why"}."""
    cmd = (sc.checks or "").strip()
    if not cmd:
        return {"ran": False, "why": "checks are off for this project"}
    home_dir = Path.home()
    hide = [app.paths.config, app.paths.state, *(home_dir / x for x in (".ssh", ".gnupg", ".aws", ".gemini", ".claude",
            ".config/gcloud", ".docker", ".kube"))]  # fmt: skip
    pre = sandbox(sc.work, hide)  # Kurooto's state folder is hidden too; the scratch folder is bound back in
    if pre is None:
        return {"ran": False, "why": "this computer has no sandbox for them (bubblewrap on Linux, macOS's own)"}
    env = {
        k: os.environ[k] for k in ("PATH", "LANG", "LC_ALL", "HOME", "USER", "TERM", "SYSTEMROOT") if k in os.environ
    }
    env["TMPDIR"] = "/tmp"  # noqa: S108 (inside the sandbox: a fresh one of its own)
    shell = ["sh", "-c", cmd] if os.name != "nt" else ["cmd", "/c", cmd]
    t0 = time.monotonic()
    r = proc.run([*pre, *shell], cwd=sc.work, env=env, timeout=timeout)
    secs = round(time.monotonic() - t0, 1)
    out = ((r.out or "") + ("\n" + r.err if r.err else "")).strip()
    if r.code is None:
        return {"ran": True, "ok": False, "code": None, "out": out[-CHECK_OUT:], "seconds": secs,
                "why": f"stopped after {int(timeout)} s"}  # fmt: skip
    return {"ran": True, "ok": r.code == 0, "code": r.code, "out": out[-CHECK_OUT:], "seconds": secs, "why": ""}


# ------------------------------------------------------------------------------------- the AI's tools there
def context(app: App, sc: Scratch) -> str:
    """What the AI is told about its scratch folder (after the usual unattended-run context)."""
    what = (
        f"a git worktree of {sc.origin} on its own branch ({sc.branch}): every file as last committed"
        if sc.kind == "git"
        else f"a mirror of {sc.origin} that starts empty: to change a file there, change the same path here. "
        "Kurooto's tools (write_note, add_to_note, edit_note, delete_file) copy the file in first by themselves; "
        "with your own file tools, copy the original here first, then change the copy"
    )
    checks = (
        "run_checks runs the project's own checks (the command they chose) in your scratch folder; use it after "
        "your changes"
        if sc.checks
        else "Don't run commands that build, test or change anything"
    )
    return "\n".join(
        [
            "",
            "THIS REQUEST CHANGES FILES, THROUGH A SCRATCH FOLDER.",
            f"Your scratch folder: {sc.work}. It's {what}.",
            f"Write only in your scratch folder; {sc.origin} stays read-only for you. Nothing you write reaches it "
            "until the user has seen your changes as a proposal (a diff) and tapped Apply, so you may draft freely.",
            "Change only what the request asks for. To remove a file, delete it in the scratch folder (delete_file); "
            "the proposal will say so at the top.",
            f"{checks}. Never read, copy or change keys, passwords or .env files.",
            "When you're done, answer with: a first line that is a short title for the change (under 70 characters), "
            "then 2 to 5 short lines in plain English on what you changed and why. They're shown above the diff. If "
            "nothing should change, say so and why.",
        ]
    )


def tools(app: App, sc: Scratch, jid: str | None = None) -> list[Tool]:
    """The tools of a request that works in a scratch folder: everything that only reads, as always (reading a file
    finds the scratch copy first), and writing that goes into the scratch folder and nowhere else. Tools that change
    anything else (reminders, calls, syncs, other features' writes) aren't there."""
    from kurooto.core import tools as T
    from kurooto.modules.calls.tools import Tool, arg, clip

    notes = os.path.normcase(os.path.abspath(sc.origin)) == os.path.normcase(os.path.abspath(app.workspace))

    def where(raw: str, tool: str) -> tuple[str | None, str]:
        rel, why = locate(sc, raw, note=notes and not Path(str(raw)).suffix)
        if rel is None and why == "outside":
            return None, block(app, sc, raw, tool)
        return rel, why

    def read_one(a: dict):
        rel, why = locate(sc, a.get("slug") or a.get("path") or "", note=notes)
        if rel is None:
            return why if why != "outside" else f"That's not in {sc.label} or your scratch folder."
        text = read(sc, rel)
        return clip(text, 12000) if text is not None else f"No file {rel}."

    def read_any(a: dict):
        """read_file: the project (scratch copy first), else any folder the AI may read, as always."""
        raw = str(a.get("path") or "")
        rel, why = locate(sc, raw, note=False)
        if rel is None and why == "outside":
            if secret(raw):
                return "That's a file of keys or passwords: never read."
            return T.FileTools(app).read(a)
        return read_one(a)

    def write_new(a: dict):
        rel, why = where(a.get("slug", ""), "write_note")
        if rel is None:
            return why
        text = str(a.get("text") or "")
        if not text.strip() or len(text) > T.MAX_NOTE:
            return "Nothing to write, or too long."
        if read(sc, rel) is not None:
            return "That exists already: use edit_note (or add_to_note) to change it."
        write(sc, rel, text.rstrip("\n") + "\n")
        return f"Written in your scratch folder: {rel} (a new file, in the proposal)."

    def add(a: dict):
        rel, why = where(a.get("slug", ""), "add_to_note")
        if rel is None:
            return why
        text = str(a.get("text") or "")
        if not text.strip() or len(text) > T.MAX_NOTE:
            return "Nothing to add, or too long."
        old = read(sc, rel) or ""
        write(sc, rel, T.add_to_section(old, str(a.get("section") or ""), text))
        return f"Added, in your scratch folder: {rel}."

    def edit(a: dict):
        rel, why = where(a.get("slug", ""), "edit_note")
        if rel is None:
            return why
        old_part, new_part = str(a.get("old") or ""), str(a.get("new") or "")
        text = read(sc, rel)
        if text is None:
            return f"No file {rel}."
        if not old_part.strip():
            return "Say which exact text to replace (read_note shows it)."
        n = text.count(old_part)
        if n != 1:
            return "That text isn't in the file." if not n else f"That text is there {n} times; include more of it."
        write(sc, rel, text.replace(old_part, new_part, 1))
        return f"Changed in your scratch folder: {rel} (the user sees it as a proposal)."

    def remove_file(a: dict):
        rel, why = where(a.get("path", ""), "delete_file")
        if rel is None:
            return why
        if read(sc, rel) is None:
            return f"No file {rel}."
        if sc.kind == "files":
            delete(sc, rel)
        else:
            (sc.work / rel).unlink(missing_ok=True)
        return (
            f"Deleted in your scratch folder: {rel} (the proposal says so at the top; nothing is deleted before Apply)."
        )

    def checks(a: dict):
        timeout = float(app.settings.get("projects.check_timeout_s") or 300)
        r = run_checks(app, sc, timeout)
        if not r.get("ran"):
            return f"Checks didn't run: {r.get('why')}."
        head = "passed" if r.get("ok") else f"failed ({r.get('why') or 'exit ' + str(r.get('code'))})"
        return f"Checks {head} in {r.get('seconds')} s.\n{r.get('out') or ''}"

    where_words = f"in {sc.label} ({'a note slug or a path' if notes else 'a path relative to the project'})"
    own = [
        Tool(
            "read_note",
            f"Read a file {where_words}: your scratch copy if you changed it, else the original.",
            read_one,
            {"slug": arg()},
            ("slug",),
            writes=False,
        ),
        Tool(
            "read_file",
            f"Read a file {where_words} (your scratch copy first), or anywhere you may read as always (notes, "
            "Documents, Downloads ...): text, Markdown, PDF, Word.",
            read_any,
            {"path": arg()},
            ("path",),
            writes=False,
        ),
        Tool(
            "write_note",
            f"Create a NEW file {where_words}, in your scratch folder.",
            write_new,
            {"slug": arg(), "text": arg("the whole file")},
            ("slug", "text"),
            writes=True,
        ),
        Tool(
            "add_to_note",
            "Add text to a file (at the end, or a '## section''s end), in your scratch folder.",
            add,
            {"slug": arg(), "text": arg(), "section": arg("heading text, optional")},
            ("slug", "text"),
            writes=True,
        ),
        Tool(
            "edit_note",
            "Replace one exact passage of a file with new text, in your scratch folder.",
            edit,
            {"slug": arg(), "old": arg("the exact text to replace"), "new": arg("what it becomes")},
            ("slug", "old"),
            writes=True,
        ),
        Tool(
            "delete_file",
            "Delete a file, in your scratch folder (the proposal says so at the top).",
            remove_file,
            {"path": arg()},
            ("path",),
            writes=True,
        ),
    ]
    if sc.checks:
        own.append(Tool("run_checks", "Run the project's checks in your scratch folder (time limit, no network).",
                        checks, writes=False))  # fmt: skip
    names = {t.name for t in own}
    keep = [t for t in T.agent_tools(app) if t.writes is False and t.name not in names]  # reading, as always
    return own + keep


def lazy_tools(app: App, jid: str, base: list[Tool]) -> list[Tool]:
    """An ordinary request's tools with edit_note turned into a proposal: the first change to your text makes a
    scratch folder of your notes for this request, and the change goes there; reading a note finds that copy first.
    Adding to notes and new notes are as always."""
    from kurooto.core import tools as T
    from kurooto.modules.calls.tools import Tool, clip

    root = Path(os.path.abspath(app.workspace))

    def mine() -> Scratch | None:
        sc = for_job(app, jid)
        return sc if sc is not None and sc.lazy else None

    def edit(a: dict):
        f, why = T.writable(app, a.get("slug", ""), must_exist=True)
        if not f:
            return why
        try:
            rel = f.relative_to(root.resolve()).as_posix()
        except ValueError:  # course files, add-ons' skills: as always
            return T.NoteTools(app).edit(a)
        sc = mine()
        if sc is None:
            sc = create(app, root, "your notes", lazy=True, git_ok=False)
            attach(app, sc, jid)
        old_part, new_part = str(a.get("old") or ""), str(a.get("new") or "")
        text = read(sc, rel)
        if text is None:
            return "There's no such file."
        if not old_part.strip():
            return "Say which exact text to replace (read_note shows it)."
        n = text.count(old_part)
        if n != 1:
            return "That text isn't in the file." if not n else f"That text is there {n} times; include more of it."
        write(sc, rel, text.replace(old_part, new_part, 1))
        return (
            f"Proposed: the change to {rel} waits for the user's OK (they get it as a proposal with the diff when "
            "this request ends). Tell them it's proposed, not done."
        )

    def read_one(a: dict):
        sc = mine()
        if sc is not None:
            f = T.note_path(root, a.get("slug", ""), must_exist=False)
            if f is not None:
                rel = f.relative_to(root.resolve()).as_posix()
                if rel in sc.seeded:
                    text = read(sc, rel)
                    return clip(text, 12000) if text is not None else f'No note "{a.get("slug", "")}".'
        return T.NoteTools(app).read(a)

    out = []
    for t in base:
        if t.name == "edit_note":
            t = Tool(t.name, t.description + " The change becomes a proposal the user approves.", edit, t.params,
                     t.required, t.offline, t.hint, t.writes)  # fmt: skip
        elif t.name == "read_note":
            t = Tool(t.name, t.description, read_one, t.params, t.required, t.offline, t.hint, t.writes)
        out.append(t)
    return out

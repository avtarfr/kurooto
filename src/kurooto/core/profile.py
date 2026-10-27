"""Your Kurooto profile: your setup, saved ENCRYPTED in a private GitHub repository of yours (the one Notes sync
uses, or another), so a new computer or a reinstall is set up again in a minute ("I've used Kurooto before" on the
setup page, or `kurooto profile restore`).

What's in it:
    settings   everything you changed in Settings, and which features you had on
    secrets    your bot token, API keys, the Google sign-in, your call line's keys and its Cloudflare sign-in
    state      deadlines, quiz progress, routines, observations, the Agent plan calendar, Classroom's "already seen"
               lists, and the reminders, calls and alarm you scheduled
Never in it: your notes (Notes sync keeps those), AI request history, call transcripts, the reports you gave "Teach
it about you", caches, logs, and this computer's own keys (the dashboard's).

How it's kept: on its own branch, kurooto-profile, in a folder .kurooto-profile/:
    key.json        your data key, locked with your passphrase (scrypt, then AES-GCM)
    manifest.json   when it was saved and from which computer (a random id), and checksums of the parts, signed
    *.enc           settings, secrets and state, each encrypted with the data key (AES-GCM)
Everything personal is encrypted, settings included. The passphrase is never stored or logged; this computer keeps
the data key in its keychain, like your other keys, so it can save by itself. A new computer needs the passphrase
once. Forget it and the profile can't be opened (your notes are still fine).
"""

from __future__ import annotations

import base64
import binascii
import datetime as dt
import hashlib
import hmac
import json
import os
import platform
import secrets as pysecrets
import shutil
import time
from fnmatch import fnmatch
from pathlib import Path, PurePosixPath
from zoneinfo import ZoneInfo

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from kurooto import __version__
from kurooto.core import egress, proc
from kurooto.core.clock import now
from kurooto.core.config import merge
from kurooto.core.lock import Lock
from kurooto.core.state import jload, jsave

FOLDER = ".kurooto-profile"
BRANCH = "kurooto-profile"
FORMAT = 1
KDF = {"n": 2**17, "r": 8, "p": 1}  # scrypt: about 0.3 s and 128 MB, once per unlock (tests lower it)
MIN_PASSPHRASE = 10
DEK = "profile.key"  # this computer's copy of the data key (keychain); never in the profile itself
TOKEN = "profile.token"  # noqa: S105 (the secret's name): a token for the profile's own repository
NEVER = {"web.token", DEK, "ledger.key", "biometric.voice.key"}  # this computer's own keys (the memory ledger's, Voice
# ID's too): never saved or restored
PARTS = ("settings", "secrets", "state")
KEEP = (  # (folder, pattern inside it): Kurooto's own state worth keeping on a new computer; nothing else goes
    ("state", "deadlines.json"),
    ("state", "deadlines-recurring.json"),
    ("state", "quiz/*.json"),
    ("state", "observations.json"),
    ("state", "retro-state.json"),
    ("state", "alarm.json"),
    ("state", "agent-plan.json"),
    ("state", "google-classroom.json"),
    ("state", "classroom-notes/folders.json"),
    ("state", "classroom-notes/seen.json"),
    ("data", "skills/routines.json"),
)
SKIP = {"state/quiz/session.json", "state/quiz/offered.json"}  # a practice session in progress: not worth moving
LOCAL_ONLY = ("data/mail/confidential/",)  # confidential mail summarised on this computer stays on this computer
SECRET_FILES = (("config", "cloudflare/.wrangler/config/default.toml"),)  # the call line's Cloudflare sign-in
SCHEDULED = ("reminders:", "calls:ring:", "alarm:ring")  # one-off jobs that are yours: reminders, calls, the alarm
FOLDERS = ("you.workspace", "backups.folder", "overlay.path", "files.folder")  # kept only where it exists here
LOCAL = ("brain.agy.io_mode",)  # how this computer runs a program: found out again here
MAX_FILE = 4 * 1024**2
README = """# Kurooto profile

Kurooto keeps your setup here, encrypted with your passphrase, so a new computer is set up again in a minute:
on its setup page choose "I've used Kurooto before", or run `kurooto profile restore`.

Don't edit these files: a changed file is refused when restoring. Every earlier version is in this branch's history.
"""


class ProfileError(Exception):
    """Something went wrong that the person should read (plain English)."""


class WrongPassphrase(ProfileError):
    pass


class Damaged(ProfileError):
    pass


# ------------------------------------------------------------------------------------------------- encryption
def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode()


def _unb64(s) -> bytes:
    try:
        return base64.b64decode(str(s), validate=True)
    except (binascii.Error, ValueError):
        raise Damaged("a file in your profile is damaged") from None


def canon(obj) -> bytes:
    """The one byte form of a JSON value, for checksums."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode()


def _kek(passphrase: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    return Scrypt(salt=salt, length=32, n=n, r=r, p=p).derive(passphrase.encode("utf-8"))


def check_passphrase(passphrase: str, again: str | None = None) -> None:
    if len(passphrase or "") < MIN_PASSPHRASE:
        raise ProfileError(
            f"Pick a passphrase of at least {MIN_PASSPHRASE} characters (a few words you'll remember is best)."
        )
    if again is not None and again != passphrase:
        raise ProfileError("The two passphrases aren't the same.")


def new_key(passphrase: str) -> tuple[bytes, dict]:
    """A new random data key, and key.json: that key locked with the passphrase."""
    check_passphrase(passphrase)
    dek, salt, nonce, kid = os.urandom(32), os.urandom(16), os.urandom(12), pysecrets.token_hex(8)
    wrapped = AESGCM(_kek(passphrase, salt, **KDF)).encrypt(nonce, dek, f"kurooto-profile:key:{kid}".encode())
    return dek, {
        "format": FORMAT,
        "id": kid,
        "kdf": "scrypt",
        **KDF,
        "salt": _b64(salt),
        "nonce": _b64(nonce),
        "key": _b64(wrapped),
    }


def unlock(keyfile: dict, passphrase: str) -> bytes:
    """The data key from key.json and the passphrase. WrongPassphrase / Damaged."""
    try:
        n, r, p, kid = int(keyfile["n"]), int(keyfile["r"]), int(keyfile["p"]), str(keyfile["id"])
        salt, nonce, wrapped = _unb64(keyfile["salt"]), _unb64(keyfile["nonce"]), _unb64(keyfile["key"])
    except (KeyError, TypeError, ValueError):
        raise Damaged("your profile's key.json is damaged") from None
    # a changed file must not make this computer spend minutes or gigabytes
    if (
        keyfile.get("kdf") != "scrypt"
        or not (2**10 <= n <= 2**20)
        or n & (n - 1)
        or not (1 <= r <= 16)
        or not 1 <= p <= 4
    ):
        raise Damaged("your profile's key.json is damaged")
    try:
        return AESGCM(_kek(passphrase or "", salt, n, r, p)).decrypt(
            nonce, wrapped, f"kurooto-profile:key:{kid}".encode()
        )
    except (InvalidTag, ValueError):
        raise WrongPassphrase("That passphrase doesn't open this profile.") from None


def _sub(dek: bytes, kid: str, what: str) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=f"kurooto-profile:{what}:{kid}".encode()).derive(
        dek
    )


def seal(dek: bytes, kid: str, name: str, data: bytes) -> dict:
    nonce = os.urandom(12)
    ct = AESGCM(_sub(dek, kid, "enc")).encrypt(nonce, data, f"kurooto-profile:{kid}:{name}".encode())
    return {"format": FORMAT, "nonce": _b64(nonce), "data": _b64(ct)}


def unseal(dek: bytes, kid: str, name: str, env: dict) -> bytes:
    try:
        return AESGCM(_sub(dek, kid, "enc")).decrypt(
            _unb64(env["nonce"]), _unb64(env["data"]), f"kurooto-profile:{kid}:{name}".encode()
        )
    except (InvalidTag, KeyError, TypeError, ValueError):
        raise Damaged(f"{name}.enc in your profile was changed or damaged, so it can't be trusted") from None


def mac(dek: bytes, kid: str, data: bytes) -> str:
    return hmac.new(_sub(dek, kid, "mac"), data, hashlib.sha256).hexdigest()


def sign(dek: bytes, kid: str, manifest: dict) -> dict:
    body = {k: v for k, v in manifest.items() if k != "mac"}
    return {**body, "mac": mac(dek, kid, canon(body))}


def verify(dek: bytes, kid: str, manifest) -> dict:
    if not isinstance(manifest, dict) or not hmac.compare_digest(
        str(manifest.get("mac", "")), sign(dek, kid, manifest)["mac"]
    ):
        raise Damaged("manifest.json in your profile was changed or damaged, so it can't be trusted")
    if manifest.get("key") != kid:
        raise Damaged("the profile's parts don't belong to its key")
    return manifest


# ------------------------------------------------------------------------------------------------ what goes in
def _allowed(top: str, rel: str) -> bool:
    """Is <top>/<rel> one of the files the profile may hold (when saving, and above all when restoring)?"""
    pp = PurePosixPath(rel)
    if not rel or pp.is_absolute() or "\\" in rel or any(x in ("", ".", "..") for x in pp.parts):
        return False
    if f"{top}/{rel}" in SKIP or f"{top}/{rel}".startswith(LOCAL_ONLY):
        return False
    return any(t == top and rel.count("/") == pat.count("/") and fnmatch(rel, pat) for t, pat in KEEP)


def _roots(app) -> dict[str, Path]:
    return {"state": app.paths.state, "data": app.paths.data, "config": app.paths.config}


def _read_text(f: Path) -> str | None:
    try:
        if not f.is_file() or f.stat().st_size > MAX_FILE:
            return None
        return f.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def secret_names(app) -> list[str]:
    from kurooto.modules.backups import known_secret_names  # one list of the keys Kurooto uses (Backups' too)

    return [n for n in known_secret_names(app.secrets) if n not in NEVER]


def collect(app) -> dict[str, dict]:
    """The three parts, as plain values (they're encrypted before they leave)."""
    roots = _roots(app)
    secrets = {n: v for n in secret_names(app) if (v := app.secrets.get(n))}
    secret_files = {}
    for top, rel in SECRET_FILES:
        text = _read_text(roots[top] / rel)
        if text is not None:
            secret_files[f"{top}/{rel}"] = text
    files = {}
    for top, pat in KEEP:
        base = roots[top] / PurePosixPath(pat).parent
        for f in sorted(base.glob(PurePosixPath(pat).name)) if base.is_dir() else []:
            rel = f.relative_to(roots[top]).as_posix()
            text = _read_text(f) if _allowed(top, rel) else None
            if text is not None:
                files[f"{top}/{rel}"] = text
    t = time.time()
    scheduled = [
        {
            "key": j.key,
            "module": j.module,
            "action": j.action,
            "payload": {k: v for k, v in j.payload.items() if k not in ("late_s", "missed")},
            "at": j.next_run,
            "grace_s": j.grace_s,
            "respect": j.respect,
        }
        for j in app.scheduler.jobs()
        if j.kind == "once" and j.key.startswith(SCHEDULED) and j.next_run > t
    ]
    return {
        "settings": app.settings.user(),
        "secrets": {"secrets": secrets, "files": secret_files},
        "state": {"files": files, "scheduled": scheduled},
    }


def counts(parts: dict) -> dict:
    s, st = parts.get("secrets") or {}, parts.get("state") or {}
    return {
        "settings": _leaves(parts.get("settings") or {}),
        "secrets": len(s.get("secrets") or {}) + len(s.get("files") or {}),
        "files": len(st.get("files") or {}),
        "scheduled": len(st.get("scheduled") or []),
        "features": len(((parts.get("settings") or {}).get("modules") or {}).get("enabled") or []),
    }


def _leaves(d: dict) -> int:
    return sum(_leaves(v) if isinstance(v, dict) else 1 for v in d.values())


# ------------------------------------------------------------------------------------------------- the repository
def git_exe(app) -> str | None:
    from kurooto.core.prereqs import Prereqs

    return Prereqs(app.paths.app, app.paths.cache).items["git"].find()


def ensure_git(app, progress=print) -> str:
    exe = git_exe(app)
    if exe:
        return exe
    from kurooto.core.prereqs import Prereqs

    ok, msg = Prereqs(app.paths.app, app.paths.cache).install("git", progress)
    exe = git_exe(app)
    if not exe:
        raise ProfileError(msg if not ok else "Git didn't install")
    return exe


def target(app) -> tuple[str, str | None, str]:
    """(address, token, branch) of the profile's repository: its own (profile.repo), else the one Notes sync uses."""
    s = app.settings
    branch = s.get("profile.branch") or BRANCH
    remote, repo = s.get("profile.remote") or "", s.get("profile.repo") or ""
    if remote:
        return remote, None, branch
    if repo:
        tok = app.secrets.get(TOKEN) or (
            app.secrets.get("notes_sync.token") if repo == s.get("notes_sync.repo") else None
        )
        return f"https://github.com/{repo}.git", tok, branch
    if s.get("notes_sync.remote"):
        return s.get("notes_sync.remote"), None, branch
    if s.get("notes_sync.repo"):
        return f"https://github.com/{s.get('notes_sync.repo')}.git", app.secrets.get("notes_sync.token"), branch
    raise ProfileError(
        "there's no repository for your profile yet: set up Notes sync, or give Profile sync a private repository"
    )


class Repo:
    """The profile's branch, through a small Git working copy of Kurooto's own (data/profile/repo). It never
    touches your notes folder or any other branch."""

    def __init__(self, app, url: str, token: str | None, branch: str = BRANCH):
        self.app, self.url, self.token, self.branch = app, url, token, branch
        self.dir = app.paths.data / "profile" / "repo"
        self.ref = f"refs/remotes/origin/{branch}"

    def _env(self) -> dict:
        env = {
            **os.environ,
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_AUTHOR_NAME": "Kurooto",
            "GIT_COMMITTER_NAME": "Kurooto",
            "GIT_AUTHOR_EMAIL": "kurooto@localhost",
            "GIT_COMMITTER_EMAIL": "kurooto@localhost",
            "LC_ALL": "C",
        }
        if self.token and self.url.startswith("https://github.com/"):
            # as in Notes sync: the token goes to git as an HTTP header in the environment, never a URL, file or argv
            basic = base64.b64encode(f"x-access-token:{self.token}".encode()).decode()
            env.update(
                GIT_CONFIG_COUNT="1",
                GIT_CONFIG_KEY_0="http.https://github.com/.extraheader",
                GIT_CONFIG_VALUE_0=f"AUTHORIZATION: basic {basic}",
            )
        return env

    def git(self, *args: str, timeout: float = 120) -> proc.Result:
        exe = git_exe(self.app)
        if not exe:
            raise ProfileError("Git isn't installed")
        if args and args[0] in egress.GIT_ONLINE:
            egress.handed("git", "Profile sync")
        return proc.run([exe, "-C", str(self.dir), *args], timeout=timeout, env=self._env())

    def _prepare(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        if not (self.dir / ".git").exists():
            r = self.git("init", "-q")
            if not r.ok:
                raise ProfileError(f"git init failed: {r.err.strip()[-200:]}")
        have = self.git("remote").out.split()
        self.git("remote", "set-url" if "origin" in have else "add", "origin", self.url)

    def fetch(self) -> bool:
        """Get the profile's branch. False if the repository has none yet."""
        self._prepare()
        r = self.git("ls-remote", "--heads", "origin", f"refs/heads/{self.branch}", timeout=90)
        if not r.ok:
            raise ProfileError(f"couldn't reach your repository: {_last(r)}")
        if not r.out.strip():
            self.git("update-ref", "-d", self.ref)
            return False
        f = self.git("fetch", "-q", "--depth", "1", "origin", f"+refs/heads/{self.branch}:{self.ref}", timeout=300)
        if not f.ok:
            raise ProfileError(f"couldn't fetch your profile: {_last(f)}")
        return True

    def read(self, name: str) -> str | None:
        r = self.git("show", f"{self.ref}:{FOLDER}/{name}")
        return r.out if r.ok else None

    def publish(self, files: dict[str, str], message: str, exists: bool) -> bool:
        """Make the branch's .kurooto-profile/ exactly `files` (the rest of the branch is left as it is) and send it
        up. False if nothing changed."""
        for attempt in range(2):
            if attempt:
                exists = self.fetch()  # someone else sent something meanwhile: build on top of theirs
            self.git("symbolic-ref", "HEAD", f"refs/heads/{self.branch}")
            if exists:
                self.git("update-ref", f"refs/heads/{self.branch}", self.ref)
                self.git("read-tree", self.ref)
            else:
                self.git("update-ref", "-d", f"refs/heads/{self.branch}")
                self.git("read-tree", "--empty")
            folder = self.dir / FOLDER
            if folder.exists():
                shutil.rmtree(folder)
            folder.mkdir(parents=True)
            for name, text in files.items():
                (folder / name).write_text(text, encoding="utf-8", newline="\n")
            self.git("add", "-A", "--", FOLDER)
            if exists and self.git("diff", "--cached", "--quiet").code == 0:
                return False
            c = self.git("commit", "-q", "-m", message)
            if not c.ok:
                raise ProfileError(f"couldn't save your profile: {_last(c)}")
            p = self.git("push", "-q", "origin", f"HEAD:refs/heads/{self.branch}", timeout=300)
            if p.ok:
                self.git("update-ref", self.ref, "HEAD")
                return True
            if attempt:
                raise ProfileError(f"couldn't send your profile to your repository: {_last(p)}")
        return False  # pragma: no cover


def _last(r: proc.Result) -> str:
    return (r.err or r.out or f"exit {r.code}").strip()[-200:]


# ----------------------------------------------------------------------------------------- this computer's record
def state_file(app) -> Path:
    return app.paths.state / "profile.json"  # not in backups (backups.SKIP_STATE): it names this computer


def local(app) -> dict:
    st = jload(state_file(app), {}) or {}
    if not st.get("machine"):
        st["machine"] = pysecrets.token_hex(8)
        jsave(state_file(app), st)
    return st


def record(app, **changes) -> dict:
    st = {**local(app), **changes}
    jsave(state_file(app), st)
    return st


def key_file(app) -> Path:
    return app.paths.data / "profile" / "key.json"  # a copy of key.json (no secret in it), to re-make the branch


def remember_key(app, dek: bytes, keyfile: dict) -> None:
    app.secrets.set(DEK, _b64(dek))
    jsave(key_file(app), keyfile)


def cached_key(app) -> bytes | None:
    v = app.secrets.get(DEK)
    try:
        return base64.b64decode(v, validate=True) if v else None
    except (binascii.Error, ValueError):
        return None


# ---------------------------------------------------------------------------------------------------- saving
def save(app, *, force: bool = False) -> tuple[bool, str]:
    """Save this computer's profile. Without `force` it doesn't overwrite a profile another computer saved since
    this one last saved or restored (it says so instead). Returns (ok, what happened)."""
    dek = cached_key(app)
    if not dek:
        raise ProfileError("this computer doesn't have your profile's key: connect Profile sync again (Set up)")
    url, token, branch = target(app)
    with Lock(app.paths.state, "profile", timeout=60):
        repo = Repo(app, url, token, branch)
        exists = repo.fetch()
        keyfile = _json(repo.read("key.json")) if exists else jload(key_file(app), None)
        if not isinstance(keyfile, dict) or not keyfile.get("id"):
            raise ProfileError("the profile's key is missing: connect Profile sync again (Set up)")
        kid = str(keyfile["id"])
        if exists and not _same_key(dek, keyfile):
            raise ProfileError(
                "the profile in your repository has another passphrase now (set on another computer): connect "
                "Profile sync again with that passphrase"
            )
        st = local(app)
        manifest = None
        if exists:
            raw = _json(repo.read("manifest.json"))
            try:
                manifest = verify(dek, kid, raw) if raw is not None else None
            except Damaged:
                if not force:
                    raise
            if (
                manifest
                and not force
                and manifest.get("machine") != st["machine"]
                and manifest.get("id") != st.get("saved_id")
            ):
                record(app, held=manifest.get("saved"))
                return False, (
                    f"your profile was saved from another computer ({_when(manifest.get('saved'))}), so this one "
                    "doesn't overwrite it. Restore it here (kurooto profile restore), or save over it (/profile save)"
                )
        parts = collect(app)
        files = {"README.md": README, "key.json": json.dumps(keyfile, indent=1) + "\n"}
        sums, changed = {}, manifest is None
        for name in PARTS:
            data = canon(parts[name])
            sums[name] = {"mac": mac(dek, kid, data)}
            old = ((manifest or {}).get("parts") or {}).get(name) or {}
            blob = repo.read(f"{name}.enc") if exists and old.get("mac") == sums[name]["mac"] else None
            if blob is None:  # changed (or new): sealed again; an unchanged part keeps its file as it is
                blob = json.dumps(seal(dek, kid, name, data), indent=1) + "\n"
                changed = True
            files[f"{name}.enc"] = blob
        if not changed:
            record(
                app,
                saved=manifest.get("saved"),
                saved_id=manifest.get("id"),
                at=time.time(),
                ok=True,
                error="",
                held="",
                counts=counts(parts),
            )
            return True, "Nothing changed since the last save."
        man = sign(
            dek,
            kid,
            {
                "format": FORMAT,
                "kurooto": __version__,
                "saved": now().isoformat(timespec="seconds"),
                "id": pysecrets.token_hex(8),  # this save: how a computer knows whether it's still its own
                "machine": st["machine"],
                "os": platform.system(),
                "key": kid,
                "parts": sums,
            },
        )
        files["manifest.json"] = json.dumps(man, indent=1) + "\n"
        repo.publish(files, f"profile: {man['saved'].replace('T', ' ')[:16]}", exists)
    record(
        app, saved=man["saved"], saved_id=man["id"], at=time.time(), ok=True, error="", held="", counts=counts(parts)
    )
    app.events.emit("profile_saved", **counts(parts))
    return True, "Saved your profile."


def _same_key(dek: bytes, keyfile: dict) -> bool:
    """Does this data key belong to that key.json? (Its parts were sealed with it; checked by sealing a probe.)"""
    probe = keyfile.get("probe")
    if not probe:
        return True  # older key files: the parts' own checks catch a wrong key
    try:
        unseal(dek, str(keyfile["id"]), "probe", probe)
        return True
    except Damaged:
        return False


def add_probe(dek: bytes, keyfile: dict) -> dict:
    return {**keyfile, "probe": seal(dek, str(keyfile["id"]), "probe", b"kurooto")}


def _json(text: str | None):
    if text is None:
        return None
    try:
        return json.loads(text)
    except ValueError:
        raise Damaged("a file in your profile isn't readable") from None


def _when(iso) -> str:
    try:
        return dt.datetime.fromisoformat(str(iso)).strftime("%a %d %b %H:%M")
    except ValueError:
        return "earlier"


# ------------------------------------------------------------------------------------------------ connecting
def connect(app, passphrase: str, again: str | None = None, progress=print) -> tuple[bool, str]:
    """Start keeping a profile in the repository profile.repo (or Notes sync's) now names. If one is there already
    the passphrase must open it, and this computer won't overwrite it until you restore it or save over it."""
    check_passphrase(passphrase, again)
    ensure_git(app, progress)
    url, token, branch = target(app)
    with Lock(app.paths.state, "profile", timeout=60):
        repo = Repo(app, url, token, branch)
        exists = repo.fetch()
        keyfile = _json(repo.read("key.json")) if exists else None
    if isinstance(keyfile, dict):
        try:
            dek = unlock(keyfile, passphrase)
        except WrongPassphrase:
            raise WrongPassphrase(
                "There's already a profile in that repository, and that passphrase doesn't open it."
            ) from None
        remember_key(app, dek, keyfile)
        raw = _json(repo.read("manifest.json"))
        man = verify(dek, str(keyfile["id"]), raw) if raw is not None else {}
        st = local(app)
        if man.get("machine") and man["machine"] != st["machine"] and man.get("id") != st.get("saved_id"):
            record(app, held=man.get("saved"))
            return True, (
                f"Connected to the profile already there (saved {_when(man.get('saved'))} from another computer). "
                "To bring its settings here: kurooto profile restore. To replace it with this computer's: "
                "/profile save (the old one stays in the history)."
            )
        return save(app)
    dek, keyfile = new_key(passphrase)
    keyfile = add_probe(dek, keyfile)
    remember_key(app, dek, keyfile)
    ok, msg = save(app, force=True)
    return ok, ("Your profile is saved, encrypted, in your repository." if ok else msg)


# ------------------------------------------------------------------------------------------------- restoring
def fetch(app, url: str, token: str | None, branch: str, passphrase: str) -> tuple[bytes, dict, dict, dict]:
    """Read and check a profile: (data key, key.json, manifest, the three parts). Nothing is changed here."""
    with Lock(app.paths.state, "profile", timeout=60):
        repo = Repo(app, url, token, branch)
        if not repo.fetch():
            raise ProfileError("There's no Kurooto profile in that repository (it has no kurooto-profile branch).")
        keyfile = _json(repo.read("key.json"))
        if not isinstance(keyfile, dict):
            raise ProfileError("There's no Kurooto profile in that repository.")
        dek = unlock(keyfile, passphrase)
        kid = str(keyfile.get("id"))
        manifest = verify(dek, kid, _json(repo.read("manifest.json")))
        if int(manifest.get("format") or 0) > FORMAT:
            raise ProfileError("That profile was saved by a newer Kurooto: update this one first (kurooto update).")
        parts = {}
        for name in PARTS:
            env = _json(repo.read(f"{name}.enc"))
            if not isinstance(env, dict):
                raise Damaged(f"{name}.enc is missing from your profile")
            data = unseal(dek, kid, name, env)
            want = ((manifest.get("parts") or {}).get(name) or {}).get("mac", "")
            if not hmac.compare_digest(mac(dek, kid, data), str(want)):
                raise Damaged(f"{name}.enc in your profile isn't the one its manifest names (an older copy?)")
            parts[name] = json.loads(data)
    return dek, keyfile, manifest, parts


def _get(d: dict, dotted: str):
    cur = d
    for k in dotted.split("."):
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur


def _put(d: dict, dotted: str, value) -> None:
    keys = dotted.split(".")
    cur = d
    for k in keys[:-1]:
        if not isinstance(cur.get(k), dict):
            cur[k] = {}
        cur = cur[k]
    if value is None:
        cur.pop(keys[-1], None)
    else:
        cur[keys[-1]] = value


def _folder_here(value, dotted: str) -> bool:
    if not isinstance(value, str) or not value:
        return False
    p = Path(value).expanduser()
    if not p.is_absolute():
        return False
    return p.is_dir() or (dotted in ("you.workspace", "files.folder") and p.parent.is_dir())


def _write(target: Path, text: str, mode: int | None = None) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f"{target.name}.tmp{os.getpid()}")
    tmp.write_text(text, encoding="utf-8")
    if mode is not None and os.name != "nt":
        os.chmod(tmp, mode)
    os.replace(tmp, target)


def _keep_copy(app) -> Path:
    """What restoring replaces (settings and the kept state files, never keys) goes to data/profile/before-restore-*
    first; the last three are kept."""
    base = app.paths.data / "profile"
    d = base / f"before-restore-{now():%Y%m%d-%H%M%S}"
    d.mkdir(parents=True, exist_ok=True)
    if app.settings.file.exists():
        shutil.copy2(app.settings.file, d / "settings.json")
    roots = _roots(app)
    for top, pat in KEEP:
        b = roots[top] / PurePosixPath(pat).parent
        for f in b.glob(PurePosixPath(pat).name) if b.is_dir() else []:
            dst = d / top / f.relative_to(roots[top])
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dst)
    for old in sorted(base.glob("before-restore-*"))[:-3]:
        shutil.rmtree(old, ignore_errors=True)
    return d


def apply(app, parts: dict, progress=print, skip: set[str] | frozenset = frozenset()) -> dict:
    """Put a fetched profile in place on this computer, then turn its features on where they're ready. Kurooto's
    own files are replaced (a copy is kept first); nothing in your notes is touched. Returns the report."""
    report = {"notes": [], "on": [], "left": [], "counts": counts(parts)}
    report["kept_copy"] = str(_keep_copy(app))
    roots = _roots(app)

    # settings: the profile's on top of what's here; this computer's own folders and quirks stay this computer's
    cur = app.settings.user()
    got = parts.get("settings") if isinstance(parts.get("settings"), dict) else {}
    wanted = [x for x in report_wanted(parts) if x not in skip]
    new = merge(cur, got)
    _put(new, "modules.enabled", list(_get(cur, "modules.enabled") or []))
    for dotted in LOCAL:
        _put(new, dotted, _get(cur, dotted))
    for dotted in FOLDERS:
        v = _get(got, dotted)
        if v and not _folder_here(v, dotted):
            here = _get(cur, dotted)
            _put(new, dotted, here if _folder_here(here, dotted) else None)
            report["notes"].append(f"{dotted}: the folder {v} isn't on this computer, so it wasn't kept")
    jsave(app.settings.file, new)
    tz = _get(new, "you.timezone")
    if tz:
        try:
            app.scheduler.tz = ZoneInfo(tz)
        except (ValueError, KeyError, OSError):
            pass
    progress(f"Settings: {report['counts']['settings']} restored.")

    # passwords and keys
    sec = parts.get("secrets") if isinstance(parts.get("secrets"), dict) else {}
    n = 0
    for name, value in (sec.get("secrets") or {}).items():
        if isinstance(name, str) and isinstance(value, str) and value and name not in NEVER:
            app.secrets.set(name, value)
            n += 1
    allowed_secret_files = {f"{t}/{r}" for t, r in SECRET_FILES}
    for arc, text in (sec.get("files") or {}).items():
        if arc in allowed_secret_files and isinstance(text, str):
            top, _, rel = arc.partition("/")
            f = roots[top].joinpath(*rel.split("/"))
            for parent in reversed(f.relative_to(roots[top]).parents[:-1]):
                (roots[top] / parent).mkdir(parents=True, exist_ok=True)
                if os.name != "nt":
                    os.chmod(roots[top] / parent, 0o700)
            _write(f, text, mode=0o600)
            n += 1
    progress(f"Passwords and keys: {n} restored.")

    # the state worth keeping, and what you'd scheduled
    st = parts.get("state") if isinstance(parts.get("state"), dict) else {}
    files = 0
    for arc, text in (st.get("files") or {}).items():
        top, _, rel = str(arc).partition("/")
        if top in ("state", "data") and _allowed(top, rel) and isinstance(text, str):
            _write(roots[top].joinpath(*rel.split("/")), text)
            files += 1
    t = time.time()
    sched = 0
    for j in st.get("scheduled") or []:
        try:
            if not str(j["key"]).startswith(SCHEDULED) or float(j["at"]) <= t:
                continue
            app.scheduler.at(
                float(j["at"]),
                str(j["action"]),
                dict(j.get("payload") or {}),
                key=str(j["key"]),
                module=str(j.get("module") or ""),
                replace=False,
                grace_s=int(j.get("grace_s") or 12 * 3600),
                respect=str(j.get("respect") or "none"),
            )
            sched += 1
        except (KeyError, TypeError, ValueError):
            continue
    progress(f"Saved items: {files} restored; {sched} reminders, calls and alarms still to come.")
    report["notes"] += _old_computer_notes(new)

    # features: turned on in Kurooto's order where they're ready; the rest are listed for setting up here
    _features(app, wanted, report, progress)
    return report


def _old_computer_notes(settings: dict) -> list[str]:
    out = []
    on = set(_get(settings, "modules.enabled") or [])
    if _get(settings, "telegram.chat_id") or "telegram" in on:
        out.append(
            "Turn Kurooto off on your old computer (kurooto off): two computers can't share one Telegram bot or "
            "call line."
        )
    return out


def _features(app, wanted: list[str], report: dict, progress=print) -> None:
    from kurooto.app import met

    live = app._loop is not None  # inside the running assistant (the setup page); else a `kurooto` command
    done: set[str] = set()
    for _ in range(2):  # twice: turning on "Your add-ons" can bring new features with it
        first = "calls" if "telegram" not in wanted else ""  # the phone app's chat, before what needs somewhere to talk
        for mid in sorted(app.modules, key=lambda x: x != first):
            if mid not in wanted or mid in done:
                continue
            done.add(mid)
            m = app.modules[mid]
            if app.is_on(mid):
                report["on"].append(m.title)
                continue
            if live:
                ok, why = app.enable(mid)
            else:
                on = list(app.settings.get("modules.enabled") or [])
                missing = [r for r in m.requires if not met(r, on, m)]  # the phone app's chat stands in for Telegram
                if missing:
                    ok, why = False, "needs " + ", ".join(app.modules[r].title for r in missing if r in app.modules)
                else:
                    try:
                        ok, why = m.ready()
                    except Exception as e:
                        ok, why = False, f"{type(e).__name__}: {e}"[:200]
                    if ok:
                        app.settings.set("modules.enabled", [*on, mid])
            if ok:
                report["on"].append(m.title)
            else:
                report["left"].append(
                    {"id": mid, "title": m.title, "why": why or "not ready", "setup": hasattr(m, "setup")}
                )
    for mid in wanted:
        if mid not in done and mid not in app.modules:
            if not live and app.is_on("overlay"):  # an add-on: it loads with your add-ons when Kurooto starts
                app.settings.set("modules.enabled", [*(app.settings.get("modules.enabled") or []), mid])
                report["on"].append(mid)
            else:
                report["left"].append(
                    {"id": mid, "title": mid, "why": "not part of this Kurooto (an add-on of yours?)", "setup": False}
                )
    progress(f"On: {', '.join(report['on']) or 'nothing yet'}.")
    if report["left"]:
        progress("Not on yet: " + "; ".join(f"{x['title']} ({x['why']})" for x in report["left"]))


def restore(
    app,
    passphrase: str,
    *,
    repo: str = "",
    token: str = "",
    remote: str = "",
    branch: str = BRANCH,
    progress=print,
) -> dict:
    """Bring a profile to this computer: from `repo` (owner/name on GitHub, with `token`), or `remote` (any Git
    address; tests use a local one). Raises ProfileError (WrongPassphrase, Damaged) with nothing changed."""
    progress("Checking Git is here…")
    ensure_git(app, progress)
    repo, token = repo.strip(), token.strip()
    if remote:
        url = remote
    else:
        notes = app.modules.get("notes_sync")
        if not repo:
            raise ProfileError("Write the repository as owner/name, e.g. sam/notes.")
        if not token:
            token = app.secrets.get(TOKEN) or app.secrets.get("notes_sync.token") or ""
        ok, why = notes.check_repo(repo, token) if notes else (True, "")
        if not ok:
            raise ProfileError(why)
        url = f"https://github.com/{repo}.git"
    progress("Opening your profile…")
    dek, keyfile, manifest, parts = fetch(app, url, token or None, branch, passphrase)
    progress(f"Found your profile, saved {_when(manifest.get('saved'))} with Kurooto {manifest.get('kurooto', '?')}.")
    report = apply(app, parts, progress, skip={"profile"})

    # keep saving to the same place from here on (Profile sync itself is turned on last, once it has its key)
    s = app.settings
    if remote:
        s.set("profile.remote", remote)
    elif repo == (s.get("notes_sync.repo") or ""):
        s.set("profile.repo", "")
        app.secrets.set("notes_sync.token", token)  # the token that just worked; the saved one may be an old one
    else:
        s.set("profile.repo", repo)
        app.secrets.set(TOKEN, token)
    if branch != BRANCH:
        s.set("profile.branch", branch)
    remember_key(app, dek, keyfile)
    record(
        app,
        saved=manifest.get("saved"),
        saved_id=manifest.get("id"),
        held="",
        restored=time.time(),
        wanted=report_wanted(parts),
    )
    if not app.is_on("profile"):
        if app._loop is not None:
            ok, why = app.enable("profile")
            if not ok:
                report["notes"].append(f"Profile sync isn't on yet: {why}")
        else:
            s.set("modules.enabled", [*(s.get("modules.enabled") or []), "profile"])

    # your notes come back with Notes sync
    notes = app.modules.get("notes_sync")
    if notes and app.is_on("notes_sync") and not (app.workspace / ".git").exists():
        progress("Bringing your notes back from your repository…")
        try:
            ok, msg = notes.first_sync(progress)
        except Exception as e:
            ok, msg = False, f"{type(e).__name__}: {e}"[:300]
        progress(msg)
        if not ok:
            report["notes"].append(f"Notes sync: {msg}")
    report["brain"] = _brain(app)
    app.events.emit("profile_restored", **report["counts"], left=len(report["left"]))
    record(app, report=report)
    return report


def report_wanted(parts: dict) -> list[str]:
    return [str(x) for x in (_get(parts.get("settings") or {}, "modules.enabled") or []) if isinstance(x, str)]


def _brain(app) -> dict:
    """The AI you used: is it ready here? (Agent programs need installing and signing in again on a new computer.)"""
    from kurooto import providers

    main = app.settings.get("brain.main") or ""
    if not main:
        return {"main": "", "label": "", "ready": False, "why": "none picked"}
    try:
        b = providers.build(app, main)
        ok, why = b.available() if b else (False, "unknown")
    except Exception as e:
        ok, why = False, f"{type(e).__name__}: {e}"[:200]
    return {"main": main, "label": providers.label(main, main), "ready": bool(ok), "why": why or ""}


def status(app) -> dict:
    """What `kurooto profile status`, /profile and the dashboard show."""
    st = jload(state_file(app), {}) or {}
    try:
        url, _, branch = target(app)
        where = app.settings.get("profile.repo") or (
            "the repository Notes sync uses" if not app.settings.get("profile.remote") else url
        )
    except ProfileError as e:
        where, branch = f"not set: {e}", BRANCH
    return {
        "on": app.is_on("profile"),
        "where": where,
        "branch": branch,
        "has_key": bool(cached_key(app)),
        "saved": st.get("saved"),
        "at": st.get("at"),
        "ok": st.get("ok", True),
        "error": st.get("error", ""),
        "held": st.get("held", ""),
        "counts": st.get("counts") or {},
        "restored": st.get("restored"),
        "report": st.get("report"),
        "wanted": st.get("wanted") or [],
    }

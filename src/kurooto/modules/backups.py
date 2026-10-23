"""Backups: once a day, a zip of Kurooto's settings, data and state (and, if you want, your notes) in a folder you
pick: an external drive, or a folder your computer already syncs to a cloud (Google Drive, OneDrive, iCloud Drive,
Dropbox). The last few are kept (7 by default); older ones from Kurooto are removed.

It's heavy work, so on battery it waits for the charger. `/backup` makes one now; `kurooto restore <zip>` puts one
back (it stops Kurooto, restores, and starts it again).

Passwords and keys (your bot token, API keys, sign-ins) are left out unless you turn on backups.secrets: then
anyone who can open the zip can use them. The zip isn't encrypted. Your notes are left out unless you turn on
backups.notes; when a zip with notes is restored, a note that's missing is put back, and one that's different now is
never overwritten: the backup's copy goes to restored-<date>/ in your notes folder instead.
"""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import sqlite3
import sys
import tempfile
import threading
import time
import zipfile
from pathlib import Path, PurePosixPath

from kurooto import __version__
from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.lock import Lock, Timeout
from kurooto.core.state import jload, jsave
from kurooto.modules.base import Command, Incoming, Module

register_defaults(
    "backups",
    {
        "folder": "",  # where the zips go: an external drive or a cloud-synced folder
        "when": "daily 03:30",
        "keep": 7,  # how many zips to keep
        "notes": False,  # also your notes folder
        "secrets": False,  # also passwords and keys (bot token, API keys, sign-ins): anyone with the zip can use them
        "index": True,  # also the notes brain's index (big, but slow to rebuild)
        "confidential_mail": False,  # also confidential mail summarised on this computer (Mail digest's local mode)
        "memory": False,  # also the memory ledger (encrypted: it opens only where its key is, see backups.secrets)
    },
)
CLAUDE_ACCOUNTS = (
    "claude-accounts"  # in the data folder: extra Claude accounts' sign-ins (providers/claude_accounts.py)
)
CONFIDENTIAL = ("mail", "confidential")  # in the data folder: only with backups.confidential_mail
PREFIX = "kurooto-backup-"
NAME = re.compile(r"kurooto-backup-(\d{8}-\d{6})\.zip")
# state that only means something to the program that wrote it (and must not come back from an older copy)
SKIP_STATE = {
    "web.json",
    "daemon.json",
    "supervisor.json",
    "off.json",
    "pause.json",
    "power-held.json",
    "update-ready.json",
    "backups.json",
    "focus-queue.jsonl",
    "profile.json",  # this computer's own id for the encrypted profile: it mustn't move to another computer
}
SKIP_STATE_DIRS = {"locks", "logs", "cases"}  # cases: what you typed, kept on this computer only
SKIP_STATE_FILES = {
    ("telegram", "offset.json"),
    ("telegram", "pairing.json"),
    ("calls", "link.json"),
    *(("learning", f"history.db{x}") for x in ("", "-wal", "-shm")),  # the search index: built again from the rest
}
LEDGER = {f"ledger.db{x}" for x in ("", "-wal", "-shm")}  # the memory ledger (core/ledger.py): only with backups.memory
SKIP_NOTES_DIRS = {".git", ".trash", "node_modules", ".obsidian"}
TOPS = ("config", "data", "state", "notes")
SAFETY = "restore-safety"  # in the data folder: what was there before the last restore
README = """A backup of Kurooto (made {when}, Kurooto {version}).

To put it back: kurooto restore "<this zip>"
It stops Kurooto, restores its settings and data, and starts it again. Your notes (if this zip has them) are only
added where missing; a note that's different now is kept, and the backup's copy goes to restored-<date>/.
{secrets}
"""


# ---------------------------------------------------------------------------------------------- what goes in
def known_secret_names(secrets) -> list[str]:
    from kurooto.diagnostics import KNOWN_SECRETS

    return sorted(set(secrets.names()) | set(KNOWN_SECRETS))


def sources(
    p,
    workspace: Path | None,
    *,
    notes: bool,
    secrets: bool,
    index: bool,
    skip: Path | None = None,
    confidential: bool = False,
    memory: bool = False,
):
    """(name in the zip, file) for everything a backup holds. `skip`: a folder never to read (the backups' own)."""
    skip = skip.resolve() if skip else None

    def walk(root: Path, top: str, keep_dir=lambda parts: True, keep_file=lambda parts: True):
        root = Path(root)
        if not root.is_dir():
            return
        for dirpath, dirs, files in os.walk(root):
            d = Path(dirpath)
            if skip and (d.resolve() == skip or skip in d.resolve().parents):
                dirs[:] = []
                continue
            rel = d.relative_to(root).parts
            dirs[:] = [x for x in sorted(dirs) if keep_dir((*rel, x))]
            for f in sorted(files):
                parts = (*rel, f)
                if ".tmp" in f or f.endswith((".part", "-wal", "-shm", "-journal")) or not keep_file(parts):
                    continue
                yield "/".join((top, *parts)), d / f

    # settings: settings.json and the other files beside it; never the secrets file (they go in separately, if at
    # all) and never its folders (a sign-in lives in config/cloudflare) unless secrets are wanted
    yield from walk(
        p.config,
        "config",
        keep_dir=lambda parts: secrets,
        keep_file=lambda parts: parts[-1] != "secrets.json",
    )
    yield from walk(
        p.data,
        "data",
        keep_dir=lambda parts: (
            parts[0] != SAFETY
            and (secrets or parts[0] != CLAUDE_ACCOUNTS)  # extra Claude accounts' sign-ins: only with secrets
            and (index or parts[0] != "gbrain")
            and (confidential or tuple(parts[:2]) != CONFIDENTIAL)
        ),
        keep_file=lambda parts: not (len(parts) == 1 and parts[0].startswith(("kurooto-diagnostics-", "restore-"))),
    )
    yield from walk(
        p.state,
        "state",
        keep_dir=lambda parts: not (len(parts) == 1 and parts[0] in SKIP_STATE_DIRS),
        keep_file=lambda parts: (
            not (len(parts) == 1 and parts[0] in SKIP_STATE)
            and tuple(parts) not in SKIP_STATE_FILES
            and (memory or not (len(parts) == 1 and parts[0] in LEDGER))
        ),
    )
    if notes and workspace:
        yield from walk(
            workspace,
            "notes",
            keep_dir=lambda parts: parts[-1] not in SKIP_NOTES_DIRS,
            keep_file=lambda parts: parts[-1] not in (".DS_Store", "Thumbs.db", "desktop.ini"),
        )


def _sqlite_copy(src: Path, dst: Path) -> None:
    """A consistent copy of a database another program may be writing to (the sqlite backup API, not a file copy),
    as one self-contained file: everything in its write-ahead log is in it, and it uses a plain rollback journal, so
    a restore never needs (or replays) a -wal file."""
    a = sqlite3.connect(f"file:{src.as_posix()}?mode=ro", uri=True)
    try:
        b = sqlite3.connect(dst)
        with b:
            a.backup(b)
        b.execute("pragma journal_mode=delete")
        b.close()
    finally:
        a.close()


JOURNALS = ("-wal", "-shm", "-journal")


def _retry(fn, *args, attempts: int = 12):
    """Windows: a file someone has open (an antivirus scan, a cloud app, a program just stopping) can't be replaced
    or removed for a moment; try again briefly before giving up."""
    for i in range(attempts):
        try:
            return fn(*args)
        except PermissionError:
            if i == attempts - 1:
                raise
            time.sleep(0.1 * (i + 1))


def _in_use(files: list[Path]) -> list[Path]:
    """The files another program holds open so they can't be replaced (Windows locks open files; elsewhere nothing
    is reported). Checked by renaming each one away and back."""
    busy = []
    for f in files:
        if not f.exists():
            continue
        probe = f.with_name(f"{f.name}.restore-check")
        try:
            _retry(os.replace, f, probe, attempts=6)
        except OSError:
            busy.append(f)
            continue
        _retry(os.replace, probe, f)
    return busy


def make_zip(
    p,
    folder: Path,
    workspace: Path | None,
    *,
    notes: bool = False,
    secrets=None,
    index: bool = True,
    name: str | None = None,
    lock_dir: Path | None = None,
    confidential: bool = False,
    memory: bool = False,
) -> tuple[Path, dict]:
    """Write one backup zip into `folder`. `secrets`: a Secrets object to include them, else None. Returns (the
    zip, its manifest)."""
    folder = Path(folder)
    stamp = now().strftime("%Y%m%d-%H%M%S")
    name = name or f"{PREFIX}{stamp}.zip"
    files = list(
        sources(
            p,
            workspace,
            notes=notes,
            secrets=bool(secrets),
            index=index,
            skip=folder,
            confidential=confidential,
            memory=memory,
        )
    )
    total = 0
    for _, f in files:
        try:
            total += f.stat().st_size
        except OSError:
            pass
    free = shutil.disk_usage(folder).free
    if free < total * 1.1 + 50 * 1024**2:
        raise OSError(
            f"not enough room in the backup folder ({free / 1024**2:.0f} MB free, needs up to {total / 1024**2:.0f} MB)"
        )
    part = folder / f".{name}.part"
    skipped: list[str] = []
    counts = {t: 0 for t in TOPS}
    index_files = [(a, f) for a, f in files if a.startswith("data/gbrain/")]
    files = [(a, f) for a, f in files if not a.startswith("data/gbrain/")]
    try:
        with (
            zipfile.ZipFile(part, "w", zipfile.ZIP_DEFLATED, compresslevel=6, strict_timestamps=False) as z,
            tempfile.TemporaryDirectory() as tmp,
        ):

            def add(arc: str, f: Path) -> None:
                try:
                    if f.suffix == ".db" and _is_sqlite(f):
                        snap = Path(tmp) / "snap.db"
                        snap.unlink(missing_ok=True)
                        _sqlite_copy(f, snap)
                        z.write(snap, arc)
                    else:
                        z.write(f, arc)
                    counts[arc.split("/", 1)[0]] += 1
                except (OSError, ValueError, sqlite3.Error):
                    skipped.append(arc)

            for arc, f in files:
                add(arc, f)
            if index_files:
                try:  # the notes brain's database allows one writer: copy it while nobody writes
                    with Lock(lock_dir or p.state, "gbrain", timeout=600):
                        for arc, f in index_files:
                            add(arc, f)
                except Timeout:
                    skipped.append("data/gbrain/ (busy)")
            has_secrets = False
            if secrets is not None:
                values = {n: v for n in known_secret_names(secrets) if (v := secrets.get(n))}
                z.writestr("secrets.json", json.dumps(values, indent=1))
                has_secrets = bool(values)
            manifest = {
                "kurooto": __version__,
                "created": now().isoformat(),
                "os": platform.system(),
                "files": counts,
                "notes": notes,
                "secrets": has_secrets,
                "index": index,
                "skipped": skipped[:50],
            }
            z.writestr("manifest.json", json.dumps(manifest, indent=1))
            warn = (
                "THIS ZIP HOLDS YOUR PASSWORDS AND KEYS (secrets.json): keep it private."
                if has_secrets
                else "Passwords and keys aren't in it: after a restore, sign in again where Kurooto asks."
            )
            z.writestr("README.txt", README.format(when=manifest["created"], version=__version__, secrets=warn))
        dest = folder / name
        _retry(os.replace, part, dest)
    except BaseException:
        part.unlink(missing_ok=True)
        raise
    return dest, manifest


def _is_sqlite(f: Path) -> bool:
    try:
        with open(f, "rb") as fh:
            return fh.read(16) == b"SQLite format 3\x00"
    except OSError:
        return False


def listing(folder: Path) -> list[Path]:
    """Kurooto's zips in that folder, oldest first."""
    try:
        return sorted(f for f in Path(folder).iterdir() if NAME.fullmatch(f.name))
    except OSError:
        return []


def prune(folder: Path, keep: int) -> list[str]:
    """Remove Kurooto's own older zips beyond the newest `keep` (nothing else in the folder is touched)."""
    old = listing(folder)[: -max(1, int(keep))]
    gone = []
    for f in old:
        try:
            f.unlink()
            gone.append(f.name)
        except OSError:
            pass
    for f in Path(folder).glob(f".{PREFIX}*.zip.part"):  # a backup cut off by a shutdown
        try:
            if time.time() - f.stat().st_mtime > 86400:
                f.unlink()
        except OSError:
            pass
    return gone


def suggest_folders(home: Path | None = None, env: dict | None = None) -> list[tuple[str, str]]:
    """Folders on this computer a backup could go to: cloud-synced folders and external drives that exist now."""
    home = Path(home or Path.home())
    env = os.environ if env is None else env
    out: list[tuple[str, str]] = []

    def add(label: str, path: Path | str | None) -> None:
        if path and Path(path).is_dir() and str(path) not in [p for _, p in out]:
            out.append((label, str(path)))

    for var in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
        add("OneDrive", env.get(var))
    for d in sorted(home.glob("OneDrive*")):
        add("OneDrive", d)
    cloud = home / "Library" / "CloudStorage"
    if cloud.is_dir():
        for d in sorted(cloud.iterdir()):
            label = "Google Drive" if d.name.startswith("GoogleDrive") else d.name.split("-")[0]
            add(label, d / "My Drive" if (d / "My Drive").is_dir() else d)
    add("iCloud Drive", home / "Library" / "Mobile Documents" / "com~apple~CloudDocs")
    add("Google Drive", home / "Google Drive" / "My Drive")
    add("Google Drive", home / "Google Drive")
    add("Dropbox", home / "Dropbox")
    if sys.platform == "win32":
        for letter in "DEFGHIJKLMNOPQRSTUVWXYZ":
            add("Google Drive", f"{letter}:\\My Drive")
    try:
        import psutil

        for part in psutil.disk_partitions(all=False):
            mp = part.mountpoint
            removable = "removable" in (part.opts or "")
            external = mp.startswith(("/media/", "/run/media/", "/Volumes/")) and mp != "/Volumes/Macintosh HD"
            if removable or external:
                add("External drive", mp)
    except Exception:
        pass
    return out


def backup_now(p, settings, secrets, workspace: Path, folder: Path | None = None, reason: str = "now"):
    """One backup with these settings (to `folder`, else backups.folder), the old ones pruned and the result
    recorded for `kurooto doctor`. Returns (ok, message). Used by the feature and by `kurooto backup`."""
    from kurooto.core.events import Events

    def get(k, d=None):
        v = settings.get(f"backups.{k}")
        return d if v is None else v

    state_file = p.state / "backups.json"
    target = Path(folder or get("folder") or "").expanduser() if (folder or get("folder")) else None
    if target is None or not target.is_dir():
        return False, ("pick a folder for the backups first" if target is None else f"there's no folder {target}")
    try:
        with Lock(p.state, "backups", timeout=0):
            started = time.monotonic()
            dest, man = make_zip(
                p,
                target,
                workspace,
                notes=bool(get("notes", False)),
                secrets=secrets if get("secrets", False) else None,
                index=bool(get("index", True)),
                confidential=bool(get("confidential_mail", False)),
                memory=bool(get("memory", False)),
            )
            gone = prune(target, int(get("keep", 7) or 7)) if folder is None else []
    except Timeout:
        return False, "a backup is already running"
    size = dest.stat().st_size
    prev = jload(state_file, {}) or {}
    jsave(
        state_file,
        {
            "ok": True,
            "at": time.time(),
            "file": dest.name,
            "folder": str(target),
            "size": size,
            "seconds": round(time.monotonic() - started, 1),
            "notes": man["notes"],
            "secrets": man["secrets"],
            "skipped": len(man["skipped"]),
            "error": "",
            "told": prev.get("told", 0),
        },
    )
    Events(p.state).emit("backup_done", size=size, removed=len(gone), skipped=len(man["skipped"]), reason=reason)
    extra = f"; {len(man['skipped'])} files couldn't be read" if man["skipped"] else ""
    return True, f"Backed up: {dest} ({_mb(size)}){extra}."


# ------------------------------------------------------------------------------------------------- restoring
def read_manifest(zip_path: Path) -> dict:
    """The backup's manifest, after checking every name in it is one a restore may write. Raises ValueError."""
    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        for n in names:
            pp = PurePosixPath(n)
            if (
                n.startswith(("/", "\\"))
                or "\\" in n
                or ".." in pp.parts
                or re.match(r"^[A-Za-z]:", n)
                or (pp.parts[0] not in TOPS and n not in ("manifest.json", "secrets.json", "README.txt"))
            ):
                raise ValueError(f"unexpected entry in the zip: {n[:80]}")
        if "manifest.json" not in names:
            raise ValueError("that isn't a Kurooto backup (no manifest.json)")
        m = json.loads(z.read("manifest.json"))
        m["has_secrets"] = "secrets.json" in names
        m["has_notes"] = any(n.startswith("notes/") for n in names)
        return m


def _write(target: Path, data: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f"{target.name}.tmp{os.getpid()}")
    tmp.write_bytes(data)
    try:
        _retry(os.replace, tmp, target)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise


class InUse(RuntimeError):
    """Kurooto (or another program) still has some of its files open: nothing was restored."""


def restore(zip_path: Path, p, *, secrets=None, notes: bool = True, progress=print) -> dict:
    """Put a backup back: Kurooto's own files are replaced; notes are only added (see the module's docstring).
    Kurooto must not be running. Returns counts."""
    from kurooto.app import default_workspace
    from kurooto.core.config import Settings
    from kurooto.core.proc import pid_alive

    read_manifest(zip_path)
    pid = (jload(p.state / "daemon.json", {}) or {}).get("pid")
    if pid and pid_alive(pid, "kurooto"):
        raise InUse("Kurooto is running; stop it first (kurooto restore does that for you)")
    out = {"files": 0, "secrets": 0, "notes_added": 0, "notes_kept": 0, "notes_same": 0, "workspace": ""}
    stamp = now().strftime("%Y-%m-%d")
    with zipfile.ZipFile(zip_path) as z:
        roots = {"config": p.config, "data": p.data, "state": p.state}
        todo = []
        for info in z.infolist():
            top, _, rest = info.filename.partition("/")
            if info.is_dir() or top not in roots or not rest or rest.endswith(JOURNALS):
                continue  # (a database's journal is never restored: the backup's copy is self-contained)
            todo.append((info, roots[top].joinpath(*rest.split("/"))))
        dbs = [t for _, t in todo if t.suffix == ".db"]
        busy = _in_use([*dbs, *(Path(f"{t}{j}") for t in dbs for j in JOURNALS)])
        if busy:  # before anything changes: a half-restored Kurooto would be worse than none
            raise InUse(
                f"{busy[0].name} is still open in another program (is Kurooto still running?); nothing was changed"
            )
        for info, target in todo:
            if target.suffix == ".db":  # the old database's journal must not be replayed into the restored one
                for j in JOURNALS:
                    _retry(Path(f"{target}{j}").unlink, True)
            _write(target, z.read(info))
            out["files"] += 1
        progress(f"Restored {out['files']} files of Kurooto's settings and data.")
        if secrets is not None and "secrets.json" in z.namelist():
            for k, v in json.loads(z.read("secrets.json")).items():
                if isinstance(v, str) and v:
                    secrets.set(k, v)
                    out["secrets"] += 1
            progress(f"Restored {out['secrets']} passwords and keys.")
        settings = Settings(p.config / "settings.json")
        ws = settings.get("you.workspace") or ""
        if ws and not (Path(ws).is_absolute() and Path(Path(ws).anchor).exists()):
            settings.set("you.workspace", "")  # a folder from another kind of computer: use the default here
            progress(f"The notes folder in that backup ({ws}) doesn't exist on this computer; using the default.")
            ws = ""
        workspace = Path(ws) if ws else default_workspace()
        out["workspace"] = str(workspace)
        if notes:
            for info in z.infolist():
                if info.is_dir() or not info.filename.startswith("notes/"):
                    continue
                rel = info.filename[len("notes/") :].split("/")
                target = workspace.joinpath(*rel)
                data = z.read(info)
                if not target.exists():
                    _write(target, data)
                    out["notes_added"] += 1
                elif target.read_bytes() == data:
                    out["notes_same"] += 1
                else:  # yours now is kept; the backup's copy goes beside it, in its own folder
                    _write(workspace.joinpath(f"restored-{stamp}", *rel), data)
                    out["notes_kept"] += 1
            if out["notes_added"] or out["notes_kept"]:
                progress(
                    f"Notes: {out['notes_added']} put back, {out['notes_same']} unchanged, {out['notes_kept']} "
                    f"different now (yours kept; the backup's copies are in restored-{stamp}/)."
                )
    return out


# ------------------------------------------------------------------------------------------------- the module
class Backups(Module):
    id = "backups"
    title = "Backups"
    heavy = True  # waits for the charger on battery (saver mode, core/power.py)
    description = (
        "A zip of Kurooto's settings and data every day (your notes too, if you want) in a folder you pick: an "
        "external drive or a cloud-synced folder."
    )
    privacy = (
        "The zip goes only to the folder you pick; if that folder syncs to a cloud (Google Drive, OneDrive, iCloud, "
        "Dropbox), it goes there too. It isn't encrypted. Passwords and keys are left out unless you turn them on."
    )

    def __init__(self, app):
        super().__init__(app)
        self.state_file = app.paths.state / "backups.json"
        self._running = threading.Lock()

    def folder(self) -> Path | None:
        f = self.setting("folder")
        return Path(f).expanduser() if f else None

    def ready(self):
        f = self.folder()
        if not f:
            return False, "pick a folder for the backups (Set up)"
        if not f.is_dir():
            return False, f"the backup folder isn't there ({f}); is the drive plugged in?"
        return True, ""

    def start(self):
        self.every("run", self.setting("when") or "daily 03:30", lambda p: self.backup("scheduled"))
        self.every("catchup", "hourly", lambda p: self.catch_up())

    def catch_up(self) -> tuple[bool, str] | None:
        """A day without a backup (the drive was unplugged, the laptop was off): make one as soon as it can."""
        st = self.last()
        if time.time() - (st.get("at") or 0) < 26 * 3600 or not self.ready()[0]:
            return None
        return self.backup("catch-up")

    # ---------------------------------------------------------------------------------------- doing it
    def backup(self, reason: str = "now") -> tuple[bool, str]:
        st = jload(self.state_file, {}) or {}
        if reason == "scheduled" and st.get("ok") and time.time() - st.get("at", 0) < 12 * 3600:
            return True, "a recent backup is still fresh"
        ok, why = self.ready()
        if not ok:  # an unplugged drive is normal for a day or two: only nag when it's been a while
            return self._fail(why, nag=time.time() - (st.get("at") or 0) > 3 * 86400)
        if not self._running.acquire(blocking=False):
            return False, "a backup is already running"
        try:
            ok, text = backup_now(
                self.app.paths, self.app.settings, self.app.secrets, self.app.workspace, reason=reason
            )
        except Exception as e:
            return self._fail(f"{type(e).__name__}: {e}"[:300])
        finally:
            self._running.release()
        if not ok and "already running" in text:
            return False, text
        return (True, text) if ok else self._fail(text)

    def _fail(self, why: str, nag: bool = True) -> tuple[bool, str]:
        prev = jload(self.state_file, {}) or {}
        rec = {**prev, "ok": False, "failed_at": time.time(), "error": why}
        if nag and time.time() - prev.get("told", 0) > 20 * 3600:  # at most once a day
            self.app.notify(f"Backup didn't work: {why}", kind="info", why="backups.failed")
            rec["told"] = time.time()
        jsave(self.state_file, rec)
        self.app.events.emit("backup_failed", error=why[:200])
        return False, why

    def last(self) -> dict:
        return jload(self.state_file, {}) or {}

    def health(self):
        st = self.last()
        age = time.time() - st["at"] if st.get("at") else None
        last = f"last backup {_ago(age)} ago" if age is not None else "no backup yet"
        f = self.folder()
        if not f:
            return False, "pick a folder for the backups (Set up)"
        if not f.is_dir():  # an external drive that isn't plugged in now
            gone = f"the backup folder isn't there now ({f}); {last}"
            return (None, gone) if age is not None and age < 3 * 86400 else (False, gone)
        if st.get("error") and not st.get("ok"):
            return False, f"the last backup failed: {st['error']}"
        if age is None:
            return None, "no backup yet (the first one runs tonight on the charger, or /backup now)"
        detail = f"{last} ({_mb(st.get('size', 0))})"
        if st.get("secrets"):
            detail += ", with passwords and keys"
        if age > 3 * 86400:
            return False, detail + "; it runs on the charger, so plug the laptop in for a while"
        return True, detail

    # ----------------------------------------------------------------------------------------- telegram
    def commands(self):
        return [
            Command("backup", "make a backup now", self._cmd_backup),
            Command("backups", "the backups you have, and where", self._cmd_list),
        ]

    def _cmd_backup(self, msg: Incoming, arg: str) -> str:
        def work():
            ok, text = self.backup("now")
            self.app.notify(text if ok else f"Backup didn't work: {text}", kind="result", why="asked")

        threading.Thread(target=work, name="backup", daemon=True).start()
        return "Backing up now; I'll tell you when it's done."

    def _cmd_list(self, msg: Incoming, arg: str) -> str:
        f = self.folder()
        zips = listing(f) if f else []
        if not zips:
            return f"No backups yet in {f}." if f else "Backups aren't set up: pick a folder (dashboard → Features)."
        rows = []
        for z in reversed(zips[-10:]):
            try:
                rows.append(f"• {z.name} ({_mb(z.stat().st_size)})")
            except OSError:
                continue
        extras = [
            w for w, on in (("notes", self.setting("notes")), ("passwords and keys", self.setting("secrets"))) if on
        ]
        what = "settings and data" + "".join(f", {w}" for w in extras)
        return f"Backups in {f} ({what}; keeping {self.setting('keep')}):\n" + "\n".join(rows)

    # ------------------------------------------------------------------------------------------- setup
    def setup_form(self) -> dict:
        found = suggest_folders()
        hint = (
            " Found on this computer: " + "; ".join(f"{label}: {path}" for label, path in found[:5]) + "."
            if found
            else ""
        )
        return {
            "intro": "Pick the folder the daily backup goes to: a folder on an external drive, or one your computer "
            "syncs to a cloud (Google Drive, OneDrive, iCloud Drive, Dropbox). Paste its full path. Your notes and "
            "your passwords and keys are left out; turn on backups.notes or backups.secrets in Settings to add them "
            "(anyone with a zip that has your keys can use them). Only for a computer that's yours alone." + hint,
            "links": [],
            "fields": [
                {
                    "name": "folder",
                    "label": "Backup folder",
                    "type": "text",
                    "placeholder": found[0][1] if found else "e.g. a folder on your external drive",
                },
            ],
        }

    def configure(self, values: dict) -> dict:
        raw = str(values.get("folder", "")).strip().strip('"')
        if not raw:
            return {"ok": False, "message": "Paste the folder's full path."}
        f = Path(raw).expanduser()
        if not f.is_absolute():
            return {"ok": False, "message": "That needs the full path, starting from the drive."}
        if not f.is_dir():
            return {"ok": False, "message": f"There's no folder {f}. Make it first (or plug the drive in)."}
        ws = self.app.workspace.resolve()
        if f.resolve() == ws or ws in f.resolve().parents:
            return {"ok": False, "message": "Pick a folder outside your notes folder."}
        try:
            with tempfile.NamedTemporaryFile(dir=f):
                pass
        except OSError:
            return {"ok": False, "message": f"Kurooto can't write to {f}."}
        self.app.settings.set("backups.folder", str(f))
        if self.app.is_on(self.id):
            self.start()
        return {"ok": True, "message": f"Backups go to {f}."}


def _mb(n: float) -> str:
    return f"{n / 1024**2:.1f} MB" if n >= 1024**2 else f"{max(1, round(n / 1024))} KB"


def _ago(seconds: float) -> str:
    if seconds < 3600:
        return f"{max(1, int(seconds // 60))} min"
    if seconds < 2 * 86400:
        return f"{int(seconds // 3600)} h"
    return f"{int(seconds // 86400)} days"


def age_line(p) -> tuple[bool | None, str]:
    """For `kurooto doctor` when the module is off: a note, not a problem."""
    st = jload(p.state / "backups.json", {}) or {}
    if st.get("at"):
        return None, f"off; the last backup was {_ago(time.time() - st['at'])} ago"
    return None, "off: nothing is backed up (Features → Backups)"

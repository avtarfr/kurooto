"""Keeping Kurooto's own footprint small: what it has piled up, and what can go without anyone missing it.

Only Kurooto's own leftovers are ever touched, never your notes, your files, your books or anything in a folder you
chose except Kurooto's own backup zips there:

    backups          more zips than backups.keep, or more than space.backups_max_gb in total, or older than
                     space.backups_max_age_days: the oldest go first, and the newest is never removed
    cache            installer downloads, the zips made to send you a study pack or files, and cut-off downloads, once
                     they're older than space.cache_days (they're made again when needed)
    logs             a log file past space.log_mb is cut to its newest part
    jobs             finished AI requests older than space.jobs_days (their answers were delivered long ago)
    pending          unfinished work files of the concept graph and its before-copies, once they're older than
                     space.undo_days
    diagnostics      help bundles (kurooto-diagnostics-*) and restore leftovers older than space.cache_days
    versions         program versions beyond the ones kept for going back (updates already keep three)

`plan(app)` says what would go and how much it frees; `clean(app, plan)` does it. Both are plain functions, run weekly
by the Space keeper feature, by `kurooto space`, by /space, and by `kurooto doctor` (which only reports).
"""

from __future__ import annotations

import os
import re
import shutil
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto.core.config import register_defaults

if TYPE_CHECKING:
    from kurooto.app import App

register_defaults(
    "space",
    {
        "backups_max_gb": 3.0,  # the most the backup zips may take in total (0: no limit)
        "backups_max_age_days": 0,  # zips older than this go (0: no limit; backups.keep still applies)
        "cache_days": 14,  # downloads, made zips and cut-off downloads older than this go
        "log_mb": 20,  # a log file bigger than this is cut to its newest part
        "jobs_days": 60,  # finished AI requests older than this are forgotten
        "undo_days": 30,  # the concept graph's before-copies and unfinished work files older than this go
        "when": "weekly sun 04:30",  # when the Space keeper cleans by itself
    },
)
GB = 1024**3
MB = 1024**2
DIAG = re.compile(r"^(kurooto-diagnostics-.*|restore-.*)$")


@dataclass
class Item:
    kind: str  # backups | cache | logs | jobs | pending | diagnostics | versions
    what: str  # a plain sentence
    bytes: int
    paths: list[Path] = field(default_factory=list)
    cut_to: int = 0  # for a log: keep this many bytes from the end
    sql: str = ""  # for jobs: the cutoff time


def size(p: Path) -> int:
    try:
        if p.is_file() or p.is_symlink():
            return p.lstat().st_size
        return sum(f.lstat().st_size for f in p.rglob("*") if f.is_file() and not f.is_symlink())
    except OSError:
        return 0


def older(p: Path, days: float, now: float | None = None) -> bool:
    try:
        return (now or time.time()) - p.stat().st_mtime > days * 86400
    except OSError:
        return False


def human(n: int) -> str:
    for unit, div in (("GB", GB), ("MB", MB), ("KB", 1024)):
        if n >= div:
            return f"{n / div:.1f} {unit}"
    return f"{n} B"


def backup_items(app: App, now: float) -> list[Item]:
    from kurooto.modules import backups

    mod = app.modules.get("backups")
    folder = mod.folder() if mod is not None else None
    if folder is None or not Path(folder).is_dir():
        return []
    zips = backups.listing(folder)  # oldest first
    s = app.settings
    keep = max(1, int(s.get("backups.keep") or 7))
    max_gb = float(s.get("space.backups_max_gb") or 0)
    max_age = float(s.get("space.backups_max_age_days") or 0)
    doomed: dict[Path, str] = {}
    for f in zips[:-keep]:
        doomed[f] = f"more than the {keep} you keep"
    left = [f for f in zips if f not in doomed]
    if max_age:
        for f in left[:-1]:
            if older(f, max_age, now):
                doomed[f] = f"older than {max_age:g} days"
    left = [f for f in zips if f not in doomed]
    if max_gb:
        total = sum(size(f) for f in left)
        for f in left[:-1]:  # never the newest
            if total <= max_gb * GB:
                break
            doomed[f] = f"the zips together passed {max_gb:g} GB"
            total -= size(f)
    if not doomed:
        return []
    by_reason: dict[str, list[Path]] = {}
    for f, why in doomed.items():
        by_reason.setdefault(why, []).append(f)
    return [
        Item("backups", f"{len(fs)} old backup zip{'s' if len(fs) != 1 else ''} ({why})", sum(size(f) for f in fs), fs)
        for why, fs in by_reason.items()
    ]


def cache_items(app: App, now: float) -> list[Item]:
    days = float(app.settings.get("space.cache_days") or 14)
    out: list[Item] = []
    cache = Path(app.paths.cache)
    for sub, what in (
        ("downloads", "installer downloads"),
        ("study-packs", "study-pack zips"),
        ("send", "zips made to send you files"),
    ):
        d = cache / sub
        old = [p for p in d.iterdir() if older(p, days, now)] if d.is_dir() else []
        if old:
            out.append(Item("cache", f"{len(old)} old {what}", sum(size(p) for p in old), old))
    parts = [p for p in cache.rglob("*.part") if older(p, 1, now)] if cache.is_dir() else []
    if parts:
        out.append(Item("cache", f"{len(parts)} cut-off downloads", sum(size(p) for p in parts), parts))
    return out


def log_items(app: App) -> list[Item]:
    cap = int(float(app.settings.get("space.log_mb") or 20) * MB)
    out = []
    logs = Path(app.paths.logs)
    for f in sorted(logs.glob("*")) if logs.is_dir() else []:
        n = size(f)
        if f.is_file() and n > cap:
            out.append(
                Item(
                    "logs", f"the log {f.name} ({human(n)}) cut to its newest part", n - cap // 2, [f], cut_to=cap // 2
                )
            )
    return out


def job_items(app: App, now: float) -> list[Item]:
    days = float(app.settings.get("space.jobs_days") or 60)
    db = Path(app.paths.state) / "jobs.db"
    if not db.is_file():
        return []
    cutoff = now - days * 86400
    try:
        con = sqlite3.connect(str(db), timeout=5)
        try:
            n, chars = con.execute(
                "select count(*), coalesce(sum(length(coalesce(prompt,'')) + length(coalesce(result,''))), 0) "
                "from jobs where finished is not null and finished < ? and status in ('ok','failed','cancelled')",
                (cutoff,),
            ).fetchone()
        finally:
            con.close()
    except sqlite3.Error:
        return []
    if not n:
        return []
    return [Item("jobs", f"{n} finished AI requests older than {days:g} days", int(chars), [db], sql=str(cutoff))]


def pending_items(app: App, now: float) -> list[Item]:
    days = float(app.settings.get("space.undo_days") or 30)
    out = []
    for sub, what in (
        ("integrate/undo", "before-copies from the concept graph"),
        ("integrate/pending", "unfinished concept-graph work"),
    ):
        d = Path(app.paths.state) / sub
        old = [p for p in d.iterdir() if older(p, days, now)] if d.is_dir() else []
        if old:
            out.append(Item("pending", f"{len(old)} {what}", sum(size(p) for p in old), old))
    return out


def diagnostics_items(app: App, now: float) -> list[Item]:
    days = float(app.settings.get("space.cache_days") or 14)
    d = Path(app.paths.data)
    old = [p for p in d.iterdir() if DIAG.match(p.name) and older(p, days, now)] if d.is_dir() else []
    return (
        [Item("diagnostics", f"{len(old)} help bundles and restore leftovers", sum(size(p) for p in old), old)]
        if old
        else []
    )


def plan(app: App, now: float | None = None) -> list[Item]:
    now = now or time.time()
    return [
        *backup_items(app, now),
        *cache_items(app, now),
        *log_items(app),
        *job_items(app, now),
        *pending_items(app, now),
        *diagnostics_items(app, now),
    ]


def footprint(app: App) -> dict[str, int]:
    """How much room each part of Kurooto takes (the folders it owns, not your notes or books)."""
    p = app.paths
    out = {
        "program versions": size(Path(p.app) / "versions"),
        "downloads and caches": size(Path(p.cache)),
        "state and logs": size(Path(p.state)),
        "its data (books' text, profile, index)": size(Path(p.data)),
    }
    mod = app.modules.get("backups")
    folder = mod.folder() if mod is not None else None
    if folder is not None and Path(folder).is_dir():
        from kurooto.modules import backups

        out["backup zips"] = sum(size(f) for f in backups.listing(folder))
    return out


def clean(app: App, items: list[Item]) -> dict:
    """Do the plan. Returns {"freed": bytes, "removed": n, "failed": n}; one failure never stops the rest."""
    freed = removed = failed = 0
    for it in items:
        try:
            if it.kind == "logs":
                for f in it.paths:
                    data = f.read_bytes()
                    keep = data[-it.cut_to :]
                    nl = keep.find(b"\n")
                    f.write_bytes(keep[nl + 1 :] if nl >= 0 else keep)
                freed += it.bytes
                removed += len(it.paths)
            elif it.kind == "jobs":
                con = sqlite3.connect(str(it.paths[0]), timeout=30)
                try:
                    cutoff = float(it.sql)
                    ids = [
                        r[0]
                        for r in con.execute(
                            "select id from jobs where finished is not null and finished < ? "
                            "and status in ('ok','failed','cancelled')",
                            (cutoff,),
                        )
                    ]
                    for i in range(0, len(ids), 500):
                        chunk = ids[i : i + 500]
                        marks = ",".join("?" * len(chunk))
                        con.execute(f"delete from attempts where job in ({marks})", chunk)  # noqa: S608 (placeholders only)
                        con.execute(f"delete from jobs where id in ({marks})", chunk)  # noqa: S608 (placeholders only)
                    con.commit()
                    con.execute("vacuum")
                finally:
                    con.close()
                freed += it.bytes
                removed += len(ids)
            else:
                for pth in it.paths:
                    n = size(pth)
                    if pth.is_dir() and not pth.is_symlink():
                        shutil.rmtree(pth, ignore_errors=False)
                    else:
                        pth.unlink()
                    freed += n
                    removed += 1
        except (OSError, sqlite3.Error):
            failed += 1
    app.events.emit("space_cleaned", freed=freed, removed=removed, failed=failed)
    return {"freed": freed, "removed": removed, "failed": failed}


def report(items: list[Item]) -> str:
    if not items:
        return "Nothing to clean: Kurooto isn't holding on to anything it doesn't need."
    lines = [f"- {it.what}: {human(it.bytes)}" for it in items]
    return "\n".join([*lines, f"Together {human(sum(i.bytes for i in items))}."])


def low_disk(app: App) -> str | None:
    """A plain warning when the disk Kurooto lives on is nearly full, else None."""
    try:
        free = shutil.disk_usage(app.paths.data).free
    except OSError:
        return None
    return f"Only {human(free)} is free on the disk Kurooto uses." if free < 2 * GB else None


__all__ = ["Item", "plan", "clean", "report", "footprint", "human", "low_disk", "size", "os"]

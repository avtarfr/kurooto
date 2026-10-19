"""Small JSON state files, written atomically. Always UTF-8: Windows would otherwise default to a code page."""

from __future__ import annotations

import copy
import json
import os
import time
from pathlib import Path


def jload(path, default=None):
    """The file's JSON, or a copy of `default` if it is missing or unreadable."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return copy.deepcopy(default)


def jsave(path, obj, mode: int = 0o600) -> None:
    """Write JSON atomically: a temporary file, then a rename over the target.

    On Windows an antivirus scanner or the search indexer can hold the target for a moment, which makes the
    rename fail with PermissionError, so it is retried briefly. File modes only mean something on POSIX.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(f"{p.name}.tmp{os.getpid()}")
    tmp.write_text(json.dumps(obj, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    if os.name != "nt":
        os.chmod(tmp, mode)
    for attempt in range(10):
        try:
            os.replace(tmp, p)
            return
        except PermissionError:
            if attempt == 9:
                tmp.unlink(missing_ok=True)
                raise
            time.sleep(0.05 * (attempt + 1))


def owner_only(db) -> None:
    """A database, and SQLite's -wal and -shm files beside it, readable by this account only (like the JSON files):
    it holds what you asked the AI and your reminders. File modes only mean something on POSIX."""
    if os.name == "nt":
        return
    for p in (Path(db), Path(f"{db}-wal"), Path(f"{db}-shm")):
        try:
            os.chmod(p, 0o600)
        except OSError:
            pass

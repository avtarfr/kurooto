"""One read of the chat's turns for the readers that look back over them (0.9.1, L94, memory.night_read, on).

The nightly readers each read Chat's recent turns (chat/history.json) for themselves: what you set up in passing
(core/infer.py: sweep, 04:20), what you said you'd do (modules/fold.py, 04:50) and the history index
(modules/learning.py). `turns(app)` reads the file once and hands every one of them the same rows until the file
changes (its size and time), so a night's passes don't each parse it again. Their own schedules, marks and outputs
stay exactly as they were: each still takes only the turns after its own mark. Off: each reads the file itself, as
before. Nothing is written; the rows live in memory only, never leave this computer.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto.core.config import register_defaults
from kurooto.core.state import jload

if TYPE_CHECKING:
    from kurooto.app import App

# one read of the chat's turns shared by the readers that look back over them (infer, fold, the history index)
register_defaults("memory", {"night_read": True})

_lock = threading.Lock()
_cache: dict[str, tuple[tuple[int, int], list[dict]]] = {}
reads = {"parsed": 0, "shared": 0}  # how often the file was parsed, and how often a reader got the rows already read


def _file(app: App) -> Path:
    return Path(app.paths.state) / "chat" / "history.json"


def turns(app: App) -> list[dict]:
    """Chat's turns as stored ({"at", "user", "assistant", ...}), oldest first; the same list for every reader while
    the file is unchanged (don't change it). [] when there's none."""
    f = _file(app)
    if not app.settings.get("memory.night_read"):
        return [t for t in jload(f, []) or [] if isinstance(t, dict)]
    try:
        st = f.stat()
    except OSError:
        return []
    key = (st.st_mtime_ns, st.st_size)
    with _lock:
        got = _cache.get(str(f))
        if got and got[0] == key:
            reads["shared"] += 1
            return got[1]
        rows = [t for t in jload(f, []) or [] if isinstance(t, dict)]
        _cache[str(f)] = (key, rows)
        reads["parsed"] += 1
    return rows


def said_since(app: App, since: float) -> list[tuple[float, str]]:
    """(when, your words) for each turn after `since` that has words of yours."""
    out = []
    for t in turns(app):
        at = float(t.get("at") or 0)
        if at > since and t.get("user"):
            out.append((at, str(t["user"])))
    return out

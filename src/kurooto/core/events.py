"""The event log: one JSON line per thing that happened (a message, a reminder, a job), kept on this computer.
The dashboard's feed and the weekly summary read it; nothing here leaves the machine."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from pathlib import Path

from kurooto.core.clock import now

_lock = threading.Lock()
_listeners: list[Callable[[dict], None]] = []


class Events:
    def __init__(self, state_dir: Path):
        self.file = Path(state_dir) / "events.jsonl"

    def emit(self, event: str, /, **fields) -> dict:
        """Record one event. A caller's own kind= (e.g. a message's kind) is kept as "subkind"."""
        if "kind" in fields:
            fields["subkind"] = fields.pop("kind")
        rec = {"ts": now().isoformat(), "kind": event, **fields}
        line = json.dumps(rec, ensure_ascii=False, default=str)
        with _lock:
            self.file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.file, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        for cb in list(_listeners):
            try:
                cb(rec)
            except Exception:
                pass
        return rec

    def tail(self, n: int = 50, kinds: set[str] | None = None) -> list[dict]:
        try:
            lines = self.file.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        out = []
        for ln in reversed(lines):
            try:
                rec = json.loads(ln)
            except ValueError:
                continue
            if kinds is None or rec.get("kind") in kinds:
                out.append(rec)
                if len(out) >= n:
                    break
        return list(reversed(out))


def subscribe(cb: Callable[[dict], None]) -> Callable[[], None]:
    """Call cb for every new event (the dashboard's live feed). Returns an unsubscribe function."""
    _listeners.append(cb)
    return lambda: _listeners.remove(cb) if cb in _listeners else None

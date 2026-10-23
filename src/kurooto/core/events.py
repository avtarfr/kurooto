"""The event log: one JSON line per thing that happened (a message, a reminder, a job), kept on this computer.
The dashboard's feed and the weekly summary read it; nothing here leaves the machine."""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Callable, Iterator
from pathlib import Path

from kurooto.core.clock import now

_lock = threading.Lock()
_listeners: list[Callable[[dict], None]] = []
MAX_BYTES = 10_000_000  # past this the log moves to events.jsonl.1 (replacing the one before) and starts again


def lines_back(file: Path, end: int | None = None) -> Iterator[str]:
    """A log's lines from byte `end` (its end) backwards (newest first), read a block at a time."""
    try:
        f = open(file, "rb")  # noqa: SIM115 (a generator keeps it open while it's read)
    except OSError:
        return
    with f:
        pos, rest = os.fstat(f.fileno()).st_size if end is None else end, b""
        while pos > 0:
            n = min(1 << 20, pos)
            pos -= n
            f.seek(pos)
            parts = (f.read(n) + rest).split(b"\n")
            rest = parts[0]
            for ln in reversed(parts[1:]):
                if ln:
                    yield ln.decode("utf-8", "replace")
        if rest:
            yield rest.decode("utf-8", "replace")


class Events:
    def __init__(self, state_dir: Path):
        self.file = Path(state_dir) / "events.jsonl"
        self.older = Path(state_dir) / "events.jsonl.1"

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
                f.flush()
                full = os.fstat(f.fileno()).st_size > MAX_BYTES
            if full:  # trimmed like the logs: the newest MAX_BYTES or more stay readable (lines())
                try:
                    os.replace(self.file, self.older)
                except OSError:
                    pass  # (Windows, another program has it open) next time
        for cb in list(_listeners):
            try:
                cb(rec)
            except Exception:
                pass
        return rec

    def lines(self) -> Iterator[str]:
        """Every line of the log, newest first: this file, then the one it moved aside."""
        yield from lines_back(self.file)
        yield from lines_back(self.older)

    def tail(self, n: int = 50, kinds: set[str] | None = None) -> list[dict]:
        """The last n events (of these kinds), read from the end: the cost is what's read, not the log's size."""
        out = []
        for ln in self.lines():
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

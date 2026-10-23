#!/usr/bin/env python3
"""A tqdm-style progress bar for the test suite, to watch a long run from another window (no extra packages).

    PYTHONPATH=tools uv run pytest -p pytest_progress tests/unit    writes the progress to .pytest-progress.json
    python3 tools/pytest_progress.py [FILE]                         draws the bar until that run ends

KUROOTO_TEST_PROGRESS names another file for both. The bar shows tests done of all, the rate, time left, and each
failure as it happens; when the run ends it prints the failures and how long it took.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path

DEFAULT = ".pytest-progress.json"
_clock = time.time  # the real clock, taken before any test fakes time.time (a faked one froze the bar)


def target() -> Path:
    return Path(os.environ.get("KUROOTO_TEST_PROGRESS") or DEFAULT)


# ---------------------------------------------------------------------------------------- the plugin (in pytest)
class _State:
    def __init__(self, path: Path):
        self.path = path
        self.d = {"total": 0, "done": 0, "failed": [], "skipped": 0, "start": _clock(), "end": None, "now": ""}
        self.last = 0.0

    def save(self, force: bool = False) -> None:
        if not force and _clock() - self.last < 0.5:
            return
        self.last = _clock()
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_text(json.dumps(self.d), encoding="utf-8")
        tmp.replace(self.path)


_state: _State | None = None


def pytest_configure(config):
    global _state
    _state = _State(target().resolve())
    _state.save(force=True)


def pytest_collection_finish(session):
    if _state:
        _state.d["total"] = len(session.items)
        _state.save(force=True)


def pytest_runtest_logreport(report):
    if not _state:
        return
    d = _state.d
    if report.when == "call" or (report.when == "setup" and not report.passed):
        d["done"] += 1
        d["now"] = report.nodeid.split("::")[-1][:60]
        if report.failed:
            d["failed"].append(report.nodeid)
        elif report.skipped:
            d["skipped"] += 1
        _state.save()
    elif report.when == "teardown" and report.failed:
        d["failed"].append(report.nodeid + " (teardown)")
        _state.save()


def pytest_sessionfinish(session, exitstatus):
    if _state:
        _state.d["end"] = _clock()
        _state.d["exit"] = int(exitstatus)
        _state.save(force=True)


# ------------------------------------------------------------------------------------------ the viewer
def clock(s: float) -> str:
    s = int(max(0, s))
    return f"{s // 3600}:{s // 60 % 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60:02d}:{s % 60:02d}"


def bar(d: dict, width: int) -> str:
    total, done = d.get("total") or 0, d.get("done") or 0
    spent = (d.get("end") or time.time()) - (d.get("start") or time.time())
    rate = done / spent if spent > 0 else 0.0
    left = (total - done) / rate if rate > 0 and total else 0
    frac = min(1.0, done / total) if total else 0.0
    info = (
        f" {done}/{total or '?'} {frac * 100:3.0f}% [{clock(spent)}<{clock(left)}, {rate:.1f} tests/s]"
        f" {len(d.get('failed') or [])} failed"
    )
    n = max(10, width - len(info) - 9)
    full, part = divmod(frac * n, 1)
    blocks = " ▏▎▍▌▋▊▉"
    body = "█" * int(full) + (blocks[int(part * 8)] if full < n else "")
    return f"tests ▕{body.ljust(n)}▏{info}"


def watch(path: Path) -> int:
    seen = 0
    print(f"Watching {path} (Ctrl+C stops watching; the run goes on).")
    while True:
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            sys.stdout.write("\rwaiting for the run to start…")
            sys.stdout.flush()
            time.sleep(1)
            continue
        failed = d.get("failed") or []
        width = shutil.get_terminal_size((100, 20)).columns
        for f in failed[seen:]:
            sys.stdout.write("\r" + " " * (width - 1) + f"\rFAILED {f}\n")
        seen = len(failed)
        sys.stdout.write("\r" + bar(d, width)[: width - 1])
        sys.stdout.flush()
        if d.get("end"):
            spent = d["end"] - d["start"]
            ok = "passed" if not failed and not d.get("exit") else "had failures"
            print(f"\n\nDone in {clock(spent)}: {d['done']} tests {ok}, {d.get('skipped', 0)} skipped.")
            for f in failed:
                print(f"  FAILED {f}")
            return 1 if failed else 0
        time.sleep(0.5)


if __name__ == "__main__":
    try:
        raise SystemExit(watch(Path(sys.argv[1]) if len(sys.argv) > 1 else target()))
    except KeyboardInterrupt:
        print()

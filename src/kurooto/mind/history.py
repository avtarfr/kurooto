"""Feeding Brain what happened before it was switched on (0.8.1). Off until you turn it on: `mind.backfill.on`.

Kurooto has kept an event history since you installed it (`events.jsonl`: deadlines, reminders, calls, AI requests,
buttons, power). Brain's log began the day Brain was switched on, so its read, forecasts and plans start with no past.
This reads that history, read-only, and hands it to the scorekeeper in batches, which files each event in a `history`
table under its own time. It never goes into the log's chain, and it is never a reward: history trains priors (what a
normal day was), nothing else (invariants I-3 and I-4). Only ids and numbers pass (records.clean_fact); no words of any
message.

    status(app)    what is imported, and what is waiting
    plan(app)      a dry run: counts per kind and the dates, nothing written
    run(app)       the import: resumable, idempotent (a batch's rows have fixed keys), with progress
    forget(app)    remove all of it (and what was learned only from it)
    daily(app)     {date: {kind: count}} of the imported past, for the read's and forecast's history
"""

from __future__ import annotations

import datetime as dt
import json
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto import mind
from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave
from kurooto.mind import log as mlog

if TYPE_CHECKING:
    from kurooto.app import App

PART = "backfill"  # its switch: mind.backfill.on

register_defaults(
    "mind",
    {
        "backfill": {
            "on": False,  # off until you turn it on: Brain reads what Kurooto kept before it was on (`/mind backfill`)
            "events": True,  # read Kurooto's own event history (deadlines, reminders, calls, AI requests, buttons)
        }
    },
)

BATCH = 500


def _file(app: App) -> Path:
    return Path(app.paths.state) / "events.jsonl"


def _state_file(app: App) -> Path:
    return Path(app.paths.state) / "mind" / "history-import.json"


def _epoch(ts: str) -> float | None:
    try:
        return dt.datetime.fromisoformat(ts).timestamp()  # events are stamped in local time
    except (TypeError, ValueError):
        return None


def _cutoff(app: App) -> float | None:
    """When Brain's own log began: events from then on are already in it."""
    recs = mind.connect(app).log(after=0, limit=1)
    return recs[0].ts if recs else None


def _rows(app: App, until: float | None):
    """(line number, {at, kind, body}) for each mirrored event before `until`, oldest first."""
    f = _file(app)
    if not f.exists():
        return
    with f.open(encoding="utf-8", errors="replace") as fh:
        for n, line in enumerate(fh):
            try:
                e = json.loads(line)
            except ValueError:
                continue
            kind = str(e.get("kind") or "")
            at = _epoch(e.get("ts"))
            if at is None or not mlog.mirrored(kind) or (until is not None and at >= until):
                continue
            yield n, {"at": at, "kind": kind, "body": {k: v for k, v in e.items() if k not in ("ts", "kind")}}


def plan(app: App) -> dict:
    """A dry run: how many events of each kind, and the dates they span. Writes nothing."""
    until = _cutoff(app)
    kinds: dict[str, int] = defaultdict(int)
    lo = hi = None
    total = 0
    for _, r in _rows(app, until):
        kinds[r["kind"]] += 1
        total += 1
        lo = r["at"] if lo is None else min(lo, r["at"])
        hi = r["at"] if hi is None else max(hi, r["at"])
    return {"rows": total, "kinds": dict(sorted(kinds.items(), key=lambda kv: -kv[1])), "from": lo, "to": hi}


def status(app: App) -> dict:
    st = jload(_state_file(app), {}) or {}
    have = len(mind.connect(app).history_rows())
    return {
        "imported": have,
        "done_at": st.get("done_at"),
        "from": st.get("from"),
        "to": st.get("to"),
        "lines": st.get("lines", 0),
    }


def run(app: App, progress: Callable[[int, int], None] | None = None) -> dict:
    """Import everything before Brain's own log began. Safe to run again: batch ids come from the line numbers, so a
    re-run rewrites the same rows. Returns {rows, batches, from, to}."""
    if not mind.on(app) or not app.settings.get("mind.backfill.on"):
        return {"error": "Turn on Brain and mind.backfill.on first."}
    if not app.settings.get("mind.backfill.events"):
        return {"error": "mind.backfill.events is off."}
    c = mind.connect(app)
    if not c.running()[0]:
        return {"error": "The scorekeeper isn't running."}
    until = _cutoff(app)
    total = sum(1 for _ in _rows(app, until))
    sent = batches = 0
    lo = hi = None
    buf: list[dict] = []
    first_line = 0

    def flush() -> bool:
        nonlocal sent, batches
        if not buf:
            return True
        res = c.import_history(f"ev{first_line:07d}", list(buf))
        if not res.get("ok"):
            return False
        sent += int(res.get("rows") or 0)
        batches += 1
        buf.clear()
        if progress:
            progress(sent, total)
        return True

    for n, r in _rows(app, until):
        if not buf:
            first_line = n
        buf.append(r)
        lo = r["at"] if lo is None else min(lo, r["at"])
        hi = r["at"] if hi is None else max(hi, r["at"])
        if len(buf) >= BATCH and not flush():
            return {"error": "The scorekeeper refused a batch; nothing more was sent.", "rows": sent}
    if not flush():
        return {"error": "The scorekeeper refused a batch.", "rows": sent}
    jsave(_state_file(app), {"done_at": dt.datetime.now().timestamp(), "from": lo, "to": hi, "lines": total})
    return {"rows": sent, "batches": batches, "from": lo, "to": hi}


def forget(app: App) -> int:
    res = mind.connect(app).forget_history()
    try:
        _state_file(app).unlink()
    except OSError:
        pass
    return int(res.get("rows") or 0)


def daily(app: App) -> dict[str, dict[str, int]]:
    """{date: {kind: count}} of the imported past. Empty when nothing was imported or backfill is off."""
    if not mind.part_on(app, "backfill"):
        return {}
    out: dict[str, dict[str, int]] = {}
    for r in mind.connect(app).history_rows():
        k = (r.get("meta") or {}).get("k")
        if not k:
            continue
        day = dt.datetime.fromtimestamp(float(r["value"])).date().isoformat()
        d = out.setdefault(day, {})
        d[k] = d.get(k, 0) + 1
    return out


def describe(app: App) -> list[str]:
    """What /mind backfill says about the imported past: a normal week, from the history."""
    days = daily(app)
    if not days:
        return ["Nothing from before Brain was on is imported."]
    wd: dict[int, list[int]] = defaultdict(list)
    for day, ks in days.items():
        wd[dt.date.fromisoformat(day).weekday()].append(ks.get("reminder_fired", 0) + ks.get("deadline_added", 0))
    names = "Mon Tue Wed Thu Fri Sat Sun".split()
    line = ", ".join(f"{names[i]} {sum(v) / len(v):.0f}" for i, v in sorted(wd.items()))
    return [
        f"{len(days)} days imported ({min(days)} to {max(days)}).",
        f"Reminders and new deadlines a day, on average: {line}.",
    ]

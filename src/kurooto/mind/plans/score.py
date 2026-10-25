"""Scoring plans against what happened (stage 15): calibration, never compliance.

When a plan is made its p50 finish dates are kept. A week or more later, for each milestone that has since been
finished, the
question is whether it finished on or before its predicted p50: if the plans are calibrated about half do. The score
is how close
that fraction is to a half (1 is perfectly calibrated), and needs at least 6 finished milestones before it says
anything.

It looks only at when things finished. Whether you followed the suggested allocation is not an input anywhere, so a
plan earns
nothing for being obeyed (the forecast firewall of stage 04): this module is not a reward source (mind/whitelist.py) and
feeds no reward.
"""

from __future__ import annotations

import datetime as dt
import time
from typing import TYPE_CHECKING

from kurooto.core.state import jsave
from kurooto.mind.plans.tree import FILE, _state

if TYPE_CHECKING:
    from kurooto.app import App

MIN_SCORED = 6
KEEP = 24


def record(app: App, results: dict, today: dt.date | None = None) -> None:
    """Keep this plan's p50 dates (one record a week at most)."""
    today = today or dt.date.today()
    st = _state(app)
    if st["predictions"] and (today - dt.date.fromisoformat(st["predictions"][-1]["on"])).days < 7:
        return
    st["predictions"].append(
        {
            "on": today.isoformat(),
            "nodes": {
                i: {"p50": r.p50.isoformat() if r.p50 else None, "due": r.due.date().isoformat()}
                for i, r in results.items()
            },
        }
    )
    st["predictions"] = st["predictions"][-KEEP:]
    jsave(app.paths.state / FILE, st)


def finished_on(app: App, nid: str) -> dt.date | None:
    """When a node was finished, if it was (a deadline marked done keeps its time)."""
    dl = app.modules.get("deadlines")
    if dl is None or not nid.startswith("d:"):
        return None
    it = dl.items().get(nid[2:])
    if not it or it.get("status") != "done":
        return None
    at = it.get("done_at") or it.get("updated")
    try:
        return (
            dt.datetime.fromtimestamp(float(at)).date()
            if isinstance(at, (int, float))
            else dt.datetime.fromisoformat(str(at)).date()
        )
    except (TypeError, ValueError):
        return None


def calibration(app: App, today: dt.date | None = None, finish=None) -> tuple[int, float | None, float | None]:
    """(milestones scored, the share finished on or before their p50, the score 0 to 1). `finish(id)` is for tests."""
    today = today or dt.date.today()
    seen: dict[str, bool] = {}
    for p in _state(app)["predictions"]:
        if (today - dt.date.fromisoformat(p["on"])).days < 7:
            continue
        for nid, n in p["nodes"].items():
            if nid in seen or not n["p50"]:
                continue
            f = (finish or (lambda i: finished_on(app, i)))(nid)
            if f is not None:
                seen[nid] = f <= dt.date.fromisoformat(n["p50"])
    if len(seen) < MIN_SCORED:
        return len(seen), None, None
    frac = sum(seen.values()) / len(seen)
    return len(seen), round(frac, 3), round(1 - 2 * abs(frac - 0.5), 3)


def stamp() -> float:
    return time.time()

"""Measuring the body budget's variables (Brain, 0.8.0 stage 05): the daemon's half. It looks at Kurooto's own state,
hands
the numbers to the scorekeeper as a `budget_tick` fact, and that is all: the setpoints, the drive and the reward are the
scorekeeper's (mind/engine.py), so what is measured can be true or false, but can't be scored by whoever measured it.

    health          the share of OK among: disk free, backup age, the call line, AI limits, crashes in 24 h, its own log
    promise_slack   mind/promises.py
    deadline_margin not measured yet: it needs deadlines Kurooto has a claimed help act on (stage 06 makes them)
"""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

from kurooto import mind
from kurooto.core.clock import now
from kurooto.mind import promises, stops

if TYPE_CHECKING:
    from kurooto.app import App

PART = "budget"  # its switch: mind.budget.on
DISK_MIN_GB = 5.0
BACKUP_MAX_DAYS = 7


def health(app: App) -> float | None:
    """The share of OK among the checks that can be made now (None when none can)."""
    ok: list[bool] = []
    try:
        ok.append(shutil.disk_usage(app.paths.state).free / 1e9 >= DISK_MIN_GB)
    except OSError:
        pass
    try:
        if app.is_on("backups"):
            at = float((app.modules["backups"].last() or {}).get("at") or 0)
            ok.append(at > 0 and (now().timestamp() - at) < BACKUP_MAX_DAYS * 86400)
    except Exception:
        pass
    try:
        if app.is_on("calls"):
            last = app.events.tail(1, {"calls_link"})
            if last:
                ok.append(bool(last[-1].get("connected")))
    except Exception:
        pass
    try:
        ok.append(not any(r.get("until") for r in app.quota.report()))
    except Exception:
        pass
    try:
        c = mind.connect(app)
        recent = [r for r in c.log(0, {"kurooto_crashed", "module_failed", "mind_keeper_exited"}, 2000)]
        cutoff = now().timestamp() - 86400
        ok.append(stops.crashes([r for r in recent if r.ts >= cutoff]) == 0)
        ok.append(c.verify().ok)  # its own log's chain: "memory checksums"
    except Exception:
        pass
    return round(sum(ok) / len(ok), 4) if ok else None


def measure(app: App) -> dict:
    """The body of a budget_tick: the variables, the hour, whether you're at the computer, whether it's exam season."""
    x: dict = {"promise_slack": round(promises.slack(app), 4)}
    h = health(app)
    if h is not None:
        x["health"] = h
    t = now()
    at = False
    try:
        from kurooto.core.idle import IdleProbe

        idle = IdleProbe(app.paths.state).idle_seconds()
        at = idle is not None and idle < 600
    except Exception:
        pass
    season = False
    try:
        ex = app.modules.get("exam_season")
        season = bool(ex is not None and app.is_on("exam_season") and ex.season())
    except Exception:
        pass
    return {"x": x, "hour": t.hour, "at_computer": at, "season": season}


def run(app: App, payload: dict | None = None) -> bool:
    """Every 5 minutes: measure and hand it over. False when the budget is off."""
    if not mind.part_on(app, "budget"):
        return False
    return mind.connect(app).report("budget_tick", measure(app))

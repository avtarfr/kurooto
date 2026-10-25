"""Where the senses keep what they saw: raw events for 7 days, then only daily totals.

    <state>/mind-senses/senses.db     events(t, sensor, kind, target, n) and days(day, sensor, key, value)

Only text-free things go in: a sensor name, a kind, a short shape or hash as the target, a number. Raw events older than
`KEEP_DAYS` are folded into per-day totals ("minutes on glacier-flow") and deleted. `forget_today` and `off` remove a
sensor's rows. Nothing here is ever sent anywhere.
"""

from __future__ import annotations

import datetime as dt
import sqlite3
import threading
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from kurooto.app import App

KEEP_DAYS = 7
SCHEMA = """
create table if not exists events(
  t real not null, sensor text not null, kind text not null, target text not null default '', n real not null default 0
);
create index if not exists events_t on events(sensor, t);
create table if not exists days(
  day text not null, sensor text not null, key text not null, value real not null, primary key(day, sensor, key)
);
"""
_lock = threading.Lock()
UPSERT = "insert into days values (?,?,?,?) on conflict(day, sensor, key) do update set value = value + excluded.value"


def path(app: App) -> Path:
    return app.paths.state / "mind-senses" / "senses.db"


def _db(app: App) -> sqlite3.Connection:
    p = path(app)
    p.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(p, timeout=10)
    db.executescript(SCHEMA)
    return db


def add(app: App, sensor: str, kind: str, target: str = "", n: float = 0.0, t: float | None = None) -> None:
    with _lock:
        db = _db(app)
        with db:
            db.execute(
                "insert into events values (?,?,?,?,?)",
                (t or time.time(), sensor[:20], kind[:30], target[:80], float(n)),
            )
        db.close()


def events(app: App, sensor: str, since: float = 0.0, kind: str | None = None) -> list[dict]:
    if not path(app).exists():
        return []
    with _lock:
        db = _db(app)
        q, a = "select t, kind, target, n from events where sensor=? and t>=?", [sensor, since]
        if kind:
            q, a = q + " and kind=?", [*a, kind]
        rows = db.execute(q + " order by t", a).fetchall()
        db.close()
    return [{"t": t, "kind": k, "target": g, "n": n} for t, k, g, n in rows]


def day_start(now: float | None = None) -> float:
    d = dt.datetime.fromtimestamp(now or time.time()).replace(hour=0, minute=0, second=0, microsecond=0)
    return d.timestamp()


def bump(app: App, day: str, sensor: str, key: str, value: float) -> None:
    with _lock:
        db = _db(app)
        with db:
            db.execute(
                UPSERT,
                (day, sensor, key[:60], float(value)),
            )
        db.close()


def totals(app: App, sensor: str, day: str) -> dict[str, float]:
    if not path(app).exists():
        return {}
    with _lock:
        db = _db(app)
        rows = db.execute("select key, value from days where day=? and sensor=?", (day, sensor)).fetchall()
        db.close()
    return {k: v for k, v in rows}


def rollup(app: App, now: float | None = None) -> int:
    """Fold raw events older than KEEP_DAYS into the days table (counts per kind:target) and delete them."""
    if not path(app).exists():
        return 0
    cut = (now or time.time()) - KEEP_DAYS * 86400
    with _lock:
        db = _db(app)
        old = db.execute("select t, sensor, kind, target, n from events where t<?", (cut,)).fetchall()
        with db:
            for t, sensor, kind, target, n in old:
                day = dt.datetime.fromtimestamp(t).date().isoformat()
                key = f"{kind}:{target}" if target else kind
                db.execute(
                    UPSERT,
                    (day, sensor, key[:60], n or 1.0),
                )
            db.execute("delete from events where t<?", (cut,))
        db.close()
    return len(old)


def forget(app: App, sensor: str | None = None, today_only: bool = True) -> int:
    """Remove a sensor's (or every sensor's) rows: today's, or all of them."""
    if not path(app).exists():
        return 0
    start = day_start() if today_only else 0.0
    with _lock:
        db = _db(app)
        w, a = "t>=?", [start]
        if sensor:
            w, a = w + " and sensor=?", [*a, sensor]
        n = db.execute(f"select count(*) from events where {w}", a).fetchone()[0]  # noqa: S608 (fixed fragments)
        with db:
            db.execute(f"delete from events where {w}", a)  # noqa: S608
            dq = "delete from days where day>=?" if today_only else "delete from days where 1=1"
            da = [dt.date.today().isoformat()] if today_only else []
            if sensor:
                dq, da = dq + " and sensor=?", [*da, sensor]
            db.execute(dq, da)
        db.close()
    return n

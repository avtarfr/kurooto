"""The scheduler: every timed thing Kurooto does (check-ins, reminders, syncs), kept in SQLite so it survives
restarts and catches up after the computer sleeps. It replaces systemd timers and `systemd-run` one-offs.

Recurring specs, in the user's time zone:
    every 10m | every 2h | hourly | daily 05:00 | daily 07:00,13:00,19:00 | weekly sun 19:30
One-off jobs: at(when, action, payload, key=...) and cancel(key).

When a job comes due late (the laptop was asleep):
    recurring jobs run once ("coalesce") or not at all ("skip"), then continue from now;
    one-off jobs run with payload["late_s"] set if they're within their grace period, or with payload["missed"]
    if not, so the module can say "this was due at 09:00" instead of acting as if it were on time.
Gates postpone a job instead of running it: respect="quiet" waits out focus time (do-not-disturb: what it holds are
messages, and "no calls until X" lets messages through), respect="call_block" waits until a call is allowed (both are
hooks the availability rules provide).
"""

from __future__ import annotations

import asyncio
import datetime as dt
import inspect
import json
import re
import sqlite3
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

from kurooto.core.state import owner_only

DAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}

SCHEMA = """
create table if not exists schedule (
    key text primary key, module text not null default '', action text not null, payload text not null default '{}',
    kind text not null, spec text, next_run real not null, misfire text not null default 'coalesce',
    grace_s integer not null default 43200, respect text not null default 'none',
    last_run real, last_result text, created real not null
);
create index if not exists schedule_next on schedule(next_run);
"""


def local_tz() -> dt.tzinfo:
    return dt.datetime.now().astimezone().tzinfo


def next_after(spec: str, after: dt.datetime, tz: dt.tzinfo) -> dt.datetime:
    """The first time strictly after `after` (aware) that matches the spec. Raises ValueError on a bad spec."""
    s = spec.strip().lower()
    loc = after.astimezone(tz)
    m = re.fullmatch(r"every (\d+)\s*(m|min|h)", s)
    if m:
        step = dt.timedelta(minutes=int(m[1])) if m[2] != "h" else dt.timedelta(hours=int(m[1]))
        if step.total_seconds() < 60:
            raise ValueError("the shortest interval is a minute")
        return after + step
    if s == "hourly":
        return (loc.replace(minute=0, second=0, microsecond=0) + dt.timedelta(hours=1)).astimezone(dt.UTC)
    m = re.fullmatch(r"daily ((?:\d{1,2}:\d{2})(?:\s*,\s*\d{1,2}:\d{2})*)", s)
    w = re.fullmatch(r"weekly (mon|tue|wed|thu|fri|sat|sun) (\d{1,2}:\d{2})", s)
    if not m and not w:
        raise ValueError(f"unknown schedule {spec!r}")
    times = [tuple(map(int, t.split(":"))) for t in (m[1].split(",") if m else [w[2]])]
    for h, mi in times:
        if not (0 <= h < 24 and 0 <= mi < 60):
            raise ValueError(f"no such time in {spec!r}")
    for add in range(0, 8 if w else 2):
        day = loc.date() + dt.timedelta(days=add)
        if w and day.weekday() != DAYS[w[1]]:
            continue
        for h, mi in sorted(times):
            cand = dt.datetime(day.year, day.month, day.day, h, mi, tzinfo=tz)
            # a time that doesn't exist (spring-forward) or repeats (fall-back): fold=0 keeps the first
            if cand.astimezone(dt.UTC) > after.astimezone(dt.UTC):
                return cand.astimezone(dt.UTC)
    raise ValueError(f"no next time for {spec!r}")  # pragma: no cover


@dataclass
class Job:
    key: str
    module: str
    action: str
    payload: dict
    kind: str  # once | recurring
    spec: str | None
    next_run: float
    misfire: str
    grace_s: int
    respect: str
    last_run: float | None
    last_result: str | None

    @property
    def when(self) -> dt.datetime:
        return dt.datetime.fromtimestamp(self.next_run, dt.UTC)

    @property
    def label(self) -> str:
        return describe(self.action, self.key, self.payload)


LABELS = {  # what scheduled work is, in a few words (/status, `kurooto top`)
    "alarm.prep": "morning plan",
    "alarm.ring": "wake-up call",
    "ask.sweep": "open questions",
    "calendar.focus_end": "focus ends",
    "calendar.refresh": "calendar refresh",
    "calls.missed": "missed-call check",
    "calls.realert": "unanswered call rings again",
    "calls.task_check": "call follow-up",
    "checkins.deferred": "morning check-in",
    "checkins.plan": "today's check-ins",
    "checkins.unstick": "check-in follow-up",
    "deadlines.tick": "deadline check",
    "notes_sync.soon": "notes sync",
    "profile.soon": "profile save",
    "quiz.exam_daily": "exam practice",
    "quiz.offers": "quiz offers",
    "research.idle": "quiet projects",
    "research.logs": "project logs",
    "research.papers": "papers digest",
    "retro.nightly": "nightly look back",
    "study.session_end": "study session ends",
    "study.write": "study hours into the daily note",
    "telegram.focus_end": "focus ends",
    "updates.apply": "update",
    "updates.check": "update check",
    "updates.probation": "update settles",
    "updates.rolled_back": "rollback notice",
    "upgrade.whats_new": "what's new",
}


def describe(action: str, key: str = "", payload: dict | None = None) -> str:
    """A scheduled job in a few words: what it says it's about, else what kind of work it is."""
    p = payload if isinstance(payload, dict) else {}
    for k in ("what", "title", "reason"):
        if isinstance(p.get(k), str) and p[k].strip():
            return p[k].strip()
    name = p.get("name") or p.get("subject") or p.get("project")
    if action == "checkins.fire" and name:
        return f"{name} check-in"
    if action in ("capture.ask", "quiz.checkin", "research.remind") and name:
        return {"capture.ask": "after {}", "quiz.checkin": "quiz: {}", "research.remind": "about {}"}[action].format(
            name
        )
    if action in LABELS:
        return LABELS[action]
    mod, _, what = action.partition(".")
    return f"{mod}: {what}".replace("_", " ") if what else (key or action)


class Scheduler:
    def __init__(self, db: Path, tz: dt.tzinfo | str | None = None, clock: Callable[[], float] = time.time):
        self.db_path = Path(db)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.tz = ZoneInfo(tz) if isinstance(tz, str) else (tz or local_tz())
        self.clock = clock
        self.actions: dict[str, Callable] = {}
        self.gates: dict[str, Callable[[dt.datetime], dt.datetime | None]] = {}
        self.hold: Callable[[Job], float | None] | None = None  # power: paused or saver mode holds jobs back
        self.on_result: Callable[[Job, str, BaseException | None], None] | None = None
        self._lock = threading.Lock()
        self._wake = None  # an asyncio.Event once the loop runs
        self._db = sqlite3.connect(self.db_path, check_same_thread=False, isolation_level=None)
        owner_only(self.db_path)
        self._db.execute("pragma journal_mode=wal")
        self._db.executescript(SCHEMA)

    # ------------------------------------------------------------------------------- registering work
    def action(self, name: str, fn: Callable) -> None:
        """fn(payload) -> anything; may be async. Its return value is stored as the job's last result."""
        self.actions[name] = fn

    def now(self) -> dt.datetime:
        return dt.datetime.fromtimestamp(self.clock(), dt.UTC)

    def every(
        self,
        key: str,
        spec: str,
        action: str,
        payload: dict | None = None,
        *,
        module: str = "",
        misfire: str = "coalesce",
        respect: str = "none",
    ) -> Job:
        """Create or update a recurring job. Changing its spec reschedules it; otherwise its next run is kept."""
        nxt = next_after(spec, self.now(), self.tz).timestamp()
        with self._lock:
            row = self._db.execute("select spec, next_run from schedule where key=?", (key,)).fetchone()
            keep = row and row[0] == spec
            self._db.execute(
                "insert into schedule(key,module,action,payload,kind,spec,next_run,misfire,respect,created) "
                "values(?,?,?,?,'recurring',?,?,?,?,?) on conflict(key) do update set module=excluded.module, "
                "action=excluded.action, payload=excluded.payload, kind='recurring', spec=excluded.spec, "
                "misfire=excluded.misfire, respect=excluded.respect" + ("" if keep else ", next_run=excluded.next_run"),
                (key, module, action, json.dumps(payload or {}), spec, nxt, misfire, respect, self.clock()),
            )
        self._poke()
        return self.get(key)

    def at(
        self,
        when: dt.datetime | float,
        action: str,
        payload: dict | None = None,
        *,
        key: str | None = None,
        module: str = "",
        replace: bool = True,
        grace_s: int = 12 * 3600,
        respect: str = "none",
    ) -> str:
        """A one-off job. Naive datetimes are local time. With replace=False an existing key is left alone."""
        key = key or f"once:{uuid.uuid4().hex[:10]}"
        ts = when if isinstance(when, (int, float)) else (when if when.tzinfo else when.astimezone()).timestamp()
        verb = "insert or replace" if replace else "insert or ignore"
        with self._lock:
            self._db.execute(
                f"{verb} into schedule(key,module,action,payload,kind,spec,next_run,misfire,grace_s,respect,created) "
                "values(?,?,?,?,'once',null,?,'run',?,?,?)",
                (key, module, action, json.dumps(payload or {}), float(ts), grace_s, respect, self.clock()),
            )
        self._poke()
        return key

    def cancel(self, key: str) -> bool:
        with self._lock:
            return self._db.execute("delete from schedule where key=?", (key,)).rowcount > 0

    def cancel_prefix(self, prefix: str) -> int:
        with self._lock:
            esc = prefix.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            return self._db.execute("delete from schedule where key like ? escape '\\'", (esc + "%",)).rowcount

    def get(self, key: str) -> Job | None:
        row = self._db.execute(f"select {self._cols} from schedule where key=?", (key,)).fetchone()
        return self._job(row) if row else None

    def jobs(self, prefix: str = "") -> list[Job]:
        rows = self._db.execute(
            f"select {self._cols} from schedule where key like ? order by next_run",
            (prefix + "%",),
        )
        return [self._job(r) for r in rows]

    # only constants are put into SQL text below (column names, the insert verb); values are always bound
    _cols = "key,module,action,payload,kind,spec,next_run,misfire,grace_s,respect,last_run,last_result"

    @staticmethod
    def _job(r) -> Job:
        return Job(r[0], r[1], r[2], json.loads(r[3] or "{}"), r[4], r[5], r[6], r[7], r[8], r[9], r[10], r[11])

    # -------------------------------------------------------------------------------------- running
    def due(self) -> list[Job]:
        rows = self._db.execute(
            f"select {self._cols} from schedule where next_run <= ? order by next_run",
            (self.clock(),),
        )
        return [self._job(r) for r in rows]

    async def tick(self) -> list[tuple[str, str]]:
        """Run everything that is due now. Returns (key, outcome) pairs; outcome is ran | postponed | skipped |
        missing-action | error."""
        out = []
        now = self.now()
        for job in self.due():
            held = self.hold(job) if self.hold else None
            if held:
                self._set_next(job.key, held)
                out.append((job.key, "held"))
                continue
            gate = self.gates.get(job.respect)
            until = gate(now) if gate and job.respect != "none" else None
            if until:
                self._set_next(job.key, until.timestamp() if until.tzinfo else until.astimezone().timestamp())
                out.append((job.key, "postponed"))
                continue
            late = now.timestamp() - job.next_run
            payload = dict(job.payload)
            run_it = True
            if job.kind == "once":
                if late > job.grace_s:
                    payload["missed"] = True
                elif late > 120:
                    payload["late_s"] = int(late)
            elif job.misfire == "skip" and late > 120:
                run_it = False
            outcome, result, err = "skipped", None, None
            if run_it:
                fn = self.actions.get(job.action)
                if fn is None:
                    outcome, result = "missing-action", f"no action {job.action!r}"
                else:
                    try:
                        res = fn(payload)
                        if inspect.isawaitable(res):
                            res = await res
                        outcome, result = "ran", (None if res is None else str(res)[:500])
                    except Exception as e:  # one failing job never stops the others
                        outcome, result, err = "error", f"{type(e).__name__}: {e}"[:500], e
            self._finish(job, result)
            if self.on_result:
                try:
                    self.on_result(job, outcome, err)
                except Exception:
                    pass
            out.append((job.key, outcome))
        return out

    def _set_next(self, key: str, ts: float) -> None:
        with self._lock:
            self._db.execute("update schedule set next_run=? where key=?", (ts, key))

    def _finish(self, job: Job, result: str | None) -> None:
        with self._lock:
            if job.kind == "once":
                self._db.execute("delete from schedule where key=? and next_run=?", (job.key, job.next_run))
                return
            nxt = next_after(job.spec, self.now(), self.tz).timestamp()
            self._db.execute(
                "update schedule set next_run=?, last_run=?, last_result=? where key=? and next_run=?",
                (nxt, self.clock(), result, job.key, job.next_run),
            )

    def _poke(self) -> None:
        if self._wake is not None and self._loop is not None:
            self._loop.call_soon_threadsafe(self._wake.set)

    _loop = None

    async def run_forever(self, stop: asyncio.Event, max_sleep: float = 30.0) -> None:
        """Run due jobs, then sleep until the next one (at most `max_sleep`, so a clock jump after sleep or a
        time-zone change is noticed quickly)."""
        self._loop = asyncio.get_running_loop()
        self._wake = asyncio.Event()
        while not stop.is_set():
            await self.tick()
            row = self._db.execute("select min(next_run) from schedule").fetchone()
            wait = max_sleep if row[0] is None else min(max_sleep, max(0.0, row[0] - self.clock()))
            self._wake.clear()
            stopper = asyncio.ensure_future(stop.wait())
            waker = asyncio.ensure_future(self._wake.wait())
            await asyncio.wait({stopper, waker}, timeout=wait, return_when=asyncio.FIRST_COMPLETED)
            for f in (stopper, waker):
                f.cancel()

    def close(self) -> None:
        self._db.close()

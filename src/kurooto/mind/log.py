"""The mind log (Brain, 0.8.0): an append-only, hash-chained record of what Kurooto's mind saw and decided.

One SQLite file, `<state>/mind/log.db`, one table:

    records(seq INTEGER PRIMARY KEY, ts REAL, kind TEXT, body TEXT, prev TEXT, hash TEXT)

`body` is canonical JSON (sorted keys, no spaces); `prev` is the record before's hash (64 zeros for the first);
`hash = sha256(prev | seq | ts | kind | body)`. Changing, deleting, inserting or reordering a past record breaks the
chain at that record, and verify() names it. Rewriting the whole chain consistently is caught by the anchors: every
`mind.anchor_every` records and once a day the scorekeeper writes the head (seq, hash) to `anchors.jsonl`, and the
morning message shows it, so a log that no longer reaches an anchor you were shown, or reaches it with another hash,
fails verify().

Only the scorekeeper process writes (invariant I-1): it calls allow_writes() at its start, and a MindLog opened for
writing anywhere else raises MindWriteDenied. Everything else opens the file read-only (`mode=ro`).

What goes in: ids, kinds and numbers, never the words of a message (invariant I-11). MIRRORED lists the event kinds
copied in from Kurooto's event log (core/events.py); the scorekeeper keeps only their id-like and number fields.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

GENESIS = "0" * 64

# The event kinds mirrored into the log (core/events.py names): deadlines, reminders, calls, AI requests, buttons,
# undos, proposals, power, sleep, and Kurooto starting and stopping. Kinds ending in "_undo" / "_undone" and starting
# with "proposal_" are mirrored too (mirrored()).
MIRRORED = frozenset(
    {
        "deadline_added",
        "deadline_done",
        "deadline_moved",
        "deadline_snooze",
        "deadline_undo",
        "reminder_set",
        "reminder_fired",
        "call_rang",
        "call_rang_offline",
        "call_answered",
        "call_missed",
        "call_realert",
        "job_queued",
        "job_ended",
        "job_failed",
        "job_crashed",
        "job_cancelled",
        "button_tapped",
        "power_mode",
        "power_pause",
        "power_resume",
        "power_off",
        "lidsafe_sleep",
        "started",
        "stopped",
        "module_enabled",
        "module_disabled",
        "gate_receipt",  # stage 03: what the gate did to a message and why (ids and numbers only)
        "gate_lint",
        "gate_mute",
        "gate_call",
        "stop_span",  # stage 02: a stop, restart, sleep or unclean stop, from core/presence.py
        "kurooto_crashed",  # stage 02: the supervisor saw Kurooto end with an error
        "module_failed",
        "mind_keeper_exited",
        "read_day",  # stage 04: a day's read (its counts only: no label, no signal values)
        "read_answer",  # stage 04: that you answered (a number: right or not), never which label
        "forecast",  # stage 04: a frozen forecast (day, channels planned, its sha256; the numbers are in score.db)
        "forecast_score",  # stage 04: the mean surprise of a scored forecast
        "promise_made",  # stage 05
        "promise_kept",
        "promise_broken",
    }
)


def mirrored(kind: str) -> bool:
    """Is this event kind copied into the mind log?"""
    return kind in MIRRORED or kind.startswith("proposal_") or kind.endswith(("_undo", "_undone"))


# stage 04: facts about the day (the scorekeeper checks and files them; see scorekeeper.Keeper.mood)
MOOD_KINDS = frozenset({"signal", "read_day", "read_answer", "forecast", "score_forecast", "read_forget", "read_off"})
BUDGET_KINDS = frozenset({"budget_tick", "learning_verdict", "learning_freeze"})  # stage 05: see mind/engine.py


def accepted_fact(kind: str) -> bool:
    """A kind of fact the daemon may hand the scorekeeper: a mirrored event, a decision record or a fact about the day
    (never a score)."""
    return kind == "decision" or kind in MOOD_KINDS or kind in BUDGET_KINDS or mirrored(kind)


class MindWriteDenied(PermissionError):
    """Something other than the scorekeeper tried to write the mind log (invariant I-1)."""


_writer_pid: int | None = None


def allow_writes() -> None:
    """Called once by the scorekeeper's main(): this process may write. Nothing else calls it (test_mind_invariants)."""
    global _writer_pid
    _writer_pid = os.getpid()


def may_write() -> bool:
    return _writer_pid is not None and _writer_pid == os.getpid()


class Record(NamedTuple):
    seq: int
    ts: float
    kind: str
    body: dict
    prev: str
    hash: str


@dataclass(frozen=True)
class VerifyResult:
    ok: bool
    first_bad_seq: int | None = None  # the first record that doesn't hold (or the first missing one)
    why: str = ""
    head: int = 0  # the last seq read
    records: int = 0


def canonical(body: dict) -> str:
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def chain_hash(prev: str, seq: int, ts: float, kind: str, body: str) -> str:
    return hashlib.sha256(f"{prev}|{seq}|{ts:.6f}|{kind}|{body}".encode()).hexdigest()


SCHEMA = (
    "CREATE TABLE IF NOT EXISTS records("
    "seq INTEGER PRIMARY KEY, ts REAL NOT NULL, kind TEXT NOT NULL, body TEXT NOT NULL, prev TEXT NOT NULL, "
    "hash TEXT NOT NULL)"
)


def private(path: Path, mode: int = 0o600) -> None:
    """Owner-only (0600; 0640 in hardened mode, for the owner's group). Windows: the folder's own permissions."""
    try:
        os.chmod(path, mode)
    except OSError:
        pass


class MindLog:
    """The log file. writable=True only in the scorekeeper process (allow_writes()); otherwise read-only."""

    def __init__(self, path: Path, writable: bool = False, mode: int = 0o600):
        self.path = Path(path)
        self.writable = writable
        self._lock = threading.Lock()
        if writable:
            if not may_write():
                raise MindWriteDenied("only the scorekeeper writes the mind log")
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.db = sqlite3.connect(self.path, isolation_level=None, check_same_thread=False, timeout=10)
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.execute(SCHEMA)
            private(self.path, mode)
        else:
            self.db = None  # opened per read: a file that appears later is still found

    # ------------------------------------------------------------------------------------------ reading
    def _ro(self) -> sqlite3.Connection | None:
        if self.db is not None:
            return self.db
        if not self.path.exists():
            return None
        db = sqlite3.connect(f"{self.path.resolve().as_uri()}?mode=ro", uri=True, check_same_thread=False, timeout=10)
        return db

    def _rows(self, sql: str, args: tuple = ()) -> list[tuple]:
        db = self._ro()
        if db is None:
            return []
        try:
            return db.execute(sql, args).fetchall()
        except sqlite3.OperationalError:  # no table yet (a scorekeeper that never wrote)
            return []
        finally:
            if db is not self.db:
                db.close()

    def head(self) -> tuple[int, str]:
        rows = self._rows("SELECT seq, hash FROM records ORDER BY seq DESC LIMIT 1")
        return (int(rows[0][0]), str(rows[0][1])) if rows else (0, GENESIS)

    def read(
        self, after_seq: int = 0, kinds: set[str] | frozenset[str] | None = None, limit: int = 1000
    ) -> list[Record]:
        q, args = "SELECT seq, ts, kind, body, prev, hash FROM records WHERE seq > ?", [int(after_seq)]
        if kinds:
            q += f" AND kind IN ({','.join('?' * len(kinds))})"
            args += sorted(kinds)
        q += " ORDER BY seq LIMIT ?"
        args.append(max(1, int(limit)))
        out = []
        for seq, ts, kind, body, prev, h in self._rows(q, tuple(args)):
            try:
                b = json.loads(body)
            except ValueError:
                b = {"_unreadable": True}
            out.append(Record(int(seq), float(ts), str(kind), b, str(prev), str(h)))
        return out

    def count(self) -> int:
        rows = self._rows("SELECT COUNT(*) FROM records")
        return int(rows[0][0]) if rows else 0

    def verify(self, from_seq: int = 1, anchors: list[dict] | None = None) -> VerifyResult:
        """Walk the chain from from_seq: every seq in order with no gap, each prev the hash before it, each hash right;
        then every anchor (seq, hash) must be in it. The first that doesn't hold is first_bad_seq."""
        from_seq = max(1, int(from_seq))
        prev = GENESIS
        if from_seq > 1:
            r = self._rows("SELECT hash FROM records WHERE seq = ?", (from_seq - 1,))
            if not r:
                return VerifyResult(False, from_seq - 1, "missing")
            prev = str(r[0][0])
        expect, n, last = from_seq, 0, from_seq - 1
        db = self._ro()
        if db is not None:
            try:
                cur = db.execute(
                    "SELECT seq, ts, kind, body, prev, hash FROM records WHERE seq >= ? ORDER BY seq", (from_seq,)
                )
                for seq, ts, kind, body, p, h in cur:
                    if seq != expect:
                        return VerifyResult(False, expect, "missing", last, n)
                    if p != prev:
                        return VerifyResult(False, seq, "broken chain", last, n)
                    if chain_hash(p, seq, ts, kind, body) != h:
                        return VerifyResult(False, seq, "changed", last, n)
                    prev, expect, last, n = h, seq + 1, seq, n + 1
            except sqlite3.OperationalError:
                pass
            finally:
                if db is not self.db:
                    db.close()
        for a in anchors or []:
            try:
                aseq, ahash = int(a["seq"]), str(a["hash"])
            except (KeyError, TypeError, ValueError):
                continue
            if aseq > last:
                return VerifyResult(False, last + 1, f"cut short: an anchor reaches {aseq}", last, n)
            if aseq >= from_seq:
                r = self._rows("SELECT hash FROM records WHERE seq = ?", (aseq,))
                if not r or r[0][0] != ahash:
                    return VerifyResult(False, aseq, "rewritten: doesn't match an anchor", last, n)
        return VerifyResult(True, None, "", last, n)

    # ------------------------------------------------------------------------------------------ writing
    def append(self, kind: str, body: dict, ts: float | None = None) -> int:
        if not (self.writable and may_write()) or self.db is None:
            raise MindWriteDenied("only the scorekeeper writes the mind log")
        text = canonical(body)
        with self._lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                row = self.db.execute("SELECT seq, hash FROM records ORDER BY seq DESC LIMIT 1").fetchone()
                seq, prev = (int(row[0]) + 1, str(row[1])) if row else (1, GENESIS)
                t = round(float(ts if ts is not None else time.time()), 6)
                h = chain_hash(prev, seq, t, kind, text)
                self.db.execute("INSERT INTO records VALUES (?,?,?,?,?,?)", (seq, t, kind, text, prev, h))
                self.db.execute("COMMIT")
            except BaseException:
                self.db.execute("ROLLBACK")
                raise
        return seq

    def close(self) -> None:
        if self.db is not None:
            self.db.close()
            self.db = None


def read_anchors(mind_dir: Path) -> list[dict]:
    out = []
    try:
        lines = (Path(mind_dir) / "anchors.jsonl").read_text(encoding="utf-8").splitlines()
    except OSError:
        return out
    for ln in lines:
        try:
            a = json.loads(ln)
        except ValueError:
            continue
        if isinstance(a, dict) and "seq" in a and "hash" in a:
            out.append(a)
    return out

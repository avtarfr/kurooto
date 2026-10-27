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
        "mind_feeling",  # stage 07: a change of feeling label (ids and numbers), for the journal
        "mind_act",  # stage 07: something it did on its own (class and action id)
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
BUDGET_KINDS = frozenset(
    {
        "budget_tick",
        "learning_verdict",
        "learning_freeze",
        "trust_evidence",
        "harness_result",
        "workspace_cycle",
        "attention_check",
        "belief_outcome",
        "lab_prereg",
        "lab_result",
        "improve_event",
        "skill_event",
        "finetune_event",
        "forget_event",
        "talk_heard",  # 0.8.8 (I-3'): a message from him, only its focus/asleep/exam flags: the bounded talk reward
        "talk_unprompted",  # one of Kurooto's own unprompted messages went out (his answers in 10 minutes pay nothing)
        "talk_rejected",  # Less of this, a mute or an hour unanswered on one of them: it costs 3w
        "talk_met",  # 0.8.12: an add-on chatted with someone in the room (a quality 0..1 only): its own small budget
    }
)  # stages 05, 09 and 10: see mind/engine.py


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


# ------------------------------------------------------------------------------------------------ the imported past
# What happened before Brain was on (mind/history.py, 0.8.7): its own file, `<state>/mind/history.db`, written only by
# the scorekeeper, never mixed into the live log. One chain per source (events, jobs, deadlines ...), each in the time
# order of the original events, so a source imported later never has to go back into another's chain:
#
#     past(source, n, key, ts, kind, body, prev, hash)     PRIMARY KEY (source, n), key UNIQUE
#
# `n` counts 1, 2, 3 ... within a source; `prev` is the source's row before (64 zeros for its first); hash =
# chain_hash(prev, n, ts, "<source>/<kind>", "<key>|<body>"). A row earlier than its source's head is refused (it
# would break the time order), and a key already there is skipped, so an import is idempotent and resumes where it
# stopped. Each accepted batch leaves one `history_import` record in the live log with the source's head (n, hash):
# those are its anchors, so a rewritten past chain no longer matches what the live log witnessed.
PAST_SOURCES = ("events", "jobs", "deadlines", "checkins", "quiz", "calls", "learning", "study")
PAST_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS past(source TEXT NOT NULL, n INTEGER NOT NULL, key TEXT NOT NULL UNIQUE, ts REAL NOT "
    "NULL, kind TEXT NOT NULL, body TEXT NOT NULL, prev TEXT NOT NULL, hash TEXT NOT NULL, PRIMARY KEY(source, n))"
)


def past_hash(prev: str, source: str, n: int, ts: float, key: str, kind: str, body: str) -> str:
    return chain_hash(prev, n, ts, f"{source}/{kind}", f"{key}|{body}")


class PastLog:
    """The imported past. writable=True only in the scorekeeper process (allow_writes()); otherwise read-only."""

    def __init__(self, path: Path, writable: bool = False, mode: int = 0o600):
        self.path = Path(path)
        self.writable = writable
        self._lock = threading.Lock()
        self.db = None
        if writable:
            if not may_write():
                raise MindWriteDenied("only the scorekeeper writes the imported past")
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.db = sqlite3.connect(self.path, isolation_level=None, check_same_thread=False, timeout=10)
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.execute(PAST_SCHEMA)
            private(self.path, mode)

    def _rows(self, sql: str, args: tuple = ()) -> list[tuple]:
        db = self.db
        if db is None:
            if not self.path.exists():
                return []
            db = sqlite3.connect(f"{self.path.resolve().as_uri()}?mode=ro", uri=True, timeout=10)
        try:
            return db.execute(sql, args).fetchall()
        except sqlite3.OperationalError:
            return []
        finally:
            if db is not self.db:
                db.close()

    def head(self, source: str) -> tuple[int, float, str]:
        """(n, ts, hash) of a source's last row; (0, 0.0, GENESIS) when it has none."""
        r = self._rows("SELECT n, ts, hash FROM past WHERE source = ? ORDER BY n DESC LIMIT 1", (source,))
        return (int(r[0][0]), float(r[0][1]), str(r[0][2])) if r else (0, 0.0, GENESIS)

    def counts(self) -> dict[str, int]:
        return {str(s): int(c) for s, c in self._rows("SELECT source, COUNT(*) FROM past GROUP BY source")}

    def read(self, source: str | None = None, kinds=None, limit: int = 500_000) -> list[dict]:
        """[{source, n, key, ts, kind, body}], each source in its chain's order."""
        q, args = "SELECT source, n, key, ts, kind, body FROM past", []
        where = []
        if source:
            where.append("source = ?")
            args.append(source)
        if kinds:
            where.append(f"kind IN ({','.join('?' * len(kinds))})")
            args += sorted(kinds)
        if where:
            q += " WHERE " + " AND ".join(where)
        q += " ORDER BY source, n LIMIT ?"
        args.append(max(1, int(limit)))
        out = []
        for s, n, k, ts, kind, body in self._rows(q, tuple(args)):
            try:
                b = json.loads(body)
            except ValueError:
                b = {}
            out.append({"source": s, "n": int(n), "key": k, "ts": float(ts), "kind": kind, "body": b})
        return out

    def verify(self, witnessed: list[dict] | None = None) -> dict:
        """Every source's chain: n 1, 2, 3 ... with no gap, each prev the hash before it, each hash right, the times
        never going back; then every witnessed head (source, n, hash) from the live log must still be in it.
        {ok, sources: {source: rows}, bad: {source, n, why} | None}."""
        sources: dict[str, int] = {}
        db = self.db
        if db is None and self.path.exists():
            db = sqlite3.connect(f"{self.path.resolve().as_uri()}?mode=ro", uri=True, timeout=10)
        if db is not None:
            try:
                cur = db.execute("SELECT source, n, key, ts, kind, body, prev, hash FROM past ORDER BY source, n")
                src, prev, expect, last_ts = None, GENESIS, 1, 0.0
                for s, n, k, ts, kind, body, p, h in cur:
                    if s != src:
                        src, prev, expect, last_ts = s, GENESIS, 1, 0.0
                    if n != expect:
                        return {"ok": False, "sources": sources, "bad": {"source": s, "n": expect, "why": "missing"}}
                    if p != prev:
                        return {"ok": False, "sources": sources, "bad": {"source": s, "n": n, "why": "broken chain"}}
                    if ts < last_ts:
                        return {"ok": False, "sources": sources, "bad": {"source": s, "n": n, "why": "out of order"}}
                    if past_hash(p, s, n, ts, k, kind, body) != h:
                        return {"ok": False, "sources": sources, "bad": {"source": s, "n": n, "why": "changed"}}
                    prev, expect, last_ts = h, n + 1, ts
                    sources[s] = n
            except sqlite3.OperationalError:
                pass
            finally:
                if db is not self.db:
                    db.close()
        for w in witnessed or []:
            s, n, h = str(w.get("source") or ""), int(w.get("n") or 0), str(w.get("head") or "")
            if not n:
                continue
            if n > sources.get(s, 0):
                return {"ok": False, "sources": sources, "bad": {"source": s, "n": n, "why": "cut short"}}
            r = self._rows("SELECT hash FROM past WHERE source = ? AND n = ?", (s, n))
            if not r or r[0][0] != h:
                return {"ok": False, "sources": sources, "bad": {"source": s, "n": n, "why": "rewritten"}}
        return {"ok": True, "sources": sources, "bad": None}

    # ------------------------------------------------------------------------------------------ writing
    def _w(self) -> sqlite3.Connection:
        if not (self.writable and may_write()) or self.db is None:
            raise MindWriteDenied("only the scorekeeper writes the imported past")
        return self.db

    def append_many(self, source: str, rows: list[tuple[str, float, str, dict]]) -> dict:
        """Add (key, ts, kind, body) rows to a source's chain, in the order given. A key already there is skipped
        (`dup`); a row earlier than the chain's head is refused (`late`). {added, dup, late, n, head, from, to}."""
        db = self._w()
        added = dup = late = 0
        lo = hi = None
        with self._lock:
            db.execute("BEGIN IMMEDIATE")
            try:
                r = db.execute("SELECT n, ts, hash FROM past WHERE source = ? ORDER BY n DESC LIMIT 1", (source,))
                row = r.fetchone()
                n, last_ts, prev = (int(row[0]), float(row[1]), str(row[2])) if row else (0, 0.0, GENESIS)
                for key, ts, kind, body in rows:
                    if db.execute("SELECT 1 FROM past WHERE key = ?", (key,)).fetchone():
                        dup += 1
                        continue
                    t = round(float(ts), 6)
                    if t < last_ts:
                        late += 1
                        continue
                    text = canonical(body)
                    h = past_hash(prev, source, n + 1, t, key, kind, text)
                    db.execute(
                        "INSERT INTO past VALUES (?,?,?,?,?,?,?,?)", (source, n + 1, key, t, kind, text, prev, h)
                    )
                    n, prev, last_ts = n + 1, h, t
                    added += 1
                    lo = t if lo is None else lo
                    hi = t
                db.execute("COMMIT")
            except BaseException:
                db.execute("ROLLBACK")
                raise
        return {"added": added, "dup": dup, "late": late, "n": n, "head": prev, "from": lo, "to": hi}

    def drop(self, source: str | None = None) -> int:
        db = self._w()
        with self._lock:
            if source:
                cur = db.execute("DELETE FROM past WHERE source = ?", (source,))
            else:
                cur = db.execute("DELETE FROM past")
            return cur.rowcount or 0

    def close(self) -> None:
        if self.db is not None:
            self.db.close()
            self.db = None

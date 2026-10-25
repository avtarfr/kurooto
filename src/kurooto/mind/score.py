"""The scorekeeper's tables (Brain, 0.8.0): `<state>/mind/score.db`.

    setpoints  the target level of each variable the mind keeps in balance (stage 05)
    vars       the body budget's variables, their levels now (stage 05)
    values     the learned value of each kind of action (stage 05)
    trust      the trust in each risk class of action (stage 06)
    signals    the day's numbers the read is made from (stage 04): key "YYYY-MM-DD:name", kept 30 days
    reads       what the read said each day and what you answered, and the calibration pairs (stage 04)

Each table is (key TEXT PRIMARY KEY, value REAL, meta TEXT JSON, at REAL). Only the scorekeeper process opens it for
writing (log.may_write(), invariant I-1); everything else reads it with `mode=ro` through the mind client. In stage 01
the tables exist and stay empty: nothing scores yet.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path

from kurooto.mind.log import MindWriteDenied, may_write, private

TABLES = ("setpoints", "vars", "values", "trust", "signals", "reads", "history")


class Score:
    def __init__(self, path: Path, writable: bool = False, mode: int = 0o600):
        self.path = Path(path)
        self.writable = writable
        self._lock = threading.Lock()
        self.db = None
        if writable:
            if not may_write():
                raise MindWriteDenied("only the scorekeeper writes the mind's scores")
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.db = sqlite3.connect(self.path, isolation_level=None, check_same_thread=False, timeout=10)
            self.db.execute("PRAGMA journal_mode=WAL")
            for t in TABLES:
                self.db.execute(
                    f'CREATE TABLE IF NOT EXISTS "{t}"(key TEXT PRIMARY KEY, value REAL, meta TEXT, at REAL)'  # noqa: S608
                )
            private(self.path, mode)

    def get(self, table: str, key: str) -> dict | None:
        if table not in TABLES:
            return None
        db = self.db
        if db is None:
            if not self.path.exists():
                return None
            db = sqlite3.connect(f"{self.path.resolve().as_uri()}?mode=ro", uri=True, timeout=10)
        try:
            row = db.execute(f'SELECT value, meta, at FROM "{table}" WHERE key = ?', (str(key),)).fetchone()  # noqa: S608
        except sqlite3.OperationalError:
            return None
        finally:
            if db is not self.db:
                db.close()
        if row is None:
            return None
        try:
            meta = json.loads(row[1]) if row[1] else {}
        except ValueError:
            meta = {}
        return {"value": row[0], "meta": meta, "at": row[2]}

    def rows(self, table: str, prefix: str = "", limit: int = 5000) -> list[dict]:
        """Rows whose key starts with prefix, oldest key first: [{key, value, meta, at}]."""
        if table not in TABLES:
            return []
        db = self.db
        if db is None:
            if not self.path.exists():
                return []
            db = sqlite3.connect(f"{self.path.resolve().as_uri()}?mode=ro", uri=True, timeout=10)
        try:
            cur = db.execute(
                f'SELECT key, value, meta, at FROM "{table}" WHERE substr(key, 1, ?) = ? ORDER BY key LIMIT ?',  # noqa: S608
                (len(prefix), prefix, int(limit)),
            )
            out = []
            for k, v, m, a in cur.fetchall():
                try:
                    meta = json.loads(m) if m else {}
                except ValueError:
                    meta = {}
                out.append({"key": k, "value": v, "meta": meta, "at": a})
            return out
        except sqlite3.OperationalError:
            return []
        finally:
            if db is not self.db:
                db.close()

    def _purge(self, table: str, prefix: str, older_than: float) -> int:
        """Scorekeeper only: delete the rows of this kind last written before older_than (retention)."""
        if not (self.writable and may_write()) or self.db is None or table not in TABLES:
            raise MindWriteDenied("only the scorekeeper writes the mind's scores")
        with self._lock:
            cur = self.db.execute(
                f'DELETE FROM "{table}" WHERE substr(key, 1, ?) = ? AND at < ?',  # noqa: S608
                (len(prefix), prefix, float(older_than)),
            )
            return cur.rowcount or 0

    def _drop(self, table: str, key_prefix: str) -> int:
        """Scorekeeper only: delete rows by key (Forget this, and turning the read off)."""
        if not (self.writable and may_write()) or self.db is None or table not in TABLES:
            raise MindWriteDenied("only the scorekeeper writes the mind's scores")
        with self._lock:
            cur = self.db.execute(
                f'DELETE FROM "{table}" WHERE substr(key, 1, ?) = ?',  # noqa: S608
                (len(key_prefix), key_prefix),
            )
            return cur.rowcount or 0

    def snapshot(self) -> dict[str, int]:
        """How many rows each table holds (what /mind shows, and what tests compare)."""
        out = {}
        for t in TABLES:
            db = self.db
            if db is None:
                if not self.path.exists():
                    return {t: 0 for t in TABLES}
                db = sqlite3.connect(f"{self.path.resolve().as_uri()}?mode=ro", uri=True, timeout=10)
            try:
                out[t] = int(db.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0])  # noqa: S608
            except sqlite3.OperationalError:
                out[t] = 0
            finally:
                if db is not self.db:
                    db.close()
        return out

    def _put(self, table: str, key: str, value: float, meta: dict | None = None) -> None:
        """Scorekeeper code paths only (stage 05 on): there is no request that reaches this from outside."""
        if not (self.writable and may_write()) or self.db is None or table not in TABLES:
            raise MindWriteDenied("only the scorekeeper writes the mind's scores")
        with self._lock:
            self.db.execute(
                f'INSERT OR REPLACE INTO "{table}" VALUES (?,?,?,?)',  # noqa: S608
                (str(key), float(value), json.dumps(meta or {}, sort_keys=True), time.time()),
            )

    def close(self) -> None:
        if self.db is not None:
            self.db.close()
            self.db = None

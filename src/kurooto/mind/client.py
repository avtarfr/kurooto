"""The mind client (Brain, 0.8.0): how the rest of Kurooto reads the mind, and its one way to tell it something.

Reads go straight to the files, read-only (`mode=ro`): state(), log(), value(), trust(), setpoint(), verify(). The one
write is report(kind, body): a plain fact (a mirrored event, a decision record) handed to the scorekeeper, which checks
it and alone writes it (invariant I-1). There is no method that sets a score, a setpoint, trust or a reward, and the
scorekeeper refuses any request that tries.

report() never blocks and never fails the caller: facts wait in a queue for a sender thread; when the scorekeeper
can't be reached they go to `spool.jsonl`, which it takes in when it's back. A full queue drops the newest fact and
counts it (`dropped` in state()).
"""

from __future__ import annotations

import json
import queue
import threading
import time
from multiprocessing.connection import Client
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto.mind import log as mlog
from kurooto.mind import records
from kurooto.mind.score import Score

if TYPE_CHECKING:
    from kurooto.app import App

QUEUE_MAX = 10_000
REPLY_S = 10.0  # a reply from the scorekeeper is waited for this long, then the fact goes to the spool
ALIVE_MAX_S = 30.0  # `alive` older than this: the scorekeeper isn't running
SPOOL_MAX = 20_000_000  # bytes; past this the spool takes no more (facts are counted as dropped)


def mind_dir(app: App) -> Path:
    return app.paths.state / "mind"


class MindClient:
    def __init__(self, app: App):
        self.app = app
        self.dir = mind_dir(app)
        self._q: queue.Queue = queue.Queue(maxsize=QUEUE_MAX)
        self._thread: threading.Thread | None = None
        self._start = threading.Lock()
        self._conn = None
        self.dropped = 0
        self.spooled = 0
        self.sent = 0

    # ------------------------------------------------------------------------------------------- reading
    def _log(self) -> mlog.MindLog:
        return mlog.MindLog(self.dir / "log.db")

    def _score(self) -> Score:
        return Score(self.dir / "score.db")

    def running(self) -> tuple[bool, int]:
        """(running, its pid): the endpoint names a live process and it touched `alive` lately."""
        try:
            ep = json.loads((self.dir / "endpoint.json").read_text(encoding="utf-8"))
            pid = int(ep.get("pid") or 0)
            fresh = time.time() - (self.dir / "alive").stat().st_mtime < ALIVE_MAX_S
        except (OSError, ValueError, TypeError):
            return False, 0
        if not fresh or not pid:
            return False, pid
        try:
            import psutil

            return psutil.pid_exists(pid), pid
        except Exception:
            return True, pid

    def state(self) -> dict:
        lg = self._log()
        seq, h = lg.head()
        anchors = mlog.read_anchors(self.dir)
        up, pid = self.running()
        return {
            "running": up,
            "pid": pid,
            "head": seq,
            "hash": h,
            "records": lg.count(),
            "anchor": anchors[-1] if anchors else None,
            "scores": self._score().snapshot(),
            "queued": self._q.qsize(),
            "waiting": self.waiting(),
            "sent": self.sent,
            "spooled": self.spooled,
            "dropped": self.dropped,
        }

    def waiting(self) -> int:
        """Facts kept aside for the scorekeeper right now (lines in the spool)."""
        try:
            with open(self.dir / "spool.jsonl", "rb") as f:
                return sum(1 for _ in f)
        except OSError:
            return 0

    def log(self, after: int = 0, kinds=None, limit: int = 1000) -> list[mlog.Record]:
        return self._log().read(after, frozenset(kinds) if kinds else None, limit)

    def value(self, action: str) -> dict | None:
        return self._score().get("values", action)

    def trust(self, cls: str) -> dict | None:
        return self._score().get("trust", cls)

    def setpoint(self, name: str) -> dict | None:
        return self._score().get("setpoints", name)

    # ------------------------------------------------------------------------------- the day's numbers (stage 04)
    def signal_days(self) -> dict[str, dict[str, float]]:
        """{day: {signal: value}} for every day the scorekeeper holds numbers for (30 days at most)."""
        out: dict[str, dict[str, float]] = {}
        for r in self._score().rows("signals", ""):
            day, _, name = r["key"].partition(":")
            out.setdefault(day, {})[name] = r["value"]
        return out

    def trust_rows(self, prefix: str = "") -> list[dict]:
        """Rows of the trust table: one per class of action, its Beta counts and evidence in `meta` (read-only)."""
        return self._score().rows("trust", prefix)

    def vars_rows(self, prefix: str = "") -> list[dict]:
        """Rows of the body budget's `vars` table (x:<name>, D, tonic, neg, negd:<class> ...), read-only."""
        return self._score().rows("vars", prefix)

    def values_rows(self, prefix: str = "") -> list[dict]:
        """Rows of the learned values (V:<state>, Q:<state>|<action class>), read-only."""
        return self._score().rows("values", prefix)

    def mood_rows(self, prefix: str = "") -> list[dict]:
        """Rows of the mood table: read:<day>, answer:<day>, cal:<day>, forecast:<day>, score:<day>."""
        return self._score().rows("reads", prefix)

    def history_rows(self, prefix: str = "h:", limit: int = 200000) -> list[dict]:
        """The imported past (0.8.1): [{key, value: when, meta: {k: kind, ...ids and numbers}}], oldest key first."""
        return self._score().rows("history", prefix, limit)

    def request(self, op: str, **kw) -> dict:
        """One request to the scorekeeper and its answer ({} when it can't be reached): the import."""
        conn = None
        try:
            conn = self._connect()
            conn.send_bytes(json.dumps({"op": op, **kw}).encode())
            if not conn.poll(30):
                return {}
            return json.loads(conn.recv_bytes())
        except Exception:
            return {}
        finally:
            if conn is not None:
                try:
                    conn.close()
                except OSError:
                    pass

    def verify(self, from_seq: int = 1) -> mlog.VerifyResult:
        return self._log().verify(from_seq, mlog.read_anchors(self.dir))

    # ------------------------------------------------------------------------------------------- the one write
    def report(self, kind: str, body: dict) -> bool:
        """Hand a fact to the scorekeeper (later, on a thread of its own). False when the kind isn't one it takes or
        the queue is full; never raises, never waits."""
        if not mlog.accepted_fact(kind):
            return False
        clean = (
            records.plain(body or {})
            if kind in mlog.MOOD_KINDS | mlog.BUDGET_KINDS
            else records.clean_fact(kind, body or {})
        )
        fact = {"kind": kind, "body": clean, "ts": round(time.time(), 3)}
        try:
            self._q.put_nowait(fact)
        except queue.Full:
            self.dropped += 1
            return False
        self._ensure_thread()
        return True

    def _ensure_thread(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        with self._start:
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._sender, name="mind-report", daemon=True)
                self._thread.start()

    def _connect(self):
        ep = json.loads((self.dir / "endpoint.json").read_text(encoding="utf-8"))
        key = bytes.fromhex((self.dir / "key").read_text(encoding="utf-8").strip())
        return Client(("127.0.0.1", int(ep["port"])), authkey=key)

    def _send(self, fact: dict) -> bool:
        try:
            if self._conn is None:
                self._conn = self._connect()
            self._conn.send_bytes(json.dumps({"op": "append", **fact}).encode())
            if not self._conn.poll(REPLY_S):
                raise TimeoutError
            res = json.loads(self._conn.recv_bytes())
            return bool(res.get("ok"))
        except Exception:
            self._drop_conn()
            return False

    def _drop_conn(self) -> None:
        c, self._conn = self._conn, None
        if c is not None:
            try:
                c.close()
            except OSError:
                pass

    def _spool(self, fact: dict) -> None:
        f = self.dir / "spool.jsonl"
        try:
            if f.exists() and f.stat().st_size > SPOOL_MAX:
                self.dropped += 1
                return
            self.dir.mkdir(parents=True, exist_ok=True)
            new = not f.exists()
            with open(f, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(fact, ensure_ascii=False) + "\n")
            if new:
                mlog.private(f)
            self.spooled += 1
        except OSError:
            self.dropped += 1

    def _sender(self) -> None:
        while True:
            fact = self._q.get()
            try:
                if fact is None:
                    return
                if self._send(fact):
                    self.sent += 1
                else:
                    self._spool(fact)
            finally:
                self._q.task_done()

    def flush(self, timeout: float = 5.0) -> bool:
        """Wait until the queue is empty (tests, and before Brain is turned off). True if it emptied."""
        end = time.monotonic() + timeout
        while self._q.unfinished_tasks:
            if self._thread is None or not self._thread.is_alive() or time.monotonic() > end:
                return not self._q.unfinished_tasks
            time.sleep(0.02)
        return True

    def close(self) -> None:
        t = self._thread
        if t is not None and t.is_alive():
            try:
                self._q.put_nowait(None)
            except queue.Full:
                pass
            t.join(timeout=2)
        self._drop_conn()

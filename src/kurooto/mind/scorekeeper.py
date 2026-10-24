"""The scorekeeper (Brain, 0.8.0): the one process that writes the mind log and the mind's scores (invariant I-1).

    python -m kurooto.mind.scorekeeper --dir <state>/mind [--parent PID] [--anchor-every N] [--hardened]

modules/mind.py starts it, restarts it if it dies (with a growing wait) and ends it with Kurooto; with --parent it also
ends by itself within a few seconds of Kurooto going away. In the optional hardened mode (tools/mind_harden.sh) it runs
as its own system user under systemd or launchd instead, and its files are readable by the owner's group (0640).

Talking to it: a socket on 127.0.0.1 with a random key per start (multiprocessing.connection with an authkey), JSON
both ways (never pickles, which could run code here). The
port is in `endpoint.json`, the key in `key`, both 0600 (0640 hardened). Requests are dicts with an "op":

    append  {kind, body}         a fact: only ACCEPTED_FROM_DAEMON kinds (mirrored events, decision records), and only
                                 their id and number fields (records.clean_fact): facts, never scores
    get     {table, key}         a row of score.db
    log     {after, kinds, limit}
    verify  {from}               the chain, and the anchors
    head / ping

Anything else is refused and the refusal is logged: there is no request that sets a setpoint, a value, trust or a
reward. Those change only through this process's own code paths, from approved sources (stage 05 on).

When it can't be reached, the daemon's client writes facts to `spool.jsonl`; this process takes them in at start and
within seconds whenever there are any (each checked like an append). Anchors: every --anchor-every records and once a
day, the head goes to `anchors.jsonl`. `alive` is touched every few seconds, so /mind can tell it's running without
asking it.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import signal
import sys
import threading
import time
from multiprocessing.connection import Listener
from pathlib import Path

from kurooto.mind import log as mlog
from kurooto.mind import records
from kurooto.mind.score import TABLES, Score

ACCEPTED_FROM_DAEMON = frozenset({*mlog.MIRRORED, "decision"})
ALIVE_S = 5.0  # `alive` is touched this often
CHECK_S = 60.0  # the spool and the daily anchor are looked at this often
PARENT_S = 2.0  # with --parent: how often it checks Kurooto is still there
LIMIT_MAX = 5000  # the most records one `log` request returns
MSG_MAX = 1 << 20  # a request is at most this many bytes (a longer one ends the conversation)


def accepted(kind: str) -> bool:
    return kind in ACCEPTED_FROM_DAEMON or mlog.accepted_fact(kind)


def _clip(s, n: int = 40) -> str:
    return str(s or "")[:n]


class Keeper:
    """The tables and the log, and what each request may do with them."""

    def __init__(self, mind_dir: Path, anchor_every: int = 1000, hardened: bool = False):
        mlog.allow_writes()
        self.dir = Path(mind_dir)
        self.mode = 0o640 if hardened else 0o600
        self.dir.mkdir(parents=True, exist_ok=True)
        mlog.private(self.dir, 0o750 if hardened else 0o700)
        self.log = mlog.MindLog(self.dir / "log.db", writable=True, mode=self.mode)
        self.score = Score(self.dir / "score.db", writable=True, mode=self.mode)
        self.anchor_every = max(10, int(anchor_every or 1000))
        self.lock = threading.Lock()

    # -------------------------------------------------------------------------------------------- requests
    def handle(self, req) -> dict:
        if not isinstance(req, dict):
            return self.refuse("not a request")
        op = req.get("op")
        if op == "append":
            return self.append(str(req.get("kind") or ""), req.get("body"))
        if op == "get":
            table, key = str(req.get("table") or ""), str(req.get("key") or "")
            if table not in TABLES:
                return {"error": "no such table"}
            return {"ok": True, "row": self.score.get(table, key)}
        if op == "log":
            kinds = req.get("kinds")
            rows = self.log.read(
                int(req.get("after") or 0),
                frozenset(map(str, kinds)) if kinds else None,
                min(LIMIT_MAX, int(req.get("limit") or 1000)),
            )
            return {"ok": True, "records": [r._asdict() for r in rows]}
        if op == "verify":
            r = self.log.verify(int(req.get("from") or 1), mlog.read_anchors(self.dir))
            return {"ok": True, "verify": r.__dict__}
        if op in ("head", "ping"):
            seq, h = self.log.head()
            return {"ok": True, "head": [seq, h], "pid": os.getpid()}
        return self.refuse(_clip(op) or "nothing")

    def refuse(self, what: str) -> dict:
        """Any other request (to set a score, a setpoint, trust): refused, and the attempt kept in the log."""
        with self.lock:
            self.log.append("refused", {"op": records.ID.match(what) and what or "other"})
        return {"error": "refused"}

    def append(self, kind: str, body, ts: float | None = None) -> dict:
        if not accepted(kind):
            return self.refuse(f"append:{kind}"[:40] if records.ID.match(kind or "x") else "append")
        clean = records.clean_fact(kind, body if isinstance(body, dict) else {})
        if kind == "decision" and not clean:
            return {"error": "not a decision record"}
        if ts is not None:  # a fact from the spool: when it happened, as a number
            clean["at"] = round(float(ts), 3)
        with self.lock:
            seq = self.log.append(kind, clean)
            if seq % self.anchor_every == 0:
                self.anchor("every")
        return {"ok": True, "seq": seq}

    # -------------------------------------------------------------------------------------------- anchors
    def anchor(self, why: str) -> dict | None:
        seq, h = self.log.head()
        if seq == 0:
            return None
        a = {"seq": seq, "hash": h, "at": dt.datetime.now().astimezone().isoformat(timespec="seconds"), "why": why}
        f = self.dir / "anchors.jsonl"
        with open(f, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(a) + "\n")
        mlog.private(f, self.mode)
        return a

    def daily(self) -> None:
        """Once a day (the first check after midnight): an anchor, if anything was written since the last one."""
        anchors = mlog.read_anchors(self.dir)
        last = anchors[-1] if anchors else None
        today = dt.date.today().isoformat()
        seq, _ = self.log.head()
        if seq and (last is None or (str(last.get("at", ""))[:10] != today and int(last["seq"]) != seq)):
            with self.lock:
                self.anchor("daily")

    # -------------------------------------------------------------------------------------------- the spool
    def take_spool(self) -> int:
        """Facts the daemon kept while this process was away: each checked like an append, then the file goes."""
        spool = self.dir / "spool.jsonl"
        if not spool.exists():
            return 0
        took = self.dir / f"spool.{os.getpid()}.taking"
        try:
            os.replace(spool, took)
        except OSError:
            return 0
        n = 0
        try:
            for ln in took.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    item = json.loads(ln)
                    kind, body, ts = str(item.get("kind") or ""), item.get("body"), item.get("ts")
                    ts = float(ts) if isinstance(ts, (int, float)) else None
                except (ValueError, AttributeError, TypeError):
                    continue
                if self.append(kind, body, ts).get("ok"):
                    n += 1
        finally:
            took.unlink(missing_ok=True)
        return n

    def close(self) -> None:
        self.log.close()
        self.score.close()


def _write_private(path: Path, text: str, mode: int) -> None:
    """Written whole and private from the start (created 0600, then renamed into place)."""
    tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    mlog.private(tmp, mode)
    os.replace(tmp, path)


def serve(keeper: Keeper, stop: threading.Event) -> None:
    """Listen on 127.0.0.1 (a free port) with a fresh key until stop is set."""
    key = os.urandom(32)
    listener = Listener(("127.0.0.1", 0), authkey=key)
    port = listener.address[1]
    _write_private(keeper.dir / "key", key.hex(), keeper.mode)
    _write_private(
        keeper.dir / "endpoint.json", json.dumps({"port": port, "pid": os.getpid(), "since": time.time()}), keeper.mode
    )

    def conversation(conn) -> None:
        with conn:
            while not stop.is_set():
                try:  # JSON, never pickles: a pickle could run code in this process (the reason it's separate)
                    req = json.loads(conn.recv_bytes(MSG_MAX))
                except (EOFError, OSError):
                    return
                except (ValueError, UnicodeDecodeError):
                    req = None
                try:
                    res = keeper.handle(req)
                except Exception as e:
                    res = {"error": f"{type(e).__name__}"}
                try:
                    conn.send_bytes(json.dumps(res, default=str).encode())
                except OSError:
                    return

    def accept() -> None:
        while not stop.is_set():
            try:
                conn = listener.accept()
            except OSError:
                if stop.is_set():
                    return
                continue
            except Exception:  # noqa: S112 (a wrong key: AuthenticationError; a client gone mid-handshake)
                continue
            threading.Thread(target=conversation, args=(conn,), name="mind-conn", daemon=True).start()

    threading.Thread(target=accept, name="mind-accept", daemon=True).start()
    try:
        stop.wait()
    finally:
        try:
            listener.close()
        except OSError:
            pass
        for name in ("endpoint.json", "key"):
            (keeper.dir / name).unlink(missing_ok=True)


def _parent_gone(pid: int) -> bool:
    try:
        import psutil

        return not psutil.pid_exists(pid)
    except Exception:
        return False


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="kurooto.mind.scorekeeper", description="Brain's scorekeeper (see module doc)")
    ap.add_argument("--dir", required=True, help="the mind's folder (<state>/mind)")
    ap.add_argument("--parent", type=int, default=0, help="end when this process (Kurooto) has gone")
    ap.add_argument("--anchor-every", type=int, default=1000)
    ap.add_argument("--hardened", action="store_true", help="files readable by the owner's group (mind_harden.sh)")
    a = ap.parse_args(argv)
    if hasattr(os, "umask"):  # every file it makes (the databases' -wal and -shm too) starts private
        os.umask(0o027 if a.hardened else 0o077)
    mind_dir = Path(a.dir)
    mind_dir.mkdir(parents=True, exist_ok=True)

    from filelock import FileLock, Timeout

    lock = FileLock(str(mind_dir / "scorekeeper.lock"))
    try:
        lock.acquire(timeout=0)
    except Timeout:
        print("another scorekeeper is running for this folder", file=sys.stderr)
        return 3
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(sig, lambda *_: stop.set())
        except (ValueError, OSError):
            pass
    keeper = Keeper(mind_dir, a.anchor_every, a.hardened)
    with keeper.lock:
        keeper.log.append("keeper_started", {"pid": os.getpid(), "hardened": bool(a.hardened)})
    keeper.take_spool()

    def chores() -> None:
        last_check = 0.0
        alive = mind_dir / "alive"
        while not stop.is_set():
            try:
                alive.touch()
            except OSError:
                pass
            if a.parent and _parent_gone(a.parent):
                stop.set()
                return
            try:
                if (mind_dir / "spool.jsonl").exists():  # facts kept aside while it was away: in within seconds
                    keeper.take_spool()
            except Exception as e:
                print(f"spool: {type(e).__name__}: {e}", file=sys.stderr)
            if time.monotonic() - last_check >= CHECK_S:
                last_check = time.monotonic()
                try:
                    keeper.daily()
                except Exception as e:
                    print(f"chores: {type(e).__name__}: {e}", file=sys.stderr)
            stop.wait(min(ALIVE_S, PARENT_S) if a.parent else ALIVE_S)

    threading.Thread(target=chores, name="mind-chores", daemon=True).start()
    try:
        serve(keeper, stop)
    finally:
        try:
            with keeper.lock:
                keeper.log.append("keeper_stopped", {"pid": os.getpid()})
        except Exception:
            pass
        keeper.close()
        (mind_dir / "alive").unlink(missing_ok=True)
        lock.release()
    return 0


if __name__ == "__main__":
    sys.exit(main())

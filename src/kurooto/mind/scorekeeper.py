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
import re
import signal
import sys
import threading
import time
from multiprocessing.connection import Listener
from pathlib import Path

from kurooto.mind import engine as eng
from kurooto.mind import forecast as fc
from kurooto.mind import log as mlog
from kurooto.mind import read as rd
from kurooto.mind import records, stops
from kurooto.mind.score import TABLES, Score

# stage 04: facts about the day, handled here (stored in score.db with a retention, not copied whole into the log)
MOOD_KINDS = mlog.MOOD_KINDS
BUDGET_KINDS = mlog.BUDGET_KINDS
ACCEPTED_FROM_DAEMON = frozenset({*mlog.MIRRORED, "decision", *MOOD_KINDS, *BUDGET_KINDS})
SIGNALS_KEEP_S = 30 * 86400
ANSWER_KEEP_S = 7 * 86400
CAL_KEEP = 200  # calibration pairs (strength, right), no dates or words
STOP_KINDS = frozenset({"stop_span", "power_pause", "power_resume", "module_disabled", "module_enabled"})
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
        self.engine = eng.Engine(self)

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
        if kind in MOOD_KINDS:
            return self.day_fact(kind, body if isinstance(body, dict) else {})
        if kind in BUDGET_KINDS:
            return self.budget_fact(kind, records.plain(body) if isinstance(body, dict) else {}, ts)
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

    # -------------------------------------------------------------------------------------------- stage 04: the read
    def day_fact(self, kind: str, b: dict) -> dict:
        """The day's numbers, the read, your answer and the forecast. Each is checked here; the read, the answer and the
        forecast keep only counts, ids and a hash in the log, and the rest in score.db, where it has a retention and
        Forget this / turning the read off remove it."""
        day = str(b.get("day") or "")
        if kind in (
            "signal",
            "read_day",
            "read_answer",
            "forecast",
            "score_forecast",
            "read_forget",
        ) and not records.DAY.match(day):
            return {"error": "bad day"}
        with self.lock:
            if kind == "signal":
                name = str(b.get("name") or "")
                if (
                    name not in (*rd.SIGNALS, *rd.LOAD_SIGNALS)
                    or not isinstance(b.get("value"), (int, float))
                    or isinstance(b.get("value"), bool)
                ):
                    return {"error": "not a signal"}
                v = float(b["value"])
                if not -1e6 < v < 1e6:
                    return {"error": "not a signal"}
                self.score._put("signals", f"{day}:{name}", v)
                return {"ok": True}
            if kind == "read_day":
                votes = [
                    [str(n)[:20], round(float(z), 3)]
                    for n, z in (b.get("votes") or [])
                    if isinstance(n, str) and isinstance(z, (int, float))
                ][:8]
                ev = {
                    str(k): round(float(z), 3)
                    for k, z in (b.get("evidence") or {}).items()
                    if str(k) in rd.SIGNALS and isinstance(z, (int, float))
                }
                label = str(b.get("label") or "")
                label = label if label in rd.LABELS else "steady"
                meta = {"label": label, "votes": votes, "evidence": ev, "confidence": b.get("confidence")}
                meta["confidence"] = (
                    round(float(meta["confidence"]), 3) if isinstance(meta["confidence"], (int, float)) else None
                )
                strength = round(float(b.get("strength") or 0.0), 4)
                self.score._put("reads", f"read:{day}", strength, {**meta, "counted": bool(b.get("counted"))})
                seq = self.log.append(
                    "read_day",
                    records.clean_fact(
                        "read_day",
                        {"day": day, "n_votes": len(votes), "counted": bool(b.get("counted")), "strength": strength},
                    ),
                )
                return {"ok": True, "seq": seq}
            if kind == "read_answer":
                right = bool(b.get("right"))
                strength = round(float(b.get("strength") or 0.0), 4)
                self.score._put(
                    "reads", f"answer:{day}", 1.0 if right else 0.0, {"label": str(b.get("label") or "")[:12]}
                )
                self.score._put("reads", f"cal:{day}", strength, {"right": right})  # no label, no words
                seq = self.log.append(
                    "read_answer", records.clean_fact("read_answer", {"day": day, "right": right, "strength": strength})
                )
                return {"ok": True, "seq": seq}
            if kind == "forecast":
                params = b.get("params") if isinstance(b.get("params"), dict) else {}
                clean = {
                    k: [float(x) for x in v][:8]
                    for k, v in params.items()
                    if k in fc.CHANNELS and isinstance(v, list) and v and all(isinstance(x, (int, float)) for x in v)
                }
                if not clean:
                    return {"error": "no parameters"}
                rec = fc.freeze(day, clean, b.get("planned") or (), bool(b.get("holdout")))
                if self.score.get("reads", f"forecast:{day}"):
                    return {"ok": True, "frozen": True}  # once frozen, it isn't replaced
                self.score._put("reads", f"forecast:{day}", 1.0, rec)
                seq = self.log.append(
                    "forecast",
                    records.clean_fact(
                        "forecast",
                        {"day": day, "hash": rec["hash"], "planned": rec["planned"], "holdout": rec["holdout"]},
                    ),
                )
                return {"ok": True, "seq": seq, "hash": rec["hash"]}
            if kind == "score_forecast":
                return self._score_forecast(day)
            if kind == "read_forget":
                n = sum(
                    self.score._drop(t, p)
                    for t, p in (
                        ("signals", f"{day}:"),
                        ("reads", f"read:{day}"),
                        ("reads", f"answer:{day}"),
                        ("reads", f"cal:{day}"),
                        ("reads", f"forecast:{day}"),
                        ("reads", f"score:{day}"),
                    )
                )
                return {"ok": True, "dropped": n}
            if kind == "read_off":
                n = self.score._drop("signals", "") + self.score._drop("reads", "")
                return {"ok": True, "dropped": n}
        return {"error": "unknown"}

    def _score_forecast(self, day: str) -> dict:
        """Score the frozen forecast for `day` against the numbers stored for it: from this process's own data only."""
        row = self.score.get("reads", f"forecast:{day}")
        if not row or not isinstance(row.get("meta"), dict) or not fc.check(row["meta"]):
            return {"error": "no frozen forecast"}
        if self.score.get("reads", f"score:{day}"):
            return {"ok": True, "scored": True}
        observed = {r["key"].split(":", 1)[1]: r["value"] for r in self.score.rows("signals", f"{day}:")}
        d = dt.date.fromisoformat(day)
        same: dict = {}
        for k in range(1, 5):
            past = (d - dt.timedelta(days=7 * k)).isoformat()
            for r in self.score.rows("signals", f"{past}:"):
                same.setdefault(r["key"].split(":", 1)[1], []).insert(0, r["value"])
        scored = fc.score(row["meta"], observed, same)
        if not scored:
            return {"error": "nothing observed"}
        mean = fc.mean_surprise(scored)
        self.score._put("reads", f"score:{day}", mean or 0.0, {"channels": scored})
        seq = self.log.append(
            "forecast_score",
            records.clean_fact("forecast_score", {"day": day, "n": len(scored), "mean_surprise": mean}),
        )
        return {"ok": True, "seq": seq}

    def budget_fact(self, kind: str, b: dict, ts: float | None = None) -> dict:
        """The body budget's inputs (mind/engine.py): measurements of Kurooto's own state, never scores."""
        with self.lock:
            if kind == "budget_tick":
                return self.engine.tick(b, ts)
            if kind == "learning_verdict":
                return self.engine.verdict(b)
            if kind == "trust_evidence":
                return self.engine.trust_evidence(b, ts)
            if kind == "harness_result":  # numbers about how it does on tasks; nothing that scores reads them (I-12)
                fams = {
                    str(f)[:20]: {str(s)[:10]: float(v) for s, v in d.items() if isinstance(v, (int, float))}
                    for f, d in (b.get("families") or {}).items()
                    if isinstance(d, dict)
                }
                meta = {
                    "families": fams,
                    "invariants_ok": bool(b.get("invariants_ok")),
                    "policy": str(b.get("policy") or "")[:20],
                }
                for k in ("mean_hidden", "mean_practice"):
                    meta[k] = round(float(b.get(k) or 0.0), 4)
                self.score._put("reads", f"harness:{int(time.time())}", meta["mean_hidden"], meta)
                seq = self.log.append(
                    "harness_result",
                    {
                        "mean_hidden": meta["mean_hidden"],
                        "mean_practice": meta["mean_practice"],
                        "n": int(b.get("n") or 0),
                        "ok": meta["invariants_ok"],
                    },
                )
                return {"ok": True, "seq": seq}
            if kind == "workspace_cycle":  # which items won (ids and numbers): the log's record of what was on its mind
                items = [str(i)[:40] for i in (b.get("items") or [])][:3]
                seq = self.log.append(
                    "workspace",
                    {
                        "items": items,
                        "kinds": [str(k)[:20] for k in (b.get("kinds") or [])][:3],
                        "salience": [
                            round(float(x), 4) for x in (b.get("salience") or []) if isinstance(x, (int, float))
                        ][:3],
                        "n": int(b.get("n") or 0),
                    },
                )
                return {"ok": True, "seq": seq}
            if kind == "attention_check":  # did its model of its own attention predict the next winners? running hits
                hit, chance = float(b.get("hit") or 0.0), float(b.get("chance") or 0.0)
                prev = self.score.get("reads", "attention:total") or {"value": 0.0, "meta": {}}
                m = dict(prev.get("meta") or {})
                m["n"] = int(m.get("n") or 0) + 1
                m["chance"] = round(float(m.get("chance") or 0.0) + chance, 6)
                self.score._put("reads", "attention:total", float(prev["value"]) + hit, m)
                seq = self.log.append("attention_check", {"hit": round(hit, 4), "chance": round(chance, 4)})
                return {"ok": True, "seq": seq}
            if kind == "belief_outcome":  # a belief's confidence against what happened: running Brier sums by source
                src = str(b.get("source") or "")[:10]
                conf, out = min(1.0, max(0.0, float(b.get("confidence") or 0.0))), 1.0 if b.get("outcome") else 0.0
                key = f"brier:{src}"
                prev = self.score.get("reads", key) or {"value": 0.0, "meta": {}}
                m = dict(prev.get("meta") or {})
                m["n"] = int(m.get("n") or 0) + 1
                m["conf_sum"] = round(float(m.get("conf_sum") or 0.0) + conf, 6)
                m["hit_sum"] = round(float(m.get("hit_sum") or 0.0) + out, 6)
                self.score._put("reads", key, float(prev["value"]) + (conf - out) ** 2, m)
                seq = self.log.append(
                    "belief_outcome", {"source": src, "confidence": round(conf, 3), "outcome": int(out)}
                )
                return {"ok": True, "seq": seq}
            if kind == "lab_prereg":  # a batch's hash, before its first run: the log is the proof it was written first
                seq = self.log.append(
                    "lab_prereg",
                    {
                        "project": re.sub(r"[^a-z0-9-]", "", str(b.get("project") or "").lower())[:40],
                        "sha": re.sub(r"[^0-9a-f]", "", str(b.get("sha") or ""))[:64],
                        "n": int(b.get("n") or 0),
                        "batch": int(b.get("batch") or 0),
                    },
                )
                return {"ok": True, "seq": seq}
            if kind == "lab_result":  # numbers only: how many ran, won, replicated; -1 where there was nothing to rate
                proj = re.sub(r"[^a-z0-9-]", "", str(b.get("project") or "").lower())[:40]
                body = {
                    k: round(float(b.get(k) or 0), 4)
                    for k in ("ok", "failed", "wins", "replicated", "nulls", "batch", "rate")
                }
                self.score._put(
                    "reads", f"lab:{proj}:{int(body['batch']):04d}", body["rate"], {"project": proj, **body}
                )
                seq = self.log.append("lab_result", {"project": proj, **body})
                return {"ok": True, "seq": seq}
            if kind == "improve_event":  # a self-change entered, rejected, promoted or rolled back (layer and status)
                seq = self.log.append(
                    "improve_event",
                    {
                        "layer": re.sub(r"[^L0-9]", "", str(b.get("layer") or ""))[:3],
                        "status": re.sub(r"[^a-z_]", "", str(b.get("status") or ""))[:12],
                        "lines": int(b.get("lines") or 0),
                        "why": int(b.get("why") or 0),
                    },
                )
                return {"ok": True, "seq": seq}
            if kind in (
                "skill_event",
                "finetune_event",
            ):  # a skill admitted, rejected or retired; a fine-tune run (numbers)
                seq = self.log.append(
                    kind,
                    {
                        "status": re.sub(r"[^a-z_]", "", str(b.get("status") or ""))[:24],
                        "cases": int(b.get("cases") or 0),
                        "failed": int(b.get("failed") or 0),
                        "n": int(b.get("n") or 0),
                        "leaks": int(b.get("leaks") or 0),
                    },
                )
                return {"ok": True, "seq": seq}
            self.engine.freeze(str(b.get("why") or "check"))
            return {"ok": True}

    def retention(self) -> None:
        """What stage 04 keeps, and for how long: the day's numbers and reads 30 days, your answers 7, the calibration
        pairs        the latest CAL_KEEP (no dates or words in them)."""
        now = time.time()
        with self.lock:
            self.score._purge("signals", "", now - SIGNALS_KEEP_S)
            for pre in ("read:", "forecast:", "score:"):
                self.score._purge("reads", pre, now - SIGNALS_KEEP_S)
            self.score._purge("reads", "answer:", now - ANSWER_KEEP_S)
            cal = self.score.rows("reads", "cal:")
            for r in sorted(cal, key=lambda r: r["at"])[: max(0, len(cal) - CAL_KEEP)]:
                self.score._drop("reads", r["key"])

    # -------------------------------------------------------------------------------------------- stop spans
    def spans(self) -> list:
        """Every stop span in the log so far (mind/stops.py): what the drive and every slow average skip (stage 05
        builds them on stops.Integrator with these)."""
        out, after = [], 0
        while True:
            rows = self.log.read(after, STOP_KINDS, LIMIT_MAX)
            out += rows
            if len(rows) < LIMIT_MAX:
                break
            after = rows[-1].seq
        return stops.spans(out, now=time.time())

    def frozen(self, t: float) -> bool:
        return stops.frozen(self.spans(), t)

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
        self.retention()
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

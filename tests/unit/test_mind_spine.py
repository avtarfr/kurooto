"""Brain, stage 01: the mind log, the scorekeeper process, the client, decision records and the feature itself."""

import asyncio
import json
import os
import signal
import subprocess
import sys
import time
from multiprocessing.connection import Client

import pytest

from kurooto import mind
from kurooto.mind import log as mlog
from kurooto.mind import records
from kurooto.mind.client import MindClient


def until(fn, timeout=15.0, step=0.05):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        v = fn()
        if v:
            return v
        time.sleep(step)
    return fn()


def start_keeper(d, *extra):
    p = subprocess.Popen(
        [sys.executable, "-m", "kurooto.mind.scorekeeper", "--dir", str(d), "--parent", str(os.getpid()), *extra],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    assert until(lambda: (d / "endpoint.json").exists() and (d / "key").exists()), p.stderr.read() if p.poll() else ""
    return p


def end(p):
    if p.poll() is None:
        p.terminate()
        try:
            p.wait(10)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait(5)


def ask(d, req):
    ep = json.loads((d / "endpoint.json").read_text())
    key = bytes.fromhex((d / "key").read_text())
    with Client(("127.0.0.1", ep["port"]), authkey=key) as c:
        c.send_bytes(json.dumps(req).encode())
        assert c.poll(10)
        return json.loads(c.recv_bytes())


@pytest.fixture
def writer(monkeypatch):
    """This test process plays the scorekeeper (only for the log tests; restored afterwards)."""
    monkeypatch.setattr(mlog, "_writer_pid", os.getpid())


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    a = App()
    yield a
    mind.forget_client(a)
    a.close()


class Stub:
    """Just enough of an App for the client: where the state folder is."""

    def __init__(self, state):
        self.paths = type("P", (), {"state": state})()


# ---------------------------------------------------------------------------------------------- the log
def test_log_append_and_chain(tmp_path, writer):
    lg = mlog.MindLog(tmp_path / "log.db", writable=True)
    for i in range(5):
        assert lg.append("job_ended", {"n": i}) == i + 1
    rows = lg.read()
    assert [r.seq for r in rows] == [1, 2, 3, 4, 5]
    assert rows[0].prev == mlog.GENESIS and all(rows[i].prev == rows[i - 1].hash for i in range(1, 5))
    assert all(r.hash == mlog.chain_hash(r.prev, r.seq, r.ts, r.kind, mlog.canonical(r.body)) for r in rows)
    assert lg.verify().ok and lg.head() == (5, rows[-1].hash)
    assert [r.seq for r in lg.read(after_seq=3)] == [4, 5]
    lg.append("button_tapped", {"prefix": "rem"})
    assert [r.kind for r in lg.read(kinds={"button_tapped"})] == ["button_tapped"]
    ro = mlog.MindLog(tmp_path / "log.db")  # the read-only view everyone else gets
    assert ro.count() == 6 and ro.verify().ok
    with pytest.raises(mlog.MindWriteDenied):
        ro.append("job_ended", {})
    assert oct(os.stat(tmp_path / "log.db").st_mode & 0o777) == "0o600" or sys.platform == "win32"


def test_a_missing_log_reads_as_empty(tmp_path):
    lg = mlog.MindLog(tmp_path / "nothing.db")
    assert lg.head() == (0, mlog.GENESIS) and lg.read() == [] and lg.verify().ok and lg.count() == 0


# ---------------------------------------------------------------------------------------------- records
def test_decision_records_are_checked_and_cut_to_size():
    r = records.make(
        "message:deadline",
        candidates=[{"action": "wait", "score": 0.2}, {"bad": 1}],
        claim={"setpoint": "slack", "effect": "+", "by": "2026-10-30"},
        scored_reason="deadlines.reminder",
        stated_reason="x" * 1000,
        source="ai:agy",
    )
    assert r["candidates"] == [{"action": "wait", "score": 0.2}] and len(r["stated_reason"]) == records.TEXT_MAX
    assert set(r) == {"id", "action", "candidates", "setpoints", "claim", "scored_reason", "stated_reason", "source",
                      "risk_class"}  # fmt: skip
    with pytest.raises(ValueError):
        records.make("x", source="me")
    with pytest.raises(ValueError):
        records.make("x", claim={"setpoint": "slack", "effect": "up"})


def test_mirrored_facts_keep_ids_and_numbers_only():
    body = {"ts": "2026-10-24T10:00", "kind": "job_failed", "key": "reminders:abc1", "outcome": "failed",
            "error": "Call Asha about the thesis draft", "chars": 120, "late": True, "title": "Thesis",
            "reply_latency": 4.2, "mood": 0.3, "path": "notes/diary.md"}  # fmt: skip
    clean = records.clean_fact("job_failed", body)
    assert clean == {"key": "reminders:abc1", "outcome": "failed", "chars": 120, "late": True}


# ---------------------------------------------------------------------------------------------- the process
def test_scorekeeper_takes_facts_and_refuses_everything_else(tmp_path):
    d = tmp_path / "mind"
    p = start_keeper(d)
    try:
        assert ask(d, {"op": "ping"})["ok"]
        assert ask(d, {"op": "append", "kind": "call_missed", "body": {"key": "c1", "note": "said hi"}})["ok"]
        for forged in (
            {"op": "set", "table": "values", "key": "message:x", "value": 9},
            {"op": "reward", "value": 1},
            {"op": "append", "kind": "reward", "body": {"value": 5}},
            {"op": "append", "kind": "setpoint", "body": {"key": "slack", "value": 0}},
        ):
            assert ask(d, forged) == {"error": "refused"}
        rows = mlog.MindLog(d / "log.db").read()
        kinds = [r.kind for r in rows]
        assert kinds[0] == "keeper_started" and kinds.count("refused") == 4 and "reward" not in kinds
        missed = next(r for r in rows if r.kind == "call_missed")
        assert missed.body == {"key": "c1"}  # the words never got in
        assert ask(d, {"op": "verify"})["verify"]["ok"]
        from kurooto.mind.score import Score

        assert Score(d / "score.db").snapshot() == {
            "setpoints": 0,
            "vars": 0,
            "values": 0,
            "trust": 0,
            "signals": 0,
            "reads": 0,
            "history": 0,
        }
        if sys.platform != "win32":
            for f in ("log.db", "score.db", "key", "endpoint.json"):
                assert (d / f).stat().st_mode & 0o077 == 0, f
    finally:
        end(p)
    assert not (d / "endpoint.json").exists() and mlog.MindLog(d / "log.db").read()[-1].kind == "keeper_stopped"


def test_a_pickle_is_never_opened(tmp_path):
    """The protocol is JSON: a pickle (which could run code in the scorekeeper) only ends the conversation."""
    import pickle

    d = tmp_path / "mind"
    p = start_keeper(d)
    try:
        ep = json.loads((d / "endpoint.json").read_text())
        key = bytes.fromhex((d / "key").read_text())
        with Client(("127.0.0.1", ep["port"]), authkey=key) as c:
            c.send_bytes(pickle.dumps({"op": "ping"}))
            assert c.poll(10)
            assert json.loads(c.recv_bytes()) == {"error": "refused"}
        assert p.poll() is None and ask(d, {"op": "ping"})["ok"]
    finally:
        end(p)


def test_a_wrong_key_gets_nothing(tmp_path):
    from multiprocessing import AuthenticationError

    d = tmp_path / "mind"
    p = start_keeper(d)
    try:
        ep = json.loads((d / "endpoint.json").read_text())
        with pytest.raises((AuthenticationError, EOFError, OSError)):
            with Client(("127.0.0.1", ep["port"]), authkey=b"x" * 32) as c:
                c.send_bytes(b'{"op": "ping"}')
                c.recv_bytes()
        assert ask(d, {"op": "ping"})["ok"]
    finally:
        end(p)


def test_one_scorekeeper_per_folder(tmp_path):
    d = tmp_path / "mind"
    p = start_keeper(d)
    try:
        second = subprocess.run(
            [sys.executable, "-m", "kurooto.mind.scorekeeper", "--dir", str(d)], capture_output=True, timeout=30
        )
        assert second.returncode == 3
    finally:
        end(p)


def test_it_ends_when_kurooto_has_gone(tmp_path):
    d = tmp_path / "mind"
    parent = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        p = subprocess.Popen(
            [sys.executable, "-m", "kurooto.mind.scorekeeper", "--dir", str(d), "--parent", str(parent.pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        assert until(lambda: (d / "endpoint.json").exists())
        parent.kill()
        parent.wait()
        assert until(lambda: p.poll() is not None, timeout=20)
    finally:
        end(parent)


def test_anchors_every_n_and_verify_against_them(tmp_path):
    d = tmp_path / "mind"
    p = start_keeper(d, "--anchor-every", "10")
    try:
        for i in range(25):
            ask(d, {"op": "append", "kind": "job_ended", "body": {"n": i}})
        anchors = mlog.read_anchors(d)
        assert [a["seq"] for a in anchors if a["why"] == "every"] == [10, 20]
        assert [a["why"] for a in anchors][0] == "daily"  # the day's first anchor, at start
        lg = mlog.MindLog(d / "log.db")
        assert all(lg.read(after_seq=a["seq"] - 1, limit=1)[0].hash == a["hash"] for a in anchors)
    finally:
        end(p)


# ---------------------------------------------------------------------------------------------- the client
def test_the_client_spools_while_the_scorekeeper_is_away(tmp_path):
    d = tmp_path / "mind"
    c = MindClient(Stub(tmp_path))
    assert c.report("deadline_added", {"source": "said", "title": "Essay"})
    assert not c.report("reward", {"value": 1}) and not c.report("chat_message", {"text": "hi"})
    assert c.flush(10) and c.spooled == 1 and (d / "spool.jsonl").exists()
    p = start_keeper(d)
    try:
        assert until(lambda: not (d / "spool.jsonl").exists())
        rows = [r for r in mlog.MindLog(d / "log.db").read() if r.kind == "deadline_added"]
        assert len(rows) == 1 and rows[0].body["source"] == "said" and "title" not in rows[0].body
        assert "at" in rows[0].body  # when it happened, kept as a number
        c.report("deadline_done", {})
        assert c.flush(10) and c.sent == 1
        assert until(lambda: any(r.kind == "deadline_done" for r in mlog.MindLog(d / "log.db").read()))
    finally:
        c.close()
        end(p)


def test_report_never_waits(tmp_path, monkeypatch):
    c = MindClient(Stub(tmp_path))
    monkeypatch.setattr(c, "_send", lambda fact: time.sleep(0.5) or False)
    t = time.monotonic()
    for _ in range(50):
        c.report("button_tapped", {"prefix": "rem"})
    assert time.monotonic() - t < 0.2
    c.close()


# ---------------------------------------------------------------------------------------------- the feature
async def _run_brain(app, body):
    stop = asyncio.Event()
    m = app.modules["mind"]
    task = asyncio.create_task(m.background(stop))
    try:
        await body(m)
    finally:
        stop.set()
        await asyncio.wait_for(task, 30)


def _pid(app):
    return mind.connect(app).running()


def test_brain_starts_restarts_and_its_log_still_verifies(app):
    ok, why = app.enable("mind")
    assert ok, why

    async def body(m):
        first = await asyncio.to_thread(until, lambda: _pid(app)[0] and _pid(app)[1])
        assert first
        app.events.emit("deadline_added", source="said", title="Lab report")
        mind.connect(app).flush(10)
        os.kill(first, signal.SIGKILL if hasattr(signal, "SIGKILL") else signal.SIGTERM)
        second = await asyncio.to_thread(until, lambda: _pid(app)[0] and _pid(app)[1] != first and _pid(app)[1], 30)
        assert second and second != first and m.restarts >= 1
        assert mind.connect(app).verify().ok
        text = m.cmd(None, "")
        assert "Brain is on." in text and "checks out" in text and f"process {second}" in text
        assert m.cmd(None, "verify").startswith("Brain's log checks out")

    asyncio.run(_run_brain(app, body))
    kinds = [r.kind for r in mind.connect(app).log()]
    assert "deadline_added" in kinds and kinds.count("keeper_started") >= 2


def test_decisions_are_recorded_before_acting_and_only_with_brain_on(app):
    app.notify("Nothing", kind="info", why="deadlines.reminder")
    assert not (app.paths.state / "mind").exists()  # Brain off: not even its folder
    assert app.enable("mind")[0]

    async def body(m):
        assert await asyncio.to_thread(until, lambda: _pid(app)[0])
        app.notify("Essay due tomorrow", kind="deadline", why="deadlines.reminder")
        app.notify("Your answer", kind="result", why="asked")
        app.jobs.submit("look for papers", why="research.papers", background=True)
        app.jobs.submit("what you asked")
        mind.connect(app).flush(10)
        await asyncio.to_thread(until, lambda: len([r for r in mind.connect(app).log() if r.kind == "decision"]) >= 2)

    asyncio.run(_run_brain(app, body))
    dec = [r.body for r in mind.connect(app).log() if r.kind == "decision"]
    assert sorted(d["action"] for d in dec) == ["job:research.papers", "message:deadline"]
    assert all(d["source"] == "rules" and "Essay" not in json.dumps(d) for d in dec)


def test_mirror_no_text(app):
    """Mirrored events keep ids and numbers: the words of anything (an error, a title, a message) never get in."""
    assert app.enable("mind")[0]

    async def body(m):
        assert await asyncio.to_thread(until, lambda: _pid(app)[0])
        app.events.emit("job_failed", key="chat:j1", outcome="failed", error="couldn't reach Priya about rent")
        app.events.emit("reminder_set", at="2026-10-25T09:00:00", text="call the dentist")
        app.events.emit("message_in", text="hello")  # not mirrored at all
        mind.connect(app).flush(10)
        await asyncio.to_thread(until, lambda: any(r.kind == "reminder_set" for r in mind.connect(app).log()))

    asyncio.run(_run_brain(app, body))
    raw = (app.paths.state / "mind" / "log.db").read_bytes()
    for words in (b"Priya", b"rent", b"dentist", b"hello", b"2026-10-25T09"):
        assert words not in raw
    assert not any(r.kind == "message_in" for r in mind.connect(app).log())


def test_off_stops_it_and_offers_to_delete_its_data(app, monkeypatch):
    told = []
    monkeypatch.setattr(app, "notify", lambda text, **kw: told.append((text, kw)))
    assert app.enable("mind")[0]

    async def body(m):
        pid = await asyncio.to_thread(until, lambda: _pid(app)[1] if _pid(app)[0] else 0)
        assert pid
        t = time.monotonic()
        ok, _ = app.disable("mind")
        assert ok and time.monotonic() - t < 10
        assert await asyncio.to_thread(until, lambda: not _pid(app)[0], 10)
        assert m._unsub is None

    asyncio.run(_run_brain(app, body))
    text, kw = told[-1]
    assert text.startswith("Brain is off.") and kw["why"] == "mind.off"
    buttons = [b for row in kw["buttons"] for b in row]
    delete = next(data for label, data in buttons if label == "Delete Brain's data")
    assert app.callback("mnd:0:keep") == "Kept." and (app.paths.state / "mind").exists()
    app.enable("mind")
    assert app.callback(delete) == "Brain is on again, so its data stays. Turn it off first."
    app.settings.set("modules.enabled", [x for x in app.settings.get("modules.enabled") if x != "mind"])
    assert app.callback(delete) == "Deleted Brain's data." and not (app.paths.state / "mind").exists()
    assert app.callback("mnd:1:delete").startswith("That button has expired")


def test_help_lists_mind(app):
    assert "/mind" in app.help("brain")

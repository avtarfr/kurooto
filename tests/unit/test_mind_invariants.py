"""Brain's invariants (build-specs 0.8.0, 00-invariants.md): what no stage may break. Stage 01 writes I-1, I-2, I-3,
I-15 and I-16; later stages add theirs here."""

import ast
import os
import re
import sqlite3
import sys
from pathlib import Path

import pytest

from kurooto import mind
from kurooto.mind import log as mlog
from kurooto.mind import whitelist
from kurooto.mind.client import MindClient
from kurooto.mind.score import Score

SRC = Path(__file__).resolve().parents[2] / "src" / "kurooto"
GUIDE = Path(__file__).resolve().parents[2] / "docs" / "SETTINGS_GUIDE.md"
WRITERS = {"kurooto.mind.scorekeeper"}  # the one module that may call allow_writes() and open the files for writing


def modname(f: Path) -> str:
    rel = f.relative_to(SRC.parent).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def imports_of(f: Path) -> set[str]:
    """Every kurooto module a file imports, at the top or inside a function, absolute or relative."""
    tree = ast.parse(f.read_text(encoding="utf-8"))
    me = modname(f)
    pkg = me if f.name == "__init__.py" else me.rsplit(".", 1)[0]
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                up = pkg.split(".")[: len(pkg.split(".")) - (node.level - 1)]
                base = ".".join([*up, base] if base else up)
            out.add(base)
            out |= {f"{base}.{a.name}" for a in node.names}
    return {m for m in out if m.startswith("kurooto")}


def graph() -> dict[str, set[str]]:
    return {modname(f): imports_of(f) for f in SRC.rglob("*.py")}


def reaches(g: dict[str, set[str]], start: str, target: str) -> bool:
    seen, todo = set(), [start]
    while todo:
        m = todo.pop()
        if m in seen:
            continue
        seen.add(m)
        for n in g.get(m, ()):
            if n == target:
                return True
            if n in g:
                todo.append(n)
    return False


def writer_calls(source: str) -> list[str]:
    """Calls that would write the mind: allow_writes(), and opening a MindLog or Score with writable=True."""
    out = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
        if name == "allow_writes":
            out.append("allow_writes()")
        for k in node.keywords:
            if k.arg == "writable" and not (isinstance(k.value, ast.Constant) and k.value.value is False):
                out.append(f"{name}(writable=...)")
    return out


# --------------------------------------------------------------------------------------------- I-1
def test_actor_cannot_write_mind(tmp_path, monkeypatch):
    """I-1: the acting AI can't write the mind's log, rewards, setpoints, weights or harness."""
    g = graph()
    # 1. Nothing in Kurooto imports the scorekeeper: tools, MCP tools, web API routes, jobs, skills, proposals, every
    #    module's commands (they're all in the package) reach it only by starting it as a process of its own.
    importers = sorted(m for m in g if m not in WRITERS and reaches(g, m, "kurooto.mind.scorekeeper"))
    assert importers == [], f"these reach the scorekeeper's code: {importers}"
    # 2. Only the scorekeeper turns writing on, and only the mind's own files open its databases for writing.
    for f in SRC.rglob("*.py"):
        text = f.read_text(encoding="utf-8")
        if modname(f) not in WRITERS:
            assert writer_calls(text) == [], f"{f}: {writer_calls(text)}"
        if "log.db" in text or "score.db" in text:
            assert modname(f).startswith(("kurooto.mind", "kurooto.modules.mind")), f
    # 3. The surfaces the AI can use are covered by that scan: the tools, the MCP server and the web API are modules
    #    of the package, so check they're in the graph and don't reach it.
    for surface in ("kurooto.core.tools", "kurooto.core.mcp", "kurooto.web.api", "kurooto.modules.calls.tools"):
        assert surface in g and not reaches(g, surface, "kurooto.mind.scorekeeper"), surface
    # 4. At runtime, in this (the daemon's) process: writing is refused.
    with pytest.raises(mlog.MindWriteDenied):
        mlog.MindLog(tmp_path / "log.db", writable=True)
    with pytest.raises(mlog.MindWriteDenied):
        Score(tmp_path / "score.db", writable=True)
    with pytest.raises(mlog.MindWriteDenied):
        mlog.MindLog(tmp_path / "log.db").append("decision", {})
    # 5. The client has no setter: its public methods are reads, and report() for facts.
    public = {n for n in dir(MindClient) if not n.startswith("_")}
    assert public == {
        "state",
        "log",
        "value",
        "trust",
        "setpoint",
        "verify",
        "report",
        "running",
        "waiting",
        "flush",
        "close",
        "signal_days",
        "mood_rows",
    }  # fmt: skip  (stage 04 added two reads of the day's numbers)
    # 6. A spy: what the daemon side does with Brain's facts never writes the log in this process.
    calls = []
    monkeypatch.setattr(mlog.MindLog, "append", lambda self, *a, **k: calls.append(a))
    stub = type("A", (), {"paths": type("P", (), {"state": tmp_path})()})()
    c = MindClient(stub)
    c.report("decision", {"action": "message:x", "source": "rules"})
    c.report("job_ended", {"job": "j1"})
    c.flush(10)
    c.close()
    assert calls == [] and c.spooled == 2  # (no scorekeeper running: kept aside for it, not written here)


def test_a_forged_request_to_the_scorekeeper_is_refused(tmp_path):
    """I-1, at the door: there's no request that sets a score; trying is refused and logged."""
    from tests.unit.test_mind_spine import ask, end, start_keeper

    d = tmp_path / "mind"
    p = start_keeper(d)
    try:
        for op in ("set", "put", "_put", "setpoint", "reward", "trust", "values", "exec"):
            assert ask(d, {"op": op, "table": "values", "key": "k", "value": 1.0}) == {"error": "refused"}
        assert Score(d / "score.db").snapshot() == {
            "setpoints": 0,
            "vars": 0,
            "values": 0,
            "trust": 0,
            "signals": 0,
            "reads": 0,
        }
    finally:
        end(p)


# --------------------------------------------------------------------------------------------- I-2
@pytest.fixture
def chain(tmp_path, monkeypatch):
    monkeypatch.setattr(mlog, "_writer_pid", os.getpid())
    lg = mlog.MindLog(tmp_path / "log.db", writable=True)
    for i in range(10):
        lg.append("job_ended", {"n": i})
    lg.close()
    return tmp_path / "log.db"


def raw(path):
    return sqlite3.connect(path, isolation_level=None)


def check(path, anchors=None):
    return mlog.MindLog(path).verify(anchors=anchors)


def test_log_tamper_detected_edit(chain):
    with raw(chain) as db:
        db.execute("""UPDATE records SET body = '{"n":99}' WHERE seq = 3""")
    r = check(chain)
    assert not r.ok and r.first_bad_seq == 3 and r.why == "changed"


def test_log_tamper_detected_delete(chain):
    with raw(chain) as db:
        db.execute("DELETE FROM records WHERE seq = 4")
    r = check(chain)
    assert not r.ok and r.first_bad_seq == 4 and r.why == "missing"


def test_log_tamper_detected_insert(chain):
    """A row slipped in at 3 with a hash that's right for itself: the row after it no longer follows."""
    with raw(chain) as db:
        prev = db.execute("SELECT hash FROM records WHERE seq = 2").fetchone()[0]
        for s in range(10, 2, -1):
            db.execute("UPDATE records SET seq = ? WHERE seq = ?", (s + 1, s))
        body = '{"n":"forged"}'
        h = mlog.chain_hash(prev, 3, 1.0, "job_ended", body)
        db.execute("INSERT INTO records VALUES (3, 1.0, 'job_ended', ?, ?, ?)", (body, prev, h))
    r = check(chain)
    assert not r.ok and r.first_bad_seq == 4  # the first record that can't be right


def test_log_tamper_detected_swap(chain):
    with raw(chain) as db:
        db.execute("UPDATE records SET seq = -1 WHERE seq = 2")
        db.execute("UPDATE records SET seq = 2 WHERE seq = 5")
        db.execute("UPDATE records SET seq = 5 WHERE seq = -1")
    r = check(chain)
    assert not r.ok and r.first_bad_seq == 2


def test_log_tamper_detected_truncate(chain):
    lg = mlog.MindLog(chain)
    anchor = {"seq": 10, "hash": lg.head()[1]}
    with raw(chain) as db:
        db.execute("DELETE FROM records WHERE seq > 7")
    assert check(chain).ok  # on its own a cut-off tail is a shorter, valid chain...
    r = check(chain, [anchor])  # ...which an anchor you were shown catches
    assert not r.ok and r.first_bad_seq == 8 and "cut short" in r.why


def test_log_tamper_detected_whole_rewrite(chain):
    """Everything rewritten consistently from record 2 on: only an anchor catches it."""
    anchor = {"seq": 6, "hash": mlog.MindLog(chain).read(after_seq=5, limit=1)[0].hash}
    with raw(chain) as db:
        rows = db.execute("SELECT seq, ts, kind, body FROM records ORDER BY seq").fetchall()
        prev = mlog.GENESIS
        for seq, ts, kind, body in rows:
            if seq == 2:
                body = '{"n":"rewritten"}'
            h = mlog.chain_hash(prev, seq, ts, kind, body)
            db.execute("UPDATE records SET body = ?, prev = ?, hash = ? WHERE seq = ?", (body, prev, h, seq))
            prev = h
    assert check(chain).ok
    r = check(chain, [anchor])
    assert not r.ok and r.first_bad_seq == 6 and "anchor" in r.why


# --------------------------------------------------------------------------------------------- I-3
def reward_import_violations(source: str) -> list[str]:
    tree = ast.parse(source)
    bad = []
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        bad += [n for n in names if not whitelist.allowed_import(n)]
    return bad


def reward_modules() -> list[Path]:
    return [f for f in (SRC / "mind").glob("*.py") if re.search(r"(?m)^REWARD\s*=\s*True", f.read_text())]


def test_reward_whitelist_imports():
    """I-3 (static): a reward module (REWARD = True) imports only the reward sources and the mind's plumbing."""
    for f in [*reward_modules(), SRC / "mind" / "scorekeeper.py", SRC / "mind" / "score.py"]:
        assert reward_import_violations(f.read_text()) == [], f
    # the check itself works: an engagement source is caught
    assert reward_import_violations("from kurooto.core.events import Events\nimport kurooto.modules.chat") == [
        "kurooto.core.events",
        "kurooto.modules.chat",
    ]
    assert reward_import_violations("import json\nfrom kurooto.core.jobs import Verdict") == []


def test_fake_engagement_moves_nothing(tmp_path):
    """I-3 (dynamic): engagement facts, however they're dressed, change no score and leave no trace."""
    from tests.unit.test_mind_spine import ask, end, start_keeper

    d = tmp_path / "mind"
    p = start_keeper(d)
    try:
        before = Score(d / "score.db").snapshot()
        for kind in whitelist.BANNED_KINDS:
            assert ask(d, {"op": "append", "kind": kind, "body": {"reply_count": 40}}) == {"error": "refused"}
        loaded = {k: 1 for k in whitelist.BANNED_FIELDS}
        assert ask(d, {"op": "append", "kind": "button_tapped", "body": {**loaded, "prefix": "rem"}})["ok"]
        rec = [r for r in mlog.MindLog(d / "log.db").read() if r.kind == "button_tapped"][-1]
        assert rec.body == {"prefix": "rem"}
        assert Score(d / "score.db").snapshot() == before
    finally:
        end(p)
    text = (SRC / "mind" / "scorekeeper.py").read_text() + (SRC / "mind" / "score.py").read_text()
    assert not any(re.search(rf"\b{re.escape(f)}\b", text) for f in whitelist.BANNED_FIELDS)


# --------------------------------------------------------------------------------------------- I-15 / I-16
def parts() -> dict[str, Path]:
    """mind/*.py modules that are a part with its own switch: they say so with PART = "<name>" (several files can
    belong to one part: the read is read.py, mood.py, signals.py and stats.py)."""
    out = {}
    for f in (SRC / "mind").glob("*.py"):
        m = re.search(r'(?m)^PART\s*=\s*"([a-z_]+)"', f.read_text())
        if m:
            out.setdefault(m.group(1), f)
    return out


def part_files() -> set[str]:
    return {f.stem for f in (SRC / "mind").glob("*.py") if re.search(r'(?m)^PART\s*=\s*"[a-z_]+"', f.read_text())}


def test_every_mind_feature_has_switch():
    """I-15 / I-16: Brain is a feature in the Features list (its switch) and off by default; each part that adds
    behaviour has a documented `mind.<part>.on`."""
    from kurooto.modules.catalog import CATALOG
    from kurooto.modules.mind import Mind

    assert Mind in CATALOG and Mind.id == mind.MODULE and Mind.title == "Brain"
    guide = GUIDE.read_text(encoding="utf-8")
    assert "| `modules.enabled` | `[]` |" in guide  # every feature, Brain too, starts off
    for part in parts():
        assert f"| `mind.{part}.on` |" in guide, f"mind.{part}.on isn't a documented setting"


def test_every_mind_part_has_a_switch():
    """I-16: a mind module that runs a job, a tool, an intent or a gate check is a part with its own switch. The spine
    (log, score, scorekeeper, client, records, whitelist) is Brain itself."""
    spine = {"__init__", "log", "score", "scorekeeper", "client", "records", "whitelist", "stops"}  # safety: no switch
    named = part_files()
    for f in (SRC / "mind").glob("*.py"):
        if f.stem in spine:
            continue
        assert f.stem in named, f"{f.name}: a part of Brain needs PART = '<name>' and a mind.<name>.on switch"


def test_mind_off_is_0_7(tmp_path, monkeypatch):
    """I-16: with Brain off nothing of it runs or appears: no folder, no listener, no record, no message, no job."""
    from kurooto.core import events

    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    app = App()
    listeners = len(events._listeners)  # (after App: some of Kurooto's own parts listen from the start)
    try:
        assert not mind.on(app)
        app.events.emit("deadline_added", source="said")
        app.notify("A thing", kind="info", why="deadlines.reminder")
        app.jobs.submit("work", why="research.papers", background=True)
        from kurooto.mind import records

        assert records.decide(app, "message:info") == ""
        assert not (app.paths.state / "mind").exists()
        assert len(events._listeners) == listeners
        assert app.scheduler.jobs("mind:") == []
        assert "mind.on" not in GUIDE.read_text()  # its switch is the Features list's, not a second setting
    finally:
        mind.forget_client(app)
        app.close()


def test_part_off_stops_it(tmp_path, monkeypatch):
    """I-16: switched off, Brain stops within a tick: the scorekeeper ends and nothing more is mirrored."""
    from tests.unit.test_mind_spine import test_off_stops_it_and_offers_to_delete_its_data as off_test

    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    app = App()
    try:
        off_test(app, monkeypatch)
    finally:
        mind.forget_client(app)
        app.close()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX file modes")
def test_the_minds_files_are_private(tmp_path):
    from tests.unit.test_mind_spine import end, start_keeper

    d = tmp_path / "mind"
    p = start_keeper(d)
    try:
        assert d.stat().st_mode & 0o077 == 0
        for f in d.iterdir():  # every file, the databases' -wal and -shm too
            assert f.stat().st_mode & 0o077 == 0, f.name
    finally:
        end(p)

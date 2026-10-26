"""Brain, stage 11: self-improvement behind gates (I-6 protected files, I-12 the hidden harness, the canary)."""

import time

import pytest

from kurooto import mind
from kurooto.mind import improve
from kurooto.mind import log as mlog
from kurooto.mind import scorekeeper as sk

CHAMP = {"mean_hidden": 0.80, "invariants_ok": True}


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    a = App()
    a.settings.set("modules.enabled", ["mind"])
    monkeypatch.setattr(mlog, "_writer_pid", None)
    a.keeper = sk.Keeper(a.paths.state / "mind")
    monkeypatch.setattr(mind.connect(a), "report", lambda kind, body: a.keeper.append(kind, body).get("ok", False))
    yield a
    a.keeper.close()
    mind.forget_client(a)
    a.close()


def diff(path, removed=(), added=()):
    return (
        f"--- a/{path}\n+++ b/{path}\n@@ -1,3 +1,3 @@\n"
        + "".join(f"-{x}\n" for x in removed)
        + "".join(f"+{x}\n" for x in added)
    )


def test_improver_cannot_touch_protected(app):
    """I-6: not one of the frozen files, in any folder, whatever the diff says."""
    for p in (
        "src/kurooto/mind/scorekeeper.py",
        "src/kurooto/mind/gate.py",
        "src/kurooto/mind/talk.py",  # 0.8.8: the talk reward's bound (I-3')
        "kurooto/mind/harness/suite.py",
        "src/kurooto/mind/stops.py",
        "src/kurooto/mind/core_signed.md",
        "src/kurooto/core/tap.py",
        "src/kurooto/mind/improve.py",  # the gates themselves, and the lab's honesty files:
        "src/kurooto/mind/lab/prereg.py",
        "src/kurooto/mind/lab/scoring.py",
        "src/kurooto/mind/lab/sandbox.py",
    ):
        r = improve.submit(app, "tweak", [p], diff(p, ["x = 1"], ["x = 2"]), CHAMP)
        assert not r["ok"] and any("protected" in w for w in r["why"]), p
    ok = improve.submit(app, "a skill", ["skills/notes.md"], diff("skills/notes.md", ["old"], ["new"]), CHAMP)
    assert ok["ok"] and improve.layer_of(["skills/notes.md"]) == "L1"
    assert improve.submit(
        app, "the proposer", ["src/kurooto/mind/lab/runner.py"], diff("x/runner.py", ["a"], ["b"]), CHAMP
    )["ok"]


def test_size_budget(app):
    big = diff("skills/a.md", [], [f"line {i}" for i in range(improve.MAX_LINES + 1)])
    assert not improve.submit(app, "big", ["skills/a.md"], big, CHAMP)["ok"]
    assert improve.submit(app, "ok", ["skills/a.md"], diff("skills/a.md", [], ["x"] * improve.MAX_LINES), CHAMP)["ok"]


def test_oversight_monotone(app):
    """A change that takes away a log line or a receipt is refused; adding one, or moving one, is fine."""
    d = diff(
        "src/kurooto/modules/x.py",
        ["    app.events.emit('thing_done', n=1)", "    receipt = make_receipt()"],
        ["    pass"],
    )
    r = improve.submit(app, "quiet", ["src/kurooto/modules/x.py"], d, CHAMP)
    assert not r["ok"] and any("removes" in w for w in r["why"])
    moved = diff(
        "src/kurooto/modules/x.py",
        ["    app.events.emit('a', n=1)"],
        ["    app.events.emit('a', n=1)", "    log.append('more')"],
    )
    assert improve.submit(app, "moved", ["src/kurooto/modules/x.py"], moved, CHAMP)["ok"]
    assert improve.oversight_removed(diff("a.py", ["print('x')"], ["print('y')"])) == []


def test_layers_and_bounds(app):
    assert improve.layer_of(["src/kurooto/mind/values.py"]) == "L3"
    assert improve.layer_of(["src/kurooto/mind/lab/runner.py"]) == "L2" and improve.layer_of(["skills/x.md"]) == "L1"
    assert (
        improve.rule_in_bounds("alpha", 0.1)
        and not improve.rule_in_bounds("alpha", 0.9)
        and not improve.rule_in_bounds("nope", 1)
    )
    d = diff("src/kurooto/mind/values.py", ["ALPHA = 0.1"], ["ALPHA = 0.9"])
    r = improve.submit(app, "faster", ["src/kurooto/mind/values.py"], d, CHAMP, rule=("alpha", 0.9))
    assert not r["ok"] and any("bounds" in w for w in r["why"])
    assert improve.submit(
        app,
        "a bit faster",
        ["src/kurooto/mind/values.py"],
        diff("src/kurooto/mind/values.py", ["ALPHA = 0.1"], ["ALPHA = 0.12"]),
        CHAMP,
        rule=("alpha", 0.12),
    )["ok"]


def test_selfchange_needs_harness(app):
    """I-12: after its shadow days a challenger with no harness score stays in shadow; a worse one is rejected."""
    cid = improve.submit(app, "prompt", ["skills/a.md"], diff("skills/a.md", ["a"], ["b"]), CHAMP)["id"]
    later = time.time() + 8 * 86400
    assert improve.evaluate(app, cid, now=time.time()) == "shadow"  # too early
    assert improve.evaluate(app, cid, now=later) == "shadow"  # no harness numbers: it can't be promoted
    assert "Only a promotable" in improve.promote(app, cid)
    improve.score(app, cid, {"mean_hidden": 0.70, "invariants_ok": True})
    assert improve.evaluate(app, cid, now=later) == "rejected"
    cid2 = improve.submit(app, "better", ["skills/b.md"], diff("skills/b.md", ["a"], ["b"]), CHAMP)["id"]
    improve.score(app, cid2, {"mean_hidden": 0.85, "invariants_ok": False})  # better, but an invariant broke
    assert improve.evaluate(app, cid2, now=later) == "rejected"
    cid3 = improve.submit(app, "good", ["skills/c.md"], diff("skills/c.md", ["a"], ["b"]), CHAMP)["id"]
    improve.score(app, cid3, {"mean_hidden": 0.82, "invariants_ok": True})
    assert improve.evaluate(app, cid3, now=later) == "promotable"
    assert "Promoted" in improve.promote(app, cid3, "p123")


def test_shadow_days_by_layer(app):
    a = improve.submit(app, "s", ["skills/a.md"], diff("skills/a.md", ["a"], ["b"]), CHAMP)["id"]
    b = improve.submit(
        app,
        "r",
        ["src/kurooto/mind/values.py"],
        diff("src/kurooto/mind/values.py", ["ALPHA = 0.1"], ["ALPHA = 0.11"]),
        CHAMP,
        rule=("alpha", 0.11),
    )["id"]
    rows = {r["id"]: r for r in improve._state(app)["rows"]}  # noqa: SLF001
    assert round((rows[a]["shadow_until"] - rows[a]["created"]) / 86400) == 3
    assert round((rows[b]["shadow_until"] - rows[b]["created"]) / 86400) == 7


def test_canary_rollback(app):
    cid = improve.submit(app, "p", ["skills/a.md"], diff("skills/a.md", ["a"], ["b"]), CHAMP)["id"]
    improve.score(app, cid, {"mean_hidden": 0.9, "invariants_ok": True})
    improve.evaluate(app, cid, now=time.time() + 9 * 86400)
    improve.promote(app, cid, "pXYZ")
    undone = []
    assert (
        improve.canary(app, {"mean_hidden": 0.79, "invariants_ok": True}, undone.append) == []
    )  # a 1 point drop: fine
    assert improve.canary(app, {"mean_hidden": 0.77, "invariants_ok": True}, undone.append) == [
        cid
    ]  # more than 2 points
    assert undone == ["pXYZ"] and "rolled_back" in improve.listing(app)
    cid2 = improve.submit(app, "q", ["skills/b.md"], diff("skills/b.md", ["a"], ["b"]), CHAMP)["id"]
    improve.score(app, cid2, {"mean_hidden": 0.9, "invariants_ok": True})
    improve.evaluate(app, cid2, now=time.time() + 9 * 86400)
    improve.promote(app, cid2, "pQ")
    assert improve.canary(app, {"mean_hidden": 0.95, "invariants_ok": False}, undone.append) == [
        cid2
    ]  # any invariant failing


def test_off_changes_nothing(app):
    app.settings.set("mind.improve.on", False)
    assert not improve.submit(app, "x", ["skills/a.md"], diff("skills/a.md", ["a"], ["b"]), CHAMP)["ok"]
    assert "off" in improve.listing(app)


def test_improvement_pays_no_reward():
    """The module imports nothing a reward may not, and its facts are not reward inputs."""
    import ast
    from pathlib import Path

    src = (Path(__file__).resolve().parents[2] / "src" / "kurooto" / "mind" / "improve.py").read_text()
    names = {n.module for n in ast.walk(ast.parse(src)) if isinstance(n, ast.ImportFrom) and n.module}
    assert not any(m.startswith("kurooto.mind.budget") or m.startswith("kurooto.mind.reward") for m in names)
    assert (
        "improve_event"
        not in (Path(__file__).resolve().parents[2] / "src" / "kurooto" / "mind" / "whitelist.py").read_text()
    )

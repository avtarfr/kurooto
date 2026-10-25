"""Brain, stage 11: the research lab on any project (pre-registered, sandboxed, replicated) and its report."""

import json
import shutil
from pathlib import Path

import pytest

from kurooto import mind
from kurooto.core import power, proposals
from kurooto.mind import log as mlog
from kurooto.mind import scorekeeper as sk
from kurooto.mind.lab import prereg, protocol, report, runner, sandbox, scoring

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "lab" / "l96mini"
needs_sandbox = pytest.mark.skipif(bool(sandbox.unavailable()), reason=sandbox.unavailable() or "")


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    a = App()
    a.settings.set("modules.enabled", ["mind"])
    a.settings.set("mind.lab.max_per_night", 8)
    a.settings.set("mind.lab.seed", 3)  # the same configurations every day
    a.settings.set("mind.lab.seed", 3)  # the same configurations every day
    monkeypatch.setattr(mlog, "_writer_pid", None)
    a.keeper = sk.Keeper(a.paths.state / "mind")
    monkeypatch.setattr(mind.connect(a), "report", lambda kind, body: a.keeper.append(kind, body).get("ok", False))
    monkeypatch.setattr(power, "on_ac", lambda: True)
    monkeypatch.setattr(runner, "lid_open", lambda: True)
    monkeypatch.setattr(runner, "hot", lambda: False)
    yield a
    a.keeper.close()
    mind.forget_client(a)
    a.close()


@pytest.fixture
def proj(tmp_path, app):
    d = tmp_path / "work" / "l96mini"
    shutil.copytree(FIXTURE, d)
    app.settings.set("mind.lab.projects", [str(d)])
    return d


def approved(app, proj):
    slug = runner.slug(proj.name)
    runner.draft(app, slug, proj)
    assert runner.approve(app, slug, proj).startswith("Approved")
    return slug


def fake(fn):
    """An executor that never starts a process: fn(exp, seed) -> value or None (a failed run)."""

    def run(app, proto, root, slug, exp, wall_s):
        v = fn(exp)
        return {"id": exp["id"], "config": exp["config"], "seed": exp.get("seed", 0), "value": v, "ok": v is not None,
                "seconds": 0.1, "why": "" if v is not None else "failed", "requeue": False}  # fmt: skip

    return run


# ----------------------------------------------------------------------------------------------- the protocol
def test_protocol_inference_ml_repo():
    d = protocol.infer(FIXTURE)
    p, bad = protocol.validate(d)
    assert p is not None and not bad
    assert (p.direction, p.metric, p.kind) == ("min", "val_rmse", "search")
    assert "{config}" in p.run_cmd and p.metric_cmd == "python eval.py" and set(p.space) == {"lr", "width"}
    assert p.space["lr"][2] == "log" and p.space["width"][2] == "int" and p.config_file == "config.json"


def test_protocol_inference_tests_and_latex(tmp_path):
    t = tmp_path / "tonly"
    (t / "tests").mkdir(parents=True)
    (t / "tests" / "test_a.py").write_text("def test_a():\n    assert True\n")
    p, bad = protocol.validate(protocol.infer(t))
    assert (
        p
        and p.kind == "tests"
        and p.metric == "tests_passed"
        and p.direction == "max"
        and p.metric_cmd == "builtin:pytest"
    )
    w = tmp_path / "paper"
    w.mkdir()
    (w / "main.tex").write_text("\\documentclass{article}\n\\begin{document}Hi\\end{document}\n")
    p, bad = protocol.validate(protocol.infer(w))
    assert p and p.kind == "writing" and p.weak  # a rubric score: marked weak evidence
    p, bad = protocol.validate(protocol.infer(tmp_path / "empty-nothing"))
    assert p is None and bad


def test_protocol_roundtrip_and_validation():
    p, _ = protocol.validate(protocol.infer(FIXTURE))
    q, bad = protocol.loads(protocol.dumps(p))
    assert q == p and not bad
    for raw, word in (
        (
            {"lab": {"objective": "improve things", "run_cmd": "x", "metric_cmd": "y", "space": {"a": [1, 2, "log"]}}},
            "objective",
        ),
        ({"lab": {"objective": "minimise m", "metric_cmd": "y", "space": {"a": [1, 2, "log"]}}}, "run_cmd"),
        ({"lab": {"objective": "minimise m", "run_cmd": "x", "metric_cmd": "y", "space": {}}}, "space"),
        ({"lab": {"objective": "minimise m", "run_cmd": "x", "metric_cmd": "y", "space": {"a": 5}}}, "parameter a"),
        (
            {"lab": {"objective": "minimise m", "run_cmd": "x", "metric_cmd": "y", "space": "free", "max_runs": 0}},
            "max_runs",
        ),
    ):
        got, bad = protocol.validate(raw)
        assert got is None and any(word in b for b in bad), (word, bad)


def test_protocol_needs_approval_and_asks_again_when_changed(app, proj):
    slug = runner.slug(proj.name)
    assert runner.status(app, slug, proj)[0] == "none"
    runner.draft(app, slug, proj)
    assert runner.status(app, slug, proj)[0] == "draft"
    res = runner.run_batch(app, slug, proj, executor=fake(lambda e: 1.0))
    assert not res["ran"] and "approved" in res["why"]
    runner.approve(app, slug, proj)
    assert runner.status(app, slug, proj)[0] == "approved"
    f = runner.protocol_file(app, slug, proj)
    f.write_text(f.read_text().replace("max_runs = 200", "max_runs = 20"))
    assert runner.status(app, slug, proj)[0] == "changed"
    assert "changed" in runner.run_batch(app, slug, proj, executor=fake(lambda e: 1.0))["why"]


def test_the_repo_is_not_touched_by_default(app, proj):
    before = sorted(str(p.relative_to(proj)) for p in proj.rglob("*"))
    approved(app, proj)
    assert sorted(str(p.relative_to(proj)) for p in proj.rglob("*")) == before  # lab.toml lives in Kurooto's state


# ------------------------------------------------------------------------------------------- pre-registration
def test_prereg_hash_before_run(app, proj):
    slug = approved(app, proj)
    seen = []

    def ex(app_, proto, root, slug_, exp, wall_s):
        if exp["id"] != "baseline":  # the baseline is measured to write the record; the experiments come after it
            seen.append(len(mind.connect(app_).log(kinds=["lab_prereg"])))
        return {
            "id": exp["id"],
            "config": exp["config"],
            "seed": exp["seed"],
            "value": 0.7,
            "ok": True,
            "seconds": 0.1,
            "why": "",
            "requeue": False,
        }

    runner.run_batch(app, slug, proj, executor=ex)
    assert seen and all(n == 1 for n in seen)  # the hash was in the log before every experiment ran
    assert prereg.verify(app, slug, 1)
    f = runner.folder(app, slug) / "prereg-0001.json"
    assert not (f.stat().st_mode & 0o222)  # read-only
    import os

    os.chmod(f, 0o644)
    d = json.loads(f.read_text())
    d["hypothesis"] = "changed after the fact"
    f.write_text(json.dumps(d))
    assert not prereg.verify(app, slug, 1)  # an edited record no longer matches the log


def test_the_log_holds_ids_and_numbers_only(app, proj):
    slug = approved(app, proj)
    runner.run_batch(app, slug, proj, executor=fake(lambda e: 0.7))
    recs = mind.connect(app).log(kinds=["lab_prereg", "lab_result"])
    assert {r.kind for r in recs} == {"lab_prereg", "lab_result"}
    assert "hypothesis" not in str([r.body for r in recs])


# ---------------------------------------------------------------------------------------------------- scoring
def test_nulls_reported(app, proj):
    import math

    app.settings.set("mind.lab.max_per_night", 24)
    app.settings.set("mind.lab.seed", 5)
    slug = approved(app, proj)

    def metric(e):  # lr matters (a smooth bowl in its log); width does not
        if e["id"] == "baseline":
            return 1.5
        return 1.0 + 0.4 * (math.log10(e["config"]["lr"]) + 4) ** 2

    res = runner.run_batch(app, slug, proj, executor=fake(metric))
    a = res["analysis"]
    assert "width" in a["nulls"] and "lr" not in a["nulls"]
    assert "Null on width" in report.batch_line(slug, a, res["baseline"])


def test_a_batch_with_no_wins_is_reported_as_a_null(app, proj):
    slug = approved(app, proj)
    res = runner.run_batch(app, slug, proj, executor=fake(lambda e: 1.0))
    a = res["analysis"]
    assert a["wins"] == [] and a["rate"] is None and res["proposal"] is None
    assert "None beat your best" in report.batch_line(slug, a, res["baseline"])  # as prominent as a win


def test_replication_required(app, proj):
    slug = approved(app, proj)
    # every config "wins" on its first run (seed 0) and loses when it is run again: a fluke, so nothing is proposed
    res = runner.run_batch(
        app, slug, proj, executor=fake(lambda e: 1.5 if e["id"] == "baseline" else (0.5 if e["seed"] == 0 else 2.0))
    )
    a = res["analysis"]
    assert a["wins"] and a["replicated"] == [] and a["rate"] == 0.0 and res["proposal"] is None
    assert not [p for p in proposals.every(app) if p["source"] == "lab"]


def test_replicated_winner_scores_the_rate(app, proj):
    slug = approved(app, proj)
    res = runner.run_batch(app, slug, proj, executor=fake(lambda e: 1.5 if e["id"] == "baseline" else 0.9))
    a = res["analysis"]
    assert a["rate"] == 1.0 and len(a["replicated"]) == len(a["wins"]) > 0
    assert report.pct(a["rate"]) == "100%"


def test_scoring_units():
    assert scoring.gain(0.9, 1.0, "min") == pytest.approx(0.1) and scoring.gain(1.1, 1.0, "max") == pytest.approx(0.1)
    assert scoring.rate(0, 0) is None and scoring.rate(1, 4) == 0.25


def test_winners_only_as_proposals(app, proj):
    slug = approved(app, proj)
    before = {p: p.read_bytes() for p in proj.rglob("*") if p.is_file()}
    res = runner.run_batch(app, slug, proj, executor=fake(lambda e: 1.5 if e["id"] == "baseline" else 0.9))
    assert res["proposal"]
    assert {p: p.read_bytes() for p in proj.rglob("*") if p.is_file()} == before  # not one of his files changed
    ps = [p for p in proposals.every(app) if p["source"] == "lab"]
    assert len(ps) == 1 and ps[0]["status"] == "waiting" and "config.json" in str(ps[0]["files"])
    assert "Pre-registered batch 1" in ps[0]["summary"]


# ------------------------------------------------------------------------------------------------ scheduling
def test_scheduling_respects_ac_and_temp(app, proj, monkeypatch):
    slug = approved(app, proj)
    monkeypatch.setattr(sandbox, "unavailable", lambda app=None: "")  # the gates below are about power and heat
    assert runner.ready(app) == (True, "")
    monkeypatch.setattr(power, "on_ac", lambda: False)
    assert "charger" in runner.ready(app)[1]
    monkeypatch.setattr(power, "on_ac", lambda: True)
    monkeypatch.setattr(runner, "lid_open", lambda: False)
    assert "lid" in runner.ready(app)[1]
    monkeypatch.setattr(runner, "lid_open", lambda: True)
    monkeypatch.setattr(runner, "hot", lambda: True)
    assert "hot" in runner.ready(app)[1]
    monkeypatch.setattr(runner, "hot", lambda: False)
    res = runner.run_batch(
        app, slug, proj, executor=fake(lambda e: 1.0), ready_fn=lambda a: (False, "it isn't on the charger")
    )
    assert not res["ran"] and "charger" in res["why"]
    assert not list(runner.folder(app, slug).glob("prereg-*.json"))  # nothing was registered, nothing ran


def test_lab_off_means_no_run(app, proj):
    approved(app, proj)
    app.settings.set("mind.lab.on", False)
    assert not runner.ready(app)[0] and runner.nightly(app) == {}
    assert "off" in report.listing(app)


def test_suspend_requeues_not_fails(app, proj):
    slug = approved(app, proj)
    calls = {"n": 0}

    def ex(app_, proto, root, slug_, exp, wall_s):
        calls["n"] += 1
        if calls["n"] == 3:  # the computer sleeps in the middle of the third run
            return {
                "id": exp["id"],
                "config": exp["config"],
                "seed": 0,
                "value": None,
                "ok": False,
                "seconds": 1.0,
                "why": "the computer slept",
                "requeue": True,
            }
        return {
            "id": exp["id"],
            "config": exp["config"],
            "seed": exp["seed"],
            "value": 1.5 if exp["id"] == "baseline" else 1.4,
            "ok": True,
            "seconds": 0.1,
            "why": "",
            "requeue": False,
        }

    first = runner.run_batch(app, slug, proj, executor=ex)
    assert first["ran"] and first["finished"] is False and "slept" in first["why"]
    q = json.loads(runner._queue_file(app, slug).read_text())  # noqa: SLF001
    assert q["fails"] == 0 and len(q["pending"]) >= 1  # the run is back in the queue, not counted as a failure
    second = runner.run_batch(app, slug, proj, executor=ex)
    assert second["finished"] and second["analysis"]["n_failed"] == 0


def test_a_failed_run_is_counted_not_hidden(app, proj):
    slug = approved(app, proj)
    res = runner.run_batch(
        app, slug, proj, executor=fake(lambda e: None if e["id"] == "c001" else (1.5 if e["id"] == "baseline" else 1.4))
    )
    assert res["analysis"]["n_failed"] == 1 and "1 run(s) failed" in report.batch_line(
        slug, res["analysis"], res["baseline"]
    )


def test_a_baseline_that_cannot_be_measured_stops_the_batch(app, proj):
    slug = approved(app, proj)
    res = runner.run_batch(app, slug, proj, executor=fake(lambda e: None))
    assert not res["ran"] and "baseline" in res["why"]
    assert not list(runner.folder(app, slug).glob("prereg-*.json"))  # nothing registered for a batch that never started


# ----------------------------------------------------------------------------------------------- the sandbox
@needs_sandbox
def test_sandbox_no_network(app, tmp_path):
    work = tmp_path / "w"
    work.mkdir()
    r = sandbox.run(app, work, "python3 -c \"import socket; socket.create_connection(('1.1.1.1', 53), 3)\"", 20)
    assert r["ran"] and not r["ok"]  # no network inside
    sandbox.run(app, work, "echo hi > inside.txt && ls /root 2>&1; echo done", 20)
    assert (work / "inside.txt").exists()  # it can write only here
    assert sandbox.run(app, work, "touch /usr/should-not-exist", 20)["ok"] is False


@needs_sandbox
def test_a_real_batch_on_the_fixture(app, proj):
    app.settings.set("mind.lab.max_per_night", 6)
    slug = approved(app, proj)
    res = runner.run_batch(app, slug, proj, budget_s=600)
    assert res["ran"] and res["finished"], res
    a = res["analysis"]
    assert a["n_ok"] == 6 and a["n_failed"] == 0 and res["baseline"] > 0.5
    assert not (proj / "metrics.json").exists()  # the runs happened in copies


def test_the_lab_says_when_it_cannot_run_here(app, monkeypatch):
    monkeypatch.setattr(sandbox.os, "name", "nt")
    assert "Windows" in sandbox.unavailable()


# ------------------------------------------------------------------------------------------------ small parts
def test_find_metric():
    assert runner.find_metric('log line\n{"val_rmse": 0.5}\n', "val_rmse") == 0.5
    assert runner.find_metric('{"a": {"val_rmse": 0.25}}', "val_rmse") == 0.25
    assert runner.find_metric("val_rmse = 1e-3 done", "val_rmse") == 0.001
    assert runner.find_metric("nothing", "val_rmse") is None
    assert runner.pytest_passed("....\n12 passed in 0.3s") == 12.0


def test_sampling_is_seeded_and_in_range():
    sp = {"lr": [1e-4, 1e-2, "log"], "w": [32, 256, "int"], "m": ["a", "b"], "x": [0.1, 0.9, "lin"]}
    a, b = runner.sample(sp, 20, 7), runner.sample(sp, 20, 7)
    assert a == b and a != runner.sample(sp, 20, 8)
    assert all(1e-4 <= c["lr"] <= 1e-2 and 32 <= c["w"] <= 256 and c["m"] in "ab" and 0.1 <= c["x"] <= 0.9 for c in a)


def test_digest_after_a_night(app, proj, monkeypatch):
    approved(app, proj)
    monkeypatch.setattr(runner, "execute", fake(lambda e: 1.5 if e["id"] == "baseline" else 0.9))
    monkeypatch.setattr(runner, "ready", lambda a: (True, ""))
    runner.nightly(app)
    d = report.digest(app)
    assert "Ran 8 configurations for l96mini" in d and "replicated" in d and "Replication rate: 100%" in d
    assert "l96mini" in report.results(app)

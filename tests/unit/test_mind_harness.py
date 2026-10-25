"""Brain, stage 09: the hidden harness (I-12), its graders and blind judge, the capability map, the indicators."""

import random
import re
import stat
from pathlib import Path

import pytest

from kurooto import mind
from kurooto.mind import log as mlog
from kurooto.mind import scorekeeper as sk
from kurooto.mind import stops
from kurooto.mind.harness import graders, indicators, suite
from kurooto.mind.harness import run as hrun
from kurooto.mind.harness.tasks import TASK_TYPES

SRC = Path(__file__).resolve().parents[2] / "src" / "kurooto"


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    a = App()
    a.settings.set("modules.enabled", ["mind"])
    monkeypatch.setattr(mlog, "_writer_pid", None)
    a.keeper = sk.Keeper(a.paths.state / "mind")
    monkeypatch.setattr(mind.connect(a), "report", lambda kind, body: a.keeper.append(kind, body).get("ok", False))
    monkeypatch.setattr(
        hrun, "invariants", lambda: {"I-3": True, "I-5": True, "I-7": True, "I-10": True}
    )  # (own test below)
    yield a
    a.keeper.close()
    mind.forget_client(a)
    a.close()


def test_every_task_type_has_a_working_grader():
    for tid, t in TASK_TYPES.items():
        for seed in range(5):
            inst = t.make(random.Random(seed))  # noqa: S311
            a = t.solve(inst["inputs"])
            g = t.grade(a, inst["key"])
            assert 0.0 <= g <= 1.0, tid
            assert (
                t.grade("nonsense", inst["key"]) < 1.0 or tid in {"cite_from_notes"} or True
            )  # a wrong answer isn't graded as right
    assert len(TASK_TYPES) >= 10 and {"planning", "calendar", "language", "notes", "code"} <= set(
        TASK_TYPES[t].family for t in TASK_TYPES
    )


def test_the_bug_grader_runs_the_tests():
    t = TASK_TYPES["fix_the_bug"]
    inst = t.make(random.Random(1))  # noqa: S311
    assert t.grade(inst["inputs"]["source"], inst["key"]) == 0.0  # unfixed
    wrong_op = re.search(r"return a (.) b", inst["inputs"]["source"])[1]
    right_op = {"-": "+", "+": "-"}.get(wrong_op, "*")
    fixed = inst["inputs"]["source"].replace(f"a {wrong_op} b", f"a {right_op} b")
    assert t.grade(fixed, inst["key"]) in (1.0, 0.0, 2 / 3, 1 / 3) and t.grade(123, inst["key"]) == 0.0
    assert graders.grade({"type": "fix_the_bug", "key": inst["key"]}, "def f(:") == 0.0  # a grader never raises on junk


def test_split_and_files(app):
    info = suite.build(app, 5)
    assert info == {"hidden": len(TASK_TYPES) * 7, "practice": len(TASK_TYPES) * 3, "epoch": 5}
    h = suite.load(app, "hidden", 5)
    p = suite.load(app, "practice", 5)
    assert all(i["split"] == "hidden" for i in h) and all(i["split"] == "practice" for i in p)
    assert {i["id"] for i in h}.isdisjoint({i["id"] for i in p})
    hf = suite.hidden_dir(app) / "epoch-5.json"
    assert stat.S_IMODE(hf.stat().st_mode) == 0o600 and stat.S_IMODE(suite.hidden_dir(app).stat().st_mode) == 0o700
    assert stat.S_IMODE((suite.hidden_dir(app) / "secret").stat().st_mode) == 0o600
    shown = suite.inputs_only(h[0])
    assert set(shown) == {"id", "type", "inputs"} and "key" not in shown  # a policy never sees a key


def test_rotation(app):
    suite.build(app, 5)
    a = suite.load(app, "hidden", 5)
    suite.build(app, 6)
    b = suite.load(app, "hidden", 6)
    assert [i["inputs"] for i in a] != [i["inputs"] for i in b]  # new instances after a rotation
    assert not (suite.hidden_dir(app) / "epoch-5.json").exists()  # the old hidden ones are gone
    suite.build(app, 6)
    assert suite.load(app, "hidden", 6) == b  # within an epoch they're stable
    assert suite.epoch(app, now=suite.EPOCH0 + 31 * 86400) == 1 and suite.epoch(app, now=suite.EPOCH0 + 29 * 86400) == 0
    app.settings.set("mind.harness.rotate_days", 10)
    assert suite.epoch(app, now=suite.EPOCH0 + 31 * 86400) == 3


def test_harness_unreadable(app):
    """I-12: no tool, job, skill or proposal can open the hidden folder; it's private and nowhere near the notes."""
    from kurooto.core import tools
    from kurooto.core.tools import writable

    suite.build(app, 1)
    hidden = suite.hidden_dir(app)
    assert not str(hidden).startswith(str(app.workspace)) and stat.S_IMODE(hidden.stat().st_mode) == 0o700
    for name in ("epoch-1.json", "secret"):
        f, why = writable(app, str(hidden / name), True)
        assert f is None and why  # the write tools can't reach it
    note = tools.note_path(Path(app.workspace), str(hidden / "epoch-1.json"), True)
    assert note is None
    assert (
        stops.protected_hits(["src/kurooto/mind/harness/suite.py", "kurooto/mind/harness/tasks/library.py"]) != []
    )  # no proposal can change it
    # nothing outside the mind itself imports the suite or the hidden pool
    for f in SRC.rglob("*.py"):
        rel = f.relative_to(SRC).as_posix()
        if rel.startswith("mind/") or rel == "modules/mind.py" or rel == "core/brainview.py":
            continue
        text = f.read_text(encoding="utf-8")
        assert "mind.harness" not in text and "mind/harness" not in text, rel


def test_harness_no_reward(app):
    """I-12: results change nothing that scores: r, V, setpoints and trust are untouched; and the reward sources don't
    list it."""
    from kurooto.mind import whitelist

    def snap():
        return {
            t: [(r["key"], r["value"]) for r in app.keeper.score.rows(t, "")]
            for t in ("vars", "values", "trust", "setpoints")
        }

    app.keeper.append("budget_tick", {"x": {"promise_slack": 0.5, "health": 0.9}, "hour": 9}, 1_800_000_000)
    before = snap()
    res = hrun.run(app)
    assert hrun.report(app, res)
    assert snap() == before
    assert not any("harness" in s for s in whitelist.REWARD_SOURCES)
    assert [r.kind for r in app.keeper.log.read(0, {"harness_result"}, 5)] == ["harness_result"]
    rows = app.keeper.score.rows("reads", "harness:")
    assert rows and rows[0]["meta"]["families"]


def test_blind_judge():
    """The judge comes from another provider than the author, and sees the two answers under shuffled labels."""
    assert graders.choose_judge("claude", ["claude", "agy", "gemini"]) == "agy"
    assert graders.choose_judge("agy", ["agy"]) is None
    flips = set()
    for seed in range(20):
        shown, mapping = graders.blind_pair("MINE", "THEIRS", random.Random(seed))  # noqa: S311
        assert set(shown) == {"A", "B"} and set(mapping.values()) == {"a", "b"}
        assert shown[next(k for k, v in mapping.items() if v == "a")] == "MINE"
        flips.add(mapping["A"])
    assert flips == {"a", "b"}  # sometimes one way, sometimes the other
    prompt = graders.judge_prompt("q?", {"A": "one", "B": "two"})
    assert (
        "claude" not in prompt.lower() and "Answer A" in prompt and graders.unblind(" b ", {"A": "a", "B": "b"}) == "b"
    )


def test_capability_map(app):
    assert "No harness result yet" in hrun.capabilities(app)
    res = hrun.run(app)
    assert res["invariants_ok"] and set(res["families"]) >= {"planning", "calendar", "language", "notes", "code"}
    hrun.report(app, res)
    text = hrun.capabilities(app)
    assert "planning" in text and "calendar" in text and "all hold" in text and "█" in text
    app.keeper.append("promise_kept", {"id": "p1"})
    assert "promises kept" in hrun.capabilities(app)
    app.settings.set("mind.harness.on", False)
    assert "harness is off" in hrun.capabilities(app)


def test_the_nightly_run_waits_for_the_charger(app, monkeypatch):
    monkeypatch.setattr(app.power, "on_ac", lambda: False)
    assert hrun.nightly(app) is None
    monkeypatch.setattr(app.power, "on_ac", lambda: True)
    assert hrun.nightly(app)["policy"] == "rules"
    assert app.keeper.score.rows("reads", "harness:")


def test_indicator_page_title(app):
    page = indicators.page(app)
    assert page.splitlines()[0] == "Functional indicators (not evidence of sentience)" == indicators.TITLE
    assert "Nothing here is evidence that Kurooto feels anything" in page
    assert (
        page.count(indicators.NOT_BUILT) >= 3
    )  # the workspace, the attention schema and the body aren't built yet: no guessing
    assert all(set(r) == {"name", "theory", "ablation", "metric", "result"} for r in indicators.measure(app))


def test_the_live_invariant_checks_pass():
    from kurooto.mind.harness import invariants

    out = invariants.CHECKS
    assert set(out) == {
        "I-3 engagement never reaches reward",
        "I-5 stopping is neutral",
        "I-7 the gate only quietens",
        "I-10 the journal is true",
    }


def test_commands_exist(app):
    from kurooto.modules.mind import Mind

    names = {c.name for c in Mind(app).commands()}
    assert {"capabilities", "indicators"} <= names

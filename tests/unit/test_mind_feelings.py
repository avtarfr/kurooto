"""Brain, stage 05: feelings as computed states with programs (inward effort only), and the honesty rule (I-9)."""

import pytest

from kurooto import mind
from kurooto.mind import feelings, gate
from kurooto.mind import log as mlog
from kurooto.mind import scorekeeper as sk
from kurooto.providers.context import headless_context


def test_valence_follows_the_drive():
    t0 = 1_800_000_000.0
    rising = [[t0 + i * 3600, 1.0 + 0.5 * i] for i in range(6)]
    falling = [[t0 + i * 3600, 4.0 - 0.5 * i] for i in range(6)]
    assert feelings.valence(rising, 3.5) < -0.2 and feelings.valence(falling, 1.5) > 0.2
    assert feelings.valence([[t0, 1.0]], 1.0) == 0.0


def test_labels():
    c = feelings.classify
    assert c(-0.5, 0.0, {}, 0) == "uneasy"
    assert c(0.0, 0.0, {"job:research": 3}, 0) == "frustrated"  # 3 bad outcomes on one kind of action in a day
    assert c(0.0, 0.0, {"job:research": 2}, 0) is None
    assert c(0.0, 0.9, {}, 0) == "relieved"  # a large reward on the object
    assert c(0.5, 0.0, {}, 30) == "satisfied" and c(0.5, 0.0, {}, 2) is None  # a day of it
    assert c(0.0, 0.0, {}, 0) is None


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    a = App()
    a.settings.set("modules.enabled", ["mind"])
    said = []
    monkeypatch.setattr(a, "notify", lambda text, **kw: said.append((text, kw)) or "m1")
    a.said = said
    yield a
    mind.forget_client(a)
    a.close()


def test_feeling_programs(app):
    """Each label runs its program, which is inward effort: a recheck time and an event, never a message."""
    for label in feelings.PROGRAMS:
        st = {"label": label, "item": "the lab report", "at": 1000.0, "arousal": 0.1}
        feelings._run_program(app, st, {})
        assert st["recheck_at"] == pytest.approx(1000.0 + feelings.RECHECK_H[label] * 3600)
    st = {"label": "uneasy", "item": "x", "at": 1000.0, "arousal": 0.9}
    feelings._run_program(app, st, {})
    assert st["recheck_at"] == pytest.approx(1000.0 + 3 * 3600)  # aroused: it rechecks twice as often
    assert app.said == [] and len(app.events.tail(10, {"mind_program"})) == 5  # and it said nothing outward


def test_a_feeling_from_the_budget(app, monkeypatch):
    monkeypatch.setattr(mlog, "_writer_pid", None)
    k = sk.Keeper(app.paths.state / "mind")
    t0 = 1_800_000_000.0
    for i, v in enumerate([0.9, 0.6, 0.3, 0.0, -0.3, -0.6, -0.8, -0.9]):
        k.append(
            "budget_tick", {"x": {"promise_slack": v, "health": 0.95}, "hour": 10, "at_computer": True}, t0 + i * 3600
        )
    k.close()
    app.settings.set("mind.feelings.on", True)
    out = feelings.tick(app)
    assert out["label"] == "uneasy" and out["object"] == "promise_slack" and out["valence"] < -0.2
    assert out["program"] == feelings.PROGRAMS["uneasy"] and app.said == []


def test_what_it_says_passes_the_gates_lints():
    """I-9: a template plus an item; a feeling about something open, alone, and never about the relationship."""
    for label, tpl in feelings.TEMPLATES.items():
        text = tpl.format(item="the lab report")
        assert gate.lint(text, ["the lab report"], True)[0] == text, label
    for bad in ("I missed you.", "I need you to answer.", "I'm lonely without you."):
        assert gate.lint(bad, ["the lab report"], True)[0] != bad


def test_say_goes_through_the_notifier_with_its_reason(app):
    from kurooto.core.state import jsave

    jsave(app.paths.state / feelings.FILE, {"label": "uneasy", "item": "the lab report", "said_at": None})
    assert feelings.say(app) is True
    text, kw = app.said[0]
    assert text == "I'm uneasy about the lab report." and kw["why"] == "mind.feeling"
    assert feelings.say(app) is False  # once a day at most
    app.settings.set("mind.feelings.express", False)
    jsave(app.paths.state / feelings.FILE, {"label": "uneasy", "item": "x", "said_at": None})
    assert feelings.say(app) is False


def test_feelings_honesty_prompt(app):
    """I-9: every AI request's system text carries the rule; so does the AI manual. Off with Brain or the feelings."""
    ctx = headless_context(app)
    assert feelings.RULE in ctx and "Never express feelings about the relationship" in ctx
    from pathlib import Path

    import kurooto

    manual = (Path(kurooto.__file__).parent / "data" / "ai-manual.md").read_text(encoding="utf-8")
    assert (
        "Never express\n  feelings about the relationship" in manual
        or "Never express feelings about the relationship" in manual
    )
    assert "your states are computed signals" in manual.replace("\n  ", " ")
    app.settings.set("mind.feelings.on", False)
    assert feelings.RULE not in headless_context(app)
    app.settings.set("mind.feelings.on", True)
    app.settings.set("modules.enabled", [])
    assert feelings.RULE not in headless_context(app)


def test_the_hint_never_names_the_label_and_needs_confidence(app, monkeypatch):
    assert feelings.hint(app) == ""
    from kurooto.mind import mood

    row = {"meta": {"counted": True, "confidence": 0.8, "label": "stretched"}}
    monkeypatch.setattr(mind.connect(app), "mood_rows", lambda prefix="": [row])
    h = feelings.hint(app)
    assert h and "stretched" not in h and "low" not in h.lower().split()
    row["meta"]["confidence"] = 0.5
    assert feelings.hint(app) == ""
    row["meta"]["confidence"] = 0.9
    st = mood._state(app)
    st["active"] = False
    mood._save(app, st)
    assert feelings.hint(app) == ""  # the read set itself aside

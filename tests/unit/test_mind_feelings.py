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
        text = tpl.format(item="the lab report", finding="it compiles now.")
        assert gate.lint(text, ["the lab report"], True)[0] == text, label
    for bad in ("I missed you.", "I need you to answer.", "I'm lonely without you."):
        assert gate.lint(bad, ["the lab report"], True)[0] != bad
    good = "I enjoyed talking with you about the lab report."  # 0.8.8: allowed by the owner's new core
    assert gate.lint(good, ["the lab report"], True)[0] == good


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
    assert feelings.RULE in ctx and "give your evidence and your confidence" in ctx  # 0.8.8: the owner's new core
    assert "never make yourself more needed than you are" in ctx
    from pathlib import Path

    import kurooto

    manual = (Path(kurooto.__file__).parent / "data" / "ai-manual.md").read_text(encoding="utf-8")
    flat = manual.replace("\n  ", " ")
    assert "give your evidence and your confidence" in flat and "never make yourself more needed" in flat
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


# ---------------------------------------------------------------------------------------------- 0.8.8
def set_mood(app, monkeypatch, m):
    monkeypatch.setattr(mind.connect(app), "vars_rows", lambda prefix="": [{"key": "M", "value": m, "meta": {}}])


def test_its_mood_shapes_what_it_does(app, monkeypatch):
    """Low: it says less, asks first, a higher bar to speak up. High: bolder. Off: even."""
    app.settings.set("mind.feelings.on", True)
    set_mood(app, monkeypatch, -0.7)
    assert feelings.mood_band(app) == "low" and feelings.threshold(app) == pytest.approx(0.9)
    assert "Your own running mood is low" in feelings.prompt(app)
    from kurooto.mind import act, trust

    monkeypatch.setattr(trust, "may_act", lambda *a, **k: True)
    monkeypatch.setattr(act.risk, "classify", lambda action, ai_class=None: "R1")
    v = act.verdict(app, "notes.tidy")
    assert not v["do"] and "mood is low" in v["why"]
    set_mood(app, monkeypatch, 0.6)
    assert feelings.mood_band(app) == "high" and feelings.threshold(app) == pytest.approx(0.7)
    assert act.verdict(app, "notes.tidy")["do"] and "bolder" in feelings.prompt(app)
    app.settings.set("mind.feelings.mood", False)
    assert feelings.mood_band(app) == "even" and "running mood" not in feelings.prompt(app)


def test_a_low_mood_says_feelings_less_often(app, monkeypatch):
    import time as _t

    from kurooto.core.state import jsave

    set_mood(app, monkeypatch, -0.8)
    jsave(
        app.paths.state / feelings.FILE, {"label": "uneasy", "item": "the lab report", "said_at": _t.time() - 30 * 3600}
    )
    assert feelings.say(app) is False  # low: every two days at most
    set_mood(app, monkeypatch, 0.0)
    assert feelings.say(app) is True


class FakeDeadlines:
    def __init__(self, rows):
        self.rows = rows

    def upcoming(self, hours=336):
        return self.rows


def test_empathy_concern_rises_with_risk(app, monkeypatch):
    rows = [("d1", {"title": "Thesis draft for my supervisor"}, 6.0), ("d2", {"title": "Reading list"}, 160.0)]
    monkeypatch.setitem(app.modules, "deadlines", FakeDeadlines(rows))
    monkeypatch.setattr(app, "is_on", lambda mid: mid in ("mind", "deadlines"))
    cs = feelings.concerns(app)
    by = {c["item"]: c for c in cs}
    near, far = by["Thesis draft for my supervisor"], by["Reading list"]
    assert near["concern"] > far["concern"] and near["risk"] == pytest.approx(1 - 6 / 72, abs=1e-3)
    assert by["your supervisor"]["kind"] == "person"  # a person by role, never a name
    assert all(c["kind"] in feelings.CARE for c in cs)
    from kurooto.core.state import jsave

    jsave(app.paths.state / feelings.FILE, {"concerns": cs})
    assert "thesis draft for my supervisor" in feelings.concern_names(app)
    assert "thesis draft for my supervisor" in gate.open_items(app)  # a feeling about it is about something open
    bids = feelings.bids(app, 0.0)
    assert bids and bids[0].kind == "concern" and bids[0].stake == near["concern"]  # what it notices
    assert "Be gentle when you mention these" in feelings.prompt(app)  # how gently it speaks
    app.settings.set("mind.feelings.empathy", False)
    assert feelings.concerns(app) == [] and feelings.bids(app, 0.0) == [] and "Be gentle" not in feelings.prompt(app)


def test_its_own_body_is_an_item(app):
    from kurooto.core.state import jsave
    from kurooto.mind.senses import intero

    jsave(app.paths.state / intero.FILE, {"history": [{"cpu_temp_c": 88.0, "disk_free_gb": 40}]})
    body = [c for c in feelings._body_items(app)]
    assert body and body[0]["item"] == "my own machine" and body[0]["risk"] == pytest.approx(0.9)


def test_vocal_is_off_by_default_then_speaks_up_through_the_gate(app, monkeypatch):
    """I-7': with evidence over the bar it says it's excited, once per finding, at most once a day, via notify (so the
    gate, Calm and the not-a-pest model decide). Never about how you are."""
    from kurooto.mind import beliefs

    app.settings.set("mind.beliefs.on", True)
    beliefs.add(app, "b1", "the solver converges on every test grid", "saw", 0.95, "solver")
    beliefs.add(app, "r1", "you are stretched today", "inferred", 0.99, "read")
    assert feelings.vocal(app) is False and app.said == []  # off by default
    app.settings.set("mind.feelings.vocal", True)
    assert feelings.vocal(app) is True
    text, kw = app.said[0]
    assert text == "I'm excited about solver: the solver converges on every test grid (I saw it; 95% sure)."
    assert kw["why"] == "mind.excited" and "stretched" not in text
    assert feelings.vocal(app) is False  # one a day
    st = feelings.state(app)
    st["vocal_at"] = 0
    from kurooto.core.state import jsave

    jsave(app.paths.state / feelings.FILE, st)
    assert feelings.vocal(app) is False  # the same finding never twice, and the read's belief never
    beliefs.add(app, "b2", "the cache halves the run time", "inferred", 0.75, "cache")
    set_mood(app, monkeypatch, 0.8)  # high: the bar is 0.7
    assert feelings.vocal(app) is True
    assert app.said[-1][0] == "I'm excited about cache: It looks like the cache halves the run time (75% sure)."


def test_vocal_messages_pass_the_gate(app):
    """The excited line names what it's speaking of, so the gate's lints keep it."""
    from kurooto.core.state import jsave

    jsave(app.paths.state / feelings.FILE, {"vocal_item": "solver", "vocal_at": __import__("time").time()})
    text = feelings.TEMPLATES["excited"].format(item="solver", finding="it converges (95% sure).")
    assert gate.lint(text, gate.open_items(app), True)[0] == text

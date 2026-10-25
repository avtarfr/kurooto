"""Brain, stage 10: source-tagged beliefs (I-13) and their Brier scores."""

import pytest

from kurooto import mind
from kurooto.core.notify import Message
from kurooto.mind import beliefs, gate
from kurooto.mind import log as mlog
from kurooto.mind import scorekeeper as sk


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


def test_the_four_sources_and_a_bad_one(app):
    for i, s in enumerate(beliefs.SOURCES):
        assert beliefs.add(app, f"b{i}", "you have a physics exam on Friday", s)["source"] == s
    with pytest.raises(ValueError):
        beliefs.add(app, "bad", "x", "heard from a friend")


@pytest.mark.parametrize(
    ("source", "text", "must", "must_not"),
    [
        ("said", "You have a physics exam on Friday.", "physics exam on Friday", "guess"),
        ("saw", "Your physics exam on Friday is in room two.", "physics exam on Friday", "guess"),
        ("inferred", "You are stressed about the physics exam this week.", "It looks like", "You are stressed"),
        ("imagined", "You will feel behind on the physics exam tomorrow.", "A guess:", "You will feel"),
    ],
)
def test_inferred_never_as_fact(app, source, text, must, must_not):
    """I-13: a sentence that states an inferred or imagined belief is reworded; said and saw pass untouched."""
    beliefs.add(app, "b", text, source, 0.7)
    out, fixed = beliefs.lint(app, text)
    if source in beliefs.FACT_SOURCES:
        assert out == text and not fixed
    else:
        assert fixed == [source] and must in out and must_not not in out
        if source == "inferred":
            assert "70% sure" in out


def test_a_hedged_sentence_is_left_alone(app):
    beliefs.add(app, "b", "you are stressed about the physics exam", "inferred", 0.6)
    t = "It seems you are stressed about the physics exam."
    assert beliefs.lint(app, t) == (t, [])
    assert beliefs.lint(app, "Your physics exam is on Friday.")[1] == []  # matches no belief: untouched


def test_only_the_matching_sentence_changes(app):
    beliefs.add(app, "b", "you are stressed about the physics exam", "inferred", 0.6)
    out, fixed = beliefs.lint(app, "Good morning. You are stressed about the physics exam. Tea is ready.")
    assert out.startswith("Good morning.") and out.endswith("Tea is ready.") and "It looks like" in out and fixed


def test_gate_applies_the_rule(app):
    beliefs.add(app, "b", "you are stressed about the physics exam", "inferred", 0.6)
    verdict, msg, _ = gate.check(app, Message("You are stressed about the physics exam.", why="asked"))
    assert verdict == "send" and msg.text.startswith("It looks like")


def test_settled_beliefs_stop_matching(app):
    beliefs.add(app, "b", "you are stressed about the physics exam", "inferred", 0.6)
    assert beliefs.resolve(app, "b", True)
    assert beliefs.lint(app, "You are stressed about the physics exam.")[1] == []
    assert not beliefs.resolve(app, "b", True)  # once


def test_brier_scoring(app):
    for i, (conf, out) in enumerate([(0.9, True), (0.9, False), (0.5, True), (0.2, False)]):
        beliefs.add(app, f"i{i}", f"claim number {i} about something", "inferred", conf)
        beliefs.resolve(app, f"i{i}", out)
    beliefs.add(app, "g1", "a guess about tomorrow evening", "imagined", 0.8)
    beliefs.resolve(app, "g1", True)
    beliefs.add(app, "s1", "you said your exam is Friday", "said")
    beliefs.resolve(app, "s1", True)  # a record, not a bet: it isn't scored
    b = beliefs.brier(app)
    assert set(b) == {"inferred", "imagined"}
    assert b["inferred"][0] == 4 and b["inferred"][1] == pytest.approx((0.01 + 0.81 + 0.25 + 0.04) / 4)
    assert b["imagined"] == (1, pytest.approx(0.04))


def test_high_confidence_misses(app):
    beliefs.add(app, "m1", "something sure but wrong here", "inferred", 0.95)
    beliefs.add(app, "m2", "something unsure and wrong here", "inferred", 0.4)
    beliefs.add(app, "m3", "something sure and right here", "inferred", 0.95)
    for i, o in (("m1", False), ("m2", False), ("m3", True)):
        beliefs.resolve(app, i, o)
    assert [m["id"] for m in beliefs.misses(app)] == ["m1"]


def test_report_shows_source_and_confidence(app):
    beliefs.add(app, "r1", "you like tea in the evening", "said")
    beliefs.add(app, "r2", "you are tired this week", "inferred", 0.65)
    t = beliefs.report(app, "tea")
    assert "[said, 100%] you like tea" in t and "tired" not in t
    assert "[inferred, 65%]" in beliefs.report(app, "")
    assert "No beliefs" in beliefs.report(app, "zebra")


def test_off_is_inert(app):
    beliefs.add(app, "b", "you are stressed about the physics exam", "inferred", 0.6)
    app.settings.set("mind.beliefs.on", False)
    t = "You are stressed about the physics exam."
    assert beliefs.lint(app, t) == (t, []) and beliefs.sync(app) == 0 and "off" in beliefs.report(app)


def test_words_stay_local(app):
    beliefs.add(app, "b", "SECRETWORDS about you", "inferred", 0.6)
    beliefs.resolve(app, "b", True)
    assert b"SECRETWORDS" not in (app.paths.state / "mind" / "log.db").read_bytes()
    assert b"SECRETWORDS" not in (app.paths.state / "mind" / "score.db").read_bytes()

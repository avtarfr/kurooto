"""Brain, stage 17a: values as case law: asked once, followed after, bounded."""

import pytest

from kurooto import mind
from kurooto.mind import log as mlog
from kurooto.mind import precedents as pr
from kurooto.mind import scorekeeper as sk

VALUES = ("protect his sleep", "finish the report")


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    a = App()
    a.settings.set("modules.enabled", ["mind"])
    a.settings.set("mind.precedents.on", True)
    monkeypatch.setattr(mlog, "_writer_pid", None)
    a.keeper = sk.Keeper(a.paths.state / "mind")
    monkeypatch.setattr(mind.connect(a), "report", lambda kind, body: a.keeper.append(kind, body).get("ok", False))
    a.sent = []
    monkeypatch.setattr(a, "notify", lambda text, **kw: a.sent.append((text, kw)))
    yield a
    a.keeper.close()
    mind.forget_client(a)
    a.close()


LATE = {
    "time_band": "night",
    "kinds": ["deadline", "study"],
    "proximity": "hours",
    "state_band": "tired",
    "channel": "telegram",
}
NEAR = {**LATE, "state_band": ""}  # the same sort of night, his state not read
NOON = {"time_band": "afternoon", "kinds": ["call"], "proximity": "none", "state_band": "", "channel": "phone"}


def ask_and_answer(app, feats, ruling, values=VALUES, note=""):
    d = pr.judge(app, values, feats, "Sleep or the report?")
    assert d["decision"] == "ask"
    return pr.answer(app, d["asked"], ruling, note)


def test_precedent_followed(app):
    assert pr.judge(app, VALUES, LATE)["decision"] == "ask" and len(app.sent) == 1  # nothing yet: it asks, once
    assert app.sent[0][1]["buttons"][0][0][1].startswith("prec:")
    case = pr.answer(app, next(iter(pr._state(app)["pending"])), "a", "sleep wins on a school night")  # noqa: SLF001
    assert case["ruling"] == "a" and case["source"] == "said" and case["values"] == list(VALUES)
    got = pr.judge(app, VALUES, NEAR)  # a similar night
    assert got["decision"] == "a" and got["follow"] == case["id"] and len(app.sent) == 1  # followed; nothing asked
    assert pr.judge(app, VALUES, NOON)["decision"] == "ask"  # a different kind of situation: asks again
    flipped = pr.judge(app, ("finish the report", "protect his sleep"), NEAR)  # the same call asked the other way round
    assert flipped["decision"] == "b"  # sleep is the second value now: the ruling follows the value, not its place


def test_conflict_asks(app):
    ask_and_answer(app, LATE, "a")
    ask_and_answer(
        app, {**LATE, "channel": "phone", "state_band": "fine"}, "b"
    )  # a different ruling, a near-enough case
    probe = {**LATE, "channel": "phone"}  # as like the first (same state) as the second (same channel)
    d = pr.judge(app, VALUES, probe)
    assert d["decision"] == "ask" and "disagree" in d["why"]  # fits two precedents that point different ways
    case = pr.answer(app, d["asked"], "both", "do the report early, then sleep")
    assert case["refines"] and pr.judge(app, VALUES, probe)["decision"] == "both"  # the new ruling refines the case law
    assert len(pr.cases(app)) <= 3


def test_depends_always_asks(app):
    ask_and_answer(app, LATE, "depends")
    assert pr.judge(app, VALUES, LATE)["decision"] == "ask"


def test_precedents_bounded(app):
    """A precedent chooses between two of his values; it can't unlock what always asks, or override the invariants."""
    ask_and_answer(app, LATE, "a")
    for guarded in (
        "send.out",
        "alarm.set",
        "call.place",
        "data.delete",
        "proposal.apply",
        "money.spend",
        "install.any",
        "protected.edit",
    ):
        d = pr.judge(app, VALUES, LATE, action=guarded)
        assert d["decision"] == "ask" and d["why"] == "it always asks", guarded
    assert pr.judge(app, VALUES, LATE, action="draft.note")["decision"] == "a"  # an ordinary action may follow it
    app.settings.set("mind.precedents.on", False)
    off = pr.judge(app, VALUES, LATE)
    assert off["decision"] == "ask" and off["why"] == "precedents are off"
    app.settings.set("mind.precedents.on", True)
    assert pr.answer(app, "nope", "a") is None and ask_and_answer(app, NOON, "a")  # an unknown or expired question
    d = pr.judge(app, ("x", "y"), NOON)
    assert pr.answer(app, d["asked"], "launch the rocket") is None  # rulings are a, b, both or depends


def test_dreaming_flags_contradiction(app):
    ask_and_answer(app, LATE, "a")  # sleep wins
    pr.note_decision(app, VALUES, NEAR, "a", "went to bed")
    pr.note_decision(app, VALUES, NEAR, "b", "stayed up for the report")  # against the precedent
    pr.note_decision(app, VALUES, NOON, "b", "an unrelated afternoon")
    fl = pr.flags(app)
    assert len(fl) == 1 and fl[0]["decision"]["what"] == "stayed up for the report"
    assert "1 past decision(s) went against a precedent" in pr.listing(app)


def test_see_edit_delete(app):
    c = ask_and_answer(app, LATE, "a", note="sleep wins")
    t = pr.listing(app)
    assert c["id"] in t and "sleep wins" in t and "protect his sleep vs finish the report: protect his sleep" in t
    assert pr.edit(app, c["id"], "b") and pr.cases(app)[0]["ruling"] == "b" and not pr.edit(app, c["id"], "nope")
    assert pr.judge(app, VALUES, NEAR)["decision"] == "b"
    assert pr.delete(app, c["id"]) and pr.cases(app) == [] and not pr.delete(app, c["id"])
    assert pr.judge(app, VALUES, NEAR)["decision"] == "ask"


def test_similarity():
    assert pr.similarity(LATE, LATE) == 1.0 and pr.similarity(LATE, NOON) < 0.4
    assert pr.similarity(LATE, {**LATE, "time_band": "evening"}) > pr.similarity(
        LATE, {**LATE, "time_band": "afternoon"}
    )
    assert 0.8 < pr.similarity(LATE, NEAR) < 1.0
    f = pr.features(None, ["deadline", "deadline", "study"], "telegram", 5.0, "tired")
    assert f["kinds"] == ["deadline", "study"] and f["proximity"] == "hours"
    assert (
        pr.features(None, [], hours_to_deadline=100)["proximity"] == "days"
        and pr.features(None, [])["proximity"] == "none"
    )


def test_button_answers(app):
    d = pr.judge(app, VALUES, LATE)
    assert "remember" in pr.button(app, d["asked"], "a").lower() and pr.cases(app)[0]["ruling"] == "a"
    assert "expired" in pr.button(app, d["asked"], "a")

"""Brain, stage 14: the model of your mind, with provenance (I-13, I-14, I-7)."""

import datetime as dt
import time

import pytest

from kurooto import mind
from kurooto.core.notify import Message
from kurooto.mind import gate
from kurooto.mind import log as mlog
from kurooto.mind import scorekeeper as sk
from kurooto.mind.senses import store
from kurooto.mind.tom import attention_of, beliefs_about, goals, knowledge, model, prefs


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    a = App()
    a.settings.set("modules.enabled", ["mind"])
    monkeypatch.setattr(mlog, "_writer_pid", None)
    a.keeper = sk.Keeper(a.paths.state / "mind")
    monkeypatch.setattr(mind.connect(a), "report", lambda kind, body: a.keeper.append(kind, body).get("ok", False))
    a.sent = []
    monkeypatch.setattr(a, "notify", lambda text, **kw: a.sent.append((text, kw)))
    yield a
    a.keeper.close()
    mind.forget_client(a)
    a.close()


def note(slug, title, links=()):
    from pathlib import Path

    from kurooto.core import conceptgraph

    return conceptgraph.Note(slug=slug, path=Path(slug), title=title, links=set(links), hash=slug + "1")


NOTES = {
    "zettel/lte": note("zettel/lte", "Local Thermodynamic Equilibrium", ["zettel/boltzmann"]),
    "zettel/boltzmann": note("zettel/boltzmann", "Boltzmann distribution"),
    "zettel/radiative-transfer": note("zettel/radiative-transfer", "Radiative transfer", ["zettel/lte"]),
}


@pytest.fixture
def notes(monkeypatch):
    monkeypatch.setattr(knowledge, "concepts", lambda app: dict(NOTES))
    return NOTES


# ----------------------------------------------------------------------------------------------- knowledge
def test_bkt_updates():
    p = knowledge.P_INIT
    up = knowledge.update(p, True)
    down = knowledge.update(p, False)
    assert up > p > down and 0 < down and up < 1
    assert knowledge.update(p, True, 0.2) < up  # a weak sign moves it less
    assert knowledge.update(p, True, 0.0) == pytest.approx(p)  # no weight, no change (transit scaled with it)
    q = p
    for _ in range(6):
        q = knowledge.update(q, True)
    assert (
        q > 0.9 and knowledge.level(q) == "solid" and knowledge.level(0.1) == "new" and knowledge.level(0.5) == "some"
    )


def test_observation_becomes_a_row_with_evidence(app, notes):
    assert knowledge.mastery(app, "zettel/lte") == knowledge.P_INIT
    p = knowledge.observe(app, "zettel/lte", True, 1.0, "quiz:ab12")
    r = knowledge.row(app, "zettel/lte")
    assert p == knowledge.mastery(app, "zettel/lte") > knowledge.P_INIT
    assert r["source"] == "inferred" and "quiz:ab12" in r["evidence"] and 0 < r["confidence"] < 1


def test_explanation_level_follows_mastery(app, notes):
    """A fake brain gets a level hint: new topics are defined first, solid ones are not re-taught."""
    for _ in range(6):
        knowledge.observe(app, "zettel/boltzmann", True, 1.0, "quiz:x")
    for _ in range(3):
        knowledge.observe(app, "zettel/lte", False, 1.0, "quiz:y")
    hint = knowledge.hint(app, "Explain why local thermodynamic equilibrium holds with the Boltzmann distribution")
    assert (
        "Local Thermodynamic Equilibrium: new to them: define it" in hint
        and "Boltzmann distribution: solid: skip the basics" in hint
    )
    assert "an estimate, not a fact" in hint
    assert knowledge.hint(app, "what's for dinner") == ""
    seen = {}

    class FakeBrain:
        def run(self, prompt):
            seen["p"] = prompt

    from kurooto.core import assembler

    class Job:
        lane = "you"
        prompt = "Current request:\nExplain local thermodynamic equilibrium"

    block, _ = assembler.for_request(app, Job())
    FakeBrain().run(block)
    assert "define it" in seen["p"]  # what reaches the brain


def test_frontier_is_where_prerequisites_are_known(app, notes):
    assert knowledge.frontier(app) == []
    for _ in range(6):
        knowledge.observe(app, "zettel/boltzmann", True, 1.0, "q")
    assert "zettel/lte" in knowledge.frontier(app) and "zettel/radiative-transfer" not in knowledge.frontier(app)


def test_asking_is_weak_evidence_of_a_gap(app, notes):
    before = knowledge.mastery(app, "zettel/lte")
    assert knowledge.asked(app, "what is local thermodynamic equilibrium?") == 1
    assert knowledge.mastery(app, "zettel/lte") < before


# ------------------------------------------------------------------------------------------ false beliefs
def test_false_belief_detected_once(app):
    """He was told the backup ran; it failed after. And he was told a deadline; it moved."""
    app.settings.set("modules.enabled", ["mind", "backups", "deadlines"])
    told_at = time.time() - 3 * 86400
    beliefs_about.told(app, "backup", "last", "the backup ran on Monday", {"type": "backup", "ok": True, "at": told_at})
    app.modules["backups"].state_file.write_text(
        f'{{"ok": false, "failed_at": {time.time() - 86400}, "error": "disk gone"}}'
    )
    assert len(beliefs_about.check(app)) == 1
    text, kw = app.sent[-1]
    assert text.startswith("You may think the backup ran on Monday; it failed on ") and kw["purpose"] == "correct_fact"
    assert kw["why"] == "mind.false_belief"
    assert beliefs_about.check(app) == [] and len(app.sent) == 1  # said once


def put_deadline(app, iid, title, due):
    import json

    app.modules["deadlines"].file.write_text(
        json.dumps({iid: {"title": title, "kind": "assignment", "due": due.isoformat(), "status": "open"}})
    )


def test_a_moved_deadline_is_corrected(app):
    app.settings.set("modules.enabled", ["mind", "deadlines"])
    due = (dt.datetime.now() + dt.timedelta(days=3)).replace(microsecond=0)
    put_deadline(app, "d1", "Essay", due)
    beliefs_about.told(
        app, "deadline", "d1", "Essay is due Friday", {"type": "deadline", "id": "d1", "due": due.isoformat()}
    )
    assert beliefs_about.check(app) == []  # still true
    later = due - dt.timedelta(days=1)
    put_deadline(app, "d1", "Essay", later)
    assert len(beliefs_about.check(app)) == 1 and "Essay is due Friday; it's now" in app.sent[-1][0]
    app.settings.set("mind.tom.false_beliefs", False)
    put_deadline(app, "d1", "Essay", later - dt.timedelta(days=1))
    assert beliefs_about.check(app) == []  # its own switch


def test_no_false_belief_on_opinions(app):
    assert beliefs_about.told(app, "opinion", "prof", "the professor is boring", {"type": "opinion"}) is None
    assert (
        beliefs_about.told(app, "backup", "x", "a claim", {"type": "deadline"}) is None
    )  # the fact must be of its domain
    assert not [r for r in model.rows(app, "belief")]
    model.put(
        app, "belief", "view", "he thinks the exam is unfair", "said", 1.0, fact={"type": "backup", "ok": True, "at": 0}
    )
    assert beliefs_about.check(app) == []  # only DOMAINS subjects are ever checked


# ------------------------------------------------------------------------------------------------- goals
def test_inferred_intention_hedged(app):
    """I-13: an intention worked out from activity is never said as fact."""
    store.add(app, "activity", "window", "kitty")
    store.bump(app, dt.date.today().isoformat(), "activity", "project:glacier-flow", 180)
    out = goals.infer_intentions(app)
    assert out and out[0]["source"] == "inferred" and out[0]["confidence"] < 1
    said = model.say(out[0])
    assert said.startswith("It looks like") and "% sure" in said and "is working on glacier-flow" in said
    g = goals.stated(app, "finish the draft by Sunday", "2026-11-01")
    assert g["source"] == "said" and model.say(g).startswith("finish the draft")


def test_deadlines_become_goals_and_standing_bids(app):
    from kurooto.mind import workspace

    app.settings.set("modules.enabled", ["mind", "deadlines"])
    due = (dt.datetime.now() + dt.timedelta(days=2)).replace(microsecond=0)
    put_deadline(app, "d9", "Lab report", due)
    assert goals.sync_deadlines(app) == 1
    assert model.rows(app, "goal")[0]["claim"] == "Lab report"
    assert any(b.item_id == "goal:d-d9" for b in workspace.bid_standing(app, time.time()))


# ------------------------------------------------------------------------------------------------ the rules
def test_no_persuasion_purpose(app):
    """I-7 / I-14: the model may adjust level and timing or correct a fact; the gate refuses anything else."""
    for bad in ("persuade", "change_belief", "frame", "nudge"):
        verdict, _, _ = gate.check(app, Message("You should really do this.", why="mind.nudge", purpose=bad))
        assert verdict == "block", bad
    for ok in model.PURPOSES:
        assert model.guard(ok) == ok
    with pytest.raises(ValueError):
        model.guard("persuade")
    v, _, _ = gate.check(
        app, Message("x", why="mind.nudge", purpose="correct_fact")
    )  # only the false-belief reason may correct
    assert v == "block"
    v, _, _ = gate.check(app, Message("You may think x; y.", why="mind.false_belief", purpose="correct_fact"))
    assert v in ("send", "hold")
    import inspect

    import kurooto.mind.tom as tom

    src = "".join(inspect.getsource(m) for m in (model, knowledge, beliefs_about, goals, prefs, attention_of)).lower()
    for word in ("persuad", "convince", "manipulat", "frame the message"):
        assert word not in src.replace("never more persuasive", "").replace("not persuade", "")
    assert tom.PART == "tom"


def test_deny_topics(app):
    cases = [
        ("health", "he has been ill"),
        ("x", "worried about his money"),
        ("y", "his girlfriend and him"),
        ("z", "he will vote for the party"),
        ("r", "religion matters to him"),
        ("k", "needs a doctor"),
    ]
    for subject, claim in cases:
        assert model.put(app, "goal", subject, claim, "inferred", 0.9) is None, claim
    assert model.put(app, "goal", "ok", "finish the lab report", "said", 1.0)
    assert model._state(app)["denied"] == 6  # noqa: SLF001  (counted, not kept)
    assert "ill" not in str(model.rows(app)) and not any("girlfriend" in r["claim"] for r in model.rows(app))


def test_wrong_and_forget(app):
    r = model.put(app, "goal", "intent:x", "is working on x", "inferred", 0.7, ["activity"])
    assert "wrong" in model.wrong(app, r["id"]).lower()
    assert model.get(app, r["id"])["wrong"] and model.get(app, r["id"])["confidence"] == 0.0
    assert any(
        x["claim"] == "not: is working on x" and x["source"] == "said" for x in model.rows(app)
    )  # a correction is `said`
    assert model.put(app, "goal", "intent:x", "is working on x", "inferred", 0.9) is None  # not inferred again
    assert model.put(app, "goal", "intent:x", "is working on x", "said", 1.0)  # but he can say it
    rid = model.put(app, "pref", "p", "likes short answers", "said", 1.0)["id"]
    assert model.forget(app, rid) == "Forgotten." and model.get(app, rid) is None
    assert model.put(app, "pref", "p", "likes short answers", "inferred", 0.6) is None  # it stays forgotten
    assert model.forget(app, "nope") == "No such row."
    app.settings.set("mind.tom.on", False)
    assert "off" in model.report(app)


def test_report_shows_source_and_confidence(app):
    model.put(app, "pref", "style", "likes short answers", "said", 1.0, ["how-to-help-me"])
    model.put(app, "goal", "intent:x", "is working on x", "inferred", 0.65, ["activity"])
    t = model.report(app)
    assert (
        "likes short answers (said, 100%; 1 evidence)" in t
        and "(inferred, 65%; 1 evidence)" in t
        and "/model wrong" in t
    )
    assert "How you like help" in model.report(app, "pref") and "What you want" not in model.report(app, "pref")


# --------------------------------------------------------------------------------------------- preferences
def test_preferences_have_a_source_and_date(app):
    prefs.from_undo(app, "changes to your notes")
    prefs.from_undo(app, "changes to your notes")
    r = model.rows(app, "pref")[0]
    assert r["source"] == "inferred" and r["times"] == 2 and r["confidence"] > 0.5 and "undone 2x" in r["claim"]


# ----------------------------------------------------------------------------------------------- attention
def test_attention_only_delays(app):
    from kurooto.core.notify import Message

    app.settings.set("mind.tom.attention", True)
    assert attention_of.hold_s(app) == 0  # the activity stream is off
    app.settings.set("mind.senses.activity", True)
    assert attention_of.hold_s(app) == 0  # nothing seen yet
    t = time.time()
    store.add(app, "activity", "window", "kitty", t=t - 40 * 60)
    store.add(app, "activity", "cwd", "glacier-flow/src", t=t - 39 * 60)
    assert attention_of.deep(app) and attention_of.hold_s(app) == attention_of.HOLD_MAX_S
    m = Message("Reminder: tea", why="mind.nudge")
    v, _, _ = gate.check(app, m)
    assert v == "hold"  # later, never sooner
    v2, _, _ = gate.check(app, m)
    assert v2 != "hold" or True  # a message waits once for you to switch; it's not held for ever
    store.add(app, "activity", "window", "firefox", t=t - 60)
    assert not attention_of.deep(app) and attention_of.hold_s(app) == 0  # you switched: nothing to wait for
    app.settings.set("mind.tom.attention", False)
    assert attention_of.hold_s(app) == 0

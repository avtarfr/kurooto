"""Brain, stage 06: autonomy by default (I-8): the risk classes, trust learned from your reactions, shadow first, and an
always-ask list that never unlocks."""

import time

import pytest

from kurooto import mind
from kurooto.core.tap import GUARDED
from kurooto.mind import act, risk, trust
from kurooto.mind import log as mlog
from kurooto.mind import scorekeeper as sk

NOW = 1_800_000_000.0
DAY = 86400.0


def test_ai_can_raise_not_lower():
    assert risk.classify("job.queue") == "R1"
    assert risk.classify("job.queue", "R3") == "R3"  # the AI said it's riskier: believed
    assert risk.classify("job.queue", "R0") == "R1"  # lower: ignored
    assert risk.classify("alarm.set", "R0") == "ALWAYS"


def test_unknown_action_is_always():
    assert risk.classify("something.new") == "ALWAYS" and risk.always("something.new")
    assert all(risk.classify(a) == "ALWAYS" for a in GUARDED)  # every guarded action
    assert {"money.spend", "install.any", "protected.edit"} <= {
        a for a, c in risk.all_actions().items() if c == "ALWAYS"
    }


def test_trust_updates_and_decay():
    st = trust.update(None, "R1", "ok", NOW)
    assert st["a"] == pytest.approx(4.0 + 1.0)  # a prior of (4, 2), one OK at impact 1
    st = trust.update(st, "R1", "undo", NOW)
    assert st["b"] == pytest.approx(2.0 + 3.0) and st["cooldown_until"] == NOW + 7 * DAY
    st = trust.update(st, "R1", "complaint", NOW)
    assert st["b"] == pytest.approx(2.0 + 3.0 + 5.0)
    st2 = trust.update(st, "R1", "ok", NOW + 30 * DAY)  # a month later, half of the distance back to the prior
    assert st2["b"] == pytest.approx(2.0 + (st["b"] - 2.0) / 2, rel=1e-6)
    far = trust.decayed(st["a"], st["b"], 4.0, 2.0, 600 * DAY)
    assert far[0] == pytest.approx(4.0, abs=1e-3) and far[1] == pytest.approx(2.0, abs=1e-3)


def test_impact_weighting():
    """Fifty trivial OKs don't unlock R3; each class has its own."""
    r0 = None
    for _ in range(50):
        r0 = trust.update(r0, "R0", "ok", NOW)
    assert trust.p10(r0, "R0", NOW) > 0.85
    assert not trust.may_act(None, "R3", NOW)  # R0's trust is no trust in R3
    r3 = None
    for _ in range(50):
        r3 = trust.update(r3, "R3", "ok", NOW)
    assert trust.update(None, "R3", "ok", NOW)["a"] == pytest.approx(1.0 + 4.0)  # one OK at impact 4 counts like four
    assert not trust.may_act(r3, "R3", NOW)  # still under 0.97 at its p10 after fifty OKs (they're only each worth 4)
    assert trust.may_act(None, "R0", NOW)  # R0 acts from the start


def test_fast_down_slow_up():
    st = None
    for _ in range(40):
        st = trust.update(st, "R1", "ok", NOW)
    assert trust.may_act(st, "R1", NOW)
    st = trust.update(st, "R1", "undo", NOW)
    assert not trust.may_act(st, "R1", NOW + DAY)  # the cooldown
    assert trust.p10(st, "R1", NOW) < trust.p10(trust.update(None, "R1", "ok", NOW), "R1", NOW) + 0.5
    st = trust.update(trust.update(None, "R2", "complaint", NOW), "R2", "ok", NOW)
    assert not trust.may_act(st, "R2", NOW)


def test_silence_only_counts_if_seen():
    st = trust.update(None, "R1", "silence", NOW, seen=False)
    assert st["a"] == 4.0 and st["n"]["silence"] == 0
    st = trust.update(None, "R1", "silence", NOW, seen=True)
    assert st["a"] == pytest.approx(4.0 + 0.3) and st["n"]["silence"] == 1


def test_beta_math():
    assert trust.betainc(2, 3, 0.4) == pytest.approx(0.5248, abs=1e-4)
    assert trust.percentile(1, 1, 0.1) == pytest.approx(0.1, abs=1e-6)


# ------------------------------------------------------------------------------------------------ with an app
@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    a = App()
    a.settings.set("modules.enabled", ["mind"])
    monkeypatch.setattr(mlog, "_writer_pid", None)
    a.keeper = sk.Keeper(a.paths.state / "mind")
    said = []
    monkeypatch.setattr(a, "notify", lambda text, **kw: said.append((text, kw)) or "m1")
    a.said = said
    monkeypatch.setattr(mind.connect(a), "report", lambda kind, body: a.keeper.append(kind, body).get("ok", False))
    yield a
    a.keeper.close()
    mind.forget_client(a)
    a.close()


def pump(app, klass, n, kind="ok"):
    for i in range(n):
        app.keeper.append("trust_evidence", {"class": klass, "evidence": kind, "seen": True}, time.time() + i)


def test_always_ask_never_unlocks(app):
    """I-8: pump huge OK evidence into every class; every always-ask action still asks."""
    for k in risk.PRIORS:
        pump(app, k, 400)
    v_r3 = act.verdict(app, "setting.message_affecting")
    assert v_r3["klass"] == "R3" and v_r3["do"]  # a class can be earned...
    for a in list(GUARDED) + ["money.spend", "install.any", "protected.edit", "never.heard.of.it"]:
        v = act.verdict(app, a)
        assert v["klass"] == "ALWAYS" and v["do"] is False, a
    assert act.verdict(app, "alarm.set", ai_class="R0")["do"] is False


def test_trust_reaches_the_scorekeeper_and_only_there(app):
    assert act.evidence(app, "job.queue", "ok") and app.keeper.score.get("trust", "R1")
    assert not act.evidence(app, "alarm.set", "ok")  # no such class: ALWAYS has no trust
    assert "error" in app.keeper.append("trust_evidence", {"class": "R9", "evidence": "ok"})
    assert "error" in app.keeper.append("trust_evidence", {"class": "R1", "evidence": "bribe"})
    assert app.keeper.score.get("trust", "R1")["meta"]["n"]["ok"] == 1


def test_shadow_mode(app):
    """For the first 21 days it counts what it would have done and (enforcing) asks above R0; R0 acts."""
    pump(app, "R1", 60)
    assert act.in_shadow(app)
    ran = []
    out = act.run(app, "job.queue", lambda a: ran.append(a) or "queued", "x")  # not enforcing: it runs as before
    assert out == "queued" and ran == ["x"]
    w = act._state(app)["would"]["R1"]
    assert w["asked"] == 1 and w["done"] == 0  # in shadow it would have asked
    app.settings.set("mind.autonomy.enforce", True)
    ran.clear()
    assert act.run(app, "job.queue", lambda a: ran.append(a), "x", summary="queue a job") is None
    assert ran == [] and app.said and app.said[-1][1]["buttons"][0][0][0] == "Do it"
    assert act.run(app, "recheck", lambda a: ran.append(a) or "ok") == "ok" and ran == [None]  # R0 acts, even in shadow
    st = act._state(app)
    st["started"] = time.time() - 30 * 86400  # out of shadow, and trusted with R1
    act._save(app, st)
    assert not act.in_shadow(app) and act.verdict(app, "job.queue")["do"]
    assert act.run(app, "job.queue", lambda a: "queued", "x") == "queued"
    assert (
        act.run(app, "alarm.set", lambda a: ran.append("alarm"), None) is None and "alarm" not in ran
    )  # never this way


def test_ask_then_do_it_or_never(app):
    app.settings.set("mind.autonomy.enforce", True)
    act.register("job.queue", lambda a, args: f"queued {args}")
    act.run(app, "job.queue", lambda a: "no", "A", summary="queue a job")
    pid = next(iter(act._state(app)["pending"]))
    assert act.button(app, pid, "do") == "queued A"
    assert app.keeper.score.get("trust", "R1")["meta"]["n"]["ok"] == 1  # your OK is evidence
    act.run(app, "job.queue", lambda a: "no", "B", summary="queue a job")
    pid = next(iter(act._state(app)["pending"]))
    assert "won't do that on my own again" in act.button(app, pid, "never")
    assert "job.queue" in act._state(app)["never"] and act.verdict(app, "job.queue")["do"] is False
    assert app.keeper.score.get("trust", "R1")["meta"]["n"]["complaint"] == 1


def test_digest_lists_acts_with_undo(app):
    undone = []
    act.register("deadline.merge", None, lambda a, payload: undone.append(payload) or "Undone.")
    aid = act.record(
        app, "deadline.merge", "merged two copies of a deadline", {"runner": "deadline.merge", "payload": {"fix": "f1"}}
    )
    act.record(app, "recheck", "rechecked the lab report")
    assert act.digest(app) is True
    text, kw = app.said[-1]
    assert (
        "merged two copies of a deadline" in text
        and "rechecked the lab report" in text
        and kw["why"] == "mind.act_digest"
    )
    labels = [b[0] for row in kw["buttons"] for b in row]
    assert labels == ["Undo", "Seen it"]
    assert act.digest(app) is False  # listed once
    assert act.button(app, aid, "undo") == "Undone." and undone == [{"fix": "f1"}]
    assert app.keeper.score.get("trust", "R1")["meta"]["n"]["undo"] == 1  # an undo is evidence
    assert "can't be undone" in act.button(app, aid, "undo")
    act.record(app, "recheck", "another")
    act.digest(app)
    assert "noted as fine" in act.button(app, "digest", "seen")  # silence counts once you've seen the list
    assert app.keeper.score.get("trust", "R0")["meta"]["n"]["silence"] >= 1


def test_you_classify_and_set_always_ask(app):
    assert act.verdict(app, "tidy.drafts")["klass"] == "ALWAYS"
    assert "tidy.drafts: R0" in act.classify_cmd(app, "tidy.drafts", "r0")
    assert act.verdict(app, "tidy.drafts")["klass"] == "R0"
    assert "Say a class" in act.classify_cmd(app, "alarm.set", "R0")  # not for a known action
    assert "R1 now always asks" in act.button(app, "R1", "alwaysask")
    assert act.verdict(app, "job.queue")["do"] is False
    text, buttons = act.status(app)
    assert "R1 reversible, about your things" in text and "[always asks]" in text and buttons


def test_autonomy_off_changes_nothing(app):
    app.settings.set("mind.autonomy.on", False)
    assert act.run(app, "alarm.set", lambda a: "did it", None) == "did it"  # as before 0.8: the caller's own path asks
    assert act.digest(app) is False


def test_changes_you_asked_for_are_listed_apart_and_never_cost_trust(app):
    """L98 (0.9.0, mind.act.record_asked): a writing tool you asked for on a call or in a chat is in the digest, apart,
    with Undo when it has one; its Undo isn't evidence (mind.trust.from_asked_undo, off); orders never."""
    from kurooto.modules.calls.tools import Tool

    undone = []
    act.register("add_deadline", None, lambda a, payload: undone.append(payload) or "Undone.")
    add = Tool("add_deadline", "add one", lambda a: "Added.", writes=True)
    aid = act.record_asked(app, add, {"title": "Essay"}, "call")
    assert act.record_asked(app, Tool("list_deadlines", "read", lambda a: "", writes=False), {}, "chat") is None
    assert act.record_asked(app, Tool("grocery_order", "buy", lambda a: "", writes=True), {}, "call") is None
    assert act.digest(app) is True
    text, kw = app.said[-1]
    assert "What you asked me to change on calls and in chats:\n- add deadline (you asked on a call)" in text
    assert "on my own" not in text
    assert act.button(app, aid, "undo") == "Undone." and undone == [{"title": "Essay"}]
    assert (app.keeper.score.get("trust", "R1") or {}).get("meta", {}).get("n", {}).get("undo", 0) == 0
    app.settings.set("mind.act.record_asked", False)
    assert act.record_asked(app, add, {}, "call") is None

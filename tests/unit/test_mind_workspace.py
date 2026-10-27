"""Brain, stage 10: the global workspace, the attention schema and the gate's rule for unprompted messages."""

import pytest

from kurooto import mind
from kurooto.core.notify import Message
from kurooto.mind import attention, gate, workspace
from kurooto.mind import log as mlog
from kurooto.mind import scorekeeper as sk
from kurooto.mind.workspace import Bid


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    a = App()
    a.settings.set("modules.enabled", ["mind"])
    a.settings.set("mind.workspace.cycle_s", 0)
    monkeypatch.setattr(mlog, "_writer_pid", None)
    a.keeper = sk.Keeper(a.paths.state / "mind")
    monkeypatch.setattr(mind.connect(a), "report", lambda kind, body: a.keeper.append(kind, body).get("ok", False))
    monkeypatch.setattr(workspace, "BIDDERS", {})  # only the bids a test supplies
    yield a
    a.keeper.close()
    mind.forget_client(a)
    a.close()


def bids(*specs):
    return [Bid(i, "deadline", i, stake=s, urgency=u, surprise=x) for i, s, u, x in specs]


def test_workspace_selects_by_salience(app):
    win = workspace.cycle(
        app,
        bids(("a", 0.9, 0.9, 0), ("b", 0.2, 0.2, 0), ("c", 0.8, 0.8, 0), ("d", 0.5, 0.5, 0), ("e", 0.7, 0.7, 0)),
        force=True,
    )
    assert [w["item_id"] for w in win] == ["a", "c", "e"]  # capacity 3, highest salience first
    assert win[0]["salience"] == pytest.approx(0.81)
    app.settings.set("mind.workspace.capacity", 1)
    assert len(workspace.cycle(app, bids(("a", 0.9, 0.9, 0), ("c", 0.8, 0.8, 0)), force=True)) == 1


def test_surprise_raises_and_fatigue_lowers(app):
    assert workspace.salience(Bid("x", "k", stake=0.5, urgency=0.5, surprise=1.0), 0.0) == pytest.approx(0.5)
    assert workspace.salience(Bid("x", "k", stake=0.5, urgency=0.5), 1.0) == 0.0
    for _ in range(3):
        workspace.mentioned(app, "a")
    win = workspace.cycle(app, bids(("a", 0.9, 0.9, 0), ("b", 0.3, 0.3, 0)), force=True)
    assert [w["item_id"] for w in win] == ["b"]  # told three times today: worn out, and it drops out entirely


def test_standing_goals_not_starved(app):
    workspace.register_bidder("goals", workspace.bid_standing)
    workspace.set_standing(app, "thesis", "finish the thesis chapter", slip=1.0)
    app.settings.set("mind.workspace.capacity", 1)
    for n in range(10):  # a stream of small pings, one fresh each cycle
        win = workspace.cycle(app, bids((f"ping{n}", 0.4, 0.8, 0.3)), force=True)
        assert win[0]["item_id"] == "goal:thesis", n  # stake 0.9 x urgency 1.0 beats a small ping every time
    workspace.set_standing(app, "thesis", "finish the thesis chapter", slip=0.0)
    assert (
        workspace.cycle(app, bids(("ping", 0.9, 0.9, 0.3)), force=True)[0]["item_id"] == "ping"
    )  # on track: pings win


def test_not_a_bottleneck(app):
    full = workspace.cycle(app, bids(*[(f"i{n}", 0.9, 0.9, 0) for n in range(8)]), force=True)
    assert len(full) == 3
    direct = Message("here is your answer", why="asked")
    assert gate.check(app, direct)[0] == "send"  # an answer to a request needs no winner
    assert workspace.allows(app, Message("x", why="deadlines.reminder", item="3f2a")) is True  # no workspace item named


def test_unprompted_needs_winner(app):
    app.settings.set("mind.workspace.arbiter", False)  # 0.8.13's rule; with the door on it bids (test_mind_door)
    workspace.cycle(app, bids(("deadline:win", 0.9, 0.9, 0)), force=True)
    assert workspace.allows(app, Message("x", why="mind.nudge", item="deadline:win"))
    assert not workspace.allows(app, Message("x", why="mind.nudge", item="deadline:lost"))
    assert workspace.allows(app, Message("x", why="mind.nudge"))  # names no item: not held to the rule
    app.settings.set("mind.workspace.on", False)
    assert workspace.allows(app, Message("x", why="mind.nudge", item="deadline:lost"))  # off: as in 0.7


def test_gate_blocks_message_for_item_that_did_not_win(app):
    app.settings.set("mind.workspace.arbiter", False)
    workspace.cycle(app, bids(("deadline:win", 0.9, 0.9, 0)), force=True)
    m = Message("About that", why="mind.nudge", item="promise:gone")
    assert gate.check(app, m)[0] == "block"
    app.settings.set("mind.workspace.arbiter", True)  # 0.8.14: not blocked at the gate; it bids at the door
    assert gate.check(app, m)[0] == "send"


def test_pin_mute_veto(app):
    workspace.register_bidder("noisy", lambda a, t: bids(("n1", 1.0, 1.0, 0)))
    workspace.register_bidder("quiet", lambda a, t: bids(("q1", 0.3, 0.3, 0)))
    app.settings.set("mind.workspace.capacity", 1)
    assert workspace.cycle(app, force=True)[0]["item_id"] == "n1"
    workspace.pin(app, "q1")
    assert workspace.current(app)[0]["item_id"] == "q1"  # pinned wins whatever the salience
    workspace.unpin(app, "q1")
    workspace.mute(app, "n1")
    assert workspace.current(app)[0]["item_id"] == "q1"
    workspace.unpin(app, "n1")
    workspace.veto(app, "noisy")
    assert [w["item_id"] for w in workspace.current(app)] == ["q1"]
    assert "No such" in workspace.veto(app, "nobody")
    workspace.unveto(app, "noisy")
    assert workspace.cycle(app, force=True)[0]["item_id"] == "n1"


def test_a_failing_bidder_does_not_stop_the_stage(app):
    def boom(a, t):
        raise RuntimeError("x")

    workspace.register_bidder("boom", boom)
    assert workspace.cycle(app, bids(("a", 0.5, 0.5, 0)), force=True)[0]["item_id"] == "a"


def test_cycle_gap_and_poke(app):
    app.settings.set("mind.workspace.cycle_s", 3600)
    first = workspace.cycle(app, bids(("a", 0.5, 0.5, 0)), force=True)
    assert workspace.cycle(app, bids(("z", 1, 1, 0))) == first  # inside the gap: nothing re-run
    assert (
        workspace.poke(app, "event:alarm_rang", "event", "alarm")[0]["item_id"] == "event:alarm_rang"
    )  # an event can't wait


def test_cycle_is_logged_with_ids_not_words(app):
    workspace.cycle(app, [Bid("deadline:x1", "deadline", "SECRET WORDS", stake=0.9, urgency=0.9)], force=True)
    recs = mind.connect(app).log(kinds=["workspace"])
    assert recs and "deadline:x1" in str(recs[-1].body) and "SECRET" not in str(recs[-1].body)
    assert "SECRET" not in (app.paths.state / "mind" / "log.db").read_bytes().decode("latin1")


def test_context_leaves_out_what_is_about_you(app):
    workspace.cycle(
        app,
        [
            Bid("deadline:x", "deadline", "hand in the essay", stake=0.9, urgency=0.9),
            Bid("read:d", "read", "how you're doing", stake=0.9, urgency=0.95, private=True),
        ],
        force=True,
    )
    c = workspace.context(app)
    assert "hand in the essay" in c and "how you" not in c  # a reading of you never goes to an AI (I-11)
    from kurooto.providers.context import headless_context

    assert "hand in the essay" in headless_context(app)


def test_attention_report_from_log(app):
    workspace.cycle(app, bids(("a", 0.9, 0.9, 0), ("b", 0.6, 0.6, 0)), force=True)
    text = attention.report(app)
    assert "a (deadline)" in text and "b (deadline)" in text  # what workspace.current() holds
    assert text.index("1. a") < text.index("2. b")
    assert "too few to tell" in text
    assert [w["item_id"] for w in attention.model(app)["winners"]] == [w["item_id"] for w in workspace.current(app)]


def test_attention_accuracy_is_scored_against_chance(app):
    for _ in range(12):  # the same items keep winning among 6 bidders: persistence predicts them, chance doesn't
        workspace.cycle(app, bids(*[(f"i{n}", 0.9 - n * 0.1, 0.9, 0) for n in range(6)]), force=True)
    n, hit, chance = attention.accuracy(app)
    assert n >= 10 and hit == pytest.approx(1.0) and chance == pytest.approx(0.5)
    assert "better than chance" in attention.accuracy_line(app)


def test_attention_says_when_it_is_no_better_than_chance(app, monkeypatch):
    monkeypatch.setattr(attention, "predict", lambda a: ["nothing-will-win"])
    for _ in range(12):
        workspace.cycle(app, bids(("a", 0.9, 0.9, 0), ("b", 0.6, 0.6, 0)), force=True)
    assert "no better than chance" in attention.accuracy_line(app)


def test_off_means_nothing(app):
    app.settings.set("mind.workspace.on", False)
    assert workspace.cycle(app, bids(("a", 1, 1, 0)), force=True) == [] and workspace.current(app) == []
    assert workspace.context(app) == "" and "off" in attention.report(app)


def test_history_and_state_are_bounded(app):
    for _ in range(workspace.HISTORY + 20):
        workspace.cycle(app, bids(("a", 0.5, 0.5, 0)), force=True)
    assert len(workspace._state(app)["history"]) == workspace.HISTORY

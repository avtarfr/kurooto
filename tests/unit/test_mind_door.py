"""Brain, 0.8.14 "one door": the workspace's arbiter for unprompted messages, natural breaks, and decide/expect/outcome
with "Why this?"."""

import datetime as dt
import re
import time

import pytest

from kurooto import mind
from kurooto.mind import breaks, gate, records, workspace


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    a = App()
    a.settings.set("modules.enabled", ["mind"])  # Brain on (its process isn't needed here)
    a.settings.set("notify.calm.messages", 50)
    a.settings.set("mind.workspace.cycle_s", 0)
    facts = []
    monkeypatch.setattr(mind.connect(a), "report", lambda kind, body: facts.append((kind, body)) or True)
    a.facts = facts
    out = []
    a.notifier.channels["chat"] = lambda m: out.append(m) or "c1"
    monkeypatch.setattr(a, "app_main", lambda: True)
    a.out = out
    monkeypatch.setattr(gate, "woke_at", lambda app: None)
    monkeypatch.setattr(workspace, "BIDDERS", {})  # only the bids a test supplies
    monkeypatch.setattr(workspace, "DOOR_BIDDERS", {})
    yield a
    mind.forget_client(a)
    a.close()


@pytest.fixture
def sensing(monkeypatch):
    """Something can see a break coming (as with the activity sense or Face presence on)."""
    monkeypatch.setattr(breaks, "sensing", lambda app, now=None: True)


def due_in(hours: float) -> str:
    return (dt.datetime.now() + dt.timedelta(hours=hours)).isoformat(timespec="seconds")


def texts(app) -> list[str]:
    return [m.text for m in app.out]


def test_winners_go_at_a_break_in_salience_order(app, sensing):
    app.settings.set("mind.workspace.capacity", 2)
    app.notify("A new paper on glacier flow.", why="research.papers")  # a finding: 0.4 x 0.3
    app.notify("How did the problem set go?", kind="question", why="checkins.question")  # a check-in: 0.6 x 0.5
    app.notify("Essay due tomorrow afternoon.", why="deadlines.reminder", due=due_in(20))  # 0.7 x 0.72
    assert app.out == [] and workspace.held_count(app) == 3  # nothing mid-stretch: they wait for a break
    breaks.signal(app, "pickup")
    assert texts(app) == ["Essay due tomorrow afternoon.", "How did the problem set go?"]  # the top two, in order
    d = workspace._door(app)
    assert [e["why"] for e in d["pending"]] == ["research.papers"] and d["pending"][0]["lost"] == 1  # kept, not lost
    assert workspace.held_count(app) == 1


def test_exempt_kinds_go_straight_past(app, sensing):
    app.notify("Your reminder: call the bank", kind="reminder", why="reminders.own")
    app.notify("May I move the study block?", kind="approval", why="deadlines.reminder")
    app.notify("Here's the list.", why="asked")
    app.notify("Lab report due in 2 hours.", why="deadlines.reminder", due=due_in(2))
    app.notify("The call line is down.", why="research.papers", urgent=True)
    assert len(app.out) == 5 and workspace.held_count(app) == 0


def test_without_a_way_to_see_breaks_winners_go_at_once(app):
    app.notify("A new paper on glacier flow.", why="research.papers")
    assert texts(app) == ["A new paper on glacier flow."]
    app.settings.set("mind.workspace.breaks", False)
    app.notify("Another paper.", why="research.papers")
    assert len(app.out) == 2


def test_breaks_from_events_and_the_senses(app, sensing):
    app.notify("A new paper on glacier flow.", why="research.papers")
    breaks.on_event(app, {"kind": "study_session_end"})
    assert len(app.out) == 1 and breaks.last(app)["kind"] == "session_end"
    # a window switch after a long stretch in one window (the activity sense)
    from kurooto.mind.senses import store

    app.settings.set("mind.senses.activity", True)
    now = time.time()
    store.add(app, "activity", "window", "kitty", t=now - 40 * 60)
    store.add(app, "activity", "window", "firefox", t=now - 30)
    assert breaks.detect(app, now) == ["window_switch"]
    assert breaks.detect(app, now + 60) == []  # seen once
    store.add(app, "activity", "window", "kitty", t=now + 90)  # a quick switch back is not a break
    assert breaks.detect(app, now + 120) == []
    breaks.signal(app, "made-up")  # unknown kinds do nothing
    assert breaks._load(app)["counts"] == {"session_end": 1, "window_switch": 1}


def test_max_hold_and_sleep(app, sensing, monkeypatch):
    app.notify("A new paper on glacier flow.", why="research.papers")
    assert workspace.release(app) == 0  # no break yet
    real = time.time
    monkeypatch.setattr(workspace.time, "time", lambda: real() + 91 * 60)
    monkeypatch.setattr(workspace, "asleep", lambda app: True)
    assert workspace.release(app) == 0 and app.out == []  # asleep: not even after the longest hold
    monkeypatch.setattr(workspace, "asleep", lambda app: False)
    assert workspace.release(app) == 1 and len(app.out) == 1
    note = records.why(app, app.out[0].rid)["door"]
    assert re.search(r"waited 9[01] min", note) and "as long as it may" in note


def test_default_bid_from_the_calm_reason(app, monkeypatch):
    assert workspace.bid_kind("checkins.question", "info") == "check-in"
    assert workspace.bid_kind("deadlines.reminder", "info") == "deadline"
    assert workspace.bid_kind("rhythm.absence", "info") == "nudge"
    assert workspace.bid_kind("mind.lab", "info") == "finding"
    assert workspace.bid_kind("updates.done", "info") == "update"
    monkeypatch.setattr(workspace, "welcome_p", lambda app, why: 0.5)  # the pest model's welcome scales the stake
    e = {"key": "m1", "why": "rhythm.absence", "bkind": "nudge", "item": "", "at": time.time(), "msg": {}}
    ws = workspace._state(app)
    s = workspace._score(app, e, time.time(), set(), ws, 5400)
    assert s["stake"] == pytest.approx(0.25) and s["salience"] == pytest.approx(0.25 * 0.4)
    on_mind = workspace._score(app, {**e, "item": "deadline:7"}, time.time(), {"deadline:7"}, ws, 5400)
    assert on_mind["salience"] == pytest.approx(2 * s["salience"])  # about something on its mind: counts double
    aged = workspace._score(app, {**e, "at": time.time() - 5400}, time.time(), set(), ws, 5400)
    assert aged["urgency"] == pytest.approx(0.9)  # waiting raises urgency, so losers aren't starved
    told = workspace._score(app, {**e, "bid": {"surprise": 1.0}}, time.time(), set(), ws, 5400)
    assert told["salience"] == pytest.approx(2 * s["salience"])  # a feature may say it's surprising


def test_the_same_thing_twice_waits_once(app, sensing):
    app.notify("How's the essay?", kind="question", why="checkins.question", item="deadline:4")
    first = workspace._door(app)["pending"][0]["at"]
    app.notify("How's the essay going?", kind="question", why="checkins.question", item="deadline:4")
    d = workspace._door(app)
    assert len(d["pending"]) == 1 and d["pending"][0]["at"] == first and "going" in d["pending"][0]["msg"]["text"]


def test_an_add_on_bidder(app, sensing):
    sent = []

    def bid(a, now):
        return [
            {"kind": "interest", "id": "i1", "stake": 0.9, "urgency": 0.6, "surprise": 0.2,
             "send": lambda: sent.append(1) or a.notify("Something on screen looks like your topic.",
                                                         why="mind.curious")},
            {"kind": "interest", "id": "has words in it", "stake": 1, "urgency": 1, "send": lambda: sent.append(2)},
            {"kind": "interest", "id": "i3", "stake": 1, "urgency": 1},  # nothing to send: ignored
        ]  # fmt: skip

    workspace.add_bidder("body", bid)
    workspace.release(app)
    assert sent == [] and workspace.held_count(app) == 1  # it waits for a break like the rest (it isn't urgent)
    breaks.signal(app, "stood")
    assert sent == [1] and texts(app) == ["Something on screen looks like your topic."]  # it went past the door
    raw = (app.paths.state / workspace.DOOR_FILE).read_text()
    assert "words" not in raw and "screen" not in raw  # numbers and ids only


def test_losers_fold_into_the_evening_bundle(app, sensing, monkeypatch):
    app.settings.set("mind.workspace.capacity", 1)
    app.notify("Essay due tomorrow afternoon.", why="deadlines.reminder", due=due_in(20))
    app.notify("A new paper on glacier flow.", why="research.papers")
    real = time.time
    monkeypatch.setattr(workspace.time, "time", lambda: real() + 7 * 3600)
    monkeypatch.setattr(workspace, "_may_go", lambda app, w, now: "wait")  # no break all that time
    workspace.release(app)
    held = app.calm.held()
    assert [r["held"] for r in held] == ["workspace"] and "glacier" in held[0]["text"]
    assert [e["why"] for e in workspace._door(app)["pending"]] == ["deadlines.reminder"]


def test_off_switches_and_flush(app, sensing):
    app.notify("A new paper on glacier flow.", why="research.papers")
    assert app.out == []
    app.settings.set("mind.workspace.arbiter", False)
    assert workspace.release(app) == 1 and len(app.out) == 1  # turned off: what waited goes now
    app.notify("Another paper.", why="research.papers")
    assert len(app.out) == 2 and workspace.held_count(app) == 0
    app.settings.set("mind.workspace.arbiter", True)
    app.settings.set("modules.enabled", [])
    app.notify("And another.", why="research.papers")  # Brain off: as in 0.8.13
    assert len(app.out) == 3


def test_why_this_and_outcomes(app, monkeypatch):
    monkeypatch.setattr(app, "app_main", lambda: False)  # Telegram is the main channel, the chat gets a copy
    tg = []
    app.notifier.channels["telegram"] = lambda m: tg.append(m) or 42
    app.settings.set("notify.app_chat", True)
    app.notify("How did the problem set go?", kind="question", why="checkins.question")
    m = app.out[-1]
    assert [("Why this?", f"calm:{m.rid}:why")] in m.buttons  # the chat's copy has Why this?
    assert any(b[0] == "Why?" for row in tg[-1].buttons for b in row)  # Telegram keeps Calm's Why?
    (dec,) = [b for k, b in app.facts if k == "decision"]
    assert dec["expect"] == {"what": "reply", "within_h": 3.0}
    w = records.why(app, m.rid)
    assert w["found"] and "check-in" in w["reason"].lower() and w["door"].startswith("went at once")
    assert w["expect"] == "a reply within 3 h" and w["outcome"] == "" and w["sent_today"] == 1
    assert "The door: went at once" in app.calm.why_text(app.calm.get(m.rid))
    records.heard(app)
    assert ("decision_outcome", {"decision": dec["id"], "result": "replied", "value": 1.0}) in app.facts
    assert records.why(app, m.rid)["outcome"] == "replied"
    # a nudge expects to be acted on within 2 h; nothing came: missed
    app.notify("Start the lab report: 25 minutes now?", why="rhythm.lighter", buttons=[[("Start", "x:1:start")]])
    real = time.time
    monkeypatch.setattr(records.time, "time", lambda: real() + 2 * 3600 + 60)
    assert records.sweep(app) == 1
    assert app.facts[-1][0] == "decision_outcome" and app.facts[-1][1]["result"] == "missed"
    assert records.why(app, "nope")["found"] is False
    app.settings.set("mind.why.on", False)
    assert records.why_lines(app, m.rid) == []


def test_outcome_written_by_the_scorekeeper(tmp_path, monkeypatch):
    from kurooto.mind import log as mlog
    from kurooto.mind import scorekeeper as sk

    monkeypatch.setattr(mlog, "_writer_pid", None)
    k = sk.Keeper(tmp_path / "mind")
    try:
        rec = records.make("message:question", expect={"what": "reply", "within_h": 3})
        assert k.append("decision", rec)["ok"]
        assert k.append("decision_outcome", {"decision": rec["id"], "result": "replied", "value": 1})["ok"]
        assert "error" in k.append("decision_outcome", {"decision": rec["id"], "result": "anything you like"})
        rows = k.log.read(0, ["decision", "outcome"])
        assert rows[0].body["expect"] == {"what": "reply", "within_h": 3.0}
        want = {"decision": rec["id"], "result": "replied", "value": 1.0}
        assert rows[-1].kind == "outcome" and rows[-1].body == want
    finally:
        k.close()
    assert records.make("x", expect={"what": "smile", "within_h": 3}).get("expect") is None

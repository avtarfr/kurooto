"""Brain, 0.8.8: the not-a-pest model (Beta counts of welcome and rejection per kind, hour band and his state) and the
daemon's half of the talk reward (its facts carry no content)."""

import time

import pytest

from kurooto import mind
from kurooto.core.notify import Message
from kurooto.mind import gate, pest


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    a = App()
    a.settings.set("modules.enabled", ["mind"])
    a.settings.set("notify.calm.messages", 50)
    facts = []
    monkeypatch.setattr(mind.connect(a), "report", lambda kind, body: facts.append((kind, body)) or True)
    a.facts = facts
    out = []
    a.notifier.channels["chat"] = lambda m: out.append(m) or "c1"
    monkeypatch.setattr(a, "app_main", lambda: True)
    monkeypatch.setattr(gate, "woke_at", lambda app: None)
    a.out = out
    yield a
    mind.forget_client(a)
    a.close()


def test_kinds_bands_and_the_prior():
    assert pest.kind_of("mind.lab") == "finding" and pest.kind_of("mind.excited") == "excitement"
    assert pest.kind_of("rhythm.absence") == "nudge" and pest.kind_of("mood.ask") == "check-in"
    assert pest.kind_of("deadlines.reminder") is None  # reminders you set aren't its own kinds
    assert [pest.band(h) for h in (3, 9, 15, 21)] == ["night", "morning", "afternoon", "evening"]
    d = {"cells": {}}
    assert pest.expected(d, "finding", "morning", "free") == pytest.approx(2 / 3)  # starts out welcome


def test_rejections_weigh_three_and_fade():
    t = time.time()
    d = {"cells": {}}
    pest._count(d, "finding|morning|free", True, t)
    assert pest.expected(d, "finding", "morning", "free", t) == pytest.approx(3 / 4)
    pest._count(d, "finding|morning|free", False, t)  # one rejection outweighs a welcome threefold
    assert pest.expected(d, "finding", "morning", "free", t) == pytest.approx(3 / 7)
    assert pest.expected(d, "finding", "morning", "free", t) <= pest.THRESHOLD
    later = t + 30 * 86400  # a month on, the counts have faded: it may try again
    assert pest.expected(d, "finding", "morning", "free", later) > pest.THRESHOLD
    # another cell of the kind lends a quarter of its weight; another kind lends nothing
    assert pest.expected(d, "finding", "evening", "late", t) < 2 / 3
    assert pest.expected(d, "nudge", "morning", "free", t) == pytest.approx(2 / 3)


def test_welcome_ignored_less_and_acted(app):
    """Answered within the hour: welcome. An hour of silence: rejected. Less of this: rejected. A button: acted on."""
    msg = Message(
        "Found: the lab's third run replicated.", why="mind.lab", rid="r1", buttons=[[("Open", "lab:1:open")]]
    )
    pest.sent(app, msg)
    assert ("talk_unprompted", {}) in app.facts
    pest.heard(app, "oh nice")
    d = pest._load(app)
    assert d["pending"][-1]["done"] == "welcome" and next(iter(d["cells"].values()))["a"] == 1
    kinds = [k for k, _ in app.facts]
    assert "talk_heard" in kinds and "talk_rejected" not in kinds
    pest.tapped(app, "calm:r1:less")  # Less of this, even after a reply: a rejection, and it costs the talk reward
    assert pest._load(app)["pending"][-1]["done"] == "less" and ("talk_rejected", {"how": "less"}) in app.facts
    pest.sent(app, Message("Another finding.", why="mind.lab", rid="r2", buttons=[[("Open", "lab:2:open")]]))
    pest.tapped(app, "lab:2:open")
    assert pest._load(app)["pending"][-1]["done"] == "welcome"
    pest.sent(app, Message("A third.", why="mind.lab", rid="r3"))
    d = pest._load(app)
    d["pending"][-1]["at"] -= 3700
    pest._save(app, d)
    assert pest.sweep(app) == 0
    assert pest._load(app)["pending"][-1]["done"] == "ignored" and ("talk_rejected", {"how": "ignored"}) in app.facts


def test_talk_facts_carry_no_content(app):
    pest.heard(app, "here is something private about my day")
    pest.heard(app, "/mind learning")
    heard = [b for k, b in app.facts if k == "talk_heard"]
    assert heard[0] == {"flags": {"focus": False, "asleep": heard[0]["flags"]["asleep"], "exam": False},
                        "command": False}  # fmt: skip
    assert heard[1]["command"] is True
    assert all(set(b) == {"flags", "command"} and set(b["flags"]) == {"focus", "asleep", "exam"} for b in heard)
    app.availability.set_focus(__import__("datetime").datetime.now() + __import__("datetime").timedelta(hours=1))
    pest.heard(app, "in focus")
    assert [b for k, b in app.facts if k == "talk_heard"][-1]["flags"]["focus"] is True


def test_an_add_ons_meeting_is_a_fact_with_only_a_number_and_the_flags(app):
    assert pest.met(app, 0.8)
    pest.met(app, 7)  # clipped
    pest.met(app, float("nan"))
    met = [b for k, b in app.facts if k == "talk_met"]
    assert [b["quality"] for b in met] == [0.8, 1.0, 0.0]
    assert all(set(b) == {"quality", "flags"} and set(b["flags"]) == {"focus", "asleep", "exam"} for b in met)
    assert pest.met(app, "not a number") is False  # never raises
    app.settings.set("mind.talk.met", False)
    assert pest.met(app, 1.0) is False
    app.settings.set("mind.talk.met", True)
    app.settings.set("mind.talk.on", False)
    assert pest.met(app, 1.0) is False
    app.settings.set("mind.talk.on", True)
    app.settings.set("modules.enabled", [])  # Brain off
    assert pest.met(app, 1.0) is False and len([k for k, _ in app.facts if k == "talk_met"]) == 3


def test_every_unprompted_message_is_its_own_ping(app):
    """Through the notifier: anything it sends by itself is a talk_unprompted fact (exempt kinds too), so no message
    of its own can buy an answer's worth; an answer to you isn't."""
    app.notifier.send("The lab report is due Friday.", kind="info", why="deadlines.reminder")
    app.notifier.send("Here you go.", kind="info", why="asked")
    assert [k for k, _ in app.facts].count("talk_unprompted") == 1


def test_switches(app, tmp_path):
    app.settings.set("mind.talk.on", False)
    pest.heard(app, "hello")
    pest.sent(app, Message("x", why="mind.lab"))
    assert not [k for k, _ in app.facts if k.startswith("talk_")]
    assert pest._load(app)["pending"]  # the model still learns
    app.settings.set("mind.pest.on", False)
    assert pest.welcome(app, Message("x", why="mind.lab")) == (True, 1.0)
    assert pest.lines(app) == ["Not-a-pest model: off (mind.pest.on)."]
    app.settings.set("modules.enabled", [])  # Brain off: nothing at all
    (app.paths.state / pest.FILE).unlink()
    app.settings.set("mind.pest.on", True)
    app.settings.set("mind.talk.on", True)
    pest.heard(app, "hello")
    pest.sent(app, Message("x", why="mind.lab"))
    assert not (app.paths.state / pest.FILE).exists()


def test_shown_in_mind_learning(app):
    from kurooto.mind import report

    text = report.learning_text(app)
    assert "Not a pest" in text and "finding: 67% expected welcome (may go)" in text
    assert "Talk reward today: 0 messages counted" in text and "Mood: not measured yet." in text

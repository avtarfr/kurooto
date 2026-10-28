"""Brain's model of you hears what you state in a message (L94, 0.9.0, mind.tom.from_chat): goals and a deadline's
due date become rows with source "said"; health, money and the deny-list never do; off, nothing."""

from __future__ import annotations

import datetime as dt

from kurooto.core.clock import now
from kurooto.mind.tom import model


def test_goals_and_due_dates_you_state(env, monkeypatch):
    app = env.app
    monkeypatch.setattr(model, "on", lambda a: True)
    env.on("deadlines")
    dl = app.modules["deadlines"]
    dl.add("Topology essay", now() + dt.timedelta(days=3))
    n = model.from_chat(app, "My goal is to finish the topology draft by friday. The topology essay is due monday.")
    assert n == 2
    rows = {r["part"]: r for r in model.rows(app)}
    assert rows["goal"]["source"] == "said" and rows["goal"]["claim"].startswith("finish the topology draft")
    assert rows["goal"]["evidence"] == ["chat"]
    assert rows["belief"]["fact"]["type"] == "deadline" and rows["belief"]["source"] == "said"
    before = len(model.rows(app))
    assert model.from_chat(app, "I want to see a doctor about my health by friday.") == 0  # never health
    assert model.from_chat(app, "I want to pay the rent by friday.") == 0  # nor money
    assert model.from_chat(app, "/remind me to finish the draft") == 0
    app.settings.set("mind.tom.from_chat", False)
    assert model.from_chat(app, "I want to finish the measure theory notes by sunday.") == 0
    assert len(model.rows(app)) == before


def test_app_handle_feeds_it(env, monkeypatch):
    seen = []
    monkeypatch.setattr(model, "from_chat", lambda a, t: seen.append(t) or 0)
    env.say("I want to finish the lab report by thursday")
    assert seen == ["I want to finish the lab report by thursday"]

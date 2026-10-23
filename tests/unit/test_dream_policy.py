"""Dream RSI, part two (core/policy.py): the policy for messages that come by themselves, replayed each night on what
was recorded; today's policy is always a candidate, so the result is never worse on the replay; reasons that always
come are never touched; at most one change a night, applied through Calm with Undo; the runtime side in Calm
(habituation, hours) and /dream policy."""

from __future__ import annotations

import datetime as dt
import uuid

import pytest

from kurooto.core import calm as calm_mod
from kurooto.core import events as events_mod
from kurooto.core import policy as policy_mod
from kurooto.modules import dreaming as dreaming_mod

MON = dt.date(2026, 11, 2)
START = MON - dt.timedelta(days=14)


def at(day: dt.date, h: int, m: int = 0) -> dt.datetime:
    return dt.datetime.combine(day, dt.time(h, m))


@pytest.fixture
def clock(env, monkeypatch):
    t = {"now": at(MON, 7, 30)}
    for mod in (calm_mod, policy_mod, dreaming_mod, events_mod):
        monkeypatch.setattr(mod, "now", lambda: t["now"])
    env.app.settings.set("availability.night.enabled", False)
    return t


def put(app, why: str, t: dt.datetime, answered_min: float | None = None, exempt: str = "", buttons: str = '["x:1:a"]'):
    """One recorded message that came by itself (answered that many minutes later, or not at all)."""
    app.calm._insert(
        {
            "id": "n" + uuid.uuid4().hex[:10],
            "ts": t.timestamp(),
            "day": t.date().isoformat(),
            "why": why,
            "kind": "question",
            "state": "sent",
            "exempt": exempt,
            "buttons": buttons,
            "map_kind": "",
            "answered": None if answered_min is None else t.timestamp() + answered_min * 60,
            "budgeted": 0 if exempt else 1,
        }
    )


def history(app):
    """Two weeks: questions about quiet projects answered at first, then ignored ten days running; start-by messages
    always answered; your own reminders and deadline reminders ignored (they're never tuned)."""
    for k in range(13):
        day = START + dt.timedelta(days=k)
        put(app, "research.idle", at(day, 10), 10 if k < 3 else None)
        if k % 2 == 0:
            put(app, "startby.tell", at(day, 9), 45)
        put(app, "reminders.own", at(day, 8), exempt="own")
        put(app, "deadlines.reminder", at(day, 12))


def test_ignored_kind_gets_used_to_with_a_line_and_undo(env, clock):
    app = env.app
    history(app)
    d = policy_mod.tune(app)
    assert d["applied"] and (d["kind"], d["lever"], d["value"]) == ("research.idle", "habituate", 2)
    assert (d["saved"], d["delayed"], d["days"]) == (8, 0, 14) and d["best"] - d["score"] >= 3
    assert app.settings.get("notify.calm.habituate") == {"research.idle": 2}
    assert policy_mod.tune(app) is None  # one round (one change) a night
    # the morning message says it, with Undo (and /dream shows it again)
    clock["now"] = at(MON, 7, 31)
    env.on("dreaming")
    text = app.modules["dreaming"].report(send=False)
    assert (
        "Learned while you slept: questions about quiet projects wait for your evening bundle once 2 in a row go "
        "unanswered; over the last 14 days that would have saved 8 ignored pings and delayed none you answered."
    ) in text
    lines, undo = policy_mod.morning(app, send=False)
    assert undo == [[("Undo", f"calm:{d['uid']}:undo")]]
    env.press(f"calm:{d['uid']}:undo")
    assert app.settings.get("notify.calm.habituate") == {}
    # the next night it leaves that kind alone (undone), and changes nothing else
    clock["now"] = at(MON + dt.timedelta(days=1), 7, 30)
    d2 = policy_mod.tune(app)
    assert not d2["applied"] and d2.get("kind") != "research.idle"
    assert app.settings.get("notify.calm.habituate") == {} and app.settings.get("notify.calm.evening") == []


def test_todays_policy_is_a_candidate_and_never_loses(env, clock):
    app = env.app
    for k in range(13):  # everything answered: nothing to gain, nothing changes
        put(app, "research.idle", at(START + dt.timedelta(days=k), 10), 5)
    d = policy_mod.tune(app)
    assert not d["applied"] and d["best"] == d["score"] and d["candidates"] >= 1
    # a mix where bundling everything would delay quick answers: the replay never picks a worse policy than today's
    history(app)
    rows = policy_mod.record(app)
    cur = policy_mod.today(app)
    base = policy_mod.replay(app, cur, rows).score
    cands = policy_mod.propose(app, cur, rows, set())
    assert cands and all(c.lever and c.kind == "research.idle" for c in cands)
    evening = next(c for c in cands if c.lever == "evening")
    assert policy_mod.replay(app, evening, rows).score < base  # the quick answers would have waited till 20:00
    # a small margin of difference isn't enough
    clock["now"] = at(MON + dt.timedelta(days=1), 7, 30)
    app.settings.set("dreaming.tune_margin", 100)
    assert not policy_mod.tune(app)["applied"] and app.settings.get("notify.calm.habituate") == {}


def test_reasons_that_always_come_and_never_tune_are_untouched(env, clock):
    app = env.app
    for k in range(13):
        day = START + dt.timedelta(days=k)
        put(app, "reminders.own", at(day, 8), exempt="own")
        put(app, "deadlines.reminder", at(day, 12))  # dreaming.never_tune
        put(app, "research.idle", at(day, 10), exempt="deadline")  # a deadline under 12 hours: always comes
        put(app, "quiz.offer", at(day, 19))  # can't wait for the evening (Reason.later False)
    rows = policy_mod.record(app)
    assert {r.why for r in rows} == {"deadlines.reminder", "quiz.offer"}  # exempt ones aren't even replayed
    assert policy_mod.propose(app, policy_mod.today(app), rows, set()) == []
    d = policy_mod.tune(app)
    assert not d["applied"] and "kind" not in d
    # a kind you set yourself is yours: never proposed again
    app.settings.set("notify.calm.evening", ["research.idle"])
    history(app)
    assert all(
        c.kind != "research.idle" for c in policy_mod.propose(app, policy_mod.today(app), policy_mod.record(app), set())
    )


def test_calm_holds_a_kind_you_stopped_answering_and_outside_its_hours(env, clock):
    app = env.app
    calm = app.calm
    put(app, "research.idle", at(MON, 6))
    put(app, "research.idle", at(MON - dt.timedelta(days=1), 10))
    app.settings.set("notify.calm.habituate", {"research.idle": 2})
    clock["now"] = at(MON, 10)
    app.notify("Thesis code: no commits for 9 days. Still on it?", why="research.idle", buttons=[[("Yes", "x:2:a")]])
    assert [r["held"] for r in calm.held() if r["why"] == "research.idle"] == ["habit"]
    # you answer one: the run ends, and the next comes as it happens
    with calm._db() as db:
        db.execute(
            "update sent set answered=? where why='research.idle' and ts=?",
            (at(MON, 9).timestamp(), at(MON, 6).timestamp()),
        )
    assert calm.ignored("research.idle", at(MON, 10)) == 0
    # hours: outside them it waits
    app.settings.set("notify.calm.windows", {"startby.tell": "17:00-19:00"})
    app.notify("Start the report by Wednesday.", why="startby.tell")
    assert [r["held"] for r in calm.held() if r["why"] == "startby.tell"] == ["window"]
    out = env.say("/calm")
    assert "questions about quiet projects after 2 unanswered in a row" in out and "(17:00-19:00)" in out
    assert calm_mod.inside("22:00-06:00", at(MON, 23)) and not calm_mod.inside("22:00-06:00", at(MON, 12))


def test_dream_policy_shows_the_rules_and_the_decisions(env, clock):
    app = env.app
    env.on("dreaming")
    history(app)
    policy_mod.tune(app)
    out = env.say("/dream policy")
    assert "Evening once that many in a row go unanswered: questions about quiet projects after 2." in out
    assert "Never tuned: the alarm, your reminders" in out and "replay score" in out
    assert "questions about quiet projects wait for your evening bundle once 2" in out

"""Commitments (modules/commitments.py): regular things that aren't classes hold calls like a class; skip one for a day;
"every Tuesday and Thursday at 7pm I go to the gym" adds one with Undo (core/infer.py)."""

import datetime as dt

from kurooto.core import infer
from kurooto.modules.commitments import parse_days


def test_days_are_read_the_ways_people_say_them():
    assert parse_days("mon,wed,fri") == ["mon", "wed", "fri"]
    assert parse_days("Tuesday and Thursday") == ["tue", "thu"]
    assert parse_days("weekdays") == ["mon", "tue", "wed", "thu", "fri"]
    assert parse_days("fri-mon") == ["mon", "fri", "sat", "sun"]
    assert parse_days("daily") == ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    assert parse_days("someday") == []


def test_a_commitment_holds_calls_and_a_skipped_one_doesnt(env):
    app = env.app
    env.on("commitments")
    out = env.say("/busy add gym daily 18:00-19:00")
    assert out == "Added gym: daily 18:00–19:00. Calls wait while it's on."
    today = dt.date.today()
    during = dt.datetime.combine(today, dt.time(18, 30))
    reason, until = app.availability.call_block(during)
    assert reason == "commitment: gym" and until == dt.datetime.combine(today, dt.time(19, 0))
    assert "gym: daily 18:00–19:00" in env.say("/busy")
    assert env.say("/busy skip gym").startswith("Skipping gym today")
    assert app.modules["commitments"]._block(during) is None
    assert "(skipping today)" in env.say("/busy")
    env.say("/busy unskip gym")
    env.say("/busy calls gym off")
    assert app.modules["commitments"]._block(during) is None  # it no longer holds calls
    assert env.say("/busy remove gym") == "Removed gym."
    assert env.say("/busy").startswith("No commitments yet")


def test_a_night_shift_holds_calls_past_midnight(env):
    app = env.app
    app.settings.set("availability.night.enabled", False)
    env.on("commitments")
    env.say("/busy add night shift daily 22:00-06:00")
    t = dt.datetime.combine(dt.date.today(), dt.time(2, 0))
    reason, until = app.availability.call_block(t)
    assert reason == "commitment: night shift" and until == dt.datetime.combine(dt.date.today(), dt.time(6, 0))


def test_skipping_one_in_plain_english(env):
    env.on("commitments")
    env.say("/busy add gym daily 18:00-19:00")
    assert env.say("skipping gym today").startswith("Skipping gym today")
    assert "gym" in env.app.modules["commitments"].skipped()


def test_said_in_passing_it_becomes_a_commitment_and_undo_takes_it_back(env):
    app = env.app
    assert not app.is_on("commitments")
    told = infer.observe(app, "Every Tuesday and Thursday at 7pm I go to the gym, ugh.")
    assert told == ["Added gym to your commitments: Tue, Thu 19:00–20:00; calls wait while it's on."]
    assert app.is_on("commitments")
    assert infer.observe(app, "I work a shift every weekend from 9 to 5") == [
        "Added shift to your commitments: weekends 09:00–17:00; calls wait while it's on."
    ]
    assert infer.observe(app, "We have standup every weekday at 10") == [
        "Added standup to your commitments: weekdays 10:00–11:00; calls wait while it's on."
    ]
    # not commitments: someone else's, a negation, a class, a test
    for line in (
        "My brother goes to the gym every monday at 6",
        "I don't go to the gym every friday at 6 any more",
        "every Monday at 9 I have a physics lab",
        "I have a quiz every friday at 3",
    ):
        assert infer.observe(app, line) == [], line
    items = infer._load(app)["items"]
    for it in items[1:]:
        infer.undo(app, it["id"])
    assert [r["name"] for r in app.modules["commitments"].items()] == ["gym"]
    assert app.is_on("commitments")
    assert infer.undo(app, items[0]["id"]).startswith("Undone: Added gym to your commitments")
    assert not app.modules["commitments"].items() and not app.is_on("commitments")  # it turned it on: off again

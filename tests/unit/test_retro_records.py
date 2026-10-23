"""The nightly look back's rules (modules/retro.py records()): a routine seen in the records (the same thing at the
same time on 3+ weeks) is asked about with Add / No; a data fix it is sure of (two copies of one deadline) is made
at once with Undo; nothing guarded by core/tap.py is ever among them."""

import datetime as dt
import json

import pytest

from kurooto.core import tap
from kurooto.core.clock import now
from tests.fakes.openai import FakeOpenAI


@pytest.fixture
def look(env):
    """The look back on (it needs Chat, which needs an AI: a pretend one), with a subject."""
    ai = FakeOpenAI()
    app = env.app
    app.settings.set("availability.night.enabled", False)
    app.secrets.set("custom.api_key", ai.key)
    app.settings.set("brain.base_urls", {"custom": ai.base})
    app.settings.set("brain.models", {"custom": {"medium": "m", "low": "m", "high": "m"}})
    app.settings.set("brain.main", "custom")
    env.on("subjects", "deadlines", "chat", "retro")
    env.say("/subject add Linear Algebra (la)")
    yield env
    ai.close()


def past(app, kind: str, t: dt.datetime, **fields) -> None:
    """An event as if it had happened at t."""
    with open(app.events.file, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": t.isoformat(), "kind": kind, **fields}) + "\n")


def last_buttons(env):
    msg = [p for m, p in env.fake.sent if m == "sendMessage"][-1]
    return msg["text"], [b["callback_data"] for row in msg["reply_markup"]["inline_keyboard"] for b in row]


def test_a_routine_seen_on_three_weeks_is_asked_about_and_add_makes_it_one(look):
    env, app = look, look.app
    retro = app.modules["retro"]
    base = dt.datetime.combine(now().date() - dt.timedelta(days=now().weekday() + 6), dt.time(18, 5))  # a Tuesday
    for w in (0, 1, 2):
        past(app, "study_session_start", base - dt.timedelta(weeks=w), subject="linear-algebra", planned=90)
    for w in (0, 1):  # calls held on two weeks only: not a routine yet
        t = base.replace(hour=21) - dt.timedelta(weeks=w)
        past(app, "calls_held", t, until=(t + dt.timedelta(hours=1)).isoformat())
    (seen,) = retro.routines_seen()
    assert seen["name"] == "study linear algebra" and seen["days"] == ["tue"]
    assert (seen["start"], seen["end"], seen["weeks"]) == ("18:00", "19:30", 3)
    assert retro.records() == (1, 0)
    text, buttons = last_buttons(env)
    assert "you started studying Linear Algebra around Tue 18:00 on 3 different weeks" in text
    assert not app.modules["commitments"].items()  # nothing until you tap
    assert retro.records() == (0, 0)  # asked once, not every night
    assert env.press(buttons[0]).startswith("Added study linear algebra to your commitments: Tue 18:00–19:30")
    assert app.is_on("commitments") and app.modules["commitments"].find("study linear algebra")


def test_no_keeps_a_routine_away_and_a_class_at_that_time_covers_it(look):
    env, app = look, look.app
    retro = app.modules["retro"]
    base = dt.datetime.combine(now().date() - dt.timedelta(days=now().weekday() + 4), dt.time(10, 0))  # a Thursday
    for w in (0, 1, 2, 3):
        t = base - dt.timedelta(weeks=w)
        past(app, "calls_held", t, until=(t + dt.timedelta(minutes=45)).isoformat())
    assert retro.records() == (1, 0)
    _, buttons = last_buttons(env)
    assert env.press(buttons[1]).startswith("OK, I won't suggest that again")
    assert retro.records() == (0, 0) and not app.modules["commitments"].items()
    retro._save_state({**retro._state(), "routines": {}})  # forgotten: a class at that time covers it now
    env.say("/class thu 10:00-11:00 la")
    assert retro.records() == (0, 0)


def test_two_copies_of_one_deadline_become_one_at_once_with_undo(look):
    env, app = look, look.app
    dl = app.modules["deadlines"]
    due = (now() + dt.timedelta(days=3)).replace(hour=23, minute=59, second=0, microsecond=0)
    dl.add("Linear Algebra: Problem set 3", due, source="classroom", link="https://example.org/ps3")
    dl.add("LA problem set 3", due.replace(hour=17, minute=0) - dt.timedelta(days=1), source="manual")
    dl.add("LA problem set 3 prep quiz", due, source="manual")  # more words: not sure, left alone
    dl.add("Problem set 4", due, source="manual")  # another number: never the same thing
    assert len(dl.items()) == 4  # a day apart when they came in: kept apart
    said = next(i for i, it in dl.items().items() if it["title"] == "LA problem set 3")
    dl.move(said, due.replace(hour=17, minute=0))  # you moved yours to Classroom's day: now two copies
    retro = app.modules["retro"]
    assert retro.records() == (0, 1)
    text, buttons = last_buttons(env)
    assert "was on your list twice, from Classroom and what you said; I kept one." in text
    items = dl.items()
    assert len(items) == 3 and said not in items
    kept = next(it for it in items.values() if it["title"] == "Linear Algebra: Problem set 3")
    assert kept["sources"] == ["classroom", "manual"] and kept["due"].endswith("T17:00:00")  # a known time wins
    assert dl._resolve(items, said) is not None  # the copy's buttons still reach the one kept
    assert retro.records() == (0, 0)  # nothing left to fix
    assert env.press(buttons[0]) == "Undone: both copies are back."
    items = dl.items()
    assert len(items) == 4 and items[said]["title"] == "LA problem set 3"
    kept = next(it for it in items.values() if it["title"] == "Linear Algebra: Problem set 3")
    assert kept["sources"] == ["classroom"] and kept["due"].endswith("T23:59:00") and not kept.get("aliases")
    assert retro.undo_fix(retro._state()["fixes"][-1]["id"]) == "Undone already."
    app.settings.set("retro.fixes", False)
    assert retro.records() == (0, 0)


def test_what_the_look_back_does_by_itself_is_never_guarded():
    assert tap.BY_ITSELF and not set(tap.BY_ITSELF) & set(tap.GUARDED)
    assert not any(k.split(".")[0] in ("alarm", "call", "send", "mail") for k in tap.BY_ITSELF)

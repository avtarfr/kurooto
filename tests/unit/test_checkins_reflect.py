"""The evening check-in's reflection (modules/checkins.py, checkins.reflect): up to three things the day's records show
you did (deadlines done or moved on, threads closed, study time), never what you said; nothing recorded, no list; one
question about tomorrow; Not tonight ends it; the setting turns it off."""

import datetime as dt
import json

import pytest

from kurooto.core import threads


@pytest.fixture
def ev(env):
    env.on("checkins", "deadlines", "subjects", "study")
    c = env.app.modules["checkins"]
    c._save({"evening": {"time": "22:00", "status": "planned"}})
    return env, c


def fire(env, c):
    c._fire({"name": "evening", "day": c.day_of().isoformat()})
    sent = [p for m, p in env.fake.sent if m == "sendMessage"][-1]
    return sent["text"], json.dumps(sent.get("reply_markup") or {})


def test_it_lists_only_what_was_recorded(ev):
    env, c = ev
    app = env.app
    dl = app.modules["deadlines"]
    due = dt.datetime.now() + dt.timedelta(days=2)
    for title in ("Problem set 3", "Essay draft", "Lab report"):
        dl.add(title, due)
    ids = {it["title"]: i for i, it in dl.items().items()}
    dl._status(ids["Problem set 3"], "done")
    dl.progress("Essay draft", 4, 7)
    env.say("/subject add Linear Algebra (la)")
    app.modules["study"].add(app.modules["subjects"].resolve("la"), 5400)
    env.say("I'll send the glacier draft to Ortiz tonight.")  # said, then closed by what you said you did
    env.say("I sent the glacier draft to Ortiz.")
    env.say("I finished the lab report today, honestly.")  # words alone: not a record, so not listed
    assert c.done_today(c.day_of()) == [
        "Problem set 3: done",
        "send the glacier draft to Ortiz tonight: done",
        "Essay draft: 4 of 7 done",
    ]  # three at most: the study time doesn't fit
    text, buttons = fire(env, c)
    assert text.startswith("Evening check-in: How did today go?")
    assert "From today's records:\n- Problem set 3: done\n- send the glacier draft" in text
    assert "Lab report" not in text and "Studied" not in text
    assert "What's first tomorrow?" in text
    for word in ("streak", "score", "missed", "proud"):
        assert word not in text.lower()
    assert "Not tonight" in buttons and "Skip today" not in buttons


def test_fewer_than_three_and_none(ev):
    env, c = ev
    app = env.app
    env.say("/subject add Linear Algebra (la)")
    app.modules["study"].add(app.modules["subjects"].resolve("la"), 5400)
    app.modules["study"].add(app.modules["subjects"].resolve("la"), 300, day=c.day_of() - dt.timedelta(days=1))
    assert c.done_today(c.day_of()) == ["Studied Linear Algebra 1.5 h"]
    assert c.done_today(c.day_of() - dt.timedelta(days=1)) == []  # 5 minutes isn't a session worth telling


def test_nothing_recorded_skips_the_list_but_asks_about_tomorrow(ev):
    env, c = ev
    text, _ = fire(env, c)
    assert "From today's records" not in text and "nothing" not in text.lower()
    assert "What's first tomorrow?" in text


def test_not_tonight_ends_the_check_in(ev):
    env, c = ev
    _, buttons = fire(env, c)
    day = c.day_of().isoformat()
    assert f"chk:evening|{day}:not" in buttons
    assert env.press(f"chk:evening|{day}:not") == "OK, not tonight."
    assert c.today()["evening"]["status"] == "skipped"


def test_the_setting_turns_it_off(ev):
    env, c = ev
    env.app.settings.set("checkins.reflect", False)
    dl = env.app.modules["deadlines"]
    dl.add("Problem set 3", dt.datetime.now() + dt.timedelta(days=1))
    dl._status(next(iter(dl.items())), "done")
    text, buttons = fire(env, c)
    assert "From today's records" not in text and "What's first tomorrow?" not in text
    assert "Skip today" in buttons and "Not tonight" not in buttons
    assert "From today's records" not in c.script("evening")


def test_the_evening_call_script_says_them_back(ev):
    env, c = ev
    dl = env.app.modules["deadlines"]
    dl.add("Problem set 3", dt.datetime.now() + dt.timedelta(days=1))
    dl._status(next(iter(dl.items())), "done")
    assert "From today's records they did: Problem set 3: done." in c.script("evening")


def test_a_thread_of_a_deadline_is_told_once(ev):
    env, c = ev
    dl = env.app.modules["deadlines"]
    dl.add("Problem set 3", dt.datetime.now() + dt.timedelta(days=1))
    dl.progress("Problem set 3", 3, 7)  # opens a thread keyed to the deadline
    dl._status(next(iter(dl.items())), "done")  # closes it
    assert threads.closed_between(env.app, 0, 2e9)  # the thread did close
    assert c.done_today(c.day_of()) == ["Problem set 3: done"]

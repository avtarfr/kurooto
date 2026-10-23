"""Open threads: what you said you'd do (in a chat or on a call) and tasks you started stay open until done, dropped
or untouched for a week; "did I finish that thing?" resolves from the last 48 hours and asks once when two fit; a
thread found that way is only read or asked about, and every close has Undo."""

import datetime as dt
import json
import time

import pytest

from kurooto.core import ledger, threads


@pytest.fixture
def two(env):
    """One thread from a chat, one from what was said on a call."""
    app = env.app
    env.say("I'll send the glacier draft to Ortiz tonight.")
    app.settings.set("availability.night.enabled", False)
    c = app.modules["calls"]
    c.save_transcript(
        {
            "lines": [
                {"who": app.name, "text": "Anything else for tomorrow? I'll keep it short."},
                {"who": "You", "text": "Yes. I need to book the wind tunnel slot before Friday."},
            ],
            "since": "5",
            "purpose": "Evening check-in",
        }
    )
    return env


def test_threads_open_from_a_chat_and_from_a_call(two):
    env = two
    rows = threads.open_threads(env.app)
    assert [(r["text"], r["via"]) for r in rows] == [
        ("book the wind tunnel slot before Friday", "call"),
        ("send the glacier draft to Ortiz tonight", "chat"),
    ]
    assert ledger.said(rows[0]).startswith("said on the call at ") and rows[1]["due"]  # "tonight" is when
    out = env.say("/threads")
    assert out.startswith("What you're in the middle of:\n1. book the wind tunnel slot before Friday (said on the call")
    sent = [p for m, p in env.fake.sent if m == "sendMessage"][-1]
    assert f"thr:{rows[0]['id']}:done" in json.dumps(sent["reply_markup"])
    # Kurooto's own words on the call open nothing; neither do questions, health/money lines or "remind me"
    for s in ("Should I send the draft?", "I need to pay my rent tonight", "Remind me at 9 to call mum", "I'll be"):
        threads.observe(env.app, s)
    assert len(threads.open_threads(env.app)) == 2


def test_that_thing_asks_once_when_two_fit_and_never_acts(two):
    env = two
    out = env.say("did I finish that thing?")
    assert out == "Which one do you mean? These are from the last 48 hours:"
    sent = [p for m, p in env.fake.sent if m == "sendMessage"][-1]
    labels = [b[0]["text"] for b in sent["reply_markup"]["inline_keyboard"]]
    assert labels == ["book the wind tunnel slot before Friday", "send the glacier draft to Ortiz tonight"]
    out = env.say("did I finish that wind tunnel thing?")
    assert out.startswith('That\'s "book the wind tunnel slot before Friday" (said on the call at ')
    assert out.endswith("It's still open.")
    assert len(threads.open_threads(env.app)) == 2  # read, not acted on
    out = env.say("the glacier thing is done")
    assert out.startswith('Closed "send the glacier draft to Ortiz tonight"')
    (r,) = [r for r in ledger.of(env.app).rows(("thread",)) if r["sub"] == "done"]
    assert env.press(f"thr:{r['id']}:undo").startswith("Open again")


def test_saying_its_done_closes_it_with_undo_and_old_ones_close_by_themselves(two):
    env = two
    app = env.app
    threads.observe(app, "I sent the glacier draft to Ortiz.")
    (r,) = [r for r in ledger.of(app).rows(("thread",)) if r["sub"] == "done"]
    assert r["text"] == "send the glacier draft to Ortiz tonight"
    out = env.say("/threads")
    assert "Closed in the last 48 hours:\n- send the glacier draft to Ortiz tonight: done" in out
    assert env.press(f"thr:{r['id']}:undo") == 'Open again: "send the glacier draft to Ortiz tonight".'
    assert env.say("/threads drop 2").startswith('Dropped: "send the glacier draft')
    assert threads.expire(app, time.time() + 8 * 86400) == 1  # memory.thread_days (7) untouched
    assert threads.open_threads(app) == []


def test_started_tasks_are_threads_until_done(env):
    app = env.app
    env.on("deadlines")
    dl = app.modules["deadlines"]
    dl.add("Problem set 3", dt.datetime.now() + dt.timedelta(days=2))
    dl.progress("problem set 3", 4, 7)
    (r,) = threads.open_threads(app)
    assert r["text"] == "Problem set 3 (4 of 7 done)" and r["via"] == "deadline"
    dl.progress("problem set 3", 5, 7)
    (r,) = threads.open_threads(app)
    assert r["text"] == "Problem set 3 (5 of 7 done)"  # the same thread, its words kept new
    (i,) = dl.items()
    dl._button(i, "done")
    assert threads.open_threads(app) == []


def test_off_opens_nothing(env):
    env.app.settings.set("memory.threads", False)
    env.say("I'll send the glacier draft tonight.")
    assert threads.open_threads(env.app) == []
    assert env.say("/threads").startswith("Nothing open (memory.threads is off)")

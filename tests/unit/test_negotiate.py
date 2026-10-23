"""Negotiate, don't repeat (modules/startby.py, modules/deadlines.py): a reminder that would repeat for a deadline
that's slipping becomes a reshaped plan from the Start-by plan ("1 h now, 1 h tomorrow?") with [Do that] [Not today],
once a day per deadline; Do that sets tomorrow's part, Not today ends it for the day; calls get the same as tools."""

from __future__ import annotations

import datetime as dt

import pytest

from kurooto.modules import deadlines as dl_mod
from kurooto.modules import startby as sb_mod


def at(day: int, h: int, m: int = 0) -> dt.datetime:
    return dt.datetime(2026, 11, day, h, m)


@pytest.fixture
def sb(env, monkeypatch):
    class Clock:
        t = at(2, 19)  # a Monday evening

    c = Clock()
    for mod in (sb_mod, dl_mod):
        monkeypatch.setattr(mod, "now", lambda: c.t)
    app = env.app
    app.settings.set("availability.night.enabled", False)
    app.settings.set("startby.window", "09:00-21:00")
    app.settings.set("startby.share", 50)
    app.settings.set("startby.sizes", {"problem_set": 3, "report": 12, "quiz": 3, "exam": 10, "other": 2})
    env.on("deadlines", "startby")
    dl = app.modules["deadlines"]
    dl.add("Problem set 4", at(3, 11))  # 3 h: 1 h fits Tuesday 09:00-11:00, so 2 h were planned for Monday
    i = next(iter(dl.items()))
    return env, app.modules["startby"], dl, i, c


def test_a_slipping_deadline_gets_a_reshaped_plan_from_its_own_numbers(sb):
    env, s, dl, i, clock = sb
    x = s.reshape(i)
    assert (x["planned"], x["now"], x["later"], x["at"]) == (2, 1, 1, at(3, 9))
    assert s.reshape_text(x) == (
        "Problem set 4 (due Tue 03 Nov 11:00): your Start-by plan has 2 h of it today, and about 1 h of today's free "
        "time is left. 1 h now, 1 h tomorrow?"
    )
    clock.t = at(2, 20, 30)
    assert "today's free time is used up. 2 h tomorrow instead?" in s.reshape_text(s.reshape(i))
    clock.t = at(2, 12)
    assert s.reshape(i) is None  # what's left of today still fits it
    clock.t = at(2, 22)
    assert s.reshape(i) is None  # outside today's window


def test_instead_of_a_repeat_once_a_day_and_do_that(sb):
    env, s, dl, i, clock = sb
    it = dl.items()[i]
    dl._chase("ping", i, it, 16, again=False)  # the first reminder is the reminder
    assert env.fake.texts()[-1].startswith("Due in")
    dl._chase("urgent", i, it, 16, again=True)  # a repeat: the reshaped plan instead
    assert env.fake.texts()[-1].endswith("1 h now, 1 h tomorrow?")
    sent = [p for m, p in env.fake.sent if m == "sendMessage" and "reply_markup" in p][-1]
    row = sent["reply_markup"]["inline_keyboard"][0]
    assert [(b["text"], b["callback_data"]) for b in row] == [("Do that", f"neg:{i}:yes"), ("Not today", f"neg:{i}:no")]
    dl._chase("urgent", i, it, 16, again=True)  # once a day: the reminder comes as it was
    assert env.fake.texts()[-1].startswith("Due in")
    assert env.press(f"neg:{i}:yes") == "OK: 1 h now, 1 h tomorrow from 09:00. I'll remind you then."
    assert env.press(f"neg:{i}:yes") == "Already answered."
    job = env.app.scheduler.get(f"startby:moved:{i}")
    assert job is not None and job.action == "startby.moved"
    s._moved({"id": i, "hours": 1})
    assert env.fake.texts()[-1] == "Problem set 4: the 1 h you moved to today. Due Tue 03 Nov 11:00."


def test_not_today_ends_it_and_start_by_counts_as_said_before(sb):
    env, s, dl, i, clock = sb
    assert s.offer_reshape(i, again=False) is False  # nothing came before: not a repeat
    # "time to start" yesterday, so some of it counts as done by now: a bigger one, still slipping
    s._put_state(told={i: "2026-11-01"}, sizes={i: 6})
    assert s.offer_reshape(i, again=False) is True
    assert env.press(f"neg:{i}:no") == "OK, not today. I won't bring it up again today."
    assert s.offer_reshape(i, again=True) is False
    clock.t = at(3, 9, 30)  # a new day: may offer again (when it slips)
    assert env.press(f"neg:{i}:yes") == "That offer was for another day."


def test_a_missed_deadline_call_and_the_call_tools(sb):
    env, s, dl, i, clock = sb
    dl.call_outcome(f"deadlines:{i}", "missed")
    assert env.fake.texts()[-1].endswith("1 h now, 1 h tomorrow?")  # not "Missed call. Due ..."
    dl.call_outcome(f"deadlines:{i}", "missed")
    assert env.fake.texts()[-1].startswith("Missed call. Due")
    tools = {t.name: t for t in s.call_tools()}
    assert "Nothing to reshape" in tools["reshape_plan"].run({"id": i})  # offered today already
    assert tools["reshape_answer"].run({"id": i, "answer": "no"}).startswith("OK, not today")
    assert "never press or repeat it" in tools["reshape_plan"].hint


def test_off(sb):
    env, s, dl, i, clock = sb
    env.app.settings.set("startby.negotiate", False)
    assert s.offer_reshape(i, again=True) is False
    dl._chase("urgent", i, dl.items()[i], 16, again=True)
    assert env.fake.texts()[-1].startswith("Due in")

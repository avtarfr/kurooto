"""Rescheduling the day: today's blocks still to do (and ones slept through) move to start from now or a time you
give, in order, keeping their lengths and the breaks between them; a block planned twice keeps its first; pushing
"by" moves only what isn't over; Undo puts them back. Plus "I just woke up, reschedule my day" isn't the wake-up call,
and an alarm time in the current minute rings now."""

import datetime as dt

import pytest

from kurooto.modules import alarm as alarm_mod
from kurooto.modules import google_plan
from kurooto.modules.text import up_now
from tests.unit.test_google import allow, gx  # noqa: F401

DAY = (dt.datetime.now() + dt.timedelta(days=2)).date()


def at(h, m=0, day=DAY):
    return dt.datetime.combine(day, dt.time(h, m))


@pytest.fixture
def plan(gx, monkeypatch):  # noqa: F811
    env, g, ai = gx
    allow(env, g, "agent_plan")
    ap = env.app.modules["agent_plan"]
    clock = {"t": at(10)}
    monkeypatch.setattr(google_plan, "now", lambda: clock["t"])
    made = ((16, 18, "POTA prep"), (18.5, 20.5, "TSA prep"), (21.25, 22.5, "PST set"), (19, 21, "POTA prep"))
    for s, e, title in made:
        ap.plan_block(at(int(s), int(s % 1 * 60)), at(int(e), int(e % 1 * 60)), title)
    clock["t"] = at(17, 2)
    return env, ap, clock


def blocks(ap):
    return [(f"{b['start']:%H:%M}", f"{b['end']:%H:%M}", b["title"]) for b in ap.plan_blocks(DAY)]


def test_woke_up_late_the_day_starts_now(plan):
    env, ap, clock = plan
    out = ap.reschedule()
    assert out.startswith("Your day, from now:")
    # POTA (slept through) first, from 17:15; the 30-minute break kept; the second POTA dropped; PST after 45 minutes
    assert blocks(ap) == [
        ("17:15", "19:15", "POTA prep"),
        ("19:45", "21:45", "TSA prep"),
        ("22:30", "23:45", "PST set"),
    ]
    from kurooto.modules import daily

    assert "## Plan rescheduled (17:02)" in daily.note_path(env.app, DAY).read_text()
    assert ap.undo_reschedule().startswith("Put 4 blocks back")
    assert [b[2] for b in blocks(ap)].count("POTA prep") == 2


def test_from_a_time_and_by_some_hours(plan):
    env, ap, clock = plan
    assert env.say("/blocks shift 19:00").startswith("Your day, from now:")
    assert blocks(ap)[0][:2] == ("19:00", "21:00")
    clock["t"] = at(19, 30)  # in the middle of the first one: pushing moves what isn't over
    ap.reschedule(by=dt.timedelta(hours=1))
    assert blocks(ap)[0] == ("20:00", "22:00", "POTA prep")


def test_plain_english(plan):
    env, ap, clock = plan
    it = ap.intents()[0]
    assert it.match("I just woke up, reschedule my day") == {"from": "", "by": ""}
    assert it.match("push my day by 2 hours") == {"from": "", "by": "2 hours"}
    assert it.match("reschedule my day from 19:00") == {"from": "19:00", "by": ""}
    assert it.match("what's my day like") is None
    assert not up_now("I just woke up, reschedule my day") and up_now("I just woke up")


def test_an_alarm_for_this_very_minute_rings_now(monkeypatch):
    t = dt.datetime(2026, 10, 23, 16, 36, 4)
    monkeypatch.setattr(alarm_mod, "now", lambda: t)
    assert alarm_mod._this_minute(dt.datetime(2026, 10, 24, 16, 36)) == t + dt.timedelta(seconds=15)
    assert alarm_mod._this_minute(dt.datetime(2026, 10, 24, 16, 35)) == dt.datetime(2026, 10, 24, 16, 35)

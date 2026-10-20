"""Quick win 2: first-week quests. One message a day for seven days, only for features that are on and pass their
checks, each leaving real data; skipped when already done; they stop for good at the first Stop or ignored day."""

from __future__ import annotations

import datetime as dt
import json

import pytest

from kurooto.modules import quests as qmod

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


class Clock:
    def __init__(self, monkeypatch):
        self.t = dt.datetime.combine(dt.date.today(), dt.time(18, 0))
        monkeypatch.setattr(qmod, "now", lambda: self.t)

    def next_day(self):
        self.t += dt.timedelta(days=1)


@pytest.fixture
def week(env, monkeypatch):
    env.app.settings.set("availability.night.enabled", False)
    clock = Clock(monkeypatch)
    env.on("subjects", "deadlines", "reminders")
    env.say("/subject add Linear Algebra (la)")
    env.on("quests")
    return env, env.app.modules["quests"], clock


def quest_texts(env):
    return [t for t in env.fake.texts() if t and t.startswith("First week")]


def last_buttons(env):
    sent = [p for m, p in env.fake.sent if m == "sendMessage" and "reply_markup" in p]
    return [b["callback_data"] for row in sent[-1]["reply_markup"]["inline_keyboard"] for b in row]


def test_one_quest_a_day_while_you_do_them(week):
    env, q, clock = week
    assert q.daily() == "sent timetable"
    first = quest_texts(env)[-1]
    tomorrow = DAYS[(clock.t.date() + dt.timedelta(days=1)).weekday()]
    assert first.startswith("First week, day 1 of 7: add tomorrow's classes") and f"/class {tomorrow} 09:00" in first
    assert "la" in first and "<subject>" not in first
    assert last_buttons(env)[0].startswith("quest:") and last_buttons(env)[0].endswith(":skip")
    assert q.daily() == "already sent today"  # a second run the same day sends nothing
    env.say(f"/class {tomorrow} 09:00-09:55 la")  # done: there's a timetable now
    clock.next_day()
    assert q.daily() == "sent deadline"
    env.say("/due fri 17:00 essay draft")
    clock.next_day()
    assert q.daily() == "sent reminder"
    st = q.state()
    assert [s["status"] for s in st["sent"]] == ["done", "done", "open"] and not st.get("stopped")
    assert "2 of 7 sent" not in q._cmd(None, "") and "3 of 7 sent" in q._cmd(None, "")


def test_an_ignored_day_stops_them_for_good(week):
    env, q, clock = week
    q.daily()
    clock.next_day()
    assert q.daily() == "stopped (ignored)"
    assert len(quest_texts(env)) == 1 and env.app.scheduler.get("quests:daily") is None
    clock.next_day()
    assert q.daily() == "stopped (ignored)" and len(quest_texts(env)) == 1
    q.start()  # restarting Kurooto doesn't bring them back
    assert env.app.scheduler.get("quests:daily") is None
    assert "a day's quest was left alone" in env.say("/quests")


def test_skip_moves_on_and_stop_ends_them(week):
    env, q, clock = week
    q.daily()
    skip = last_buttons(env)[0]
    assert env.press(skip) == "Skipped. Another one tomorrow."
    clock.next_day()
    assert q.daily() == "sent deadline"  # a skipped day isn't an ignored one
    assert env.press(last_buttons(env)[1]) == "OK, no more of these."
    clock.next_day()
    assert q.daily() == "stopped (stop)" and len(quest_texts(env)) == 2
    events = [json.loads(ln)["kind"] for ln in env.app.events.file.read_text().splitlines()]
    assert "quest_skipped" in events and "quests_stopped" in events


def test_replying_with_the_thing_does_it(week):
    env, q, clock = week
    env.say("/class mon 09:00-09:55 la")  # the timetable quest is already done, so it's left out
    assert q.daily() == "sent deadline"
    env.reply_to_last("I have problem set 3 due fri 17:00")
    assert any("Added: problem set 3" in (t or "") for t in env.fake.texts())
    assert q.state()["sent"][-1]["status"] == "answered"
    clock.next_day()
    assert q.daily() == "sent reminder"
    env.reply_to_last("stop")
    assert q.state()["stopped"] == "stop"


def test_only_features_that_are_on_and_working(week, monkeypatch):
    env, q, clock = week
    env.say("/class mon 09:00-09:55 la")
    monkeypatch.setattr(env.app.modules["deadlines"], "health", lambda: (False, "broken"))
    env.app.modules["reminders"].add(dt.datetime.now() + dt.timedelta(hours=2), "tea")  # a reminder this week
    assert q.daily() == "nothing to suggest today"  # deadlines fails its check; reminders is done already
    assert quest_texts(env) == []
    clock.next_day()
    assert q.daily() == "nothing to suggest today"  # no quest sent means none ignored


def test_the_week_ends(week):
    env, q, clock = week
    for _ in range(7):
        clock.next_day()
    assert q.daily() == "stopped (finished)"
    assert "the week ended" in env.say("/quests")
    env.say("/quests stop")
    assert q.state()["stopped"] == "finished"


def test_quests_are_listed_and_off_until_turned_on(env):
    from kurooto.web.api import MODULE_ORDER

    assert "quests" in MODULE_ORDER and not env.app.is_on("quests")
    assert all(x.module in env.app.modules or x.module == "doubts" for x in qmod.QUESTS)

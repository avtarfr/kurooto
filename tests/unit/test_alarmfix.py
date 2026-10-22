"""The daily alarm across nights the computer sleeps through: the next one is always with the call line (planned as soon
as one has rung, at start and after a wake), one-day skips the daily re-plan respects, and the daily alarm turned off
for good. A fake clock for the alarm and the scheduler; the phone ring is recorded, not placed."""

import asyncio
import datetime as dt

import pytest

from kurooto.modules import alarm as alarm_mod
from kurooto.modules.calls import deploy

WED = dt.date(2026, 10, 21)
THU, FRI, SAT = (WED + dt.timedelta(days=n) for n in (1, 2, 3))


def at(day, h, m=0):
    return dt.datetime.combine(day, dt.time(h, m))


class World:
    """The time the alarm and the scheduler see; tick() runs what's due then (as after a sleep, all at once)."""

    def __init__(self, app, monkeypatch, t):
        self.app, self.t = app, t
        monkeypatch.setattr(alarm_mod, "now", lambda: self.t)
        monkeypatch.setattr(app.scheduler, "clock", lambda: self.t.timestamp())
        self.rang: list[tuple[str, bool]] = []
        monkeypatch.setattr(
            app.modules["calls"],
            "ring",
            lambda reason, alarm=False, key="", buttons=None: self.rang.append((key, alarm)),
        )

    def tick(self, t=None):
        if t is not None:
            self.t = t
        return asyncio.run(self.app.scheduler.tick())


@pytest.fixture
def world(env, monkeypatch):
    env.app.secrets.set("gemini.api_key", "k")
    deploy.ensure_secrets(env.app)
    env.app.settings.set("calls.worker", {"url": "https://kurooto-abc.your-subdomain.workers.dev"})
    env.app.settings.set("availability.night.enabled", False)
    env.on("calls")
    w = World(env.app, monkeypatch, at(WED, 6, 0))
    env.app.settings.set("alarm.daily", "07:00")
    env.on("alarm")
    return env, env.app.modules["alarm"], w


def line(a):
    """What the call line holds for the alarm."""
    return [dt.datetime.fromtimestamp(x["at"]) for x in a.call_schedule()]


def test_the_line_has_tomorrows_alarm_before_the_night(world):
    env, a, w = world
    assert a.next() == at(WED, 7) and env.app.scheduler.get("alarm:plan").spec == alarm_mod.PLAN_EVERY
    w.tick(at(WED, 7, 0))
    assert w.rang == [("alarm:next", True)]
    assert a.next() == at(THU, 7) and line(a) == [at(THU, 7)]  # sent at once, not at 00:02
    a.call_outcome("alarm:next", "answered")
    assert a.next() == at(THU, 7)
    # the laptop sleeps from 23:00 to 09:00: the line rang Thursday's alarm itself
    w.t = at(WED, 23, 0)
    assert line(a) == [at(THU, 7)]
    w.tick(at(THU, 9, 0))  # waking up: the scheduler catches up (the ring is past its grace: missed)
    assert len(w.rang) == 1  # the computer doesn't ring it again two hours late
    assert a.next() == at(FRI, 7) and line(a) == [at(FRI, 7)]


def test_repeat_rings_and_the_plan_check_dont_fight(world):
    env, a, w = world
    w.tick(at(WED, 7, 0))
    assert a.call_outcome("alarm:next", "missed") is True  # rings again at 07:05
    assert a.next() == at(WED, 7, 5)
    w.t = at(WED, 7, 3)
    a._plan()  # the half-hourly check leaves the repeat ring alone
    assert a.next() == at(WED, 7, 5)
    w.tick(at(WED, 7, 5))
    a._plan()  # between the ring and its outcome: Thursday's goes to the line meanwhile
    assert a.next() == at(THU, 7)
    assert a.call_outcome("alarm:next", "missed") is True  # the count survived: second repeat
    w.tick(at(WED, 7, 10))
    assert a.call_outcome("alarm:next", "missed") is False  # no more repeats
    assert a.next() == at(THU, 7) and len(w.rang) == 3


def test_skip_a_day_and_the_daily_alarm_comes_back(world):
    env, a, w = world
    w.tick(at(WED, 7, 0))
    a.call_outcome("alarm:next", "answered")
    w.t = at(WED, 22, 0)
    assert env.say("no alarm tomorrow") == "No alarm on Thu 22 Oct. Next: Fri 23 Oct, 07:00."
    a._plan()
    assert a.next() == at(FRI, 7)  # the re-plan respects the skip
    w.tick(at(THU, 7, 0))
    assert len(w.rang) == 1
    # "cancel my alarm" skips the morning that's set; it doesn't come back at midnight
    assert env.say("cancel my alarm") == (
        'Alarm off for Fri 23 Oct. Your daily alarm is back Sat 24 Oct, 07:00 ("turn my daily alarm off" stops it).'
    )
    w.tick(at(FRI, 0, 2))
    a._plan()
    assert a.next() == at(SAT, 7)
    # still up at 1 am, "tomorrow" is the coming morning
    w.t = at(FRI, 1, 0)
    assert env.say("cancel tomorrow's alarm") == "No alarm on Sat 24 Oct. Next: Sun 25 Oct, 07:00."
    assert env.say("/alarm skip tuesday") == "No alarm on Tue 27 Oct. Next: Sun 25 Oct, 07:00."
    # off for good, and on again
    assert env.say("turn my daily alarm off") == "Daily alarm off."
    assert a.next() is None and env.app.settings.get("alarm.daily") is None
    a._plan()
    assert a.next() is None
    assert env.say("/alarm daily 6:30") == "Daily alarm at 06:30. Next: Sun 25 Oct, 06:30."  # Fri, Sat skipped


def test_one_alarm_per_morning_and_settings_changes(world):
    env, a, w = world
    w.tick(at(WED, 7, 0))
    a.call_outcome("alarm:next", "answered")
    w.t = at(WED, 22, 0)
    assert a.set(at(THU, 6)) == "Alarm set for Thu 22 Oct, 06:00."  # "wake me at 6 tomorrow"
    a._plan()
    assert a.next() == at(THU, 6)  # one you set stays
    w.tick(at(THU, 6, 0))
    assert a.next() == at(FRI, 7)  # Thursday already had its alarm: not again at 07:00
    a.set(at(FRI, 0, 40))  # a nap alarm after midnight (or a late one) isn't Friday's morning
    w.tick(at(FRI, 0, 40))
    a.call_outcome("alarm:next", "answered")
    assert a.next() == at(FRI, 7)
    env.app.settings.set("alarm.daily", "06:30")
    env.app.settings.set("alarm.days", ["mon", "tue", "wed", "thu"])
    a._plan()
    assert a.next() == at(dt.date(2026, 10, 26), 6, 30)  # the time and days changed: Monday at 06:30
    assert a.call_schedule()[0]["at"] == int(at(dt.date(2026, 10, 26), 6, 30).timestamp())


def test_start_plans_it_and_phrases(world):
    env, a, w = world
    a.clear()
    a.stop()
    w.t = at(THU, 12, 0)
    a.start()  # Kurooto starting (or the half-hourly check after a wake)
    assert a.next() == at(FRI, 7)
    assert env.say("/alarm") == "Alarm: Fri 23 Oct, 07:00. Daily alarm: 07:00 (every day)."
    m = a.intents()[0].match
    assert m("turn off the daily alarm") == {"daily_off": True} and m("stop my daily alarm") == {"daily_off": True}
    assert m("turn off my alarm") == {"off": True} and m("no alarm") == {"off": True}
    assert m("no alarm on friday") == {"skip": FRI} and m("don't wake me tomorrow") == {"skip": FRI}
    assert m("no alarm today") == {"skip": THU} and m("skip the alarm next week") is None


def test_keep_awake_lasts_through_the_morning_that_rang(world, monkeypatch):
    from kurooto.core import inhibit

    env, a, w = world
    monkeypatch.setattr(inhibit.proc, "kill_tree", lambda pid: None)

    class Proc:
        pid = 999999

        def poll(self):
            return None

        def wait(self, timeout=None):
            return 0

    a.inhibitor = inhibit.Inhibitor(
        platform="linux",
        popen=lambda args, **kw: Proc(),
        which=lambda n: f"/usr/bin/{n}",
        clock=lambda: w.t.timestamp(),
    )
    env.app.settings.set("alarm.keep_awake", True)
    w.t = at(WED, 6, 50)
    assert a.keep_awake()
    w.tick(at(WED, 7, 0))
    assert a.next() == at(THU, 7) and a.inhibitor.held()  # tomorrow's is planned, this morning still holds
    a.call_outcome("alarm:next", "answered")
    assert not a.inhibitor.held()  # you're up
    assert dt.datetime.fromtimestamp(env.app.scheduler.get("alarm:awake").next_run) == at(WED, 19, 0)


@pytest.mark.parametrize(
    "text",
    [
        "Any morning alarms set for me?",
        "Do I have any alarms?",
        "do i have an alarm set",
        "is my alarm set",
        "what alarms do I have",
        "When is my alarm?",
        "what time does my alarm ring",
        "show my alarms",
    ],
)
def test_alarm_questions_are_answered_at_once_without_the_ai(world, text):
    env, a, w = world
    out = env.say(text)
    assert out == a.status() and "Alarm:" in out and "Daily alarm: 07:00" in out


def test_setting_an_alarm_is_not_mistaken_for_asking(world):
    env, a, w = world
    assert env.say("wake me at 6:30").startswith("Alarm set for")


def test_alarm_status_has_a_tool_and_a_markdown_file(world):
    env, a, w = world
    assert "get_alarm" in {t.name for t in a.call_tools()}
    a.skip(THU)
    text = a.mirror_file.read_text(encoding="utf-8")
    assert text.startswith("# Alarm") and "Daily alarm: 07:00" in text and "No alarm on Thu 22 Oct" in text


def test_the_today_page_sets_skips_and_shows_the_alarm(world):
    from kurooto.core import actions

    env, a, w = world
    st = actions.today(env.app)["alarm_state"]
    assert st["daily"] == "07:00" and "Daily alarm: 07:00" in st["status"]
    assert actions.act(env.app, "alarm.skip", {"day": "tomorrow"})["ok"]
    assert "No alarm on Thu 22 Oct" in actions.today(env.app)["alarm_state"]["status"]
    r = actions.act(env.app, "alarm.set", {"when": "tomorrow 6:15"})
    assert r["ok"] and "Alarm set for" in r["message"]
    assert actions.act(env.app, "alarm.daily", {"time": "off"})["message"].startswith("Daily alarm off")

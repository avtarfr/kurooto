"""Several alarms you set: a new one doesn't replace the others, the soonest is the one set and the next takes its
place once it has rung, the call line holds them all, and one or all can be cancelled. The daily alarm stays."""

import datetime as dt

import pytest

from kurooto.modules import alarm as alarm_mod
from kurooto.modules.calls import deploy
from tests.unit.test_alarmfix import THU, WED, World, at, line


@pytest.fixture
def world(env, monkeypatch):
    env.app.secrets.set("gemini.api_key", "k")
    deploy.ensure_secrets(env.app)
    env.app.settings.set("calls.worker", {"url": "https://kurooto-abc.your-subdomain.workers.dev"})
    env.app.settings.set("availability.night.enabled", False)
    env.on("calls")
    w = World(env.app, monkeypatch, at(WED, 8, 0))
    env.on("alarm")
    return env, env.app.modules["alarm"], w


def test_a_later_alarm_waits_its_turn_and_rings_after(world):
    env, a, w = world
    a.set(at(WED, 10, 30))
    out = a.set(at(WED, 15, 30))
    assert "Also set: Wed 10:30" in out
    assert a.next() == at(WED, 10, 30) and line(a) == [at(WED, 10, 30), at(WED, 15, 30)]
    w.tick(at(WED, 10, 30))
    assert w.rang == [("alarm:next", True)]
    assert a.next() == at(WED, 15, 30)  # the next one took its place
    a.call_outcome("alarm:next", "answered")
    assert a.next() == at(WED, 15, 30)
    w.tick(at(WED, 15, 30))
    assert len(w.rang) == 2
    a.call_outcome("alarm:next", "answered")
    assert a.next() is None and a.mine() == []


def test_a_sooner_alarm_goes_first_and_a_repeat_ring_doesnt_lose_the_rest(world):
    env, a, w = world
    a.set(at(WED, 15, 30))
    a.set(at(WED, 10, 0))
    assert a.next() == at(WED, 10, 0)
    w.tick(at(WED, 10, 0))
    a.call_outcome("alarm:next", "missed")  # rings again in 5 minutes
    assert a.next() == at(WED, 10, 5)
    w.tick(at(WED, 10, 5))
    a.call_outcome("alarm:next", "answered")
    assert a.next() == at(WED, 15, 30)


def test_cancel_one_by_time_or_all(world):
    env, a, w = world
    for h in (10, 12, 15):
        a.set(at(WED, h))
    assert "Alarms: Wed 21 Oct, 10:00; Wed 21 Oct, 12:00; Wed 21 Oct, 15:00." in a.status()
    assert a.intents()[0].match("cancel the 12:00 alarm") == {"off_at": "12:00"}
    assert "off for Wed 21 Oct, 12:00" in a.clear_at("12:00")
    assert a.upcoming() == [at(WED, 10), at(WED, 15)]
    assert "Next: Wed 21 Oct, 15:00" in a.clear()  # "cancel my alarm": the next one
    a.set(at(THU, 9))
    assert a.intents()[0].match("cancel all my alarms") == {"all_off": True}
    assert "All 2 alarms" in a.clear_all()
    assert a.next() is None and a.upcoming() == []


def test_the_daily_alarm_stays_and_a_morning_you_set_replaces_it(world):
    env, a, w = world
    a.set_daily("07:00")
    assert a.next() == at(THU, 7)
    a.set(at(THU, 8))  # that morning: yours instead of the daily one
    a.set(at(WED, 16))
    assert a.upcoming() == [at(WED, 16), at(THU, 8)]
    w.tick(at(WED, 16))
    a.call_outcome("alarm:next", "answered")
    assert a.next() == at(THU, 8)
    a.clear_all()
    assert a.next() == at(THU, 7)  # the daily one is back


def test_at_most_max_set(world):
    env, a, w = world
    for m in range(alarm_mod.MAX_SET):
        a.set(at(WED, 10, m))
    assert "already" in a.set(at(WED, 11))
    assert len(a.upcoming()) == alarm_mod.MAX_SET
    assert dt.datetime(2026, 10, 21, 11) not in a.upcoming()

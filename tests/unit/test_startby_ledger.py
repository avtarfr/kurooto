"""Start-by's free time as one ledger (0.9.0): commitments and the blocks already in the Agent plan calendar are busy
(L49, L50), a block of yours that's running holds Kurooto's own calls only with agent_plan.holds_calls (L50), and
with mind.presence_forecast.plan the free hours are filled likeliest-free first and the window can learn from the
usual quiet hours, never losing an hour (L55). A fixed clock throughout."""

from __future__ import annotations

import datetime as dt

import pytest

from kurooto.mind import presence_forecast as pf
from kurooto.mind import study_push
from kurooto.modules import startby as sb_mod
from kurooto.modules.startby import allocate, by_hour
from tests.unit.test_google import allow, gx  # noqa: F401

T0 = dt.datetime(2026, 11, 2, 7, 0)  # a Monday morning


def at(day: int, h: int, m: int = 0) -> dt.datetime:
    return dt.datetime(2026, 11, day, h, m)


@pytest.fixture
def sb(env, monkeypatch):
    monkeypatch.setattr(sb_mod, "now", lambda: T0)
    env.app.settings.set("availability.night.enabled", False)
    env.app.settings.set("startby.window", "09:00-21:00")
    env.app.settings.set("startby.share", 50)
    env.on("subjects", "deadlines", "startby")
    return env


def free(env, day: int) -> list:
    return env.app.modules["startby"].slots(at(day, 0), at(day, 23, 59))


def test_commitments_are_not_free_time(sb):
    assert free(sb, 3) == [(at(3, 9), at(3, 21))]
    sb.on("commitments")
    sb.app.modules["commitments"].add("gym", ["tue"], "09:00", "11:00")
    sb.app.modules["commitments"].add("shift", ["mon"], "20:00", "10:00")  # a night shift runs into Tuesday
    assert free(sb, 3) == [(at(3, 11), at(3, 21))]
    sb.app.modules["commitments"].set_skip("gym", day=dt.date(2026, 11, 3))
    sb.app.modules["commitments"].remove("shift")
    assert free(sb, 3) == [(at(3, 9), at(3, 21))]  # a skipped commitment frees its time


class FakePlan:
    """The Agent plan calendar's ledger (modules/google_plan.py:busy) without Google."""

    id = "agent_plan"

    def __init__(self, blocks=None, fail=False, holds=False):
        self.blocks, self.fail, self.holds = blocks or [], fail, holds

    def busy(self, t0, until):
        if self.fail:
            return []  # the real one returns none when Google is out of reach
        return [(a, b) for a, b in self.blocks if b > t0 and a < until]

    def setting(self, key):
        return self.holds if key == "holds_calls" else None

    def running_block(self, t=None):
        t = t or dt.datetime.now()
        for a, b in self.blocks:
            if a <= t < b:
                return {"title": "Problem set 4", "start": a, "end": b}
        return None


def plan_on(env, monkeypatch, fake):
    env.app.modules["agent_plan"] = fake
    real = env.app.is_on
    monkeypatch.setattr(env.app, "is_on", lambda mid: True if mid == "agent_plan" else real(mid))


def test_agent_plan_blocks_are_busy_and_offline_means_none(sb, monkeypatch):
    plan_on(sb, monkeypatch, FakePlan([(at(3, 14), at(3, 16))]))
    assert free(sb, 3) == [(at(3, 9), at(3, 14)), (at(3, 16), at(3, 21))]
    plan_on(sb, monkeypatch, FakePlan([(at(3, 14), at(3, 16))], fail=True))
    assert free(sb, 3) == [(at(3, 9), at(3, 21))]


def test_the_ledger_reads_the_real_calendar_once(gx_plan, monkeypatch):
    env, ap, day = gx_plan
    t0 = dt.datetime.combine(day, dt.time(0))
    got = ap.busy(t0, t0 + dt.timedelta(days=1))
    assert got == [(dt.datetime.combine(day, dt.time(14)), dt.datetime.combine(day, dt.time(15, 30)))]
    assert ap.busy(t0, t0 + dt.timedelta(days=1)) == got  # kept a moment
    monkeypatch.setattr(ap, "plan_ready", lambda: False)  # off or signed out
    assert ap.busy(t0, t0 + dt.timedelta(days=1)) == []  # off: no busy time


@pytest.fixture
def gx_plan(gx):  # noqa: F811
    env, g, _ai = gx
    allow(env, g, "agent_plan")
    ap = env.app.modules["agent_plan"]
    day = (dt.datetime.now() + dt.timedelta(days=2)).date()
    out = ap.plan_block(dt.datetime.combine(day, dt.time(14)), dt.datetime.combine(day, dt.time(15, 30)), "Essay")
    assert out.startswith("Planned"), out
    return env, ap, day


def test_a_running_block_holds_only_kurootos_own_calls(env, monkeypatch):
    calls = env.app.modules["calls"]  # asked directly: setting the call line up isn't needed for this
    t = dt.datetime.now()
    fake = FakePlan([(t - dt.timedelta(minutes=10), t + dt.timedelta(minutes=50))])
    plan_on(env, monkeypatch, fake)
    assert calls.plan_block_hold("checkins") is None  # agent_plan.holds_calls is off
    fake.holds = True
    when, why = calls.plan_block_hold("checkins")
    assert why == "your planned block: Problem set 4" and when > t + dt.timedelta(minutes=50)
    assert calls.plan_block_hold("calls.own") is None  # one you asked for rings
    assert calls.plan_block_hold("alarm.ring") is None
    assert calls.plan_block_hold(None) is None


# ------------------------------------------------------------------------------------ the forecast
def test_ranked_allocation_prefers_likely_hours_and_keeps_every_hour():
    slots = [(at(2, 9), at(2, 21)), (at(3, 9), at(3, 21))]
    assert sum((b - a).total_seconds() for a, b in by_hour(slots)) == 24 * 3600
    items = [{"id": "x", "due": at(4, 0), "hours": 2}]
    plain = allocate(items, slots, 0.5)["x"]
    assert plain == (at(3, 17), 0.0)  # as late as possible
    mornings = lambda t: 0.9 if t.hour < 12 else 0.3  # noqa: E731
    pieces: dict = {}
    got = allocate(items, slots, 0.5, pieces, rank=mornings)["x"]
    assert got == (at(2, 11), 0.0)  # Tuesday's morning (09:00-12:00 is 1.5 h of work), then Monday's 11:00
    assert sum(h for *_, h in pieces["x"]) == pytest.approx(2.0)
    assert all(lo.hour < 12 for lo, _top, _h in pieces["x"])
    # nothing lost: a deadline too big for the time still gets every hour there is
    big = allocate([{"id": "y", "due": at(4, 0), "hours": 20}], slots, 0.5, rank=mornings)["y"]
    assert big == (at(2, 9), 8.0)


def test_the_plan_switch_orders_slots_and_the_study_push_picks_a_likely_hour(sb, monkeypatch):
    app = sb.app
    s = app.modules["startby"]
    assert s.rank() is None  # mind.presence_forecast.plan is off by default
    monkeypatch.setattr(pf, "on", lambda a: True)
    app.settings.set("mind.presence_forecast.plan", True)
    monkeypatch.setattr(pf, "p_free", lambda a, t, st=None: 0.9 if t.hour >= 18 else 0.4)
    rank = s.rank()
    assert rank(at(2, 19)) == 0.9 and rank(at(2, 10)) == 0.4
    t = at(2, 9)
    assert study_push.slot(app, 30, t) == at(2, 18)  # the likeliest free stretch, not the first
    app.settings.set("mind.presence_forecast.plan", False)
    assert study_push.slot(app, 30, t) == at(2, 9, 30)  # as before: the first stretch long enough


def test_the_window_can_learn_from_the_usual_quiet_hours(env, monkeypatch):
    app = env.app
    env.on("deadlines", "startby")
    s = app.modules["startby"]
    monkeypatch.setattr(app.rhythm, "usual_hours", lambda: {"from": "01:00", "to": "10:30"})
    assert s.learn_window() == ""  # the switch is off: too few messages, nothing learned
    monkeypatch.setattr(pf, "on", lambda a: True)
    app.settings.set("mind.presence_forecast.plan", True)
    line = s.learn_window()
    assert line.startswith("Start-by dates now count your free time from 10:30 to 01:00")
    assert "you're usually around from 10:30 to 01:00" in line
    assert app.callback("sby:window:undo").startswith("Back to 09:00-22:00")

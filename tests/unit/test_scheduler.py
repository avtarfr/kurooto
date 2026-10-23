import asyncio
import datetime as dt
from zoneinfo import ZoneInfo

import pytest

from kurooto.core.scheduler import Scheduler, next_after

TZ = ZoneInfo("America/Sao_Paulo")  # no daylight saving: fixed expectations
UTC = dt.UTC


class Clock:
    def __init__(self, t: dt.datetime):
        self.t = t.timestamp()

    def __call__(self):
        return self.t

    def advance(self, **kw):
        self.t += dt.timedelta(**kw).total_seconds()


def at(y, mo, d, h, mi, tz=TZ):
    return dt.datetime(y, mo, d, h, mi, tzinfo=tz)


@pytest.fixture
def sched(tmp_path):
    clock = Clock(at(2026, 10, 19, 17, 40))
    s = Scheduler(tmp_path / "s.db", tz=TZ, clock=clock)
    s.clock_ = clock
    s.ran = []
    s.action("note", lambda p: s.ran.append(p))
    yield s
    s.close()


def run(s):
    return asyncio.run(s.tick())


def test_specs():
    base = at(2026, 10, 19, 17, 40)
    assert next_after("daily 05:00", base, TZ) == at(2026, 10, 20, 5, 0).astimezone(UTC)
    assert next_after("daily 07:00,13:00,19:00", base, TZ) == at(2026, 10, 19, 19, 0).astimezone(UTC)
    assert next_after("weekly sun 19:30", base, TZ) == at(2026, 10, 25, 19, 30).astimezone(UTC)
    assert next_after("weekly mon 19:30", base, TZ) == at(2026, 10, 19, 19, 30).astimezone(UTC)
    assert next_after("hourly", base, TZ) == at(2026, 10, 19, 18, 0).astimezone(UTC)
    assert next_after("every 10m", base, TZ) == base + dt.timedelta(minutes=10)
    for bad in ("daily 25:00", "sometimes", "every 0m", "weekly funday 10:00"):
        with pytest.raises(ValueError):
            next_after(bad, base, TZ)


def test_daylight_saving_keeps_local_time():
    ny = ZoneInfo("America/New_York")
    before = dt.datetime(2026, 3, 7, 12, 0, tzinfo=ny)  # DST starts 2026-03-08
    nxt = next_after("daily 09:00", before + dt.timedelta(days=1), ny)
    assert nxt.astimezone(ny).hour == 9 and nxt.astimezone(ny).utcoffset() == dt.timedelta(hours=-4)


def test_one_off_runs_once_then_disappears(sched):
    sched.at(at(2026, 10, 19, 18, 0), "note", {"what": "tea"}, key="remind:tea")
    assert run(sched) == []
    sched.clock_.advance(minutes=21)
    assert run(sched) == [("remind:tea", "ran")] and sched.ran == [{"what": "tea"}]
    assert sched.get("remind:tea") is None and run(sched) == []


def test_late_and_missed_one_offs(sched):
    sched.at(at(2026, 10, 19, 18, 0), "note", {"n": 1}, key="a")
    sched.at(at(2026, 10, 19, 18, 0), "note", {"n": 2}, key="b", grace_s=3600)
    sched.clock_.advance(hours=3)  # asleep for three hours
    run(sched)
    got = {p["n"]: p for p in sched.ran}
    assert got[1]["late_s"] == 2 * 3600 + 40 * 60 and "missed" not in got[1]
    assert got[2]["missed"] is True


def test_recurring_coalesces_after_sleep_and_keeps_going(sched):
    sched.every("sync", "every 10m", "note", {"k": "sync"})
    sched.every("digest", "daily 05:00", "note", {"k": "digest"}, misfire="skip")
    sched.clock_.advance(hours=13)  # 06:40 next day: both overdue
    out = dict(run(sched))
    assert out == {"sync": "ran", "digest": "skipped"} and sched.ran == [{"k": "sync"}]
    assert sched.get("sync").when == sched.now() + dt.timedelta(minutes=10)
    assert sched.get("digest").when == at(2026, 10, 21, 5, 0).astimezone(UTC)


def test_every_keeps_next_run_unless_spec_changes(sched):
    first = sched.every("x", "daily 05:00", "note").next_run
    sched.clock_.advance(minutes=5)
    assert sched.every("x", "daily 05:00", "note").next_run == first
    assert sched.every("x", "daily 06:00", "note").next_run != first


def test_gates_postpone(sched):
    quiet_until = at(2026, 10, 19, 23, 0)
    sched.gates["quiet"] = lambda now: quiet_until if now < quiet_until else None
    sched.at(at(2026, 10, 19, 17, 41), "note", {"x": 1}, key="q", respect="quiet")
    sched.clock_.advance(minutes=2)
    assert run(sched) == [("q", "postponed")] and sched.ran == []
    assert sched.get("q").when == quiet_until.astimezone(UTC)
    sched.clock_.advance(hours=6)
    assert run(sched) == [("q", "ran")]


def test_errors_are_contained_and_reported(sched):
    seen = []
    sched.on_result = lambda job, outcome, err: seen.append((job.key, outcome, type(err).__name__ if err else None))

    def boom(p):
        raise RuntimeError("nope")

    sched.action("boom", boom)
    sched.every("bad", "every 10m", "boom")
    sched.at(sched.now(), "nowhere", key="lost")
    sched.at(sched.now(), "note", {"ok": 1}, key="good")
    sched.clock_.advance(minutes=11)
    out = dict(run(sched))
    assert out == {"bad": "error", "lost": "missing-action", "good": "ran"}
    assert ("bad", "error", "RuntimeError") in seen and "nope" in sched.get("bad").last_result


def test_async_actions_and_cancel(sched):
    async def later(p):
        await asyncio.sleep(0)
        return "done"

    sched.action("later", later)
    sched.at(sched.now(), "later", key="call:rering:1")
    sched.at(sched.now(), "later", key="call:rering:2")
    sched.at(sched.now(), "later", key="checkin:evening")
    assert sched.cancel_prefix("call:rering:") == 2 and sched.cancel("checkin:evening")
    assert run(sched) == []


def test_survives_a_restart(tmp_path):
    clock = Clock(at(2026, 10, 19, 17, 40))
    s1 = Scheduler(tmp_path / "s.db", tz=TZ, clock=clock)
    s1.at(at(2026, 10, 19, 21, 0), "note", {"x": 1}, key="evening")
    s1.close()
    s2 = Scheduler(tmp_path / "s.db", tz=TZ, clock=clock)
    try:
        assert s2.get("evening").when == at(2026, 10, 19, 21, 0).astimezone(UTC)
    finally:
        s2.close()


def test_loop_wakes_for_new_jobs(tmp_path):
    s = Scheduler(tmp_path / "s.db")
    ran = []
    s.action("note", lambda p: ran.append(p))

    async def main():
        stop = asyncio.Event()
        task = asyncio.create_task(s.run_forever(stop, max_sleep=5))
        await asyncio.sleep(0.05)
        s.at(s.now(), "note", {"hi": 1})
        for _ in range(100):
            if ran:
                break
            await asyncio.sleep(0.02)
        stop.set()
        await task

    asyncio.run(main())
    s.close()
    assert ran == [{"hi": 1}]


def test_a_missing_action_is_reported_as_itself(env):
    import time

    app, s = env.app, env.app.scheduler
    s.action("t.fine", lambda p: "all fine")
    s.every("t:x", "every 10m", "t.fine")
    s._set_next("t:x", time.time() - 1)
    asyncio.run(s.tick())
    assert s.get("t:x").last_result == "all fine"
    del s.actions["t.fine"]  # its feature went away
    s._set_next("t:x", time.time() - 1)
    asyncio.run(s.tick())
    failed = app.events.tail(5, {"job_failed"})[-1]
    assert failed["outcome"] == "missing-action" and failed["error"] == "no action 't.fine'"  # not the run before

"""The concept graph after a restart (0.6.1): a batch whose request the restart lost goes back to pending at once (not
after STALE_S), and a restart inside tonight's reading window carries the night on, through the nightly start's own
path, so /graph stop, the budget gate and one bulk request per AI still hold. A fake AI answers; the job queue, the
ledger and the scheduler are real."""

import datetime as dt
import time

from kurooto.core import jobs as jobs_mod
from kurooto.modules import integrate as integrate_mod
from tests.unit.test_integrate import answer, c_ad, run_all, world  # noqa: F401 (a fixture)

BOOK = "deep-learning/bishop"


def the_batch(env) -> tuple[str, dict]:
    batches = env.integrate.load("ledger.json", {})["books"][BOOK]["batches"]
    return next(iter(batches.items()))


def ask_one(env) -> str:
    """One batch asked for (queued in the job queue, not run). Its job id."""
    env.fake_ai.answer = answer(c_ad())
    assert env.integrate.tick()["submitted"] == 1
    return the_batch(env)[1]["job"]


def job_set(env, jid: str, status: str, runner: str, finished: float | None = None, started: float | None = None):
    env.app.jobs._db.execute(
        "update jobs set status=?, runner=?, finished=?, started=? where id=?", (status, runner, finished, started, jid)
    )


def test_a_batch_whose_job_ended_in_a_process_that_is_gone_is_asked_again_at_once(world):  # noqa: F811
    env = world
    jid = ask_one(env)
    assert env.integrate.inflight() == (1, 0)
    assert env.integrate.tick()["submitted"] == 0  # one bulk request at a time
    # an update restarted Kurooto after the job had ended but before its answer was written
    job_set(env, jid, status="ok", runner="1:0.00", finished=time.time() - 30)
    assert env.integrate.inflight() == (0, 0)
    _, rec = the_batch(env)
    assert rec["state"] == "pending" and "lost" in rec["why"]
    assert env.say("/graph now") == "Started."
    jid2 = the_batch(env)[1]["job"]
    assert jid2 != jid
    run_all(env)
    assert the_batch(env)[1]["state"] == "done"


def test_a_job_that_is_gone_from_the_queue_is_lost_too(world):  # noqa: F811
    env = world
    jid = ask_one(env)
    env.app.jobs._db.execute("delete from jobs where id=?", (jid,))
    assert env.integrate.inflight() == (0, 0)
    assert env.integrate.tick()["submitted"] == 1


def test_a_job_a_restart_cut_off_mid_run_is_not_lost_it_runs_again(world):  # noqa: F811
    env = world
    jid = ask_one(env)
    job_set(env, jid, status="running", runner="1:0.00", started=time.time() - 60)
    assert env.integrate.inflight() == (1, 0)  # still the job queue's: recover() queues it again
    assert env.app.jobs.recover() == 1
    run_all(env)
    assert the_batch(env)[1]["state"] == "done"
    assert (env.app.workspace / "zettel" / "automatic-differentiation.md").is_file()


def test_a_job_whose_answer_is_being_written_here_is_not_taken_for_lost(world, monkeypatch):  # noqa: F811
    env = world
    monkeypatch.setattr(jobs_mod, "FOLLOW_GRACE_S", 0)  # only the follow-up itself keeps it
    ask_one(env)
    seen = []
    write = env.integrate.write

    def watching(*a, **kw):
        seen.append((env.integrate.inflight(), the_batch(env)[1]["state"]))
        return write(*a, **kw)

    monkeypatch.setattr(env.integrate, "write", watching)
    assert env.app.jobs.run_next()
    assert seen == [((1, 0), "queued")]  # while its answer is written, it's still out
    assert the_batch(env)[1]["state"] == "done"


def test_a_check_job_lost_to_a_restart_sends_the_batch_back_and_leaves_nothing_behind(world):  # noqa: F811
    env = world
    env.fake_ai.answer = answer(c_ad(quote="words that are nowhere in these pages at all, so a second look is due"))
    env.integrate.tick()
    assert env.app.jobs.run_next()  # the bulk answer: a doubt, so a second look is queued
    bid, rec = the_batch(env)
    assert rec["state"] == "checking" and (env.integrate.dir / "pending" / f"{rec['job']}.json").is_file()
    env.app.jobs._db.execute("delete from jobs where id=?", (rec["check_job"],))
    assert env.integrate.inflight() == (0, 0)
    assert the_batch(env)[1]["state"] == "pending"
    assert not (env.integrate.dir / "pending" / f"{rec['job']}.json").exists()


def at(env, monkeypatch, when: dt.datetime) -> None:
    monkeypatch.setattr(integrate_mod, "now", lambda: when)
    env.integrate.budget.clock = lambda: when.timestamp()


def test_a_restart_inside_tonights_window_carries_the_night_on(world, monkeypatch):  # noqa: F811
    env = world
    at(env, monkeypatch, dt.datetime(2026, 10, 24, 2, 18))  # integrate.at is 01:30: the night began
    env.integrate.start()  # what a restart runs
    soon = env.app.scheduler.get("integrate:soon")
    assert soon is not None and abs(soon.next_run - (dt.datetime(2026, 10, 24, 2, 19).timestamp())) < 2
    assert env.integrate.tick()["submitted"] == 1  # what integrate.soon runs: the nightly start's path


def test_a_restart_outside_the_window_or_after_graph_stop_waits_for_the_night(world, monkeypatch):  # noqa: F811
    env = world
    env.app.scheduler.cancel("integrate:soon")  # booked when the fixture turned the graph on, if it's night now
    at(env, monkeypatch, dt.datetime(2026, 10, 24, 14, 0))
    assert env.integrate.resume() is False and env.app.scheduler.get("integrate:soon") is None
    at(env, monkeypatch, dt.datetime(2026, 10, 24, 7, 45))  # no wake time known: until 07:30
    assert env.integrate.resume() is False
    at(env, monkeypatch, dt.datetime(2026, 10, 24, 3, 0))
    env.say("/graph stop")
    assert env.integrate.resume() is False and env.app.scheduler.get("integrate:soon") is None
    (env.integrate.dir / "stopped.json").unlink()
    ask_one(env)  # a bulk request is out already: one at a time
    assert env.integrate.resume() is False
    env.app.settings.set("integrate.per_night", 1)
    run_all(env)  # tonight's one batch is read: the budget gate says no
    assert env.integrate.budget.gate() == {"limit": "per_night"}
    assert env.integrate.resume() is False


def test_the_reading_window_ends_when_you_wake(world, monkeypatch):  # noqa: F811
    env = world
    env.app.settings.set("availability.night", {"enabled": True, "from": "23:30", "to": "06:30"})
    b = env.integrate.budget
    start, end = b.window(dt.datetime(2026, 10, 24, 3, 0).timestamp())
    assert start == dt.datetime(2026, 10, 24, 1, 30) and end == dt.datetime(2026, 10, 24, 6, 30)
    assert b.in_window(dt.datetime(2026, 10, 24, 6, 29).timestamp())
    assert not b.in_window(dt.datetime(2026, 10, 24, 6, 31).timestamp())
    assert not b.in_window(dt.datetime(2026, 10, 24, 1, 0).timestamp())

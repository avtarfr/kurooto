"""The concept graph's reading budget (core/readbudget.py): how many book batches a night, fitted to the AI's plan by
itself. A fake clock; fake AI answers (a Claude Code "usage limit reached|<epoch>" read by the real parser); no
network."""

import datetime as dt
import json
import time

import pytest

from kurooto.core import readbudget as rb
from kurooto.core.state import jsave
from kurooto.providers.base import Brain, Result, Verdict
from tests.unit.test_integrate import answer, c_ad
from tests.unit.test_integrate import world as world  # noqa: F401  (the fixture)


def ts(day: int, hh: int, mm: int = 0) -> float:
    """A local time in late October 2026 (a night that ends on the morning of `day`)."""
    return dt.datetime(2026, 10, day, hh, mm).timestamp()


class Clock:
    def __init__(self, t: float):
        self.t = t

    def __call__(self) -> float:
        return self.t


def budget(env, bulk: str, t: float) -> rb.Budget:
    b = rb.Budget(env.app, lambda: bulk)
    b.clock = Clock(t)
    return b


def claude_limit(reset_in_s: int) -> Result:
    """What Claude Code says at its limit, read by the real parser (the reset is an epoch)."""
    from kurooto.core.proc import Result as Run
    from kurooto.providers.claude import ClaudeCode

    out = json.dumps(
        {"type": "result", "is_error": True, "result": f"Claude AI usage limit reached|{int(time.time()) + reset_in_s}"}
    )
    return ClaudeCode(exe="claude").verdict(Run(1, out, ""), 1.0, 15)


class Job:
    def __init__(self, brain):
        self.brain = brain


def read(b: rb.Budget, n: int, step_s: int = 120) -> None:
    for _ in range(n):
        b.clock.t += step_s
        b.count()


# ---------------------------------------------------------------------------------------------- a subscription
def test_the_first_night_reads_30_and_a_clean_night_raises_it_by_half(env):
    b = budget(env, "claude", ts(23, 1, 40))
    r = b.tonight()
    assert r["kind"] == "plan" and r["batches"] == 30 and "first night" in r["how"]
    read(b, 30)
    assert b.gate() == {"limit": "per_night"}
    b.clock.t = ts(24, 1, 40)  # the next night
    r = b.tonight()
    assert r["batches"] == 45 and r["used"] == 0 and "up from 30" in r["how"]
    read(b, 45)
    b.clock.t = ts(25, 1, 40)
    assert b.tonight()["batches"] == 68
    hist = rb.jload(b.file, {})["brains"]["claude"]["nights"]
    assert [hist[k]["batches"] for k in sorted(hist)] == [30, 45, 68]


def test_a_night_that_did_not_finish_its_budget_does_not_grow(env):
    b = budget(env, "claude", ts(23, 1, 40))
    read(b, 12)  # the books ran out
    b.clock.t = ts(24, 1, 40)
    assert b.tonight()["batches"] == 30


def test_the_5_hour_window_halves_it_waits_for_the_reset_and_keeps_a_share_for_you(env):
    b = budget(env, "claude", ts(23, 1, 40))
    b.tonight()
    read(b, 25)  # 25 batches fit in the window, then the limit
    b.seen(Job("claude"), claude_limit(3 * 3600))
    st = rb.jload(b.file, {})["brains"]["claude"]
    assert st["last_hit"]["kind"] == "window" and st["last_hit"]["fit"] == 25 and st["learned"] == 15
    g = b.gate()
    assert g["limit"] == "hit" and abs(g["until"] - (b.clock.t + 3 * 3600)) < 5
    b.clock.t += 3 * 3600 + 60  # the window has reset, but tonight's (halved) budget is read already
    assert b.gate() == {"limit": "per_night"}
    b.clock.t = ts(24, 1, 40)
    r = b.tonight()
    assert r["batches"] == 15 and "60% of the 25 that fit last night" in r["how"]
    assert "halved after the 5-hour window" in st["why"]
    read(b, 15)
    b.clock.t = ts(25, 1, 40)  # grows again, but never past 60% of what fit in one window (25: 15)
    r = b.tonight()
    assert r["batches"] == 15 and "60% of the 25 that fit on 23 Oct" in r["how"]
    lines = " ".join(b.lines())
    assert "Tonight's reading budget: 15 batches" in lines and "Last limit: the 5-hour window" in lines
    assert "after 25 batches in it" in lines


def test_the_weekly_limit_waits_days_and_starts_the_week_lower(env):
    b = budget(env, "claude", ts(20, 1, 40))
    for d in (20, 21, 22):  # three nights of 30, 45, 68
        b.clock.t = ts(d, 1, 40)
        read(b, b.tonight()["batches"])
    b.clock.t = ts(23, 1, 40)
    b.tonight()
    read(b, 10)
    b.seen(Job("claude"), claude_limit(3 * 86400))  # the reset is days away: the weekly cap
    st = rb.jload(b.file, {})["brains"]["claude"]
    assert st["last_hit"]["kind"] == "week"
    # 153 batches fit in that week: 60% of it a night is 13, lower than half of 68
    assert st["learned"] == 13 and "weekly limit" in st["why"]
    b.clock.t = ts(24, 1, 40)
    assert b.gate()["limit"] == "hit"  # still days to go
    assert "Last limit: the weekly limit" in " ".join(b.lines())
    b.clock.t = ts(27, 1, 40)
    assert b.gate() is None and b.tonight()["batches"] == 13


def test_a_limit_the_stand_in_answered_for_still_counts(env):
    b = budget(env, "claude", ts(23, 2))
    b.tonight()
    read(b, 8)
    ok = Result(Verdict.OK, "{}", usage={"limits": [{"brain": "claude", "retry_after_s": 7200, "detail": "x"}]})
    b.seen(Job("agy"), ok)
    assert b.gate()["limit"] == "hit"


def test_agy_hits_its_days_limit_and_waits_for_googles_day(env):
    b = budget(env, "agy", ts(23, 2))
    b.tonight()
    read(b, 20)
    b.seen(Job("agy"), Result(Verdict.RATE_LIMITED, detail="quota exhausted"))
    st = rb.jload(b.file, {})["brains"]["agy"]
    assert st["last_hit"]["kind"] == "day" and st["capacity"] == 20 and st["hold_until"] > b.clock.t


# ---------------------------------------------------------------------------------------------- a number
def test_a_number_is_a_hard_ceiling(env):
    env.app.settings.set("integrate.per_night", 20)
    b = budget(env, "claude", ts(23, 1, 40))
    r = b.tonight()
    assert r["batches"] == 20 and "your ceiling" in r["how"]
    read(b, 20)
    assert b.gate() == {"limit": "per_night"}
    for d in (24, 25, 26):  # clean nights: it never grows past the ceiling
        b.clock.t = ts(d, 1, 40)
        assert b.tonight()["batches"] == 20
        read(b, 20)


def test_the_owners_60_keeps_reading_60_from_the_first_night(env):
    """An install that had integrate.per_night = 60 and read 60 a night before keeps a ceiling of 60 at once."""
    env.app.settings.set("integrate.per_night", 60)
    (env.app.paths.state / "integrate").mkdir(parents=True, exist_ok=True)
    jsave(env.app.paths.state / "integrate" / "ledger.json", {"nights": {"2026-10-20": {"batches": 60}}})
    b = budget(env, "agy", ts(23, 1, 40))
    assert b.tonight()["batches"] == 60
    read(b, 60)
    assert b.gate() == {"limit": "per_night"}
    b.clock.t = ts(24, 1, 40)
    assert b.tonight()["batches"] == 60


# ---------------------------------------------------------------------------------------------- money, free, local
def test_an_api_key_reads_until_the_nights_money_is_spent(env):
    env.app.settings.set("brain.base_urls", {"custom": "https://api.example.com/v1"})
    env.app.settings.set("brain.models", {"custom": {"low": "m", "medium": "m", "high": "m"}})
    env.app.secrets.set("custom.api_key", "k")
    b = budget(env, "custom", ts(23, 2))
    r = b.tonight()
    assert r["kind"] == "money" and r["cost"] == 0.5 and r["batches"] is None
    b.seen(Job("custom"), Result(Verdict.OK, "{}", usage={"cost": 0.2}))
    b.seen(Job("custom"), Result(Verdict.OK, "{}", usage={"cost": 0.2}))
    assert b.gate() is None
    # no cost reported: estimated from tokens (20k in, 2k out at $2 and $8 per million = $0.056)
    b.seen(Job("custom"), Result(Verdict.OK, "{}", usage={"prompt_tokens": 20_000, "completion_tokens": 2_000}))
    assert b.tonight()["spent"] == pytest.approx(0.456)
    b.seen(Job("custom"), Result(Verdict.OK, "{}", usage={"cost": 0.05}))
    assert b.gate() == {"limit": "cost"}
    assert "$0.50" in b.lines()[0] and "spent" in b.lines()[0]
    b.clock.t = ts(24, 2)
    assert b.gate() is None


def test_a_free_gemini_key_with_a_tiny_limit_says_to_read_with_agy_or_this_computer(env):
    env.app.settings.set("brain.models", {"gemini": {"low": "gemini-flash-lite-latest"}})
    b = budget(env, "gemini", ts(23, 2))
    pool = "gemini:gemini-flash-lite-latest"
    env.app.quota.record(pool, "rate_limited", hint={"per": "day", "limit": 15})
    r = b.tonight()
    assert r["kind"] == "free" and r["batches"] == 9 and "daily limit (15 requests)" in r["how"]
    assert "agy" in r["advice"] and "this computer" in r["advice"]
    assert any("agy" in ln for ln in b.lines())
    env.app.settings.set("quota.limits", {pool: 250})  # a bigger limit: room enough, no advice
    r = b.tonight()
    assert r["batches"] == 150 and not r["advice"]


def test_a_per_minute_limit_on_a_free_key_changes_nothing_but_the_days_limit_does(env):
    b = budget(env, "gemini", ts(23, 2))
    b.tonight()
    read(b, 6)
    minute = "HTTP 429: Quota exceeded for metric generate_content_free_tier_requests per minute. Please retry in 30s."
    b.seen(Job("gemini"), Result(Verdict.RATE_LIMITED, detail=minute, retry_after_s=30))
    assert b.gate() is None and rb.jload(b.file, {})["brains"]["gemini"]["learned"] == 30
    b.seen(Job("gemini"), Result(Verdict.RATE_LIMITED, detail="HTTP 429: free tier requests per day exhausted"))
    st = rb.jload(b.file, {})["brains"]["gemini"]
    assert st["last_hit"]["kind"] == "day" and st["learned"] == 15 and b.gate()["limit"] == "hit"


def test_the_model_on_this_computer_has_no_budget(env):
    env.app.settings.set("brain.models", {"ollama": {"low": "m", "medium": "m", "high": "m"}})
    b = budget(env, "ollama", ts(23, 2))
    read(b, 500)
    r = b.tonight()
    assert r["kind"] == "local" and r["batches"] is None and b.gate() is None


# ---------------------------------------------------------------------------------------------- when the night starts
def test_the_night_starts_5_hours_before_you_wake_but_not_before_bed_nor_after_integrate_at(env):
    b = budget(env, "claude", ts(22, 12))
    d = dt.date(2026, 10, 23)
    # the night hours (23:30 to 07:00): 5 hours before 07:00 is 02:00, later than 01:30, so 01:30
    assert b.plan(d) == (dt.datetime(2026, 10, 23, 1, 30), dt.datetime(2026, 10, 23, 1, 30))
    b.app.availability.sleep = lambda: [(dt.datetime(2026, 10, 22, 23, 0), dt.datetime(2026, 10, 23, 5, 30))]
    assert b.plan(d)[0] == dt.datetime(2026, 10, 23, 0, 30)  # up at 05:30: start at 00:30
    b.app.availability.sleep = lambda: [(dt.datetime(2026, 10, 23, 1, 0), dt.datetime(2026, 10, 23, 4, 0))]
    assert b.plan(d)[0] == dt.datetime(2026, 10, 23, 1, 0)  # a short night: from bedtime
    b.app.availability.sleep = lambda: [(dt.datetime(2026, 10, 22, 23, 0), dt.datetime(2026, 10, 23, 5, 30))]
    b.clock.t = ts(23, 0, 10)
    assert b.night() == "2026-10-22"  # before tonight's start: still yesterday's night
    b.clock.t = ts(23, 0, 31)
    assert b.night() == "2026-10-23"


# ---------------------------------------------------------------------------------------------- through the feature
class FakeClaude(Brain):
    id = "claude"
    label = "Claude Code"
    kind = "cli"

    def __init__(self, script):
        self.script = script

    def available(self):
        return True, ""

    def has_worked(self, app):
        return True

    def run(self, task):
        r = self.script.pop(0)
        self.metered(None, r)
        return r


def test_a_limit_hit_through_the_queue_stops_reading_and_graph_says_when_it_resets(world, monkeypatch):
    from kurooto import providers

    env = world
    script = [claude_limit(2 * 3600)]
    real = providers._build
    monkeypatch.setattr(
        providers, "_build", lambda app, which: FakeClaude(script) if which == "claude" else real(app, which)
    )
    env.app.settings.set("integrate.roles", {"bulk": "claude", "check": "claude"})
    integ = env.integrate
    integ.budget.clock = Clock(ts(23, 2))
    assert integ.tick()["submitted"] == 1
    env.app.jobs.run_next()
    r = integ.tick()
    assert r["limit"] == "hit" and r["until"] > ts(23, 3)
    out = env.say("/graph")
    assert "Tonight's reading budget: 15 batches" in out and "Last limit: the 5-hour window" in out
    assert "Nothing to start" in env.say("/graph now")
    assert "Concept graph:" in rb.usage_text(env.app)
    integ.budget.clock.t = ts(23, 4, 30)  # after the reset, the same night: the halved budget isn't read yet
    env.app.settings.set("quota.on", False)  # (the queue's own hold for that limit runs on the real clock)
    script += [Result(Verdict.OK, answer(c_ad()), usage={"cost": 0.01}), Result(Verdict.OK, '{"items": []}')] * 2
    assert integ.tick()["submitted"] == 1
    while env.app.jobs.run_next():
        pass
    assert integ.budget.tonight()["used"] == 1
    assert integ.card()["lines"][0].startswith("Tonight's reading budget")


def test_an_early_riser_gets_an_early_start(world):
    env = world
    integ = env.integrate
    integ.budget.clock = Clock(ts(22, 20))
    env.app.availability.sleep = lambda: [(dt.datetime(2026, 10, 22, 23, 0), dt.datetime(2026, 10, 23, 5, 0))]
    integ.plan_night()
    job = env.app.scheduler.get("integrate:early")
    assert job is not None and job.next_run == dt.datetime(2026, 10, 23, 0, 0).timestamp()
    env.app.availability.sleep = None  # the usual night hours: 01:30 is early enough, no extra start
    integ.plan_night()
    assert env.app.scheduler.get("integrate:early") is None

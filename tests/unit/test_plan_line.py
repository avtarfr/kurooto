"""The plan line (0.5.22): a text request of yours that usually takes more than 20 s on that AI gets one short line
first ("Searching your notes, then answering (about 40 s with ...)"), guessed from the last requests; never for quiet
or background work, never while you're on a call, and jobs.plan_line turns it off."""

from __future__ import annotations

import datetime as dt

import pytest

from kurooto import providers
from kurooto.providers.base import Result, Verdict


class Slow:
    id, label, kind = "slow", "A slow AI", "api"

    def __init__(self):
        self.secs = 40.0

    def available(self):
        return True, ""

    def run(self, task):
        return Result(Verdict.OK, "Done.", self.secs)


@pytest.fixture
def slow(env, monkeypatch):
    brain = Slow()
    monkeypatch.setattr(providers, "build", lambda a, w: brain if w == "main" else None)
    env.app.settings.set("brain.main", "main")
    return env, brain


def ask(env, prompt="summarise my notes on martingales", **kw):
    jid = env.app.jobs.submit(prompt, effort="low", reply_to="5", **kw)
    assert env.app.jobs.run_next() == jid
    return jid


def texts(env):
    return env.fake.texts()


def test_a_long_answer_gets_a_line_first_once_its_usual_time_is_known(slow):
    env, _ = slow
    for _ in range(3):  # fewer than three past requests: no guess, no line
        ask(env)
    assert not any("then answering" in t for t in texts(env))
    before = len(texts(env))
    ask(env)
    new = texts(env)[before:]
    assert new[0] == "Searching your notes, then answering (about 40 s with A slow AI)."
    assert "Done." in new[1]
    before = len(texts(env))
    ask(env, "explain https://example.org/paper and what it means")
    assert texts(env)[before] == "Reading the link, then answering (about 40 s with A slow AI)."


def test_never_quiet_background_on_a_call_quick_or_switched_off(slow):
    env, brain = slow
    for _ in range(3):
        ask(env)
    n = len(texts(env))
    ask(env, quiet=True)  # a call's request, the terminal
    env.app.jobs.submit("summarise my notes for the digest", effort="low", background=True)
    env.app.jobs.run_next()
    assert not any("then answering" in t for t in texts(env)[n:])
    env.app.availability.set_on_call(dt.datetime.now() + dt.timedelta(minutes=10))
    ask(env)
    assert not any("then answering" in t for t in texts(env)[n:])
    env.app.availability.set_on_call(None)
    env.app.settings.set("jobs.plan_line", False)
    ask(env)
    assert not any("then answering" in t for t in texts(env)[n:])
    env.app.settings.set("jobs.plan_line", True)
    brain.secs = 5.0
    for _ in range(6):  # the median moves under 20 s
        ask(env)
    assert not texts(env)[-1].endswith("with A slow AI).")

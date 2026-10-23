"""Repair with two readings (core/repair.py): a short request no pattern takes, close to two requests' examples, gets
both as buttons instead of a guess; a tap runs one, the second repair of a phrasing teaches it (modules/cases.py);
not close, another channel or repair.on off: as before."""

from __future__ import annotations

import re

import pytest

from kurooto.core import repair
from kurooto.modules.base import Incoming, Intent, Module


class Plans(Module):
    id = "plans_test"
    title = "Plans (test)"

    def intents(self):
        return [
            Intent(
                "plan_today",
                "what's my plan today",
                lambda t: {} if re.fullmatch(r"(?i)what'?s my plan today\??", t) else None,
                lambda msg, s: "Plan for today: gym.",
                questions=True,
            ),
            Intent(
                "day_plan",
                "what's my day plan",
                lambda t: {} if re.fullmatch(r"(?i)what'?s my day plan\??", t) else None,
                lambda msg, s: "Day plan: study.",
                questions=True,
            ),
        ]


@pytest.fixture
def plans(env):
    env.app.modules["plans_test"] = Plans(env.app)
    env.on("plans_test", "cases")
    return env


def buttons(env):
    sent = [p for m, p in env.fake.sent if m == "sendMessage" and "reply_markup" in p]
    return [b for row in sent[-1]["reply_markup"]["inline_keyboard"] for b in row]


def test_two_close_readings_are_asked_and_the_second_repair_teaches_it(plans):
    env = plans
    rows = repair.readings("whats my plan", env.app.enabled(), True)
    assert [r["intent"] for r in rows[:2]] == ["day_plan", "plan_today"] and repair.close(rows)
    assert env.say("whats my plan") == 'Did you mean "what\'s my day plan" or "what\'s my plan today"?'
    labels = {b["text"]: b["callback_data"] for b in buttons(env)}
    assert set(labels) >= {"what's my day plan", "what's my plan today", "Neither"}
    assert env.press(labels["what's my day plan"]) == "OK."
    assert env.fake.texts()[-1] == "Day plan: study."
    assert env.press(labels["what's my day plan"]) == "That's old now: say it again."
    env.say("whats my plan")  # asked again; the second repair to the same request teaches it
    labels = {b["text"]: b["callback_data"] for b in buttons(env)}
    env.press(labels["what's my day plan"])
    said = env.fake.texts()[-1]
    assert said.startswith('You picked "what\'s my day plan" for "whats my plan" 2 times, so: Learned')
    assert env.say("whats my plan") == "Day plan: study."  # taught: no question now


def test_neither_not_close_other_channels_and_off_are_as_before(plans):
    env = plans
    env.say("whats my plan")
    labels = {b["text"]: b["callback_data"] for b in buttons(env)}
    assert env.press(labels["Neither"]) == "OK, left as it is."
    assert not repair.close(repair.readings("plans", env.app.enabled(), False))
    assert env.say("plans").startswith("I can't answer free text yet")
    said: list[str] = []
    env.app.handle(Incoming("whats my plan", via="terminal", respond=lambda t, buttons=None: said.append(t)))
    assert not said[0].startswith("Did you mean")
    assert env.say("what's my plan today") == "Plan for today: gym."  # a pattern takes it: it runs, no question
    env.app.settings.set("repair.on", False)
    assert env.say("whats my plan").startswith("I can't answer free text yet")

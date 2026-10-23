"""Keep or drop (core/keep.py): what you use of each feature is counted (requests, commands, buttons, call tools,
replies); on day 10 one message asks Keep / Quiet / Off per feature, and monthly about features unused for 60 days that
still run scheduled jobs. Quiet stops what it sends by itself (Calm's stop list), Off turns it off; both with Undo."""

import datetime as dt

import pytest

from kurooto.core import calm as calm_mod
from kurooto.core import keep as keep_mod

T0 = dt.datetime(2026, 11, 2, 12, 0)


@pytest.fixture
def kp(env, monkeypatch):
    clock = {"t": T0}
    for mod in (keep_mod, calm_mod):
        monkeypatch.setattr(mod, "now", lambda: clock["t"])
    app = env.app
    app.settings.set("availability.night.enabled", False)
    app.settings.set("setup.done", True)
    env.on("reminders", "weekly")
    app.keep.start()
    return env, app.keep, clock


def sent(env) -> list[dict]:
    return [p for m, p in env.fake.sent if m == "sendMessage"]


def labels(p: dict) -> list[str]:
    return [b["text"] for row in (p.get("reply_markup") or {}).get("inline_keyboard", []) for b in row]


def test_what_you_use_is_counted_by_feature(kp):
    env, keep, clock = kp
    env.say("/reminders")
    env.say("remind me in 20 minutes to stretch")
    env.app.callback("remx:nothing:")
    use = keep.counts(10)
    assert use["reminders"] == {"command": 1, "intent": 1, "button": 1}
    assert "weekly" not in use
    keep.used("reminders", "intent", via="setup")  # the setup page's try-it box doesn't count
    assert keep.counts(10)["reminders"]["intent"] == 1
    out = env.say("/keep")
    assert "- Reminders: used 3 times (1 request, 1 command, 1 button)" in out
    assert "- Weekly summary: not used" in out


def test_day_ten_asks_keep_quiet_or_off_and_both_undo(kp):
    env, keep, clock = kp
    env.say("/reminders")
    clock["t"] = T0 + dt.timedelta(days=9)
    assert keep.tick() == ""
    clock["t"] = T0 + dt.timedelta(days=10)
    assert keep.tick() == "first"
    p = sent(env)[-1]
    assert p["text"].startswith("Keep or drop\n\nTen days in:")
    assert "- Weekly summary: not used" in p["text"] and "- Reminders: used 1 time (1 command)" in p["text"]
    assert "Telegram" not in p["text"]
    assert labels(p)[:3] == ["Weekly summary: Keep", "Quiet", "Off"]  # the least used first
    assert keep.tick() == ""  # once
    # Quiet: Weekly keeps working, its messages stop
    assert env.press("keep:weekly:quiet") == "Done: Weekly summary keeps working but stops messaging you."
    assert {"weekly.summary", "weekly.call"} <= set(env.app.settings.get("notify.calm.stopped"))
    assert env.app.is_on("weekly")
    n = len(sent(env)) - 1
    assert env.app.notify("Your week: 3 deadlines done.", why="weekly.summary") is None and len(sent(env)) - 1 == n
    undo = sent(env)[-1]["reply_markup"]["inline_keyboard"][0][0]["callback_data"]
    env.press(undo)
    assert env.app.settings.get("notify.calm.stopped") == []
    # Off: through the usual path, with Undo
    assert env.press("keep:weekly:off") == "Done: turns off Weekly summary."
    assert not env.app.is_on("weekly") and env.app.scheduler.jobs("weekly:") == []
    env.press(sent(env)[-1]["reply_markup"]["inline_keyboard"][0][0]["callback_data"])
    assert env.app.is_on("weekly")
    assert env.press("keep:reminders:keep") == "OK, Reminders stays as it is."
    assert "reminders" in keep.state()["answered"]


def test_monthly_only_unused_features_that_still_run_jobs(kp):
    env, keep, clock = kp
    keep._mark("first", T0.timestamp())
    clock["t"] = T0 + dt.timedelta(days=59)
    assert keep.tick() == ""  # 60 days of counting first
    clock["t"] = T0 + dt.timedelta(days=61)
    assert [m.id for m in keep.idle()] == ["weekly"]  # Reminders runs no recurring job
    env.say("/week")  # used: not asked
    assert keep.idle() == []
    clock["t"] = T0 + dt.timedelta(days=122)
    assert keep.tick() == "monthly"
    p = sent(env)[-1]
    assert "\nNot used in 60 days" in p["text"] and "Weekly summary" in p["text"]
    clock["t"] += dt.timedelta(days=5)
    assert keep.tick() == ""  # at most once a month
    env.press("keep:weekly:keep")
    clock["t"] += dt.timedelta(days=40)
    assert keep.idle() == []  # kept: not asked again for 90 days


def test_never_without_setup_or_with_keep_ask_off(kp):
    env, keep, clock = kp
    env.app.settings.set("setup.done", False)
    clock["t"] = T0 + dt.timedelta(days=10)
    assert keep.tick() == ""
    env.app.settings.set("setup.done", True)
    env.app.settings.set("keep.ask", False)
    n = len(sent(env))
    assert keep.tick() == "" and len(sent(env)) == n
    clock["t"] = T0 + dt.timedelta(days=100)
    assert keep.tick() == "" and len(sent(env)) == n


def test_keep_for_one_feature_offers_its_buttons(kp):
    env, keep, clock = kp
    env.say("/keep weekly")
    p = sent(env)[-1]
    assert p["text"] == "In the last 30 days:\n- Weekly summary: not used"
    assert labels(p) == ["Weekly summary: Keep", "Quiet", "Off"]
    assert "No feature that's on" in env.say("/keep astrology")
    assert calm_mod.REASONS["keep.ask"].setting == "keep.ask"

"""0.5.1: "I'm awake" is the morning call now; a time in a past or negated clause ("since I didn't wake up at 12")
is never when to call or remind; "cancel that call" in plain English; `kurooto ask` never reads a shell command as
English ("!command" runs one there)."""

from __future__ import annotations

import builtins
import datetime as dt
import json

import pytest

from kurooto import cli
from kurooto.modules.calls import deploy
from kurooto.modules.text import a_time, stale_time, up_now

WOKE = (
    "Helllooo, I am awake, i just woke up, call me if you need to re configure the day accordingly and ask me about "
    "things since I didn't wake up at 12 as I said I would"
)
NOON = dt.datetime(2026, 10, 19, 12, 0)


@pytest.fixture
def calls(env):
    env.app.secrets.set("gemini.api_key", "k")
    deploy.ensure_secrets(env.app)
    env.app.settings.set("calls.worker", {"url": "https://kurooto-abc.your-subdomain.workers.dev"})
    env.app.settings.set("availability.night.enabled", False)
    env.on("calls", "alarm", "reminders", "checkins")
    return env


def rings(app) -> list[dict]:
    return list((json.loads((app.paths.state / "calls" / "rings.json").read_text()) or {}).values())


# ------------------------------------------------------------------------------------------------- reading
def test_a_time_in_a_past_or_negated_clause_is_never_the_time():
    assert a_time(WOKE, NOON) is None and stale_time(WOKE) == "12"
    assert a_time("call me, I was supposed to be up at 9", NOON) is None
    assert a_time("remind me at 5 since I didn't do it at 3", NOON) == "17:00"
    assert a_time("I said I'd wake at 10, call me at 4", NOON) == "16:00"
    assert a_time("the evening check-in was at 9, move it to 10 pm", NOON) == "22:00"
    assert a_time("call me at 9 as I said I would", NOON) == "21:00" and stale_time("call me at 9") is None


@pytest.mark.parametrize(
    "text, up",
    [
        (WOKE, True),
        ("I'm awake", True),
        ("i just woke up", True),
        ("I'm up", True),
        ("I'm up now, call me if you need anything", True),
        ("I'm still up", False),
        ("I'm up for a call at 5", False),
        ("I'm up but don't call me", False),
        ("I'm up, remind me at 3 to send the form", False),
        ("I'm up, call me in 20 minutes", False),
        ("I'm up, also what's due today", False),
        ("I didn't wake up at 7", False),
    ],
)
def test_up_now(text, up):
    assert up_now(text) is up


# ------------------------------------------------------------------------------------------- the morning
def test_awake_rings_the_morning_call_now_and_books_nothing_at_the_time_it_mentions(calls):
    out = calls.say(WOKE)
    assert out.startswith("Good morning. Calling you now")
    r = rings(calls.app)[-1]
    assert r["key"] == "alarm:awake" and not r["alarm"] and "morning_plan" in r["reason"]
    assert not calls.app.scheduler.jobs("calls:ring:")  # nothing at 12:00 tomorrow
    assert calls.app.modules["alarm"].next() is None  # and it isn't an alarm
    assert calls.say("I'm awake").startswith("Good morning.")


def test_the_awake_call_is_a_plain_call_not_the_alarm(calls):
    alarm, c = calls.app.modules["alarm"], calls.app.modules["calls"]
    calls.say("i just woke up")
    r = rings(calls.app)[-1]
    assert c._tell_owner_module(r, "missed") is False and alarm.next() is None  # no repeat ring as an alarm
    assert alarm.call_reschedule("alarm:awake", dt.datetime.now() + dt.timedelta(minutes=10)) is None
    alarm.set(dt.datetime.now().replace(microsecond=0) + dt.timedelta(hours=2))
    assert "still set" in calls.say("I'm up")


def test_only_a_time_that_didnt_happen_asks_when(calls):
    assert calls.say("call me, I didn't wake up at 12").startswith("When should I call?")
    assert calls.say("remind me since I didn't do it at 3").startswith("When should I remind you?")
    assert not calls.app.scheduler.jobs("calls:ring:") and not calls.app.scheduler.jobs("reminders:")
    assert "17:00" in calls.say("remind me at 5 since I didn't do it at 3")


def test_call_me_at_5_is_five_oclock_not_five_minutes(calls):
    calls.say("call me at 5")
    at = dt.datetime.fromtimestamp(calls.app.scheduler.jobs("calls:ring:")[0].next_run)
    assert (at.hour, at.minute) == (17, 0)


# --------------------------------------------------------------------------------------------- cancelling
def test_cancel_a_booked_call_in_plain_english(calls):
    c = calls.app.modules["calls"]
    assert calls.say("cancel that call").startswith("No calls booked")
    base = dt.datetime.now().replace(second=0, microsecond=0) + dt.timedelta(days=1)
    c.schedule(base.replace(hour=12, minute=0), "the laundry", key="aaaa1111")
    c.schedule(base.replace(hour=18, minute=30), "stand-up", key="bbbb2222")
    calls.say("cancel that call")
    texts = calls.fake.texts()
    assert any("Which one?" in t for t in texts) and any("aaaa1111" in t and "the laundry" in t for t in texts)
    assert len(calls.app.scheduler.jobs("calls:ring:")) == 2  # two it could mean: listed, none taken off
    assert calls.say("cancel the 9:15 call").startswith("Or say")
    assert any("No booked call at 9:15" in t for t in calls.fake.texts())
    assert calls.say("cancel the 12:00 call").startswith("Cancelled the") and not c.app.scheduler.get(
        "calls:ring:aaaa1111"
    )
    assert calls.press("callx:bbbb2222:x") == "Cancelled." and not calls.app.scheduler.jobs("calls:ring:")
    assert calls.press("callx:bbbb2222:x") == "Already gone."


def test_cancel_that_call_and_shell_lines_leave_the_check_ins_alone(calls):
    ck = calls.app.modules["checkins"]
    ck.move("evening", "23:59")
    for text in ("cancel that call", "call-me --cancel 1234", "drop the call"):
        calls.say(text)
        assert ck.today()["evening"]["status"] == "planned", text
    calls.say("skip tonight's call")
    assert ck.today()["evening"]["status"] == "skipped"


# ------------------------------------------------------------------------------------------- kurooto ask
@pytest.mark.parametrize(
    "line, shell",
    [
        ("call-me --cancel 1234", True),
        ("ask-me --pending", True),
        ("kurooto status", True),
        ("systemctl --user restart kurooto", True),
        ("git log --oneline", True),
        ("cancel that call", False),
        ("call me at 5", False),
        ("Kurooto, call me now", False),
        ("make the evening call half an hour earlier", False),
        ("i just woke up", False),
        ("focus off", False),
    ],
)
def test_shell_line(line, shell):
    assert cli.shell_line(line) is shell


def test_ask_repl_runs_bang_commands_and_never_sends_shell_lines(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    lines = iter(["!echo hi", "call-me --cancel 1234", "systemctl --user status kurooto", "I'm awake"])

    def typed(prompt=""):
        try:
            return next(lines)
        except StopIteration:
            raise EOFError from None

    sent, ran = [], []
    monkeypatch.setattr(builtins, "input", typed)
    monkeypatch.setattr(cli, "say", lambda text: sent.append(text) or {"ok": True, "replies": ["Good morning."]})
    monkeypatch.setattr("subprocess.run", lambda cmd, **kw: ran.append(cmd))
    assert cli.plain_loop(1) == 0
    out = capsys.readouterr().out
    assert sent == ["I'm awake"] and ran == ["echo hi"]
    assert "$ echo hi" in out and out.count(cli.SHELL_HINT) == 2
    assert cli.plain("systemctl --user status kurooto", True, 1) == 2 and sent == ["I'm awake"]

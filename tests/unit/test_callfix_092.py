"""0.9.2 call fixes, from a midday check-in call that went wrong:
1. repeating reminders ("every day at 22:15", reminders.repeat), listed once with Cancel and Skip next;
2. "make it 10:15" after setting 22:00 moves that reminder (change_reminder) instead of adding a second;
3. (the call page: tests/js/callpage.mjs 10 and 11) two assistant turns aren't run together, one question at a time;
4. an after-class question already answered in spirit (its quiz talked about) isn't asked again;
5. (the call page: tests/js/callpage.mjs 12) the greeting is said once, with what the call starts from fetched first.
"""

from __future__ import annotations

import asyncio
import datetime as dt

import pytest

from kurooto.core import actions
from kurooto.core.clock import now
from kurooto.core.scheduler import Scheduler
from kurooto.modules import reminders as R


def tomorrow(h: int, m: int = 0) -> dt.datetime:
    return dt.datetime.combine(now().date() + dt.timedelta(days=1), dt.time(h, m))


def series(app) -> list:
    return [j for j in app.scheduler.jobs("reminders:") if j.action == "reminders.fire"]


# ------------------------------------------------------------------------------------------ 1. repeating
def test_how_often_is_read_from_words_and_tool_arguments():
    assert R.repeat_days("every day") == list(range(7))
    assert R.repeat_days("daily") == list(range(7))
    assert R.repeat_days("weekdays") == [0, 1, 2, 3, 4]
    assert R.repeat_days("on weekends") == [5, 6]
    assert R.repeat_days("mon,thu") == [0, 3]
    assert R.repeat_days("Monday and Thursday") == [0, 3]
    assert R.repeat_days("to call my parents from today onwards every day at 10 pm") == list(range(7))
    assert R.repeat_days("at 9 to gym every Monday and Thursday") == [0, 3]
    assert R.repeat_days("on Tuesdays at 5 to water the plants") == [1]
    assert R.repeat_days("at 9 to check the daily summary") is None  # "daily" as a word in the text
    assert R.repeat_days("at 9 to call the clinic on monday") is None  # one Monday, not every
    assert R.repeat_days("tomorrow at 9") is None
    left = R.strip_repeat("to call my parents from today onwards every day at 10 pm until friday")
    assert " ".join(left.split()) == "to call my parents at 10 pm"
    assert R.repeat_label({"days": [0, 3]}) == "every Mon and Thu"
    assert R.repeat_label({"days": [0, 1, 2, 3, 4]}) == "on weekdays"


def test_a_series_next_time_and_its_end():
    rep = {"days": [0, 3], "at": "09:00", "until": "2026-11-05"}
    thu = dt.datetime(2026, 10, 29, 9, 0)  # a Thursday
    assert R.next_time(rep, thu - dt.timedelta(seconds=1)) == thu
    assert R.next_time(rep, thu) == dt.datetime(2026, 11, 2, 9, 0)  # the Monday after
    assert R.next_time(rep, dt.datetime(2026, 11, 5, 9, 0)) is None  # past its last day
    assert R.until_date("4 dec", dt.datetime(2026, 10, 29)) == dt.date(2026, 12, 4)
    assert R.until_date("2026-12-04") == dt.date(2026, 12, 4)


def test_the_scheduler_keeps_a_series_that_books_itself_again(tmp_path):
    """_rearm relies on this: a one-off job whose action books the same key at a later time isn't dropped."""
    t = [1_800_000_000.0]
    s = Scheduler(tmp_path / "s.db", clock=lambda: t[0])
    s.action("x", lambda p: s.at(t[0] + 86400, "x", p, key="k"))
    s.at(t[0] - 1, "x", {}, key="k")
    asyncio.run(s.tick())
    assert s.get("k") is not None and s.get("k").next_run == t[0] + 86400
    s.close()


def test_typed_every_day_makes_one_series_that_rearms_and_is_listed_once(env, monkeypatch):
    env.on("reminders")
    out = env.say("remind me to call my parents from today onwards every day at 10 pm")
    assert out.startswith("I'll remind you every day at 22:00, starting ") and out.endswith(": call my parents")
    (job,) = series(env.app)
    ref = job.key.split(":", 1)[1]
    assert job.payload["repeat"]["days"] == list(range(7)) and job.payload["series"] == ref
    first = job.when.astimezone().replace(tzinfo=None)
    monkeypatch.setattr(R, "now", lambda: first)  # it fires at its time
    env.app.modules["reminders"]._fire(dict(job.payload))
    assert env.fake.texts()[-1] == "Reminder: call my parents"
    (again,) = series(env.app)
    assert again.key == job.key
    assert again.when.astimezone().replace(tzinfo=None) == first + dt.timedelta(days=1)
    assert again.payload["ref"] != job.payload["ref"]  # each time said once (Reminders with the lid shut)
    monkeypatch.undo()
    env.say("/reminders")
    listed = [p for m, p in env.fake.sent if m == "sendMessage"][-1]
    assert listed["text"].startswith("Every day at 22:00  call my parents")
    row = listed["reply_markup"]["inline_keyboard"][0]
    assert [b["text"] for b in row] == ["Cancel", "Skip next"]
    assert env.press(row[1]["callback_data"]).startswith(f"Skipped {first + dt.timedelta(days=1):%a %d %b}")
    assert series(env.app)[0].when.astimezone().replace(tzinfo=None) == first + dt.timedelta(days=2)
    assert env.press(row[0]["callback_data"]) == "Cancelled, every time of it."
    assert series(env.app) == []


def test_the_call_tool_repeats_and_the_switch_turns_it_off(env):
    env.on("reminders")
    rem = env.app.modules["reminders"]
    tool = next(t for t in rem.call_tools() if t.name == "add_reminder")
    assert "repeat" in tool.params and "never say a reminder repeats" in tool.hint.lower()
    out = tool.run({"when": "tomorrow 07:00", "what": "stretch", "repeat": "weekdays", "until": "2099-01-01"})
    assert "on weekdays until" in out and "at 07:00" in out
    env.app.settings.set("reminders.repeat", False)
    tool = next(t for t in rem.call_tools() if t.name == "add_reminder")
    assert "repeat" not in tool.params
    out = rem.add(tomorrow(8), "water the plants", repeat=list(range(7)))
    assert "Repeating reminders are off, so this one comes once" in out
    assert "repeat" not in rem.app.scheduler.jobs("reminders:")[-1].payload
    (sr,) = [j for j in series(env.app) if j.payload.get("repeat")]
    rem._fire(dict(sr.payload))  # off: it comes once more and isn't booked again (the scheduler then drops it)
    assert env.app.scheduler.get(sr.key).next_run == sr.next_run
    ended = env.app.events.tail(20, kinds={"reminder_series_ended"})
    assert ended and ended[-1].get("why") == "off"


def test_the_api_adds_a_series_and_snoozing_one_time_keeps_it(env):
    env.on("reminders")
    r = actions.act(env.app, "reminder.add", {"when": "tomorrow 21:00", "what": "read", "repeat": "daily"})
    assert r["ok"] and "every day at 21:00" in r["message"]
    (job,) = series(env.app)
    assert actions.today(env.app)["reminders"][0]["repeat"] == "every day"
    key = job.key.split(":", 1)[1]
    r = actions.act(env.app, "reminder.snooze", {"key": key, "minutes": 30})
    assert r["ok"]
    jobs = series(env.app)
    assert len(jobs) == 2 and sum(bool(j.payload.get("repeat")) for j in jobs) == 1
    kept = env.app.scheduler.get(job.key)
    assert kept.when == job.when + dt.timedelta(days=1)  # the series goes on from its next time


# ---------------------------------------------------------------------------------------- 2. changing
def test_make_it_1015_moves_the_one_just_set(env):
    env.on("reminders")
    rem = env.app.modules["reminders"]
    rem.add(tomorrow(22), "Call parents")
    change = next(t for t in rem.call_tools() if t.name == "change_reminder")
    out = change.run({"when": "10:15"})
    assert out.startswith(f"Changed: now {tomorrow(22, 15):%a %d %b at %H:%M}: Call parents (was ")
    (job,) = series(env.app)
    assert job.when.astimezone().replace(tzinfo=None) == tomorrow(22, 15)
    out = change.run({"what": "parents", "repeat": "every day"})  # "can you do that every day?"
    assert "every day at 22:15" in out
    (job,) = series(env.app)
    assert job.payload["repeat"]["days"] == list(range(7))
    assert change.run({"what": "parents", "repeat": "once"}).startswith("Changed: now ")
    assert "repeat" not in series(env.app)[0].payload


def test_a_second_add_with_the_same_words_moves_the_first(env):
    env.on("reminders")
    rem = env.app.modules["reminders"]
    add = next(t for t in rem.call_tools() if t.name == "add_reminder")
    add.run({"when": "tomorrow 22:00", "what": "Call parents"})
    out = add.run({"when": "tomorrow 22:15", "what": "call my parents"})
    assert "moved it instead of adding a second" in out
    (job,) = series(env.app)
    assert job.when.astimezone().replace(tzinfo=None) == tomorrow(22, 15)
    add.run({"when": "tomorrow 23:00", "what": "call parents", "another": "yes"})  # they want both
    assert len(series(env.app)) == 2


def test_a_bare_time_takes_the_reading_nearest_the_old_one():
    old = dt.datetime(2026, 10, 30, 22, 0)
    base = dt.datetime(2026, 10, 29, 13, 30)
    assert R.moved_time(old, "10:15", base) == dt.datetime(2026, 10, 30, 22, 15)
    assert R.moved_time(old, "9", base) == dt.datetime(2026, 10, 30, 21, 0)
    assert R.moved_time(old, "10:15 am", base) == dt.datetime(2026, 10, 30, 10, 15)


# ------------------------------------------------------------------------- 4. answered in spirit on a call
@pytest.fixture
def chem(env):
    env.on("subjects", "deadlines", "capture")
    env.say("/subject add Organic Chemistry (oc)")
    today = now().date().isoformat()
    cap = env.app.modules["capture"]
    cap._ask({"subject": "organic-chemistry", "name": "Organic Chemistry", "day": today, "start": "09:00"})
    (q,) = env.app.ask.pending(source="capture")
    return env, q


def test_the_brief_says_todays_quiz_in_that_class_is_the_same_talk(chem):
    env, q = chem
    dl = env.app.modules["deadlines"]
    dl.add("Organic Chemistry: Quiz", dt.datetime.combine(now().date(), dt.time(9)), kind="exam",
           subject="organic-chemistry")  # fmt: skip
    rows = env.app.ask.call_brief()["open_questions"]
    (row,) = [r for r in rows if r["id"] == q["id"]]
    assert row["same_as"].startswith("Organic Chemistry: Quiz was in this class that day")
    tool = next(t for t in env.app.ask.call_tools() if t.name == "answer_question")
    assert "already answered in spirit" in tool.hint and "already answered it" in tool.hint


def calls_on(app):
    app.settings.set("modules.enabled", [*(app.settings.get("modules.enabled") or []), "calls"])
    calls = app.modules["calls"]
    calls.start()
    return calls


def test_after_the_call_its_answer_about_the_quiz_closes_the_after_class_question(chem):
    env, q = chem
    calls = calls_on(env.app)
    lines = [
        {"who": "Kurooto", "text": "Hi, how did your Organic quiz go this morning?"},
        {"who": "Sam", "text": "Pretty well, the mechanisms question was fine."},
        {"who": "Kurooto", "text": "How was the Organic Chemistry class today?"},
        {"who": "Sam", "text": "I already answered that."},
    ]
    calls.save_transcript({"since": "1", "lines": lines, "purpose": "Midday check-in"})
    got = env.app.ask.get(q["id"])
    assert got["status"] == "answered" and got["via"] == "call"
    log = (env.app.workspace / "organic-chemistry" / "class-log.md").read_text(encoding="utf-8")
    assert "mechanisms question" in log


def test_only_i_already_answered_closes_it_and_later_keeps_it(chem):
    env, q = chem
    cap = env.app.modules["capture"]
    assert (
        cap.covered_by_call([{"who": "Kurooto", "text": "How was Organic Chemistry?"}, {"who": "Sam", "text": "later"}])
        == 0
    )
    assert env.app.ask.get(q["id"])["status"] == "open"
    n = cap.covered_by_call(
        [{"who": "Kurooto", "text": "How was Organic Chemistry?"}, {"who": "Sam", "text": "I already told you."}]
    )
    assert n == 1 and env.app.ask.get(q["id"])["status"] == "expired"


# ---------------------------------------------------------------------------- 3 and 5: what calls are told
def test_calls_are_told_one_thing_at_a_time_and_to_greet_once(env):
    calls = calls_on(env.app)
    si = calls.config_template()["systemInstruction"]
    assert "One thing at a time: after a question, stop and wait for their answer." in si
    assert "greet them once" in calls.texts()["purpose"]
    env.on("checkins")
    assert "One question at a time" in env.app.modules["checkins"].script("midday")

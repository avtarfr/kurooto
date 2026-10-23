"""Start-by dates and crunch weeks (modules/startby.py): sizes guessed from the kind of deadline and corrected with a
tap, free time from the window less classes and calendar events, as-late-as-possible start-by dates, the morning plan,
the start-by message, the exam question, the Sunday summary's crunch weeks. A fixed clock throughout."""

from __future__ import annotations

import datetime as dt
import json

import pytest

from kurooto.modules import alarm as alarm_mod
from kurooto.modules import daily
from kurooto.modules import startby as sb_mod
from kurooto.modules.startby import allocate, free_slots, kind_of, overlap_h, parse_size, parse_window, size_text

T0 = dt.datetime(2026, 11, 2, 7, 0)  # a Monday morning


def at(day: int, h: int, m: int = 0) -> dt.datetime:
    return dt.datetime(2026, 11, day, h, m)


def last_buttons(env):
    sent = [p for m, p in env.fake.sent if m == "sendMessage" and "reply_markup" in p]
    return [b for row in sent[-1]["reply_markup"]["inline_keyboard"] for b in row]


@pytest.fixture
def clock(monkeypatch):
    class Clock:
        t = T0

    c = Clock()
    for mod in (sb_mod, daily, alarm_mod):
        monkeypatch.setattr(mod, "now", lambda: c.t)
    return c


@pytest.fixture
def sb(env, clock):
    env.app.settings.set("availability.night.enabled", False)
    env.app.settings.set("startby.window", "09:00-21:00")
    env.app.settings.set("startby.share", 50)
    env.on("subjects", "deadlines")
    env.say("/subject add Linear Algebra (la, linalg)")
    env.say("/subject add Topology")
    assert env.app.enable("startby") == (True, "Start-by dates is on")
    return env


def add(env, title: str, due: dt.datetime, **extra) -> str:
    dl = env.app.modules["deadlines"]
    dl.add(title, due, **extra)
    return next(i for i, it in dl.items().items() if it["title"] == title)


def plan(env) -> dict:
    return {r["title"]: r for r in env.app.modules["startby"].plan()}


# ------------------------------------------------------------------------------------------- helpers
def test_sizes_are_guessed_from_the_kind_of_deadline():
    assert kind_of("Problem set 4") == "problem_set"
    assert kind_of("Homework 2: chapter 3") == "problem_set"
    assert kind_of("Lab report: pendulum") == "report"  # a report beats a lab
    assert kind_of("Essay draft") == "report"
    assert kind_of("Topology midterm", "exam") == "exam"
    assert kind_of("Linear Algebra: Quiz", "exam") == "quiz"
    assert kind_of("Pay the hostel fee") == "other"
    assert parse_size("2-3 days") == 12 and parse_size("An evening") == 3 and parse_size("a week") == 25
    assert parse_size("10h") == 10 and parse_size("about 3 days") == 15 and parse_size("1.5 hours") == 1.5
    assert parse_size("two weeks") == 50 and parse_size("soon") is None and parse_size("0 h") is None
    assert size_text(12) == "about 12 h (2-3 days)" and size_text(7) == "about 7 h" and size_text(0.5) == "about 0.5 h"
    assert parse_window("18:00-01:00") == (dt.time(18), dt.time(1))  # past midnight
    assert parse_window("nonsense") == (dt.time(9), dt.time(22))


def test_free_time_is_the_window_less_what_is_busy():
    day = dt.date(2026, 11, 2)
    busy = [(at(2, 9), at(2, 13)), (at(2, 12), at(2, 14)), (at(2, 17), at(2, 17, 20)), (at(3, 10), at(3, 11))]
    got = free_slots(day, (dt.time(9), dt.time(21)), busy, min_gap=30)
    assert got == [(at(2, 14), at(2, 17)), (at(2, 17, 20), at(2, 21))]
    assert free_slots(day, (dt.time(9), dt.time(21)), busy, after=at(2, 18)) == [(at(2, 18), at(2, 21))]
    short = [(at(2, 14), at(2, 14, 50)), (at(2, 15, 10), at(2, 21))]
    assert free_slots(day, (dt.time(9), dt.time(21)), short, at(2, 13, 50)) == []  # gaps under half an hour
    late = free_slots(day, (dt.time(22), dt.time(1)), [])
    assert late == [(at(2, 22), at(3, 1))]  # a window past midnight
    assert overlap_h(got, at(2, 0), at(2, 16)) == 2


def test_as_late_as_possible_and_later_deadlines_push_earlier_ones():
    slots = [(at(d, 9), at(d, 21)) for d in range(2, 7)]  # Mon-Fri, 12 h each, half of it usable: 6 h a day
    items = [
        {"id": "report", "due": at(6, 23, 59), "hours": 12},
        {"id": "pset", "due": at(5, 23, 59), "hours": 3},
    ]
    got = allocate(items, slots, 0.5)
    assert got["report"] == (at(5, 9), 0.0)  # Fri and Thu
    assert got["pset"] == (at(4, 15), 0.0)  # Thu is the report's: Wed evening
    big = allocate([{"id": "x", "due": at(3, 12), "hours": 20}], slots, 0.5)
    assert big["x"] == (at(2, 9), 12.5)  # Mon 6 h + Tue morning 1.5 h: 12.5 h don't fit
    assert allocate([{"id": "y", "due": at(2, 8), "hours": 1}], slots, 0.5)["y"] == (None, 1.0)


# ------------------------------------------------------------------------------------ the plan
def test_start_by_dates_work_back_from_classes_and_calendar(sb):
    app = sb.app
    for day in ("mon", "tue", "wed", "thu", "fri"):
        sb.say(f"/class {day} 09:00-13:00 la")
    rows = [
        {"title": "Seminar", "start": at(4, 14).astimezone().isoformat(), "end": at(4, 18).astimezone().isoformat(),
         "all_day": False, "location": ""},
        {"title": "Holiday trip", "start": at(3, 0).astimezone().isoformat(),
         "end": at(4, 0).astimezone().isoformat(), "all_day": True, "location": ""},
    ]  # fmt: skip
    app.secrets.set("calendar.ics", json.dumps(["https://example.invalid/basic.ics"]))
    (app.paths.state / "calendar.json").write_text(json.dumps({"events": rows}), encoding="utf-8")
    sb.on("calendar")
    add(sb, "Lab report: pendulum", at(6, 23, 59))
    add(sb, "Problem set 4", at(5, 23, 59))
    p = plan(sb)
    # 13:00-21:00 free on weekdays (4 usable hours); Wed loses 14-18 to the seminar (2 usable)
    rep, ps = p["Lab report: pendulum"], p["Problem set 4"]
    assert (rep["hours"], rep["kind"], rep["guessed"]) == (12, "report", True)
    assert rep["start"] == dt.date(2026, 11, 3)  # Fri 4 + Thu 4 + Wed 2 + Tue 2
    assert ps["start"] == dt.date(2026, 11, 2) and ps["short"] == 0  # pushed back to Monday by the report
    assert app.modules["startby"].to_start() == [ps]  # only the problem set today
    assert app.modules["startby"].morning_lines() == [
        "Problem set 4 (due Thu 05 Nov): start working on it today, about 3 h (an evening) of work"
    ]
    # the morning page and the wake-up call
    view = daily.morning_view(app)
    assert view["start"] == [{"title": "Problem set 4", "when": "start today · due Thu 05 Nov"}]
    assert "Time to start (an estimate): Problem set 4 (due Thu 05 Nov): start working on it today" in app.modules["alarm"].script()
    # a skipped class frees its time
    app.modules["subjects"].set_skip(["linear-algebra"], day=dt.date(2026, 11, 3))
    assert plan(sb)["Lab report: pendulum"]["start"] == dt.date(2026, 11, 3)
    assert plan(sb)["Problem set 4"]["start"] == dt.date(2026, 11, 3)  # Tue has 6 usable hours now


def test_not_enough_time_says_so(sb):
    add(sb, "Essay final", at(3, 12))  # 12 h by tomorrow noon: Mon 6 h + Tue morning 1.5 h
    r = plan(sb)["Essay final"]
    assert r["start"] == dt.date(2026, 11, 2) and r["short"] == 4.5 and r["free"] == 7.5
    assert "start working on it now, it may not fit" in sb.app.modules["startby"].morning_lines()[0]


def test_done_ignored_and_far_away_deadlines_are_left_out(sb):
    i = add(sb, "Problem set 5", at(4, 23, 59))
    add(sb, "Drama club poster", at(4, 23, 59))
    add(sb, "Thesis chapter", at(2, 1) + dt.timedelta(days=60))
    sb.say("/ignore drama club")
    assert set(plan(sb)) == {"Problem set 5"}
    sb.app.modules["deadlines"]._status(i, "done")
    assert plan(sb) == {}


# --------------------------------------------------------------------------- the morning pass
def test_morning_pass_tells_big_ones_once_with_sizes_to_tap(sb, clock):
    app, s = sb.app, sb.app.modules["startby"]
    for day in ("mon", "tue", "wed", "thu", "fri"):
        sb.say(f"/class {day} 09:00-13:00 la")  # 4 usable hours a weekday
    s._morning({})  # the first pass: a hello only when something is to start (nothing yet: no message)
    n = len(sb.fake.texts())
    add(sb, "Project report", at(13, 23, 59))  # 12 h: Fri, Thu, Wed: start-by Wed 11 Nov
    add(sb, "Problem set 6", at(2, 23, 59))  # starts today, but the deadline's own day-before nudge covers it
    s._morning({})
    assert len(sb.fake.texts()) == n  # nothing big to start today
    told = json.loads(s.file.read_text())["told"]
    assert list(told.values()) == ["2026-11-02"]  # the problem set is in the morning plan from today
    clock.t = at(11, 7)
    s._morning({})
    text = sb.fake.texts()[-1]
    assert text.startswith("Start-by date\n\nTime to start: Project report, due Fri 13 Nov.")
    assert "about 12 h (2-3 days) of work (my guess for a report)" in text and "An estimate" in text
    assert [b["text"] for b in last_buttons(sb)] == ["An hour", "An evening", "A day", "A week", "Why?", "Less of this"]
    s._morning({})
    assert sb.fake.texts()[-1] == text  # once
    # one tap: a day of work (Fri's 4 usable hours and one on Thu) moves the start-by to Thu
    data = next(b["callback_data"] for b in last_buttons(sb) if b["text"] == "A day")
    assert sb.press(data) == "Project report: about 5 h (a day) of work. Start by Thu 12 Nov."
    r = plan(sb)["Project report"]
    assert (r["hours"], r["guessed"]) == (5, False)
    assert [e["kind"] for e in app.events.tail(20)].count("startby_size_set") == 1
    assert s.morning_lines() == []  # not today any more


def test_three_messages_a_day_at_most_and_a_hello_on_the_first_pass(sb, clock):
    s = sb.app.modules["startby"]
    sb.app.settings.set("startby.sizes.report", 30)  # 30 h each, due tomorrow and the day after: start now
    for k in range(2):
        add(sb, f"Report {k}", at(3 + k, 23, 59))
    s._morning({})
    hello = sb.fake.texts()[-1]
    assert "Start-by dates are on. Time to start now: Report 0 (due" in hello and "/startby shows them all" in hello
    sb.app.settings.set("startby.sizes.report", 100)  # far more than the free time: every essay starts now
    for k in "ABCD":
        add(sb, f"Essay {k}", at(5 + "ABCD".index(k), 23, 59))
    clock.t = at(3, 7)
    n = len(sb.fake.texts())
    s._morning({})
    new = sb.fake.texts()[n:]
    assert len(new) == 3 and all("Time to start: Essay" in t for t in new)
    assert all("there's hardly any free time for it before then" in t for t in new)  # Essay D took it all
    clock.t = at(4, 7)
    s._morning({})
    assert len(sb.fake.texts()) == n + 4 and "Time to start: Essay" in sb.fake.texts()[-1]
    assert sb.app.events.tail(5)[-1]["kind"] == "startby_planned"


def test_an_exam_asks_once_per_subject_and_the_answer_counts_for_the_subject(sb):
    app, s = sb.app, sb.app.modules["startby"]
    i = add(sb, "Topology midterm", at(16, 9), kind="exam", subject="topology")
    add(sb, "Topology final exam", at(30, 9), kind="exam", subject="topology")
    r = plan(sb)["Topology midterm"]
    assert (r["kind"], r["hours"], r["guessed"]) == ("exam", 10, True)
    s._morning({})
    qs = [q for q in app.ask.pending() if q["source"] == "startby"]
    assert len(qs) == 1 and "prepare for a Topology exam" in qs[0]["text"]
    assert qs[0]["choices"] == ["An evening", "A day", "2-3 days", "A week", "Two weeks"]
    s._morning({})
    assert len([q for q in app.ask.pending() if q["source"] == "startby"]) == 1  # once
    assert app.ask.answer(qs[0]["id"], "A week", "telegram")
    assert app.settings.get("startby.exam_by_subject") == {"topology": 25}
    assert plan(sb)["Topology final exam"]["hours"] == 25 and not plan(sb)["Topology final exam"]["guessed"]
    # a tap on one exam is that subject's exam size from then on
    assert "Topology exams count as that from now on." in s.set_size(i, 50)
    assert app.settings.get("startby.exam_by_subject.topology") == 50
    assert sb.say("/startby exam la 2-3 days") == "Linear Algebra exams: about 12 h (2-3 days) to prepare. " + (
        "Start-by dates follow it."
    )
    assert "Linear Algebra: about 12 h (2-3 days)" in sb.say("/startby exam")
    assert sb.say("/startby exam chemistry a week").startswith("I don't know a subject called 'chemistry'")


# ------------------------------------------------------------------------------- crunch weeks
def test_crunch_weeks_in_the_sunday_summary(sb, clock):
    app = sb.app
    for day in ("mon", "tue", "wed", "thu", "fri"):
        sb.say(f"/class {day} 09:00-13:00 la")
    app.settings.set("startby.exam_by_subject.topology", 25)
    add(sb, "Project report", at(10, 23, 59))
    add(sb, "Essay", at(11, 23, 59))
    add(sb, "Topology final exam", at(13, 9), kind="exam", subject="topology")
    add(sb, "Problem set 7", at(4, 23, 59))
    clock.t = dt.datetime(2026, 11, 8, 19, 0)  # Sunday evening
    weeks = app.modules["startby"].crunch()
    # week of 9 Nov: 49 h due; free 5 weekdays x 4 + 2 weekend days x 6 = 32 h
    assert weeks == [{"week": dt.date(2026, 11, 9), "work": 49.0, "free": 32.0}]
    sb.on("weekly")
    summary = app.modules["weekly"].summary()
    assert "Crunch weeks (an estimate): week of 9 Nov: about 49 h of work, about 32 h free." in summary
    assert "To start this week" not in summary  # all of it is to start now
    clock.t = dt.datetime(2026, 11, 1, 19, 0)  # a week earlier, the exam and the essay are still ahead
    assert "To start this week: Essay (Wed), Topology final exam (Sat)" in app.modules["weekly"].summary()
    assert sb.say("are there any crunch weeks coming?").startswith("Crunch weeks (an estimate): week of 9 Nov")
    app.settings.set("startby.crunch_weeks", 0)
    assert "Crunch weeks" not in app.modules["weekly"].summary()


# ------------------------------------------------------------------------------- asking, calls
def test_startby_command_intent_and_tools(sb):
    app = sb.app
    i = add(sb, "Lab report: pendulum", at(6, 23, 59))
    add(sb, "Problem set 4", at(2, 23, 59))
    assert (
        sb.say("/startby")
        == "Lab report: pendulum (due Fri 06 Nov): start working on it by Thu 05 Nov, about 12 h (2-3 days) of work"
    )
    texts = sb.fake.texts()[-3:]
    assert texts[0].startswith("Start-by dates, worked back from each deadline's size")
    assert texts[1].startswith("Problem set 4 (due") and texts[2].startswith("Lab report: pendulum (due")
    assert [b["text"] for b in last_buttons(sb)] == ["An hour", "An evening", "A day", "A week"]
    assert sb.say("when should I start the lab report?").startswith(
        "Lab report: pendulum (due Fri 06 Nov): start working on it by Thu 05 Nov"
    )
    assert "Problem set 4 (due Mon 02 Nov): start working on it today" in sb.say("when should I start?")
    assert sb.say("when do I start on the thesis?") == (
        "I don't have 'thesis' on the deadline list. /startby shows them all."
    )
    tools = {t.name: t for t in app.modules["startby"].call_tools()}
    out = tools["start_by"].run({})
    assert f"[{i}] Lab report: pendulum (due Fri 06 Nov): start working on it by Thu 05 Nov" in out and tools["start_by"].writes is False
    assert tools["set_work_size"].run({"id": i, "size": "a week"}).startswith("Lab report: pendulum: about 25 h")
    assert "couldn't read" in tools["set_work_size"].run({"id": i, "size": "soonish"})
    assert app.modules["startby"].call_brief()["time_to_start"] == [  # a week of work: from today
        "Problem set 4 (due Mon 02 Nov): start working on it today, about 3 h (an evening) of work",
        "Lab report: pendulum (due Fri 06 Nov): start working on it today, about 25 h (a week) of work",
    ]
    assert sb.press("sby:nope:3") == "That one is gone." and sb.press(f"sby:{i}:x") == "That button is out of date."


def test_health_check_and_off_by_default(env, clock):
    from kurooto.core.health import Check

    assert not env.app.is_on("startby")
    env.on("deadlines")
    assert "startby" not in [c.id for c in env.app.health.checks()]
    env.on("startby")
    c = next(c for c in env.app.health.checks() if c.id == "startby")
    assert isinstance(c, Check) and c.events == ("startby_planned",) and c.every_h == 30
    assert [j.key for j in env.app.scheduler.jobs("startby:")] == ["startby:morning"]
    env.app.disable("startby")
    assert env.app.scheduler.jobs("startby:") == []

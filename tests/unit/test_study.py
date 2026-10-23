"""Study: the deadline radar (sources merged, the six-hour call, the overdue check, ticking the box in the notes,
calendar events, recurring quizzes), the not-interested list, exam mode, and quizzes (sessions, the evening offer,
by call, check-ins)."""

from __future__ import annotations

import datetime as dt
import json

import pytest

from kurooto.core import notinterested as ni
from kurooto.core.clock import now
from kurooto.core.lock import Lock
from kurooto.core.state import jsave
from kurooto.modules import recurring
from kurooto.modules.calls import deploy
from kurooto.modules.deadlines import did, due_from, similar


def last_buttons(env):
    sent = [p for m, p in env.fake.sent if m == "sendMessage" and "reply_markup" in p]
    return [b for row in sent[-1]["reply_markup"]["inline_keyboard"] for b in row]


def calls_for(app, key):
    """The reasons of calls placed or waiting for this key (calls.place rings at once; calls.schedule waits)."""
    out = [j.payload["reason"] for j in app.scheduler.jobs(f"calls:ring:{key}")]
    f = app.paths.state / "calls" / "rings.json"
    rings = json.loads(f.read_text()) if f.exists() else {}
    return out + [r["reason"] for r in rings.values() if r.get("key") == key]


def items_by_title(env):
    return {it["title"]: (i, it) for i, it in env.app.modules["deadlines"].items().items()}


@pytest.fixture
def study(env):
    env.app.settings.set("availability.night.enabled", False)  # the tests run at the real time, maybe at night
    env.on("subjects", "deadlines")
    env.say("/subject add Linear Algebra (la, linalg)")
    env.say("/subject add Topology")
    return env


@pytest.fixture
def calls(study):
    study.app.secrets.set("gemini.api_key", "k")
    deploy.ensure_secrets(study.app)
    study.app.settings.set("calls.worker", {"url": "https://kurooto-abc.your-subdomain.workers.dev"})
    study.on("calls")
    return study


# ----------------------------------------------------------------------------------------- helpers
def test_same_thing_from_two_places():
    assert similar("Linear Algebra: Problem set 3", "Problem set 3")
    assert similar("Linear Algebra: Quiz", "LA quiz", {"linear", "algebra", "la"})
    assert not similar("Quiz 2", "Quiz 3")
    assert not similar("Essay draft", "Essay final")
    assert not similar("Lab report", "Reading response")
    assert due_from("2026-11-02", " 5:00 PM") == "2026-11-02T17:00:00"
    assert due_from("2026-11-02", "") == "2026-11-02T23:59:00"


def test_recurring_table_helpers():
    text = recurring.new_note("Kurooto", dt.date(2026, 10, 20)) + "\nMy own words after the table.\n"
    text = recurring.insert(text, recurring.line({"subject": "la", "what": "Quiz", "every": 2, "day": "thu",
                                                  "time": "10:00", "next": "2026-10-22"}))  # fmt: skip
    assert text.endswith("My own words after the table.\n")
    rows = recurring.parse(text + "| stats | Test | every other week | | 14:00 | | |\n")
    assert [(r["subject"], r["every"], r["day"]) for r in rows] == [("la", 2, "thu"), ("stats", 2, "")]
    dates = recurring.dates(rows[0], dt.date(2026, 11, 1), 30, holidays=["2026-11-19"])
    assert dates == [dt.date(2026, 11, 5)]  # every two weeks from 22 Oct; 19 Nov is a holiday
    assert recurring.dates(rows[1], dt.date(2026, 11, 1), 30) == []  # which week is unknown
    assert recurring.read_rule("there's a quiz every other thursday at 10am") == {
        "what": "Quiz",
        "every": 2,
        "day": "thu",
        "time": "10:00",
        "next": "",
    }
    assert recurring.read_rule("weekly tests on fridays at 3")["time"] == "15:00"
    assert recurring.read_rule("a quiz on thursday") is None
    assert recurring.remove(text, rows[0]["line"]).count("| la |") == 0


# ------------------------------------------------------------------------------- not interested
def test_not_interested_list(study):
    app = study.app
    study.app.modules["deadlines"].add("Drama club auditions", now() + dt.timedelta(days=2))
    study.app.modules["deadlines"].add("Problem set 3", now() + dt.timedelta(days=2))
    out = study.say("I don't care about the drama club")
    assert out.startswith("Ignoring 'drama club' from now on") and "1 hidden now" in out
    note = (app.workspace / "about-me" / "not-interested.md").read_text(encoding="utf-8")
    assert "- drama club" in note and "made_by: Kurooto" in note
    assert ni.is_ignored(app, "Drama Club auditions on Friday") == "drama club"
    assert ni.is_ignored(app, "Dramatic club") is None
    assert app.modules["deadlines"].ignored("drama club social") == "drama club"
    assert [it["title"] for _, it, _ in app.modules["deadlines"].upcoming()] == ["Problem set 3"]
    assert "already" in study.say("/ignore Drama Club")
    # your own edits count; the why after a dash is not part of the topic
    with open(app.workspace / ni.NOTE, "a", encoding="utf-8") as f:
        f.write("- photo society — not this term\n")
    assert ni.ignored_topics(app) == ["drama club", "photo society"]
    assert "photo society" in study.say("/ignored")
    assert study.say("/unignore drama club") == "'drama club' is off the list."
    assert ni.ignored_topics(app) == ["photo society"] and "not this term" in ni.note_file(app).read_text()
    assert study.say("ignore that") != "Ignoring 'that' from now on"  # too vague: not a topic


# ------------------------------------------------------------------------------- one list, merged
def test_classroom_calendar_and_notes_are_one_deadline(study):
    app, dl = study.app, study.app.modules["deadlines"]
    day = (now() + dt.timedelta(days=3)).date()
    # Classroom gives a date only; the calendar gives the exact time; a note has a box to tick
    assert dl.add("Linear Algebra: Problem set 3", dt.datetime.combine(day, dt.time(23, 59)), source="classroom")
    app.secrets.set("calendar.ics", json.dumps(["https://example.invalid/basic.ics"]))
    start = dt.datetime.combine(day, dt.time(8, 54)).astimezone()
    rows = [
        {"title": "Assignment: Problem set 3", "start": start.isoformat(),
         "end": (start + dt.timedelta(hours=1)).isoformat(), "all_day": False, "location": ""},
        {"title": "Topology midterm", "start": (start + dt.timedelta(days=1)).isoformat(),
         "end": (start + dt.timedelta(days=1, hours=2)).isoformat(), "all_day": False, "location": ""},
        {"title": "Lunch with Sam", "start": start.isoformat(), "end": start.isoformat(), "all_day": False,
         "location": ""},
    ]  # fmt: skip
    (app.paths.state / "calendar.json").write_text(json.dumps({"events": rows}), encoding="utf-8")
    study.on("calendar")
    la = app.workspace / "linear-algebra"
    la.mkdir()
    (la / "tasks.md").write_text(f"# Tasks\n\n- [ ] Problem set 3 ({day.isoformat()})\n- [ ] Read ch. 4\n", "utf-8")
    dl.refresh()
    items = items_by_title(study)
    assert set(items) == {"Linear Algebra: Problem set 3", "Topology midterm"}
    i, it = items["Linear Algebra: Problem set 3"]
    assert it["due"] == f"{day.isoformat()}T08:54:00" and it["subject"] == "linear-algebra"
    assert set(it["sources"]) == {"classroom", "calendar", "notes:linear-algebra/tasks.md"}
    assert items["Topology midterm"][1]["kind"] == "exam" and items["Topology midterm"][1]["subject"] == "topology"
    # handed in on Classroom: done, and the box in the notes is ticked
    assert dl.mark_done("Linear Algebra: Problem set 3", dt.datetime.combine(day, dt.time(23, 59)))
    text = (la / "tasks.md").read_text(encoding="utf-8")
    assert f"- [x] Problem set 3 ({day.isoformat()})" in text and "- [ ] Read ch. 4" in text
    dl.refresh()
    assert items_by_title(study)["Linear Algebra: Problem set 3"][1]["status"] == "done"
    # an event that's gone from the calendar is gone from the list
    (app.paths.state / "calendar.json").write_text(json.dumps({"events": rows[:1]}), encoding="utf-8")
    dl.refresh()
    assert items_by_title(study)["Topology midterm"][1]["status"] == "gone"


def test_done_ticks_only_that_line_and_keeps_line_endings(study):
    dl = study.app.modules["deadlines"]
    soon = now() + dt.timedelta(days=2)
    f = study.app.workspace / "todo.md"
    f.write_bytes(f"* [ ] Essay draft ({soon:%Y-%m-%d} 5:00 PM)\r\n* [ ] Other\r\n".encode())
    dl.refresh()
    i, it = items_by_title(study)["Essay draft"]
    assert it["due"].endswith("T17:00:00")
    assert study.press(f"dl:{i}:done") == "Marked done (ticked in todo.md)."
    assert f.read_bytes() == f"* [x] Essay draft ({soon:%Y-%m-%d} 5:00 PM)\r\n* [ ] Other\r\n".encode()


# ---------------------------------------------------------------------------------------- the chase
def test_six_hour_call_respects_no_call_rules(calls, monkeypatch):
    app, dl = calls.app, calls.app.modules["deadlines"]
    dl.add("Lab report", now() + dt.timedelta(hours=5))
    i, _ = items_by_title(calls)["Lab report"]
    dl._tick()
    placed = calls_for(app, f"deadlines:{i}")
    assert len(placed) == 1 and placed[0].startswith("Lab report is due")
    assert not [t for t in calls.fake.texts() if t.startswith("Due in")]  # a call, not a message
    dl._tick()
    assert len(calls_for(app, f"deadlines:{i}")) == 1  # once
    # a missed call: a message with the buttons instead
    dl.call_outcome(f"deadlines:{i}", "missed")
    assert calls.fake.texts()[-1].startswith("Missed call. Due in")
    # marking it done cancels a call that's still waiting
    assert calls.press(f"dl:{i}:done") == "Marked done."
    assert not app.scheduler.get(f"calls:ring:deadlines:{i}")
    # when no call fits before the deadline (a class until after it), a message instead
    dl.add("Problem sheet", now() + dt.timedelta(hours=4))
    late = now() + dt.timedelta(hours=5)
    monkeypatch.setattr(app.availability, "next_callable", lambda t=None, limit=24: (late, None))
    dl._tick()
    assert calls.fake.texts()[-1].startswith("Due in") and "Problem sheet" in calls.fake.texts()[-1]
    j, _ = items_by_title(calls)["Problem sheet"]
    assert calls_for(app, f"deadlines:{j}") == []


def test_six_hour_call_goes_through_calls_place_when_there_is_one(calls):
    app, dl = calls.app, calls.app.modules["deadlines"]
    placed = []
    app.modules["calls"].place = lambda reason, key="", **kw: placed.append((reason, key)) or "Calling you now."
    dl.add("Lab report", now() + dt.timedelta(hours=5))
    dl._tick()
    i, _ = items_by_title(calls)["Lab report"]
    assert placed == [(placed[0][0], f"deadlines:{i}")] and not app.scheduler.jobs("calls:ring:")
    app.modules["quiz"] if calls.app.is_on("quiz") else calls.on("quiz")
    app.modules["quiz"].call_quiz("topology")
    assert placed[-1] == ("Quiz call, about 10 minutes on Topology.", "quiz:topology")


def test_without_calls_the_urgent_nudge_is_a_message(study):
    dl = study.app.modules["deadlines"]
    dl.add("Lab report", now() + dt.timedelta(hours=5))
    dl._tick()
    assert study.fake.texts()[-1].startswith("Due in") and not study.app.scheduler.jobs("calls:ring:")


def test_overdue_check_new_date_and_drop(study):
    app, dl = study.app, study.app.modules["deadlines"]
    dl.add("Lab report", now() - dt.timedelta(hours=2))
    dl.add("Reading response", now() - dt.timedelta(hours=3))
    dl._tick()
    assert [t for t in study.fake.texts() if t.startswith("Overdue?")]
    assert [b["text"] for b in last_buttons(study)] == ["Done", "New date", "Drop", "Why?", "Less of this"]
    dl._tick()
    assert len([t for t in study.fake.texts() if t.startswith("Overdue?")]) == 2  # once each
    i, _ = items_by_title(study)["Lab report"]
    assert study.press(f"dl:{i}:date").startswith("When is it due now?")
    q = app.ask.pending(source="deadlines")[-1]
    out = app.ask.answer(q["id"], "2026-12-01 17:00", via="test")
    assert out["ok"] and out["note"].startswith("Moved: Lab report, now due Tue 01 Dec 17:00")
    it = items_by_title(study)["Lab report"][1]
    assert it["due"] == "2026-12-01T17:00:00" and it["told"] == [] and it["status"] == "open"
    j, _ = items_by_title(study)["Reading response"]
    assert study.press(f"dl:{j}:drop") == "Dropped."
    assert items_by_title(study)["Reading response"][1]["status"] == "ignored"


# ------------------------------------------------------------------------------------ recurring
def test_recurring_quiz_from_plain_english_uses_the_timetable(study):
    app, dl = study.app, study.app.modules["deadlines"]
    study.say("/class thu 10:00-10:55 la")
    out = study.say("linear algebra has a quiz every thursday")
    assert out.startswith("Linear Algebra: Quiz every week, Thu 10:00; next Thu")
    note = (app.workspace / recurring.NOTE).read_text(encoding="utf-8")
    assert "| linear-algebra | Quiz | 1 | Thu | 10:00 |" in note
    quizzes = [it for it in dl.items().values() if "recurring" in it["sources"]]
    assert len(quizzes) >= 4 and all(it["kind"] == "exam" and it["due"].endswith("T10:00:00") for it in quizzes)
    assert all(dt.date.fromisoformat(it["due"][:10]).weekday() == 3 for it in quizzes)
    assert "Linear Algebra: Quiz, every week, Thu 10:00" in study.say("/recurring")
    assert "already" in study.say("/recurring add la quiz weekly")
    assert study.say("/recurring remove la quiz") == "Removed."
    assert all(it["status"] == "gone" for it in dl.items().values() if it["due"] > now().isoformat())


def test_recurring_asks_for_the_day_and_the_week(study):
    app = study.app
    study.say("/class mon 09:00-09:55 topology")
    study.say("/class wed 14:00-14:55 topology")
    study.say("/recurring add topology quiz every 2 weeks")
    q = app.ask.pending(source="deadlines")[-1]
    assert "Which day" in q["text"] and q["choices"] == ["Mon 09:00", "Wed 14:00"]
    out = app.ask.answer(q["id"], "2", via="test")  # the second choice
    assert out["ok"] and out["note"].startswith("One question first: The Topology quiz is every 2 weeks")
    q2 = app.ask.pending(source="deadlines")[-1]
    first = recurring.first_on("wed", now().date())
    assert q2["choices"] == [f"{first:%a %d %b}", f"{first + dt.timedelta(weeks=1):%a %d %b}"]
    out = app.ask.answer(q2["id"], q2["choices"][1], via="test")
    assert out["note"].startswith("Topology: Quiz every 2 weeks, Wed 14:00")
    row = recurring.parse((app.workspace / recurring.NOTE).read_text(encoding="utf-8"))[0]
    assert row["next"] == (first + dt.timedelta(weeks=1)).isoformat() and row["day"] == "wed"
    dues = sorted(it["due"][:10] for it in app.modules["deadlines"].items().values())
    assert dues[0] == row["next"] and all(
        (dt.date.fromisoformat(d) - first).days % 14 == 7 for d in dues
    )  # every other week only


def test_a_row_you_wrote_without_a_day_is_asked_about_once(study):
    app, dl = study.app, study.app.modules["deadlines"]
    f = app.workspace / recurring.NOTE
    f.parent.mkdir(parents=True)
    text = "# My quizzes\n\n| Subject | What | Every | Day | Time | Next | Until |\n|---|---|---|---|---|---|---|\n"
    text += "| la | Quiz | 1 | | | | |\n"
    f.write_text(text, encoding="utf-8")
    dl.refresh()
    dl.refresh()
    qs = app.ask.pending(source="deadlines")
    assert len(qs) == 1 and qs[0]["choices"] == []  # no class in the timetable: an open question
    out = app.ask.answer(qs[0]["id"], "friday at 11:30", via="test")
    assert out["note"].startswith("Linear Algebra: Quiz every week, Fri 11:30")
    assert f.read_text(encoding="utf-8") == text  # your note is left as you wrote it
    assert any(it["due"].endswith("T11:30:00") for it in dl.items().values())


# -------------------------------------------------------------------------------------- exam mode
def test_exam_mode_and_briefs(study):
    app, dl = study.app, study.app.modules["deadlines"]
    assert study.say("/exam").startswith("Exam mode is off")
    dl.add("Linear Algebra midterm", now() + dt.timedelta(days=5))
    dl.add("Topology quiz", now() + dt.timedelta(days=20))
    dl.add("Essay draft", now() + dt.timedelta(hours=30))
    dl._tick()
    news = [t for t in study.fake.texts() if t.startswith("Exam mode for Linear Algebra")]
    assert len(news) == 1
    dl._tick()
    assert len([t for t in study.fake.texts() if t.startswith("Exam mode for")]) == 1  # said once
    modes = dl.exam_mode()
    assert [(e["subject"], e["name"]) for e in modes] == [("linear-algebra", "Linear Algebra")]
    assert 4.5 < modes[0]["days"] <= 5
    assert "Linear Algebra midterm" in study.say("/exam") and "Topology" not in study.say("/exam")
    assert "Linear Algebra midterm" in study.say("when's my next exam?")
    assert "Linear Algebra midterm" not in study.say("turn off exam mode")  # not this rule: the AI's
    brief = dl.call_brief()
    assert brief["exam_mode"][0].startswith("Linear Algebra: Linear Algebra midterm")
    assert [d["what"] for d in brief["due_soon"]] == ["Essay draft"]  # the 72-hour line
    soon = dl.deadlines_soon(72)
    assert soon[0]["title"] == "Essay draft" and set(soon[0]) >= {"id", "title", "subject", "due", "kind", "when"}
    assert [e["title"] for e in dl.exams_soon(30)] == ["Linear Algebra midterm", "Topology quiz"]
    app.settings.set("deadlines.exam_mode_days", 0)
    assert dl.exam_mode() == [] and "turned off" in study.say("/exam")


# ------------------------------------------------------------------------------------------- quiz
def write_prep(app, subject="linear-algebra", n=4):
    d = app.workspace / subject
    d.mkdir(exist_ok=True)
    bullets = "\n".join(f"- Fact number {k} that is worth remembering well." for k in range(n))
    (d / "exam-prep.md").write_text(f"# Prep\n## Must know\n{bullets}\n", encoding="utf-8")


def test_quiz_sessions_and_exam_mode_spacing(study):
    app = study.app
    study.on("quiz")
    app.settings.set("quiz.per_session", 2)
    write_prep(app)
    assert study.say("/quiz la") == "4 due in linear-algebra."
    for _ in range(2):
        study.reply_to_last("an answer")
        grade = [b for b in last_buttons(study) if b["text"] == "Easy"][0]["callback_data"]
        out = study.press(grade)
    assert out.endswith("That's the session. /quiz for more.")
    st = json.loads((app.paths.state / "quiz" / "linear-algebra.json").read_text())
    assert sum(1 for v in st["items"].values() if v["reps"]) == 2
    # exam mode: longer sessions, and items come back before the exam
    app.modules["deadlines"].add("Linear Algebra quiz", now() + dt.timedelta(days=4))
    quiz = app.modules["quiz"]
    assert quiz.exam_subject() == "linear-algebra" and quiz.exam_days("linear-algebra") > 3
    iid = next(k for k, v in st["items"].items() if v["reps"] == 0)
    for q in (5, 5, 5, 5):
        quiz.grade("linear-algebra", iid, q)
    item = json.loads((app.paths.state / "quiz" / "linear-algebra.json").read_text())["items"][iid]
    assert item["interval"] <= 2  # without exam mode it would be weeks
    quiz.start_session()
    assert json.loads((app.paths.state / "quiz" / "session.json").read_text())["left"] == 6
    assert quiz._tool_next({})["subject"] == "linear-algebra" and "exam_in_days" in quiz._tool_next({})


def test_quiz_offered_the_evening_before(calls):
    app = calls.app
    calls.on("quiz")
    app.settings.set("quiz.offer_at", "00:00")  # any time of day counts as "the evening" in this test
    write_prep(app)
    tomorrow = dt.datetime.combine(now().date() + dt.timedelta(days=1), dt.time(10, 0))
    app.modules["deadlines"].add("Linear Algebra quiz 2", tomorrow)
    quiz = app.modules["quiz"]
    assert quiz._offers() == 1 and quiz._offers() == 0  # once
    text = calls.fake.texts()[-1]
    assert text.startswith("Linear Algebra quiz 2 is tomorrow at 10:00. Practise? 4 questions are due.")
    labels = {b["text"]: b["callback_data"] for b in last_buttons(calls)}
    assert list(labels) == ["Quiz me now", "Call me for a quiz", "Not tonight", "Why?", "Less of this"]
    app.modules["deadlines"]._tick()
    assert not [t for t in calls.fake.texts() if t.startswith("Linear Algebra quiz 2:")]  # no second reminder
    assert calls.press(labels["Quiz me now"]) == "4 due in linear-algebra."
    assert calls.fake.texts()[-1].startswith("Quiz (linear-algebra")
    calls.press(labels["Call me for a quiz"])
    assert calls_for(app, "quiz:linear-algebra") == ["Quiz call, about 10 minutes on Linear Algebra."]
    app.modules["quiz"].call_outcome("quiz:linear-algebra", "missed")
    assert calls.fake.texts()[-1] == "Missed the quiz call. /quiz linear-algebra practises here instead."


def test_exam_reminder_without_quiz(study):
    dl = study.app.modules["deadlines"]
    dl.add("Topology midterm", now() + dt.timedelta(hours=20))
    dl._tick()
    assert [t for t in study.fake.texts() if t.startswith("Topology midterm: in 20 h")]


def test_quiz_by_call_and_quiz_check_ins(calls):
    app = calls.app
    calls.on("quiz")
    write_prep(app, "topology", 2)
    assert calls.say("/quiz topology") is not None
    assert [b["text"] for b in last_buttons(calls)] == ["Here", "By call"]
    assert calls.press("qo:s-topology:here") == "2 due in topology."
    calls.say("/quiz topology call")
    assert calls_for(app, "quiz:topology")
    out = calls.say("/quiz at 21:00 topology")
    assert out.startswith("Quiz on Topology at") and "first question" in out
    job = app.scheduler.jobs("quiz:checkin:")[0]
    assert job.payload == {"subject": "topology"} and job.respect == "quiet"
    app.modules["quiz"]._checkin(job.payload)
    assert calls.fake.texts()[-1].startswith("Quiz (topology")
    app.settings.set("quiz.by_call", True)
    out = calls.say("quiz me on topology at 9pm")
    assert out.startswith("I'll call you") and len(app.scheduler.jobs("calls:ring:quiz:topology:")) == 1


def test_quiz_me_in_plain_english(study):
    study.on("quiz")
    write_prep(study.app, "topology", 2)
    assert study.say("quiz me on topology") == "2 due in topology."
    assert study.fake.texts()[-2].startswith("Quiz (topology")


def test_exam_mode_daily_practice(calls):
    app = calls.app
    app.settings.set("quiz.exam_daily", "18:00")  # off unless you set a time
    calls.on("quiz")
    write_prep(app)
    app.modules["deadlines"].add("Linear Algebra quiz", now() + dt.timedelta(days=6))
    app.modules["quiz"]._exam_daily()
    assert calls.fake.texts()[-1].startswith("Exam mode: Linear Algebra quiz in 6 days. 4 questions to practise.")
    assert [b["text"] for b in last_buttons(calls)] == ["Quiz me now", "Call me", "Skip today", "Why?", "Less of this"]
    assert calls.press(last_buttons(calls)[2]["callback_data"]) == "Skipped for today."
    app.settings.set("quiz.by_call", True)
    app.modules["quiz"]._exam_daily()
    assert calls_for(app, "quiz:linear-algebra")
    assert "quiz:exam_daily" in [j.key for j in app.scheduler.jobs("quiz:")]


def test_ids_stay_stable():
    assert did("Lab report", "2026-11-02T23:59") == did("lab  report", "2026-11-02T17:00:00")


def test_plain_english_variants_and_older_lists(study):
    app, dl = study.app, study.app.modules["deadlines"]
    out = study.say("/recurring add la quiz thu 10:00")
    assert out.startswith("Linear Algebra: Quiz every week, Thu 10:00")
    study.say("/subject add Statistics (stats)")
    out = study.say("there's a statistics test every other friday at 2pm")
    assert out.startswith("OK. One question first: The Statistics test is every 2 weeks")
    # a list kept by 0.1.0: a ticked task is still noticed
    soon = now() + dt.timedelta(days=1)
    old = {"d0000001": {"title": "Old task", "due": f"{soon:%Y-%m-%dT%H:%M}", "source": "notes:x.md",
                        "status": "open", "kind": "task", "told": []}}  # fmt: skip
    (app.paths.state / "deadlines.json").write_text(json.dumps(old), encoding="utf-8")
    dl.refresh()
    assert dl.items()["d0000001"]["status"] == "done"
    assert "Added: essay" in study.say(f"/due {(now() + dt.timedelta(days=2)):%Y-%m-%d} essay")
    i = next(i for i, it in dl.items().items() if it["title"] == "essay")
    study.press(f"dl:{i}:ignore")
    assert study.say(f"/due {(now() + dt.timedelta(days=2)):%Y-%m-%d} essay").startswith("Already on the list")
    assert dl.items()[i]["status"] == "open"  # you added it yourself after all


# ------------------------------------------------- what a morning call got wrong (2026-10-23)
def test_a_course_page_names_its_subject_so_its_quiz_isnt_merged_into_another_subjects(study):
    import datetime as dt

    dl = study.app.modules["deadlines"]
    assert dl.subject_of("Quiz-04 (2026-10-22)", "maps/courses/topology.md") == "topology"
    day = (dt.date.today() + dt.timedelta(days=5)).isoformat()
    with Lock(study.app.paths.state, "deadlines"):
        items = dl.items()
        a, _ = dl._put(items, "Quiz", f"{day}T10:00:00", "recurring", kind="exam", subject="linear-algebra")
        b, new = dl._put(items, "Quiz-04", f"{day}T23:59:00", "notes:x", kind="exam", note="maps/courses/topology.md")
    assert new and a != b and items[b]["subject"] == "topology"


def test_a_bare_quiz_title_gets_its_subject_and_a_past_quiz_is_over_not_overdue(study):
    import datetime as dt

    dl = study.app.modules["deadlines"]
    day = (dt.date.today() + dt.timedelta(days=5)).isoformat()
    with Lock(study.app.paths.state, "deadlines"):
        items = dl.items()
        i, _ = dl._put(items, "Quiz", f"{day}T10:00:00", "recurring", kind="exam", subject="linear-algebra")
        j, _ = dl._put(
            items, "Linear Algebra: Quiz", f"{day}T10:00:00", "recurring", kind="exam", subject="linear-algebra"
        )
        past = (dt.datetime.now() - dt.timedelta(hours=3)).replace(microsecond=0).isoformat()
        k, _ = dl._put(items, "Topology quiz", past, "call", kind="exam", subject="topology")
        jsave(dl.file, items)
    assert i == j and dl.items()[i]["title"] == "Linear Algebra: Quiz"  # the fuller name from the same place wins
    assert k not in [x for x, _, _ in dl.upcoming()]  # yesterday's quiz isn't "overdue"
    assert dl.full_title({"title": "Quiz", "subject": "topology"}) == "Topology: Quiz"


def test_a_call_can_remove_a_deadline_that_isnt_happening_and_it_stays_removed(study):
    import datetime as dt

    dl = study.app.modules["deadlines"]
    due = dt.datetime.now() + dt.timedelta(days=3)
    dl.add("Topology: Quiz", due, source="recurring", kind="exam", subject="topology")
    i = next(k for k, it in dl.items().items() if it["title"] == "Topology: Quiz")
    tool = next(t for t in dl.call_tools() if t.name == "remove_deadline")
    assert "Dropped" in str(tool.run({"id": i}))
    dl.add("Topology: Quiz", due, source="recurring", kind="exam", subject="topology")  # the next scan finds it again
    assert all(it["status"] != "open" for it in dl.items().values() if it["title"] == "Topology: Quiz")
    assert {"remove_deadline", "unignore_topic"} <= {t.name for t in dl.call_tools()}


def test_add_deadline_takes_the_course_and_kind_so_a_mails_lab_report_lands_on_it(study):
    dl = study.app.modules["deadlines"]
    tool = next(t for t in dl.call_tools() if t.name == "add_deadline")
    tool.run({"title": "Lab report", "due": "2030-11-02 17:00", "subject": "topology", "kind": "task"})
    tool.run({"title": "Midterm", "due": "2030-11-03 10:00", "subject": "la", "kind": "exam"})
    got = {it["title"]: (it["subject"], it["kind"]) for it in dl.items().values()}
    assert got["Lab report"] == ("topology", "task") and got["Midterm"] == ("linear-algebra", "exam")

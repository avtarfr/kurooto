import asyncio
import datetime as dt

import pytest

from kurooto.core.clock import now
from kurooto.modules.text import a_minutes, a_time, when_from


def run_due(app, ahead=dt.timedelta(0)):
    """Run whatever the scheduler has due, as if `ahead` had passed."""
    real = app.scheduler.clock
    app.scheduler.clock = lambda: real() + ahead.total_seconds()
    try:
        return asyncio.run(app.scheduler.tick())
    finally:
        app.scheduler.clock = real


# ------------------------------------------------------------------------------------------- text
BASE = dt.datetime(2026, 10, 19, 12, 0)


@pytest.mark.parametrize(
    "text,want",
    [
        ("at 9:30", "21:30"),  # at noon, the next 9:30 is tonight
        ("till 6", "18:00"),
        ("at 8", "20:00"),
        ("at 8 tomorrow", "08:00"),
        ("9 pm", "21:00"),
        ("in 2 hours", None),
        ("for 50 min", None),
    ],
)
def test_times(text, want):
    assert a_time(text, BASE) == want


def test_durations_and_moments():
    assert a_minutes("for an hour and a half") == 90 and a_minutes("half an hour") == 30 and a_minutes("2h") == 120
    assert when_from("in 20 minutes", BASE) == BASE + dt.timedelta(minutes=20)
    assert when_from("tomorrow at 7", BASE) == dt.datetime(2026, 10, 20, 7, 0)


# -------------------------------------------------------------------------------------- reminders
def test_reminder_in_plain_english_fires_and_snoozes(env):
    env.on("reminders")
    out = env.say("remind me in 20 minutes to take the tea off")
    assert out.startswith("I'll remind you") and out.endswith("take the tea off")
    assert run_due(env.app) == []
    run_due(env.app, dt.timedelta(minutes=21))
    assert env.fake.texts()[-1] == "Reminder: take the tea off"
    buttons = [p for m, p in env.fake.sent if m == "sendMessage"][-1]["reply_markup"]["inline_keyboard"][0]
    assert env.press(buttons[0]["callback_data"]).startswith("Again at")
    assert len(env.app.scheduler.jobs("reminders:")) == 1


def test_reminder_command_and_negation(env):
    env.on("reminders")
    assert env.say("/remind tomorrow 7am gym").startswith("I'll remind you")
    env.app.settings.set("modules.enabled", env.app.settings.get("modules.enabled"))
    assert "turn on Chat" in env.say("don't remind me at 9 about anything")


# --------------------------------------------------------------------------------------- check-ins
def test_checkin_asks_and_saves_the_reply_to_the_journal(env):
    env.on("checkins")
    plan = env.app.modules["checkins"].today()
    assert plan["evening"]["status"] == "planned"
    env.app.modules["checkins"]._fire({"name": "evening", "day": now().date().isoformat()})
    assert "Evening check-in" in env.fake.texts()[-1]
    out = env.reply_to_last("Finished the lab report, skipped the gym. Tomorrow: chapter 4.")
    assert out.startswith("Saved to your journal")
    journal = (env.app.workspace / "journal" / f"{now().date().isoformat()}.md").read_text(encoding="utf-8")
    assert "chapter 4" in journal and "## Evening check-in" in journal


@pytest.mark.parametrize(
    "text,want",
    [
        ("move tonight's check-in to 9:30", "Evening check-in at 21:30."),
        ("skip the midday check-in", "No midday check-in today."),
        ("/checkin evening 23:15", "Evening check-in at 23:15."),
    ],
)
def test_checkin_moves(env, text, want):
    env.on("checkins")
    assert env.say(text) == want


def test_checkin_question_goes_to_the_ai_not_the_rules(env):
    env.on("checkins")
    assert "turn on Chat" in env.say("is the evening check-in at 9?")


# -------------------------------------------------------------------------------------- deadlines
def test_deadlines_from_notes_and_commands_nudge_once(env):
    env.on("deadlines")
    soon = now() + dt.timedelta(hours=20)
    (env.app.workspace / "tasks.md").write_text(
        f"- [ ] Lab report ({soon:%Y-%m-%d %H:%M})\n- [x] Old thing (2026-01-01)\n- [ ] Undated task\n",
        encoding="utf-8",
    )
    assert env.say(f"/due {(now() + dt.timedelta(days=5)):%Y-%m-%d} essay draft").startswith("Added: essay draft")
    env.app.modules["deadlines"]._tick()
    texts = env.fake.texts()
    assert texts[-1].startswith("Due in") and "Lab report" in texts[-1]
    env.app.modules["deadlines"]._tick()
    assert env.fake.texts() == texts  # not twice
    i = next(i for i, it in env.app.modules["deadlines"].items().items() if it["title"] == "Lab report")
    assert env.press(f"dl:{i}:done") == "Marked done (ticked in tasks.md)."
    assert "- [x] Lab report" in (env.app.workspace / "tasks.md").read_text(encoding="utf-8")
    out = env.say("what's due this week?")
    assert "essay draft" in out and "Lab report" not in out


def test_exams_are_not_done_and_add_in_plain_english(env):
    env.on("deadlines")
    out = env.say("add a deadline: midterm exam due friday 10am")
    assert out.startswith("Added: midterm exam")
    items = env.app.modules["deadlines"].items()
    assert next(iter(items.values()))["kind"] == "exam"


# -------------------------------------------------------------------------------------- subjects
def test_subjects_timetable_skip_and_no_calls_in_class(env):
    env.on("subjects")
    assert env.say("/subject add Linear Algebra (la, linalg)").startswith("Added Linear Algebra")
    day = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][now().weekday()]
    start = (now() - dt.timedelta(minutes=10)).strftime("%H:%M")
    end = (now() + dt.timedelta(minutes=50)).strftime("%H:%M")
    if start > end:
        pytest.skip("too close to midnight for a one-hour class")
    assert "added" in env.say(f"/class {day} {start}-{end} la")
    reason, until = env.app.availability.call_block(now())
    if reason != "it's night":
        assert reason == "class: Linear Algebra"
    assert env.say("skipping linear algebra today").startswith("Today you're skipping: Linear Algebra")
    assert env.app.availability.call_block(now())[0] in (None, "it's night")


# ------------------------------------------------------------------------------------------- quiz
def test_quiz_from_notes_with_self_grading(env):
    env.on("quiz")
    d = env.app.workspace / "topology"
    d.mkdir()
    (d / "exam-prep.md").write_text(
        "# Topology\n## Must know\n- A compact metric space is sequentially compact.\n"
        "- Continuous images of connected sets are connected.\n## Other\n- not this one at all\n",
        encoding="utf-8",
    )
    assert env.say("/quiz topology") == "2 due in topology."
    assert "Quiz (topology" in [t for t in env.fake.texts() if t.startswith("Quiz")][-1]
    env.reply_to_last("compact means every sequence has a convergent subsequence")
    buttons = [p for m, p in env.fake.sent if m == "sendMessage"][-1]["reply_markup"]["inline_keyboard"][0]
    assert [b["text"] for b in buttons] == ["Forgot", "Hard", "Good", "Easy"]
    assert env.press(buttons[2]["callback_data"]).startswith("Grade 4/5. Next time:")


# ------------------------------------------------------------------------------------ weekly, files
def test_weekly_counts_and_files_inbox(env):
    env.on("weekly", "files", "reminders")
    env.say("remind me in 5 minutes to stretch")
    run_due(env.app, dt.timedelta(minutes=6))
    env.fake.files["docs/F9.pdf"] = b"%PDF"
    assert env.say("", document={"file_id": "F9", "file_name": "syllabus.pdf"}).startswith("Saved to inbox/")
    out = env.say("/week")
    assert "Reminders: 1 set, 1 delivered" in out and "Messages to me:" in out


# ------------------------------------------------------------------------------- holds and routing
@pytest.mark.parametrize(
    "text,start",
    [
        ("no calls till 6", "No calls until"),
        ("don't call me for 2 hours", "No calls until"),
        ("calls are fine again", "Calls are allowed again"),
        ("focus for 45 min", "Focus until"),
        ("focus off", "Focus off."),
    ],
)
def test_plain_english_holds(env, text, start):
    assert env.say(text).startswith(start)


def test_several_requests_go_to_the_ai(env):
    env.on("reminders", "checkins")
    assert "turn on Chat" in env.say("remind me at 9 to call mum and skip the evening check-in")


def test_help_lists_only_what_is_on(env):
    env.on("reminders")
    h = env.say("/help")
    assert "/reminders" in h and "/deadlines" not in h and "Chat is off" in h

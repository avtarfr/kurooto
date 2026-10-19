"""The day's rhythm: check-ins (other days, debrief, buttons), the night and the alarm, call repeats and held calls,
#nocall and #focus events, mornings, study sessions, the Sunday review and after-class notes."""

import asyncio
import datetime as dt
import json

import pytest

from kurooto.core.clock import now
from kurooto.modules import checkins as ck_mod
from kurooto.modules import daily
from kurooto.modules import study as study_mod
from kurooto.modules.calls import deploy
from kurooto.modules.text import a_day, another_day

DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
SUBJECTS = [
    {"name": "Linear Algebra", "slug": "linear-algebra", "aliases": ["la"]},
    {"name": "Probability", "slug": "probability", "aliases": ["prob"]},
]


def run_due(app, ahead=dt.timedelta(0)):
    real = app.scheduler.clock
    app.scheduler.clock = lambda: real() + ahead.total_seconds()
    try:
        return asyncio.run(app.scheduler.tick())
    finally:
        app.scheduler.clock = real


class Jobs:
    """Stands in for the AI: records what would be asked of it."""

    def __init__(self, app, monkeypatch):
        self.prompts: list[dict] = []
        monkeypatch.setattr(daily, "ai_on", lambda a: True)

        def submit(prompt, title=None, **kw):
            self.prompts.append({"prompt": prompt, "title": title, **kw})
            return f"j{len(self.prompts)}"

        monkeypatch.setattr(app.jobs, "submit", submit)

    def titles(self):
        return [p["title"] for p in self.prompts]


@pytest.fixture
def calls(env):
    env.app.secrets.set("gemini.api_key", "k")
    deploy.ensure_secrets(env.app)
    env.app.settings.set("calls.worker", {"url": "https://kurooto-abc.your-subdomain.workers.dev"})
    env.app.settings.set("availability.night.enabled", False)
    env.on("calls")
    return env


def rings(app):
    f = app.paths.state / "calls" / "rings.json"
    return json.loads(f.read_text()) if f.exists() else {}


def add_class_now(env, minutes_ago=30, minutes_left=30):
    """A class running now (today), for Linear Algebra. None if it's too close to midnight."""
    start, end = now() - dt.timedelta(minutes=minutes_ago), now() + dt.timedelta(minutes=minutes_left)
    if start.date() != now().date() or end.date() != now().date():
        return None
    day = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][now().weekday()]
    env.app.settings.set(
        "subjects.timetable",
        [{"day": day, "start": f"{start:%H:%M}", "end": f"{end:%H:%M}", "subject": "linear-algebra"}],
    )
    return start, end


# ------------------------------------------------------------------------------------------ other days
BASE = dt.datetime(2026, 10, 19, 12, 0)  # a Monday


@pytest.mark.parametrize(
    "text,want",
    [
        ("skip the check-in", dt.date(2026, 10, 19)),
        ("skip tonight's check-in", dt.date(2026, 10, 19)),
        ("skip tomorrow's check-in", dt.date(2026, 10, 20)),
        ("skip Friday's check-in", dt.date(2026, 10, 23)),
        ("skip monday's check-in", dt.date(2026, 10, 19)),
        ("move the check-in on the day after tomorrow to 9", dt.date(2026, 10, 21)),
        ("skip yesterday's check-in", None),
        ("skip next friday's check-in", None),
        ("skip the check-in on 25 oct", None),
        ("skip friday and saturday", None),
    ],
)
def test_the_day_a_request_is_about(text, want):
    assert a_day(text, BASE) == want
    assert another_day(text, BASE) == (want != BASE.date())


def test_skipping_fridays_check_in_leaves_todays_alone(env, monkeypatch):
    env.on("checkins")
    ck = env.app.modules["checkins"]
    today = now().date()
    later = today + dt.timedelta(days=3)
    out = env.say(f"skip {DAYS[later.weekday()]}'s check-in")
    assert out == f"No evening check-in on {later:%a %d %b}."
    assert ck.today()["evening"]["status"] == "planned" and env.app.scheduler.get("checkins:evening")
    assert ck.today(later)["evening"]["status"] == "skipped"
    # that day comes: the daily plan keeps it skipped
    monkeypatch.setattr(ck_mod, "now", lambda: dt.datetime.combine(later, dt.time(0, 5)))
    ck._plan({})
    assert ck.today(later)["evening"]["status"] == "skipped"
    # tomorrow's, moved ahead of time
    monkeypatch.undo()
    tomorrow = today + dt.timedelta(days=1)
    assert env.say("move tomorrow's check-in to 21:15") == "Evening check-in tomorrow at 21:15."
    assert ck.today(tomorrow)["evening"] == {"time": "21:15", "status": "planned"}
    assert ck.today()["evening"]["time"] == "22:00"
    ev = [e for e in env.app.events.tail(50) if e["kind"] == "checkin_moved"][-1]
    assert ev["to_time"] == "21:15" and ev["day"] == tomorrow.isoformat() and ev["via"] == "intent"
    # a day it can't pin down goes to the AI
    assert "turn on Chat" in env.say("skip yesterday's check-in")


def test_other_days_for_classes_and_holds(env):
    env.app.settings.set("subjects.list", SUBJECTS)
    env.on("subjects")
    later = now().date() + dt.timedelta(days=2)
    out = env.say(f"skipping LA on {DAYS[later.weekday()]}")
    assert out.startswith(f"On {later:%a %d %b} you're skipping: Linear Algebra")
    subj = env.app.modules["subjects"]
    assert "linear-algebra" in subj.skipped(later) and not subj.skipped()
    assert "turn on Chat" in env.say("skipping LA next week")
    assert "turn on Chat" in env.say("no calls on friday till 6")
    assert env.say("no calls till 6").startswith("No calls until")


def test_checkins_list_has_buttons(env):
    env.on("checkins")
    assert env.say("/checkins") == "evening: 22:00 (planned)\nnight: 23:15 (planned)"
    buttons = [p for m, p in env.fake.sent if m == "sendMessage"][-1]["reply_markup"]["inline_keyboard"]
    assert [b["text"] for b in buttons[0]] == ["Evening +30 min", "Skip evening"]
    assert [b["text"] for b in buttons[1]] == ["Night +30 min", "Tomorrow morning", "Skip night"]
    assert env.press(buttons[0][0]["callback_data"]).startswith("Evening check-in at")
    assert env.press(buttons[0][1]["callback_data"]) == "No evening check-in today."
    env.press(buttons[1][2]["callback_data"])
    assert env.say("/checkins").endswith("(skipped)")  # nothing left to move: no buttons


# ------------------------------------------------------------------------------------ calendar tags
def test_nocall_and_focus_events(env):
    from kurooto.modules import calendar as cal_mod

    env.app.settings.set("availability.night.enabled", False)
    c = env.app.modules["calendar"]
    t0 = dt.datetime.now().astimezone().replace(microsecond=0)
    ev = lambda title, s, e, **k: {  # noqa: E731
        "title": title,
        "start": (t0 + dt.timedelta(minutes=s)).isoformat(),
        "end": (t0 + dt.timedelta(minutes=e)).isoformat(),
        "all_day": False,
        "location": "",
        **k,
    }
    rows = [ev("Lunch", -10, 20), ev("Deep work", 30, 60, focus=True), ev("Exam #nocall", 90, 120, nocall=True)]
    from kurooto.core.state import jsave

    jsave(c.file, {"events": rows, "at": t0.isoformat()})
    c.start = lambda: None  # no refresh from the network
    env.app.secrets.set(cal_mod.SECRET, json.dumps(["http://127.0.0.1:1/x.ics"]))
    env.on("calendar")
    env.app.availability.blockers["calendar:event"] = c._block
    env.app.availability.blockers["focus:calendar"] = c._focus
    av = env.app.availability
    here = lambda m: (t0 + dt.timedelta(minutes=m)).replace(tzinfo=None)  # noqa: E731
    assert av.call_block(here(0))[0] == "in Lunch"
    env.app.settings.set("calendar.nocall_events", "tagged")
    assert av.call_block(here(0)) == (None, None)
    assert av.call_block(here(100))[0] == "no-call event: Exam #nocall"
    assert av.call_block(here(40))[0] == "focus" and av.focus_until(here(40)) == here(60)
    # tags come from the title, the description, or a calendar named "no call"
    assert c._tags({"title": "Seminar", "description": "Room 4 #NoCall"}) == {"nocall": True}
    assert c._tags({"title": "x", "calendar": "My No Call blocks"}) == {"nocall": True}
    assert c._tags({"title": "Write #focus"}) == {"focus": True}
    assert c._tags({"title": "Lunch"}) == {}


def test_focus_event_end_delivers_what_waited(env, monkeypatch):
    c = env.app.modules["calendar"]
    t0 = dt.datetime.now().astimezone().replace(microsecond=0)
    rows = [
        {
            "title": "Deep work #focus",
            "start": t0.isoformat(),
            "end": (t0 + dt.timedelta(minutes=5)).isoformat(),
            "all_day": False,
            "location": "",
            "focus": True,
        }
    ]
    env.app.scheduler.action("calendar.focus_end", c._focus_end)
    c._plan_focus_ends(rows)
    assert env.app.scheduler.jobs("calendar:focus:")
    env.app.availability.blockers["focus:calendar"] = c._focus
    from kurooto.core.state import jsave

    jsave(c.file, {"events": rows})
    n = len(env.fake.texts())
    env.app.notify("A result that can wait")
    assert len(env.fake.texts()) == n  # queued during focus
    env.app.availability.blockers.pop("focus:calendar")
    run_due(env.app, dt.timedelta(minutes=6))
    assert env.fake.texts()[-1] == "A result that can wait"


# --------------------------------------------------------------------------------- night and alarm
def test_night_runs_from_bedtime_to_the_alarm(calls, monkeypatch):
    app = calls.app
    app.settings.set("availability.night", {"enabled": True, "from": "23:30", "to": "07:00"})
    calls.on("alarm")
    a = app.modules["alarm"]
    av = app.availability
    tomorrow = now().date() + dt.timedelta(days=1)
    at = dt.datetime.combine(tomorrow, dt.time(6, 0))
    app.settings.set("alarm.bedtime", "22:30")
    a.set(at, daily=True)
    t = lambda d, h, m=0: dt.datetime.combine(d, dt.time(h, m))  # noqa: E731
    assert av.night(t(now().date(), 22, 45)) == ("you're asleep (alarm set)", at)
    assert av.night(t(now().date(), 22, 0)) is None  # before bedtime (and the night's 23:30 doesn't apply)
    assert av.night(t(tomorrow, 6, 30)) is None  # up: the fixed night's 07:00 doesn't hold calls
    assert av.night(t(tomorrow, 23, 45))[0] == "it's night"  # another night: the fixed hours
    # it rang: that night still counts until it's over
    monkeypatch.setattr("kurooto.modules.alarm.now", lambda: t(tomorrow, 6, 1))
    a._ring({"tries": 0, "first": True, "late_s": 60})
    a.clear()
    assert av.night(t(tomorrow, 6, 30)) is None
    # without the alarm: the fixed hours
    calls.app.disable("alarm")
    assert av.night(t(tomorrow, 6, 30))[0] == "it's night"


def test_alarm_prep_page_and_wake_up_script(calls, monkeypatch, tmp_path):
    app = calls.app
    calls.on("alarm", "checkins")
    a = app.modules["alarm"]
    jobs = Jobs(app, monkeypatch)
    at = now() + dt.timedelta(hours=2)
    a.set(at)
    prep = app.scheduler.get("alarm:prep")
    assert prep and abs(prep.next_run - (at - dt.timedelta(minutes=20)).timestamp()) < 2
    a._prep(prep.payload)
    assert jobs.prompts[-1]["title"] == "Drafting today's plan" and jobs.prompts[-1]["quiet"]
    assert "Plan for today (draft" in jobs.prompts[-1]["prompt"]
    # a plan is already there: not drafted again
    daily.append(app, "Plan for today (draft, 06:40)", "- Top 3: finish problem set 4", at.date())
    a._prep(prep.payload)
    assert len(jobs.prompts) == 1
    # the wake-up call goes through it
    if at.date() == now().date():
        s = a.script()
        assert "problem set 4" in s and "evening check-in is at 22:00" in s
    assert any(t.name == "morning_plan" for t in app.modules["calls"].tools())
    # at the alarm, the morning page opens if there's a screen
    opened = []
    monkeypatch.setattr("webbrowser.open", lambda url: opened.append(url) or True)
    monkeypatch.setenv("DISPLAY", ":0")
    app.web_port = 18771
    a._ring({"tries": 0, "first": True})
    assert opened == ["http://127.0.0.1:18771/morning"]
    a._ring({"tries": 1, "first": False})  # a repeat ring doesn't open it again
    assert len(opened) == 1
    # snoozing doesn't draft again
    app.scheduler.cancel("alarm:prep")
    a.call_outcome("alarm:next", "later")
    assert not app.scheduler.get("alarm:prep")


def test_wake_up_call_notes(calls, monkeypatch):
    app = calls.app
    calls.on("alarm")
    a = app.modules["alarm"]
    lines = [{"who": "Kurooto", "text": "Morning!"}, {"who": "Sam", "text": "Skipping the lab, library till noon."}]
    a.call_transcript("alarm:next", lines)
    note = daily.note_path(app).read_text()
    assert "## Wake-up call" in note and "library till noon" in note and "Morning!" not in note
    jobs = Jobs(app, monkeypatch)
    a.call_transcript("alarm:next", lines)
    assert jobs.prompts[-1]["title"] == "Today's plan, from your wake-up call"


# --------------------------------------------------------------------------------- calls: repeats
def test_unanswered_call_rings_again_at_3_and_6_minutes(calls):
    app = calls.app
    c = app.modules["calls"]
    calls.on("checkins")
    first = c.ring("Evening debrief", key=f"checkins:evening:{now().date().isoformat()}")
    app.modules["checkins"].today()  # the check-in plan exists
    c._missed({"since": first})
    job = app.scheduler.get(f"calls:realert:{first}")
    assert job and abs(job.next_run - (float(rings(app)[first]["at"]) + 180)) < 2
    assert "missed call" not in " ".join(calls.fake.texts()[-1:]).lower()
    app.scheduler.cancel(job.key)  # what the scheduler does once it has run it
    c._realert(job.payload)
    second = [k for k, r in rings(app).items() if r.get("again") == 1][0]
    r2 = rings(app)[second]
    assert r2["again"] == 1 and r2["first"] == first and r2["state"] == "ringing"
    c._missed({"since": second})
    job = app.scheduler.get(f"calls:realert:{first}")
    assert job and abs(job.next_run - (float(rings(app)[first]["at"]) + 360)) < 2
    app.scheduler.cancel(job.key)
    c._realert(job.payload)
    third = [k for k, r in rings(app).items() if r.get("again") == 2][0]
    c._missed({"since": third})
    assert not app.scheduler.get(f"calls:realert:{first}")
    assert any(t.startswith("Missed call: Evening debrief") for t in calls.fake.texts()[-3:])
    ev = [e["kind"] for e in app.events.tail(80)]
    assert ev.count("call_realert") == 2 and ev.count("call_missed") == 1


def test_answering_stops_the_repeats_and_alarms_dont_repeat_here(calls):
    app = calls.app
    c = app.modules["calls"]
    first = c.ring("Stand-up")
    c._missed({"since": first})
    assert app.scheduler.get(f"calls:realert:{first}")
    c.on_event({"name": "call_started", "since": first})  # answered from the first message's link
    assert not app.scheduler.get(f"calls:realert:{first}")
    c._realert({"since": first})
    assert len(rings(app)) == 1
    alarm = c.ring("Wake-up call", alarm=True, key="alarm:next")
    c._missed({"since": alarm})
    assert not app.scheduler.get(f"calls:realert:{alarm}")
    # blocked by the time it would ring again: a missed call now
    calls.app.settings.set("calls.realert_min", [3, 6])
    third = c.ring("Later thing")
    app.availability.set_quiet(now() + dt.timedelta(hours=1))
    c._missed({"since": third})
    assert not app.scheduler.get(f"calls:realert:{third}") and "Missed call: Later thing" in calls.fake.texts()[-1]


def test_held_call_notice_and_place(calls):
    app = calls.app
    c = app.modules["calls"]
    until = now() + dt.timedelta(hours=1)
    app.availability.set_quiet(until)
    out = c.place("Deadline in 6 hours: essay", key="deadlines:7")
    assert out.startswith(f"Held a call until {until + dt.timedelta(minutes=1):%H:%M} (you asked for no calls)")
    assert "Held a call until" in calls.fake.texts()[-1] and not rings(app)
    job = app.scheduler.get("calls:ring:deadlines:7")
    assert job and job.payload["key"] == "deadlines:7" and job.respect == "none"
    # a scheduled call that comes due during a block is held again, and you're told
    c._scheduled_ring(job.payload)
    assert "Held a call until" in calls.fake.texts()[-1] and not rings(app)
    app.availability.set_quiet(None)
    c._scheduled_ring(job.payload)
    assert rings(app) and list(rings(app).values())[0]["key"] == "deadlines:7"
    assert c.place("Now please", force=True) == "Calling you now: Now please"
    assert [e for e in app.events.tail(50) if e["kind"] == "call_held"]


# ------------------------------------------------------------------------------------ the debrief
def test_evening_debrief_script(calls, monkeypatch):
    app = calls.app
    app.settings.set("subjects.list", SUBJECTS)
    calls.on("subjects", "checkins", "alarm", "study", "capture")
    if not add_class_now(calls):
        return
    ck = app.modules["checkins"]
    app.modules["study"].add("probability", 5400)
    daily.append(app, "Plan for today", "1. Problem set 4\n2. Read chapter 3")
    cap = app.modules["capture"]
    cap._ask({"subject": "linear-algebra", "name": "Linear Algebra", "day": now().date().isoformat()})
    qid = app.ask.pending(source="capture")[0]["id"]
    app.ask.answer(qid, "later")
    monkeypatch.setattr(app, "is_on", lambda m, real=app.is_on: m == "deadlines" or real(m))
    app.modules["deadlines"].exams_soon = lambda days=14: [{"title": "Quiz 3", "when": "in 4 days"}]
    s = ck.script("evening")
    assert s.startswith("Evening debrief")
    assert "Linear Algebra (" in s and "kept the after-class question for this call: Linear Algebra" in s
    assert "Problem set 4" in s and "Probability 1.5 h" in s and "Quiz 3, in 4 days" in s
    assert "set_alarm" not in s and "night check-in at 23:15" in s  # goodnight is the night call's
    assert "Midday check-in" in ck.script("midday")
    night = ck.script("night")
    assert night.startswith("Night check-in") and "set_alarm" in night and "defer_checkin" in night
    assert "never schedule_call" in night
    both = ck._tool_script({})
    assert set(both) == {"evening", "midday", "night"}
    ck.skip("night")  # no night call today: the evening one does tomorrow and the alarm
    assert "set_alarm" in ck.script("evening")
    st = app.modules["calls"].state_message()
    assert "checkin_script" in st["offline"]["brief"] and "evening" in st["brief"]["checkin_script"]
    assert "checkin_script" in st["config"]["systemInstruction"]


def test_debrief_call_becomes_journal_and_study_logs(calls, monkeypatch):
    app = calls.app
    app.settings.set("subjects.list", SUBJECTS)
    calls.on("subjects", "checkins")
    app.settings.set("checkins.by_call", True)
    has_class = add_class_now(calls)
    ck = app.modules["checkins"]
    day = now().date().isoformat()
    jobs = Jobs(app, monkeypatch)
    lines = [{"who": "Kurooto", "text": "How was linear algebra?"}, {"who": "Sam", "text": "Eigenvalues, all clear."}]
    ck.call_transcript(f"checkins:evening:{day}", lines)
    assert jobs.prompts[0]["title"] == "Journal from your evening call"
    assert "Eigenvalues, all clear." in jobs.prompts[0]["prompt"] and "How was" not in jobs.prompts[0]["prompt"]
    if has_class:
        assert jobs.prompts[1]["title"] == "Study logs from your evening call"
        assert (
            "Classes on" in jobs.prompts[1]["prompt"]
            and "Kurooto: How was linear algebra?" in jobs.prompts[1]["prompt"]
        )
    # the AI failed: your words are kept anyway
    from kurooto.providers.base import Result, Verdict

    ck._notes_done(None, Result(Verdict.ERROR, detail="x"), jobs.prompts[0]["then_payload"])
    assert "Eigenvalues, all clear." in daily.note_path(app).read_text()


def test_change_checkin_on_a_call_for_another_day(env):
    env.on("checkins")
    ck = env.app.modules["checkins"]
    later = now().date() + dt.timedelta(days=2)
    out = ck._tool_change({"name": "midday", "action": "move", "when": "13:30", "day": DAYS[later.weekday()]})
    assert out == f"Midday check-in on {later:%a %d %b} at 13:30."
    assert ck._tool_change({"name": "evening", "action": "skip", "day": "next week"}).startswith("I couldn't tell")
    assert ck._tool_change({"name": "evening", "action": "skip", "day": "tomorrow"}) == "No evening check-in tomorrow."


# ---------------------------------------------------------------------------------- study sessions
@pytest.fixture
def study(env, monkeypatch):
    env.app.settings.set("subjects.list", SUBJECTS)
    env.on("subjects", "study")
    monkeypatch.setattr(study_mod, "active_title", lambda: "linear-algebra-week3.pdf")
    monkeypatch.setattr(study_mod, "idle_seconds", lambda: 10.0)
    return env, env.app.modules["study"]


def test_paper_sessions_and_plain_english(study, monkeypatch):
    env, st = study
    out = env.say("/study la 50")
    assert out.startswith("Linear Algebra: session started for 50 min")
    assert env.app.scheduler.get("study:session-end")
    assert st.sample(30) is None  # the window doesn't count during a session away from the computer
    started = dt.datetime.fromisoformat(st.session()["start"])
    monkeypatch.setattr(study_mod, "now", lambda: started + dt.timedelta(minutes=40))
    assert env.say("done studying") == "Linear Algebra: 40 min logged."
    assert st.day(started.date())["linear-algebra|manual"] == 2400 and not st.session()
    monkeypatch.undo()
    monkeypatch.setattr(study_mod, "active_title", lambda: "x")
    assert env.say("starting probability for 25 min").startswith("Probability: session started for 25 min")
    st._session_end({})
    assert "Session done. Probability:" in env.fake.texts()[-1]
    assert env.say("studied probability for an hour") == "Logged 1.0 h of Probability."
    assert env.say("how much did I study today?").startswith("Today (")
    assert env.say("/study stop") == "No study session is running."
    assert env.say("/study basket weaving").startswith("I don't know the subject")
    assert "turn on Chat" in env.say("studied probability yesterday for an hour")
    kinds = [e["kind"] for e in env.app.events.tail(80)]
    assert "study_session_start" in kinds and "study_session_end" in kinds


def test_study_hours_go_into_the_daily_note_once(study, monkeypatch):
    env, st = study
    st.add("linear-algebra", 3600)
    st.add("probability", 1800, manual=True)
    monkeypatch.setattr(study_mod, "now", lambda: dt.datetime.combine(dt.date.today(), dt.time(23, 50)))
    assert st.write_day() is True
    note = daily.note_path(env.app).read_text()
    assert "## Study hours" in note and "Linear Algebra: 1.0 h" in note and "away from the computer 0.5 h" in note
    assert st.write_day() is False  # once a day
    assert note.count("## Study hours") == 1
    # late (the computer slept through 23:45): yesterday's goes into yesterday's note
    yesterday = dt.date.today() - dt.timedelta(days=1)
    st.add("probability", 600, day=yesterday)
    monkeypatch.setattr(study_mod, "now", lambda: dt.datetime.combine(dt.date.today(), dt.time(8, 0)))
    assert st.write_day() is True
    assert "Probability: 0.2 h" in daily.note_path(env.app, yesterday).read_text()


# ------------------------------------------------------------------------------- the Sunday review
def test_sunday_review_call(calls, monkeypatch):
    app = calls.app
    calls.on("weekly")
    app.settings.set("weekly.call", True)
    w = app.modules["weekly"]
    sunday = now().date() + dt.timedelta(days=(6 - now().weekday()) % 7)
    monkeypatch.setattr("kurooto.modules.weekly.now", lambda: dt.datetime.combine(sunday + dt.timedelta(1), dt.time(8)))
    w._sunday({})  # the computer was off all Sunday: Monday morning gets the text only
    assert not rings(app)
    monkeypatch.setattr("kurooto.modules.weekly.now", lambda: dt.datetime.combine(sunday, dt.time(19, 5)))
    w._sunday({})
    assert any(t.startswith("Your week") for t in calls.fake.texts())
    r = list(rings(app).values())
    assert r and r[0]["reason"] == "Sunday review" and r[0]["key"].startswith("weekly:review:")
    s = w.script()
    assert s.startswith("Sunday review") and "what went well" in s and "Next week" in s
    assert any(t.name == "weekly_review" for t in app.modules["calls"].tools())
    lines = [{"who": "Kurooto", "text": "What went well?"}, {"who": "Sam", "text": "Kept the morning routine."}]
    w.call_transcript(r[0]["key"], lines)
    assert "## Weekly review, by call" in daily.note_path(app).read_text()
    jobs = Jobs(app, monkeypatch)
    w.call_transcript(r[0]["key"], lines)
    assert jobs.prompts[-1]["title"] == "Weekly review from your call"


# ----------------------------------------------------------------------------- after-class notes
def test_after_class_question_files_later_and_nothing(env, monkeypatch):
    env.app.settings.set("subjects.list", SUBJECTS)
    env.on("subjects", "capture")
    app, cap = env.app, env.app.modules["capture"]
    day = now().date().isoformat()
    cap._ask({"subject": "linear-algebra", "name": "Linear Algebra", "day": day, "start": "09:00"})
    assert "How was Linear Algebra?" in env.fake.texts()[-1]
    env.fake.files["docs/B1.pdf"] = b"%PDF board"
    mid = max(int(k) for k in json.loads((env.tg.dir / "map.json").read_text()))
    out = env.say(
        "",
        caption="Eigenvectors; homework 2.1-2.4",
        document={"file_id": "B1", "file_name": "board.pdf"},
        reply_to_message={"message_id": mid},
    )
    assert out == "Saved to linear-algebra/class-log.md with 1 file(s)."
    log = (app.workspace / "linear-algebra" / "class-log.md").read_text()
    assert "homework 2.1-2.4" in log and f"[{day}-" in log and "](files/" in log
    assert list((app.workspace / "linear-algebra" / "files").glob("*board.pdf"))
    assert not list((app.workspace / "inbox").glob("*board.pdf"))  # moved next to the log, not copied
    assert cap.statuses()["linear-algebra"] == "answered"
    # Later: kept for the evening call; Nothing new: nothing written
    cap._ask({"subject": "probability", "name": "Probability", "day": day})
    q = app.ask.pending(source="capture")[0]
    app.ask.answer(q["id"], "later")
    assert cap.statuses()["probability"] == "later"
    assert app.ask.answer(q["id"], "Nothing new")["note"] == "OK, nothing new from Probability."
    assert cap.statuses()["probability"] == "nothing" and not (app.workspace / "probability").exists()
    # with Chat on, the AI writes a study log too
    jobs = Jobs(app, monkeypatch)
    cap._ask({"subject": "probability", "name": "Probability", "day": day})
    q = app.ask.pending(source="capture")[0]
    assert app.ask.answer(q["id"], "Bayes' rule")["note"].endswith("The AI is writing a study log for it.")
    assert jobs.prompts[-1]["title"] == "Study log: Probability" and "Bayes' rule" in jobs.prompts[-1]["prompt"]


def test_no_after_class_questions_in_exams_or_after_term(env):
    env.app.settings.set("subjects.list", SUBJECTS)
    env.on("subjects", "capture")
    if not add_class_now(env):
        return
    subj, cap = env.app.modules["subjects"], env.app.modules["capture"]
    today = now().date()
    assert subj.classes_on()
    assert env.say(f"/term exams {today - dt.timedelta(days=1)} to {today + dt.timedelta(days=3)}").startswith("Exams")
    assert subj.no_classes() == "exams" and subj.classes_on() == [] and subj._block(now()) is None
    n = len(env.fake.texts())
    cap._ask({"subject": "linear-algebra", "name": "Linear Algebra", "day": today.isoformat()})
    assert len(env.fake.texts()) == n
    env.say("/term clear")
    assert subj.classes_on()
    assert env.say(f"/term ends {today - dt.timedelta(days=1)}").startswith("Classes end on")
    assert subj.no_classes() == "term over" and subj.classes_on() == []
    assert env.say("/term").startswith("Last day of classes:")
    kinds = [e for e in env.app.events.tail(50) if e["kind"] == "capture_skipped"]
    assert kinds and kinds[-1]["why"] == "exams"


# -------------------------------------------------------------------------------- the morning page
def test_morning_page(tmp_path, monkeypatch):
    from kurooto.app import App
    from kurooto.web.server import start
    from tests.unit.test_web import call

    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    app = App()
    srv = start(app, port=18790)
    try:
        app.settings.set("subjects.list", SUBJECTS)
        app.enable("subjects")
        daily.append(app, "Plan for today (draft, 06:40)", "- Problem set 4")
        code, page = call(srv, "/morning", token=False)
        assert code == 200 and srv.token in page and "/static/morning.js" in page
        assert call(srv, "/static/morning.js", token=False)[0] == 200
        assert call(srv, "/api/morning", token=False)[0] == 401
        code, d = call(srv, "/api/morning")
        assert code == 200 and "Problem set 4" in d["plan"] and d["note"] == f"journal/{now().date().isoformat()}"
    finally:
        srv.stop()
        app.close()


def test_call_me_now(calls):
    assert calls.say("call me now") == "Calling you now: you asked me to call"
    assert calls.say("ring me about the essay") == "Calling you now: the essay"
    app = calls.app
    assert len(rings(app)) == 2
    assert "Calling you now" not in (calls.say("call me for a quiz") or "")  # the quiz's (or the AI's), not this
    assert calls.say("call me in 20 minutes about tea").startswith("I'll call you")


def test_evening_times_said_in_the_morning_mean_evening(env, monkeypatch):
    from kurooto.modules import text as text_mod

    env.on("checkins")
    monkeypatch.setattr(text_mod, "now", lambda: dt.datetime.combine(now().date(), dt.time(8, 0)))
    later = now().date() + dt.timedelta(days=2)
    assert (
        env.say(f"move {DAYS[later.weekday()]}'s check-in to 9:30") == f"Evening check-in on {later:%a %d %b} at 21:30."
    )


# ------------------------------------------------------------------------- night check-in, deferral
def buttons_of_last(env):
    sent = [p for m, p in env.fake.sent if m == "sendMessage"][-1]
    return [b["text"] for row in sent.get("reply_markup", {}).get("inline_keyboard", []) for b in row], sent


@pytest.fixture
def bycall(calls):
    calls.app.settings.set("subjects.list", SUBJECTS)
    calls.on("subjects", "capture", "checkins")
    calls.app.settings.set("checkins.by_call", True)
    return calls, calls.app.modules["checkins"], now().date()


def test_night_check_in_is_its_own_goodnight(env, monkeypatch):
    env.app.settings.set("subjects.list", SUBJECTS)
    env.on("subjects", "capture", "checkins")
    ck, day = env.app.modules["checkins"], now().date()
    assert ck.today()["night"] == {"time": "23:15", "status": "planned"}
    ck._fire({"name": "night", "day": day.isoformat()})
    texts, _ = buttons_of_last(env)
    assert "Night check-in:" in env.fake.texts()[-1] and texts == ["In 30 min", "Tomorrow morning", "Skip today"]
    has_class = add_class_now(env)
    jobs = Jobs(env.app, monkeypatch)
    lines = [{"who": "Kurooto", "text": "What did LA cover?"}, {"who": "Sam", "text": "Eigenvalues. Tired now."}]
    ck.call_transcript(f"checkins:night:{day}", lines)
    assert jobs.titles()[0] == "Journal from your night call"
    if has_class:  # the class's study log was still due: the night call logs it, and it's done after that
        assert jobs.titles()[1] == "Study logs from your night call" and "Linear Algebra" in jobs.prompts[1]["prompt"]
        assert ck.logs_due(day) == []


def test_tomorrow_morning_goes_to_the_wake_up_call(bycall, monkeypatch):
    env, ck, day = bycall
    env.on("alarm")
    alarm = env.app.modules["alarm"]
    alarm.set(now() + dt.timedelta(hours=8))
    ck._call("night", day)
    texts, _ = buttons_of_last(env)
    assert texts == ["Answer", "Tomorrow morning", "Skip"]  # on the ring's Telegram message
    data = f"chk:night|{day.isoformat()}:defer"
    assert env.press(data).startswith("OK, sleep well. The rest of it comes on your wake-up call")
    assert ck.today()["night"]["status"] == "deferred" and not env.app.scheduler.get("checkins:unstick:night")
    s = alarm.script()
    assert "Last night's night check-in was moved to this call" in s.split("\n")[1]
    # the night call's own transcript (said before deferring) waits for the morning
    jobs = Jobs(env.app, monkeypatch)
    ck.call_transcript(f"checkins:night:{day}", [{"who": "Sam", "text": "too tired"}])
    assert jobs.prompts == []
    lines = [{"who": "Kurooto", "text": "Anything for yesterday?"}, {"who": "Sam", "text": "Finished the essay."}]
    alarm.call_transcript("alarm:next", lines)
    assert (
        jobs.titles()[0] == "Journal from your night call" and f"About {day.isoformat()}" in jobs.prompts[0]["prompt"]
    )
    assert jobs.titles()[-1] == "Today's plan, from your wake-up call"
    assert ck.deferred() is None and ck.today(day)["night"]["status"] == "answered"
    assert "Last night's" not in alarm.script()


def test_too_tired_on_the_call_and_no_alarm(bycall):
    env, ck, day = bycall
    out = env.app.modules["calls"].run_tool("defer_checkin", {})
    assert out.startswith("OK, sleep well. I'll ask you the rest tomorrow morning")
    job = env.app.scheduler.get("checkins:deferred")
    assert job and dt.datetime.fromtimestamp(job.next_run).date() == day + dt.timedelta(days=1)
    ck._deferred_message(job.payload)
    assert "Last night's check-in, as promised" in env.fake.texts()[-1]
    assert env.reply_to_last("Read two papers.").startswith("Saved to your journal")
    assert "Read two papers." in daily.note_path(env.app, day).read_text()
    assert ck.deferred() is None


def test_schedule_call_during_a_check_in_keeps_it_a_check_in(bycall):
    env, ck, day = bycall
    app, c = env.app, env.app.modules["calls"]
    ck._call("evening", day)
    since = next(k for k, r in rings(app).items() if r["key"] == f"checkins:evening:{day}")
    c.on_event({"name": "call_started", "since": since})
    later = now() + dt.timedelta(minutes=45)
    if later.date() != day:
        return  # too close to midnight for this one
    out = c.run_tool("schedule_call", {"when": "in 45 minutes", "reason": "call back to finish this"})
    assert out == f"Evening check-in at {later:%H:%M}."
    assert not app.scheduler.jobs("calls:ring:")  # no bare call without the check-in's steps
    assert ck.today()["evening"] == {"time": f"{later:%H:%M}", "status": "planned"}
    assert len(app.scheduler.jobs("checkins:evening")) == 1
    # a new topic is a new call
    assert c.run_tool("schedule_call", {"when": "tomorrow 9:00", "reason": "dentist appointment"}).startswith(
        "I'll call you"
    )
    assert len(app.scheduler.jobs("calls:ring:")) == 1
    # unattended AI requests never count as "this call"
    tool = next(t for t in c.agent_tools() if t.name == "schedule_call")
    tool.run({"when": "in 2 hours", "reason": "check-in"})
    assert len(app.scheduler.jobs("calls:ring:")) == 2
    # when the call ends, there's no "this call" any more
    c.handle_request("POST", "/transcript", json.dumps({"since": since, "lines": []}).encode())
    assert c.live_call() is None
    # a check-in held twice is one booking
    app.availability.set_quiet(now() + dt.timedelta(minutes=20))
    ck._held("evening", day.isoformat())
    ck._held("evening", day.isoformat())
    assert len(app.scheduler.jobs("checkins:evening")) == 1
    c.place("Water the plants")
    c.place("Water the plants")
    assert len([j for j in app.scheduler.jobs("calls:ring:held-")]) == 1


def test_other_live_calls_keep_their_purpose(calls):
    app, c = calls.app, calls.app.modules["calls"]
    since = c.ring("Deadline in 6 hours: essay", key="deadlines:7")
    c.on_event({"name": "call_started", "since": since})
    c.run_tool("schedule_call", {"when": "in 30 minutes", "reason": "call back later"})
    job = app.scheduler.jobs("calls:ring:")[0]
    assert job.payload["key"] == "deadlines:7" and job.payload["reason"] == "Deadline in 6 hours: essay"


def test_unanswered_or_declined_check_in_calls_fall_back(bycall):
    env, ck, day = bycall
    key = f"checkins:evening:{day}"
    ck._call("evening", day)
    assert ck.today()["evening"]["status"] == "calling" and env.app.scheduler.get("checkins:unstick:evening")
    assert ck.call_outcome(key, "decline") is True
    texts, sent = buttons_of_last(env)
    assert texts == ["Call me now", "Tomorrow morning", "Skip"] and "(declined)" in sent["text"]
    assert ck.today()["evening"]["status"] == "asked" and not env.app.scheduler.get("checkins:unstick:evening")
    assert env.press(f"chk:evening|{day}:now") == "Calling you now."
    assert ck.today()["evening"]["status"] == "calling"
    # nothing came back at all: it doesn't stay "calling"
    ck._unstick({"name": "evening", "day": day.isoformat()})
    assert ck.today()["evening"]["status"] == "asked" and "(no answer)" in env.fake.texts()[-1]
    # "Later" on the ringing phone: the same check-in, half an hour on, not a bare call
    ck._call("evening", day)
    if (now() + dt.timedelta(minutes=31)).date() == day:
        assert ck.call_outcome(key, "later") is True
        assert ck.today()["evening"]["status"] == "planned" and not env.app.scheduler.jobs("calls:ring:")
    # missed after the repeats: the same message
    ck._call("evening", day)
    ck.call_outcome(key, "missed")
    assert "(missed call)" in env.fake.texts()[-1] and ck.today()["evening"]["status"] == "asked"


def test_call_me_back_on_the_wake_up_call_is_the_alarm_again(calls):
    calls.on("alarm")
    app, c = calls.app, calls.app.modules["calls"]
    since = c.ring("Wake-up call", alarm=True, key="alarm:next")
    c.on_event({"name": "call_started", "since": since})
    out = c.run_tool("schedule_call", {"when": "in 10 minutes", "reason": "wake me again"})
    assert out.startswith("Alarm set for") and not app.scheduler.jobs("calls:ring:")
    assert app.scheduler.get("alarm:ring").payload["first"] is False

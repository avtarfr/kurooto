"""0.9.1 (A): the fixes for a wake-up call's mistakes. A skip on a call can be undone (attend_class); the deferred
check-in's journal takes only its own part of the call; questions about an earlier day name it; a capture answer
that says they didn't go marks the class missed with no study log; done deadlines never reach the morning's plan; the
same open question isn't raised twice in one call."""

from __future__ import annotations

import datetime as dt

import pytest

from kurooto.core.clock import now
from kurooto.modules import capture as capture_mod
from kurooto.modules import checkins as ck_mod
from kurooto.modules import daily
from kurooto.modules.calls import deploy

SUBJECTS = [
    {"name": "Linear Algebra", "slug": "linear-algebra", "aliases": ["la"]},
    {"name": "Organic Chemistry", "slug": "organic-chemistry", "aliases": ["oc"]},
]
WD = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


class Jobs:
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


def classes_today(app):
    day = WD[now().weekday()]
    app.settings.set("subjects.list", SUBJECTS)
    app.settings.set(
        "subjects.timetable",
        [
            {"day": day, "start": "09:00", "end": "09:55", "subject": "linear-algebra"},
            {"day": day, "start": "12:00", "end": "12:55", "subject": "organic-chemistry"},
        ],
    )


# ------------------------------------------------------------------------------------------- F1
def test_attend_class_undoes_a_skip_on_a_call(calls):
    app = calls.app
    calls.on("subjects")
    classes_today(app)
    c = app.modules["calls"]
    assert c.run_tool("skip_class", {"subjects": ["Linear Algebra", "oc"]}).startswith(
        "Skipping Linear Algebra, Organic Chemistry today."
    )
    out = c.run_tool("attend_class", {"subject": "Organic Chemistry"})
    assert out.startswith("Not skipping Organic Chemistry today after all.")
    assert "Changed since this call's brief" in out  # a reshaping tool, like skip_class
    assert app.modules["subjects"].skipped() == {"linear-algebra"}
    assert c.run_tool("attend_class", {"subject": "oc"}) == "No change: Organic Chemistry wasn't skipped today."
    assert c.run_tool("attend_class", {"subjects": ["all"]}).startswith("Not skipping Linear Algebra")
    assert app.modules["subjects"].skipped() == set()
    assert c.run_tool("attend_class", {"subjects": ["all"]}) == "No class is skipped today."
    assert c.run_tool("attend_class", {"subject": "astronomy"}) == "I don't know that subject."
    si = c.config_template()["systemInstruction"]
    assert "attend_class" in si and "today's class" in si and "Say back the classes" in si
    tool = next(t for t in c.tools() if t.name == "attend_class")
    assert tool.offline == "queue"


# ------------------------------------------------------------------------------------------- F2, F3
WAKE = [
    {"who": "Kurooto", "text": "Good morning! Anything for the journal of Wednesday?"},
    {"who": "Sam", "text": "Long day, finished the essay draft."},
    {"who": "Kurooto", "text": "Nice. Now today: which classes are you skipping?"},
    {"who": "Sam", "text": "I'm skipping organic chemistry."},
]


def test_journal_answer_takes_only_the_answer_to_the_journal_question(env):
    assert ck_mod.journal_answer(env.app, WAKE) == "Long day, finished the essay draft."
    assert ck_mod.journal_answer(env.app, WAKE[2:]) == ""


def deferred(calls, day):
    calls.app.settings.set("subjects.list", SUBJECTS)
    calls.on("subjects", "capture", "checkins", "alarm")
    ck = calls.app.modules["checkins"]
    ck._status("night", day, "deferred")
    ck_mod.jsave(ck.deferred_file, {"day": day.isoformat(), "name": "night", "classes": [], "at": now().isoformat()})
    return ck


def test_the_deferred_journal_gets_the_transcript_and_only_its_part(calls, monkeypatch):
    day = now().date() - dt.timedelta(days=1)
    ck = deferred(calls, day)
    jobs = Jobs(calls.app, monkeypatch)
    calls.app.modules["alarm"].call_transcript("alarm:next", WAKE)
    journal = jobs.prompts[0]["prompt"]
    assert jobs.titles()[0] == "Journal from your night call"
    assert f"About {day.isoformat()} ({day:%A})" in journal
    assert f"Only my answer to the journal question and what I said about {day:%A}'s classes" in journal
    assert "leave out the planning of the new day" in journal and "I'm skipping organic chemistry." in journal
    assert ck.deferred() is None


def test_the_deferred_journal_without_ai_keeps_only_the_journal_answer(calls):
    day = now().date() - dt.timedelta(days=1)
    deferred(calls, day)
    calls.app.settings.set("alarm.notes", False)
    calls.app.modules["alarm"].call_transcript("alarm:next", WAKE)
    text = daily.note_path(calls.app, day).read_text()
    assert "Long day, finished the essay draft." in text and "organic chemistry" not in text


def test_the_deferred_steps_name_the_day_and_ask_an_open_class_question_once(calls):
    day = now().date() - dt.timedelta(days=1)
    ck = deferred(calls, day)
    ck_mod.jsave(
        ck.deferred_file,
        {"day": day.isoformat(), "name": "night", "classes": ["Linear Algebra", "Organic Chemistry"],
         "at": now().isoformat()},
    )  # fmt: skip
    calls.app.ask.ask(
        "How was Organic Chemistry?",
        source="capture",
        hook="capture.answer",
        hook_payload={"subject": "organic-chemistry", "name": "Organic Chemistry", "day": day.isoformat()},
    )
    s = ck.deferred_steps()
    assert f"Then what {day:%A}'s Linear Algebra covered" in s
    assert f"open_questions for Organic Chemistry are {day:%A}'s: ask each once" in s
    assert "Organic Chemistry covered" not in s and f"These are about {day:%A}, not today" in s


def test_a_question_from_an_earlier_day_says_which_on_a_call(env, monkeypatch):
    qid = env.app.ask.ask("How was Linear Algebra?", source="capture")
    q = env.app.ask.get(qid)
    assert "asked_on" not in env.app.ask.call_brief()["open_questions"][0]
    yesterday = now() - dt.timedelta(days=1)
    q["created"] = yesterday.isoformat()
    env.app.ask._save(q)
    row = env.app.ask.call_brief()["open_questions"][0]
    assert row["asked_on"] == f"{yesterday:%A} (yesterday)"
    hint = next(t for t in env.app.ask.call_tools() if t.name == "answer_question").hint
    assert "asked_on" in hint and "don't ask it again" in hint


# ------------------------------------------------------------------------------------------- F4
@pytest.mark.parametrize(
    "said,missed",
    [
        ("I did not attend lab", True),
        ("skipped it", True),
        ("Didn't go today", True),
        ("I wasn't there", True),
        ("missed the class", True),
        ("We covered eigenvalues; the prof skipped chapter 3.", False),
        ("Nothing much, a quiz next week", False),
        ("Skipped.", True),
        ("I skipped chapter 3 while revising", False),
    ],
)
def test_not_there_reads_an_answer_that_says_they_didnt_go(said, missed):
    assert capture_mod.not_there(said) is missed


def test_a_capture_answer_saying_they_didnt_go_marks_the_class_missed(env, monkeypatch):
    app = env.app
    app.settings.set("subjects.list", SUBJECTS)
    env.on("subjects", "capture")
    jobs = Jobs(app, monkeypatch)
    day = now().date().isoformat()
    qid = app.ask.ask(
        "How was Organic Chemistry?",
        source="capture",
        hook="capture.answer",
        hook_payload={"subject": "organic-chemistry", "name": "Organic Chemistry", "day": day},
    )
    out = app.ask.answer(qid, "I did not attend lab", "call")
    assert out["note"] == "OK, marked Organic Chemistry as missed today; no study log for it."
    assert app.modules["subjects"].skipped() == {"organic-chemistry"}
    assert app.modules["capture"].statuses()["organic-chemistry"] == "skipped"
    assert jobs.prompts == []  # no study-log job
    from kurooto.core import layout

    assert not layout.path(app, "class_log", subject="organic-chemistry").exists()


# ------------------------------------------------------------------------------------------- F5
def test_done_deadlines_never_reach_the_morning_plan(calls, monkeypatch):
    app = calls.app
    calls.on("deadlines", "alarm")
    dl = app.modules["deadlines"]
    due = now() + dt.timedelta(hours=2)
    dl.add("Problem set 4", due, source="manual")
    dl.add("Lab report", due + dt.timedelta(days=1), source="manual")
    items = dl.items()
    j = next(k for k, it in items.items() if it["title"] == "Problem set 4")
    dl._status(j, "done")
    alarm = app.modules["alarm"]
    assert alarm.done_lately() == ["Problem set 4"]
    s = alarm.script()
    assert "Already done, so never a to-do now (even if the plan above lists it): Problem set 4." in s
    jobs = Jobs(app, monkeypatch)
    alarm._prep({"day": now().date().isoformat(), "at": "07:30"})
    assert (
        "Already done (leave these out of the plan" in jobs.prompts[0]["prompt"]
        and "Problem set 4" in jobs.prompts[0]["prompt"]
    )


# ------------------------------------------------------------------------------------------- F6
def test_an_open_question_listed_again_in_the_same_call_is_marked_raised(calls):
    app, c = calls.app, calls.app.modules["calls"]
    app.ask.ask("How was Linear Algebra?", source="capture")
    first = c.run_tool("pending_items", {}, since="s1")
    assert "raised_this_call" not in first["open_questions"][0]
    again = c.run_tool("pending_items", {}, since="s1")
    assert again["open_questions"][0]["raised_this_call"] is True
    other = c.run_tool("pending_items", {}, since="s2")  # another call starts fresh
    assert "raised_this_call" not in other["open_questions"][0]
    assert "Ask each question once a call" in c.config_template()["systemInstruction"]

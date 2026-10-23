"""Setting up from what you say (core/infer.py): a project with its supervisor, its meetings, a class in the timetable;
one line each with Undo; nothing from other people's news, a "didn't", or a line seen before."""

import datetime as dt

from kurooto.core import infer
from kurooto.modules import research


def setup(env):
    env.app.settings.set("availability.night.enabled", False)
    env.on("subjects", "deadlines")
    env.say("/subject add Linear Algebra (la)")
    return env.app


def test_a_project_under_a_professor_becomes_a_project_note_with_them(env):
    app = setup(env)
    told = infer.observe(app, "Big news: I got a project under Prof Lena Ortiz on glacier flow.", via="journal")
    assert told and "Glacier flow" in told[0] and "Prof Lena Ortiz" in told[0]
    note = research.project_note(app, "Glacier flow")
    text = note.read_text()
    assert "With: Prof Lena Ortiz (supervisor)" in text and "## Meetings" in text
    assert "Undo" in str(env.fake.sent[-1])  # the line came with its Undo button
    # said again (a check-in answer reaches the chat and the journal): nothing twice
    assert infer.observe(app, "Big news: I got a project under Prof Lena Ortiz on glacier flow.") == []
    assert infer.projects_with(app) == [(note, "Prof Lena Ortiz", "supervisor")]


def test_other_peoples_news_and_negations_set_nothing_up(env):
    app = setup(env)
    for line in (
        "My friend got a project under Prof Okafor.",
        "I didn't get the project under Prof Okafor, sadly.",
        "Maybe I'll ask if I can do a project with Dr Okafor",
    ):
        assert infer.observe(app, line) == [], line
    assert infer.projects_with(app) == []


def test_meetings_with_a_project_person_are_logged_and_one_ahead_becomes_a_deadline(env):
    app = setup(env)
    infer.observe(app, "I've started a project with Dr Sam Okafor.")
    ((note, who, _),) = infer.projects_with(app)
    assert who == "Dr Sam Okafor" and "Project with Dr Sam Okafor" in note.read_text()
    told = infer.observe(app, "Met Okafor today and we agreed on the forcing experiments.")
    assert told and "Logged a meeting" in told[0]
    assert (
        f"- {dt.date.today():%Y-%m-%d}: Met Okafor today and we agreed on the forcing experiments." in note.read_text()
    )
    assert f"With: Dr Sam Okafor (supervisor)\nLast met: {dt.date.today():%Y-%m-%d}\n" in note.read_text()
    meet = infer._load(app)["items"][-1]
    infer.undo(app, meet["id"])
    assert "Last met" not in note.read_text() and "forcing experiments" not in note.read_text()
    told = infer.observe(app, "I have a meeting with Okafor tomorrow at 4pm.")
    assert told and "Meeting: Dr Sam Okafor" in told[0]
    assert any(d["title"] == "Meeting: Dr Sam Okafor" for d in app.modules["deadlines"].items().values())


def test_a_weekly_class_said_in_passing_joins_the_timetable(env):
    app = setup(env)
    told = infer.observe(app, "Also every Monday at 9 I have a linear algebra lab, ugh.")
    assert told == ["Added Linear Algebra lab on Mon 09:00–09:55 to your timetable."]
    assert {"day": "mon", "start": "09:00", "end": "09:55", "subject": "linear-algebra"} in (
        app.settings.get("subjects.timetable") or []
    )
    assert infer.observe(app, "I have an LA tutorial every wed at 2 to 3") == [
        "Added Linear Algebra tutorial on Wed 14:00–15:00 to your timetable."
    ]
    assert infer.observe(app, "every friday at 10 I have a knitting class") == []  # not one of your subjects


def test_undo_and_the_list(env):
    app = setup(env)
    infer.observe(app, "I got a project under Prof Lena Ortiz on glacier flow.")
    infer.observe(app, "every Monday at 9 I have a linear algebra lab")
    out = env.say("/inferred")
    assert "Set up from what you said:" in out and "Glacier flow" in out and "timetable" in out
    items = infer._load(app)["items"]
    assert env.app.callback(f"inf:{items[1]['id']}:undo").startswith("Undone: Added Linear Algebra lab")
    assert not app.settings.get("subjects.timetable")
    assert infer.undo(app, items[0]["id"]).startswith("Undone: Started the project note")
    assert not research.project_note(app, "Glacier flow").exists()  # made by it and untouched since: gone
    assert infer.undo(app, items[0]["id"]) == "Undone already."
    app.settings.set("infer.on", False)
    assert infer.observe(app, "I got a project under Prof Okafor on assimilation.") == []


def test_chat_and_journal_lines_both_go_through_it(env):
    app = setup(env)
    env.say("every Monday at 9 I have a linear algebra lab")
    assert app.settings.get("subjects.timetable")
    from kurooto.modules import daily

    daily.append(app, "Journal 21:00", "I got a project under Prof Lena Ortiz on glacier flow.")
    assert research.project_note(app, "Glacier flow").exists()


def test_a_short_name_said_in_passing_becomes_the_subjects(env):
    app = setup(env)
    env.say("/subject add Physics of the Atmosphere")
    env.say("/subject add Stochastic Calculus")
    subj = app.modules["subjects"]
    told = infer.observe(app, "By POTA I mean Physics of the Atmosphere, obviously.")
    assert told == ['Took "POTA" as Physics of the Atmosphere from now on.']
    assert subj.resolve("pota") == "physics-of-the-atmosphere"
    assert infer.observe(app, "I call stochastic calculus stoch") == [
        'Took "stoch" as Stochastic Calculus from now on.'
    ]
    assert subj.find_in("stoch quiz on friday") == ["stochastic-calculus"]
    for line in (
        "this means war with Physics of the Atmosphere",  # a word, not a name
        "LA stands for linear algebra",  # taken already
        "QFT is short for quantum field theory",  # not one of your subjects
    ):
        assert infer.observe(app, line) == [], line
    items = infer._load(app)["items"]
    assert infer.undo(app, items[0]["id"]).startswith('Undone: Took "POTA"')
    assert subj.resolve("pota") is None and subj.resolve("stoch") == "stochastic-calculus"


def test_the_evening_before_a_meeting_a_brief_from_the_project(env):
    app = setup(env)
    infer.observe(app, "I got a project under Prof Lena Ortiz on glacier flow.")
    note = research.project_note(app, "Glacier flow")
    infer.observe(app, "Met Ortiz today, we chose the forcing runs.")
    today = dt.date.today()
    text = note.read_text().replace(f"Last met: {today:%Y-%m-%d}", f"Last met: {today - dt.timedelta(days=5):%Y-%m-%d}")
    text += (
        f"- **{today - dt.timedelta(days=9):%Y-%m-%d}** | git:flow — old work\n"
        f"- **{today - dt.timedelta(days=2):%Y-%m-%d}** | git:flow — 3: ran the forcing sweep\n"
        "\n## Next steps\n- [ ] write up the sweep\n- [x] done already\n"
    )
    note.write_text(text)
    due = dt.datetime.combine(today + dt.timedelta(days=1), dt.time(16))
    app.modules["deadlines"].add("Meeting: Prof Lena Ortiz", due)
    (brief,) = app.modules["deadlines"].meeting_briefs()
    assert brief.startswith("Tomorrow at 16:00: meeting with Prof Lena Ortiz (Glacier flow).")
    assert "ran the forcing sweep" in brief and "old work" not in brief
    assert "Open next steps:\n- write up the sweep" in brief and "done already" not in brief
    assert "Last time: " in brief and "forcing runs" in brief
    assert app.modules["deadlines"].meeting_briefs() == []  # once


def test_a_recurring_fact_becomes_a_class_a_quiz_or_a_routine(env):
    app = setup(env)
    # a lab with no course named: a routine (it holds calls like a class), said so
    told = infer.observe(app, "Ugh, I have lab every Thursday 2-5.")
    assert told and told[0].startswith("Added lab to your commitments: Thu 14:00–17:00")
    assert "/class thu 14:00-17:00 <course> makes it a class" in told[0]
    # a quiz on one of your subjects, said in passing: a row in the recurring quizzes table
    told = infer.observe(app, "Also there's a quiz on Linear Algebra every Monday at 10, which is fun.")
    assert told and told[0].startswith("Added to your recurring quizzes (kurooto/recurring.md): Linear Algebra: Quiz")
    rows = app.modules["deadlines"].recurring_rows()
    assert [(r["slug"], r["what"], r["day"], r["time"]) for r in rows] == [("linear-algebra", "Quiz", "mon", "10:00")]
    # a terse one: two days and a clock time
    assert infer.observe(app, "gym Tue Thu 7am") == [
        "Added gym to your commitments: Tue, Thu 07:00–08:00; calls wait while it's on."
    ]
    assert infer.observe(app, "swimming on saturdays 8am-9:30am") == [
        "Added swimming to your commitments: Sat 08:00–09:30; calls wait while it's on."
    ]
    assert infer.observe(app, "standup every weekday 10:00")[0].endswith(
        "weekdays 10:00–11:00; calls wait while it's on."
    )
    # not sure enough: one day (a one-off), a request, a course with no day, every other week with no date
    for line in (
        "dentist Tue 7am",
        "call mum Tue Thu 7pm",
        "there's a quiz on Linear Algebra every week",
        "LA has a test every other Friday at 2",
    ):
        assert infer.observe(app, line) == [], line
    items = infer._load(app)["items"]
    assert infer.undo(app, items[1]["id"]).startswith("Undone: Added to your recurring quizzes")
    assert app.modules["deadlines"].recurring_rows() == []
    assert infer.undo(app, items[0]["id"]).startswith("Undone: Added lab")
    assert [r["name"] for r in app.modules["commitments"].items()] == ["gym", "swimming", "standup"]


def test_questions_set_up_nothing(env):
    app = setup(env)
    for line in (
        "Do I have lab every Thursday 2-5",
        "is there a quiz on Linear Algebra every Monday",
        "every Monday at 9 I have a linear algebra lab?",
        "do I go to the gym every Tuesday at 7pm",
        "When did I meet Ortiz",
    ):
        assert infer.observe(app, line) == [], line
    assert not app.settings.get("subjects.timetable") and not app.modules["commitments"].items()
    assert app.modules["deadlines"].recurring_rows() == []


def test_a_quiz_request_on_its_own_is_the_requests_not_set_up_twice(env):
    app = setup(env)
    out = env.say("la has a quiz every thursday at 10")
    assert out.startswith("Linear Algebra: Quiz every week, Thu 10:00")
    assert len(app.modules["deadlines"].recurring_rows()) == 1
    assert not [x for x in infer._load(app)["items"] if x["kind"] == "quiz"]


def test_a_short_name_used_twice_for_the_one_course_it_fits_becomes_its_short_name(env):
    app = setup(env)
    env.say("/subject add Stochastic Calculus")
    env.say("/subject add Real Analysis II")
    env.say("/subject add Statistical Computing")
    subj = app.modules["subjects"]
    assert infer.observe(app, "Finished the SC reading and half the RA problem set.") == []  # once each
    assert infer.observe(app, "Started the RA problem set again, RA is hard.") == [  # twice: RA (once per message)
        'Took "RA" as Real Analysis II from now on (you\'ve called it that twice).'
    ]
    assert subj.resolve("ra") == "real-analysis-ii"
    # "SC" fits Stochastic Calculus and Statistical Computing: never learned, however often
    assert infer.observe(app, "SC homework tonight.") == [] and infer.observe(app, "More SC tomorrow.") == []
    assert subj.resolve("sc") is None
    # said twice in one message counts once; a name that's taken or a common word never counts
    infer.observe(app, "OK, LA and LA again")
    assert subj.resolve("ok") is None
    item = infer._load(app)["items"][-1]
    assert infer.undo(app, item["id"]).startswith('Undone: Took "RA"')
    assert subj.resolve("ra") is None


def test_a_thesis_a_supervisor_said_plainly_and_a_person_before_the_word(env):
    app = setup(env)
    told = infer.observe(app, "I'm doing my thesis under Prof Ana Ruiz.")
    assert told and "Thesis with Prof Ana Ruiz" in told[0]
    told = infer.observe(app, "I started working with Prof Mira Cole on a project about sea ice.")
    assert told and "Sea ice" in told[0] and "Prof Mira Cole" in told[0]
    told = infer.observe(app, "My supervisor is Dr Ken Ito, from next week.")
    assert told and "Project with Dr Ken Ito" in told[0]
    people = {who: role for _, who, role in infer.projects_with(app)}
    assert people == {"Prof Ana Ruiz": "supervisor", "Prof Mira Cole": "supervisor", "Dr Ken Ito": "supervisor"}
    for line in ("My friend's supervisor is Dr Lee Park.", "My supervisor is not Dr Lee Park anymore."):
        assert infer.observe(app, line) == [], line


def test_on_mondays_ive_got_and_go_running_are_weekly_too(env):
    app = setup(env)
    told = infer.observe(app, "I've got a Linear Algebra tutorial on Wednesdays at 14:00")
    assert told and "Linear Algebra tutorial on Wed 14:00" in told[0]
    told = infer.observe(app, "I've got a lab on Mondays at 9")
    assert told and "Added lab to your commitments: Mon 09:00" in told[0]
    told = infer.observe(app, "I go running every morning at 6am")
    assert told and "Added running to your commitments" in told[0]
    assert infer.observe(app, "I went running on Monday at 6am and it was cold.") == []

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

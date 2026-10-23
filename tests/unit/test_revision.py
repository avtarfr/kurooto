"""The revision plan (modules/revision.py, a part of Exam season): a course's topics from its exam prep note (else its
lecture notes), ranked no note, stub, weak recall, the rest; laid into Start-by's free time before the exam around
classes and commitments, with class material's pages before the books'; in the morning plan; the evening question
whose answers grade the quiz items like a quiz answer, replaced by another tap and taken back by /revise undo. A fixed
clock throughout."""

from __future__ import annotations

import datetime as dt

import pytest

from kurooto.core import layout
from kurooto.modules import deadlines as dl_mod
from kurooto.modules import exam_season as es_mod
from kurooto.modules import revision as rv_mod
from kurooto.modules import startby as sb_mod
from kurooto.modules.revision import body_words, lay, minus, topic_name

MON = dt.date(2026, 11, 30)
EXAM = dt.datetime(2026, 12, 8, 9, 0)  # a Tuesday
SLUG = "linear-algebra"
FULL = "A vector space over a field is a set with addition and scalar multiplication satisfying the axioms. " * 6


def at(day: dt.date, h: int, m: int = 0) -> dt.datetime:
    return dt.datetime.combine(day, dt.time(h, m))


def days(n: int) -> dt.timedelta:
    return dt.timedelta(days=n)


@pytest.fixture
def world(env, monkeypatch):
    app = env.app
    clock = {"t": at(MON, 8)}
    for mod in (rv_mod, es_mod, dl_mod, sb_mod):
        monkeypatch.setattr(mod, "now", lambda: clock["t"])
    app.settings.set("availability.night.enabled", False)
    app.settings.set("exam_season.revision_share", 10)  # about one block a day
    env.on("subjects", "deadlines", "quiz", "commitments", "startby", "exam_season")
    env.say("/subject add Linear Algebra (la)")
    app.settings.set("subjects.timetable", [{"day": "mon", "start": "09:00", "end": "10:00", "subject": SLUG}])
    app.modules["commitments"].add("gym", ["tue"], "09:00", "11:00")
    app.modules["deadlines"].add("Linear Algebra final exam", EXAM, kind="exam", subject=SLUG)
    root = app.workspace
    note = lambda name, text: (root / SLUG / name).write_text(text, encoding="utf-8")  # noqa: E731
    (root / SLUG).mkdir(parents=True, exist_ok=True)
    note("2026-11-02-vector-spaces.md", f"# Vector spaces\n\n{FULL}\n")
    note("2026-11-05-eigenvalues.md", "# Eigenvalues\n\nTo do.\n")  # a stub
    note("2026-11-09-determinants.md", f"# Determinants\n\n{FULL}\n")
    note(
        "exam-prep.md",
        "# Linear Algebra exam prep\n\n## Covered so far\n"
        f"- [[{SLUG}/2026-11-02-vector-spaces|Lecture 1]]: Vector spaces\n"
        f"- [[{SLUG}/2026-11-05-eigenvalues|Lecture 2]]: Eigenvalues\n"
        "- Lecture 3: Jordan form\n"
        f"- [[2026-11-09-determinants]]\n\n"
        "## Must know\n"
        "- Vector spaces: a basis is a linearly independent spanning set.\n"
        "- Jordan form: every complex square matrix is similar to a Jordan matrix.\n\n"
        "## Gaps\n- Spectral theorem\n"
        "- The book and the slides use different sign conventions for the cofactor expansion of a determinant.\n",
    )
    cls = layout.file_dir(app, "classroom", subject=SLUG)
    cls.mkdir(parents=True, exist_ok=True)
    (cls / "Lecture 3 slides.pdf").write_bytes(b"%PDF-1.4 x")
    (cls / "Lecture 3 slides.pdf.txt").write_text(
        "Intro\f Generalised eigenvectors\f Jordan form. Each Jordan form block\f", encoding="utf-8"
    )
    book = app.paths.data / "book-text" / SLUG / "axler"
    (book / "pages").mkdir(parents=True)
    (book / "meta.json").write_text('{"title": "Axler", "pages": 300}', encoding="utf-8")
    for i, text in enumerate(["Preface", "Jordan form, and the Jordan form theorem", "Index"], 1):
        (book / "pages" / f"{i:05d}.md").write_text(text, encoding="utf-8")
    quiz = app.modules["quiz"]
    st = quiz.state(SLUG)
    weak = next(i for i, it in st["items"].items() if it["text"].startswith("Vector spaces"))
    quiz.grade(SLUG, weak, 1)
    return env, app, clock


def blocks(app) -> list[tuple[str, str]]:
    return [(f"{b['start']:%a %H:%M}", b["name"]) for b in app.modules["exam_season"].revision.plan()[0]]


# ------------------------------------------------------------------------------------------- the arithmetic
def test_topic_names_stubs_free_time_and_blocks():
    assert topic_name("[[la/2026-11-02-vector-spaces|Lecture 1]]: Vector spaces") == "Vector spaces"
    assert topic_name("[[la/2026-11-09-determinants]]") == "determinants"
    assert topic_name("Eigenvalues: the characteristic polynomial") == "Eigenvalues: the characteristic polynomial"
    assert topic_name("Week 3 - **Groups**") == "Groups"
    assert body_words("---\ntitle: x\n---\n# Head\n\nYou missed this class (skipped).\n- [Slides](http://x)\n") == 0
    assert body_words("# Head\n\nThree words here and [[a|b]].\n") == 4
    d = MON
    free = minus([(at(d, 9), at(d, 17))], [(at(d, 10), at(d, 11)), (at(d, 16, 45), at(d, 18))], 30)
    assert free == [(at(d, 9), at(d, 10)), (at(d, 11), at(d, 16, 45))]
    exams = [
        {"id": "b", "until": at(d + days(3), 9), "topics": ["b1", "b2", "b3"], "n": 2},
        {"id": "a", "until": at(d, 12), "topics": ["a1", "a2"], "n": 5},
    ]
    slots = [(at(d, 9), at(d, 13)), (at(d + days(1), 9), at(d + days(1), 13))]
    got = [(f"{x['start']:%d %H}", x["topic"]) for x in lay(slots, exams, 60, 0.5)]
    # the soonest exam first, until its blocks end; half of each day's 4 free hours; at most n for each exam
    assert got == [("30 09", "a1"), ("30 10", "a2"), ("01 09", "b1"), ("01 10", "b2")]


# -------------------------------------------------------------------------------------------- the ranking
def test_topics_from_the_exam_prep_note_ranked(world):
    env, app, clock = world
    rv = app.modules["exam_season"].revision
    ranked, where = rv.ranked(SLUG)
    assert where == f"{SLUG}/exam-prep.md"
    assert [(t["name"], t["why"]) for t in ranked] == [
        ("Jordan form", "no note yet"),
        ("Spectral theorem", "no note yet"),  # a gap; the long one about sign conventions isn't a topic
        ("Eigenvalues", "a stub"),
        ("Vector spaces", "weak recall, 1.0 of 5"),
        ("determinants", ""),  # found by name in the subject's folder
    ]
    out = env.say("/revise la")
    assert out.startswith(f"Linear Algebra: 5 topics from {SLUG}/exam-prep.md, weakest first:\n- Jordan form (no note")
    # without an exam prep note: the lecture notes, in date order
    (app.workspace / SLUG / "exam-prep.md").unlink()
    ranked, where = rv.ranked(SLUG)
    assert where == "lecture notes" and [t["name"] for t in ranked] == ["Eigenvalues", "Vector spaces", "Determinants"]


# --------------------------------------------------------------------------------------------- the plan
def test_laid_into_free_time_with_what_to_read(world):
    env, app, clock = world
    assert blocks(app) == [
        ("Mon 10:00", "Jordan form"),  # after Monday's class
        ("Tue 11:00", "Spectral theorem"),  # after the gym
        ("Wed 09:00", "Eigenvalues"),
        ("Thu 09:00", "Vector spaces"),
        ("Fri 09:00", "determinants"),
    ]
    today = app.modules["exam_season"].revision.today()
    assert today[0]["read"] == ["Lecture 3 slides.pdf, p. 3", "Axler, p. 2"]  # class material before books
    rows = app.modules["startby"].morning_rows()
    assert {"title": "Revise Jordan form", "when": "10:00-11:00 · for Linear Algebra final exam"} in rows
    assert any(x.startswith("Revise 10:00-11:00 Jordan form") for x in app.modules["startby"].morning_lines())
    out = env.say("/revise")
    assert out.startswith(
        "Revision plan (an estimate, from your notes and free time):\nToday:\n- 10:00-11:00 Jordan form (Linear "
        "Algebra final exam, no note yet). Read: Lecture 3 slides.pdf, p. 3; Axler, p. 2\nTue 1 Dec:\n"
    )
    assert env.say("what should I revise today?").startswith("Revise today:\n- 10:00-11:00 Jordan form")
    assert "/revise" in env.say("/help revise")
    assert "Revision today: Jordan form 10:00." in app.modules["exam_season"].card()["lines"]
    # today's blocks stay as they were this morning, even when the notes change
    (app.workspace / SLUG / "2026-11-20-jordan-form.md").write_text(f"# Jordan form\n\n{FULL}")
    assert blocks(app)[0] == ("Mon 10:00", "Jordan form")


def test_the_evening_question_counts_like_a_quiz_answer_with_undo(world):
    env, app, clock = world
    es, quiz = app.modules["exam_season"], app.modules["quiz"]
    clock["t"] = at(MON, 8, 15)
    es._tick()  # the day's blocks are fixed
    clock["t"] = at(MON, 21, 0)
    assert "revision" not in es._tick()  # not before night_at (21:30) without Check-ins
    clock["t"] = at(MON, 21, 30)
    assert es._tick()["revision"] is True
    assert env.fake.texts()[-1].startswith("Revision: did you cover Jordan form (Linear Algebra) today?")
    assert "revision" not in es._tick()  # once a day
    item = next(i for i, it in quiz.load(SLUG)["items"].items() if it["text"].startswith("Jordan"))
    out = env.press("rv:20261130-0:p")
    assert out.startswith("Partly: Jordan form. Counted like a quiz answer for the topic and 1 quiz item.")
    assert quiz.load(SLUG)["items"][item]["history"][-1]["q"] == 2
    env.press("rv:20261130-0:y")  # another answer replaces the first
    hist = quiz.load(SLUG)["items"][item]["history"]
    assert [h["q"] for h in hist] == [4]
    clock["t"] = at(MON + days(1), 8)
    assert "Jordan form" not in [name for _, name in blocks(app)]  # covered: not laid again
    assert env.say("/revise undo") == "Taken back: the topic's grades are as they were."
    assert quiz.load(SLUG)["items"][item]["history"] == []
    assert env.say("/revise undo") == "Nothing to undo."


def test_off_and_without_exams(world):
    env, app, clock = world
    app.settings.set("exam_season.revision", False)
    assert env.say("/revise") == "The revision plan is off (/examseason switches it on)."
    assert app.modules["startby"].morning_rows() == [] or all(
        not r["title"].startswith("Revise") for r in app.modules["startby"].morning_rows()
    )
    app.settings.set("exam_season.revision", True)
    clock["t"] = at(MON - days(10), 8)  # 18 days before the exam
    assert env.say("/revise") == "No exam in the next 14 days, so no revision plan yet."

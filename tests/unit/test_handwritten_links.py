"""Handwritten notes linked like any other note: a real title, the subject and lecture from when they were written,
a ## Links and ## Doubts list after the transcription, a line on the course page, undo, and /handwritten link for the
ones written out before. The AI's answer is faked; everything else is real."""

import datetime as dt
import json
import os
import time

import pytest

from kurooto.modules import handwritten_links as hl
from kurooto.modules.handwritten import END, _title
from tests.fakes.openai import FakeOpenAI

SUBJ = "physics-of-the-atmosphere"
SCAN = "21 October 2026_261021_105812.pdf"  # a notes app's name: written on Wed 21 Oct 2026 at 10:58
PAGES = (
    "## Page 1\n\nPhase change: $L = T \\Delta s$. The Clausius-Clapeyron relation gives the slope.\n\n"
    "## Page 2\n\nLatent heat of vaporisation stays nearly constant.\n- DOUBT: why is L constant here?\n"
    "Saturation vapour pressure ??? check the exponent"
)


def answer(**kw):
    base = {
        "title": "Phase change thermodynamics",
        "subject": SUBJ,
        "links": [
            {
                "target": "zettel/clausius-clapeyron-relation",
                "reason": "page 1 derives the slope of the saturation curve from this relation",
                "confidence": 0.9,
            },
            {
                "target": "zettel/latent-heat",
                "reason": "page 2 uses the latent heat of vaporisation as a constant",
                "confidence": 0.8,
            },
            {"target": "zettel/unrelated", "reason": "related to", "confidence": 0.9},  # vague: dropped
            {
                "target": "zettel/nowhere",
                "reason": "this note does not exist anywhere in the notes",
                "confidence": 0.9,
            },
            {
                "target": "zettel/latent-heat",
                "reason": "the same note again should not be linked twice",
                "confidence": 0.9,
            },
            {"target": "zettel/unsure", "reason": "an unsure guess about the energy budget", "confidence": 0.2},
        ],
    }
    return json.dumps({**base, **kw})


@pytest.fixture
def world(env):
    """The zettelkasten layout, a fake AI as the main brain, POTA on Wednesdays 10:00-11:00, its lecture note of
    21 Oct, its course page and three concept notes."""
    fake = FakeOpenAI()
    app = env.app
    app.secrets.set("custom.api_key", fake.key)
    app.settings.set("brain.base_urls", {"custom": fake.base})
    app.settings.set("brain.models", {"custom": {"low": "m", "medium": "m", "high": "m"}})
    app.settings.set("brain.main", "custom")
    app.settings.set("notes.layout", "zettelkasten")
    app.settings.set("subjects.list", [{"name": "Physics of the Atmosphere", "slug": SUBJ, "aliases": ["pota"]}])
    app.settings.set("subjects.timetable", [{"day": "wed", "start": "10:00", "end": "11:00", "subject": SUBJ}])
    app.power.current = "normal"
    app.settings.set("handwritten.local_model", "fake-vision")  # ready, without a key
    app.settings.set("handwritten.overlap", False)  # the linking alone (the overlap: test_handwritten_overlap.py)
    env.on("subjects", "handwritten")
    ws = app.workspace
    for rel, text in {
        f"sources/{SUBJ}/2026-10-21-lecture-20.md": "# Lecture 20: Clausius-Clapeyron\n\nSlides.\n",
        f"maps/courses/{SUBJ}.md": "# Physics of the Atmosphere\n\nMy own course intro.\n",
        "zettel/clausius-clapeyron-relation.md": "# Clausius-Clapeyron relation\n\nThe slope of a phase boundary.\n",
        "zettel/latent-heat.md": "# Latent heat\n\nHeat absorbed in a phase change at constant temperature.\n",
        "zettel/unrelated.md": "# Group theory\n\nSymmetries.\n",
        "zettel/unsure.md": "# Energy budget\n\nIn and out.\n",
    }.items():
        (ws / rel).parent.mkdir(parents=True, exist_ok=True)
        (ws / rel).write_text(text, encoding="utf-8")
    env.fake_ai = fake
    env.hw = app.modules["handwritten"]
    yield env
    fake.close()


def run_all(env):
    n = 0
    while env.app.jobs.run_next():
        n += 1
        assert n < 20
    return n


def transcribe(env, name=SCAN, md=PAGES):
    """Write one scan out (as a PDF read here page by page would be: its title is the file's name)."""
    src = env.hw.folder() / name
    src.write_bytes(b"%PDF-1.4 fake")
    os.utime(src, (time.time() - 60, time.time() - 60))
    shown = env.hw._file(src, md, title=_title(src), how="by fake-vision on this computer, 2 pages, unchecked")
    return env.app.workspace / shown


def test_a_transcription_gets_a_title_its_lecture_concepts_doubts_and_a_course_line(world):
    env = world
    env.fake_ai.answer = answer()
    note = transcribe(env)
    note.write_text(note.read_text(encoding="utf-8") + "\nMy own remark under it.\n", encoding="utf-8")
    assert run_all(env) == 1
    prompt = env.fake_ai.requests[-1]["messages"][-1]["content"]
    assert "Clausius-Clapeyron relation gives the slope" in prompt  # the pages go to the AI ...
    assert "zettel/latent-heat" in prompt and "during the Physics of the Atmosphere class" in prompt  # ... and cards
    text = note.read_text(encoding="utf-8")
    assert "\n# Phase change thermodynamics\n" in text and "# 21 October" not in text
    assert '"Phase change thermodynamics"' in text and '"21 October 2026 261021 105812"' in text  # old name: alias
    assert f"tags: [handwritten, {SUBJ}]" in text and f"course: {SUBJ}" in text
    after = text.split(END, 1)[1]
    assert after.lstrip().startswith("<!-- kurooto:linked -->\n## Links\n")  # right after the closing marker
    assert f"- [[sources/{SUBJ}/2026-10-21-lecture-20]]: written during the Physics of the Atmosphere class" in after
    assert f"- [[maps/courses/{SUBJ}]]: the course page of Physics of the Atmosphere" in after
    assert "- [[zettel/clausius-clapeyron-relation]]: page 1 derives the slope" in after
    assert after.count("[[zettel/latent-heat]]") == 1
    for gone in ("zettel/unrelated", "zettel/nowhere", "zettel/unsure"):
        assert gone not in after  # vague, missing, unsure: never linked
    assert "## Doubts\n- p. 2: DOUBT: why is L constant here?\n- p. 2: Saturation vapour pressure ???" in after
    assert "My own remark under it." in after and text.index("My own remark") > text.index("<!-- /kurooto:linked")
    course = (env.app.workspace / "maps" / "courses" / f"{SUBJ}.md").read_text(encoding="utf-8")
    assert "My own course intro." in course and "<!-- kurooto:handwritten-notes -->" in course
    rel = f"handwritten/{note.stem}"
    assert (
        f"- [[sources/{SUBJ}/2026-10-21-lecture-20|Lecture 20: Clausius-Clapeyron]]: "
        f"[[{rel}|Phase change thermodynamics]]" in course
    )
    told = env.fake.texts()[-1]
    assert told.startswith(
        "Linked your handwritten notes 'Phase change thermodynamics' to POTA lecture 20: Clausius-Clapeyron and "
        "2 concepts; 2 doubts listed."
    )
    assert "/handwritten undo" in told


def test_undo_puts_the_note_and_the_course_page_back_and_link_does_it_again_once(world):
    env = world
    env.fake_ai.answer = answer()
    note = transcribe(env)
    before = note.read_text(encoding="utf-8")
    course_f = env.app.workspace / "maps" / "courses" / f"{SUBJ}.md"
    course_before = course_f.read_text(encoding="utf-8")
    run_all(env)
    assert note.read_text(encoding="utf-8") != before
    out = env.say("/handwritten undo")
    assert "Took back the linking of 'Phase change thermodynamics' (2 files)" in out
    assert note.read_text(encoding="utf-8") == before and course_f.read_text(encoding="utf-8") == course_before
    assert env.say("/handwritten undo") == "Nothing to undo."

    # /handwritten link: every transcription without a Links section, once
    out = env.say("/handwritten link")
    assert out.startswith("Linking 1 handwritten note")
    assert env.say("/handwritten link").startswith("Already linking 1")  # asked twice: one request
    assert run_all(env) == 1
    linked = note.read_text(encoding="utf-8")
    assert "## Links" in linked and "# Phase change thermodynamics" in linked
    assert (
        "Linked 1 handwritten note ('Phase change thermodynamics') to 1 lecture and 2 concept notes"
        in (env.fake.texts()[-1])
    )
    n_req = len(env.fake_ai.requests)
    assert env.say("/handwritten link") == "Every handwritten note is linked already."
    assert run_all(env) == 0 and len(env.fake_ai.requests) == n_req
    assert note.read_text(encoding="utf-8") == linked  # twice: nothing changes


def test_an_edited_file_is_not_put_back_by_undo(world):
    env = world
    env.fake_ai.answer = answer()
    note = transcribe(env)
    run_all(env)
    note.write_text(note.read_text(encoding="utf-8") + "\nWritten after the linking.\n", encoding="utf-8")
    out = env.say("/handwritten undo")
    assert "(1 file)" in out and "1 file you changed since stayed as it is" in out
    assert "Written after the linking." in note.read_text(encoding="utf-8")


def test_an_unusable_answer_writes_nothing_and_link_tries_again(world):
    env = world
    env.fake_ai.answer = "I can't help with that."
    note = transcribe(env)
    before = note.read_text(encoding="utf-8")
    run_all(env)
    assert note.read_text(encoding="utf-8") == before
    env.fake_ai.answer = answer(links=[])
    assert env.say("/handwritten link").startswith("Linking 1")
    run_all(env)
    text = note.read_text(encoding="utf-8")
    assert "## Links" in text and f"[[sources/{SUBJ}/2026-10-21-lecture-20]]" in text and "[[zettel/" not in text


def test_your_own_heading_and_text_above_stay_and_nothing_you_wrote_changes(world):
    env = world
    env.fake_ai.answer = answer()
    note = transcribe(env)
    text = note.read_text(encoding="utf-8")
    marker = text.index("<!-- kurooto:handwritten")
    mine = text[:marker] + "Notes from the board, see the textbook too.\n\n" + text[marker:]
    note.write_text(mine, encoding="utf-8")
    run_all(env)
    new = note.read_text(encoding="utf-8")
    assert "# 21 October 2026 261021 105812" in new  # the head isn't only Kurooto's now: the heading stays
    assert "Notes from the board, see the textbook too." in new and "## Links" in new
    assert hl.yours(new) == hl.yours(mine)


def test_written_in_the_evening_it_is_that_days_class_and_a_real_title_stays(world):
    env = world
    env.fake_ai.answer = answer(subject=None, title="Something else entirely here")
    note = transcribe(env, "notes 2026-10-21 19.30.pdf", "# Saturation vapour pressure\n\nThe curve $e_s(T)$.")
    run_all(env)
    text = note.read_text(encoding="utf-8")
    assert "# Saturation vapour pressure" in text and "Something else" not in text  # a real title isn't replaced
    assert f"course: {SUBJ}" in text  # the AI didn't say; the class before that evening did
    assert "written after the Physics of the Atmosphere class on Wed 21 Oct" in text


def test_with_no_class_the_subject_comes_from_what_the_pages_say(world):
    env = world
    env.fake_ai.answer = answer()
    note = transcribe(env, "notes 2026-10-22 15.00.pdf")  # a Thursday: no POTA class, no lecture note
    run_all(env)
    text = note.read_text(encoding="utf-8")
    assert f"course: {SUBJ}" in text and f"[[maps/courses/{SUBJ}]]" in text and "lecture-20" not in text
    assert env.fake.texts()[-1].startswith(
        "Linked your handwritten notes 'Phase change thermodynamics' to Physics of the Atmosphere and 2 concepts"
    )
    course = (env.app.workspace / "maps" / "courses" / f"{SUBJ}.md").read_text(encoding="utf-8")
    assert f"- [[handwritten/{note.stem}|Phase change thermodynamics]]" in course  # under "Handwritten notes"


def test_linking_off_or_no_ai_asks_nothing(world):
    env = world
    env.app.settings.set("handwritten.link", False)
    transcribe(env)
    assert run_all(env) == 0
    assert env.say("/handwritten link") == "Linking is off (handwritten.link)."
    env.app.settings.set("handwritten.link", True)
    env.app.settings.set("brain.main", "")
    assert env.say("/handwritten link").startswith("Linking needs an AI")


def test_the_kurooto_layout_gets_a_header_and_its_own_course_page(env):
    fake = FakeOpenAI()
    try:
        app = env.app
        app.secrets.set("custom.api_key", fake.key)
        app.settings.set("brain.base_urls", {"custom": fake.base})
        app.settings.set("brain.models", {"custom": {"low": "m", "medium": "m", "high": "m"}})
        app.settings.set("brain.main", "custom")
        app.settings.set("subjects.list", [{"name": "Linear Algebra", "slug": "linear-algebra", "aliases": ["la"]}])
        app.power.current = "normal"
        app.settings.set("handwritten.local_model", "fake-vision")  # ready, without a key
        app.settings.set("handwritten.overlap", False)
        env.on("subjects", "handwritten")
        ws = app.workspace
        (ws / "linear-algebra").mkdir(parents=True)
        (ws / "linear-algebra" / "course.md").write_text("# Linear Algebra\n", encoding="utf-8")
        (ws / "linear-algebra" / "eigenvalues.md").write_text("# Eigenvalues\n\nAv = lambda v.\n", encoding="utf-8")
        fake.answer = json.dumps(
            {
                "title": "Eigenvalues of a two by two",
                "subject": "linear-algebra",
                "links": [
                    {
                        "target": "linear-algebra/eigenvalues",
                        "reason": "the pages compute the eigenvalues of a two by two matrix",
                        "confidence": 0.9,
                    }
                ],
            }
        )
        h = app.modules["handwritten"]
        src = h.folder() / "IMG_20261020_181500.jpg"
        src.write_bytes(b"\xff\xd8 fake")
        note = ws / h._file(src, "Find eigenvalues of [[2,1],[1,2]].", title=_title(src))
        run_all(env)
        text = note.read_text(encoding="utf-8")
        assert text.startswith("---\naliases: [")
        assert (
            "tags: [handwritten, linear-algebra]\ncourse: linear-algebra\n---\n\n# Eigenvalues of a two by two" in text
        )
        assert "- [[linear-algebra/eigenvalues]]: the pages compute" in text
        assert "- [[linear-algebra/course]]: the course page of Linear Algebra" in text
        assert f"[[handwritten/{note.stem}|Eigenvalues of a two by two]]" in (
            ws / "linear-algebra" / "course.md"
        ).read_text(encoding="utf-8")
    finally:
        fake.close()


def test_the_privacy_text_says_the_ai_reads_it_for_linking(env):
    assert "the AI you picked" in env.app.modules["handwritten"].privacy


# --------------------------------------------------------------------------------------- the parts, alone
def test_times_from_names_and_pdf_dates():
    assert hl.name_time("21 October 2026_261021_105812") == dt.datetime(2026, 10, 21, 10, 58, 12)
    assert hl.name_time("notes 2026-10-21 19.30.pdf") == dt.datetime(2026, 10, 21, 19, 30)
    assert hl.name_time("IMG_20261020_181500.jpg") == dt.datetime(2026, 10, 20, 18, 15)
    assert hl.name_time("21 October 2026.pdf") == dt.date(2026, 10, 21)
    assert hl.name_time("lecture_07-eigenvalues.pdf") is None
    assert hl.pdf_date("D:20261021105812") == dt.datetime(2026, 10, 21, 10, 58, 12)
    utc = hl.pdf_date("D:20261021052812Z")
    assert utc == dt.datetime(2026, 10, 21, 5, 28, 12, tzinfo=dt.UTC).astimezone().replace(tzinfo=None)
    assert hl.pdf_date("nonsense") is None


def test_the_pdfs_own_dates_come_first(tmp_path):
    from tests.unit.test_books import make_pdf

    f = tmp_path / "ink.pdf"
    make_pdf(f, [("text", "x")])
    data = f.read_bytes().replace(
        b"/Info << /Title (Linear Algebra) >>", b"/Info << /CreationDate (D:20261021103000) >>"
    )
    f.write_bytes(data)
    assert hl.written_times(f)[0] == dt.datetime(2026, 10, 21, 10, 30)


def test_doubts_carry_their_page():
    assert hl.doubts("one\n## Page 3\n\n* Doubt: sign of the work?\nfine\n1. what ??? here") == [
        (3, "Doubt: sign of the work?"),
        (3, "what ??? here"),
    ]
    assert hl.doubts("no doubts here, no questions?") == []


def test_file_names_are_told_from_titles():
    assert hl.looks_like_a_file_name("21 October 2026 261021 105812")
    assert hl.looks_like_a_file_name("Scan 3") and hl.looks_like_a_file_name("")
    assert hl.looks_like_a_file_name("Lecture 07 eigenvalues", ["lecture_07-eigenvalues.pdf"])
    assert not hl.looks_like_a_file_name("Phase change thermodynamics")

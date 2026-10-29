"""Handwritten notes that repeat what you have (0.9.0): the sections your notes for the course already cover are marked
"(already in [[note]])" with an "Already in your notes" and a "New here" list, and "only from <topic>" (a text file next
to the scan, its name, /handwritten only) adds the part from that heading on. The AI's answers are faked; the notes
folder is the test's own scratch folder."""

import json
import os
import time

import pytest

from kurooto.modules import handwritten_links as hl
from kurooto.modules import handwritten_overlap as ho
from kurooto.modules.handwritten import END, START, _title
from tests.fakes.openai import FakeOpenAI

SUBJ = "multivariable-calculus"
LECTURE = f"sources/{SUBJ}/2026-10-21-lecture-5"
SCAN = "21 October 2026_261021_103000.pdf"  # written on Wed 21 Oct 2026 at 10:30, in the class
PAGES = (
    "## Page 1\n\n## Limits in two variables\n\nThe limit of $f(x,y)$ as $(x,y) \\to (a,b)$ must agree along every "
    "path; two paths that disagree show there is no limit.\n\n## Partial derivatives\n\n$f_x$ holds $y$ fixed and "
    "differentiates in $x$; $f_y$ the other way round.\n\n## Page 2\n\n## Functions of Several Variables\n\nA function "
    "$f: \\mathbb{R}^2 \\to \\mathbb{R}$, its level sets and its graph.\n\n## Taylor's theorem in two variables\n\n"
    "The second order expansion uses the Hessian $H_f$."
)


def link_answer():
    return json.dumps({"title": "Limits and partial derivatives", "subject": SUBJ, "links": []})


def overlap_answer(**kw):
    base = {
        "covered": [
            {
                "section": 1,
                "target": LECTURE,
                "reason": "lecture 5 shows the same two-path test for a limit that fails",
                "confidence": 0.9,
            },
            {
                "section": 2,
                "target": "zettel/partial-derivatives",
                "reason": "the concept note defines f_x and f_y with the other variable held fixed",
                "confidence": 0.8,
            },
            {"section": 3, "target": "zettel/nowhere", "reason": "a note that is not one of the candidates at all"},
            {"section": 4, "target": "zettel/level-sets", "reason": "related to", "confidence": 0.9},  # vague
            {
                "section": 4,
                "target": "zettel/level-sets",
                "reason": "an unsure guess about the hessian",
                "confidence": 0.2,
            },
        ]
    }
    return json.dumps({**base, **kw})


@pytest.fixture
def world(env):
    """The zettelkasten layout in the test's scratch notes folder, a fake AI as the main brain, Multivariable Calculus
    on Wednesdays 10:00-11:00 with its lecture note of 21 Oct, its course page and three concept notes."""
    fake = FakeOpenAI()
    app = env.app
    app.secrets.set("custom.api_key", fake.key)
    app.settings.set("brain.base_urls", {"custom": fake.base})
    app.settings.set("brain.models", {"custom": {"low": "m", "medium": "m", "high": "m"}})
    app.settings.set("brain.main", "custom")
    app.settings.set("notes.layout", "zettelkasten")
    app.settings.set("subjects.list", [{"name": "Multivariable Calculus", "slug": SUBJ, "aliases": ["mvc"]}])
    app.settings.set("subjects.timetable", [{"day": "wed", "start": "10:00", "end": "11:00", "subject": SUBJ}])
    app.power.current = "normal"
    app.settings.set("handwritten.local_model", "fake-vision")  # ready, without a key
    env.on("subjects", "handwritten")
    ws = app.workspace
    for rel, text in {
        f"{LECTURE}.md": "# Lecture 5: Limits\n\n## Limits in two variables\n\nAlong two paths the limit of f(x,y) "
        "must agree.\n",
        f"maps/courses/{SUBJ}.md": "# Multivariable Calculus\n\nMy own course intro.\n",
        "zettel/partial-derivatives.md": "# Partial derivatives\n\nThe partial derivative f_x holds y fixed.\n",
        "zettel/level-sets.md": "# Level sets\n\nWhere a function of two variables takes one value.\n",
        "zettel/group-theory.md": "# Group theory\n\nSymmetries.\n",
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


def transcribe(env, name=SCAN, md=PAGES, side=None):
    """Write one scan out as a PDF read here page by page would be; `side`: the text file next to it."""
    src = env.hw.folder() / name
    src.write_bytes(b"%PDF-1.4 fake")
    if side is not None:
        src.with_suffix(".txt").write_text(side, encoding="utf-8")
    os.utime(src, (time.time() - 60, time.time() - 60))
    shown = env.hw._file(src, md, title=_title(src), how="by fake-vision on this computer, 2 pages, unchecked")
    return env.app.workspace / shown


def link_then_overlap(env, answer=None):
    """The linking request, then the overlap request it starts, each with its own answer."""
    env.fake_ai.answer = link_answer()
    assert env.app.jobs.run_next()
    env.fake_ai.answer = answer or overlap_answer()
    return run_all(env)


def block(text):
    return text[text.index(START) : text.index(END)]


# ---------------------------------------------------------------------------------------------- marking
def test_sections_already_in_your_notes_are_marked_and_listed_and_nothing_of_yours_changes(world):
    env = world
    ws = env.app.workspace
    others = {p: p.read_text(encoding="utf-8") for p in ws.rglob("*.md")}
    note = transcribe(env)
    before = note.read_text(encoding="utf-8")
    note.write_text(before + "\nMy own remark under it.\n", encoding="utf-8")
    assert link_then_overlap(env) == 1
    prompt = env.fake_ai.requests[-1]["messages"][-1]["content"]
    assert "[1] Limits in two variables (p. 1)" in prompt and "[3] Functions of Several Variables (p. 2)" in prompt
    assert LECTURE in prompt and "zettel/partial-derivatives" in prompt  # the course's notes and the concepts
    assert "My own remark" not in prompt and "My own course intro" not in prompt  # only the transcription goes
    text = note.read_text(encoding="utf-8")
    inside = block(text)
    assert f"## Limits in two variables (already in [[{LECTURE}]])" in inside
    assert "## Partial derivatives (already in [[zettel/partial-derivatives]])" in inside
    assert "## Functions of Several Variables\n" in inside and "## Taylor's theorem in two variables\n" in inside
    assert "path; two paths that disagree show there is no limit." in inside  # the text under a mark stays
    after = text.split("<!-- /kurooto:linked -->", 1)[1]
    assert after.lstrip().startswith("<!-- kurooto:overlap -->\n## Already in your notes\n")
    assert (
        f"- Limits in two variables (p. 1) → [[{LECTURE}]]: lecture 5 shows the same two-path test for a limit "
        "that fails\n- Partial derivatives (p. 1) → [[zettel/partial-derivatives]]: the concept note defines" in after
    )
    assert "## New here\n- Functions of Several Variables (p. 2)\n- Taylor's theorem in two variables (p. 2)\n" in after
    assert "zettel/nowhere" not in text and "zettel/level-sets" not in text  # not a candidate, vague, unsure
    assert "My own remark under it." in after and text.index("My own remark") > text.index("<!-- /kurooto:overlap")
    assert hl.yours(text) == hl.yours(before + "\nMy own remark under it.\n")
    assert "already in" not in hl.parts(text)[1]  # the linker and the concept graph read it clean
    for p, t in others.items():
        if p.name != f"{SUBJ}.md":  # the course page gets its linking line, nothing else does
            assert p.read_text(encoding="utf-8") == t
    told = env.fake.texts()[-1]
    assert told.startswith(
        "'Limits and partial derivatives': 2 of 4 sections are already in your notes (marked in the note); new "
        "here: Functions of Several Variables, Taylor's theorem in two variables."
    )


def test_undo_takes_back_the_linking_and_the_marks_together(world):
    env = world
    note = transcribe(env)
    before = note.read_text(encoding="utf-8")
    link_then_overlap(env)
    assert "already in" in note.read_text(encoding="utf-8")
    out = env.say("/handwritten undo")
    assert out.startswith("Took back the linking of 'Limits and partial derivatives' (2 files)")
    assert note.read_text(encoding="utf-8") == before
    assert env.hw.overlap.load()["notes"] == {}  # not written again later


def test_the_original_written_again_gets_its_marks_back(world):
    env = world
    note = transcribe(env)
    link_then_overlap(env)
    note.write_text(note.read_text(encoding="utf-8") + "\nMine.\n", encoding="utf-8")
    env.fake_ai.answer = link_answer()
    transcribe(env)  # the tablet's page changed: Kurooto's part is written again
    text = note.read_text(encoding="utf-8")
    assert "## Partial derivatives (already in [[zettel/partial-derivatives]])" in text and "Mine." in text


def test_only_the_courses_named_are_checked(world):
    env = world
    env.app.settings.set("handwritten.overlap_courses", ["Linear Algebra"])
    note = transcribe(env)
    env.fake_ai.answer = link_answer()
    assert run_all(env) == 1  # the linking only
    assert "kurooto:overlap" not in note.read_text(encoding="utf-8")
    env.app.settings.set("handwritten.overlap_courses", ["MVC"])  # its short name counts
    assert env.hw.overlap.course_allowed(SUBJ) and not env.hw.overlap.course_allowed("")
    assert env.hw.overlap.submit(note)
    env.fake_ai.answer = overlap_answer()
    assert run_all(env) == 1
    assert "kurooto:overlap" in note.read_text(encoding="utf-8")


def test_overlap_off_asks_nothing(world):
    env = world
    env.app.settings.set("handwritten.overlap", False)
    note = transcribe(env)
    env.fake_ai.answer = link_answer()
    assert run_all(env) == 1
    assert "kurooto:overlap" not in note.read_text(encoding="utf-8")
    assert "already in" not in note.read_text(encoding="utf-8")


def test_with_linking_off_it_is_asked_straight_away(world):
    env = world
    env.app.settings.set("handwritten.link", False)
    note = transcribe(env)
    env.fake_ai.answer = overlap_answer()
    assert run_all(env) == 1
    text = note.read_text(encoding="utf-8")
    assert "## Partial derivatives (already in [[zettel/partial-derivatives]])" in text and "## Links" not in text
    assert "<!-- kurooto:overlap -->" in text


def test_an_earlier_handwritten_note_of_the_course_counts(world):
    env = world
    env.app.settings.set("handwritten.link", False)
    first = transcribe(env, "week4.pdf", "## Taylor's theorem in two variables\n\nThe Hessian gives the second order.")
    env.fake_ai.answer = json.dumps({"covered": []})
    run_all(env)
    st = env.hw.linker.load()  # the linking's record says which course a note is
    st["notes"][env.hw.linker.rel(first)] = {"title": "Week 4", "subject": SUBJ, "lecture": "", "day": "2026-10-14"}
    env.hw.linker.save(st)
    note = transcribe(env)
    st["notes"][env.hw.linker.rel(note)] = {"title": "Week 5", "subject": SUBJ, "lecture": "", "day": "2026-10-21"}
    env.hw.linker.save(st)
    assert env.hw.overlap.submit(note)
    rel = env.hw.linker.rel(first)
    env.fake_ai.answer = overlap_answer(
        covered=[{"section": 4, "target": rel, "reason": "week 4 already expands to second order with the Hessian"}]
    )
    run_all(env)
    prompt = env.fake_ai.requests[-1]["messages"][-1]["content"]
    assert rel in prompt and "Taylor's theorem in two variables" in prompt
    assert f"## Taylor's theorem in two variables (already in [[{rel}]])" in note.read_text(encoding="utf-8")


# ------------------------------------------------------------------------------------------------ only from
def test_a_text_file_next_to_the_scan_asks_for_only_from_a_topic(world):
    env = world
    env.app.settings.set("handwritten.link", False)
    env.app.settings.set("handwritten.overlap", False)
    note = transcribe(env, "week5.pdf", side="only from functions of several variable\n")  # loosely spelt
    text = note.read_text(encoding="utf-8")
    assert "## Limits in two variables" in block(text)  # the full transcription stays
    part = text.split("<!-- kurooto:only-from -->", 1)[1].split("<!-- /kurooto:only-from -->")[0]
    assert part.startswith('\n## From "Functions of Several Variables" on\n*Only the part from this heading on, page 2')
    assert "### Functions of Several Variables\n" in part and "### Taylor's theorem in two variables" in part
    assert "Limits in two variables" not in part and "Partial derivatives" not in part
    assert "Original:" not in part


def test_the_marks_reach_the_only_from_part(world):
    env = world
    note = transcribe(env, "week5.pdf", side="Partial derivatives")  # a text file may say just the topic
    link_then_overlap(env)
    part = note.read_text(encoding="utf-8").split("<!-- kurooto:only-from -->", 1)[1]
    assert "### Partial derivatives (already in [[zettel/partial-derivatives]])" in part
    assert "### Functions of Several Variables\n" in part and "Limits in two" not in part.split("<!--")[0]


def test_the_scans_name_can_say_from_where(world):
    env = world
    env.app.settings.set("handwritten.link", False)
    env.app.settings.set("handwritten.overlap", False)
    note = transcribe(env, "mvc notes from Taylors theorem 2026-10-29.pdf")
    part = note.read_text(encoding="utf-8").split("<!-- kurooto:only-from -->", 1)[1]
    assert part.startswith('\n## From "Taylor\'s theorem in two variables" on')


def test_handwritten_only_by_course_file_or_the_last_one(world):
    env = world
    env.app.settings.set("handwritten.overlap", False)
    note = transcribe(env)
    env.fake_ai.answer = link_answer()
    run_all(env)
    out = env.say("/handwritten only mvc from Partial derivatives")
    assert out.startswith("Added the part from 'Partial derivatives' on to handwritten/")
    assert "/handwritten undo takes it back" in out
    text = note.read_text(encoding="utf-8")
    assert '## From "Partial derivatives" on' in text
    out = env.say("/handwritten only mvc from Fourier series")
    assert out.startswith("No heading in handwritten/") and "Its headings: Limits in two variables;" in out
    assert env.say("/handwritten only from page 2").startswith("Added the part from 'Page 2' on")  # the last note
    assert '## From "Page 2" on' in note.read_text(encoding="utf-8")
    assert env.say(f"/handwritten only {SCAN} from Limits in two variables").startswith("Added")
    assert env.say("/handwritten only chemistry from Atoms").startswith("I can't find a handwritten note")
    assert env.say("/handwritten only mvc").startswith("Say which part")
    assert env.say("/handwritten undo").startswith("Took back")
    assert '## From "Page 2" on' in note.read_text(encoding="utf-8")  # the last change only


def test_handwritten_only_for_a_scan_not_written_out_yet(world):
    env = world
    env.app.settings.set("handwritten.link", False)
    env.app.settings.set("handwritten.overlap", False)
    (env.hw.folder() / "week6.pdf").write_bytes(b"%PDF-1.4 fake")
    assert env.say("/handwritten only week6 from Taylor's theorem") == (
        "When week6.pdf is written out, its note gets the part from 'Taylor's theorem' on."
    )
    note = transcribe(env, "week6.pdf")
    assert '## From "Taylor\'s theorem in two variables" on' in note.read_text(encoding="utf-8")


def test_only_from_off(world):
    env = world
    env.app.settings.set("handwritten.only_from", False)
    env.app.settings.set("handwritten.link", False)
    env.app.settings.set("handwritten.overlap", False)
    note = transcribe(env, "week5.pdf", side="only from Partial derivatives")
    assert "only-from" not in note.read_text(encoding="utf-8")
    assert env.say("/handwritten only from Partial derivatives") == "That's off (handwritten.only_from)."


# --------------------------------------------------------------------------------------------- the parts, alone
def test_sections_headings_bold_pages_or_the_whole():
    secs = ho.sections(PAGES)
    assert [(s.title, s.page) for s in secs] == [
        ("Limits in two variables", 1),
        ("Partial derivatives", 1),
        ("Functions of Several Variables", 2),
        ("Taylor's theorem in two variables", 2),
    ]
    bold = ho.sections("**Definition**\nA set.\n\n**Examples**\nOne.\n\n**Examples**\nTwo.")
    assert [s.key for s in bold] == ["definition", "examples", "examples#2"]
    assert [s.title for s in ho.sections("## Page 1\n\nx\n\n## Page 2\n\ny")] == ["Page 1", "Page 2"]
    whole = ho.sections("Just one paragraph of notes.")
    assert len(whole) == 1 and whole[0].line == -1


def test_marks_go_on_and_come_off_cleanly():
    marked = ho.mark(PAGES, {"partialderivatives": "[[zettel/partial-derivatives]]"})
    assert "## Partial derivatives (already in [[zettel/partial-derivatives]])" in marked
    assert hl.unmark(marked) == PAGES
    assert ho.mark(marked, {}) == PAGES  # marked again with nothing: as it was
    md = ho.mark(PAGES, {"partialderivatives": "[Partial derivatives](../zettel/partial-derivatives.md)"})
    assert hl.unmark(md) == PAGES  # Markdown links too
    assert hl.unmark("Text (already in [[x]])") == "Text (already in [[x]])"  # only on headings


def test_topics_are_found_loosely():
    assert ho.find_topic(PAGES, "functions of several variables")[1] == "Functions of Several Variables"
    assert ho.find_topic(PAGES, "Functions of several variable")[1] == "Functions of Several Variables"
    assert ho.find_topic(PAGES, "taylors theorem")[1] == "Taylor's theorem in two variables"
    assert ho.find_topic(PAGES, "page 2")[1] == "Page 2"
    assert ho.find_topic(PAGES, "Fourier series") is None


def test_topics_from_text_files_and_names(tmp_path):
    assert ho.topic_in("only from Functions of Several Variables") == "Functions of Several Variables"
    assert ho.topic_in('From: "Limits"') == "Limits"
    assert ho.topic_in("Limits", sidecar=True) == "Limits" and ho.topic_in("Limits") == ""
    f = tmp_path / "MA201_notes_from_Taylor-series_261029_101500.pdf"
    assert ho.topic_of(f) == "Taylor series"
    assert ho.topic_of(tmp_path / "notes 2026-10-29.pdf") == ""
    (tmp_path / "week.txt").write_text("\nonly from Hessians\n", encoding="utf-8")
    assert ho.topic_of(tmp_path / "week.pdf") == "Hessians"


def test_the_privacy_text_says_what_the_marking_sends(env):
    assert "handwritten.overlap" in env.app.modules["handwritten"].privacy

"""Study notes from an upload as one request (0.9.0, N13; study.notes_workflow): finding the upload, reading it now
with the handwritten reader, the part from a topic on, a study pack unpacked for the AI, filing what it made in the
course's files folder with a source note, the skill and the plain-words request, and the switch. A scratch home and
notes folder; the reader's model and the AI are fakes."""

import os
import re
import threading
import time
from pathlib import Path

import pytest

from kurooto.core import layout, places, studyflow
from kurooto.core import tools as T
from kurooto.modules import skills as sk
from kurooto.providers.context import headless_context

SUBJ = "analysis-two"


class FakeDoc:
    """A PDF of `n` pages the reader can draw (as with Poppler's tools)."""

    def __init__(self, n: int):
        self.n = n
        self.tools = {"pdftoppm": "pdftoppm"}

    def pages(self):
        return self.n

    def images(self, page):
        return []

    def picture(self, page, dpi):
        return (f"page {page}".encode(), "image/png")


PAGES = {
    1: "# Sequences of functions\n\nUniform convergence.",
    2: "# Functions of several variables\n\nLinear maps and the derivative.",
    3: "## Inverse function theorem\n\nIf $f'(a)$ is invertible ...",
}


@pytest.fixture
def world(env, monkeypatch):
    """Zettelkasten notes, Analysis Two (an2) as a subject, the handwritten reader on with a fake model on this
    computer reading a 3-page PDF (page 2 waits for `gate` when it's cleared)."""
    app = env.app
    app.settings.set("notes.layout", "zettelkasten")
    app.settings.set("subjects.list", [{"name": "Analysis Two", "slug": SUBJ, "aliases": ["an2"]}])
    app.settings.set("handwritten.local_model", "fake-vision")
    app.settings.set("handwritten.link", False)
    app.power.current = "normal"
    env.on("subjects", "handwritten")
    hw = app.modules["handwritten"]
    gate = threading.Event()
    gate.set()
    seen: list[str] = []

    def ollama(model, data, prompt=""):
        page = int(re.search(rb"\d+", data)[0])
        if page == 2:
            gate.wait(10)
        seen.append(prompt)
        return PAGES[page]

    monkeypatch.setattr(hw, "_doc", lambda f: FakeDoc(3))
    monkeypatch.setattr(hw, "gpu_room", lambda model: None)
    monkeypatch.setattr(hw, "_ollama", ollama)
    monkeypatch.setattr(studyflow, "POLL_S", 0.05)
    env.hw, env.gate, env.prompts = hw, gate, seen
    yield env
    gate.set()


def scan(env, name="an2-notes.pdf", folder=None, age=60):
    f = (folder or env.hw.folder()) / name
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(b"%PDF-1.4 fake")
    os.utime(f, (time.time() - age, time.time() - age))
    return f


def tool(app, name):
    return next(t for t in T.agent_tools(app) if t.name == name)


# ---------------------------------------------------------------------------------------------- the switch
def test_the_switch_takes_the_tools_the_skill_and_the_request_away(world):
    app = world.app
    names = {t.name for t in T.agent_tools(app)}
    assert {"find_uploads", "read_handwritten", "build_study_pack", "save_course_file", "study_progress"} <= names
    assert sk.load_skill(app, studyflow.SKILL) is not None
    assert studyflow.intent_match(app, "make notes from my an2 notes from functions of several variables")
    assert studyflow.LATEX_RULE in headless_context(app)
    writes = {t.name: t.writes for t in T.agent_tools(app)}
    assert writes["find_uploads"] is False and writes["save_course_file"] is True
    app.settings.set("study.notes_workflow", False)
    names = {t.name for t in T.agent_tools(app)}
    assert not names & {"find_uploads", "read_handwritten", "build_study_pack", "save_course_file", "study_progress"}
    assert sk.load_skill(app, studyflow.SKILL) is None
    assert studyflow.intent_match(app, "make notes from my an2 notes from functions of several variables") is None
    if not studyflow.n2_present():  # the thin compile tool goes with the switch; N2's has its own (tools.latex)
        assert "compile_latex" not in names and studyflow.LATEX_RULE not in headless_context(app)


def test_the_thin_compile_tool_is_there_only_without_n2s(world):
    names = [t.name for t in T.agent_tools(world.app)]
    assert names.count("compile_latex") == 1


# ---------------------------------------------------------------------------------------------- find_uploads
def test_find_uploads_lists_new_scans_by_course_newest_first(world):
    app = world.app
    down = Path.home() / "Downloads"
    down.mkdir(exist_ok=True)
    a = scan(world, "an2 lecture 9.pdf", age=3600)
    b = scan(world, "notes.pdf", folder=app.workspace / "sources" / SUBJ, age=60)
    c = scan(world, "Analysis-Two-week5.pdf", folder=down, age=120)
    scan(world, "an2-old.pdf", age=40 * 86400)  # too old
    scan(world, "stats.pdf", folder=down, age=60)  # another course
    (down / "holiday.jpg").write_bytes(b"x")  # a picture outside the handwritten folder isn't an upload
    out = studyflow.find_uploads(app, "an2")
    assert out.index(str(b.resolve())) < out.index(str(c.resolve())) < out.index(str(a.resolve()))
    assert "an2-old" not in out and "stats.pdf" not in out and "holiday" not in out
    assert "(Downloads," in out and "(handwritten folder," in out
    assert "stats.pdf" in studyflow.find_uploads(app, "", days="2")
    assert studyflow.find_uploads(app, "knitting").startswith("No scans or PDFs for knitting")


# ------------------------------------------------------------------------------------------ read_handwritten
def test_reading_now_gives_the_pages_files_the_note_and_marks_it_done(world):
    app = world.app
    f = scan(world)
    out = tool(app, "read_handwritten").run({"file": str(f)})
    assert out.startswith(f"Transcription of {f.name} (by fake-vision on this computer, 3 pages, unchecked)")
    assert "## Page 2" in out and "Linear maps" in out
    m = re.search(r"written out as the note (\S+\.md)", out)
    assert m and (app.workspace / m[1]).is_file()  # the reader's own note, as its scan would have made
    seen = (app.paths.state / "handwritten.json").read_text(encoding="utf-8")
    assert f.name in seen  # the folder's scan won't read it again
    again = studyflow.read_handwritten(app, str(f), from_topic="functions of several variables")
    assert "From the heading 'Functions of several variables' (page 2) to the end" in again
    assert "Uniform convergence" not in again and "Inverse function theorem" in again


def test_a_long_read_comes_back_with_how_far_it_got_and_carries_on(world, monkeypatch):
    app = world.app
    world.gate.clear()
    told = []
    monkeypatch.setattr(studyflow, "PROGRESS_S", 0)
    monkeypatch.setattr(app, "notify", lambda text, **kw: told.append(text))
    f = scan(world, folder=app.workspace / "uploads")
    out = studyflow.read_handwritten(app, str(f), wait="0.5")
    assert out.startswith(f"Still reading {f.name} (page 2 of 3)") and "call read_handwritten" in out
    assert any(t == f"Reading {f.name}: page 2 of 3." for t in told)
    world.gate.set()
    out = studyflow.read_handwritten(app, str(f), wait="true")
    assert out.startswith(f"Transcription of {f.name}") and "written out as the note" not in out  # not its folder


def test_without_a_model_here_gemini_reads_only_when_allowed_and_marks_pages(world, monkeypatch):
    app = world.app
    hw = world.hw
    app.settings.set("handwritten.local", False)
    app.settings.set("handwritten.cloud", False)
    f = scan(world, folder=app.workspace / "uploads")
    assert "can't read it here" in studyflow.read_handwritten(app, str(f))
    app.settings.set("handwritten.cloud", True)
    app.secrets.set("gemini.api_key", "test-key")
    asked = []
    monkeypatch.setattr(hw, "_gemini", lambda data, mime, prompt="": asked.append(prompt) or "## Page 1\n\nAll.")
    out = studyflow.read_handwritten(app, str(f))
    assert out.startswith(f"Transcription of {f.name} (by Gemini)") and "## Page N" in asked[0]


def test_a_file_outside_the_readable_folders_is_refused(world, tmp_path):
    f = tmp_path / "elsewhere" / "x.pdf"
    f.parent.mkdir()
    f.write_bytes(b"%PDF")
    assert "outside the folders" in studyflow.read_handwritten(world.app, str(f))


def test_the_thin_topic_match_finds_a_heading_loosely():
    text = "## Page 1\n\n# Sequences\n\nx\n\n## Page 2\n\n**Functions of Several Variables:**\n\ny"
    assert studyflow._find_topic(text, "functions of several variable") == (8, "Functions of Several Variables")
    part, where = studyflow.cut_from(text, "knitting")
    assert part == text and where.startswith("No heading matches 'knitting'")


# ------------------------------------------------------------------------------------------ build_study_pack
def test_the_pack_is_unpacked_where_the_ai_can_read_it(world):
    app = world.app
    ws = app.workspace
    (ws / "sources" / SUBJ).mkdir(parents=True, exist_ok=True)
    (ws / "sources" / SUBJ / "inverse-function-theorem.md").write_text("# Inverse function theorem\nProof.", "utf-8")
    out = studyflow.build_study_pack(app, "an2", "inverse function theorem", "deep notes")
    folder = Path(re.search(r"unpacked in (\S+) ", out)[1])
    assert (folder / "PROMPT.md").is_file() and (folder / "notes" / "sources" / SUBJ).is_dir()
    assert "--- PROMPT.md ---" in out and "inverse function theorem" in out
    assert places.inside(folder / "PROMPT.md", places.read_roots(app))
    tex = Path(re.search(r"as LaTeX, at (\S+\.tex)", out)[1])
    assert places.inside(tex, places.write_roots(app)) and not places.inside(tex, [ws])
    assert T.writable(app, str(tex), must_exist=False)[0] == tex.resolve()


# ------------------------------------------------------------------------------------------ save_course_file
def test_filing_puts_the_pdf_in_the_course_files_folder_with_a_source_note(world, tmp_path):
    app = world.app
    files = tmp_path / "files"
    app.settings.set("files.folder", str(files))
    work = places.work_folder(app) / SUBJ
    work.mkdir(parents=True)
    pdf, tex = work / "an2-deep-notes.pdf", work / "an2-deep-notes.tex"
    pdf.write_bytes(b"%PDF made")
    tex.write_text("\\documentclass{article}", "utf-8")
    out = studyflow.save_course_file(app, "an2", str(pdf), title="Several variables: deep notes")
    assert (files / SUBJ / "an2-deep-notes.pdf").read_bytes() == b"%PDF made"
    note = app.workspace / "sources" / SUBJ / "an2-deep-notes.md"
    assert out.startswith(f"Filed {files / SUBJ / 'an2-deep-notes.pdf'}") and note.is_file()
    text = note.read_text(encoding="utf-8")
    assert "trust_tier: agent_written" in text and "# Several variables: deep notes" in text
    assert "an2-deep-notes.pdf" in text and "<!-- kurooto:files -->" in text
    note.write_text(text + "\nMy own line.\n", encoding="utf-8")
    pdf.write_bytes(b"%PDF made again")
    studyflow.save_course_file(app, "an2", str(tex))
    studyflow.save_course_file(app, "an2", str(pdf))  # filed again: replaced, one line each
    text = note.read_text(encoding="utf-8")
    assert text.count("- [an2-deep-notes.pdf]") == 1 and "an2-deep-notes.tex" in text and "My own line." in text
    assert (files / SUBJ / "an2-deep-notes.pdf").read_bytes() == b"%PDF made again"
    assert not list(app.workspace.glob("*.pdf")) and not (app.workspace / "an2-deep-notes.md").exists()


def test_a_file_of_yours_with_the_same_name_is_kept_and_a_copy_goes_where_you_said(world, tmp_path):
    app = world.app
    (Path.home() / "Downloads").mkdir(exist_ok=True)
    dest = layout.file_dir(app, "subject", subject=SUBJ)  # no files folder: inside the notes, never their top
    assert dest != app.workspace and places.inside(dest, [app.workspace])
    dest.mkdir(parents=True)
    (dest / "notes.pdf").write_bytes(b"yours")
    src = places.work_folder(app) / "notes.pdf"
    src.parent.mkdir(parents=True)
    src.write_bytes(b"made")
    out = studyflow.save_course_file(app, "an2", str(src), copy_to="Downloads/Study")
    assert (dest / "notes.pdf").read_bytes() == b"yours" and (dest / "notes-2.pdf").read_bytes() == b"made"
    assert (Path.home() / "Downloads" / "Study" / "notes-2.pdf").read_bytes() == b"made" and "A copy is in" in out
    assert "I can only copy into" in studyflow.save_course_file(app, "an2", str(src), copy_to="/etc")


# ------------------------------------------------------------------------------------- the request and skill
def test_the_plain_words_request_runs_the_skill(world, monkeypatch):
    app = world.app
    from kurooto.modules.skills import Skills

    app.modules["skills"] = Skills(app)
    app.settings.set("modules.enabled", [*app.settings.get("modules.enabled"), "skills"])  # without Chat's AI
    ran = []
    monkeypatch.setattr(Skills, "run", lambda self, name, args="", **kw: ran.append((name, args)) or "job1")
    out = world.say("make notes from my an2 notes from functions of several variables to the end")
    assert out.startswith("Working on it: finding the upload") and ran[0][0] == studyflow.SKILL
    for text in ("make a note that the exam is on friday", "read my notes", "write the notes", "remind me of notes"):
        assert studyflow.intent_match(app, text) is None, text
    skill = sk.load_skill(app, studyflow.SKILL)
    assert skill.effort == "high" and skill.switch == "study.notes_workflow"
    for step in (
        "find_uploads",
        "read_handwritten",
        "build_study_pack",
        "compile_latex",
        "save_course_file",
        "send_file",
        "study_progress",
        "never answer that you can't compile",
    ):
        assert step in skill.body, step


def test_progress_lines_reach_you(world, monkeypatch):
    told = []
    monkeypatch.setattr(world.app, "notify", lambda text, **kw: told.append((text, kw.get("why"))))
    assert tool(world.app, "study_progress").run({"text": "compiling, try 2 of 3"}) == "Told them."
    assert told == [("compiling, try 2 of 3", "asked")]

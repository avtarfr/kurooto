"""Notes layout and files outside the notes (core/layout.py): each layout's places, custom places, headers, links, the
AI's view of it, every feature that writes notes, and that no binary lands in the notes when files.folder is set."""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import time
from pathlib import Path

import pytest

from kurooto.core import layout
from kurooto.core.clock import now
from kurooto.core.config import Settings
from kurooto.modules import daily, recurring
from kurooto.modules import skills as sk
from kurooto.modules.skills import all_skills
from tests.fakes.openai import FakeOpenAI

TODAY = "2026-10-20"
WANT = {  # kind, fields -> (kurooto, zettelkasten)
    ("daily", (("date", TODAY),)): ("journal/2026-10-20.md", "dailies/2026-10-20.md"),
    ("profile", ()): ("about-me/profile.md", "master/profile.md"),
    ("how_to_help", ()): ("about-me/how-to-help-me.md", "master/how-to-help-me.md"),
    ("not_interested", ()): ("about-me/not-interested.md", "master/not-interested.md"),
    ("recurring", ()): ("kurooto/recurring.md", "master/recurring-assessments.md"),
    ("ideas", ()): ("kurooto/ideas.md", "master/ideas.md"),
    ("study_pack_prompt", ()): ("kurooto/study-pack-prompt.md", "master/study-pack-prompt.md"),
    ("skills", ()): ("kurooto/skills", "master/skills"),
    ("prompts", ()): ("prompts", "prompts"),
    ("inbox", ()): ("inbox", "inbox"),
    ("note", (("slug", "an-idea"),)): ("inbox/an-idea.md", "inbox/an-idea.md"),
    ("subject", (("subject", "la"),)): ("la", "sources/la"),
    ("course", (("subject", "la"),)): ("la/course.md", "maps/courses/la.md"),
    ("class_log", (("subject", "la"),)): ("la/class-log.md", "sources/la/class-log.md"),
    ("lecture", (("subject", "la"), ("date", TODAY), ("slug", "rank"))): (
        "la/2026-10-20-rank.md",
        "sources/la/2026-10-20-rank.md",
    ),
    ("concept", (("subject", "la"), ("slug", "rank"))): ("la/rank.md", "zettel/rank.md"),
    ("exam_prep", (("subject", "la"),)): ("la/exam-prep.md", "sources/la/exam-prep.md"),
    ("doubts", (("subject", "la"),)): ("la/doubts.md", "sources/la/doubts.md"),
    ("home", ()): ("index.md", "maps/index.md"),
    ("research", ()): ("research/index.md", "maps/research.md"),
    ("project", (("project", "thesis"),)): ("research/thesis/index.md", "projects/thesis/index.md"),
    ("runs", (("project", "thesis"),)): ("research/thesis/runs", "projects/thesis/runs"),
    ("handwritten", ()): ("handwritten", "handwritten"),
    ("mail", (("date", TODAY), ("time", "0700"))): ("mail/2026-10-20-0700.md", "digests/mail-2026-10-20-0700.md"),
}
BINARY = {".pdf", ".jpg", ".jpeg", ".png", ".ogg", ".tex", ".heic", ".webp"}


def lay(tmp_path, preset="kurooto", **settings) -> layout.Layout:
    s = Settings(tmp_path / "settings.json")
    s.set("notes.layout", preset)
    for k, v in settings.items():
        s.set(k.replace("__", "."), v)
    return layout.Layout(tmp_path / "notes", s, "Kurooto", tmp_path / "data")


# ---------------------------------------------------------------------------------------------- places
@pytest.mark.parametrize("preset,col", [("kurooto", 0), ("zettelkasten", 1)])
def test_each_layout_puts_every_kind_in_its_place(tmp_path, preset, col):
    L = lay(tmp_path, preset)
    for (kind, fields), want in WANT.items():
        assert L.rel(kind, **dict(fields)) == want[col], kind
        assert L.path(kind, **dict(fields)) == tmp_path / "notes" / want[col]
    assert set(layout.KINDS) == {k for k, _ in WANT}  # every kind is covered here


def test_the_default_layout_needs_no_settings_and_matches_the_old_folders(tmp_path):
    L = layout.of(tmp_path)  # a plain notes folder: the default layout
    assert L.preset == "kurooto" and L.is_default() and L.files_root() is None
    assert L.link("project", project="thesis") == "research/thesis/index"
    assert L.rel("daily").startswith(f"journal/{now():%Y-%m-%d}")  # today by default
    assert L.describe() == "" and L.translate("see journal/<YYYY-MM-DD>") == "see journal/<YYYY-MM-DD>"
    with pytest.raises(ValueError):
        L.path("course")  # a subject is needed
    assert lay(tmp_path, "nonsense").preset == "kurooto"


def test_custom_places_and_their_guard_rails(tmp_path):
    L = lay(
        tmp_path,
        "zettelkasten",
        notes__paths={
            "daily": "diary/{date}",
            "ideas": str(tmp_path / "elsewhere" / "backlog.md"),
            "course": "../../outside/{subject}.md",
            "lecture": "{nope}/{slug}.md",
        },
    )
    assert L.rel("daily", date=TODAY) == "diary/2026-10-20.md"  # .md added
    assert L.path("ideas") == tmp_path / "elsewhere" / "backlog.md"  # your own place outside the notes
    assert L.rel("course", subject="la") == "maps/courses/la.md"  # can't climb out: the layout's own place
    assert L.rel("lecture", subject="la", date=TODAY, slug="x") == "sources/la/2026-10-20-x.md"  # {nope}: the layout's
    assert L.rel("lecture", subject="../../etc", date=TODAY, slug="..x") == "sources/-..-etc/2026-10-20-x.md"
    problems = L.check()
    assert any("notes.paths.course" in p for p in problems) and any("notes.paths.lecture" in p for p in problems)
    assert any("isn't a layout" in p for p in lay(tmp_path, "mine").check())


# ----------------------------------------------------------------------------------------------- files
def test_files_go_outside_the_notes_when_files_folder_is_set(tmp_path):
    files = tmp_path / "files"
    k = lay(tmp_path)
    assert k.file_dir("inbox") == tmp_path / "notes" / "inbox"  # as before
    assert k.file_dir("subject", subject="la") == tmp_path / "notes" / "la" / "files"
    assert k.file_dir("pack", subject="la") == tmp_path / "notes" / "la"
    assert k.file_dir("classroom", subject="la") == tmp_path / "data" / "classroom" / "la"
    assert k.file_dir("handwritten") == tmp_path / "notes" / "handwritten"
    z = lay(tmp_path, "zettelkasten")
    assert z.file_dir("subject", subject="la") == tmp_path / "notes" / "attachments" / "la"
    for L in (lay(tmp_path, files__folder=str(files)), lay(tmp_path, "zettelkasten", files__folder=str(files))):
        assert not L.is_default() and L.files_root() == files
        for kind, (_, fields) in layout.FILE_KINDS.items():
            d = L.file_dir(kind, **{f: "la" for f in fields})
            assert d.is_relative_to(files) and not L.inside_notes(d), kind
        assert L.file_dir("classroom", subject="la") == files / "la"
        assert L.file_path("inbox", "../../x.pdf") == files / "inbox" / "-..-x.pdf"
    assert any("inside the notes" in p for p in lay(tmp_path, files__folder=str(tmp_path / "notes" / "f")).check())


def test_links_to_files_follow_the_layout(tmp_path):
    files = tmp_path / "files"
    k = lay(tmp_path, files__folder=str(files))
    note = k.path("class_log", subject="la")
    assert k.file_link(files / "la" / "a b.jpg", note) == "![a b.jpg](../../files/la/a%20b.jpg)"
    assert k.file_link(tmp_path / "notes" / "la" / "files" / "x.pdf", note) == "[x.pdf](files/x.pdf)"
    z = lay(tmp_path, "zettelkasten", files__folder=str(files))
    pdf = files / "la" / "x.pdf"
    assert z.file_link(pdf, z.path("class_log", subject="la")) == f"[x.pdf]({pdf.as_uri()})"
    assert z.file_link(files / "la" / "p.png", z.path("daily")).startswith("[p.png](file://")  # no embed for file://
    z2 = lay(tmp_path, "zettelkasten", files__folder=str(files), files__links="relative")
    assert z2.file_link(pdf, z2.path("daily", date=TODAY)) == "[x.pdf](../../files/la/x.pdf)"


# --------------------------------------------------------------------------------------------- headers
def test_headers_follow_the_layout(tmp_path):
    k = lay(tmp_path)
    head = k.frontmatter("exam_prep", k.path("exam_prep", subject="la"), title="Exam prep: LA", subject="la")
    assert head == f"---\nmade_by: Kurooto\ndate: {now():%Y-%m-%d}\ntags: [exam-prep]\n---\n\n"
    assert k.frontmatter("daily", k.path("daily"), bare=True) == ""
    z = lay(tmp_path, "zettelkasten")
    f = z.path("lecture", subject="la", date=TODAY, slug="rank")
    head = z.frontmatter("lecture", f, title="Rank: nullity", subject="la", date=TODAY)
    assert head == (
        '---\nid: sources/la/2026-10-20-rank\naliases: ["Rank: nullity"]\ntags: [source, la, lecture]\n'
        "trust_tier: agent_written\ndate: 2026-10-20\n---\n\n"
    )
    daily_head = z.frontmatter("daily", z.path("daily", date=TODAY), agent=False, bare=True)
    assert daily_head == "---\nid: dailies/2026-10-20\naliases: []\ntags: [daily-notes]\n---\n\n"


# ---------------------------------------------------------------------------------------------- the AI
def test_skills_are_translated_and_the_ai_is_told(env, tmp_path):
    app = env.app
    app.settings.set("notes.layout", "zettelkasten")
    app.settings.set("files.folder", str(tmp_path / "files"))
    z = layout.of(app)
    for s in all_skills(app).values():
        if s.source != "shipped":
            continue
        out = z.translate(s.body)
        for old in ("journal/<", "<subject>/course", "<subject>/exam-prep", "about-me/", "kurooto/", "<folder>/course"):
            assert not re.search(r"(?<![\w./-])" + re.escape(old), out), (s.name, old)
    t = z.translate(
        "`journal/<YYYY-MM-DD>`, `<subject>/course`, `<subject>/<concept-slug>`, `<subject>/<YYYY-MM-DD>-x`, "
        "`research/<project>/index`, `research/index`, `about-me/how-to-help-me`, `mail/<name>`, `linear-algebra/`"
    )
    assert t == (
        "`dailies/<YYYY-MM-DD>`, `maps/courses/<subject>`, `zettel/<concept-slug>`, "
        "`sources/<subject>/<YYYY-MM-DD>-x`, `projects/<project>/index`, `maps/research`, `master/how-to-help-me`, "
        "`digests/mail-<name>`, `linear-algebra/`"
    )
    prompt = sk.build(app, all_skills(app)["study-log"], "LA today")
    assert "dailies/<YYYY-MM-DD>" in prompt and "journal/<" not in prompt
    from kurooto.providers.context import headless_context

    ctx = headless_context(app)
    assert "dailies/<YYYY-MM-DD>" in ctx and str(tmp_path / "files") in ctx and "trust_tier: agent_written" in ctx


# ---------------------------------------------------------------------------------- every writer, moved
@pytest.fixture
def zk(env, tmp_path):
    """The zettelkasten layout with a files folder outside the notes."""
    files = tmp_path / "outside-files"
    env.app.settings.set("notes.layout", "zettelkasten")
    env.app.settings.set("files.folder", str(files))
    env.app.settings.set("notify.desktop", False)
    return env, files


@pytest.fixture
def ai(env):
    fake = FakeOpenAI()
    app = env.app
    app.secrets.set("custom.api_key", fake.key)
    app.settings.set("brain.base_urls", {"custom": fake.base})
    app.settings.set("brain.models", {"custom": {"low": "m", "medium": "m", "high": "m"}})
    app.settings.set("brain.main", "custom")
    yield fake
    fake.close()


def binaries_in(root: Path) -> list[str]:
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.suffix.lower() in BINARY)


def wait_for(cond, secs=5.0):
    end = time.time() + secs
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.05)
    return False


def test_every_writer_follows_the_zettelkasten_layout(zk, ai, monkeypatch):
    env, files = zk
    app, ws = env.app, env.app.workspace
    day = now().date().isoformat()
    # the daily note (check-ins, study hours, the alarm, the Sunday review all go through daily.append)
    f = daily.append(app, "Evening check-in", "good day")
    assert f == ws / "dailies" / f"{day}.md"
    assert f.read_text().startswith(f"---\nid: dailies/{day}\naliases: []\ntags: [daily-notes]\n---\n\n# {day}\n")
    assert daily.morning_view(app)["note"] == f"dailies/{day}"
    # profile, how-to-help-me, not interested, recurring, ideas, your skills and prompts
    assert app.about.profile_file == ws / "master" / "profile.md"
    from kurooto.core.notinterested import add_topic, ignored_topics
    from kurooto.modules.remember import Remember, help_file

    assert add_topic(app, "drama club") and ignored_topics(app) == ["drama club"]
    text = (ws / "master" / "not-interested.md").read_text()
    assert text.startswith("---\nid: master/not-interested\n") and "trust_tier: agent_written" in text
    app.modules.setdefault("remember", Remember(app))
    env.on("remember")
    assert env.say("/remember I like short answers").startswith("Noted in master/how-to-help-me.md")
    assert help_file(app) == ws / "master" / "how-to-help-me.md" and help_file(app).is_file()
    assert recurring.note_file(app) == ws / "master" / "recurring-assessments.md"
    assert app.modules["deadlines"].recurring_note == recurring.note_file(app)
    assert sk.user_dir(app) == ws / "master" / "skills"
    retro = app.modules["retro"]
    assert retro._apply("p1", {"type": "idea", "idea": "a weekly plan", "text": "x"}, {}).startswith(
        "Added to master/ideas.md"
    )
    assert retro._skill_path("journal")[1] == ws / "master" / "skills" / "journal" / "SKILL.md"
    # quick notes and prompts
    from kurooto.modules.library import capture, prompts

    pdf = files / "inbox" / "sheet.pdf"
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(b"%PDF")
    q = capture(app, "remember the ideal gas law", files=[pdf])
    assert q.parent == ws / "inbox" and f"({pdf.as_uri()})" in q.read_text()
    assert q.read_text().startswith("---\nid: inbox/") and "trust_tier" not in q.read_text()  # your words
    (ws / "prompts").mkdir()
    (ws / "prompts" / "summarise.md").write_text("Summarise in 5 bullets.")
    assert [p["name"] for p in prompts(app)] == ["summarise"]
    # research: projects and the hub, runs
    from kurooto.modules.research import ensure_project, log_lines
    from kurooto.runlog import Runlog

    note = ensure_project(app, "Thesis")
    assert note == ws / "projects" / "thesis" / "index.md" and note.read_text().startswith("---\nid: projects/")
    assert "[[projects/thesis/index|Thesis]]" in (ws / "maps" / "research.md").read_text()
    assert log_lines(app, "Thesis", ["- **2026-10-20** | a run"]) == 1
    assert Runlog(app.paths, app).runs_dir("Thesis") == ws / "projects" / "thesis" / "runs"
    # Classroom: exam prep, the batch text, the course files folder; mail digests
    from kurooto.core import places
    from kurooto.modules.google_classroom import write_exam_prep

    assert write_exam_prep(app, "la", "## Must know\n- rank", "Linear Algebra", app.name) == (
        "Updated sources/la/exam-prep.md."
    )
    assert (ws / "sources/la/exam-prep.md").read_text().startswith("---\nid: sources/la/exam-prep\n")
    cn = app.modules["classroom_notes"]
    assert cn.files_dir == files and places.course_files(app) == files
    assert "course page maps/courses/la.md" in cn.render({"course": "Linear Algebra", "folder": "la", "items": []})
    md = app.modules["mail_digest"]
    out = md.render({"at": f"{day}T07:00:00", "messages": [], "counted": {}})
    assert f"yes, as digests/mail-{day}-0700.md" in out
    assert files in places.write_roots(app)
    # the AI's write_note follows the layout's header
    from kurooto.core.tools import run_tool

    env.on("chat")
    assert run_tool(app, "write_note", {"slug": "zettel/rank", "text": "# Rank\n\nThe dimension."}).startswith(
        "Created"
    )
    assert (
        (ws / "zettel/rank.md")
        .read_text()
        .startswith("---\nid: zettel/rank\naliases: [Rank]\ntags: []\ntrust_tier: agent_written\n---\n\n# Rank")
    )
    assert binaries_in(ws) == []


def test_no_binary_lands_in_the_notes_when_files_folder_is_set(zk, ai, monkeypatch):
    env, files = zk
    app, ws = env.app, env.app.workspace
    day = now().date().isoformat()
    # Telegram: a document and a photo, with Files on (no AI: saved, and where it went is said in full)
    env.on("files")
    env.fake.files["docs/F1.pdf"] = b"%PDF syllabus"
    out = env.say("", document={"file_id": "F1", "file_name": "syllabus.pdf"})
    assert out.startswith(f"Saved to {files / 'inbox'}")
    assert len(list((files / "inbox").glob("*syllabus.pdf"))) == 1
    # the phone app's share
    up = app.modules["calls"]._upload({"name": ["scan.pdf"]}, b"%PDF scan")
    assert up[0] == 200 and up[1]["saved"].startswith(str(files / "inbox"))
    # after class: the photo moves to the subject's files folder, the log links it
    app.settings.set("subjects.list", [{"slug": "linear-algebra", "name": "Linear Algebra", "aliases": ["LA"]}])
    env.on("subjects", "capture")
    cap = app.modules["capture"]
    photo = next((files / "inbox").glob("*syllabus.pdf"))
    assert cap.save("linear-algebra", day, "rank-nullity", [photo]) == (
        "Saved to sources/linear-algebra/class-log.md with 1 file(s)."
    )
    kept = list((files / "linear-algebra").glob("*syllabus.pdf"))
    log = (ws / "sources/linear-algebra/class-log.md").read_text()
    assert len(kept) == 1 and kept[0].as_uri() in log and "rank-nullity" in log
    # handwriting: the note in the notes, the original in the files folder
    from tests.fakes.cloud import FakeCloud

    cloud = FakeCloud()
    try:
        app.secrets.set("gemini.api_key", "k")
        app.settings.set("voice_notes.api_base", cloud.base)
        cloud.transcript = "# Eigenvalues\n\n$$Av = \\lambda v$$"
        env.on("handwritten")
        hw = app.modules["handwritten"]
        assert hw.folder() == files / "handwritten-inbox"
        scan = hw.folder() / "page.pdf"
        scan.write_bytes(b"%PDF page")
        os.utime(scan, (time.time() - 60, time.time() - 60))
        done = hw.scan()
        assert done == [f"handwritten/{day}-eigenvalues.md"]
        assert (files / "handwritten" / f"{day}-eigenvalues.pdf").read_bytes() == b"%PDF page"
        assert (files / "handwritten" / f"{day}-eigenvalues.pdf").as_uri() in (ws / done[0]).read_text()
    finally:
        cloud.close()
    # a revision pack: LaTeX and PDF in the files folder, linked from the daily note and the course page
    from kurooto.modules.skills import Skills

    app.modules["skills"] = Skills(app)
    env.on("chat", "skills")
    course = ws / "maps/courses/linear-algebra.md"
    course.parent.mkdir(parents=True)
    course.write_text("# Linear Algebra\n")
    monkeypatch.setattr(sk, "tectonic", lambda app: "/fake/tectonic")

    def fake_compile(app, tex, timeout=900):
        tex.with_suffix(".pdf").write_bytes(b"%PDF-1.7 fake")
        return True, ""

    monkeypatch.setattr(sk, "compile_tex", fake_compile)
    env.say("/pack la midterm")
    ai.answer = "```latex\n\\documentclass{article}\\begin{document}x\\end{document}\n```"
    app.jobs.run_next()
    assert "maps/courses/linear-algebra" in ai.requests[-1]["messages"][-1]["content"]
    pdf = files / "linear-algebra" / f"revision-pack-{day}.pdf"
    assert wait_for(lambda: pdf.is_file() and "Revision packs" in course.read_text())
    assert pdf.as_uri() in (ws / "dailies" / f"{day}.md").read_text() and pdf.as_uri() in course.read_text()
    assert pdf.with_suffix(".tex").is_file()
    # nothing binary (or LaTeX) anywhere in the notes
    assert binaries_in(ws) == []
    assert len(binaries_in(files)) >= 5


def test_default_layout_keeps_files_in_the_notes_as_before(env):
    app, ws = env.app, env.app.workspace
    env.on("files")
    env.fake.files["docs/F2.pdf"] = b"%PDF"
    assert env.say("", document={"file_id": "F2", "file_name": "a.pdf"}).startswith("Saved to inbox/")
    assert app.modules["classroom_notes"].files_dir == app.paths.data / "classroom"
    assert daily.note_path(app) == ws / "journal" / f"{now():%Y-%m-%d}.md"
    assert layout.describe(app) == ""


# ------------------------------------------------------------------------------------ /observing +7 days
def test_observing_has_a_seven_more_days_button(env, ai):
    app = env.app
    app.settings.set("notify.desktop", False)
    env.on("chat", "retro")
    env.say("/observe whether I sleep better for 3 days")
    o = app.modules["retro"].observations()[0]
    env.say("/observing")
    msg = [p for m, p in env.fake.sent if m == "sendMessage" and p.get("reply_markup")][-1]
    stop, more = msg["reply_markup"]["inline_keyboard"][0]
    assert stop["callback_data"] == f"obs:{o['id']}:stop" and more["text"] == "+7 days"
    before = dt.datetime.fromisoformat(o["until"])
    assert env.press(more["callback_data"]).startswith(f"Watching until {before + dt.timedelta(days=7):%a %d %b}")
    assert dt.datetime.fromisoformat(app.modules["retro"].observations()[0]["until"]) == before + dt.timedelta(days=7)
    env.press(stop["callback_data"])
    assert env.press(more["callback_data"]) == "That isn't being watched any more."
    assert json.loads(json.dumps(app.modules["retro"].observations()))[0]["status"] == "stopped"

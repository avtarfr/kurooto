"""Sending files for real (not their paths) and study packs: a subject's notes and course files in a zip with a prompt
for another AI. Fakes only."""

import zipfile
from pathlib import Path

import pytest

from kurooto.core import layout, studypack
from kurooto.modules import skills as sk
from kurooto.modules.library import Library
from kurooto.modules.skills import Skills
from tests.fakes.openai import FakeOpenAI


@pytest.fixture
def chat_on(env):
    """The paired assistant with a fake AI, Chat and Skills on (as in test_skills)."""
    fake = FakeOpenAI()
    app = env.app
    app.secrets.set("custom.api_key", fake.key)
    app.settings.set("brain.base_urls", {"custom": fake.base})
    app.settings.set("brain.models", {"custom": {"low": "m", "medium": "m", "high": "m"}})
    app.settings.set("brain.main", "custom")
    app.modules["skills"] = Skills(app)
    app.modules["library"] = Library(app)
    env.on("chat", "skills", "library")
    yield fake
    fake.close()


def docs(env):
    return [p for m, p in env.fake.sent if m == "sendDocument"]


def seed(env):
    app = env.app
    env.on("subjects")
    env.say("/subject add Deep Learning (dl)")
    ws = app.workspace
    (ws / "sources" / "deep-learning").mkdir(parents=True)
    (ws / "sources" / "deep-learning" / "lecture-1.md").write_text("# CNNs\nConvolutions.", encoding="utf-8")
    (ws / "zettel").mkdir()
    (ws / "zettel" / "equivariance.md").write_text("Linked from [[sources/deep-learning/lecture-1]].", encoding="utf-8")
    (ws / "zettel" / "unrelated.md").write_text("Nothing here.", encoding="utf-8")
    files = layout.file_dir(app, "classroom", subject="deep-learning")
    files.mkdir(parents=True)
    (files / "slides-1.pdf").write_bytes(b"%PDF slides one")
    (files / "slides-2.PDF").write_bytes(b"%PDF slides two")
    (files / ".hidden.pdf").write_bytes(b"%PDF no")
    (files / "movie.mp4").write_bytes(b"x" * 10)
    return files


def test_a_study_pack_holds_the_notes_the_files_the_index_and_a_prompt(chat_on, env):
    seed(env)
    path, info = studypack.build(env.app, "deep-learning", "Deep Learning", "quiz on Thursday")
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        prompt = z.read("PROMPT.md").decode()
    assert "notes/sources/deep-learning/lecture-1.md" in names and "notes/zettel/equivariance.md" in names
    assert "notes/zettel/unrelated.md" not in names  # a note that doesn't touch the subject stays out
    assert {"class/slides-1.pdf", "class/slides-2.PDF", "INDEX.md", "PROMPT.md"} <= names
    assert not any("hidden" in n or "movie" in n for n in names)
    assert "What it's for: quiz on Thursday." in prompt and "Deep Learning" in prompt
    assert info["notes"] == 2 and info["files"] == 2 and not info["left_out"]


def test_a_pack_over_the_telegram_limit_leaves_files_out_and_says_so(chat_on, env, monkeypatch):
    seed(env)
    monkeypatch.setattr(studypack, "MAX_ZIP", 20)  # two small pdfs can't both fit after the notes
    path, info = studypack.build(env.app, "deep-learning")
    assert info["left_out"]
    with zipfile.ZipFile(path) as z:
        assert "Left out" in z.read("INDEX.md").decode()


def test_nothing_to_pack_says_so(chat_on, env):
    try:
        studypack.build(env.app, "knitting", "Knitting")
    except ValueError as e:
        assert "no notes or course files" in str(e)
    else:
        raise AssertionError("expected ValueError")


def test_the_command_sends_the_zip_to_telegram_and_uses_the_rest_as_the_aim(chat_on, env):
    seed(env)
    out = env.say("/studypack deep learning quiz on thursday")
    assert "2 notes and 2 course files" in out
    assert len(docs(env)) == 1
    with zipfile.ZipFile(env.app.paths.cache / "study-packs" / "deep-learning-study-pack.zip") as z:
        assert "quiz on thursday" in z.read("PROMPT.md").decode()


def test_several_files_arrive_as_one_zip_and_one_or_two_as_they_are(chat_on, env):
    files = seed(env)
    (files / "a.pdf").write_bytes(b"%PDF a")
    ok, msg = sk.send_files(env.app, [files / "slides-1.pdf"], inside=[env.app.workspace.parent])
    assert ok and len(docs(env)) == 1
    ok, msg = sk.send_files(
        env.app,
        [files / "slides-1.pdf", files / "slides-2.PDF", files / "a.pdf"],
        "three",
        inside=[env.app.workspace.parent],
        zip_name="dl files",
    )
    assert ok and "3 files in one zip" in msg and len(docs(env)) == 2


def test_files_outside_the_allowed_folders_are_refused(chat_on, env, tmp_path):
    outside = tmp_path / "elsewhere.txt"
    outside.write_text("private")
    ok, msg = sk.send_files(env.app, [outside, outside], inside=[env.app.workspace])
    assert not ok and "only send files from the notes folder" in msg
    assert not docs(env)


def test_the_tools_send_files_and_never_just_paths(chat_on, env):
    files = seed(env)
    skills = env.app.modules["skills"]
    tools = {t.name: t for t in skills.call_tools()}
    assert {"send_file", "send_files", "study_pack"} <= set(tools)
    out = skills._tool_send_many({"paths": f"file://{files / 'slides-1.pdf'}\n{files / 'slides-2.PDF'}\n"})
    assert "slides-1.pdf" in out and len(docs(env)) == 2
    out = skills._tool_study_pack({"subject": "dl", "aim": "midsem"})
    assert "course files in one zip" in out and len(docs(env)) == 3


def test_the_prompt_comes_as_its_own_message_next_to_the_zip(chat_on, env):
    seed(env)
    env.say("/studypack deep learning quiz on thursday")
    texts = " ".join(t or "" for t in env.fake.texts())
    assert "What it's for: quiz on thursday." in texts and "Write advanced, rigorous study notes" in texts
    assert len(docs(env)) == 1  # the zip; the prompt is a message, not a second file


class FakeDrive:
    """Drive upload, on: records what would go to Drive."""

    id = "drive_upload"

    def __init__(self):
        self.sent = []

    def setting(self, k):
        return {"big_files": True, "temp_days": 7}.get(k)

    def send(self, path, caption="", wait=False, temporary=False):
        self.sent.append((path.name, path.stat().st_size, temporary))
        return True, f"Uploading {path.name} to your Google Drive; the link comes when it's done."


def drive_on(env, monkeypatch):
    drive = FakeDrive()
    monkeypatch.setitem(env.app.modules, "drive_upload", drive)
    real = env.app.is_on
    monkeypatch.setattr(env.app, "is_on", lambda mid: True if mid == "drive_upload" else real(mid))
    return drive


def test_with_drive_upload_on_a_big_pack_leaves_nothing_out_and_goes_as_a_temporary_link(chat_on, env, monkeypatch):
    seed(env)
    drive = drive_on(env, monkeypatch)
    monkeypatch.setattr(sk, "TELEGRAM_MAX", 10)  # every pack is "too big for Telegram" here
    out = env.say("/studypack deep learning")
    assert "didn't fit" not in out and "Google Drive" in out
    assert drive.sent and drive.sent[0][0] == "deep-learning-study-pack.zip" and drive.sent[0][2] is True
    with zipfile.ZipFile(env.app.paths.cache / "study-packs" / "deep-learning-study-pack.zip") as z:
        assert "Left out" not in z.read("INDEX.md").decode()


def test_many_files_over_the_limit_go_to_drive_instead_of_being_refused(chat_on, env, monkeypatch):
    files = seed(env)
    (files / "a.pdf").write_bytes(b"%PDF a" * 10)
    drive = drive_on(env, monkeypatch)
    monkeypatch.setattr(sk, "TELEGRAM_MAX", 40)
    ok, msg = sk.send_files(
        env.app, [files / "slides-1.pdf", files / "slides-2.PDF", files / "a.pdf"], inside=[env.app.workspace.parent]
    )
    assert ok and "Google Drive" in msg and drive.sent[-1][2] is True


def test_temporary_drive_files_are_deleted_when_their_days_are_up(env, monkeypatch):
    """Each as the account that uploaded it, and only while it's still in Kurooto's folder (the upload message says
    moving it out keeps it)."""
    import json

    from kurooto.modules.google_drive import DriveUpload

    d = DriveUpload(env.app)
    calls, parents = [], {"old1": ["kf-main"], "moved1": ["my-own"], "school1": ["kf-school"], "gone1": ["kf-x"]}

    class G:
        def __init__(self, account):
            self.account = account

        def api(self, service, path, body=None, method=None, raw=0):
            calls.append((self.account, path, method))
            fid = path.split("/")[2].split("?")[0]
            return {} if method == "DELETE" else {"parents": parents[fid], "trashed": False}

    env.app.settings.set("google.accounts", ["main", "school"])
    monkeypatch.setattr(DriveUpload, "_as", lambda self, account: G(account))
    who = {"a": "main"}
    monkeypatch.setattr(DriveUpload, "account", property(lambda self: who["a"]))
    d.remember_temporary("old1", "pack.zip", "kf-main")
    d.remember_temporary("moved1", "kept.zip", "kf-main")
    d.remember_temporary("new1", "other.zip", "kf-main")
    d.remember_temporary("gone1", "forgotten.zip", "kf-x")
    who["a"] = "school"
    d.remember_temporary("school1", "big.zip", "kf-school")
    who["a"] = "main"  # Drive upload moved back to main since
    rows = json.loads(d.temp_file.read_text())
    for r in rows:
        r["delete_at"] = 0 if r["id"] != "new1" else r["delete_at"]
    rows[3]["account"] = "old"  # an account whose sign-in was forgotten
    d.temp_file.write_text(json.dumps(rows))
    assert d.expire() == 2
    deletes = [(a, p) for a, p, m in calls if m == "DELETE"]
    assert deletes == [("main", "/files/old1"), ("school", "/files/school1")]  # not the moved one
    assert not any(a == "old" for a, _, _ in calls)
    assert [r["id"] for r in json.loads(d.temp_file.read_text())] == ["new1"]


# ------------------------------------------------------------------------------ a topic, class first
def test_topics_come_from_what_follows_on_or_the_words_that_arent_filler():
    assert studypack.topics_of("quiz on thermodynamics and radiation") == ["thermodynamics", "radiation"]
    assert studypack.topics_of("upcoming quiz thermodynamics") == ["thermodynamics"]
    assert studypack.topics_of("quiz on thursday") == [] and studypack.topics_of("midsem friday 9am") == []
    assert studypack.topics_of("exam on lapse rate, convection for friday") == ["lapse rate", "convection"]
    rx = studypack.pattern(["thermodynamics", "lapse rate"])
    assert (
        rx.search("the first law of Thermodynamic systems") and rx.search("dry lapse-rates") and not rx.search("lapse")
    )


def test_class_material_and_books_are_told_apart_by_length_and_title():
    assert studypack.is_class("Phys_atmosphere_Lecture4.pdf", 23)
    assert studypack.is_class("Complete_Physics_of_the_Atmosphere_Midsem_Notes.pdf", 57)
    assert studypack.is_class("Radiative_Balance.pdf", 29)  # short: class, whatever it's called
    assert not studypack.is_class("Physics of the Atmosphere and Climate -Salby.pdf", 717)
    assert not studypack.is_class("salby_ch8.pdf", 63)  # a chapter of a book
    assert not studypack.is_class("Thermal Physics of the Atmosphere ( PDFDrive ).pdf", 15)  # a book's sample
    assert not studypack.is_class("Atmospheric Dynamics.pdf", 60)  # 41-80 pages, title says nothing: a book
    assert studypack.is_class("handout.pdf", size=3 << 20) and not studypack.is_class("big.pdf", size=30 << 20)


def seed_books(env):
    """Physics of the Atmosphere: two lectures and a book Books has read, and notes."""
    import json

    app = env.app
    env.on("subjects")
    env.say("/subject add Physics of the Atmosphere (pota)")
    src = app.workspace.parent / "pdfs"
    src.mkdir()
    store = app.paths.data / "book-text" / "physics-of-the-atmosphere"

    def read(fid, fname, pages):
        f = src / fname
        f.write_bytes(b"%PDF " + fname.encode())
        d = store / fid
        (d / "pages").mkdir(parents=True)
        for i, text in enumerate(pages, 1):
            (d / "pages" / f"{i:05d}.md").write_text(text, encoding="utf-8")
        (d / "meta.json").write_text(json.dumps({"file": str(f), "title": fid, "pages": len(pages)}), encoding="utf-8")

    read("lecture-3", "Lecture3.pdf", ["Thermodynamics of dry air", "The first law, thermodynamic potentials"])
    read("lecture-5", "Lecture 5 Radiation.pdf", ["Radiation fundamentals", "Planck's law"])
    book = ["Preface"] * 100
    book[29] = "# 2 Thermodynamics\nThe thermodynamic state and thermodynamics of moist air."
    book[59] = "Clouds and radiation."
    read("salby", "Physics of the Atmosphere -Salby.pdf", book)
    ws = app.workspace
    (ws / "zettel").mkdir()
    (ws / "zettel" / "potential-temperature.md").write_text(
        "# Potential temperature\n- derived from:: [[zettel/first-law-of-thermodynamics]]", "utf-8"
    )
    (ws / "zettel" / "planck-law.md").write_text("# Planck's law\nRadiation.", "utf-8")


def test_a_topic_pack_takes_class_files_about_it_whole_and_only_the_books_pages_about_it(chat_on, env):
    seed_books(env)
    path, info = studypack.build(env.app, "physics-of-the-atmosphere", "POTA", "quiz on thermodynamics")
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        book = z.read("books/salby-pages.md").decode()
        index, prompt = z.read("INDEX.md").decode(), z.read("PROMPT.md").decode()
    assert "class/Lecture3.pdf" in names and not any("Radiation" in n for n in names)  # the other lecture stays out
    assert "<!-- page 30 -->" in book and "<!-- page 29 -->" in book and "page 60 -->" not in book
    assert "notes/zettel/potential-temperature.md" in names and "notes/zettel/planck-law.md" not in names
    assert index.index("Class material (first)") < index.index("## Books") and "pages 29-31 of 100" in index
    assert "narrowed to **thermodynamics**" in prompt and "follow the class" in prompt
    assert info["class"] == 1 and info["books"] == 1 and info["topics"] == ["thermodynamics"]
    # without a topic the book stays out (its whole text would flood the other AI's context); the lectures go in
    path, info = studypack.build(env.app, "physics-of-the-atmosphere", "POTA", "")
    with zipfile.ZipFile(path) as z:
        names, index = set(z.namelist()), z.read("INDEX.md").decode()
    assert (
        not any(n.startswith("books/") for n in names)
        and {"class/Lecture3.pdf", "class/Lecture 5 Radiation.pdf"} <= names
    )
    assert "Books not packed whole" in index and "salby (100 pages): name a topic" in index and not info["left_out"]
    with pytest.raises(ValueError, match="nothing about knitting"):
        studypack.build(env.app, "physics-of-the-atmosphere", "POTA", topics=["knitting"])


def test_the_command_narrows_to_a_topic_and_the_tool_takes_topics(chat_on, env):
    seed_books(env)
    out = env.say("/studypack pota quiz on thermodynamics")
    assert out.startswith("On thermodynamics: 1 class files first, then 1 book extracts")
    sk_mod = env.app.modules["skills"]
    out = sk_mod._tool_study_pack({"subject": "pota", "topics": "thermodynamics, radiation"})
    assert out.startswith("On thermodynamics, radiation: 2 class files")


def test_a_book_gives_its_chapters_on_the_topic_whole_before_scattered_pages(tmp_path):
    d = tmp_path / "book"
    (d / "pages").mkdir(parents=True)
    for i in range(1, 61):
        text = "Clouds and droplets" if i == 50 else ("convection here and convection there" if i in (5, 6) else "x")
        (d / "pages" / f"{i:05d}.md").write_text(text, encoding="utf-8")
    s = studypack.Source(None, "Book", 60, d, is_class=False)
    s.chapters = [
        [1, "CHAPTER NINE: Aerosol and cloud", 40, 55],
        [2, "9.2 Droplet growth", 44, 48],
        [1, "Other", 1, 39],
    ]
    pages = studypack.book_pages(s, studypack.pattern(["cloud", "convection"]))
    assert set(range(40, 56)) <= set(pages)  # the matching chapter, whole
    assert {4, 5, 6, 7} <= set(pages) and 30 not in pages  # and the pages that name it, with a page either side


def test_readings_the_class_cites_come_first_and_match_a_book_by_its_name(tmp_path):
    lecture = [
        "Lecture 13\nReference\nSalby Chapter 2\nWallace and Hobbs Chapter 3 Section 3.2, 3.4\n"
        "Physics of the Atmosphere and Climate relevant Chapter 1"
    ]
    cited = studypack.citations(lecture)
    names = sorted((sorted(n), ch, secs) for n, ch, secs in cited)
    assert (["salby"], 2, []) in names and (["hobbs", "wallace"], 3, ["3.2", "3.4"]) in names
    assert not any("climate" in n or "relevant" in n for n, _, _ in names)  # what a book is about isn't its name
    d = tmp_path / "wh"
    (d / "pages").mkdir(parents=True)
    pages = ["intro"] * 30
    pages[9] = "3.2 The hydrostatic equation\ntext"
    pages[14] = "3.4 Adiabatic processes\nmore"
    pages[20] = "4.1 Radiation\nother"
    for i, x in enumerate(pages, 1):
        (d / "pages" / f"{i:05d}.md").write_text(x, encoding="utf-8")
    wh = studypack.Source(
        Path(tmp_path / "Atmospheric Science Wallace Hobbs.pdf"), "Atmospheric Science", 30, d, is_class=False
    )
    other = studypack.Source(Path(tmp_path / "Thermal Physics.pdf"), "Thermal Physics", 30, d, is_class=False)
    rx = studypack.pattern(["knitting"])
    assert studypack.book_tiers(wh, rx, cited)[0] == list(range(10, 16))  # sections 3.2 to 3.4
    assert studypack.book_tiers(other, rx, cited)[0] == []  # not cited: no name in common


def test_the_study_pack_prompt_is_a_note_you_can_edit(chat_on, env):
    seed(env)
    out = env.say("/studypack prompt")
    f = studypack.prompt_file(env.app)
    assert out.startswith("Made study-pack prompt:") and f.is_file() and "{name}" in f.read_text(encoding="utf-8")
    f.write_text("<!-- mine -->\nExplain {name}{scope} like I'm five. {aim_text}. Keep $\\{x\\}$ as it is.\n", "utf-8")
    path, info = studypack.build(env.app, "deep-learning", "Deep Learning", "quiz on convolutions")
    with zipfile.ZipFile(path) as z:
        prompt = z.read("PROMPT.md").decode()
    assert prompt.startswith("Explain Deep Learning on convolutions like I'm five. quiz on convolutions.")
    assert "mine" not in prompt and "$\\{x\\}$" in prompt
    assert env.say("/studypack prompt").startswith("Your study-pack prompt:")  # it's there: not overwritten
    assert "back to Kurooto's own" in env.say("/studypack prompt reset")
    assert "Write advanced, rigorous study notes" in studypack.prompt_text("X", app=env.app)

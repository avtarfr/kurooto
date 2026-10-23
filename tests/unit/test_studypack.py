"""Sending files for real (not their paths) and study packs: a subject's notes and course files in a zip with a prompt
for another AI. Fakes only."""

import zipfile

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
    assert {"course-files/slides-1.pdf", "course-files/slides-2.PDF", "INDEX.md", "PROMPT.md"} <= names
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
    from kurooto.modules.google_drive import DriveUpload

    d = DriveUpload(env.app)
    deleted = []

    class G:
        def api(self, service, path, body=None, method=None, raw=0):
            deleted.append((path, method))
            return {}

    monkeypatch.setattr(DriveUpload, "google", property(lambda self: G()))
    monkeypatch.setattr(DriveUpload, "account", property(lambda self: "main"))
    d.remember_temporary("old1", "pack.zip")
    d.remember_temporary("new1", "other.zip")
    rows = __import__("json").loads(d.temp_file.read_text())
    rows[0]["delete_at"] = 0
    d.temp_file.write_text(__import__("json").dumps(rows))
    assert d.expire() == 1 and deleted == [("/files/old1", "DELETE")]
    assert [r["id"] for r in __import__("json").loads(d.temp_file.read_text())] == ["new1"]

"""Attachments on the dashboard's Chat page (0.9.0, dashboard.chat_attach; web/chat_api.py, static/chat.js): a picture
or a file goes up in parts (chat/upload), is kept in Kurooto's own state under a name made here, and goes with the
next message (chat/send's files) as a file from the phone does, so Chat's AI is told where it is and gets a picture as
Task.images. The limits (20 MB a file, 10 a message), pictures told by their bytes, the switch, the dashboard's key."""

from __future__ import annotations

import base64
import os
import shutil
import subprocess
from importlib import resources

import pytest

from kurooto.core import places
from kurooto.web import chat_api
from kurooto.web.api import Api
from tests.unit.test_chat_page import Live
from tests.unit.test_dashboard import call, web  # noqa: F401 (the server fixture)
from tests.unit.test_phone import phone  # noqa: F401 (the shared fixture)
from tests.unit.test_phone_chat import said

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)
JPEG_HEAD = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01" + b"\x00" * 64


@pytest.fixture
def page(phone):  # noqa: F811
    """Phone calls paired, Chat on with a fake AI (each request's prompt and options kept), a Gemini key as the AI (it
    reads pictures), the dashboard's API and stream."""
    app = phone.app
    app.settings.set("modules.enabled", [*app.settings.get("modules.enabled"), "chat"])
    app.settings.set("brain.main", "gemini")
    jobs: list[tuple[str, dict]] = []

    def submit(prompt, **kw):
        jobs.append((prompt, kw))
        return f"j{len(jobs):07d}"

    app.jobs.submit = submit
    phone.jobs = jobs
    phone.api = Api(app)
    phone.app.live = Live()
    return phone


def up(api, data: bytes, name: str, part_size: int | None = None) -> tuple[int, dict]:
    """Send a file the way chat.js does: in parts, the first without an id. The last answer."""
    step = part_size or chat_api.PART
    parts = max(1, -(-len(data) // step))
    uid = ""
    for i in range(parts):
        b = {"part": i, "parts": parts, "size": len(data), "name": name}
        b["data"] = base64.b64encode(data[i * step : (i + 1) * step]).decode()
        if uid:
            b["id"] = uid
        code, out = api.post("chat/upload", b)
        if code != 200 or "file" in out:
            return code, out
        uid = out["id"]
    raise AssertionError("no file after the last part")


def test_a_pasted_picture_goes_up_and_reaches_the_ai_as_a_picture(page):
    app, api = page.app, page.api
    code, out = api.get("chat")
    assert code == 200 and out["attach"] == {
        "on": True,
        "max": 20 * 2**20,
        "count": 10,
        "part": chat_api.PART,
    }
    code, out = up(api, PNG, "image.png")
    assert code == 200 and out["ok"]
    card = out["file"]
    assert card["picture"] is True and card["mime"] == "image/png" and card["size"] == len(PNG)
    saved = list(places.chat_files(app).iterdir())
    assert len(saved) == 1 and saved[0].name.endswith(f"-{card['id']}-image.png")
    assert saved[0].parent == app.paths.state / "chat-files"  # Kurooto's own state, never the notes
    assert not str(saved[0]).startswith(str(app.workspace))
    if os.name != "nt":
        assert saved[0].stat().st_mode & 0o077 == 0  # owner-only, like the rest of the state
    code, out = api.post("chat/send", {"session": "main", "text": "what is this?", "files": [card["id"]]})
    assert code == 200 and out["ok"]
    mine = next(m for m in said(page) if m["id"] == out["id"])  # your phones see it as yours, with the file
    assert mine["file"] == {"name": "image.png", "size": len(PNG), "mime": "image/png"} and "files" not in mine
    prompt, kw = page.jobs[-1]
    assert str(saved[0]) in prompt and "what is this?" in prompt  # told where it is, as with a Telegram photo
    assert kw["images"] == [saved[0]]  # and given it as a picture (Task.images)
    # the AI may read the folder (Claude Code's Read rules and agy's allow-list come from read_roots)
    assert places.chat_files(app) in places.read_roots(app)


def test_files_alone_several_and_documents(page):
    app, api = page.app, page.api
    pic = up(api, JPEG_HEAD, "clipboard")[1]["file"]  # a picture whatever it's called: saved as what it is
    assert pic["picture"] and pic["name"] == "clipboard.jpg" and pic["mime"] == "image/jpeg"
    doc = up(api, b"%PDF-1.4 notes", "../../Week 3 notes.pdf")[1]["file"]
    assert doc["picture"] is False and doc["name"] == "Week-3-notes.pdf" and doc["mime"] == "application/pdf"
    for f in places.chat_files(app).iterdir():  # no way out of the folder, whatever the name said
        assert f.parent == places.chat_files(app)
    code, out = api.post("chat/send", {"session": "main", "text": "", "files": [pic["id"], doc["id"]]})
    assert code == 200 and out["ok"]
    mine = next(m for m in said(page) if m["id"] == out["id"])
    assert mine["file"]["name"] == "clipboard.jpg" and [f["name"] for f in mine["files"]] == [
        "clipboard.jpg",
        "Week-3-notes.pdf",
    ]
    prompt, kw = page.jobs[-1]
    assert "no words" in prompt and "Week-3-notes.pdf" in prompt  # a document: its path, as Telegram's are
    assert [p.name for p in kw["images"]] == [p.name for p in places.chat_files(app).glob(f"*{pic['id']}*")]
    # an AI that can't read pictures gets the paths only (an Ollama model without vision would refuse the request)
    app.settings.set("brain.main", "nothing-here")
    api.post("chat/send", {"session": "main", "text": "and now?", "files": [pic["id"]]})
    assert page.jobs[-1][1]["images"] is None


def test_a_big_file_goes_in_parts_and_the_parts_must_add_up(page, monkeypatch):
    app, api = page.app, page.api
    monkeypatch.setattr(chat_api, "PART", 1024)
    data = JPEG_HEAD + os.urandom(3000)
    code, out = up(api, data, "photo.jpg", part_size=1024)
    assert code == 200 and out["file"]["size"] == len(data)
    f = next(places.chat_files(app).glob(f"*{out['file']['id']}*"))
    assert f.read_bytes() == data
    assert not list(places.chat_files(app).glob(".part-*"))  # nothing half-done left behind
    # a part out of order, a missing id, a part of the wrong size
    first = {"part": 0, "parts": 3, "size": 2500, "name": "x.bin", "data": base64.b64encode(b"a" * 1024).decode()}
    uid = api.post("chat/upload", first)[1]["id"]
    third = {**first, "part": 2, "id": uid, "data": base64.b64encode(b"a" * 452).decode()}
    assert api.post("chat/upload", third)[0] == 409
    assert api.post("chat/upload", {**first, "part": 1, "data": first["data"]})[0] == 400  # no id
    assert api.post("chat/upload", {**first, "part": 1, "id": uid, "data": "AAAA"})[0] == 400
    assert api.post("chat/upload", {**first, "parts": 2})[0] == 400  # 2500 bytes are 3 parts of 1024
    assert api.post("chat/upload", {**first, "data": "not base64!"})[0] == 400


def test_the_limits_and_pictures_by_their_bytes(page):
    app, api = page.app, page.api
    code, out = api.post("chat/upload", {"part": 0, "parts": 11, "size": 21 * 2**20, "name": "big.mp4", "data": ""})
    assert code == 413 and "20 MB" in out["note"]
    assert api.post("chat/upload", {"part": 0, "parts": 1, "size": 0, "name": "x", "data": ""})[0] == 400
    code, out = up(api, b"MZ\x90\x00 not a picture", "cat.png")  # named like a picture, isn't one
    assert code == 415 and "isn't one" in out["note"]
    assert not list(places.chat_files(app).iterdir())  # refused: nothing kept
    gif = up(api, b"GIF89a" + b"\x00" * 20, "a.png")[1]["file"]  # a picture under another picture's name
    assert gif["name"] == "a.gif" and gif["mime"] == "image/gif"
    webp = up(api, b"RIFF\x10\x00\x00\x00WEBPVP8 " + b"\x00" * 8, "s")[1]["file"]
    assert webp["name"] == "s.webp"
    heic = up(api, b"\x00\x00\x00\x18ftypheic" + b"\x00" * 12, "IMG_1.HEIC")[1]["file"]
    assert heic["name"] == "IMG_1.heic" and heic["picture"]
    assert chat_api.picture(b"<svg xmlns=") == ""  # a drawing in text is a document, not a picture an AI is sent
    # at most 10 files to a message; ids that aren't files attached here
    n, ids = len(page.jobs), [gif["id"]] * 11
    assert api.post("chat/send", {"session": "main", "text": "x", "files": ids})[0] == 400
    assert api.post("chat/send", {"session": "main", "text": "x", "files": ["../../etc/passwd"]})[0] == 400
    assert api.post("chat/send", {"session": "main", "text": "x", "files": ["0" * 16]})[0] == 404
    assert len(page.jobs) == n  # nothing reached the AI


def test_the_switch(page):
    app, api = page.app, page.api
    pic = up(api, PNG, "p.png")[1]["file"]
    app.settings.set("dashboard.chat_attach", False)
    assert api.get("chat")[1]["attach"]["on"] is False
    code, out = api.post("chat/upload", {"part": 0, "parts": 1, "size": len(PNG), "name": "p.png",
                                         "data": base64.b64encode(PNG).decode()})  # fmt: skip
    assert code == 403 and "dashboard.chat_attach" in out["note"]
    assert api.post("chat/send", {"session": "main", "text": "x", "files": [pic["id"]]})[0] == 403
    assert places.chat_files(app) not in places.read_roots(app)  # the AI no longer reads the folder
    code, out = api.post("chat/send", {"session": "main", "text": "words still go"})  # the rest of the page works
    assert code == 200 and out["ok"]
    app.settings.set("dashboard.chat_attach", True)
    assert api.post("chat/send", {"session": "main", "text": "x", "files": [pic["id"]]})[0] == 200


def test_the_folder_is_read_only_once_used(env):
    """agy's allow-list is agreed once (providers/agy.py): the folder joins what the AI may read only once something
    was attached, so nobody who never attaches a file is asked again."""
    app = env.app
    assert app.settings.get("dashboard.chat_attach") is True  # on by default: invisible until used
    sections = {s["section"]: s for s in Api(app).get("settings")[1]["sections"]}
    assert sections["dashboard"]["values"] == {"chat_attach": True}  # in Settings, as "Dashboard pages"
    assert sections["dashboard"]["title"] == "Dashboard pages"
    assert places.chat_files(app) not in places.read_roots(app)
    places.chat_files(app).mkdir(parents=True)
    assert places.chat_files(app) in places.read_roots(app)


def test_uploads_are_behind_the_dashboards_key(web):  # noqa: F811
    app, srv = web
    body = {"part": 0, "parts": 1, "size": len(PNG), "name": "p.png", "data": base64.b64encode(PNG).decode()}
    assert call(srv, "/api/chat/upload", body, token=False)[0] == 403
    assert not places.chat_files(app).exists()


def test_the_page_attaches_by_paste_drop_and_paperclip():
    static = resources.files("kurooto.web") / "static"
    chat = (static / "chat.js").read_text(encoding="utf-8")
    for bit in ('"chat/upload"', '"paste"', '"drop"', '"dragover"', "data-clip", "data-unattach", 'type="file"'):
        assert bit in chat, bit
    assert "blob:" not in chat and "createObjectURL" not in chat  # the CSP shows data: pictures only
    node = shutil.which("node")
    if node:
        assert subprocess.run([node, "--check", str(static / "chat.js")], capture_output=True).returncode == 0

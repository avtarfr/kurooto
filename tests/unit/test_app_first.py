"""Telegram is optional (0.5.19): with the phone app paired and no Telegram, the app's chat is where Kurooto talks.
Everything Kurooto sends reaches the chat (buttons working), files come as links (Google Drive, else a sealed copy on
the call line, else a plain note), features that need "somewhere to talk" turn on, Telegram's /pause and /focus answer
in the chat, setup finishes without Telegram, and `kurooto doctor` doesn't fail. The Worker's side of files is in
tests/integration/test_phone_chat_line.py."""

from __future__ import annotations

import base64
import json
import time
import urllib.parse

import pytest

from kurooto.modules.calls import chat as chatmod
from kurooto.modules.calls import line
from tests.unit.test_phone import phone  # noqa: F401 (the shared fixture)
from tests.unit.test_phone_chat import body, said


@pytest.fixture
def nobot(phone):  # noqa: F811
    """Phone calls on and paired, Telegram turned off: the phone app's chat is the channel."""
    ok, why = phone.app.disable("telegram")
    assert ok, why
    assert phone.app.app_main() and "telegram" not in phone.app.notifier.channels
    return phone


def wait_for(fn, s=5.0):
    end = time.time() + s
    while time.time() < end:
        got = fn()
        if got:
            return got
        time.sleep(0.02)
    return fn()


# ---------------------------------------------------------------------------------------------- routing
def test_without_telegram_everything_reaches_the_chat_with_its_buttons(nobot):
    app = nobot.app
    assert not app.settings.get("notify.app_chat")  # not needed: no Telegram is enough
    n_tg = len(nobot.fake.texts())
    app.notify("Your train leaves at 9.", kind="reminder", map_kind="fakeq", map_ref="r7",
               buttons=[[("Snooze", "fq:r7:snooze")]], why="asked")  # fmt: skip
    m = said(nobot)[-1]
    assert m["text"] == "Your train leaves at 9." and m["reply"] is True and m["buttons"][0]["label"] == "Snooze"
    code, out = nobot.calls.chat.take(body(app, "a" * 16, button=0, msg=m["id"]))
    assert code == 200 and nobot.fake_mod.got[-1] == ("button", "r7", "snooze")
    # a reply to it goes to the feature that sent it, as on Telegram
    code, out = nobot.calls.chat.take(body(app, "b" * 16, text="moved to 10", to=m["id"]))
    assert nobot.fake_mod.got[-1] == ("reply", "r7", "moved to 10", "app")
    # questions keep their own answer buttons on the phone (Waiting for you), and calls ring
    app.notify("How was the lecture?", kind="question", map_kind="fakeq", map_ref="r8")
    assert any(op == "notify" for op, _ in nobot.ops)
    assert len(nobot.fake.texts()) == n_tg  # nothing went to Telegram


def test_calms_why_buttons_come_to_the_chat_without_telegram(nobot):
    app = nobot.app
    app.notify("Check-in time", kind="reminder", why="deadlines.reminder", extra=[[("Why?", "calm:x:why")]])
    labels = [b["label"] for b in said(nobot)[-1]["buttons"]]
    assert "Why?" in labels


def test_with_telegram_on_the_chat_still_needs_app_chat(phone):  # noqa: F811
    phone.app.notify("FYI", kind="info", why="asked")
    assert not said(phone)  # nothing changes for Telegram users
    assert not phone.app.app_main()
    phone.app.settings.set("notify.app_chat", True)
    phone.app.notify("report.pdf", kind="result", file=__file__, why="asked")
    assert not said(phone)  # a file is Telegram's document then, not a second copy as a link


# ---------------------------------------------------------------------------------------------- files
def test_a_long_answer_comes_as_a_drive_link_with_drive_upload_on(nobot, monkeypatch, tmp_path):
    from kurooto.core.jobs import LONG, Job
    from kurooto.providers.base import Result, Verdict

    app = nobot.app
    drive = app.modules["drive_upload"]
    app.settings.set("modules.enabled", [*app.settings.get("modules.enabled"), "drive_upload"])
    monkeypatch.setattr(drive, "ready", lambda: (True, ""))
    put = []
    monkeypatch.setattr(
        drive, "put",
        lambda p, temporary=False: put.append((p, temporary)) or ("https://drive.google.com/file/d/x/view",
                                                                  f"{p.name} is in your Google Drive (Kurooto folder)"),
    )  # fmt: skip
    app.handle = lambda msg: msg.reply("On it.")
    nobot.calls.chat.take(body(app, "c" * 16, text="write me a long essay"))
    job = Job("j1", "write me a long essay", "p", "medium", "medium", "ok", None, None, "app:" + "c" * 16, False, 0,
              1, None)  # fmt: skip
    app.jobs._deliver(job, Result(Verdict.OK, "x" * (LONG + 10)), None)
    m = wait_for(lambda: [x for x in said(nobot) if x.get("buttons") and x["buttons"][0].get("url")])[-1]
    assert m["buttons"] == [{"label": "Open in Drive", "url": "https://drive.google.com/file/d/x/view"}]
    assert m["re"] == "c" * 16 and "Google Drive" in m["text"]
    assert put and put[0][1] is True  # a copy that's deleted after drive_upload.temp_days
    assert not [t for t in nobot.fake.texts() if "essay" in t]


def test_without_drive_the_call_line_keeps_a_sealed_copy(nobot, tmp_path):
    app = nobot.app
    parts = []
    nobot.calls.connector.ws = object()  # looks connected
    nobot.calls.connector.admin_wait = lambda op, timeout=25, **kw: parts.append((op, kw)) or {"ok": True}
    f = tmp_path / "notes.md"
    f.write_bytes(b"# Notes\n" + b"y" * (chatmod.FILE_PART + 5))
    ok, now = app.modules["calls"].chat.send_file(f, "Your notes", wait=True)
    assert ok
    m = said(nobot)[-1]
    url = m["buttons"][0]["url"]
    assert url.startswith(app.modules["calls"].worker_url() + "/file#")
    frag = dict(urllib.parse.parse_qsl(url.split("#", 1)[1]))
    assert frag["n"] == "notes.md" and len(frag["i"]) == 32
    assert [op for op, _ in parts] == ["file-put", "file-put"] and parts[0][1]["parts"] == 2
    assert parts[0][1]["fid"] == frag["i"]
    blob = b"".join(base64.b64decode(kw["data"]) for _, kw in parts)
    assert parts[0][1]["size"] == len(blob)
    assert line.open_f1(line.unb64url(frag["k"]), blob) == f.read_bytes()  # the key only travels in the link
    assert frag["k"] not in json.dumps([kw for _, kw in parts])


def test_with_no_way_to_carry_it_the_file_stays_on_the_computer(nobot, tmp_path):
    app = nobot.app
    nobot.calls.connector.ws = None  # the call line isn't connected
    f = tmp_path / "big.pdf"
    f.write_bytes(b"%PDF")
    app.notify("big.pdf", kind="result", file=str(f), why="asked")
    m = wait_for(lambda: [x for x in said(nobot) if "stays on your computer" in x["text"]])[-1]
    assert str(f) in m["text"] and "Drive upload" in m["text"]


def test_kurooto_send_without_telegram_goes_to_the_chat(nobot, tmp_path):
    from kurooto.modules.skills import send_file

    nobot.calls.connector.ws = None
    f = tmp_path / "plan.txt"
    f.write_text("plan")
    ok, out = send_file(nobot.app, str(f))
    assert ok and "phone app's chat" in out
    assert wait_for(lambda: [x for x in said(nobot) if "plan.txt" in x["text"]])


# ------------------------------------------------------------------------------------ files from the phone
def test_a_shared_file_can_be_referred_to_in_the_chat(nobot):
    app = nobot.app
    code, out = nobot.calls._upload({"name": ["lecture.pdf"], "note": ["week 3"]}, b"%PDF-1.4")
    assert code == 200
    rows = json.loads((nobot.calls.dir / "shared.json").read_text())
    assert rows[-1]["name"].endswith("lecture.pdf") and rows[-1]["note"] == "week 3"
    chat = app.modules["chat"]
    got = []
    app.jobs.submit = lambda prompt, **kw: got.append(prompt) or "j9"
    from kurooto.modules.base import Incoming

    chat.ask(Incoming("summarise the PDF I just sent", via="app", message_id="app:" + "d" * 16))
    assert "lecture.pdf" in got[-1] and rows[-1]["path"] in got[-1]
    chat.ask(Incoming("what's due this week?", via="app"))
    assert "lecture.pdf" not in got[-1]  # only when a file is talked about
    chat.record_turn(got[0], "It covers Markov chains.")
    hist = json.loads(chat.history_file.read_text())
    assert hist[-1]["user"] == "summarise the PDF I just sent"


# --------------------------------------------------------------------------------------- features and help
def test_features_that_need_somewhere_to_talk_turn_on_with_the_app(nobot):
    app = nobot.app
    ok, why = app.enable("reminders")
    assert ok, why
    ok, why = app.disable("calls")
    assert not ok and "Reminders" in why  # it would leave reminders nowhere to go
    ok, why = app.enable("voice_notes")
    assert not ok and "Telegram" in why and "phone app" not in why  # voice messages come only to the bot


def test_telegrams_basics_answer_in_the_chat(nobot):
    app = nobot.app
    code, out = nobot.calls.chat.take(body(app, "e" * 16, text="/focus 1h"))
    assert out["said"][0]["text"].startswith("Focus until")
    code, out = nobot.calls.chat.take(body(app, "f" * 16, text="/focus off"))
    assert out["said"][0]["text"].startswith("Focus off")
    text = app.help()
    assert "/pause" in text and "/focus" in text and "phone app's chat" in text


# ------------------------------------------------------------------------------------------- setup, doctor
def test_setup_finishes_without_telegram(nobot):
    from kurooto.web.api import Api

    app = nobot.app
    api = Api(app)
    assert api.post("setup/channel", {"channel": "app"})[1]["ok"]
    assert api.get("state")[1]["channel"] == "app"
    assert api.post("setup/channel", {"channel": "fax"})[0] == 400
    app.disable("calls")  # as on a fresh setup: Phone calls goes on with the rest, first
    code, out = api.post("modules/enable", {"ids": ["chat", "reminders", "checkins", "deadlines", "calls"]})
    bad = {k: v for k, v in out["results"].items() if not v["ok"] and k != "chat"}  # chat: no AI picked here
    assert not bad, bad
    assert api.post("setup/done", {})[1]["ok"]
    assert "in the phone app's chat" in said(nobot)[-1]["text"]


def test_doctor_doesnt_fail_without_telegram(nobot, monkeypatch):
    from kurooto import diagnostics

    rows = diagnostics.more_checks(nobot.app)
    assert ("talks to you", True, "in the phone app's chat (Telegram is optional)") in rows
    assert not [r for r in rows if r[1] is False]
    nobot.app.disable("calls")
    rows = diagnostics.more_checks(nobot.app)
    assert next(r for r in rows if r[0] == "talks to you")[1] is None  # a note, not a problem

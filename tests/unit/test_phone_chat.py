"""The phone app as a chat (calls/chat.py) and the phone outbox's computer side, without a call line: a typed message
is handled like a Telegram one, its answers (now or from a job later) go back to the chat only, buttons under them
work by number, replies reach the feature that sent the message, notify.app_chat, and what waited on the call line
taken one item at a time (Calls.take_queued). The Worker's side is in tests/integration/test_phone_chat_line.py."""

from __future__ import annotations

import base64
import json
import os
import time

import pytest

from kurooto.modules.base import Command
from kurooto.modules.calls import line
from tests.unit.test_phone import phone  # noqa: F401 (the shared fixture)


@pytest.fixture
def chat(phone):  # noqa: F811
    def ping(msg, arg):
        msg.reply("pong", buttons=[[("Again", "fq:p1:again"), ("Docs", {"url": "https://example.com/d"})]])

    phone.fake_mod.commands = lambda: [Command("ping", "answers pong", ping)]
    phone.chat = phone.calls.chat
    return phone


def body(app, mid: str, sealed=True, **fields) -> dict:
    f = {"id": mid, "ts": int(time.time() * 1000), "n": os.urandom(16).hex(), **fields}
    b = {"device": "abcd1234", "at": int(time.time() * 1000), "id": mid}
    if sealed:
        return {**b, "k1": line.seal_k1(app.secrets.get("calls.ntfy_key"), json.dumps(f))}
    return {**b, **{k: v for k, v in f.items() if k != "id"}}


def said(env) -> list[dict]:
    return [kw["msg"] for op, kw in env.ops if op == "chat-say"]


def test_a_typed_message_is_handled_like_telegram_and_answered_in_the_chat(chat):
    app = chat.app
    n_tg = len(chat.fake.texts())
    code, out = chat.calls.handle_request("POST", "/chat", json.dumps(body(app, "a" * 16, text="/ping")).encode())
    assert code == 200 and out["ok"] and out["id"] == "a" * 16
    assert [m["text"] for m in out["said"]] == ["pong"]
    pong = out["said"][0]
    assert pong["from"] == "kurooto" and pong["re"] == "a" * 16
    assert pong["buttons"] == [{"label": "Again"}, {"label": "Docs", "url": "https://example.com/d"}]
    assert not any(k.startswith("_") for k in pong)  # the buttons' data stays on this computer
    assert [(m["from"], m["text"]) for m in said(chat)] == [("you", "/ping"), ("kurooto", "pong")]
    assert len(chat.fake.texts()) == n_tg  # nothing on Telegram
    # a button under the answer, by its number
    code, out = chat.chat.take(body(app, "b" * 16, sealed=False, button=0, msg=pong["id"]))
    assert code == 200 and out["note"] == "Did again." and chat.fake_mod.got[-1] == ("button", "p1", "again")
    assert said(chat)[-1]["text"] == "Did again."
    assert chat.chat.take(body(app, "c" * 16, button=1, msg=pong["id"]))[0] == 400  # a link isn't pressed here
    assert chat.chat.take(body(app, "c" * 16, button=0, msg="f" * 16))[0] == 400  # not a message here


def test_messages_must_be_fresh_new_and_sealed_with_the_right_key(chat):
    app = chat.app
    b = body(app, "1" * 16, text="hello")
    app.handle = lambda msg: msg.reply("hi")
    assert chat.chat.take(b)[0] == 200
    assert chat.chat.take(b)[0] == 409  # used once
    old = body(app, "2" * 16, sealed=False, text="hi", ts=int(time.time() * 1000) - 3600_000)
    code, out = chat.chat.take(old)
    assert code == 409 and "message is too old" in out["note"]
    other = {**body(app, "3" * 16, text="x"), "id": "4" * 16}  # sealed for another message
    assert chat.chat.take(other)[0] == 400
    wrong = body(app, "5" * 16, text="x")
    wrong["k1"] = line.seal_k1(line.new_key(), json.dumps({"id": "5" * 16, "text": "x"}))
    assert chat.chat.take(wrong)[1]["note"].startswith("That message couldn't be opened")
    assert chat.chat.take(body(app, "nothex", text="x"))[0] == 400
    assert chat.chat.take(body(app, "6" * 16, text="  "))[0] == 400


def test_a_later_answer_goes_back_to_the_chat_only(chat):
    app = chat.app
    app.handle = lambda msg: msg.reply("On it.")
    chat.chat.take(body(app, "d" * 16, text="summarise my week"))
    n_tg = len(chat.fake.texts())
    app.notify("[AI · medium] summarise my week\n\nA calm week.", kind="result", reply_to="app:" + "d" * 16)
    m = said(chat)[-1]
    assert m["text"].endswith("A calm week.") and m["re"] == "d" * 16
    assert len(chat.fake.texts()) == n_tg
    # Phone calls off meanwhile: Telegram gets it, as a new message
    app.notifier.unregister("chat")
    app.notify("Done.", kind="result", reply_to="app:" + "d" * 16, why="asked")
    assert chat.fake.texts()[-1] == "Done."


def test_app_chat_sends_kuroottos_own_messages_to_the_chat_too(chat):
    app = chat.app
    app.notify("Your train leaves at 9.", kind="reminder", map_kind="fakeq", map_ref="r7")
    assert not said(chat)
    app.settings.set("notify.app_chat", True)
    app.notify("Your train leaves at 9.", kind="reminder", map_kind="fakeq", map_ref="r7")
    m = said(chat)[-1]
    assert m["text"] == "Your train leaves at 9." and m["reply"] is True
    assert "Your train leaves at 9." in chat.fake.texts()[-1]  # Telegram too
    app.notify("How was the lecture?", kind="question", map_kind="fakeq", map_ref="r8")
    assert said(chat)[-1]["id"] == m["id"]  # questions stay under Waiting for you
    app.notify("Calling you", kind="call")
    assert said(chat)[-1]["id"] == m["id"]
    # a reply to it in the chat goes to the feature that sent it, as on Telegram
    code, out = chat.chat.take(body(app, "e" * 16, text="moved to 10", to=m["id"]))
    assert code == 200 and chat.fake_mod.got[-1] == ("reply", "r7", "moved to 10", "app")
    assert out["said"][0]["text"] == "Noted."


def test_what_the_line_missed_is_sent_again(chat):
    chat.calls.connector.admin_later = lambda op, then=None, **kw: False  # the line is down
    chat.app.handle = lambda msg: msg.reply("hi")
    chat.chat.take(body(chat.app, "7" * 16, text="hello"))
    sent = []
    chat.calls.connector.admin_later = lambda op, then=None, **kw: sent.append((op, kw)) or True
    assert chat.calls.chat.flush() == 2
    assert [kw["msg"]["text"] for op, kw in sent if op == "chat-say"] == ["hello", "hi"]


def test_what_waited_on_the_line_is_taken_one_item_at_a_time(chat):
    app, calls = chat.app, chat.calls
    status, note = calls.take_queued({"kind": "chat", "seq": 1, "body": body(app, "8" * 16, text="/ping")})
    assert status == 200 and said(chat)[-1]["text"] == "pong"
    raw = b"x" * 1000

    def part(n, chunk):
        q = f"?name=notes.txt&id=f1&part={n}&parts=2"
        return calls.take_queued({"kind": "upload", "search": q, "body_b64": base64.b64encode(chunk).decode()})

    assert part(0, raw[:600])[0] == 200
    status, note = part(1, raw[600:])
    assert status == 200 and note.endswith("notes.txt")
    saved = [p for p in (app.workspace / "inbox").iterdir() if p.name.endswith("notes.txt")]
    assert len(saved) == 1 and saved[0].read_bytes() == raw
    assert calls.take_queued({"kind": "nope"})[0] == 400
    assert calls.take_queued({"kind": "chat", "body": {"id": "bad"}})[0] == 400


def test_more_buttons_than_the_app_shows_go_on_in_a_follow_up(chat):
    """(0.8.17) Past six, the rest were dropped (an evening bundle's numbered buttons above all); now they follow, six
    a message, each answering the same feature."""
    rows = [[(f"Pick {i}", f"fq:p1:{i}")] for i in range(9)]
    m = chat.chat.say("Which one?", rows, mapped=("ask", "q1"))
    out = said(chat)
    assert [b["label"] for b in m["buttons"]] == [f"Pick {i}" for i in range(6)]
    follow = out[-1]
    assert follow["text"] == "More choices for the message above:" and follow["id"] != m["id"]
    assert [b["label"] for b in follow["buttons"]] == ["Pick 6", "Pick 7", "Pick 8"]
    code, _ = chat.chat.take(body(chat.app, "d" * 16, sealed=False, button=2, msg=follow["id"]))
    assert code == 200 and chat.fake_mod.got[-1] == ("button", "p1", "8")

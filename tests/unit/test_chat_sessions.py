"""The phone app's chat as a Telegram replacement (0.8.10; calls/chat.py, calls/sessions.py, modules/chat.py), without a
call line (the call line's side is tests/integration/test_chat_sessions_line.py): separate chats each with their own
AI context that carries over, replies that bring the quoted message to the AI, files both ways, editing, deleting and
pinning, "working"/"idle", the being's sealed requests and their refusals, and messages from older app versions.
The AI is faked: jobs.submit records the prompt, and an answer is recorded the way core/jobs.py does."""

from __future__ import annotations

import json
import time

import pytest

from kurooto.core.state import jload, jsave
from kurooto.modules.calls import line
from kurooto.modules.calls.chat import OFF_NOW
from tests.unit.test_phone import phone  # noqa: F401 (the shared fixture)
from tests.unit.test_phone_chat import body, said

S1, S2 = "1" * 15 + "a", "2" * 15 + "b"


def mid(n: int) -> str:
    return f"{n:016x}"


@pytest.fixture
def chat(phone):  # noqa: F811
    """Phone calls paired, Chat on with a fake AI: each request's prompt is kept, its id returned."""
    app = phone.app
    app.settings.set("modules.enabled", [*app.settings.get("modules.enabled"), "chat"])
    prompts: list[tuple[str, str]] = []

    def submit(prompt, **kw):
        jid = f"j{len(prompts):07d}"
        prompts.append((jid, prompt))
        return jid

    app.jobs.submit = submit
    phone.prompts, phone.pc = prompts, phone.calls.chat
    phone.ai = app.modules["chat"]
    phone.n = 0
    return phone


def send(env, sealed=True, **fields) -> tuple[int, dict, str]:
    env.n += 1
    m = mid(env.n)
    code, out = env.pc.take(body(env.app, m, sealed=sealed, **fields))
    return code, out, m


def ops(env, name):
    return [kw for op, kw in env.ops if op == name]


def answer(env, jid, prompt, text, to):
    """What core/jobs.py does when the AI answers: the answer to the chat, then the turn into the context."""
    env.app.notify(text, kind="result", reply_to="app:" + to, why="asked")
    env.ai.record_turn(prompt, text, jid=jid)
    env.app.events.emit("job_done", job=jid, ok=True)


def opened(env, out) -> dict:
    return json.loads(line.open_k1(env.app.secrets.get("calls.ntfy_key"), out["k1"]))


# ------------------------------------------------------------------------------------------------ sessions
def test_old_messages_belong_to_main_and_keep_the_two_hour_window(chat):
    code, out, m = send(chat, text="what is a ring?")
    assert code == 200
    mine = next(x for x in said(chat) if x["id"] == m)
    assert mine["session"] == "main" and said(chat)[-1]["text"] == "On it."  # every message says its chat
    jid, prompt = chat.prompts[-1]
    assert "Previous conversation" not in prompt
    answer(chat, jid, prompt, "A set with two operations.", m)
    assert said(chat)[-1]["session"] == "main" and said(chat)[-1]["re"] == m
    assert jload(chat.ai.history_file, [])[-1]["user"] == "what is a ring?"  # Telegram's and main's history
    send(chat, text="and a field?")
    assert "A set with two operations." in chat.prompts[-1][1]
    h = jload(chat.ai.history_file, [])
    h[-1]["at"] -= 3 * 3600  # older than 2 hours: not carried, as before
    jsave(chat.ai.history_file, h)
    send(chat, text="and a module?")
    assert "Previous conversation" not in chat.prompts[-1][1]


def test_a_session_keeps_its_own_context_for_as_long_as_it_lives(chat):
    code, out, m = send(chat, text="Let's plan the topology exam revision", session=S1)
    assert code == 200
    st = chat.calls.sessions.get(S1)
    assert st["title"] == "Let's plan the topology exam revision"  # its first words, made on the first message
    assert ops(chat, "chat-sessions")[-1]["sessions"][1]["id"] == S1
    jid, prompt = chat.prompts[-1]
    assert ops(chat, "chat-status")[-1] == {"session": S1, "state": "working", "job": jid}
    answer(chat, jid, prompt, "Start with compactness.", m)
    assert said(chat)[-1]["session"] == S1 and said(chat)[-1]["text"] == "Start with compactness."
    assert ops(chat, "chat-status")[-1] == {"session": S1, "state": "idle", "job": jid}
    turns = jload(chat.ai.session_file(S1), [])
    assert turns[-1]["user"] == "Let's plan the topology exam revision"
    assert jload(chat.ai.history_file, []) == []  # main's history is untouched
    turns[-1]["at"] -= 3 * 86400  # days later, the chat still remembers
    jsave(chat.ai.session_file(S1), turns)
    send(chat, text="what came after that?", session=S1)
    assert "Start with compactness." in chat.prompts[-1][1]
    send(chat, text="what came after that?")  # Kurooto's own chat doesn't see it
    assert "compactness" not in chat.prompts[-1][1]
    send(chat, text="/new", session=S1)  # starts that chat over, not main
    assert jload(chat.ai.session_file(S1), []) == []
    assert said(chat)[-1]["session"] == S1


def test_kuroottos_own_messages_go_to_main(chat):
    chat.app.settings.set("notify.app_chat", True)
    send(chat, text="hello", session=S1)
    chat.app.notify("Your train leaves at 9.", kind="reminder")
    assert said(chat)[-1]["text"] == "Your train leaves at 9." and said(chat)[-1]["session"] == "main"


def test_session_ops(chat):
    ss = chat.calls.sessions
    code, out, _ = send(chat, op="session.new", args={"session": S2, "title": "Groceries"})
    assert code == 200 and out["ok"] and [s["id"] for s in out["sessions"]] == ["main", S2]
    assert send(chat, op="session.new", args={"session": S2})[1]["ok"]  # sent again: the same chat
    assert ss.get(S2)["title"] == "Groceries"
    code, out, _ = send(chat, op="session.rename", session=S2, title="Food")  # arguments beside op work too
    assert out["ok"] and ss.get(S2)["title"] == "Food"
    assert send(chat, op="session.pin", args={"session": S2, "on": True})[1]["ok"] and ss.get(S2)["pinned"]
    assert send(chat, op="read", args={"session": S2, "upto": mid(1)})[1]["ok"] and ss.get(S2)["read"] == mid(1)
    assert ops(chat, "chat-sessions")[-1]["quiet"] is True  # a read mark: no notification
    code, out, _ = send(chat, op="sync")
    assert out["kind"] == "sessions" and out["sessions"][0]["id"] == "main"
    assert {"name": "help", "help": "what I can do"} in out["commands"]
    assert out["switches"] == {
        "chat_sessions": True,
        "chat_files_inline": True,
        "chat_edit": True,
        "place_names": False,
        "phone_busy": False,
    }  # fmt: skip (0.9.1: what the phone may send)
    # refusals
    no = send(chat, op="session.delete", args={"session": "main"})[1]
    assert no["note"] == "Kurooto's own chat can't be deleted."
    assert not send(chat, op="session.rename", args={"session": "main", "title": "x"})[1]["ok"]
    assert send(chat, op="session.new", args={"session": "nothex"})[0] == 400
    no = send(chat, op="session.rename", args={"session": "f" * 16, "title": "x"})[1]
    assert no["note"] == "There's no such chat."
    assert send(chat, op="nope")[0] == 400
    assert send(chat, text="hi", session="../etc")[0] == 400
    # delete: the chat, its context and its messages here go
    send(chat, text="eggs and milk", session=S2)
    jsave(chat.ai.session_file(S2), [{"user": "eggs", "assistant": "ok", "at": time.time()}])
    code, out, _ = send(chat, op="session.delete", args={"session": S2})
    assert out["ok"] and ss.get(S2) is None and not chat.ai.session_file(S2).exists()
    assert not [m for m in jload(chat.pc.file, {})["msgs"] if m.get("session") == S2]
    # an answer that comes for a deleted chat lands in main
    chat.pc.say("late answer", session=S2)
    assert said(chat)[-1]["session"] == "main"


def test_sessions_off_puts_everything_in_main(chat):
    chat.app.settings.set("calls.chat_sessions", False)
    chat.app.events.emit("setting_changed", key="calls.chat_sessions")  # as the dashboard's Settings does
    assert ops(chat, "chat-sessions")[-1]["switches"]["chat_sessions"] is False  # the phones hear at once
    code, out, m = send(chat, text="hello", session=S1)
    assert code == 200 and said(chat)[-1]["session"] == "main" and chat.calls.sessions.get(S1) is None
    assert "Separate chats are off" in send(chat, op="session.new", args={"session": S1})[1]["note"]
    assert [s["id"] for s in send(chat, op="sync")[1]["sessions"]] == ["main"]


def test_ai_titles(chat):
    chat.app.settings.set("calls.chat_titles", "ai")
    got = []
    chat.app.jobs.submit = lambda prompt, **kw: got.append((prompt, kw)) or f"j{len(got)}"
    _, _, m = send(chat, text="how do I prove the Heine-Borel theorem", session=S1)
    prompt = got[-1][0]
    chat.ai.record_turn(prompt, "Use nested intervals.", jid="j1")
    title_prompt, kw = got[-1]
    assert kw["then"] == "calls.chat_title" and kw["quiet"] and kw["text_only"] and "Heine-Borel" in title_prompt

    class R:
        ok, text = True, '"Heine-Borel proof."\n'

    chat.calls.sessions.titled(None, R(), kw["then_payload"])
    assert chat.calls.sessions.get(S1)["title"] == "Heine-Borel proof"
    send(chat, op="session.rename", args={"session": S1, "title": "Analysis"})
    chat.calls.sessions.titled(None, R(), kw["then_payload"])
    assert chat.calls.sessions.get(S1)["title"] == "Analysis"  # yours is never replaced


# --------------------------------------------------------------------------------------------- replies
def test_a_reply_brings_the_quoted_message_to_the_ai(chat):
    _, _, m = send(chat, text="list three compact spaces", session=S1)
    jid, prompt = chat.prompts[-1]
    answer(chat, jid, prompt, "[0,1], a point, the Cantor set.", m)
    k = said(chat)[-1]
    code, out, m2 = send(chat, text="why the second?", session=S1, reply=k["id"])
    mine = next(x for x in said(chat) if x["id"] == m2)
    assert mine["quote"] == {"id": k["id"], "from": "kurooto", "text": "[0,1], a point, the Cantor set."}
    assert mine["re"] == k["id"]
    assert 'replying to your earlier message: "[0,1], a point, the Cantor set."' in chat.prompts[-1][1]
    # a reply to a feature's message still goes to that feature (as on Telegram), old "to" or new "reply"
    chat.app.settings.set("notify.app_chat", True)
    chat.app.notify("Your train leaves at 9.", kind="reminder", map_kind="fakeq", map_ref="r7")
    q = said(chat)[-1]
    code, out, _ = send(chat, text="moved to 10", reply=q["id"])
    assert chat.fake_mod.got[-1] == ("reply", "r7", "moved to 10", "app") and out["said"][0]["text"] == "Noted."


# -------------------------------------------------------------------------------------------- messages
def test_edit_delete_and_pin(chat):
    _, _, m = send(chat, text="meet at 5", session=S1)
    jid, prompt = chat.prompts[-1]
    answer(chat, jid, prompt, "Noted, 5.", m)
    k = said(chat)[-1]
    n_prompts = len(chat.prompts)
    code, out, _ = send(chat, op="msg.edit", args={"target": m, "text": "meet at 6"})
    assert code == 200 and out["msg"]["text"] == "meet at 6" and out["msg"]["edited"] is True
    assert len(chat.prompts) == n_prompts  # Kurooto isn't asked again
    sent = [kw for kw in ops(chat, "chat-say") if kw["msg"]["id"] == m]
    assert sent[-1]["update"] is True and sent[-1]["msg"]["text"] == "meet at 6"
    assert send(chat, op="msg.edit", args={"target": k["id"], "text": "x"})[0] == 403  # not yours
    assert send(chat, op="msg.pin", args={"target": k["id"], "on": True})[1]["msg"]["pinned"] is True
    assert send(chat, op="msg.delete", args={"target": k["id"]})[0] == 403
    code, out, _ = send(chat, op="msg.delete", args={"target": m})
    assert out["msg"]["deleted"] is True and out["msg"]["text"] == ""
    assert "deleted" in send(chat, op="msg.edit", args={"target": m, "text": "y"})[1]["note"]
    _, _, old = send(chat, text="an old one", session=S1)
    msgs = jload(chat.pc.file, {})
    next(x for x in msgs["msgs"] if x["id"] == old)["at"] -= 20 * 60
    jsave(chat.pc.file, msgs)
    assert "15 minutes" in send(chat, op="msg.edit", args={"target": old, "text": "z"})[1]["note"]
    assert send(chat, op="msg.pin", args={"target": "f" * 16, "on": True})[0] == 404
    chat.app.settings.set("calls.chat_edit", False)
    assert send(chat, op="msg.pin", args={"target": k["id"], "on": False})[0] == 403


def test_what_the_line_missed_is_sent_again_with_its_changes(chat):
    _, _, m = send(chat, text="hello")
    chat.calls.connector.admin_later = lambda op, then=None, **kw: False  # the line is down
    send(chat, op="msg.edit", args={"target": m, "text": "hello there"})
    sent = []
    chat.calls.connector.admin_later = lambda op, then=None, **kw: sent.append((op, kw)) or True
    chat.pc.flush()
    again = [kw for op, kw in sent if op == "chat-say" and kw["msg"]["id"] == m]
    assert again and again[-1]["update"] is True and again[-1]["msg"]["text"] == "hello there"


# ------------------------------------------------------------------------------------------------ files
def test_a_file_from_the_phone_is_named_in_its_chat(chat):
    calls = chat.calls
    code, up = calls._upload({"name": ["week3.pdf"], "id": ["up1"], "chat": [S1]}, b"%PDF-1.4")
    assert code == 200 and up["fid"] == "up1"
    assert not chat.prompts  # not filed into the notes: the chat message says what it's for
    code, out, m = send(chat, text="what's in this?", session=S1,
                        file={"fid": "up1", "name": "week3.pdf", "mime": "application/pdf", "size": 8})  # fmt: skip
    assert code == 200
    mine = next(x for x in said(chat) if x["id"] == m)
    assert mine["file"] == {"name": "week3.pdf", "size": 8, "mime": "application/pdf"} and mine["session"] == S1
    jid, prompt = chat.prompts[-1]
    assert "week3.pdf" in prompt and "Files they sent with it" in prompt
    answer(chat, jid, prompt, "Week 3's slides.", m)
    assert "week3.pdf" in jload(chat.ai.session_file(S1), [])[-1]["user"]  # named in that chat's context
    send(chat, text="summarise the pdf I sent", session=S1)
    assert "week3.pdf" in chat.prompts[-1][1]
    send(chat, text="summarise the pdf I sent")  # main doesn't list another chat's files
    assert "week3.pdf" not in chat.prompts[-1][1]
    # a file alone, no words
    calls._upload({"name": ["photo.jpg"], "id": ["up2"], "chat": [S1]}, b"\xff\xd8")
    assert send(chat, session=S1, file={"fid": "up2", "name": "photo.jpg", "mime": "image/jpeg", "size": 2})[0] == 200
    assert "no words" in chat.prompts[-1][1]
    # refusals
    assert send(chat, session=S1, file={"fid": "nope", "name": "x"})[0] == 404
    chat.app.settings.set("calls.chat_files_inline", False)
    assert send(chat, session=S1, file={"fid": "up2", "name": "photo.jpg"})[0] == 403


def test_a_file_for_the_phone_comes_inline_with_the_old_button_too(chat, tmp_path):
    f = tmp_path / "notes.pdf"
    f.write_bytes(b"%PDF-1.4 hello")
    chat.pc.to_line = lambda path: ("https://line.example/file#i=abc&k=key", "")
    _, _, m = send(chat, text="send me the notes", session=S1)
    chat.pc.send_file(f, re_id=m, wait=True)
    k = said(chat)[-1]
    assert k["session"] == S1
    assert k["file"] == {"name": "notes.pdf", "size": 14, "mime": "application/pdf",
                         "url": "https://line.example/file#i=abc&k=key"}  # fmt: skip
    assert k["buttons"][0]["url"] == k["file"]["url"]  # older app versions open it in the browser
    chat.app.settings.set("calls.chat_files_inline", False)
    chat.pc.send_file(f, re_id=m, wait=True)
    assert "file" not in said(chat)[-1] and said(chat)[-1]["buttons"]


# ------------------------------------------------------------------------------------------- the being
def test_the_beings_requests(chat):
    app = chat.app
    code, out, _ = send(chat, op="settings.set", args={"key": "notify.app_chat", "value": True})
    assert code == 200 and out["ok"] and set(out) == {"ok", "op", "k1"}  # the answer itself is sealed
    assert opened(chat, out) == {"ok": True, "op": "settings.set", "key": "notify.app_chat", "value": True,
                                 "note": "Saved."}  # fmt: skip
    assert app.settings.get("notify.app_chat") is True
    # the dashboard's own checks: a hidden setting, a wrong type
    out = send(chat, op="settings.set", args={"key": "telegram.allowed_users", "value": []})[1]
    assert not out["ok"] and opened(chat, out)["note"] == "not a setting you can change here"
    out = send(chat, op="settings.set", args={"key": "notify.app_chat", "value": "yes"})[1]
    assert opened(chat, out)["note"] == "notify.app_chat takes a bool"
    # a feature on and off
    out = send(chat, op="module", args={"id": "reminders", "on": True})[1]
    assert out["ok"] and opened(chat, out)["on"] is True and app.is_on("reminders")
    out = send(chat, op="module", args={"id": "reminders", "on": False})[1]
    assert out["ok"] and not app.is_on("reminders")
    assert not opened(chat, send(chat, op="module", args={"id": "nope", "on": True})[1])["ok"]
    out = send(chat, op="module", args={"id": "calls", "on": False})[1]
    assert not out["ok"] and app.is_on("calls")  # what connects the phone stays on
    # a note's text, as the dashboard's /api/note gives it
    (app.workspace / "courses").mkdir(parents=True, exist_ok=True)
    (app.workspace / "courses" / "topology.md").write_text("---\ntags: [x]\n---\n# Topology\n\nOpen sets.\n")
    got = opened(chat, send(chat, op="note.get", args={"id": "courses/topology"})[1])
    assert got["ok"] and got["text"] == "# Topology\n\nOpen sets.\n"
    assert not opened(chat, send(chat, op="note.get", args={"id": "../../etc/passwd"})[1])["ok"]
    # refusals: not sealed (the iPhone app, a Shortcut), or it waited on the line while the computer was off
    code, out, _ = send(chat, sealed=False, op="settings.set", args={"key": "notify.app_chat", "value": False})
    assert code == 403 and app.settings.get("notify.app_chat") is True
    chat.n += 1
    status, note = chat.calls.take_queued(
        {"kind": "chat", "body": body(app, mid(chat.n), op="module", args={"id": "reminders", "on": True})}
    )
    assert status == 409 and note == OFF_NOW and not app.is_on("reminders")


def test_the_beings_mute_goes_through_the_dashboards_voice_mute(chat, monkeypatch):
    """0.8.10: the being's Mute on the phone (op voice.mute) is the dashboard's POST /api/voice/mute."""
    from kurooto.web.api import Api

    calls = []

    def fake_post(self, path, b):
        calls.append((path, b))
        return (200, {"ok": True, "message": "Muted.", "muted": True}) if path == "voice/mute" else (404, {})

    monkeypatch.setattr(Api, "post", fake_post)
    got = opened(chat, send(chat, op="voice.mute", args={})[1])
    assert got == {"ok": True, "op": "voice.mute", "muted": True, "note": "Muted."} and calls == [("voice/mute", {})]
    code, out, _ = send(chat, sealed=False, op="voice.mute", args={})
    assert code == 403 and len(calls) == 1  # only the paired phone, sealed


def test_session_turns_are_forgotten_with_the_rest(chat):
    from kurooto.core import retention

    t = time.time()
    jsave(chat.ai.session_file(S1), [{"user": "old", "assistant": "a", "at": t - 9 * 86400},
                                     {"user": "new", "assistant": "b", "at": t}])  # fmt: skip
    assert retention._chats(chat.app, 0, t - 86400) == 1
    assert [x["user"] for x in jload(chat.ai.session_file(S1), [])] == ["new"]


def test_a_being_answer_is_sealed_for_the_phone_that_asked(chat):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    k = ec.generate_private_key(ec.SECP256R1())
    pub = line.b64url(
        k.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    )
    devs = [{"id": "abcd1234", "kind": "android", "seal": pub}, {"id": "ffff0000", "kind": "android", "seal": "x"}]
    chat.calls.connector.admin_wait = lambda op, timeout=25, **kw: {"devices": devs} if op == "devices" else {}
    code, out, _ = send(chat, op="settings.set", args={"key": "notify.app_chat", "value": True})
    assert set(out) == {"ok", "op", "s1"}  # the call line can't open it; only this phone can
    assert json.loads(line.open_s1(k, out["s1"]))["note"] == "Saved."

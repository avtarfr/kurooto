"""The phone app's chats on the real call line (0.8.10; worker.js chatSay, chatSessionsPut, chatStatusPut, chat): the
real Worker under `wrangler dev` and the real connector (see test_call_line.py for the setup).

Every message keeps its `session`; the line keeps the last 50 of each chat and the list of chats with the commands,
so a phone catches up with the computer off; GET /chat without ?sessions=1 stays what older app versions read (main
only); a change to a message keeps its place with a new seq; "working" shows while an AI request runs; a deleted chat
loses what the line kept of it; the being's requests (`live`) are refused at once with the computer off.
"""

from __future__ import annotations

import json
import time

from kurooto.modules.calls import line
from tests.integration.test_call_line import Loop, pytestmark, wait, world  # noqa: F401 (the shared fixture)
from tests.integration.test_phone_chat_line import chat_log, chats, plain_chat, sealed_chat  # noqa: F401
from tests.integration.test_phone_line import ntfy_after, phones  # noqa: F401

S1 = "a1" * 8


def all_chats(w, after=0):
    return w["line"].call("GET", f"/chat?after={after}&sessions=1", key=w["keys"]["android"])[1]


def admin(w, op, **kw):
    return w["calls"].connector.admin_wait(op, **kw)


def test_a_chat_of_its_own_on_the_line(chats):  # noqa: F811
    w, ln = chats, chats["line"]
    n0 = len(w["cloud"].ntfy)
    code, out = ln.call("POST", "/chat", sealed_chat(w, "c" * 16, text="/ping", session=S1), key=w["keys"]["android"])
    assert code == 200 and out["said"][0]["session"] == S1, out
    pong = ntfy_after(w, n0, "chat")
    assert pong["session"] == S1 and pong["message"] == "pong"
    got = wait(lambda: (lambda j: j if j.get("sessions") and len(j["sessions"]) == 2 else None)(all_chats(w)), 15,
               "the list of chats")  # fmt: skip
    assert [s["id"] for s in got["sessions"]] == ["main", S1] and got["sessions"][1]["title"] == "/ping"
    assert {"name": "help", "help": "what I can do"} in got["commands"]
    assert got["switches"]["chat_edit"] is True
    mine = [m for m in got["msgs"] if m["session"] == S1]
    assert [(m["from"], m["text"]) for m in mine] == [("you", "/ping"), ("kurooto", "pong")]
    assert got["sessions"][1]["last"] == "pong"  # the line keeps the last line itself
    # an older app reads /chat without ?sessions=1: Kurooto's own chat only, as before
    old = chat_log(w)
    assert all(m.get("session", "main") == "main" for m in old["msgs"]) and "sessions" not in old
    assert not any(m["id"] == "c" * 16 for m in old["msgs"])


def test_the_line_keeps_the_last_50_of_each_chat(chats):  # noqa: F811
    w = chats
    seq0 = all_chats(w)["seq"]
    for i in range(55):
        assert admin(w, "chat-say", msg={"id": f"{i:016x}", "from": "you", "text": f"n{i}", "at": int(time.time()),
                                         "session": S1})["ok"]  # fmt: skip
    assert admin(w, "chat-say", msg={"id": "e" * 16, "from": "you", "text": "from an older computer"})["ok"]
    got = all_chats(w)
    s1 = [m for m in got["msgs"] if m["session"] == S1]
    assert len(s1) == 50 and s1[-1]["text"] == "n54"
    main = [m for m in got["msgs"] if m["session"] == "main"]
    assert main[-1]["text"] == "from an older computer" and any(m["text"] == "pong" for m in main) is False
    assert [m["seq"] for m in got["msgs"]] == sorted(m["seq"] for m in got["msgs"]) and got["seq"] > seq0
    assert len(all_chats(w, after=got["seq"] - 1)["msgs"]) == 1  # catch up from a seq, across chats


def test_a_changed_message_keeps_its_place_with_a_new_seq(chats):  # noqa: F811
    w, ln = chats, chats["line"]
    code, out = ln.call("POST", "/chat", sealed_chat(w, "d" * 16, text="/ping", session=S1), key=w["keys"]["android"])
    assert code == 200
    seq = all_chats(w)["seq"]
    edit = sealed_chat(w, "f" * 16, op="msg.edit", args={"target": "d" * 16, "text": "/ping twice"})
    code, out = ln.call("POST", "/chat", edit, key=w["keys"]["android"])
    assert code == 200 and out["msg"]["edited"] is True, out
    later = wait(lambda: all_chats(w, after=seq)["msgs"] or None, 10, "the edit on the line")
    assert later[0]["id"] == "d" * 16 and later[0]["text"] == "/ping twice" and later[0]["edited"] is True
    assert sum(m["id"] == "d" * 16 for m in all_chats(w)["msgs"]) == 1  # changed in place, not a copy


def test_working_and_idle(chats):  # noqa: F811
    w = chats
    admin(w, "chat-status", session=S1, state="working", job="j1234567")
    assert all_chats(w)["status"] == {S1: {"state": "working", "job": "j1234567"}}
    admin(w, "chat-status", session=S1, state="idle", job="j1234567")
    assert all_chats(w)["status"] == {}


def test_a_deleted_chat_leaves_the_line(chats):  # noqa: F811
    w, ln = chats, chats["line"]
    out = ln.call("POST", "/chat", sealed_chat(w, "9" * 16, op="session.delete", args={"session": S1}),
                  key=w["keys"]["android"])[1]  # fmt: skip
    assert out["ok"], out
    got = wait(lambda: (lambda j: j if len(j["sessions"]) == 1 else None)(all_chats(w)), 10, "the chat gone")
    assert not [m for m in got["msgs"] if m["session"] == S1]


def test_the_beings_requests_dont_wait_for_the_computer(chats):  # noqa: F811
    w, ln, keys = chats, chats["line"], chats["keys"]
    out = ln.call("POST", "/chat", {**sealed_chat(w, "8" * 16, op="note.get", args={"id": "courses/linear-algebra"}),
                                    "live": True}, key=keys["android"])[1]  # fmt: skip
    got = json.loads(line.open_k1(w["sec"]["NTFY_KEY"], out["k1"]))
    assert got["ok"] and got["text"].startswith("# Linear algebra")
    # plain fields from the iPhone app pass through (and are refused there: only sealed ones may do this)
    code, out = ln.call("POST", "/chat", plain_chat("7" * 16, op="settings.set", args={"key": "notify.app_chat",
                                                                                         "value": True}),
                        key=keys["web"])  # fmt: skip
    assert code == 403 and not w["app"].settings.get("notify.app_chat")
    w["loop"].halt()
    wait(lambda: ln.call("GET", "/status", key=keys["web"])[1]["computer"] == "offline", 20, "offline")
    try:
        live = {**sealed_chat(w, "6" * 16, op="module", args={"id": "reminders", "on": True}), "live": True}
        code, out = ln.call("POST", "/chat", live, key=keys["android"])
        assert code == 503 and out["note"] == "Your computer is off, try again when it's on."
        out = ln.call("POST", "/chat", sealed_chat(w, "5" * 16, text="later", session=S1), key=keys["android"])[1]
        assert out["queued"] is True  # an ordinary message still waits
        assert all_chats(w)["sessions"][0]["id"] == "main"  # the list is there with the computer off
    finally:
        w["loop"] = Loop(w["app"])
    wait(lambda: not ln.call("GET", "/outbox", key=keys["android"])[1]["waiting"], 40, "the outbox to empty")

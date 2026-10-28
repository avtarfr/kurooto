"""The dashboard's Chat page (0.8.14; web/chat_api.py, static/chat.js): the phone app's chat on this computer, without
a call line. The same chats and messages as the app with unread counts, a message written on the page handled exactly
as one typed in the app, buttons and Waiting for you answered the same way as a tap in the app (so they settle
everywhere), the {"t": "chat"} live messages, the read mark shared with the app, the switch (look.chat_page), and the
dashboard's key in front of all of it."""

from __future__ import annotations

import json
import shutil
import subprocess
from importlib import resources

import pytest

from kurooto.modules.base import Command
from kurooto.web.api import Api
from tests.unit.test_chat_sessions import S1, ops, send
from tests.unit.test_dashboard import call, web  # noqa: F401 (the server fixture)
from tests.unit.test_phone import phone  # noqa: F401 (the shared fixture)
from tests.unit.test_phone_chat import said


class Live:
    """The dashboard's stream (web/live.py), recording what it would send to open pages."""

    def __init__(self):
        self.sent: list[dict] = []

    def push(self, msg, only=None):
        self.sent.append(json.loads(json.dumps(msg, default=str)))

    def chat(self, kind: str | None = None) -> list[dict]:
        return [m for m in self.sent if m.get("t") == "chat" and (kind is None or m.get("kind") == kind)]


@pytest.fixture
def page(phone):  # noqa: F811
    """Phone calls paired, a fake feature that answers /ping with buttons, the dashboard's API and stream."""

    def ping(msg, arg):
        msg.reply("pong", buttons=[[("Again", "fq:p1:again"), ("Docs", {"url": "https://example.com/d"})]])

    phone.fake_mod.commands = lambda: [Command("ping", "answers pong", ping)]
    phone.api = Api(phone.app)
    phone.live = Live()
    phone.app.live = phone.live
    phone.pc = phone.calls.chat
    phone.n = 0
    return phone


def test_the_page_lists_the_apps_chats_and_threads_with_unread(page):
    app, api = page.app, page.api
    app.handle = lambda msg: msg.reply("hi there")
    assert send(page, text="hello", session=S1)[0] == 200  # typed in the app, in a chat of its own
    app.settings.set("notify.app_chat", True)
    app.notify("Your train leaves at 9.", kind="reminder")  # Kurooto's own message: in "main"
    code, out = api.get("chat")
    assert code == 200 and out["on"] and out["name"]
    rows = {r["id"]: r for r in out["sessions"]}
    assert list(rows) == ["main", S1] and rows["main"]["unread"] == 1 and rows[S1]["unread"] == 1
    assert out["switches"]["chat_sessions"] is True and out["waiting"] == [] and out["working"] == []
    code, th = api.get("chat/thread", {"session": S1})
    assert code == 200 and [(m["from"], m["text"]) for m in th["msgs"]] == [("you", "hello"), ("kurooto", "hi there")]
    assert not any(k.startswith("_") or k == "pushed" for m in th["msgs"] for k in m)  # buttons' data stays here
    assert api.get("chat/thread", {"session": "f" * 16})[0] == 404
    # read on the page: the computer's mark moves, and the phones hear it quietly (as the app's own read mark)
    last = th["msgs"][-1]["id"]
    code, r = api.post("chat/op", {"op": "read", "session": S1, "upto": last})
    assert code == 200 and r["ok"] and page.calls.sessions.get(S1)["read"] == last
    assert ops(page, "chat-sessions")[-1]["quiet"] is True
    assert {r["id"]: r for r in api.get("chat")[1]["sessions"]}[S1]["unread"] == 0
    # read in the app: the page's count follows
    newest = api.get("chat/thread", {"session": "main"})[1]["msgs"][-1]["id"]
    send(page, op="read", args={"session": "main", "upto": newest})
    assert api.get("chat")[1]["sessions"][0]["unread"] == 0


def test_writing_on_the_page_is_handled_as_in_the_app(page):
    app, api = page.app, page.api
    n_tg = len(page.fake.texts())
    code, out = api.post("chat/send", {"session": "main", "text": "/ping"})
    assert code == 200 and out["ok"] and [m["text"] for m in out["said"]] == ["pong"]
    assert [(m["from"], m["text"]) for m in said(page)] == [("you", "/ping"), ("kurooto", "pong")]  # phones see both
    assert len(page.fake.texts()) == n_tg  # nothing on Telegram
    # its context and its chat: handled as an app message, in the open chat
    got = []
    app.handle = lambda msg: got.append((msg.via, msg.session, msg.message_id)) or msg.reply("ok")
    send(page, op="session.new", args={"session": S1, "title": "Topology"})
    code, out = api.post("chat/send", {"session": S1, "text": "compactness?"})
    assert code == 200 and got[-1][:2] == ("app", S1) and got[-1][2] == "app:" + out["id"]
    assert out["said"][0]["session"] == S1
    # a reply to Kurooto's message reaches the feature that sent it, as in the app
    app.settings.set("notify.app_chat", True)
    del app.handle
    app.notify("Your train leaves at 9.", kind="reminder", map_kind="fakeq", map_ref="r7")
    rid = said(page)[-1]["id"]
    code, out = api.post("chat/send", {"session": "main", "text": "moved to 10", "reply": rid})
    assert code == 200 and page.fake_mod.got[-1] == ("reply", "r7", "moved to 10", "app")
    # refusals
    assert api.post("chat/send", {"session": "main", "text": "  "})[0] == 400
    assert api.post("chat/send", {"session": "e" * 16, "text": "hi"})[0] == 404  # a chat that isn't there
    assert api.post("chat/op", {"op": "settings.set", "key": "x"})[0] == 400  # the being's requests are the phone's


def test_a_button_on_the_page_is_a_tap_in_the_app(page):
    api = page.api
    pong = api.post("chat/send", {"session": "main", "text": "/ping"})[1]["said"][0]
    code, out = api.post("chat/button", {"msg": pong["id"], "n": 0})
    assert code == 200 and out["note"] == "Did again." and page.fake_mod.got[-1] == ("button", "p1", "again")
    assert said(page)[-1]["text"] == "Did again."
    assert api.post("chat/button", {"msg": pong["id"], "n": 1})[0] == 400  # a link isn't pressed here
    assert api.post("chat/button", {"msg": "f" * 16, "n": 0})[0] == 400


def test_waiting_for_you_answered_on_the_page_settles_everywhere(page):
    app, api = page.app, page.api
    qid = app.ask.ask("Which topic first?", choices=["Bayes", "Markov"])
    waiting = api.get("chat")[1]["waiting"]
    assert len(waiting) == 1 and waiting[0]["qid"] == qid and waiting[0]["choices"] == ["Bayes", "Markov"]
    assert page.live.chat("waiting")  # the open page hears it came
    code, out = api.post("chat/answer", {"item": waiting[0]["id"], "answer": "Bayes"})
    assert code == 200 and out["ok"]
    q = app.ask.get(qid)
    assert q["status"] == "answered" and q["answer"] == "Bayes"
    assert ops(page, "notify-clear")  # off your phones too
    assert api.get("chat")[1]["waiting"] == []
    assert api.post("chat/answer", {"item": waiting[0]["id"], "answer": "Markov"})[0] == 410  # once
    assert api.post("chat/answer", {"item": "x"})[0] == 400
    # a message with buttons under Waiting for you: its button, as on the phone
    app.notify("How was the lecture?", kind="question", map_kind="fakeq", map_ref="r1",
               buttons=[[("Nothing", "fq:r1:none")]])  # fmt: skip
    it = api.get("chat")[1]["waiting"][0]
    assert api.post("chat/answer", {"item": it["id"], "button": 0})[1]["note"] == "Did none."
    assert page.fake_mod.got[-1] == ("button", "r1", "none") and api.get("chat")[1]["waiting"] == []


def test_new_messages_reach_the_open_page_live(page):
    app, api, live = page.app, page.api, page.live
    send(page, text="/ping")  # typed in the app
    msgs = [m["msg"] for m in live.chat("msg")]
    assert [(m["from"], m["text"]) for m in msgs] == [("you", "/ping"), ("kurooto", "pong")]
    assert all(not k.startswith("_") for m in msgs for k in m)
    send(page, op="session.new", args={"session": S1})
    assert live.chat("sessions")
    page.calls.chat.status(S1, "working", "j1")
    assert live.chat("status")[-1] == {"t": "chat", "kind": "status", "session": S1, "state": "working"}
    pong = msgs[-1]
    send(page, op="msg.pin", args={"target": pong["id"], "on": True})
    assert live.chat("msg")[-1]["update"] is True and live.chat("msg")[-1]["msg"]["pinned"] is True
    # the switch: off, the page's routes refuse and nothing about the chat goes to open pages
    app.settings.set("look.chat_page", False)
    n = len(live.chat())
    send(page, text="/ping")
    assert len(live.chat()) == n
    code, out = api.get("chat")
    assert code == 403 and out["off"] and "look.chat_page" in out["note"]
    assert api.post("chat/send", {"session": "main", "text": "hi"})[0] == 403
    app.settings.set("look.chat_page", True)
    assert api.get("chat")[0] == 200


def test_without_phone_calls_the_page_says_where_the_chat_comes_from(env):
    api = Api(env.app)
    code, out = api.get("chat")
    assert code == 200 and out["on"] is False and "Phone calls" in out["note"]
    assert api.post("chat/send", {"text": "hi"})[1]["on"] is False


def test_the_page_is_behind_the_dashboards_key(web):  # noqa: F811
    app, srv = web
    assert call(srv, "/api/chat", token=False)[0] == 401
    assert call(srv, "/api/chat/send", {"text": "hi"}, token=False)[0] == 403
    code, out = call(srv, "/api/chat")
    assert code == 200 and out["on"] is False  # Phone calls is off here
    assert app.settings.get("look.chat_page") is True  # on by default


def test_the_dashboard_has_the_chat_page():
    static = resources.files("kurooto.web") / "static"
    js = (static / "home.js").read_text(encoding="utf-8")
    pkey = js.split("const PKEY = {")[1].split("}")[0]
    keys = [k.split(":")[1].strip().strip('"') for k in pkey.split(",")]
    assert '"h"' in pkey.split("chat:")[1].split(",")[0] and len(keys) == len(set(keys))  # Alt+H, no clash
    assert "chat:" in js.split("const DLABEL")[1].split("\n")[0] and "chat:" in js.split("const TABS")[1].split("\n")[0]
    assert 'm.t === "chat"' in js and "look.chat_page" in js and "/static/chat.js" in js
    assert "K" not in [k.upper() for k in keys] and "M" not in [k.upper() for k in keys]  # the talk box, Study mode
    chat = (static / "chat.js").read_text(encoding="utf-8")
    assert "window.CHATPAGE" in chat and '"chat/send"' in chat and '"chat/answer"' in chat
    node = shutil.which("node")
    if node:
        assert subprocess.run([node, "--check", str(static / "chat.js")], capture_output=True).returncode == 0


def test_the_chat_fills_the_page_with_the_box_at_its_foot():
    """0.8.17: the chat's list is class "log", and style.css's .log (a box of at most 180 px, for setup's logs) shrank
    it, with the box to write in right under it and the rest of the page empty. The chat's own rule undoes it."""
    static = resources.files("kurooto.web") / "static"
    style = (static / "style.css").read_text(encoding="utf-8")
    assert ".log { font: 12px/1.5 var(--mono); color: var(--dim); max-height: 180px;" in style
    chat = (static / "chat.js").read_text(encoding="utf-8")
    log = chat.split(".cp .log{", 1)[1].split("}", 1)[0]
    assert "flex:1" in log and "min-height:0" in log and "max-height:none" in log and "margin:0" in log
    th = chat.split(".cp .th{", 1)[1].split("}", 1)[0]
    assert "flex-direction:column" in th and "min-height:0" in th

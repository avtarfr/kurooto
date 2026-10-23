"""The phone app's chat and the phone outbox, end to end on this computer: the real Worker under `wrangler dev`, the
real connector and Phone calls feature, fake ntfy and Web Push (see test_call_line.py for the setup).

A typed message reaches this computer and is handled like a Telegram one; the answer reaches both kinds of phone
(sealed ntfy for Android, an empty push + /pending or /chat for the web app); buttons work by number. With this
computer off, chat messages, answers and shared files wait on the line in order, the phone sees them waiting, and
when the computer is back they're taken one at a time, each once, and the phone hears they went through.
"""

from __future__ import annotations

import json
import os
import time

import pytest

from kurooto.modules.base import Command
from kurooto.modules.calls import line
from tests.integration.test_call_line import Loop, pytestmark, wait, world  # noqa: F401 (the shared fixture)
from tests.integration.test_phone_line import ntfy_after, pending, phones, plain_answer  # noqa: F401


@pytest.fixture(scope="module")
def chats(phones):  # noqa: F811
    def ping(msg, arg):
        msg.reply("pong", buttons=[[("Again", "fq:p1:again")]])

    phones["fake"].commands = lambda: [Command("ping", "answers pong", ping)]
    return phones


def sealed_chat(w, mid, **fields):
    f = {"id": mid, "ts": int(time.time() * 1000), "n": os.urandom(16).hex(), **fields}
    return {"id": mid, "k1": line.seal_k1(w["sec"]["NTFY_KEY"], json.dumps(f))}


def plain_chat(mid, **fields):
    return {"id": mid, "ts": int(time.time() * 1000), "n": os.urandom(16).hex(), **fields}


def chat_log(w, after=0, kind="web"):
    return w["line"].call("GET", f"/chat?after={after}", key=w["keys"][kind])[1]


def test_a_chat_message_and_its_answer(chats):
    w, ln = chats, chats["line"]
    n0, p0 = len(w["cloud"].ntfy), len(w["cloud"].pushes)
    code, out = ln.call("POST", "/chat", sealed_chat(w, "a" * 16, text="/ping"), key=w["keys"]["android"])
    assert code == 200 and out["ok"] and [m["text"] for m in out["said"]] == ["pong"], out
    m = ntfy_after(w, n0, "chat")
    assert m["message"] == "pong" and "stop" in m["tags"] and m["re"] == "a" * 16  # "stop": older apps ignore it
    assert m["buttons"] == [{"label": "Again"}]
    wait(lambda: len(w["cloud"].pushes) > p0, 15, "the web push")
    log = wait(lambda: (lambda j: j if len(j["msgs"]) >= 2 else None)(chat_log(w)), 10, "the chat log")
    assert [(x["from"], x["text"]) for x in log["msgs"]] == [("you", "/ping"), ("kurooto", "pong")]
    assert log["msgs"][0]["seq"] < log["msgs"][1]["seq"] and log["waiting"] == [] and log["computer"] == "online"
    assert chat_log(w, after=log["msgs"][0]["seq"])["msgs"][0]["text"] == "pong"
    assert ln.call("GET", "/pending", key=w["keys"]["web"])[1]["chat"][-1]["text"] == "pong"  # for the service worker
    # a button under it, tapped in the web app
    code, out = ln.call("POST", "/chat", plain_chat("b" * 16, button=0, msg=m["id"]), key=w["keys"]["web"])
    assert code == 200 and out["note"] == "Did again." and w["fake"].got[-1] == ("button", "p1", "again")
    assert ln.call("POST", "/chat", plain_chat("c" * 16, text="hi")) == (401, {"error": "wrong or missing key"})
    assert ln.call("POST", "/chat", {"id": "nope"}, key=w["keys"]["web"])[0] == 400


def test_the_phone_outbox(chats):
    w, app, ln, keys = chats, chats["app"], chats["line"], chats["keys"]
    n0 = len(w["cloud"].ntfy)
    app.notify("Which chapter next?", kind="question", map_kind="fakeq", map_ref="r5")
    item = ntfy_after(w, n0, "msg")["id"]
    seq0 = chat_log(w)["seq"]
    w["loop"].halt()
    wait(lambda: ln.call("GET", "/status", key=keys["web"])[1]["computer"] == "offline", 20, "offline")

    out = ln.call("POST", "/chat", sealed_chat(w, "1" * 16, text="/ping"), key=keys["android"])[1]
    assert out["queued"] is True and "waits on your call line" in out["note"]
    assert ln.call("POST", "/answer", plain_answer(item, answer="Chapter 5"), key=keys["web"])[1]["queued"] is True
    raw = os.urandom(700 * 1024)
    for part, chunk in enumerate((raw[: 512 * 1024], raw[512 * 1024 :])):
        q = f"/upload?name=scan.pdf&note=&id=f00d&part={part}&parts=2"
        code, out = ln.call("POST", q, raw=chunk, key=keys["android"], ctype="application/octet-stream")
        assert code == 200 and out["queued"] is True, out
    out = ln.call("POST", "/chat", sealed_chat(w, "2" * 16, text="/ping"), key=keys["android"])[1]
    assert out["queued"] is True
    big = "/upload?name=huge.bin&id=f00e&part=0&parts=41"  # a whole file must fit (20 MB)
    code, out = ln.call("POST", big, raw=b"x", key=keys["android"], ctype="application/octet-stream")
    assert code == 507 and "holding as much as it can" in out["note"]
    code, out = ln.call("POST", "/upload?name=t.txt&id=f00f&part=0&parts=1", raw=b"x", key="t1.0.0")
    assert code == 401
    box = ln.call("GET", "/outbox", key=keys["android"])[1]
    want = [("1" * 16, "chat"), ("f00d", "upload"), ("2" * 16, "chat")]
    assert [(x["oid"], x["kind"]) for x in box["waiting"]] == want
    assert box["computer"] == "offline"
    assert [x["oid"] for x in ln.call("GET", "/outbox", key=keys["web"])[1]["waiting"]] == [item]

    n1 = len(w["cloud"].ntfy)
    w["loop"] = Loop(app)
    wait(lambda: not ln.call("GET", "/outbox", key=keys["android"])[1]["waiting"], 40, "the outbox to empty")
    wait(lambda: ("reply", "r5", "Chapter 5", "app") in w["fake"].got, 10, "the kept answer")
    log = chat_log(w, after=seq0)["msgs"]
    assert [(x["from"], x["text"]) for x in log] == [("you", "/ping"), ("kurooto", "pong")] * 2  # in order, once each
    saved = [p for p in (app.workspace / "inbox").iterdir() if p.name.endswith("scan.pdf")]
    assert len(saved) == 1 and saved[0].read_bytes() == raw
    done = ln.call("GET", "/outbox", key=keys["android"])[1]["done"]
    assert {(d["oid"], d["ok"]) for d in done} == {("1" * 16, True), ("f00d", True), ("2" * 16, True)}
    told = wait(lambda: [m for m in outbox_notes(w, n1) if m["dev"] == keys["android"].split(".")[1]], 15, "told")
    assert {d["oid"] for m in told for d in m["done"]} >= {"1" * 16, "f00d", "2" * 16}
    assert all("stop" in m["tags"] for m in told)


def outbox_notes(w, n0):
    out = []
    for m in w["cloud"].ntfy[n0:]:
        inner = json.loads(line.open_k1(w["sec"]["NTFY_KEY"], m["message"]) or "{}")
        if "outbox" in inner.get("tags", []):
            out.append(inner)
    return out


def test_a_file_for_the_chat_waits_sealed_on_the_line(chats, tmp_path):
    """Where Telegram would get a document, the chat gets a link: the line keeps the sealed bytes, the key is only in
    the link's #fragment, and the file page fetches it (0.5.19)."""
    import urllib.parse
    import urllib.request

    from kurooto.modules.calls import chat as chatmod

    w, ln = chats, chats["line"]
    f = tmp_path / "answer.md"
    f.write_bytes(os.urandom(chatmod.FILE_PART + 1000))
    link, why = w["calls"].chat.to_line(f)
    assert link and not why, why
    assert link.startswith(ln.base + "/file#")
    frag = dict(urllib.parse.parse_qsl(link.split("#", 1)[1]))
    with urllib.request.urlopen(f"{ln.base}/sealed/{frag['i']}", timeout=30) as r:  # no key needed: it's sealed
        blob = r.read()
    assert blob != f.read_bytes() and line.open_f1(line.unb64url(frag["k"]), blob) == f.read_bytes()
    assert ln.call("GET", "/sealed/" + "0" * 32)[0] == 404
    assert ln.call("GET", "/sealed/nothex")[0] == 404
    for page, word in (("/file", "file.js"), ("/talk", "talk.js")):  # the file page, and the web app's chat
        with urllib.request.urlopen(ln.base + page, timeout=30) as r:
            assert word in r.read().decode()
    big = tmp_path / "big.bin"
    big.write_bytes(b"\0" * (chatmod.FILE_MAX + 1))
    assert w["calls"].chat.to_line(big)[0] == ""  # too big: said so, nothing sent

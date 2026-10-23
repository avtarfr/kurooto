"""Tell Kurooto (the iPhone Shortcut), end to end on this computer: the real Worker under `wrangler dev`, the real
connector and Phone calls feature (see test_call_line.py for the setup).

A paired phone makes its Shortcut link; what the Shortcut sends is handled like a chat message from that phone and
the answer comes back as plain text; the link opens no other door; this computer lists the links and revokes one;
unpairing the phone ends its link; with this computer off the message waits in the outbox.
"""

from __future__ import annotations

import urllib.error
import urllib.request

from tests.integration.test_call_line import Loop, pytestmark, wait, world  # noqa: F401 (the shared fixture)
from tests.integration.test_phone_chat_line import chat_log, chats  # noqa: F401
from tests.integration.test_phone_line import phones  # noqa: F401


def tell(base, path, data=b"", ctype="application/json", method="POST"):
    req = urllib.request.Request(base + path, data=data if method == "POST" else None, method=method)
    req.add_header("content-type", ctype)
    try:
        with urllib.request.urlopen(req, timeout=70) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def test_make_send_scope_and_revoke(chats):  # noqa: F811
    w, ln, calls, keys = chats, chats["line"], chats["calls"], chats["keys"]
    assert ln.call("GET", "/shortcut", key=keys["web"]) == (200, {"shortcut": None})
    assert ln.call("POST", "/shortcut/new", {}, key="t1.0.0")[0] == 401  # paired phones only
    code, made = ln.call("POST", "/shortcut/new", {}, key=keys["web"])
    assert code == 200 and made["token"].startswith("tk1.") and made["url"] == f"{ln.base}/tell/{made['token']}"
    path = "/tell/" + made["token"]
    wait(lambda: any("Tell Kurooto link was made on iPhone" in m.text for m in w["sent"]), 10, "the notice")

    # it sends a chat message as that phone; the answer is plain text for the Shortcut to speak
    seq0 = chat_log(w)["seq"]
    assert tell(ln.base, path, b'{"text": "/ping"}') == (200, "pong")
    assert tell(ln.base, path, b"text=%2Fping", "application/x-www-form-urlencoded") == (200, "pong")
    assert tell(ln.base, path, b"/ping", "text/plain") == (200, "pong")
    log = chat_log(w, after=seq0)["msgs"]
    assert [(m["from"], m["text"]) for m in log[:2]] == [("you", "/ping"), ("kurooto", "pong")]
    assert tell(ln.base, path, b'{"text": "  "}')[0] == 400
    assert tell(ln.base, path, method="GET")[0] == 405

    # the link is no key anywhere else, and a near miss is no link
    for p in ("/status", "/pending", "/chat", "/outbox", "/shortcut", "/app-call"):
        assert ln.call("GET", p, key=made["token"])[0] == 401, p
    assert tell(ln.base, path[:-1] + ("0" if path[-1] != "0" else "1"), b'{"text": "hi"}')[0] == 401
    assert tell(ln.base, "/tell/" + keys["web"], b'{"text": "hi"}')[0] in (401, 404)

    # listed on this computer, one per phone: a new one replaces it
    listed = calls.shortcuts()
    assert [(s["id"], s["device_name"]) for s in listed] == [(made["id"], "iPhone")] and listed[0]["used"]
    assert ln.call("GET", "/shortcut", key=keys["web"])[1]["shortcut"]["id"] == made["id"]
    again = ln.call("POST", "/shortcut/new", {}, key=keys["web"])[1]
    assert tell(ln.base, path, b'{"text": "/ping"}')[0] == 401  # the old one stopped working
    assert [s["id"] for s in calls.shortcuts()] == [again["id"]]

    # revoked on this computer: gone at once, the phone stays paired
    assert calls.shortcut_revoke(again["id"]) is True and calls.shortcut_revoke(again["id"]) is False
    assert calls.shortcut_revoke("not-an-id") is False
    assert tell(ln.base, "/tell/" + again["token"], b'{"text": "/ping"}')[0] == 401
    assert calls.shortcuts() == [] and ln.call("GET", "/pending", key=keys["web"])[0] == 200

    # the phone removes its own
    third = ln.call("POST", "/shortcut/new", {}, key=keys["web"])[1]
    assert ln.call("POST", "/shortcut/off", {}, key=keys["web"]) == (200, {"ok": True})
    assert tell(ln.base, "/tell/" + third["token"], b'{"text": "/ping"}')[0] == 401


def test_offline_and_unpaired(chats):  # noqa: F811
    w, ln, calls, keys = chats, chats["line"], chats["calls"], chats["keys"]
    made = ln.call("POST", "/shortcut/new", {}, key=keys["web"])[1]
    path = "/tell/" + made["token"]
    seq0 = chat_log(w)["seq"]
    w["loop"].halt()
    wait(lambda: ln.call("GET", "/status", key=keys["web"])[1]["computer"] == "offline", 20, "offline")
    code, said = tell(ln.base, path, b'{"text": "/ping"}')
    assert code == 200 and "waits on your call line" in said
    assert [x["kind"] for x in ln.call("GET", "/outbox", key=keys["web"])[1]["waiting"]] == ["chat"]
    w["loop"] = Loop(w["app"])
    wait(lambda: not ln.call("GET", "/outbox", key=keys["web"])[1]["waiting"], 40, "the outbox to empty")
    log = chat_log(w, after=seq0)["msgs"]
    assert [(m["from"], m["text"]) for m in log] == [("you", "/ping"), ("kurooto", "pong")]

    # unpairing the phone ends its link
    phone = keys["web"].split(".")[1]
    assert calls.revoke(phone) is True
    assert tell(ln.base, path, b'{"text": "/ping"}')[0] == 401
    assert calls.shortcuts() == []


def test_bedside_reads_what_is_coming(world):  # noqa: F811
    import datetime

    ln, calls = world["line"], world["calls"]
    p = calls.pair_start()
    phone = ln.call("POST", "/pair/claim", {"code": p["code"], "kind": "android", "name": "Old phone"})[1]["device"]
    at = datetime.datetime.now() + datetime.timedelta(hours=8)
    calls.schedule(at, "Wake-up call", key="alarm:test", alarm=True)  # pokes the connector

    def got():
        r = ln.call("GET", "/upcoming", key=phone)[1]
        return r if any(c["reason"] == "Wake-up call" for c in r.get("calls", [])) else None

    up = wait(got, 20, "the schedule on the line")
    wake = [c for c in up["calls"] if c["alarm"]][0]
    assert wake == {"at": int(at.timestamp()), "reason": "Wake-up call", "alarm": True}
    assert up["computer"] == "online" and isinstance(up["waiting"], int)
    assert ln.call("GET", "/upcoming", key=calls.link().split("#", 1)[1])[0] == 403  # a call link isn't a phone
    calls.revoke(phone.split(".")[1])

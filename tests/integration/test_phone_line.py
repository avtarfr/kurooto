"""The phone as a second channel, end to end on this computer: the real Worker under `wrangler dev`, the real
connector and Phone calls feature, fake ntfy and Web Push (see test_call_line.py for the setup).

A question reaches both kinds of phone (sealed ntfy for Android, an empty push + /pending for the web app), answers
come back through /answer (sealed, single use), things dealt with elsewhere are cleared from the phones, a call in
progress shows as "you're on a call", and an answer given while this computer is off waits for it.
"""

from __future__ import annotations

import json
import os
import time

import pytest

from kurooto.core.availability import ON_CALL
from kurooto.modules.calls import line
from tests.integration.test_call_line import Loop, pytestmark, wait, world  # noqa: F401 (the shared fixture)
from tests.unit.test_phone import Fake


@pytest.fixture(scope="module")
def phones(world):  # noqa: F811
    app, calls, ln, cloud = world["app"], world["calls"], world["line"], world["cloud"]
    fake = Fake(app)
    app.modules["fakeq"] = fake
    app.settings.set("modules.enabled", [*app.settings.get("modules.enabled"), "fakeq"])
    calls.start()  # registers the `app` channel, as the daemon does
    keys = {}
    for kind, name in (("android", "Test phone"), ("web", "iPhone")):
        p = calls.pair_start()
        code, got = ln.call("POST", "/pair/claim", {"code": p["code"], "kind": kind, "name": name})
        assert code == 200, got
        keys[kind] = got["device"]
    sub = {"endpoint": f"{cloud.base}/push/web1", "keys": {}}
    assert ln.call("POST", "/push/subscribe", {"subscription": sub}, key=keys["web"])[0] == 200
    world.update(fake=fake, keys=keys)
    return world


def ntfy_after(w, n0, tag):
    """The first ntfy message since n0 with this tag, opened."""

    def find():
        for m in w["cloud"].ntfy[n0:]:
            inner = json.loads(line.open_k1(w["sec"]["NTFY_KEY"], m["message"]) or "{}")
            if tag in inner.get("tags", []):
                return inner
        return None

    return wait(find, 20, f"an ntfy message tagged {tag}")


def pending(w):
    return w["line"].call("GET", "/pending", key=w["keys"]["web"])[1]["items"]


def sealed_answer(w, item, **fields):
    body = {"item": item, "ts": int(time.time() * 1000), "n": os.urandom(16).hex(), **fields}
    return {"item": item, "k1": line.seal_k1(w["sec"]["NTFY_KEY"], json.dumps(body))}


def plain_answer(item, **fields):
    return {"item": item, "ts": int(time.time() * 1000), "n": os.urandom(16).hex(), **fields}


def test_a_question_reaches_both_phones(phones):
    w, app = phones, phones["app"]
    n0, p0 = len(w["cloud"].ntfy), len(w["cloud"].pushes)
    app.notify(
        "How was the lecture?", kind="question", map_kind="fakeq", map_ref="r1", buttons=[[("Nothing", "fq:r1:none")]]
    )
    m = ntfy_after(w, n0, "msg")
    assert m["message"] == "How was the lecture?" and m["kind"] == "question" and m["reply"] is True
    assert m["buttons"] == [{"label": "Nothing"}] and "kind-question" in m["tags"] and m["priority"] == 4
    wait(lambda: len(w["cloud"].pushes) > p0, 15, "the web push")
    assert w["cloud"].pushes[-1]["len"] == 0  # the push carries nothing
    items = wait(lambda: [i for i in pending(w) if i["id"] == m["id"]], 10, "the inbox")
    assert items[0]["text"] == "How was the lecture?" and not any(k.startswith("_") for k in items[0])
    w["r1"] = m["id"]


def test_a_sealed_answer_from_android_is_used_once(phones):
    w, ln = phones, phones["line"]
    item = w["r1"]
    n0 = len(w["cloud"].ntfy)
    body = sealed_answer(w, item, answer="Limits and continuity")
    code, out = ln.call("POST", "/answer", body, key=w["keys"]["android"])
    assert code == 200 and out == {"ok": True, "note": "Noted."}, out
    assert w["fake"].got == [("reply", "r1", "Limits and continuity", "app")]
    clear = ntfy_after(w, n0, "clear")
    assert item in clear["ids"] and "stop" in clear["tags"]  # "stop" keeps older apps quiet
    assert all(i["id"] != item for i in pending(w))
    assert ln.call("POST", "/answer", body, key=w["keys"]["android"])[0] in (409, 410)
    assert len(w["fake"].got) == 1
    assert ln.call("POST", "/answer", body)[0] == 401  # needs a paired phone
    assert ln.call("POST", "/answer", {"item": "nope"}, key=w["keys"]["android"])[0] == 400


def test_an_approval_answered_on_the_web_app(phones):
    w, app, ln = phones, phones["app"], phones["line"]
    aid = app.ask.ask("Send the draft to Sam?", kind="approval")
    it = wait(lambda: next((i for i in pending(w) if i.get("qid") == aid), None), 15, "the approval")
    assert it["choices"] == ["Approve", "Deny"] and it["later"] is True
    code, out = ln.call("POST", "/answer", plain_answer(it["id"], answer="Deny"), key=w["keys"]["web"])
    assert code == 200 and out["ok"], out
    q = app.ask.get(aid)
    assert q["status"] == "answered" and q["answer"] == "Deny" and q["via"] == "app"


def test_dealt_with_on_telegram_comes_off_the_phones(phones):
    w, app = phones, phones["app"]
    n0 = len(w["cloud"].ntfy)
    app.notify(
        "Anything to add?", kind="question", map_kind="fakeq", map_ref="r2", buttons=[[("Nothing", "fq:r2:none")]]
    )
    item = ntfy_after(w, n0, "msg")["id"]
    wait(lambda: any(i["id"] == item for i in pending(w)), 10, "the inbox")
    n1 = len(w["cloud"].ntfy)
    assert app.callback("fq:r2:none") == "Did none."  # tapped on Telegram
    assert item in ntfy_after(w, n1, "clear")["ids"]
    wait(lambda: all(i["id"] != item for i in pending(w)), 10, "the inbox to forget it")


def test_on_a_call(phones):
    w, app, ln = phones, phones["app"], phones["line"]
    assert ln.call("POST", "/token", {}, key=w["keys"]["android"])[0] == 200
    wait(lambda: app.availability.call_block()[0] == ON_CALL, 15, "on a call")
    ln.call("GET", "/tasks", key=w["keys"]["android"])
    assert ln.call("POST", "/transcript", {"lines": [], "ended": True}, key=w["keys"]["android"])[0] == 200
    wait(lambda: app.availability.call_block()[0] != ON_CALL, 15, "the call to end")


def test_an_answer_waits_while_the_computer_is_off(phones):
    w, app, ln = phones, phones["app"], phones["line"]
    n0 = len(w["cloud"].ntfy)
    app.notify("Which chapter next?", kind="question", map_kind="fakeq", map_ref="r3")
    item = ntfy_after(w, n0, "msg")["id"]
    w["loop"].halt()
    wait(lambda: ln.call("GET", "/status", key=w["keys"]["web"])[1]["computer"] == "offline", 20, "offline")
    assert any(i["id"] == item for i in pending(w))  # the web app can still see it
    code, out = ln.call("POST", "/answer", plain_answer(item, answer="Chapter 4"), key=w["keys"]["web"])
    assert code == 200 and out["queued"] is True
    assert all(i["id"] != item for i in pending(w))
    w["loop"] = Loop(app)
    wait(lambda: w["calls"].connector.connected, 30, "reconnect")
    wait(lambda: ("reply", "r3", "Chapter 4", "app") in w["fake"].got, 15, "the kept answer")

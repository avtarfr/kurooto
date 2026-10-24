"""The Android app's own connection to the call line (0.7.0), end to end on this computer: the real Worker under
`wrangler dev`, the real connector and Phone calls feature, a fake ntfy (see test_call_line.py for the setup), and a
WebSocket client standing in for the app.

A paired Android phone connects to /phone with its key and hears a hello; what the line sends the phones comes down
it sealed as on ntfy, with a message id, and ntfy isn't used for it while the phone is connected (a ring still goes
both ways, with the same id); "ping" is answered "pong"; a phone that reconnects gets what it missed; the computer's
own messages for the phones go through the line's /send; the dashboard sees who's connected; one connection per
phone; the computer's link isn't touched by the phones'; unpairing closes the phone's connection.
"""

from __future__ import annotations

import json
import time

import pytest
from websockets.exceptions import ConnectionClosed, InvalidStatus
from websockets.sync.client import connect

from kurooto.modules.calls import line
from tests.integration.test_call_line import Loop, pytestmark, wait, world  # noqa: F401 (the shared fixture)
from tests.integration.test_phone_line import phones  # noqa: F401

pytestmark = [pytestmark, pytest.mark.filterwarnings("ignore:connect\\(\\) must be used:DeprecationWarning")]  # noqa: F811


class Phone:
    """What the app does on its connection: read, open each message with the key from pairing."""

    opened: list = []  # every connection made here, closed when the module is done

    def __init__(self, w, key, after=0):
        self.w, self.got = w, []
        Phone.opened.append(self)
        url = w["line"].base.replace("http://", "ws://") + f"/phone?after={after}"
        self.ws = connect(url, additional_headers={"x-call-secret": key}, open_timeout=15)  # noqa: SIM115
        self.hello = json.loads(self.ws.recv(timeout=10))

    def read(self, timeout=0.5):
        """Everything that came within `timeout` of the last one: [(seq, message opened)]."""
        out = []
        while True:
            try:
                raw = self.ws.recv(timeout=timeout)
            except TimeoutError:
                return out
            if raw == "pong":
                out.append((0, "pong"))
                continue
            j = json.loads(raw)
            out.append((j["seq"], json.loads(line.open_k1(self.w["sec"]["NTFY_KEY"], j["k1"]))))
            self.got.append(out[-1])

    def wait_for(self, tag, timeout=20):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            for seq, m in self.read(0.5):
                if isinstance(m, dict) and tag in m.get("tags", []):
                    return seq, m
        raise AssertionError(f"no message tagged {tag} on the phone's connection")

    def close(self):
        self.ws.close()


def closed_soon(ws, timeout=20):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            ws.recv(timeout=1)
        except TimeoutError:
            continue
        except ConnectionClosed:
            return True
    return False


def ntfy_mids(w, n0):
    return [
        json.loads(line.open_k1(w["sec"]["NTFY_KEY"], m["message"]) or "{}").get("mid") for m in w["cloud"].ntfy[n0:]
    ]


@pytest.fixture(scope="module")
def direct(phones):  # noqa: F811
    phones["phone"] = Phone(phones, phones["keys"]["android"])
    yield phones
    for p in Phone.opened:
        p.close()


def test_only_a_paired_android_phone_connects(direct):
    w = direct
    assert w["phone"].hello["type"] == "hello" and isinstance(w["phone"].hello["seq"], int)
    for key, code in ((w["keys"]["web"], 403), ("d1.00000000." + "0" * 64, 401), ("", 401)):
        with pytest.raises(InvalidStatus) as e:
            connect(w["line"].base.replace("http://", "ws://") + "/phone", additional_headers={"x-call-secret": key})
        assert e.value.response.status_code == code
    devs = {d["kind"]: d for d in w["calls"].devices()}
    assert devs["android"]["connected"] is True and devs["android"]["heard"]
    assert "connected" not in devs["web"]  # the web app has Web Push, not a connection of its own
    assert w["calls"].phones_direct()


def test_a_message_comes_down_the_connection_and_not_through_ntfy(direct):
    w, p = direct, direct["phone"]
    n0 = len(w["cloud"].ntfy)
    w["app"].notify("Did the lab report go in?", kind="question", map_kind="fakeq", map_ref="d1")
    _, m = p.wait_for("msg")
    assert m["message"] == "Did the lab report go in?" and len(m["mid"]) == 16 and m["assistant"] == "Kurooto"
    time.sleep(1.5)
    assert m["mid"] not in ntfy_mids(w, n0)  # connected: ntfy isn't needed


def test_a_ring_goes_both_ways_with_one_id(direct):
    w, p = direct, direct["phone"]
    n0 = len(w["cloud"].ntfy)
    since = w["calls"].ring("Time for the reading group")
    _, m = p.wait_for("call")
    assert f"since-{since}" in m["tags"] and m["click"].startswith(w["line"].base)
    wait(lambda: m["mid"] in ntfy_mids(w, n0), 20, "the same ring on ntfy")  # the phone keeps the first copy
    assert ntfy_mids(w, n0).count(m["mid"]) == 1  # the computer didn't publish another: the line said android
    w["calls"]._missed({"since": since})
    p.wait_for("stop")


def test_ping_is_answered(direct):
    p = direct["phone"]
    p.ws.send("ping")
    assert (0, "pong") in p.read(2)


def test_the_computers_own_messages_go_through_the_line(direct):
    w, p = direct, direct["phone"]
    n0 = len(w["cloud"].ntfy)
    assert w["calls"].send_phones({"title": "stop", "message": "", "tags": ["stop", "since-1"], "time": 1})
    _, m = p.wait_for("stop")
    assert m["tags"] == ["stop", "since-1"]
    time.sleep(1)
    assert m["mid"] not in ntfy_mids(w, n0)
    code, _ = w["line"].call("POST", "/send", {"fields": {"title": "x"}}, key=None)
    assert code == 401  # without the connector secret


def test_one_connection_per_phone_and_the_computer_keeps_its_own(direct):
    w = direct
    second = Phone(w, w["keys"]["android"], after=w["phone"].hello["seq"])
    assert closed_soon(w["phone"].ws)
    w["phone"] = second
    assert w["calls"].connector.connected
    code, r = w["line"].call("POST", "/tool", {"name": "pending_items", "args": {}}, key=w["keys"]["android"])
    assert code == 200 and "result" in r  # still relayed to this computer


def test_a_phone_that_reconnects_gets_what_it_missed_and_ntfy_carries_it_meanwhile(direct):
    w = direct
    last = max([s for s, _ in w["phone"].got] + [w["phone"].hello["seq"]])
    w["phone"].close()
    time.sleep(1)
    n0 = len(w["cloud"].ntfy)
    w["app"].notify("Library books are due tomorrow", kind="question", map_kind="fakeq", map_ref="d2")
    wait(lambda: len(w["cloud"].ntfy) > n0, 20, "ntfy while the phone is away")
    back = Phone(w, w["keys"]["android"], after=last)
    got = back.read(2)
    texts = [m.get("message") for _, m in got if isinstance(m, dict)]
    assert "Library books are due tomorrow" in texts and all(s > last for s, _ in got)
    mid = next(m["mid"] for _, m in got if isinstance(m, dict) and m.get("message") == "Library books are due tomorrow")
    assert mid in ntfy_mids(w, n0)  # the same message both ways: the app drops the second by its id
    w["phone"] = back


def test_unpairing_closes_the_phones_connection(direct):
    w, calls = direct, direct["calls"]
    p = calls.pair_start()
    code, got = w["line"].call("POST", "/pair/claim", {"code": p["code"], "kind": "android", "name": "Spare phone"})
    assert code == 200
    spare = Phone(w, got["device"])
    assert calls.revoke(got["id"])
    assert closed_soon(spare.ws)

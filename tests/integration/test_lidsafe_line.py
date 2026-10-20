"""Reminders with the lid shut, end to end on this computer: the real Worker under `wrangler dev`, the real connector,
Phone calls and Reminders, a fake ntfy (see test_call_line.py for the setup).

The Android app gives its public key; reminders go to the call line sealed for it (the line keeps times and
ciphertext); with this computer away the cron sends a due one to the phone once, and back here it isn't said again;
one claimed here at its time is never sent by the line; a send the line couldn't make is this computer's when it's
back; and with the feature off the line drops what it holds.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import time
import urllib.request

import pytest

from kurooto.modules.calls import line
from kurooto.modules.lidsafe import item_id
from tests.integration.test_call_line import Loop, pytestmark, wait, world  # noqa: F401 (the shared fixture)
from tests.unit.test_lidsafe import Phone


@pytest.fixture(scope="module")
def lid(world):  # noqa: F811
    app, calls, ln = world["app"], world["calls"], world["line"]
    calls.start()
    app.settings.set("modules.enabled", [*app.settings.get("modules.enabled"), "calls", "reminders", "lidsafe"])
    app.modules["reminders"].start()
    p = calls.pair_start()
    code, got = ln.call("POST", "/pair/claim", {"code": p["code"], "kind": "android", "name": "Test phone"})
    assert code == 200, got
    p = calls.pair_start()
    code, web = ln.call("POST", "/pair/claim", {"code": p["code"], "kind": "web", "name": "iPhone"})
    assert code == 200, web
    world.update(
        phone=Phone(), android=got["device"], android_id=got["id"], web=web["device"], ls=app.modules["lidsafe"]
    )
    return world


def on_loop(w, coro, timeout=30):
    return asyncio.run_coroutine_threadsafe(coro, w["loop"].loop).result(timeout)


def away(w) -> None:
    w["loop"].halt()
    wait(lambda: w["line"].call("GET", "/status", key=w["android"])[1].get("computer") == "offline", 20, "offline")


def back(w) -> None:
    w["loop"] = Loop(w["app"])
    wait(lambda: w["calls"].connector.connected, 30, "reconnect")


def cron(w) -> None:
    with urllib.request.urlopen(w["line"].base + "/__scheduled?cron=*+*+*+*+*", timeout=30) as r:
        assert r.status == 200


def sealed_sent(w, n0: int) -> list[dict]:
    """The sealed reminders the line sent to ntfy since n0, opened with the ntfy key (the outer layer only)."""
    out = []
    for m in w["cloud"].ntfy[n0:]:
        inner = json.loads(line.open_k1(w["sec"]["NTFY_KEY"], m["message"]) or "{}")
        if "sealed" in inner.get("tags", []):
            out.append(inner)
    return out


def remind(w, seconds: float, what: str) -> tuple[str, float]:
    w["app"].modules["reminders"].add(dt.datetime.now() + dt.timedelta(seconds=seconds), what)
    j = next(j for j in w["app"].scheduler.jobs("reminders:") if j.payload["what"] == what)
    return item_id("rem", j.payload["ref"]), j.next_run


def said_here(w, what: str) -> list[str]:
    return [m.text for m in w["sent"] if m.text.startswith("Reminder") and m.text.endswith(what)]


def tick(w) -> None:
    asyncio.run(w["app"].scheduler.tick())


def test_the_android_app_gives_its_key(lid):
    w, ln, ls = lid, lid["line"], lid["ls"]
    ls._dirty = False
    assert ln.call("POST", "/device/key", {"pub": w["phone"].pub}, key=w["android"]) == (200, {"ok": True})
    assert ln.call("POST", "/device/key", {"pub": "not a key"}, key=w["android"])[0] == 400
    assert ln.call("POST", "/device/key", {"pub": w["phone"].pub}, key=w["web"])[0] == 403  # only the app has one
    assert ln.call("POST", "/device/key", {"pub": w["phone"].pub})[0] == 401
    devs = {d["id"]: d for d in w["calls"].devices()}
    assert devs[w["android_id"]]["seal"] == w["phone"].pub
    wait(lambda: ls._dirty, 10, "the computer hearing about the key")  # it seals for that phone from now on


def test_asleep_the_line_sends_it_once_and_back_here_it_isnt_said_again(lid):
    w, ls = lid, lid["ls"]
    rid, at = remind(w, 5, "stretch")
    res = on_loop(w, ls.push(force=True))
    assert res["ok"] and res["held"] == 1
    away(w)
    n0 = len(w["cloud"].ntfy)
    time.sleep(max(0.0, at - time.time()) + 0.5)
    cron(w)
    got = wait(lambda: sealed_sent(w, n0), 15, "the sealed reminder")
    assert len(got) == 1 and got[0]["id"] == rid and got[0]["dev"] == w["android_id"]
    assert "stretch" not in json.dumps(got[0])  # inside it, only the phone's copy, which the line can't open
    assert w["phone"].open(got[0]["sealed"])["text"] == "Reminder: stretch"
    cron(w)
    time.sleep(1)
    assert len(sealed_sent(w, n0)) == 1  # one answer per item
    back(w)
    wait(lambda: (ls._said().get(rid) or {}).get("by") == "line", 15, "the line telling it sent it")
    tick(w)  # the reminder comes due here too
    assert said_here(w, "stretch") == []


def test_claimed_here_at_its_time_the_line_stays_quiet(lid):
    w, ls = lid, lid["ls"]
    rid, at = remind(w, 4, "tea")
    assert on_loop(w, ls.push())["ok"]
    time.sleep(max(0.0, at - time.time()) + 0.3)
    tick(w)  # held back for the line's answer, which comes at once
    wait(lambda: (ls._said().get(rid) or {}).get("by") == "computer", 15, "the claim")
    tick(w)
    assert said_here(w, "tea") == ["Reminder: tea"]
    away(w)
    n0 = len(w["cloud"].ntfy)
    cron(w)
    time.sleep(1)
    assert [m for m in sealed_sent(w, n0) if m["id"] == rid] == []
    back(w)


def test_a_send_the_line_couldnt_make_is_said_here(lid):
    w, ls, cloud = lid, lid["ls"], lid["cloud"]
    rid, at = remind(w, 4, "water")
    assert on_loop(w, ls.push())["ok"]
    away(w)
    time.sleep(max(0.0, at - time.time()) + 0.3)
    cloud.ntfy_down = True
    try:
        cron(w)
    finally:
        cloud.ntfy_down = False
    n0 = len(cloud.ntfy)
    back(w)
    tick(w)
    wait(lambda: (ls._said().get(rid) or {}).get("by") == "computer", 15, "the claim")
    tick(w)
    assert said_here(w, "water") == ["Reminder: water"]
    away(w)
    cron(w)  # the line doesn't try again: it's this computer's now
    time.sleep(1)
    assert [m for m in sealed_sent(w, n0) if m["id"] == rid] == []
    back(w)


def test_turned_off_the_line_drops_what_it_holds(lid):
    w, ls, app = lid, lid["ls"], lid["app"]
    rid, at = remind(w, 4, "off now")
    assert on_loop(w, ls.push())["ok"]
    on_ = app.settings.get("modules.enabled")
    app.settings.set("modules.enabled", [m for m in on_ if m != "lidsafe"])
    try:
        on_loop(w, w["calls"].connector.push_state())  # says it's off
        away(w)
        n0 = len(w["cloud"].ntfy)
        time.sleep(max(0.0, at - time.time()) + 0.3)
        cron(w)
        time.sleep(1)
        assert [m for m in sealed_sent(w, n0) if m["id"] == rid] == []
    finally:
        app.settings.set("modules.enabled", on_)
        back(w)

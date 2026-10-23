"""The phone app's Today screen, end to end on this computer: the real Worker under `wrangler dev`, the real connector
and Phone calls feature, a fake ntfy (see test_call_line.py for the setup).

The Android app gives its key; the day's list goes to the call line sealed for it alone (the line can't read it) and
the phone is nudged; /today hands that phone its own copy, with when it came, also while this computer is away; a web
app gets none; Done tapped on Today with the computer away waits in the phone outbox and is done when it's back; and
turned off, the line drops it.
"""

from __future__ import annotations

import datetime as dt
import json

import pytest

from tests.integration.test_call_line import Loop, pytestmark, wait, world  # noqa: F401 (the shared fixture)
from tests.integration.test_lidsafe_line import away, back, on_loop
from tests.integration.test_phone_chat_line import sealed_chat
from tests.integration.test_phone_line import ntfy_after, phones  # noqa: F401
from tests.unit.test_lidsafe import Phone


@pytest.fixture(scope="module")
def day(phones):  # noqa: F811
    app, ln = phones["app"], phones["line"]
    app.settings.set("modules.enabled", [*app.settings.get("modules.enabled"), "deadlines"])
    phone = Phone()
    assert ln.call("POST", "/device/key", {"pub": phone.pub}, key=phones["keys"]["android"]) == (200, {"ok": True})
    dl = app.modules["deadlines"]
    dl.add("Problem set 3", dt.datetime.now().replace(second=0, microsecond=0) + dt.timedelta(hours=30))
    (i,) = list(dl.items())
    dl._record(i, 2, 7)
    phones.update(phone=phone, dl=dl, ps3=i, android=phones["keys"]["android"])  # (away() and back() use it)
    return phones


def today(w, kind="android"):
    code, got = w["line"].call("GET", "/today", key=w["keys"][kind])
    assert code == 200, got
    return got


def test_the_list_reaches_the_phone_sealed_and_stays_with_the_computer_away(day):
    w, t = day, day["calls"].today
    n0 = len(w["cloud"].ntfy)
    t.poke()
    got = wait(lambda: today(w)["today"] and today(w), 30, "the Today list on the line")
    assert "Problem set 3" not in json.dumps(got)  # only the phone can open it
    mine = w["phone"].open(got["today"])
    assert mine["due"][0]["title"] == "Problem set 3" and (mine["due"][0]["done"], mine["due"][0]["parts"]) == (2, 7)
    assert got["at"] and got["computer"] == "online" and not got["off"]
    assert ntfy_after(w, n0, "today")  # the phone is told to fetch it
    assert today(w, "web")["today"] is None  # the web app has no key of its own
    assert w["line"].call("GET", "/today")[0] == 401
    away(w)
    still = today(w)
    assert still["today"] == got["today"] and still["computer"] == "offline"
    back(w)


def test_done_on_today_waits_on_the_line_while_the_computer_is_away(day):
    w, i = day, day["ps3"]
    away(w)
    tap = sealed_chat(w, "7" * 16, today={"id": i, "do": "done"})
    code, out = w["line"].call("POST", "/chat", tap, key=w["keys"]["android"])
    assert code == 200 and out["queued"]
    assert w["dl"].items()[i]["status"] == "open"
    back(w)
    wait(lambda: w["dl"].items()[i]["status"] == "done", 30, "Done taken from the outbox")
    wait(lambda: not w["phone"].open(today(w)["today"])["due"], 30, "the list without it")


def test_turned_off_the_line_drops_it(day):
    w = day
    w["app"].settings.set("calls.today", False)
    try:
        on_loop(w, w["calls"].connector.push_state())
        got = wait(lambda: today(w)["off"] and today(w), 20, "the line dropping it")
        assert got["today"] is None
    finally:
        w["app"].settings.set("calls.today", True)

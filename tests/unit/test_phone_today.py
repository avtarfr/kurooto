"""The phone app's Today screen and its copy of the alarm (calls/today.py, 0.6.0), and Done / Snooze on a reminder's or
deadline's phone notification, without a call line: what the list holds (stable while nothing changes), sealed for
each Android phone alone and handed over only when it changed, turned off, and Done / +1 tapped on it coming back like
the deadline's Telegram buttons, now or from the phone outbox. The Worker's side is in
tests/integration/test_phone_today_line.py; the phone's rules in android/test/TodayTest.java."""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import os
import time

import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from kurooto.modules.calls import line
from tests.unit.test_phone import phone  # noqa: F401 (the shared fixture)


class Line:
    """The call line's admin side, as today.py sees it."""

    def __init__(self, devices):
        self.devices, self.ops = devices, []

    async def admin(self, op, **kw):
        self.ops.append((op, kw))
        if op == "devices":
            return {"devices": self.devices}
        return {"ok": True, "held": len(kw.get("seal") or {})}

    def puts(self):
        return [kw for op, kw in self.ops if op == "today-put"]


@pytest.fixture
def today(phone):  # noqa: F811
    app = phone.app
    phone.on("deadlines", "alarm")
    dl = app.modules["deadlines"]
    due = dt.datetime.now().replace(second=0, microsecond=0) + dt.timedelta(hours=30)
    dl.add("Problem set 3", due)
    dl.add("Quiz 2", due + dt.timedelta(days=1))
    ids = {it["title"]: i for i, it in dl.items().items()}
    dl._record(ids["Problem set 3"], 2, 7)
    wake = (dt.datetime.now() + dt.timedelta(days=1)).replace(hour=7, minute=0, second=0, microsecond=0)
    app.modules["alarm"].set(wake)
    key = ec.generate_private_key(ec.SECP256R1())
    pub = line.b64url(key.public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint))
    phone.dl, phone.ids, phone.wake, phone.key = dl, ids, wake, key
    phone.line = Line([{"id": "abcd1234", "kind": "android", "seal": pub}, {"id": "0000beef", "kind": "web"}])
    phone.today = phone.calls.today
    return phone


def test_the_list_has_the_day_what_is_due_with_its_buttons_and_every_alarm(today):
    snap = today.today.snapshot()
    assert snap["date"] == dt.date.today().isoformat() and snap["day"]
    ps3, quiz = snap["due"]
    assert ps3["id"] == today.ids["Problem set 3"] and ps3["title"] == "Problem set 3"
    assert (ps3["parts"], ps3["done"], ps3["acts"]) == (7, 2, ["done", "+1"])
    assert quiz["exam"] and "acts" not in quiz  # a quiz or exam isn't "done"
    assert snap["alarm"]["at"] == [int(today.wake.timestamp())] and snap["alarm"]["next"]
    assert snap["alarm"]["snooze_min"] == 10
    assert today.today.snapshot() == snap  # nothing relative to now: an unchanged day looks the same
    assert "plan" not in snap and "journal" not in snap  # only what the screen shows


def test_it_goes_sealed_for_each_android_phone_and_only_when_it_changed(today):
    ln, t = today.line, today.today
    asyncio.run(t.push(ln))
    (put,) = ln.puts()
    assert list(put["seal"]) == ["abcd1234"] and put["changed"]  # the web app has no key of its own
    got = json.loads(line.open_s1(today.key, put["seal"]["abcd1234"]))
    assert got["due"][0]["parts"] == 7 and got["made"] >= int(time.time()) - 5
    asyncio.run(t.push(ln))
    assert len(ln.puts()) == 1  # the same day: nothing sent
    today.app.callback(f"dl:{today.ids['Problem set 3']}:+1")  # +1 on Telegram: the list changed
    asyncio.run(t.push(ln))
    assert len(ln.puts()) == 2 and ln.puts()[-1]["changed"]
    assert json.loads(line.open_s1(today.key, ln.puts()[-1]["seal"]["abcd1234"]))["due"][0]["done"] == 3
    t.poke()  # asked for again with nothing changed: it goes, but the phones aren't nudged
    asyncio.run(t.push(ln))
    assert len(ln.puts()) == 3 and not ln.puts()[-1]["changed"]
    today.app.settings.set("calls.today", False)
    asyncio.run(t.push(ln))
    asyncio.run(t.push(ln))
    assert ln.puts()[-1]["seal"] == {} and ln.puts()[-1]["off"] and len(ln.puts()) == 4  # dropped, once


def test_no_android_phone_with_a_key_gets_nothing(today):
    ln = Line([{"id": "0000beef", "kind": "web"}, {"id": "abcd1234", "kind": "android", "seal": ""}])
    asyncio.run(today.today.push(ln))
    assert ln.puts() == []


def sealed(app, mid: str, **fields) -> dict:
    t = int(time.time() * 1000)
    f = {"id": mid, "ts": t, "n": os.urandom(16).hex(), **fields}
    key = app.secrets.get("calls.ntfy_key")
    return {"device": "abcd1234", "at": t, "id": mid, "k1": line.seal_k1(key, json.dumps(f))}


def test_done_and_plus_one_on_today_are_the_deadlines_own_buttons(today):
    app, chat, i = today.app, today.calls.chat, today.ids["Problem set 3"]
    code, out = chat.take(sealed(app, "a" * 16, today={"id": i, "do": "+1"}))
    assert code == 200 and out["note"].startswith("Problem set 3: 3/7")
    # tapped while the computer slept: from the phone outbox, in order (Calls.take_queued)
    later = sealed(app, "b" * 16, today={"id": i, "do": "+1"})
    status, note = today.calls.take_queued({"kind": "chat", "seq": 2, "body": later})
    assert status == 200 and note.startswith("Problem set 3: 4/7")
    assert not [op for op, kw in today.ops if op == "chat-say"]  # nothing said in the chat
    code, out = chat.take(sealed(app, "c" * 16, today={"id": i, "do": "done"}))
    assert code == 200 and out["note"] == "Marked done." and today.dl.items()[i]["status"] == "done"
    assert chat.take(sealed(app, "d" * 16, today={"id": i, "do": "done"}))[0] == 410  # done already
    assert chat.take(sealed(app, "e" * 16, today={"id": i, "do": "ignore"}))[0] == 400  # only Done and +1
    assert chat.take(sealed(app, "f" * 16, today={"id": "../x", "do": "done"}))[0] == 400
    assert chat.take(sealed(app, "1" * 16, today={"id": today.ids["Quiz 2"], "do": "done"}))[0] == 400
    assert chat.take(sealed(app, "2" * 16, today={"id": "dffffffff", "do": "+1"}))[0] == 410
    again = sealed(app, "3" * 16, today={"id": today.ids["Quiz 2"], "do": "+1"})
    chat.take(again)
    assert chat.take(again)[0] == 409  # used once


def item_of(env, kind):
    return [kw["item"] for op, kw in env.ops if op == "notify" and kw["item"]["kind"] == kind][-1]


def press(env, item, n=None, **fields):
    t = int(time.time() * 1000)
    body = {"device": "abcd1234", "at": t, "item": item["id"], "ts": t, "n": os.urandom(16).hex(), **fields}
    if n is not None:
        body["button"] = n
    return env.calls.phone.answer(body)


def test_reminder_and_deadline_notifications_snooze_and_finish_as_on_telegram(today):
    from kurooto.modules.deadlines import hours_left

    app = today.app
    app.settings.set("notify.app_kinds", ["call", "question", "approval", "reminder", "deadline"])
    today.on("reminders")
    rem = app.modules["reminders"]
    rem._fire({"what": "call Sam"})
    r = item_of(today, "reminder")
    assert [b["label"] for b in r["buttons"]] == ["+10 min", "+1 h"]  # the phone adds its own Done
    code, out = press(today, r, 0)
    assert code == 200 and out["note"].startswith("Again at")
    assert [j.payload["what"] for j in app.scheduler.jobs("reminders:")] == ["call Sam"]
    rem._fire({"what": "water the plants"})
    r2 = item_of(today, "reminder")
    assert press(today, r2, dismiss=True) == (200, {"ok": True, "note": "Dismissed."})  # Done: off every phone
    assert any(op == "notify-clear" and r2["id"] in kw["ids"] for op, kw in today.ops)
    i = today.ids["Problem set 3"]
    it = today.dl.items()[i]
    today.dl._tell(i, it, hours_left(it["due"]), urgent=False)
    d = item_of(today, "deadline")
    assert [b["label"] for b in d["buttons"]] == ["+1", "Done", "Not mine", "Snooze 3 h"]
    code, out = press(today, d, 3)
    assert code == 200 and out["note"] == "I'll ask again in 3 hours."
    assert today.dl.items()[i]["snooze_until"]
    assert d["id"] not in [x["id"] for x in today.calls.phone.inbox()["items"]]  # snoozed: off the phone

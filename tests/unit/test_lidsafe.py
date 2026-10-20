"""Reminders with the lid shut (modules/lidsafe.py) without a real call line: what goes in the batch, sealing it for
each Android phone so the call line can't read it, who says an item at its time (this computer when it's awake, the
call line when it's not, never both), waiting for the link, an older call line, turning it off, the health check and
hearing that the computer is about to sleep. The fake call line below follows worker.js's rules for the box and the
answers; tests/integration/test_lidsafe_line.py runs the real Worker.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import os
import sys
import threading
import time
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from kurooto.core import endsession
from kurooto.modules import lidsafe as ls_mod
from kurooto.modules.calls import deploy, line
from kurooto.modules.lidsafe import item_id

VECTORS = Path(__file__).parent.parent / "fixtures" / "call-vectors.json"


class Phone:
    """An Android phone's key pair, as the app makes it."""

    def __init__(self):
        self.key = ec.generate_private_key(ec.SECP256R1())
        raw = self.key.public_key().public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
        )
        self.pub = line.b64url(raw)

    def open(self, token: str) -> dict | None:
        plain = line.open_s1(self.key, token)
        return json.loads(plain) if plain else None


class FakeLine:
    """The call line's side: devices, the box of sealed items, one answer per id, and the cron (worker.js)."""

    def __init__(self):
        self.devices: dict[str, dict] = {}
        self.box = {"rev": 0, "items": []}
        self.done: dict[str, dict] = {}
        self.ops: list = []
        self.queue: list = []
        self.sent: list = []  # (id, device, token)
        self.old = False  # an older Worker that doesn't know these ops
        self.fail = False  # ntfy refuses

    async def admin(self, op, timeout=20, **kw):
        self.ops.append((op, kw))
        if op == "devices":
            return {"devices": [{"id": i, **d} for i, d in self.devices.items()]}
        if self.old:
            return {"error": "unknown op"}
        if op == "sealed-put":
            if kw["rev"] < self.box["rev"]:
                return {"ok": False, "stale": True}
            keep, told = [], {}
            for it in kw["items"]:
                d = self.done.get(it["id"])
                if d and (d["by"] == "computer" or d.get("ok")):
                    told[it["id"]] = d["by"]
                    continue
                keep.append(it)
            self.box = {"rev": kw["rev"], "items": keep}
            return {"ok": True, "held": len(keep), "done": told}
        if op == "sealed-claim":
            out = {}
            for i in kw["ids"]:
                d = self.done.get(i)
                if d and d["by"] == "line" and (d.get("ok") or d.get("busy")):
                    out[i] = "line"
                    continue
                if not d or d["by"] != "computer":
                    self.done[i] = {"by": "computer"}
                out[i] = "computer"
            self.box["items"] = [it for it in self.box["items"] if out.get(it["id"]) != "computer"]
            return {"ids": out}
        return {"error": "unknown op"}

    def cron(self, now: float, online: bool = False) -> list[str]:
        if online:
            return []
        sent = []
        for it in list(self.box["items"]):
            if it["at"] > now or now >= it["until"]:
                continue
            d = self.done.get(it["id"])
            if d and (d["by"] != "line" or d.get("ok") or d.get("tries", 0) >= 5):
                continue
            tries = (d or {}).get("tries", 0) + 1
            ok = False
            for dev, tok in it["seal"].items():
                if self.devices.get(dev, {}).get("kind") == "android" and not self.fail:
                    self.sent.append((it["id"], dev, tok))
                    ok = True
            failed = not ok and tries >= 5
            self.done[it["id"]] = (
                {"by": "line", "ok": True}
                if ok
                else {"by": "computer", "failed": True}
                if failed
                else {"by": "line", "ok": False, "tries": tries}
            )
            if ok or failed:
                self.queue.append({"name": "sealed_sent" if ok else "sealed_failed", "id": it["id"], "at": it["at"]})
            if ok:
                sent.append(it["id"])
        return sent


class FakeConnector:
    def __init__(self, fake: FakeLine):
        self.fake = fake
        self.connected = True
        self.loop = None
        self.later: list = []

    async def admin(self, op, timeout=20, **kw):
        if not self.connected:
            raise ConnectionError("not connected to your call line")
        return await self.fake.admin(op, **kw)

    def admin_later(self, op, then=None, **kw):
        self.later.append((op, kw))
        return self.connected

    def poke(self):
        pass


@pytest.fixture
def lid(env):
    app = env.app
    app.secrets.set("gemini.api_key", "k")
    deploy.ensure_secrets(app)
    app.settings.set("calls.worker", {"url": "https://kurooto-abc.your-subdomain.workers.dev"})
    app.settings.set("availability.night.enabled", False)
    env.on("calls", "reminders", "lidsafe")
    fake = FakeLine()
    calls = app.modules["calls"]
    calls.connector = FakeConnector(fake)
    phone = Phone()
    fake.devices = {
        "a1b2c3d4": {"name": "Pixel", "kind": "android", "seal": phone.pub},
        "0000beef": {"name": "Old phone", "kind": "android", "seal": ""},  # an app from before this feature
        "1234abcd": {"name": "iPhone", "kind": "web", "seal": ""},
    }
    m = app.modules["lidsafe"]
    env.fake_line, env.phone, env.ls, env.rem = fake, phone, m, app.modules["reminders"]
    return env


def run(coro):
    return asyncio.run(coro)


def add(env, minutes: float | dt.datetime, what: str) -> str:
    """A reminder in `minutes` (or at a time); returns its item id."""
    when = minutes if isinstance(minutes, dt.datetime) else dt.datetime.now() + dt.timedelta(minutes=minutes)
    env.rem.add(when, what)
    j = next(j for j in env.app.scheduler.jobs("reminders:") if j.payload["what"] == what)
    return item_id("rem", j.payload["ref"])


def payload(env, what: str) -> dict:
    return dict(next(j for j in env.app.scheduler.jobs("reminders:") if j.payload["what"] == what).payload)


def reminders_said(env) -> list[str]:
    return [t for t in env.fake.texts() if t.startswith("Reminder")]


def run_due(env) -> None:
    run(env.app.scheduler.tick())


# ------------------------------------------------------------------------------------------- the crypto
def test_s1_vectors_match_the_app():
    v = json.loads(VECTORS.read_text(encoding="utf-8"))["s1"]
    phone = ec.derive_private_key(int(v["phone_priv_hex"], 16), ec.SECP256R1())
    eph = ec.derive_private_key(int(v["eph_priv_hex"], 16), ec.SECP256R1())
    assert line.seal_s1(v["phone_pub"], v["plain"], eph, bytes.fromhex(v["nonce_hex"])) == v["sealed"]
    assert line.open_s1(phone, v["sealed"]) == v["plain"]
    assert line.open_s1(phone, v["sealed"][:-2] + "AA") is None  # changed on the way
    assert line.open_s1(ec.generate_private_key(ec.SECP256R1()), v["sealed"]) is None  # another phone
    assert line.open_s1(phone, "k1." + v["sealed"][3:]) is None
    with pytest.raises(ValueError):
        line.seal_s1(line.b64url(b"\x04" + b"\x01" * 64), "x")  # not a point on the curve


# ------------------------------------------------------------------------------------------- the batch
def test_the_batch_has_the_next_days_reminders_and_a_morning_line(lid):
    app, ls = lid.app, lid.ls
    lid.on("subjects", "deadlines")
    noon = dt.datetime.combine(dt.date.today(), dt.time(12, 0))
    a = add(lid, noon + dt.timedelta(minutes=30), "call Sam")
    add(lid, noon + dt.timedelta(hours=30), "too far ahead")
    add(lid, noon - dt.timedelta(minutes=5), "already due")
    old = (noon + dt.timedelta(hours=1)).timestamp()
    app.scheduler.at(old, "reminders.fire", {"what": "from before this update"}, key="reminders:old1")
    tomorrow = dt.date.today() + dt.timedelta(days=1)
    day = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][tomorrow.weekday()]
    app.settings.set("subjects.list", [{"slug": "la", "name": "Linear Algebra", "aliases": []}])
    app.settings.set("subjects.timetable", [{"day": day, "start": "09:00", "end": "09:55", "subject": "la"}])
    dl = app.modules["deadlines"]
    dl.add("Problem set 3", dt.datetime.combine(tomorrow, dt.time(17, 0)))
    dl.add("Essay", dt.datetime.combine(tomorrow, dt.time(23, 59)))
    ls.clock = noon.timestamp
    items = ls.batch()
    texts = {i["id"]: i["text"] for i in items}
    assert texts.get(a) == "Reminder: call Sam" and len(items) == 2  # not too far ahead, already due or without a ref
    m = next(i for i in items if i["title"] == "Today")
    assert m["id"] == item_id("day", tomorrow.isoformat())
    assert m["text"] == "First class 09:00: Linear Algebra. Due today: Problem set 3 (17:00); Essay."
    assert dt.datetime.fromtimestamp(m["at"]) == dt.datetime.combine(tomorrow, dt.time(7, 30))
    assert m["until"] - m["at"] == 3 * 3600 and items == sorted(items, key=lambda i: i["at"])
    # an earlier class pulls the line to 30 minutes before it
    app.settings.set("subjects.timetable", [{"day": day, "start": "07:45", "end": "08:40", "subject": "la"}])
    assert ls.morning(tomorrow)["at"] == dt.datetime.combine(tomorrow, dt.time(7, 15))
    # nothing on a day: no line; and each part can be turned off
    assert ls.morning(tomorrow + dt.timedelta(days=3)) is None
    app.settings.set("lidsafe.today", False)
    app.settings.set("lidsafe.reminders", False)
    assert ls.batch() == []


def test_the_morning_line_comes_with_that_mornings_alarm(lid):
    app, ls = lid.app, lid.ls
    lid.on("deadlines")
    tomorrow = dt.date.today() + dt.timedelta(days=1)
    app.modules["deadlines"].add("Lab report", dt.datetime.combine(tomorrow, dt.time(10, 0)))
    app.settings.set("modules.enabled", [*app.settings.get("modules.enabled"), "alarm"])
    alarm = app.modules["alarm"]
    alarm.next = lambda: dt.datetime.combine(tomorrow, dt.time(6, 45))
    assert ls.morning(tomorrow) == {
        "at": dt.datetime.combine(tomorrow, dt.time(6, 45)),
        "text": "Due today: Lab report (10:00).",
    }
    alarm.next = lambda: dt.datetime.combine(tomorrow, dt.time(14, 0))  # a nap, not a morning alarm
    assert ls.morning(tomorrow)["at"] == dt.datetime.combine(tomorrow, dt.time(7, 30))


# ---------------------------------------------------------------------------------------- the hand-over
def test_sealed_for_each_android_phone_and_unreadable_on_the_line(lid):
    fake, ls = lid.fake_line, lid.ls
    rid = add(lid, 45, "call Sam about the essay")
    res = run(ls.push())
    assert res["ok"] and res["held"] == 1
    op, kw = fake.ops[-1]
    assert op == "sealed-put" and [i["id"] for i in kw["items"]] == [rid]
    assert "call Sam" not in json.dumps(kw) and "Reminder" not in json.dumps(kw)  # times and ciphertext only
    it = kw["items"][0]
    assert set(it) == {"id", "at", "until", "seal"} and set(it["seal"]) == {"a1b2c3d4"}  # keyed Android phones
    got = lid.phone.open(it["seal"]["a1b2c3d4"])
    assert got["text"] == "Reminder: call Sam about the essay" and got["title"] == "Kurooto" and got["id"] == rid
    assert len(it["seal"]["a1b2c3d4"]) <= ls_mod.TOKEN_MAX
    held = ls._held()
    assert rid in held["ids"] and held["phones"] == 1 and held["held"] == 1
    assert any(e["kind"] == "lidsafe_pushed" for e in lid.app.events.tail(20))


def test_handed_over_only_when_it_changed(lid):
    fake, ls = lid.fake_line, lid.ls
    add(lid, 45, "stretch")
    run(ls.push())
    n = len(fake.ops)
    assert run(ls.push()) == {"ok": True, "same": True}
    assert [o for o, _ in fake.ops[n:]] == ["devices"]  # asked who can open them, sent nothing
    ls._dirty = False
    add(lid, 90, "tea")  # Reminders pokes it
    assert ls._dirty
    run(ls.step())
    assert fake.ops[-1][0] == "sealed-put" and len(fake.ops[-1][1]["items"]) == 2
    # cancelling one goes too
    key = next(j.key for j in lid.app.scheduler.jobs("reminders:") if j.payload["what"] == "tea")
    lid.rem._cancel(key.split(":")[1], "x")
    run(ls.step())
    assert len(fake.ops[-1][1]["items"]) == 1
    # a new phone's key: sealed for it too
    other = Phone()
    fake.devices["0000beef"]["seal"] = other.pub
    lid.app.modules["calls"].on_event({"name": "device_key", "id": "0000beef"})
    run(ls.step())
    assert set(fake.ops[-1][1]["items"][0]["seal"]) == {"a1b2c3d4", "0000beef"}


def test_awake_at_its_time_this_computer_says_it_once(lid):
    fake, ls = lid.fake_line, lid.ls
    rid = add(lid, 45, "call Sam")
    run(ls.push())
    p = payload(lid, "call Sam")
    lid.rem._fire(p)  # it comes due: held back for the call line's answer
    assert reminders_said(lid) == [] and rid in ls._waiting()
    assert run(ls.claim_waiting()) == 1
    run_due(lid)
    assert reminders_said(lid) == ["Reminder: call Sam"]
    assert fake.done[rid] == {"by": "computer"} and fake.box["items"] == []
    assert fake.cron(time.time() + 3600) == []  # the lid shuts later: the call line doesn't send it too
    lid.rem._fire(p)  # even if it ran again, it's this computer's: said as usual, not held back
    assert ls._waiting() == {}


def test_asleep_the_line_sends_it_and_waking_skips_it(lid):
    fake, ls = lid.fake_line, lid.ls
    rid = add(lid, 45, "call Sam")
    run(ls.push())
    p = payload(lid, "call Sam")
    at = fake.box["items"][0]["at"]
    # the lid is shut: the call line's cron sends it at its time, once
    assert fake.cron(at - 30) == [] and fake.cron(at + 5) == [rid] and fake.cron(at + 65) == []
    ((iid, dev, tok),) = fake.sent
    assert dev == "a1b2c3d4" and lid.phone.open(tok)["text"] == "Reminder: call Sam"
    # waking: the scheduler runs the late reminder before the link is back
    lid.app.modules["calls"].connector.connected = False
    lid.rem._fire({**p, "late_s": 600})
    assert rid in ls._waiting() and reminders_said(lid) == []
    lid.app.modules["calls"].connector.connected = True
    run(ls.step())
    run_due(lid)
    assert reminders_said(lid) == [] and ls._waiting() == {}
    assert any(e["kind"] == "lidsafe_skipped" for e in lid.app.events.tail(20))


def test_told_by_the_line_first_it_isnt_held_back_at_all(lid):
    fake, ls = lid.fake_line, lid.ls
    rid = add(lid, 45, "stretch")
    run(ls.push())
    fake.cron(fake.box["items"][0]["at"] + 5)
    for ev in fake.queue:  # what the line kept for this computer, as it reconnects
        lid.app.modules["calls"].on_event(ev)
    lid.rem._fire({**payload(lid, "stretch"), "late_s": 900})
    assert ls._waiting() == {} and reminders_said(lid) == []
    assert (ls._said()[rid] or {})["by"] == "line"


def test_without_the_link_it_waits_then_says_it_here(lid):
    ls = lid.ls
    rid = add(lid, 45, "on time")
    rid2 = add(lid, 50, "after a sleep")
    run(ls.push())
    conn = lid.app.modules["calls"].connector
    conn.connected = False
    t0 = time.time()
    ls.clock = lambda: t0
    lid.rem._fire(payload(lid, "on time"))
    lid.rem._fire({**payload(lid, "after a sleep"), "late_s": 3600})
    assert set(ls._waiting()) == {rid, rid2}
    ls.clock = lambda: t0 + ls_mod.WAIT_S - 1
    assert ls.release_overdue() == 0
    ls.clock = lambda: t0 + ls_mod.WAIT_S + 1
    assert ls.release_overdue() == 1
    run_due(lid)
    assert reminders_said(lid) == ["Reminder: on time"]
    ls.clock = lambda: t0 + ls_mod.WAIT_LATE_S + 1  # after a sleep it waits longer: the line has surely sent it
    assert ls.release_overdue() == 1
    run_due(lid)
    assert reminders_said(lid) == ["Reminder: on time", "Reminder (late: the computer was asleep): after a sleep"]
    assert ls._waiting() == {}


def test_awake_and_linked_at_its_time_the_morning_line_is_claimed(lid):
    fake, ls = lid.fake_line, lid.ls
    lid.on("deadlines")
    tomorrow = dt.date.today() + dt.timedelta(days=1)
    lid.app.modules["deadlines"].add("Problem set", dt.datetime.combine(tomorrow, dt.time(17, 0)))
    ls.clock = lambda: dt.datetime.combine(dt.date.today(), dt.time(20, 0)).timestamp()
    run(ls.push())
    day = item_id("day", tomorrow.isoformat())
    it = next(i for i in fake.box["items"] if i["id"] == day)
    assert lid.phone.open(it["seal"]["a1b2c3d4"])["text"] == "Due today: Problem set (17:00)."
    ls.clock = lambda: it["at"] + 10  # this computer is awake then
    assert run(ls.acknowledge_due()) == {day: "computer"}
    assert fake.cron(it["at"] + 600) == []  # the lid shut afterwards: not sent
    assert reminders_said(lid) == []  # and not said here either (the morning page has it)


def test_a_send_the_line_couldnt_make_comes_back(lid):
    fake, ls = lid.fake_line, lid.ls
    rid = add(lid, 45, "call Sam")
    run(ls.push())
    at = fake.box["items"][0]["at"]
    fake.fail = True
    fake.cron(at + 5)  # failed, will try again
    assert run(ls._claim([rid])) == {rid: "computer"}  # this computer is back first: it's its to say
    # the other way round: this computer heard "line" (a send under way), skipped it, then the line gave up
    ls._set_said(rid, "line")
    lid.app.modules["calls"].on_event({"name": "sealed_failed", "id": rid})
    assert any("couldn't get this to your phone: Reminder: call Sam" in t for t in lid.fake.texts())
    assert ls._said()[rid]["by"] == "computer"


def test_an_older_call_line_changes_nothing(lid):
    fake, ls = lid.fake_line, lid.ls
    fake.old = True
    add(lid, 45, "call Sam")
    res = run(ls.push())
    assert res == {"error": "unknown op"} and ls._held()["ids"] == {}
    lid.rem._fire(payload(lid, "call Sam"))  # said as usual
    assert reminders_said(lid) == ["Reminder: call Sam"]
    r = next(x for x in lid.app.health.evaluate(only="lidsafe", save=False))
    assert r.ok is False and "older than this feature" in r.detail


def test_health_needs_a_phone_that_can_open_them(lid):
    fake, ls = lid.fake_line, lid.ls
    r = next(x for x in lid.app.health.evaluate(only="lidsafe", save=False))
    assert r.ok is None
    fake.devices["a1b2c3d4"]["seal"] = ""
    run(ls.push())
    r = next(x for x in lid.app.health.evaluate(only="lidsafe", save=False))
    assert r.ok is False and "update the Kurooto app" in r.detail
    fake.devices["a1b2c3d4"]["seal"] = lid.phone.pub
    run(ls.push())
    r = next(x for x in lid.app.health.evaluate(only="lidsafe", save=False))
    assert r.ok is True and "for 1 phone" in r.detail


def test_turning_it_off_clears_the_line_and_says_what_waited(lid):
    ls, conn = lid.ls, lid.app.modules["calls"].connector
    rid = add(lid, 45, "call Sam")
    run(ls.push())
    conn.connected = False
    lid.rem._fire(payload(lid, "call Sam"))
    assert rid in ls._waiting()
    calls = lid.app.modules["calls"]
    assert calls.state_message()["sealed_on"] is True
    ok, _ = lid.app.disable("lidsafe")
    assert ok and conn.later[-1][0] == "sealed-put" and conn.later[-1][1]["items"] == []
    assert calls.state_message()["sealed_on"] is False  # the line drops its copy with the next state push too
    run_due(lid)
    assert reminders_said(lid) == ["Reminder: call Sam"] and ls._waiting() == {}
    assert ls._held()["ids"] == {}


# -------------------------------------------------------------------------------------- going to sleep
def test_going_to_sleep_hands_over_what_changed(lid):
    fake, ls = lid.fake_line, lid.ls
    conn = lid.app.modules["calls"].connector
    loop = asyncio.new_event_loop()
    t = threading.Thread(target=loop.run_forever, daemon=True)
    t.start()
    try:
        conn.loop = loop
        add(lid, 45, "stretch")
        assert ls.going_to_sleep() is True
        assert fake.ops[-1][0] == "sealed-put"
        n = len(fake.ops)
        assert ls.going_to_sleep() is True and fake.ops[n:] == [("devices", {})]  # nothing new: nothing sent
        conn.connected = False
        assert ls.going_to_sleep() is False
    finally:
        loop.call_soon_threadsafe(loop.stop)
        t.join(5)
    assert sum(e["kind"] == "lidsafe_sleep" for e in lid.app.events.tail(50)) == 3


def test_hearing_that_the_computer_is_about_to_sleep():
    assert ls_mod.sleeping("/org/freedesktop/login1: org.freedesktop.login1.Manager.PrepareForSleep (true,)")
    assert not ls_mod.sleeping("/org/freedesktop/login1: org.freedesktop.login1.Manager.PrepareForSleep (false,)")
    assert not ls_mod.sleeping("The name org.freedesktop.login1 is owned by :1.4")
    heard = []
    endsession._on_suspend.append(lambda: heard.append(1))
    try:
        assert endsession.handle(endsession.WM_POWERBROADCAST, endsession.PBT_APMSUSPEND, 0) == 1
        assert endsession.handle(endsession.WM_POWERBROADCAST, 0x12, 0) == 1  # resuming: nothing to do
        assert heard == [1]
    finally:
        endsession._on_suspend.clear()
    if sys.platform != "win32":  # elsewhere it does nothing
        endsession.on_suspend(lambda: None)()
        assert endsession._on_suspend == [] and endsession._thread is None


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="logind is Linux's")
def test_linux_hears_logind_before_a_suspend(lid, tmp_path, monkeypatch):
    fake = tmp_path / "bin" / "gdbus"
    fake.parent.mkdir()
    fake.write_text(
        "#!/bin/sh\necho 'Monitoring signals on object /org/freedesktop/login1'\n"
        "echo '/org/freedesktop/login1: org.freedesktop.login1.Manager.PrepareForSleep (true,)'\n"
        "echo '/org/freedesktop/login1: org.freedesktop.login1.Manager.PrepareForSleep (false,)'\nexec sleep 30\n"
    )
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{fake.parent}{os.pathsep}{os.environ['PATH']}")
    ls, heard = lid.ls, []
    ls.going_to_sleep = lambda: heard.append(1)
    ls._watch_sleep()
    p = ls._watch
    end = time.monotonic() + 10
    while not heard and time.monotonic() < end:
        time.sleep(0.05)
    ls._stop_watch()
    assert heard == [1] and p.wait(5) is not None and ls._watch is None

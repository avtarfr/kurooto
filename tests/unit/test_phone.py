"""The phone as a second channel (calls/phone.py) without a call line: which messages go to the phone app, what the
phone sees, answers coming back (sealed, single use, fresh), buttons, replies, app.ask questions and approvals,
taking things off the phone once they're dealt with elsewhere, and the "on a call" state.
The call line's side is tested end to end in tests/integration/test_phone_line.py."""

from __future__ import annotations

import datetime as dt
import json
import os
import time

import pytest

from kurooto.core.availability import ON_CALL
from kurooto.core.state import jsave
from kurooto.modules.base import Module
from kurooto.modules.calls import deploy, line


class Fake(Module):
    """A feature that asks something and takes replies and buttons."""

    id = "fakeq"
    title = "Fake"

    def __init__(self, app):
        super().__init__(app)
        self.got: list = []

    def replies(self):
        return {"fakeq": lambda msg, ref: self.got.append(("reply", ref, msg.text, msg.via)) or "Noted."}

    def callbacks(self):
        return {"fq": lambda ref, act: self.got.append(("button", ref, act)) or f"Did {act}."}


@pytest.fixture
def phone(env):
    app = env.app
    app.secrets.set("gemini.api_key", "k")
    deploy.ensure_secrets(app)
    app.settings.set("calls.worker", {"url": "https://kurooto-abc.your-subdomain.workers.dev"})
    app.settings.set("availability.night.enabled", False)
    env.on("calls")
    fake = Fake(app)
    app.modules["fakeq"] = fake
    app.settings.set("modules.enabled", [*app.settings.get("modules.enabled"), "fakeq"])
    calls = app.modules["calls"]
    ops: list = []

    def admin_later(op, then=None, **kw):
        ops.append((op, kw))
        if then:
            then({"ok": True})
        return True

    calls.connector.admin_later = admin_later
    env.fake_mod, env.ops, env.calls, env.phone = fake, ops, calls, calls.phone
    return env


def ask_fakeq(app, text="How was the lecture?", ref="r1"):
    app.notify(text, kind="question", map_kind="fakeq", map_ref=ref, buttons=[[("Nothing", f"fq:{ref}:none")]])


def last_item(env):
    op, kw = next(o for o in reversed(env.ops) if o[0] == "notify")
    return kw["item"]


def sealed(app, fields: dict, item: str) -> dict:
    key = app.secrets.get("calls.ntfy_key")
    body = {"ts": int(time.time() * 1000), "n": os.urandom(16).hex(), "item": item, **fields}
    return {
        "device": "abcd1234",
        "at": int(time.time() * 1000),
        "item": item,
        "k1": line.seal_k1(key, json.dumps(body)),
    }


def plain(fields: dict, item: str, **over) -> dict:
    return {"device": "abcd1234", "at": int(time.time() * 1000), "item": item, "ts": int(time.time() * 1000),
            "n": os.urandom(16).hex(), **fields, **over}  # fmt: skip


def post(env, body: dict):
    return env.calls.handle_request("POST", "/answer", json.dumps(body).encode())


# ------------------------------------------------------------------------------------------ sending
def test_questions_and_approvals_go_to_the_phone_by_default(phone):
    app = phone.app
    assert app.settings.get("notify.app_kinds") == ["call", "question", "approval"]
    app.notify("FYI", kind="info")
    app.notify("Calling you: test", kind="call")
    assert not phone.ops
    ask_fakeq(app)
    it = last_item(phone)
    assert it["kind"] == "question" and it["text"] == "How was the lecture?" and it["reply"] is True
    assert it["buttons"] == [{"label": "Nothing"}]  # the button's data stays on this computer
    assert not any(k.startswith("_") for k in it) and len(it["id"]) == 16
    app.settings.set("notify.app_kinds", ["call", "question", "approval", "info"])
    app.notify("FYI", kind="info", buttons=[[("Open", {"url": "https://example.com/x"})]])
    it = last_item(phone)
    assert (
        it["kind"] == "info"
        and it["reply"] is False
        and it["buttons"] == [{"label": "Open", "url": "https://example.com/x"}]
    )
    assert any("How was the lecture?" in t for t in phone.fake.texts())  # Telegram still gets its copy


def test_the_inbox_is_what_is_open_with_a_rising_revision(phone):
    app, ph = phone.app, phone.phone
    ask_fakeq(app)
    first = ph.inbox()
    ask_fakeq(app, "Second?", "r2")
    second = ph.inbox()
    assert second["rev"] > first["rev"] and [i["text"] for i in second["items"]] == ["How was the lecture?", "Second?"]
    st = phone.calls.state_message()
    assert st["inbox"]["rev"] == second["rev"] and len(st["inbox"]["items"]) == 2
    d = json.loads(ph.file.read_text())
    d["items"][0]["until"] = int(time.time()) - 1  # a day went by
    jsave(ph.file, d)
    assert [i["text"] for i in ph.inbox()["items"]] == ["Second?"]


def test_messages_the_line_missed_are_sent_again(phone):
    app = phone.app
    phone.calls.connector.admin_later = lambda op, then=None, **kw: False  # the line is down
    ask_fakeq(app)
    sent = []
    phone.calls.connector.admin_later = lambda op, then=None, **kw: sent.append((op, kw)) or True
    phone.calls.state_message()  # the next push after reconnecting
    assert [op for op, _ in sent] == ["notify"]


# ------------------------------------------------------------------------------------------ answers
def test_a_sealed_reply_reaches_the_feature_once(phone):
    app = phone.app
    ask_fakeq(app)
    item = last_item(phone)["id"]
    body = sealed(app, {"answer": "Eigenvalues, mostly"}, item)
    code, out = post(phone, body)
    assert code == 200 and out == {"ok": True, "note": "Noted."}
    assert phone.fake_mod.got == [("reply", "r1", "Eigenvalues, mostly", "app")]
    assert phone.phone.inbox()["items"] == []
    assert ("notify-clear", {"ids": [item], "rev": phone.phone.inbox()["rev"]}) in phone.ops
    code, out = post(phone, body)  # the same request again
    assert code in (409, 410) and not out["ok"]
    assert len(phone.fake_mod.got) == 1


def test_answers_must_be_fresh_new_and_sealed_with_the_right_key(phone):
    app = phone.app
    ask_fakeq(app)
    item = last_item(phone)["id"]
    old = plain({"answer": "x"}, item, ts=int(time.time() * 1000) - 11 * 60_000)
    assert post(phone, old)[0] == 409
    assert post(phone, plain({"answer": "x"}, item, n="short"))[0] == 409
    wrong = {**sealed(app, {"answer": "x"}, item)}
    wrong["k1"] = line.seal_k1(line.new_key(), json.dumps({"item": item, "answer": "x"}))
    assert post(phone, wrong)[0] == 400
    swapped = sealed(app, {"answer": "x"}, "f" * 16)
    swapped["item"] = item  # a sealed answer for another item can't be pointed at this one
    assert post(phone, swapped)[0] == 400
    assert post(phone, plain({"answer": "x"}, "0" * 16))[0] == 410
    n = os.urandom(16).hex()
    assert post(phone, plain({"answer": "first"}, item, n=n))[0] == 200
    assert phone.fake_mod.got == [("reply", "r1", "first", "app")]


def test_buttons_are_pressed_by_number_and_only_their_own(phone):
    app = phone.app
    ask_fakeq(app)
    item = last_item(phone)["id"]
    assert post(phone, plain({"button": 5}, item))[0] == 400
    code, out = post(phone, plain({"button": 0}, item))
    assert code == 200 and out["note"] == "Did none." and phone.fake_mod.got == [("button", "r1", "none")]
    assert phone.phone.inbox()["items"] == []


def test_dismiss(phone):
    phone.app.settings.set("notify.app_kinds", ["info"])
    phone.app.notify("Done: backups ran", kind="info")
    item = last_item(phone)["id"]
    assert post(phone, plain({"dismiss": True}, item)) == (200, {"ok": True, "note": "Dismissed."})
    assert phone.phone.inbox()["items"] == []


def test_ask_questions_and_approvals_answered_from_the_phone(phone):
    app = phone.app
    qid = app.ask.ask("Which topic first?", choices=["Bayes", "Markov"])
    it = last_item(phone)
    assert it["qid"] == qid and it["choices"] == ["Bayes", "Markov"] and it["reply"] and it["later"]
    assert it["text"] == "Which topic first?" and it["until"] > time.time() + 3600
    code, out = post(phone, sealed(app, {"answer": "markov"}, it["id"]))
    assert code == 200 and out["ok"] and "Markov" in out["note"]
    q = app.ask.get(qid)
    assert q["status"] == "answered" and q["answer"] == "Markov" and q["via"] == "app"
    assert phone.phone.inbox()["items"] == []

    aid = app.ask.ask("Send the reply to Sam?", kind="approval")
    it = last_item(phone)
    assert it["choices"] == ["Approve", "Deny"] and it["reply"] is False
    code, out = post(phone, plain({"answer": "approve"}, it["id"]))
    assert code == 200 and out["ok"] and app.ask.get(aid)["answer"] == "Approve"

    lid = app.ask.ask("Anything to add to the log?")
    it = last_item(phone)
    assert post(phone, plain({"answer": "later"}, it["id"]))[1]["ok"]
    assert app.ask.get(lid)["status"] == "later"


def test_answered_on_telegram_comes_off_the_phone(phone):
    app = phone.app
    qid = app.ask.ask("Tea or coffee?", choices=["Tea", "Coffee"])
    item = last_item(phone)["id"]
    app.ask.answer(qid, "Tea", via="telegram")
    assert ("notify-clear", {"ids": [item], "rev": phone.phone.inbox()["rev"]}) in phone.ops
    code, out = post(phone, plain({"answer": "Coffee"}, item))
    assert code == 410 and "no longer open" in out["note"]
    # a feature's own question: a reply on Telegram, or one of its buttons
    ask_fakeq(app, ref="r7")
    item = last_item(phone)["id"]
    phone.reply_to_last("Covered limits")
    assert phone.fake_mod.got[-1] == ("reply", "r7", "Covered limits", "telegram")
    assert item not in [i["id"] for i in phone.phone.inbox()["items"]]
    ask_fakeq(app, ref="r8")
    item = last_item(phone)["id"]
    assert phone.press("fq:r8:none") == "Did none."
    assert item not in [i["id"] for i in phone.phone.inbox()["items"]]


def test_answers_kept_while_the_computer_was_off_are_done_on_return(phone):
    app = phone.app
    ask_fakeq(app)
    item = last_item(phone)["id"]
    phone.calls.on_queue([{"kind": "answer", "body": sealed(app, {"answer": "From the train"}, item)}])
    assert phone.fake_mod.got == [("reply", "r1", "From the train", "app")]
    assert "Your answer from the phone: Noted." in phone.fake.texts()[-1]


def test_the_assistant_name_goes_with_rings_and_messages(phone):
    app = phone.app
    app.settings.set("you.assistant_name", "Juniper")  # renamed after the phone was paired
    ask_fakeq(app)
    phone.calls.ring("Stand-up in 5")
    by_op = {op: kw for op, kw in phone.ops}
    assert by_op["notify"]["assistant"] == "Juniper" and by_op["ring"]["assistant"] == "Juniper"
    assert phone.calls.state_message()["names"]["assistant"] == "Juniper"


# ------------------------------------------------------------------------------------------ on a call
def test_on_a_call_nothing_rings_and_updates_wait(phone):
    app, calls = phone.app, phone.calls
    assert app.availability.call_block()[0] is None
    calls.on_event({"name": "call_started", "since": "", "via": "device"})
    reason, until = app.availability.call_block()
    assert reason == ON_CALL and until > dt.datetime.now()
    app.settings.set("availability.night", {"enabled": True, "from": "00:00", "to": "23:59"})
    assert app.availability.call_block()[0] == ON_CALL  # before the night, so updates see it
    jsave(app.updates.ready_file, {"version": "9.9.9", "staged": True})
    assert app.updates.apply_if_quiet().startswith("busy")
    calls.handle_request("POST", "/transcript", json.dumps({"lines": [], "ended": True}).encode())
    assert app.availability.call_block()[0] != ON_CALL
    # a call that started while this computer was off, long ago, doesn't count
    old = (dt.datetime.now(dt.UTC) - dt.timedelta(minutes=10)).isoformat().replace("+00:00", "Z")
    calls.on_queue([{"kind": "event", "name": "call_started", "since": "", "at": old}])
    assert app.availability.on_call_until() is None
    # the call page checks in every few seconds: that keeps it live
    calls.handle_request("GET", "/tasks", b"")
    assert app.availability.on_call_until() is not None


def test_scheduled_calls_wait_for_the_call_to_end(phone):
    app = phone.app
    phone.calls.on_call()
    gate = app.availability.call_gate(dt.datetime.now(dt.UTC))
    assert gate is not None and gate > dt.datetime.now(dt.UTC)

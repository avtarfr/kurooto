"""Problem-set progress (modules/deadlines.py:progress): "ps3 4/7" or "did 4 of 7 on the stats problem set" keeps
how much is done; the lists show it and Start-by plans from what's left. 0.5.20: a reply to a deadline's message
("4/7", "4", "+1", "done") on Telegram and in the app's chat, with Undo; +1 on the message and the phone's notification
(kept open, each tap counted in order through the phone outbox); the morning's "ps3 4/7, due Fri"."""

import datetime as dt


def test_progress_is_kept_shown_and_planned_from(env):
    app = env.app
    env.on("deadlines", "startby")
    dl, sb = app.modules["deadlines"], app.modules["startby"]
    due = dt.datetime.combine(dt.date.today() + dt.timedelta(days=6), dt.time(17))
    dl.add("Problem set 3", due)
    ((i, it),) = [(i, it) for i, it in dl.items().items()]
    whole = sb.size_of(i, it)[0]
    out = env.say("problem set 3 4/7")
    assert out.startswith("Problem set 3: 4/7, 3 to go, due")
    it = dl.items()[i]
    assert (it["parts"], it["parts_done"]) == (7, 4)
    assert abs(sb.size_of(i, it)[0] - whole * 3 / 7) < 1e-9  # what's left
    assert "Problem set 3 (4/7)" in env.say("what's due this week")
    assert env.say("did 7 of 7 on problem set 3").endswith(
        "all done: tap Done on it in /deadlines once it's handed in."
    )
    assert sb.size_of(i, dl.items()[i])[0] == 0.25


def test_numbers_that_name_no_deadline_are_left_alone(env):
    env.on("deadlines")
    env.app.modules["deadlines"].add("Problem set 3", dt.datetime.now() + dt.timedelta(days=3))
    assert env.app.modules["deadlines"].find_open("chemistry lab") is None
    out = env.say("chemistry lab 4/7")
    assert not (out or "").startswith("Chemistry")  # not a deadline: not taken as progress


# ---------------------------------------------------------------- 0.5.20: replies, +1 on the phone, the morning
def _ps3(env, done=2, total=7, hours=20):
    """Problem set 3, due in `hours`, with `done` of `total` parts done, and its reminder sent."""
    from kurooto.modules.deadlines import hours_left

    dl = env.app.modules["deadlines"]
    dl.add("Problem set 3", dt.datetime.now().replace(second=0, microsecond=0) + dt.timedelta(hours=hours))
    ((i, it),) = list(dl.items().items())
    if total:
        dl._record(i, done, total)
    it = dl.items()[i]
    dl._tell(i, it, hours_left(it["due"]), urgent=False)
    return dl, i


def _last(env) -> dict:
    return [p for m, p in env.fake.sent if m == "sendMessage"][-1]


def _buttons(p: dict) -> list[tuple[str, str]]:
    rows = (p.get("reply_markup") or {}).get("inline_keyboard", [])
    return [(b["text"], b.get("callback_data", "")) for row in rows for b in row]


def test_the_reminder_shows_progress_and_offers_plus_one(env):
    env.on("deadlines")
    dl, i = _ps3(env)
    p = _last(env)
    assert p["text"].startswith("Due in 20 h: Problem set 3 (") and p["text"].endswith(", 2/7 done")
    assert _buttons(p)[:2] == [("+1", f"dl:{i}:+1"), ("Done", f"dl:{i}:done")]
    assert env.press(f"dl:{i}:+1").startswith("Problem set 3: 3/7, 4 to go, due")
    assert env.press(f"dl:{i}:+1").startswith("Problem set 3: 4/7")  # it stays, so it counts again
    assert dl.items()[i]["parts_done"] == 4


def test_a_reply_to_the_reminder_records_progress_with_undo(env):
    env.on("deadlines")
    dl, i = _ps3(env)
    assert env.reply_to_last("4/7").startswith("Problem set 3: 4/7, 3 to go, due")
    ((label, undo),) = _buttons(_last(env))
    assert label == "Undo" and undo.startswith(f"dl:{i}:undo")
    assert env.press(undo) == "Undone: Problem set 3 is back to 2/7."
    assert env.press(undo).startswith("That was changed again since")  # used once
    assert env.reply_to_last("+1").startswith("Problem set 3: 3/7")
    assert env.reply_to_last("5 done").startswith("Problem set 3: 5/7")
    stale = _buttons(_last(env))[0][1]
    assert env.reply_to_last("6").startswith("Problem set 3: 6/7, 1 to go")
    assert env.press(stale).startswith("That was changed again since")  # an older Undo doesn't undo a newer change
    assert env.reply_to_last("9").startswith("Say it as done/total")
    assert (dl.items()[i]["parts"], dl.items()[i]["parts_done"]) == (7, 6)


def test_done_in_reply_marks_it_done_and_undo_opens_it_again(env):
    env.on("deadlines")
    dl, i = _ps3(env)
    assert env.reply_to_last("done.") == "Marked done."
    ((_, undo),) = _buttons(_last(env))
    assert dl.items()[i]["status"] == "done"
    assert env.reply_to_last("4/7") == "Problem set 3 is already marked done."
    assert env.press(undo) == "Undone: Problem set 3 is open again."
    assert dl.items()[i]["status"] == "open" and dl.items()[i]["parts_done"] == 2


def test_undo_of_done_unticks_the_box_it_ticked_in_your_notes(env):
    from kurooto.modules.deadlines import hours_left

    env.on("deadlines")
    when = dt.date.today() + dt.timedelta(days=2)
    note = env.app.workspace / "todo.md"
    note.write_text(f"# Todo\n- [ ] Problem set 4 ({when} 17:00)\n- [ ] Other\n", encoding="utf-8")
    dl = env.app.modules["deadlines"]
    dl.refresh()
    ((i, it),) = [(i, it) for i, it in dl.items().items() if it["title"].startswith("Problem set 4")]
    dl._tell(i, it, hours_left(it["due"]), urgent=False)
    assert env.reply_to_last("done") == "Marked done (ticked in todo.md)."
    assert "- [x] Problem set 4" in note.read_text(encoding="utf-8")
    assert env.press(_buttons(_last(env))[0][1]) == "Undone: Problem set 4 is open again."
    assert note.read_text(encoding="utf-8") == f"# Todo\n- [ ] Problem set 4 ({when} 17:00)\n- [ ] Other\n"


def test_a_reply_without_parts_asks_out_of_how_many_and_other_replies_go_on_as_usual(env):
    env.on("deadlines")
    dl, i = _ps3(env, total=0)
    assert env.reply_to_last("+1") == "Out of how many? Reply to the reminder like 1/7."
    assert "parts" not in dl.items()[i]
    assert "Problem set 3" in env.reply_to_last("what's due this week?")  # not a count: handled as a message
    assert env.reply_to_last("3 of 8").startswith("Problem set 3: 3/8")


def test_a_reply_in_the_phone_apps_chat_and_its_plus_one(env):
    import os
    import time

    from kurooto.modules.calls import deploy

    app = env.app
    app.secrets.set("gemini.api_key", "k")
    deploy.ensure_secrets(app)
    app.settings.set("calls.worker", {"url": "https://kurooto-abc.your-subdomain.workers.dev"})
    app.settings.set("availability.night.enabled", False)
    app.settings.set("notify.app_chat", True)
    env.on("deadlines", "calls")
    calls = app.modules["calls"]
    calls.connector.admin_later = lambda op, then=None, **kw: (then({"ok": True}) if then else None) or True
    dl, i = _ps3(env)
    chat = calls.chat
    rem = next(m for m in reversed(chat._load()) if m["text"].startswith("Due in"))
    assert rem["reply"] and rem["buttons"][0] == {"label": "+1"}

    def take(mid, **f):
        b = {"device": "abcd1234", "at": int(time.time() * 1000), "id": mid, "ts": int(time.time() * 1000)}
        return chat.take({**b, "n": os.urandom(16).hex(), **f})

    code, out = take("a" * 16, text="4/7", to=rem["id"])
    assert code == 200 and out["said"][0]["text"].startswith("Problem set 3: 4/7, 3 to go")
    assert out["said"][0]["buttons"] == [{"label": "Undo"}]
    code, out = take("b" * 16, button=0, msg=rem["id"])
    assert code == 200 and out["note"].startswith("Problem set 3: 5/7")
    again = chat._load()[-1]
    assert again["buttons"] == [{"label": "+1"}] and again["_data"] == [f"dl:{i}:+1"]  # tap it again from there
    assert take("c" * 16, button=0, msg=again["id"])[1]["note"].startswith("Problem set 3: 6/7")
    assert dl.items()[i]["parts_done"] == 6


def test_plus_one_on_the_phone_notification_counts_each_tap_in_order_through_the_outbox(env):
    import os
    import time

    from kurooto.modules.calls import deploy

    app = env.app
    app.secrets.set("gemini.api_key", "k")
    deploy.ensure_secrets(app)
    app.settings.set("calls.worker", {"url": "https://kurooto-abc.your-subdomain.workers.dev"})
    app.settings.set("availability.night.enabled", False)
    app.settings.set("notify.app_kinds", ["call", "question", "approval", "deadline"])
    env.on("deadlines", "calls")
    calls, ops = app.modules["calls"], []
    calls.connector.admin_later = lambda op, then=None, **kw: ops.append((op, kw)) or True
    dl, i = _ps3(env)
    item = [kw["item"] for op, kw in ops if op == "notify"][-1]
    assert item["reply"] and [b["label"] for b in item["buttons"]] == ["+1", "Done", "Not mine", "Snooze 3 h"]

    def tapped(n):  # what waited on the call line while the computer slept (Calls.take_queued, the phone outbox)
        t = int(time.time() * 1000)
        body = {"device": "abcd1234", "at": t, "item": item["id"], "ts": t, "n": os.urandom(16).hex(), "button": n}
        return calls.take_queued({"kind": "answer", "seq": 1, "body": body})

    assert tapped(0)[1].startswith("Problem set 3: 3/7")
    assert tapped(0)[1].startswith("Problem set 3: 4/7")  # the second tap of the same notification counts too
    assert [x["id"] for x in calls.phone.inbox()["items"]] == [item["id"]]  # still on the phone
    assert not [kw for op, kw in ops if op == "notify-clear"]
    assert tapped(1)[1] == "Marked done."  # Done takes it off the phone
    assert calls.phone.inbox()["items"] == [] and dl.items()[i]["status"] == "done"
    assert tapped(0)[0] == 410


def test_the_morning_says_ps3_4_of_7_due_friday(env):
    from kurooto.modules import daily
    from kurooto.modules.deadlines import due_day, due_line

    env.on("deadlines")
    dl, i = _ps3(env, done=4, hours=50)
    day = due_day(dl.items()[i]["due"])
    (row,) = dl.deadlines_soon()
    assert row["parts"] == "4/7" and due_line(row) == f"Problem set 3 4/7, due {day}"
    assert daily.morning_view(env.app)["due"] == [{"title": "Problem set 3 4/7", "when": f"due {day}"}]
    assert f"Problem set 3 4/7, due {day}" in env.say("/status")
    fri = dt.datetime(2026, 10, 30, 17, 0)  # a Friday
    assert due_day(fri.isoformat(), fri - dt.timedelta(days=2)) == "Fri"
    assert due_day(fri.isoformat(), fri - dt.timedelta(days=1)) == "tomorrow"
    assert due_day(fri.isoformat(), fri - dt.timedelta(hours=3)) == "today 17:00"
    assert due_day(fri.isoformat(), fri - dt.timedelta(days=9)) == "Fri 30 Oct"
    plain = {"title": "Essay", "when": "in 2 days", "due": fri.isoformat()[:16]}
    assert due_line(plain) == "Essay (in 2 days)"

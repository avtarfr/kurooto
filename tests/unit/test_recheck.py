"""Rechecking memories: a line Kurooto kept in the how-to-help-me note that hasn't come up in remember.recheck_days
(90) gets a quiet "Still true?" with Keep / Change / Forget, at most two a week; lines you wrote yourself are never
touched; Forget and Change each have an Undo."""

import datetime as dt
import json

import pytest

from kurooto.modules import remember as rem

OLD = (dt.date.today() - dt.timedelta(days=200)).isoformat()
OLDER = (dt.date.today() - dt.timedelta(days=300)).isoformat()
NEW = dt.date.today().isoformat()


@pytest.fixture
def note(env):
    env.on("remember")
    f = rem.help_file(env.app)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(
        "# How to help me\n\n"
        f"- I keep my own list here ({OLDER})\n\n"  # yours: above Kurooto's sections
        "## You told me\n"
        f"- I hate calls before 8 ({OLD})\n"
        f"- Short answers please ({NEW})\n"
        "- A line I typed in myself\n\n"
        "## My own section\n"
        f"- I write in pencil ({OLDER})\n\n"
        "## Picked up from your chats and calls\n"
        f"- I study topology on Sundays ({OLDER})\n",
        encoding="utf-8",
    )
    return env, env.app.modules["remember"], f


def undo_button(env):
    last = [p for m, p in env.fake.sent if m == "sendMessage" and "Undo" in json.dumps(p.get("reply_markup"))][-1]
    return next(
        b["callback_data"] for row in last["reply_markup"]["inline_keyboard"] for b in row if b["text"] == "Undo"
    )


def asked(env):
    return [p for m, p in env.fake.sent if m == "sendMessage" and p["text"].startswith("Still true?")]


def test_only_kurootos_dated_lines_are_rechecked_oldest_first_two_a_week(note):
    env, r, f = note
    assert [x["fact"] for x in rem.kept_lines(env.app)] == [
        "I hate calls before 8",
        "Short answers please",
        "I study topology on Sundays",
    ]
    assert r.recheck() == f"I study topology on Sundays ({OLDER})"
    (msg,) = asked(env)
    assert "Keep" in json.dumps(msg["reply_markup"]) and "rck:" in json.dumps(msg["reply_markup"])
    assert r.recheck() is None  # not two days running
    st = json.loads(rem.recheck_file(env.app).read_text())
    st["sent"] = [s - 4 * 86400 for s in st["sent"]]
    rem.recheck_file(env.app).write_text(json.dumps(st))
    assert r.recheck() == f"I hate calls before 8 ({OLD})"
    st = json.loads(rem.recheck_file(env.app).read_text())
    st["sent"] = [s - 4 * 86400 for s in st["sent"]]  # 4 and 8 days ago: one this week
    rem.recheck_file(env.app).write_text(json.dumps(st))
    assert r.recheck() is None  # "Short answers please" is new, and the others were just asked
    assert env.app.calm.reason("remember.recheck").setting == "remember.recheck_days"


def test_a_fact_that_came_up_or_was_said_again_waits(note):
    env, r, f = note
    jid = env.app.jobs.submit("move my calls after nine, I hate early calls", title="calls")
    env.app.jobs._db.execute("update jobs set status='ok', finished=created where id=?", (jid,))
    rem.keep(env.app, "I study topology on Sundays")  # said again: "I know that already"
    assert r.recheck() is None
    env.app.settings.set("remember.recheck_days", 0)
    assert r.recheck() is None


def test_keep_forget_and_their_undo(note):
    env, r, f = note
    r.recheck()
    key = rem.fact_key("I study topology on Sundays")
    assert env.press(f"rck:{key}:keep").startswith("Kept.")
    assert env.press(f"rck:{key}:forget") == "Taken out."
    assert "topology" not in f.read_text() and "I write in pencil" in f.read_text()
    undo = undo_button(env)
    assert env.press(undo) == "Put back."
    assert f"- I study topology on Sundays ({OLDER})" in f.read_text()
    assert env.press(undo).startswith("That's undone already")


def test_change_asks_for_the_new_wording_by_reply(note):
    env, r, f = note
    r.recheck()
    key = rem.fact_key("I study topology on Sundays")
    assert env.press(f"rck:{key}:change") == "Reply with the new wording."
    assert "How should" in env.fake.texts()[-1]
    assert env.reply_to_last("my blood pressure is fine now").startswith("I'd rather not keep that")
    assert "topology on Sundays" in f.read_text()
    env.reply_to_last("I study topology on Saturdays")
    text = f.read_text()
    assert f"- I study topology on Saturdays ({NEW})" in text and "Sundays" not in text
    undo = undo_button(env)
    assert env.press(undo) == "Back as it was."
    assert f"- I study topology on Sundays ({OLDER})" in f.read_text()


def test_replying_yes_or_no_to_still_true(note):
    env, r, f = note
    r.recheck()
    assert env.reply_to_last("yes").startswith("Kept.")
    env.app.modules["remember"]._forget(rem.kept_lines(env.app)[0])
    assert "I hate calls before 8" not in f.read_text()

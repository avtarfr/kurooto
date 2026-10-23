"""Retention: what Kurooto keeps of conversations goes after privacy.keep_days (daily), /forget 7d forgets the last
stretch now, /forget all asks first; the notes folder is never touched."""

import asyncio
import datetime as dt
import json
import os
import time

import pytest

from kurooto.core import retention

DAY = 86400


@pytest.fixture
def kept(env):
    """One old (40 days) and one new (2 days) item of each kind, plus an old note in the notes folder; 30 days kept."""
    app = env.app
    app.settings.set("privacy.keep_days", 30)
    t = time.time()
    old, new = t - 40 * DAY, t - 2 * DAY
    st = app.paths.state
    tr = st / "calls" / "transcripts"
    tr.mkdir(parents=True)
    for when in (old, new):
        (tr / f"{dt.datetime.fromtimestamp(when):%Y-%m-%d-%H%M%S}.txt").write_text("Kurooto: hi\nYou: hello\n")
    (st / "calls" / "textcalls.json").write_text(
        json.dumps(
            {
                "a": {"state": "done", "last": old, "lines": [{"who": "You", "text": "old"}]},
                "b": {"state": "done", "last": new, "lines": [{"who": "You", "text": "new"}]},
                "c": {"state": "open", "last": old, "lines": []},  # a text call still going: never
            }
        )
    )
    jobs = {}
    for name, when in (("old", old), ("new", new)):
        jid = app.jobs.submit(f"the {name} question", title=f"{name} request")
        app.jobs._db.execute(
            "update jobs set status='ok', created=?, finished=?, result=? where id=?", (when, when, "an answer", jid)
        )
        md = st / "jobs" / f"{jid}-result.md"
        md.write_text("a long answer")
        os.utime(md, (when, when))
        jobs[name] = jid
    (st / "chat").mkdir(exist_ok=True)
    (st / "chat" / "history.json").write_text(
        json.dumps([{"user": "old", "assistant": "a", "at": old}, {"user": "new", "assistant": "b", "at": new}])
    )
    for name, when in (("old", old), ("new", new)):
        qid = app.ask.ask(f"{name} question?")
        q = app.ask.get(qid)
        q.update(status="answered", answer="yes", answered=dt.datetime.fromtimestamp(when).isoformat())
        app.ask._save(q)
    from kurooto.modules.cases import Store

    store = Store(st)

    def put(d):
        for name, when, status in (("old", old, "new"), ("new", new, "new"), ("test", old, "test")):
            d["cases"][name] = {"at": dt.datetime.fromtimestamp(when).isoformat(), "status": status, "text": name}

    store.change(put, 0)
    for name, when in (("old", old), ("new", new)):
        app.calm._insert({"id": name, "ts": when, "day": "", "why": "x", "text": f"{name} words", "state": "sent"})
    logs = app.paths.logs
    logs.mkdir(parents=True, exist_ok=True)
    stamp = lambda w: dt.datetime.fromtimestamp(w).strftime("%Y-%m-%d %H:%M:%S")  # noqa: E731
    (logs / "kurooto.log").write_text(
        f"{stamp(old)},1 INFO x: old line\nTraceback: old\n{stamp(new)},2 INFO x: new line\n", encoding="utf-8"
    )
    rotated = logs / "kurooto.log.1"
    rotated.write_text(f"{stamp(old)},1 INFO x: older\n", encoding="utf-8")
    note = app.workspace / "inbox" / "voice.ogg"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_bytes(b"audio")
    os.utime(note, (old, old))
    return env, jobs, note


def texts(app, name):
    return json.loads((app.paths.state / name).read_text())


def test_the_daily_job_forgets_what_is_older_than_keep_days(kept):
    env, jobs, note = kept
    app = env.app
    retention.start(app)  # what app.start() does
    out = asyncio.run(app.scheduler.actions["retention.expire"]({}))  # the way the scheduler calls it
    assert out == {
        "calls": 2,
        "requests": 1,
        "chats": 1,
        "questions": 1,
        "cases": 1,
        "messages": 1,
        "index": 0,
        "logs": 2,
    }
    st = app.paths.state
    assert len(list((st / "calls" / "transcripts").glob("*.txt"))) == 1
    assert set(texts(app, "calls/textcalls.json")) == {"b", "c"}
    old, new = app.jobs.get(jobs["old"]), app.jobs.get(jobs["new"])
    assert (old.prompt, old.result, old.title) == ("", None, "(forgotten)") and old.status == "ok"  # /usage keeps it
    assert new.prompt == "the new question" and new.result == "an answer"
    assert not (st / "jobs" / f"{jobs['old']}-result.md").exists()
    assert (st / "jobs" / f"{jobs['new']}-result.md").exists()
    assert [x["user"] for x in texts(app, "chat/history.json")] == ["new"]
    assert [q["text"] for q in app.ask.all()] == ["new question?"]
    assert set(texts(app, "cases/cases.json")["cases"]) == {"new", "test"}  # test cases you made stay
    assert app.calm.get("old")["text"] == "" and app.calm.get("new")["text"] == "new words"
    log = (app.paths.logs / "kurooto.log").read_text()
    assert "old" not in log and "new line" in log
    assert not (app.paths.logs / "kurooto.log.1").exists()
    assert note.read_bytes() == b"audio"  # your notes folder is never touched
    assert app.scheduler.get("retention:expire") is not None


def test_forget_7d_forgets_the_last_week_now(kept):
    env, jobs, note = kept
    app = env.app
    reply = env.say("/forget 7d")
    assert reply.startswith("Forgot 2 call transcripts, 1 AI request, 1 chat turn, 1 question, 1 case, ")
    assert reply.endswith("messages I sent and 1 log file.")  # the new record, and the replies while pairing
    assert app.calm.get("new")["text"] == "" and app.calm.get("old")["text"] == "old words"
    assert app.jobs.get(jobs["new"]).prompt == "" and app.jobs.get(jobs["old"]).prompt == "the old question"
    assert [x["user"] for x in texts(app, "chat/history.json")] == ["old"]
    assert set(texts(app, "cases/cases.json")["cases"]) == {"old", "test"}
    log = (app.paths.logs / "kurooto.log").read_text()
    assert "old line" in log and "Traceback: old" in log and "new line" not in log
    assert (app.paths.logs / "kurooto.log.1").exists()
    assert note.exists()
    assert env.say("/forget 2w").startswith("Nothing was kept from then.")


def test_forget_all_asks_first(kept):
    env, jobs, note = kept
    app = env.app
    env.say("/forget all")
    sent = [p for m, p in env.fake.sent if m == "sendMessage"][-1]
    assert "Forget everything" in json.dumps(sent.get("reply_markup"))
    assert app.jobs.get(jobs["old"]).prompt  # nothing yet
    assert env.press("fgt:0:no") == "Kept."
    assert env.press("fgt:0:all").startswith("That button has run out")  # an old button
    assert app.jobs.get(jobs["old"]).prompt
    out = env.press(f"fgt:{int(time.time())}:all")
    assert out.startswith("Forgot 4 call transcripts, 2 AI requests, 2 chat turns, 2 questions, 2 cases")
    assert env.fake.texts()[-1].startswith("Forgot 4 call transcripts")
    assert not list((app.paths.state / "calls" / "transcripts").glob("*.txt"))
    assert set(texts(app, "calls/textcalls.json")) == {"c"}
    assert set(texts(app, "cases/cases.json")["cases"]) == {"test"}
    assert note.exists()


def test_forget_alone_says_what_is_kept_and_keep_days_0_keeps(env):
    app = env.app
    assert "until you forget it" in env.say("/forget")  # the default: nothing fades by itself
    assert not any(retention.expire(app).values())  # only settled questions and cases keep their 30-day tidy-up
    app.settings.set("privacy.keep_days", 30)
    assert "for 30 days (privacy.keep_days)" in env.say("/forget")
    assert "for 30 days" in env.say("/forget soon")  # not a stretch: the same help


def test_questions_and_cases_follow_privacy_keep_days_unless_set(env):
    s = env.app.settings
    assert retention.days(s) == 0  # conversations are kept until you choose otherwise
    assert retention.days(s, "ask") == retention.days(s, "cases") == 30  # the old tidy-up stays
    s.set("privacy.keep_days", 7)
    assert retention.days(s, "ask") == 7 and retention.days(s) == 7
    s.set("cases.keep_days", 90)
    assert retention.days(s, "cases") == 90 and retention.days(s, "ask") == 7


def test_ask_sweep_uses_privacy_keep_days(env):
    app = env.app
    qid = app.ask.ask("which chapter?")
    q = app.ask.get(qid)
    q.update(status="answered", answered=(dt.datetime.now() - dt.timedelta(days=10)).isoformat())
    app.ask._save(q)
    app.ask.sweep({})
    assert app.ask.get(qid) is not None
    app.settings.set("privacy.keep_days", 7)
    app.ask.sweep({})
    assert app.ask.get(qid) is None


def test_span_and_summary():
    assert retention.span("7d") == 7 * DAY and retention.span("2w") == 14 * DAY and retention.span("12h") == 43200
    assert retention.span("3 days") == 3 * DAY
    assert retention.span("0d") is None and retention.span("soon") is None
    assert retention.summary({"calls": 1, "logs": 0}) == "Forgot 1 call transcript."
    assert retention.summary({"calls": 2, "requests": 1, "logs": 1}) == (
        "Forgot 2 call transcripts, 1 AI request and 1 log file."
    )
    assert retention.summary({}) == "Nothing was kept from then."


def test_a_log_without_times_goes_by_when_it_was_written(tmp_path):
    f = tmp_path / "ask-then.log"
    f.write_text("some output\n")
    old = time.time() - 40 * DAY
    os.utime(f, (old, old))
    assert not retention.trim_log(f, old + DAY, retention.END)
    assert retention.trim_log(f, 0, old + DAY) and f.read_text() == ""  # emptied; a rotated copy would go


def test_the_search_index_forgets_too(env):
    import contextlib

    from kurooto.modules.learning import History

    h = History(env.app)
    old, new = time.time() - 40 * DAY, time.time() - 2 * DAY
    with contextlib.closing(h._con()) as con, con:
        h._put(con, "call:old", "call", old, "Call", "Kurooto: hi")
        h._put(con, "call:new", "call", new, "Call", "Kurooto: hello")
    assert retention.forget(env.app, new - DAY, kinds=("index",)) == {"index": 1}
    assert h.old(time.time()) == 1 and h.old(new) == 1  # the old one stayed

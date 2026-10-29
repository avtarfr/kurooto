"""Brain, stage 05: the commitments ledger and the heartbeat."""

import datetime as dt

import pytest

from kurooto import mind
from kurooto.core.clock import now
from kurooto.mind import log as mlog
from kurooto.mind import promises


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    from kurooto.app import App

    a = App()
    a.settings.set("modules.enabled", ["mind", "reminders"])
    said = []
    monkeypatch.setattr(a, "notify", lambda text, **kw: said.append((text, kw)))
    a.said = said
    yield a
    mind.forget_client(a)
    a.close()


def test_detect_rules():
    base = dt.datetime(2026, 10, 25, 12, 0)
    got = {t: promises.detect(t, base) for t in (
        "I'll check back at 6.",
        "I will remind you Friday about the lab.",
        "Sure, I'll look at it tomorrow morning",
        "I'll check in 20 minutes if it's done",
        "The deadline is at 6",
        "I'll be there soon",
    )}  # fmt: skip
    assert [d["due"].hour for d in got["I'll check back at 6."]] == [18]
    assert got["I will remind you Friday about the lab."][0]["due"].weekday() == 4
    assert got["Sure, I'll look at it tomorrow morning"][0]["due"] == dt.datetime(2026, 10, 26, 9, 0)
    assert got["I'll check in 20 minutes if it's done"][0]["due"] == dt.datetime(2026, 10, 25, 12, 20)
    assert got["The deadline is at 6"] == [] and got["I'll be there soon"] == []  # no promise, no time


def test_only_what_it_started_by_itself_counts(app):
    assert promises.seen(app, "I'll check back in 30 minutes.", "asked") == 0  # you asked: not a promise of its own
    assert promises.seen(app, "I'll check back in 30 minutes.", "") == 0
    assert promises.seen(app, "I'll check back in 30 minutes.", "deadlines.reminder") == 1
    rows = promises._state(app)["rows"]
    assert len(rows) == 1 and rows[0]["state"] == "open" and rows[0]["due"] > rows[0]["made_at"]
    app.settings.set("mind.promises.on", False)
    assert promises.seen(app, "I'll check back in 40 minutes.", "deadlines.reminder") == 0


def test_kept_is_silent(app):
    promises.seen(app, "I'll check back in 30 minutes.", "deadlines.reminder")
    app.events.emit("job_ended", job="j1")  # it did something before the due time
    out = promises.review(app)
    assert out == {"kept": 1, "broken": 0} and app.said == []
    assert promises._state(app)["rows"][0]["state"] == "kept"
    assert any(r["kind"] == "promise_kept" for r in app.events.tail(20, {"promise_kept"}))


def test_broken_is_owned_up_to_first(app):
    promises.seen(app, "I'll check back in 30 minutes.", "deadlines.reminder")
    st = promises._state(app)
    st["rows"][0]["due"] = now().timestamp() - 60  # it's due, and nothing happened
    promises._save(app, st)
    out = promises.review(app)
    assert out["broken"] == 1 and len(app.said) == 1
    text, kw = app.said[0]
    assert (
        "didn't" in text
        and "Checking now" in text
        and "sorry" not in text.lower()
        and kw["why"] == "mind.promise_broken"
    )
    assert promises.review(app) == {"kept": 0, "broken": 0}  # said once
    assert app.events.tail(5, {"promise_broken"})


def test_renegotiating_writes_broken_first_then_a_new_promise(app):
    promises.seen(app, "I'll check back in 30 minutes.", "deadlines.reminder")
    promises.seen(app, "I'll check back in 2 hours instead.", "deadlines.reminder")
    rows = promises._state(app)["rows"]
    assert [r["state"] for r in rows] == ["renegotiated", "open"]
    kinds = [r["kind"] for r in app.events.tail(10, {"promise_made", "promise_broken"})]
    assert kinds == ["promise_made", "promise_broken", "promise_made"]


def test_slack_and_the_listing(app):
    assert promises.slack(app) == 1.0  # nothing open: plenty
    promises.seen(app, "I'll check back in 30 minutes.", "deadlines.reminder")
    assert -1.0 <= promises.slack(app) < 0.1  # half an hour away, half an hour of work: no slack
    assert "1 open" in promises.listing(app)


def test_the_log_gets_ids_and_numbers_never_words():
    assert {"promise_made", "promise_kept", "promise_broken"} <= mlog.MIRRORED
    from kurooto.mind import records

    clean = records.clean_fact(
        "promise_made", {"id": "abc123", "due_s": 5, "text": "I'll check back at 6", "act": "check"}
    )
    assert clean == {"id": "abc123", "due_s": 5}


def test_heartbeat_once_per_outage(app):
    """While the computer is down the call line says so once, with what the next 12 hours don't have a guarantee for."""
    app.scheduler.at(now() + dt.timedelta(hours=2), "reminders.fire", key="reminders:x1", payload={"what": "call mum"})
    promises.seen(app, "I'll check back in 30 minutes.", "deadlines.reminder")
    line = promises.outage_line(app)
    assert "2 things" in line and "no guarantee" in line
    text = app.presence.line_text()
    assert "%%SINCE%%" in text and "no guarantee" in text and text.count("%%SINCE%%") == 1  # one notice, with the list
    app.settings.set("mind.heartbeat.on", False)
    assert promises.outage_line(app) == "" and "no guarantee" not in app.presence.line_text()


def test_promises_in_its_own_answers_calls_and_desk(app):
    """L95 (0.9.0, mind.promises.answers): its answers, its side of a call and the desk are read with the same rules."""
    assert promises.said(app, "Sure, I'll look at it tomorrow morning", "answer") == 1
    rows = promises._state(app)["rows"]
    assert rows[-1]["source"] == "said.answer" and rows[-1]["state"] == "open"
    calls = app.modules["calls"]
    calls.save_transcript({"lines": [{"who": "you", "text": "I'll check in 20 minutes"},
                                     {"who": app.name, "text": "I'll remind you Friday about the lab."}]})  # fmt: skip
    rows = promises._state(app)["rows"]
    assert rows[-1]["source"] == "said.call" and "remind you" in rows[-1]["text"]  # only its own side
    assert not any("check in" in r["text"] for r in rows)
    app.settings.set("mind.promises.answers", False)
    assert promises.said(app, "I'll check back at 6.", "desk") == 0

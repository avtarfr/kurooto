"""Gists: as a conversation's words fade (privacy.keep_days, /forget), it settles into one line of what it decided or
did, from records (the call's tool log, the request's title, outcome and run receipt), never its words; /gists finds
them; /forget all asks whether they go too; a local model adds a sentence only when you allow it."""

import datetime as dt
import json
import time

import pytest

from kurooto.core import gists, retention

DAY = 86400


@pytest.fixture
def old(env):
    """An old call (with its tool log), an old call from before tool logs, an old request with a receipt, and old
    chat turns: one is that request's own turn, one isn't; 30 days kept."""
    app = env.app
    app.settings.set("privacy.keep_days", 30)
    t = time.time() - 40 * DAY
    tr = app.paths.state / "calls" / "transcripts"
    tr.mkdir(parents=True)
    a = tr / f"{dt.datetime.fromtimestamp(t):%Y-%m-%d-%H%M%S}.txt"
    a.write_text("# Evening check-in\nKurooto: hi\nYou: remind me at 9 to book the lab slot\n")
    gists.note_call(
        a,
        "Evening check-in",
        [
            {"name": "add_reminder", "args": "{}", "result": "I'll remind you Fri 23 Oct at 09:00: book the lab slot"},
            {"name": "search_notes", "args": "{}", "result": "lab-safety.md: wear goggles in the wet lab"},
        ],
    )
    b = tr / f"{dt.datetime.fromtimestamp(t + 3600):%Y-%m-%d-%H%M%S}.txt"
    b.write_text("Kurooto: hello\nYou: hold calls for two hours\n")
    jid = app.jobs.submit("plan my topology revision", title="plan my topology revision")
    app.jobs._db.execute(
        "update jobs set status='ok', created=?, finished=?, result=?, receipt=? where id=?",
        (t, t, "the plan", "agy · medium · 42 s · searched notes, wrote 1 note", jid),
    )
    (app.paths.state / "chat").mkdir(exist_ok=True)
    (app.paths.state / "chat" / "history.json").write_text(
        json.dumps(
            [
                {"user": "plan my topology revision", "assistant": "the plan", "at": t},
                {"user": "what is a compact space", "assistant": "…", "at": t + 60},
            ]
        )
    )
    return env, a, b, t


def test_the_words_fade_and_settle_into_gists(old):
    env, a, b, t = old
    app = env.app
    with open(app.events.file, "a") as f:  # what the event log saw the older call use
        ts = dt.datetime.fromtimestamp(t + 3500).isoformat()
        f.write(json.dumps({"ts": ts, "kind": "calls_tool", "name": "hold_calls"}) + "\n")
    out = retention.expire(app)
    assert out["calls"] == 2 and out["requests"] == 1 and out["chats"] == 2
    assert not a.exists() and not a.with_name(a.stem + gists.DID).exists()  # the tool log goes with its transcript
    lines = [g["text"] for g in gists.load(app)]
    assert lines[0] == (
        "Call (Evening check-in): set reminder: I'll remind you Fri 23 Oct at 09:00: book the lab slot; "
        "used search_notes"
    )
    assert "wear goggles" not in json.dumps(gists.load(app))  # what a tool read is never kept
    assert lines[1] == "plan my topology revision · answered · agy · medium · 42 s · searched notes, wrote 1 note"
    assert lines[2] == "what is a compact space"  # the chat turn of the request above adds nothing
    assert lines[3] == "Call: used hold_calls"
    assert app.jobs.ending(0, retention.END) == []  # the words are gone
    retention.expire(app)
    assert len(gists.load(app)) == 4  # once

    # /gists: newest first, numbered; words find; forget one
    said = env.say("/gists")
    assert said.startswith("The latest gists (kept until you /forget all") and "1. " in said
    assert "lab slot" in env.say("/gists lab slot") and env.say("/gists nothing-like-it").startswith("No gist")
    assert env.say("/gists forget 1").startswith("Forgot it: Call: used hold_calls")
    assert len(gists.load(app)) == 3


def test_words_wait_for_their_gist(old, monkeypatch):
    env, a, b, t = old

    def broken(app, lo, hi):
        raise OSError("disk full")

    monkeypatch.setitem(gists.MAKERS, "calls", broken)
    out = retention.expire(env.app)
    assert "calls" not in out and a.exists()  # the daily job keeps the words until the gist exists
    assert out["requests"] == 1
    assert env.say("/forget 1000w").startswith("Forgot 2 call transcripts")  # what you ask for still goes now


def test_off_no_gists_and_sensitive_lines_keep_only_their_kind(old):
    env, a, b, t = old
    app = env.app
    jid = app.jobs.submit("my bank loans", title="sort out my bank loans")
    app.jobs._db.execute(
        "update jobs set status='failed', verdict='timeout', created=?, finished=? where id=?", (t, t, jid)
    )
    retention.forget(app, 0, kinds=("requests",))
    texts = [g["text"] for g in gists.load(app)]
    assert "an AI request about something money (its words aren't kept)" in texts
    assert not any("bank" in x for x in texts)
    gists.clear(app)
    app.settings.set("privacy.keep_gist", False)
    retention.expire(app)
    assert gists.load(app) == [] and not a.exists()


def test_gists_keep_for_good_unless_given_a_time(env):
    app = env.app
    t = time.time()
    gists._save(app, [{"at": t - 400 * DAY, "kind": "chat", "text": "old"}, {"at": t, "kind": "chat", "text": "new"}])
    assert gists.expire(app) == 0
    app.settings.set("privacy.gist_days", 365)
    assert gists.expire(app) == 1 and [g["text"] for g in gists.load(app)] == ["new"]


def test_forget_all_asks_about_the_gists(old):
    env, a, b, t = old
    app = env.app
    env.say("/forget all")
    sent = [p for m, p in env.fake.sent if m == "sendMessage"][-1]
    assert "Forget gists too" in json.dumps(sent["reply_markup"]) and "gists" in sent["text"]
    out = env.press(f"fgt:{int(time.time())}:all")
    assert out.startswith("Forgot 2 call transcripts") and len(gists.load(app)) == 4  # they settled and stay
    out = env.press(f"fgt:{int(time.time())}:gists")
    assert out == "Forgot 4 gists." and gists.load(app) == []


def test_a_local_model_adds_a_sentence_only_when_allowed(old, monkeypatch):
    env, a, b, t = old
    app = env.app
    assert gists.local_model(app) is None  # privacy.gist_model is off by default
    app.settings.set("privacy.gist_model", True)
    assert gists.local_model(app) is None  # ...and Local AI models is off

    class Reply:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps({"response": "They agreed to book the lab slot on Friday."}).encode()

    asked = []
    monkeypatch.setattr(gists, "local_model", lambda app: "helper:tag")
    lm = app.modules["local_models"]
    monkeypatch.setattr(lm, "api", lambda path, body, timeout=10: asked.append(body) or Reply())
    line = gists.call_line(app, a, t, 0)
    assert line.endswith("used search_notes. They agreed to book the lab slot on Friday.")
    assert asked[0]["model"] == "helper:tag" and "book the lab slot" in asked[0]["prompt"]


def test_a_call_keeps_its_tool_log_next_to_its_transcript(env):
    env.app.settings.set("availability.night.enabled", False)
    c = env.app.modules["calls"]
    c.tool_log["5"] = [{"name": "add_deadline", "args": "{}", "result": "Added: essay, due Mon 26 Oct 23:59"}]
    c.save_transcript({"lines": [{"who": "You", "text": "add the essay"}], "since": "5", "purpose": "Quick call"})
    (f,) = (env.app.paths.state / "calls" / "transcripts").glob("*.txt")
    did = json.loads(f.with_name(f.stem + gists.DID).read_text())
    assert did == {
        "purpose": "Quick call",
        "did": [{"name": "add_deadline", "result": "Added: essay, due Mon 26 Oct 23:59"}],
    }

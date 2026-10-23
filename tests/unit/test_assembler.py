"""The context assembler: an AI reply is told the few remembered items the message refers to (open threads, gists,
meetings, daily notes), within memory.budget_tokens, never transcripts;
nothing when the message refers to nothing; the receipt counts them; a call's brief gets the open threads and the
day's gists."""

import datetime as dt
import time

import pytest

from kurooto import providers
from kurooto.core import assembler, gists, threads
from kurooto.providers.base import Result, Verdict


@pytest.fixture
def mem(env):
    """Two open threads, a call from this morning (its transcript holds words its gist doesn't), an older gist."""
    app = env.app
    threads.observe(app, "I'll send the glacier draft to Ortiz tonight.")
    threads.observe(app, "I need to book the wind tunnel slot.")
    app.settings.set("availability.night.enabled", False)
    c = app.modules["calls"]
    c.tool_log["5"] = [{"name": "add_reminder", "args": "{}", "result": "I'll remind you at 21:00: glacier draft"}]
    c.save_transcript(
        {
            "lines": [{"who": "You", "text": "the zebra plan stays between us, remind me about the glacier draft"}],
            "since": "5",
            "purpose": "Morning call",
        }
    )
    old = {"at": time.time() - 5 * 86400, "kind": "request", "text": "plan my topology revision · answered"}
    gists._save(app, [old])
    return env


def test_only_what_the_message_refers_to(mem):
    app = mem.app
    assert assembler.build(app, "what's the capital of France?") == ("", 0)
    block, n = assembler.build(app, "what did we say on the call about the glacier draft?")
    assert n >= 2 and block.startswith(f"What {app.name} remembers")
    assert "open thread, said in a chat at" in block and "send the glacier draft to Ortiz tonight" in block
    assert "call at " in block and "set reminder: I'll remind you at 21:00: glacier draft" in block
    assert "zebra" not in block  # gists only, never the transcript
    assert "wind tunnel" not in block  # not what it's about
    # no cue, but two shared words with an open thread: that thread only
    block, n = assembler.build(app, "help me word the wind tunnel booking")
    assert n == 1 and "book the wind tunnel slot" in block


def test_the_budget_caps_it(mem):
    app = mem.app
    for i in range(40):
        threads.observe(app, f"I'll revise glacier chapter {i} with the draft notes number {i}.")
    text = "where was I with the glacier draft? did I send it?"
    block, n = assembler.build(app, text)
    assert len(block) <= 600 * assembler.CHARS_PER_TOKEN and 2 <= n < 41
    app.settings.set("memory.budget_tokens", 80)
    small, k = assembler.build(app, text)
    assert len(small) <= 320 and 1 <= k < n
    app.settings.set("memory.budget_tokens", 0)
    assert assembler.build(app, text) == ("", 0)
    app.settings.set("memory.budget_tokens", 600)
    app.settings.set("memory.recall", False)
    assert assembler.build(app, text) == ("", 0)


def test_that_thing_is_named_with_its_guardrail(env):
    app = env.app
    threads.observe(app, "I'll send the glacier draft to Ortiz tonight.")
    block, n = assembler.build(app, "can you check that thing for me?")
    assert "persona card" not in block  # it goes into every request through providers/context.py, once
    assert n == 1 and '"That thing" most likely means: "send the glacier draft to Ortiz tonight"' in block
    assert "never send, move or delete anything for it without asking them first" in block


class Fake:
    id, label, kind = "fake", "A fake AI", "api"

    def __init__(self):
        self.tasks = []

    def available(self):
        return True, ""

    def run(self, task):
        self.tasks.append(task)
        return Result(Verdict.OK, "Done.", 3.0)


def test_a_request_is_told_and_its_receipt_counts_them(mem, monkeypatch):
    app = mem.app
    app.settings.set("jobs.receipt", True)
    brain = Fake()
    monkeypatch.setattr(providers, "build", lambda a, w: brain if w == "main" else None)
    app.settings.set("brain.main", "main")
    jid = app.jobs.submit("History:\nUser: hi\n\nCurrent request:\ndid I send the glacier draft yesterday?")
    assert app.jobs.run_next() == jid
    assert "send the glacier draft to Ortiz tonight" in brain.tasks[0].context
    assert app.jobs.receipt(jid).endswith(" remembered items")
    jid = app.jobs.submit("what's the capital of France?")
    app.jobs.run_next()
    assert "remembers" not in brain.tasks[1].context and "remembered" not in app.jobs.receipt(jid)
    jid = app.jobs.submit("did I send the glacier draft?", background=True)  # not yours: nothing
    app.jobs.run_next("bg")
    assert "remembers" not in brain.tasks[2].context


def test_a_calls_brief_has_the_threads_and_the_days_gists(mem):
    brief = mem.app.modules["calls"].pending()
    assert brief["open_threads"][0].startswith("open thread, said in a chat at ")
    assert any("Morning call" in x for x in brief["earlier"])
    assert not any("topology" in x for x in brief["earlier"])  # five days ago: not the last day
    assert dt.datetime.now().strftime("%H:") in " ".join(brief["earlier"])

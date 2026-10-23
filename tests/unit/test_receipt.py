"""The run receipt: every answer from your AI ends with one quiet line built from the run's own record (which AI, the
effort, how long, the share of today's limit, what it did from its tool log), in italics on Telegram and as plain
text in the dashboard and the terminal; jobs.receipt turns it off, and quiet requests get none."""

from __future__ import annotations

import pytest

from kurooto import providers
from kurooto.core import jobs as jobs_mod
from kurooto.providers.base import Result, Verdict
from kurooto.web import tools_api


class Fake:
    id, label, kind = "fake", "A fake AI", "api"

    def __init__(self, steps=()):
        self.steps = steps

    def available(self):
        return True, ""

    def run(self, task):
        for name, args in self.steps:
            task.run_tool(name, args)
        return Result(Verdict.OK, "Paris.", 3.0)


class Agent(Fake):
    id, label, kind = "claude", "Claude Code", "cli"

    def prepare(self, app):
        pass

    def mark_worked(self, app):
        pass


@pytest.fixture
def rec(env, monkeypatch):
    env.app.settings.set("jobs.receipt", True)
    brain = {"b": Fake()}
    monkeypatch.setattr(providers, "build", lambda a, w: brain["b"] if w == "main" else None)
    env.app.settings.set("brain.main", "main")
    return env, brain


def ask(env, prompt="what's the capital of France?", **kw):
    jid = env.app.jobs.submit(prompt, effort="low", **kw)
    assert env.app.jobs.run_next() == jid
    return jid


def test_the_line_says_what_it_did_from_the_tool_log():
    steps = [{"name": n} for n in ("search_notes", "read_note", "search_notes", "write_note", "add_reminder")]
    line = jobs_mod.receipt(Fake(), "medium", 42.4, 12, steps)
    did = "searched notes, read 1 note, wrote 1 note, set 1 reminder"
    assert line == f"A fake AI · medium · 42 s · 12% of today's limit · {did}"
    assert jobs_mod.receipt(Fake(), "low", 0.2, None, []) == "A fake AI · low · 1 s · did nothing"
    two = jobs_mod.receipt(Fake(), "high", 125, None, [{"name": "draft_reply"}] * 2 + [{"name": "plan_block"}])
    assert two == "A fake AI · high · 2 min · drafted 2 replies, used 1 other tool"


def test_an_agent_program_did_nothing_through_kurooto_only():
    """agy and Claude Code also work with tools of their own, which Kurooto doesn't see."""
    assert jobs_mod.receipt(Agent(), "medium", 90, None, []).endswith(
        "Claude Code · medium · 2 min · did nothing through Kurooto"
    )


def test_the_line_stays_short():
    steps = [{"name": n} for n in jobs_mod.ACTS]
    line = jobs_mod.receipt(Fake(), "medium", 4000, 99, steps)
    assert len(line) <= jobs_mod.RECEIPT_MAX and line.endswith(" and more")
    assert line.startswith("A fake AI · medium · 1 h 7 min · 99% of today's limit · searched notes")


def test_telegram_answer_ends_with_it_in_italics(rec):
    env, brain = rec
    brain["b"] = Fake([("search_notes", {"query": "france"}), ("write_note", {"slug": "inbox/paris", "text": "Paris"})])
    env.app.settings.set("quota.limits", {"fake": 4})
    env.app.quota.record("fake", "ok")
    ask(env)
    text = env.fake.texts()[-1]
    body, tail = text.rsplit("\n\n", 1)
    assert body.endswith("Paris.")
    assert tail.startswith("A fake AI · low · ")
    assert tail.endswith(" · 25% of today's limit · searched notes, wrote 1 note")
    sent = [p for m, p in env.fake.sent if m == "sendMessage"][-1]
    assert sent["entities"] == [{"type": "italic", "offset": len(text) - len(tail), "length": len(tail)}]


def test_dashboard_and_terminal_get_it_as_plain_text(rec):
    env, _ = rec
    jid = ask(env, quiet=True)  # the terminal's and the dashboard's own requests aren't sent anywhere
    assert env.fake.texts()[-1] != "Paris."
    code, out = tools_api.job(env.app, jid)
    assert code == 200 and out["receipt"].endswith("did nothing")
    assert out["answer"] == f"Paris.\n\n{out['receipt']}"


def test_turned_off_and_quiet_work_get_none(rec):
    env, _ = rec
    sent = len(env.fake.texts())
    ask(env, "a digest nobody waits for", quiet=True, background=True)
    assert len(env.fake.texts()) == sent  # quiet background work messages nobody: no receipt anywhere
    env.app.settings.set("jobs.receipt", False)
    jid = ask(env)
    assert env.fake.texts()[-1].endswith("Paris.")
    assert "receipt" not in tools_api.job(env.app, jid)[1]
    assert [p for m, p in env.fake.sent if m == "sendMessage"][-1].get("entities") is None


def test_a_failed_request_says_how_it_went_too(rec):
    env, brain = rec

    class Broken(Fake):
        def run(self, task):
            return Result(Verdict.ERROR, "", 1.0, "boom")

    brain["b"] = Broken()
    ask(env)
    text = env.fake.texts()[-1]
    assert "Something went wrong talking to A fake AI." in text and text.endswith(" · did nothing")

"""0.6.0: which model answered, shown; one AI's limit hands the request to the other (Claude Code to agy and back);
and the self-aware manual (core/selfdoc.py, data/ai-manual.md). Fake agy and Claude Code programs; no network."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

from kurooto import providers
from kurooto.core import jobs as jobs_mod
from kurooto.core import selfdoc
from kurooto.core.proc import Result as Run
from kurooto.providers import fallback
from kurooto.providers.agy import Agy
from kurooto.providers.base import Result, Verdict, short_model
from kurooto.providers.claude import ClaudeCode, reset_at, used_model

FAKES = Path(__file__).parents[1] / "fakes"
FAKE_AGY = [sys.executable, str(FAKES / "fake_agy.py")]
FAKE_CLAUDE = [sys.executable, str(FAKES / "fake_cli.py")]
ROOT = Path(__file__).resolve().parents[2]


# ------------------------------------------------------------------------------------------------ which model
def test_model_ids_are_shortened_for_the_receipt():
    assert short_model("claude-opus-4-5-20251101") == "opus-4.5"
    assert short_model("claude-3-5-haiku-20241022") == "3.5-haiku"
    assert short_model("gemini-3.8-flash-medium", "medium") == "3.8-flash"  # the effort is named beside it
    assert short_model("gemini-3.8-flash-high", "low") == "3.8-flash-high"  # not the effort shown: kept
    assert short_model("models/gemini-flash-latest") == "gemini-flash"
    assert short_model("gemma4:e4b") == "gemma4:e4b" and short_model("llama-3-8b") == "llama-3-8b"
    assert short_model("claude-opus-5-5[1m]") == "opus-5.5" and short_model("") == ""


def test_claude_code_says_which_model_did_the_work():
    data = {
        "type": "result",
        "result": "Hi.",
        "modelUsage": {
            "claude-haiku-4-5-20251001": {"costUSD": 0.001, "outputTokens": 20},
            "claude-opus-4-5-20251101": {"costUSD": 0.2, "outputTokens": 900},
        },
    }
    assert used_model(data) == "claude-opus-4-5-20251101"
    assert used_model({"model": "claude-sonnet-4-5"}) == "claude-sonnet-4-5" and used_model({}) == ""
    r = ClaudeCode(exe="claude").verdict(Run(0, json.dumps(data), ""), 1.0, 15)
    assert r.ok and r.model == "claude-opus-4-5-20251101"


def test_claude_code_without_a_report_names_the_model_it_was_given(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_CLI_MODE", "ok")
    from kurooto.providers.base import Task

    r = ClaudeCode(exe=FAKE_CLAUDE, models={"high": "opus"}).run(Task(prompt="hi", effort="high", text_only=True))
    assert r.ok and r.model == "opus"


def test_agy_names_the_model_it_ran_with(monkeypatch):
    from kurooto.providers.base import Task

    monkeypatch.setenv("FAKE_AGY_MODE", "ok")
    r = Agy(exe=FAKE_AGY).run(Task(prompt="hi", effort="high", text_only=True))
    assert r.ok and r.model == "gemini-3.8-flash-high" and "gemini-3.8-flash-high" in r.text


class Fake:
    id, label, kind = "fake", "A fake AI", "api"


class Program(Fake):
    id, label, kind = "claude", "Claude Code (Advanced)", "cli"


def test_the_receipt_names_the_model_who_decided_and_who_stood_in():
    line = jobs_mod.receipt(Program(), "high", 42, None, [], model="claude-opus-4-5-20251101")
    assert line == "Claude Code · opus-4.5 · high · 42 s · did nothing through Kurooto"
    line = jobs_mod.receipt(Program(), "high", 42, None, [], model="claude-opus-4-5", decided="gemma4:e4b")
    assert line.startswith("decided by gemma4:e4b, answered by Claude Code · opus-4.5 · high · 42 s")
    fell = "Claude Code hit its limit; agy answered"
    agy = type("A", (), {"id": "agy", "label": "Antigravity (agy)", "kind": "cli"})()
    line = jobs_mod.receipt(agy, "medium", 9, None, [], model="gemini-3.8-flash-medium", fell=fell)
    assert line.startswith("Claude Code hit its limit; agy answered · 3.8-flash · medium · 9 s")
    steps = [{"name": n} for n in jobs_mod.ACTS]
    long = jobs_mod.receipt(agy, "medium", 9, 50, steps, 3, model="x" * 20, decided="y" * 10, fell=fell)
    assert len(long) <= jobs_mod.RECEIPT_MAX and long.endswith("50% of today's limit · used 3 remembered items")
    huge = jobs_mod.receipt(agy, "medium", 9, 50, steps, 3, model="x" * 40, decided="y" * 30, fell=fell)
    assert len(huge) <= jobs_mod.RECEIPT_MAX


# --------------------------------------------------------------------------------------------- limits
@pytest.mark.parametrize(
    "text",
    [
        "5-hour limit reached ∙ resets 3pm",
        "You've hit your limit · resets 3:30pm (Europe/Berlin)",
        "Weekly limit reached ∙ resets Oct 27, 9am",
        "Opus weekly limit reached ∙ resets Mon 9am",
    ],
)
def test_claude_says_when_its_limit_resets(text):
    now = time.time()
    at = reset_at(text, now)
    assert at is not None and now < at <= now + 370 * 86400
    r = ClaudeCode(exe="claude").verdict(
        Run(1, json.dumps({"type": "result", "is_error": True, "result": text}), ""), 1, 15
    )
    assert r.verdict == Verdict.RATE_LIMITED and r.retry_after_s and r.usage["limit"]["reset_at"]
    assert reset_at("try again in a while") is None and reset_at("resets 5 things") is None


@pytest.fixture
def two(tmp_path, monkeypatch):
    """Claude Code and agy (fakes) both set up and having worked here; no Gemini key."""
    from kurooto.app import App

    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    orig = providers.build
    app = App()

    def build(a, w):
        if w == "agy":
            return Agy(exe=FAKE_AGY)
        if w == "claude":
            return ClaudeCode(exe=FAKE_CLAUDE, app=a)
        return orig(a, w)

    monkeypatch.setattr(providers, "build", build)
    for b in ("agy", "claude"):
        build(app, b).mark_worked(app)
    app.settings.set("jobs.receipt", True)
    sent: list[str] = []
    app.notifier.send = lambda text, **kw: sent.append(text)
    yield app, sent, monkeypatch
    app.close()


def ask(app, prompt="what's due?"):
    jid = app.jobs.submit(prompt, effort="medium")
    app.jobs.run_next()
    return app.jobs.get(jid)


def test_claude_at_its_limit_hands_over_to_agy_and_is_skipped_until_its_reset(two):
    app, sent, mp = two
    app.settings.set("brain.main", "claude")
    mp.setenv("FAKE_CLI_MODE", "limit")
    mp.setenv("FAKE_AGY_MODE", "ok")
    job = ask(app)
    assert job.status == "ok" and job.brain == "agy" and job.model == "gemini-3.8-flash-medium"
    line = app.jobs.receipt(job.id)
    assert line.startswith("Claude Code hit its limit; agy answered · 3.8-flash · medium")
    assert sent[-1].endswith(line)
    until = fallback.cooling(app, "claude")
    assert until and until > time.time() + 20 * 60  # no reset said: the back-off
    job = ask(app, "and tomorrow?")  # straight to agy: Claude Code isn't tried
    tries = app.jobs._read("select brain from attempts where job=?", (job.id,), one=False)
    assert [t[0] for t in tries] == ["agy"]
    assert app.jobs.receipt(job.id).startswith("Claude Code is at its limit until ")
    mp.setenv("FAKE_CLI_MODE", "ok")
    fallback.clear(app, "claude")
    assert ask(app, "x").brain == "claude"


def test_and_the_other_way_round(two):
    app, sent, mp = two
    app.settings.set("brain.main", "agy")
    mp.setenv("FAKE_AGY_MODE", "limit")
    mp.setenv("FAKE_CLI_MODE", "ok")
    job = ask(app)
    assert job.status == "ok" and job.brain == "claude" and job.result.startswith("claude says:")
    assert app.jobs.receipt(job.id).startswith("agy hit its limit; Claude Code answered")
    assert fallback.cooling(app, "agy")
    assert any(e["kind"] == "brain_limited" and e.get("brain") == "agy" for e in app.events.tail(20))


def test_only_what_fallback_on_says_moves_a_request(two):
    app, sent, mp = two
    app.settings.set("brain.main", "claude")
    mp.setenv("FAKE_CLI_MODE", "auth")
    mp.setenv("FAKE_AGY_MODE", "ok")
    job = ask(app)
    assert job.status == "failed" and job.verdict == "auth"  # signed out isn't a limit: by default nobody steps in
    app.settings.set("brain.fallback_on", ["rate_limited", "auth"])
    job = ask(app)
    assert job.status == "ok" and job.brain == "agy"
    assert app.jobs.receipt(job.id).startswith("Claude Code isn't signed in; agy answered")


def test_an_empty_order_means_no_stand_in(two):
    app, sent, mp = two
    app.settings.set("brain.main", "claude")
    app.settings.set("brain.fallback_on", [])
    mp.setenv("FAKE_CLI_MODE", "limit")
    job = ask(app)
    assert job.status == "failed" and job.verdict == "rate_limited"
    job = ask(app)  # at its limit and nobody else: it's tried anyway (it may be back early)
    assert job.brain == "claude"


def test_a_fallback_you_pick_is_the_order_one_or_a_list(two):
    app, sent, mp = two
    app.settings.set("brain.main", "claude")
    app.settings.set("brain.fallback", ["gemini", "agy"])  # no Gemini key: it can't, so agy does
    mp.setenv("FAKE_CLI_MODE", "auth")  # a fallback you picked takes over on any failure, as before
    mp.setenv("FAKE_AGY_MODE", "ok")
    job = ask(app)
    assert job.status == "ok" and job.brain == "agy"
    assert fallback.chosen(app) == ["gemini", "agy"]
    app.settings.set("brain.fallback", "agy")  # an older single name still works
    assert fallback.chosen(app) == ["agy"] and ask(app).brain == "agy"
    app.settings.set("brain.fallback", ["codex", "agy"])
    assert providers.drop_retired(app) == ["codex"] and app.settings.get("brain.fallback") == ["agy"]


def test_fallback_first_moves_the_first_of_a_list_ahead_at_its_levels(two):
    from kurooto.core import tuning

    app, sent, mp = two
    app.settings.set("brain.main", "claude")
    app.settings.set("brain.fallback", ["agy", "gemini"])
    app.settings.set("brain.fallback_first", ["medium"])  # tuned while dreaming (core/tuning.py)
    mp.setenv("FAKE_CLI_MODE", "ok")
    mp.setenv("FAKE_AGY_MODE", "ok")
    assert ask(app).brain == "agy"
    app.settings.set("brain.fallback_first", [])
    assert ask(app).brain == "claude"
    assert tuning._brains(app) == ("claude", "agy")  # the pair it tunes: main and the first fallback


def test_an_ai_that_never_answered_here_isnt_a_stand_in(two):
    app, sent, mp = two
    (app.paths.state / "agy-worked.json").unlink()
    app.settings.set("brain.main", "claude")
    mp.setenv("FAKE_CLI_MODE", "limit")
    assert ask(app).status == "failed"


def test_the_backoff_doubles_and_a_reset_it_names_wins(tmp_path, monkeypatch):
    from kurooto.app import App

    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    app = App()
    try:
        now = 1_000_000.0
        lim = Result(Verdict.RATE_LIMITED)
        assert fallback.cool(app, "claude", lim, now) == now + 30 * 60
        assert fallback.cool(app, "claude", lim, now + 60) == now + 60 + 60 * 60
        said = Result(Verdict.RATE_LIMITED, usage={"limit": {"reset_at": now + 7200}})
        assert fallback.cool(app, "claude", said, now + 120) == now + 7200
        minute = Result(Verdict.RATE_LIMITED, usage={"limit": {"per": "minute"}})
        assert fallback.cool(app, "gemini", minute, now) == now + 60
        assert fallback.status(app, now + 100) and fallback.cooling(app, "claude", now + 7300) is None
        fallback.clear(app, "claude")
        assert fallback.cooling(app, "claude", now) is None
    finally:
        app.close()


def test_the_decision_model_is_named_when_it_isnt_the_one_that_answered(tmp_path, monkeypatch):
    from kurooto.app import App

    class Small:
        id, label, kind = "ollama", "Ollama on this computer", "api"

        def available(self):
            return True, ""

        def complete(self, q, **kw):
            return Result(Verdict.OK, "high", 0.1, model="gemma4:e4b")

    class Big(Small):
        id, label = "custom", "Your AI"

        def run(self, task):
            return Result(Verdict.OK, "Done.", 2, model="big-model-2")

    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    app = App()
    try:
        monkeypatch.setattr(providers, "build", lambda a, w: {"custom": Big(), "ollama": Small()}.get(w))
        app.settings.set("brain.main", "custom")
        app.settings.set("brain.classify", "ollama")
        app.settings.set("jobs.receipt", True)
        app.notifier.send = lambda *a, **k: None
        jid = app.jobs.submit("compare these two ideas")
        app.jobs.run_next()
        job = app.jobs.get(jid)
        assert job.effort == "high" and job.model == "big-model-2"
        assert app.jobs.receipt(jid).startswith(
            "decided by gemma4:e4b, answered by your AI service · big-model-2 · high"
        )
        text, _ = app.jobs.command()
        assert "your AI service big-model-2" in text
        assert jobs_mod.public(job)["model"] == "big-model-2" and jobs_mod.public(job)["receipt"]
    finally:
        app.close()


# ------------------------------------------------------------------------------------- the concept graph
def test_a_role_at_its_limit_goes_to_the_next_ai_and_counts_on_its_own_budget(two):
    from kurooto.core import readbudget as rb

    app, sent, mp = two
    app.settings.set("integrate.roles", {"bulk": "claude", "check": "agy"})
    m = app.modules["integrate"]
    assert m.roles() == ("claude", "agy")
    fallback.cool(app, "claude", Result(Verdict.RATE_LIMITED, usage={"limit": {"reset_at": time.time() + 3600}}))
    assert m.roles() == ("agy", "agy")  # reading goes on, on agy, until Claude's reset
    b = rb.Budget(app, lambda: m.roles()[0])
    b.count("agy")
    data = json.loads((app.paths.state / "integrate" / "budget.json").read_text())
    assert "agy" in data["brains"] and "claude" not in data["brains"]
    job = type("J", (), {"brain": "agy"})()
    res = Result(
        Verdict.OK,
        "{}",
        usage={"limits": [{"brain": "claude", "retry_after_s": 3600, "detail": "Claude usage limit reached"}]},
    )
    b.seen(job, res)  # Claude's limit lands on Claude's own record, not agy's
    data = json.loads((app.paths.state / "integrate" / "budget.json").read_text())
    assert data["brains"]["claude"].get("hold_until") and not data["brains"]["agy"].get("hold_until")


# --------------------------------------------------------------------------------------------- self.md
@pytest.fixture
def app(tmp_path, monkeypatch):
    from kurooto.app import App

    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    a = App()
    yield a
    a.close()


def test_self_md_says_what_runs_without_contents_or_secrets(app):
    from kurooto import __version__

    app.secrets.set("gemini.api_key", "AIzaFAKE-not-a-real-key-123")
    app.settings.set("brain.main", "gemini")
    app.settings.set("modules.enabled", ["reminders"])
    app.events.emit("job_crashed", job="j1", error="ValueError: the text of my private note")
    app.events.emit("job_done", job="j2", ok=False, verdict="rate_limited", brain="gemini")
    text = selfdoc.refresh(app)
    assert f"Kurooto {__version__}" in text and "update channel stable" in text
    assert "Main AI: " in text and "[gemini]" in text
    assert "at a limit (brain.fallback_on: rate_limited) these take over" in text
    assert "- reminders (Reminders): " in text and "- Off: " in text
    assert "job_crashed error=ValueError" in text and "job_done brain=gemini verdict=rate_limited" in text
    assert "private note" not in text and "AIzaFAKE" not in text
    assert str(app.paths.config / "settings.json") in text
    assert selfdoc.path(app) == app.paths.state / "reserve" / "self.md" and selfdoc.path(app).is_file()


def test_it_is_written_again_when_what_it_describes_changes(app):
    selfdoc.refresh(app)
    assert not selfdoc.stale(app)
    app.settings.set("modules.enabled", ["reminders"])
    assert selfdoc.stale(app)
    assert "- reminders (Reminders)" in selfdoc.refresh(app)


def test_every_ai_can_read_it(app):
    from kurooto.core import mcp
    from kurooto.core.tools import agent_tools, run_tool

    tools = {t.name: t for t in agent_tools(app)}
    assert tools["kurooto_self"].writes is False
    assert "## AI" in run_tool(app, "kurooto_self", {})
    assert "Never without the user's tap" in run_tool(app, "kurooto_self", {"part": "manual"})
    assert "What " in mcp.resource_text("kurooto://self", app.paths)
    assert mcp.resource_text("kurooto://manual").startswith("# How Kurooto works")
    from kurooto.core import reserve

    reserve.refresh(app)
    guide = (app.paths.state / "reserve" / "agent-guide.md").read_text()
    assert "self.md" in guide and (app.paths.state / "reserve" / "ai-manual.md").is_file()


def test_a_question_about_kurooto_gets_it_in_its_context(app):
    assert selfdoc.wanted("why didn't my alarm ring?") and selfdoc.wanted("which model answered that?")
    assert selfdoc.wanted("is Kurooto at its usage limit") and selfdoc.wanted("ask Jarvis something", "Jarvis")
    assert not selfdoc.wanted("summarise my linear algebra notes")
    assert not selfdoc.wanted("what model of laptop should I buy")
    assert selfdoc.for_request(app, "plan my day") == ""
    assert "## Features" in selfdoc.for_request(app, "why isn't kurooto working?")


def test_fixme_ask_my_ai_sends_what_runs_too(app, monkeypatch):
    from kurooto.core import fixme
    from kurooto.core.state import jsave

    jsave(app.paths.state / fixme.FILE, {"answer": "Not working: Telegram.", "text": ""})
    monkeypatch.setattr(fixme, "ai_works", lambda a: (True, ""))
    got = {}
    monkeypatch.setattr(app.jobs, "submit", lambda prompt, **kw: got.setdefault("p", prompt) and "j1")
    fixme.explain(app)
    assert "Not working: Telegram." in got["p"] and "## AI" in got["p"]


# ---------------------------------------------------------------------------------------- the manual
def test_the_manual_is_current():
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "gen_ai_manual.py"), "--check"], capture_output=True)
    assert r.returncode == 0, r.stderr.decode()


def test_the_manual_names_every_feature_command_and_tap_rule(app):
    from kurooto.core import commands, tap

    text = selfdoc.manual_text()
    for m in app.modules.values():
        assert f"`{m.id}`" in text, m.id
        for c in m.commands():
            assert f"/{c.name}" in text, c.name
    for names, _ in (*commands.CORE, commands.SYNC):
        assert all(f"/{n}" in text for n in names)
    assert all(f"`{k}`" in text for k in tap.GUARDED)


def test_the_header_line_can_go_and_the_answer_comes_alone(two):
    """(0.8.17, jobs.header) "[AI · effort] what you asked" first was most of a short answer's length."""
    app, sent, mp = two
    app.settings.set("brain.main", "agy")
    mp.setenv("FAKE_AGY_MODE", "ok")
    ask(app, "what's due?")
    assert sent[-1].startswith("[")
    app.settings.set("jobs.header", False)
    app.settings.set("jobs.receipt", False)
    ask(app, "and tomorrow?")
    assert not sent[-1].startswith("[") and sent[-1].startswith("answer from")  # the answer alone

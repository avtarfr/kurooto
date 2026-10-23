"""0.7.0: more than one Claude account, each its own AI ("claude:work"): its own config folder (CLAUDE_CONFIG_DIR),
limits, receipt line, self.md and /usage line; the second follows the first at a limit. Fake Claude Code and agy
programs only; the real one is never run, and nothing is written outside the sandbox."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

from kurooto import providers
from kurooto.core import selfdoc
from kurooto.providers import claude_accounts as ca
from kurooto.providers import fallback
from kurooto.providers.agy import Agy
from kurooto.providers.base import Task
from kurooto.providers.claude import ClaudeCode

FAKES = Path(__file__).parents[1] / "fakes"
FAKE_AGY = [sys.executable, str(FAKES / "fake_agy.py")]
FAKE_CLAUDE = [sys.executable, str(FAKES / "fake_cli.py")]


@pytest.fixture
def app(tmp_path, monkeypatch):
    from kurooto.app import App

    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path / "k"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))  # the user's own ~/.claude: must stay untouched
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    a = App()
    yield a
    a.close()
    assert not (tmp_path / "home" / ".claude").exists()


@pytest.fixture
def fakes(app, monkeypatch):
    """Every Claude account and agy as fakes, through the real build (so the quota meter and labels are real)."""
    orig = providers.build

    def build(a, w):
        if w == "agy":
            return Agy(exe=FAKE_AGY)
        b = orig(a, w)
        if isinstance(b, ClaudeCode):
            b.exe = FAKE_CLAUDE
        return b

    monkeypatch.setattr(providers, "build", build)
    app.settings.set("jobs.receipt", True)
    sent: list[str] = []
    app.notifier.send = lambda text, **kw: sent.append(text)
    return build, sent


def ask(app, prompt="what's due?"):
    jid = app.jobs.submit(prompt, effort="medium")
    app.jobs.run_next()
    return app.jobs.get(jid)


# ------------------------------------------------------------------------------------------------ accounts
def test_an_account_has_its_own_id_folder_and_name(app):
    work = ca.add(app, "Work")
    assert work.id == "claude:work" and work.label == "Claude Code (Work)"
    two = ca.add(app)  # no name: numbered
    assert two.id == "claude:2" and ca.add(app, "work stuff").id == "claude:work-stuff"
    with pytest.raises(ValueError):
        ca.add(app, "work")  # names are unique
    f = ca.folder(app, "work")
    assert f.is_dir() and f.parent == app.paths.data / "claude-accounts"
    if sys.platform != "win32":
        assert f.stat().st_mode & 0o077 == 0  # only the user
    assert ca.ids(app) == ["claude:work", "claude:2", "claude:work-stuff"]
    assert providers.label("claude:work") == "Claude Code (Work)" and providers.label("claude") == "Claude Code"
    assert list(providers.choices(app))[list(providers.choices(app)).index("claude") + 1] == "claude:work"
    assert providers.build(app, "claude:nope") is None and providers.build(app, "claude:work").id == "claude:work"
    assert ca.is_claude("claude") and ca.is_claude("claude:2") and not ca.is_claude("claude:Bad Key")


def test_each_run_gets_its_own_config_folder_and_the_usual_sign_in_none(app, monkeypatch):
    monkeypatch.setenv("FAKE_CLI_MODE", "whoami")
    ca.add(app, "work")
    work = providers.build(app, "claude:work")
    work.exe = FAKE_CLAUDE
    r = work.run(Task(prompt="hi", text_only=True))
    assert r.ok and r.text == f"config dir: {ca.folder(app, 'work')}"
    usual = providers.build(app, "claude")
    usual.exe = FAKE_CLAUDE
    assert usual.env() is None  # exactly as before: nothing added
    assert usual.run(Task(prompt="hi", text_only=True)).text == "config dir: (none)"


def test_models_are_its_own_else_claude_codes(app):
    ca.add(app, "work")
    app.settings.set("brain.models", {"claude": {"high": "opus"}})
    assert providers.build(app, "claude:work").models["high"] == "opus"
    app.settings.set("brain.models", {"claude": {"high": "opus"}, "claude:work": {"high": "sonnet"}})
    assert providers.build(app, "claude:work").models["high"] == "sonnet"


def test_an_account_not_signed_in_here_says_so(app):
    ca.add(app, "work")
    import shutil

    shutil.rmtree(ca.folder(app, "work"))  # a profile restored on another computer: the setting came, not the folder
    b = providers.build(app, "claude:work")
    b.exe = FAKE_CLAUDE
    ok, why = b.available()
    assert not ok and "isn't signed in on this computer" in why


# ------------------------------------------------------------------------------------------- limits, fallback
def test_the_first_at_its_limit_hands_over_to_the_second_then_agy(app, fakes, monkeypatch):
    build, sent = fakes
    ca.add(app, "work")
    for b in ("agy", "claude", "claude:work"):
        build(app, b).mark_worked(app)
    assert (app.paths.state / "claude-work-worked.json").is_file()  # no ":" in a file name
    app.settings.set("brain.main", "claude")
    assert fallback.auto(app) == ["claude:work", "agy", "claude", "gemini"]
    monkeypatch.setenv("FAKE_CLI_MODE", "ok")
    monkeypatch.setenv("FAKE_AGY_MODE", "ok")
    monkeypatch.setenv("FAKE_CLI_LIMIT_FOR", "default")
    job = ask(app)
    assert job.status == "ok" and job.brain == "claude:work" and job.result.startswith("claude says:")
    line = app.jobs.receipt(job.id)
    assert line.startswith("Claude Code hit its limit; Claude Code (work) answered · ")
    assert sent[-1].endswith(line)
    assert fallback.cooling(app, "claude") and fallback.cooling(app, "claude:work") is None  # limits apart
    job = ask(app, "and tomorrow?")  # straight to the second: the first isn't tried
    tries = app.jobs._read("select brain from attempts where job=?", (job.id,), one=False)
    assert [t[0] for t in tries] == ["claude:work"]
    monkeypatch.setenv("FAKE_CLI_LIMIT_FOR", "default,work")
    job = ask(app, "and the day after?")
    assert job.brain == "agy" and app.jobs.receipt(job.id).startswith("Claude Code (work) hit its limit; agy answered")
    assert fallback.cooling(app, "claude:work")
    assert any(e["kind"] == "brain_limited" and e.get("brain") == "claude:work" for e in app.events.tail(30))
    # each its own limit in the quota's count and in /usage
    pools = {r["pool"]: r for r in app.quota.report()}
    assert "claude" in pools and "claude:work" in pools and pools["claude:work"]["label"] == "Claude Code (work)"
    from kurooto.modules.chat import limit_lines, usage_text

    lines = limit_lines(app)
    assert any(x.startswith("Claude Code (work) is at its limit until") for x in lines)
    assert any(x.startswith("Claude Code is at its limit until") for x in lines)
    assert "Claude Code (work)" in usage_text(app.jobs.usage(7), 7)


def test_with_the_second_as_main_the_first_follows_it(app):
    ca.add(app, "work")
    app.settings.set("brain.main", "claude:work")
    assert fallback.auto(app)[:2] == ["claude", "agy"]
    app.settings.set("brain.main", "agy")
    assert fallback.auto(app) == ["agy", "claude", "claude:work", "gemini"]
    app.settings.set("brain.fallback", ["claude:work"])  # picked: that's the order
    assert fallback.order(app) == ["claude:work"]


def test_an_account_that_never_answered_isnt_a_stand_in(app, fakes, monkeypatch):
    build, _ = fakes
    ca.add(app, "work")
    build(app, "claude").mark_worked(app)
    app.settings.set("brain.main", "claude")
    monkeypatch.setenv("FAKE_CLI_LIMIT_FOR", "default")
    assert ask(app).status == "failed"


def test_reading_budget_treats_each_account_as_a_plan(app):
    from kurooto.core import readbudget

    ca.add(app, "work")
    assert readbudget.kind(providers.build(app, "claude:work")) == "plan"


# ------------------------------------------------------------------------------------------ what it says
def test_self_md_and_brain_name_each_account(app):
    ca.add(app, "work")
    for b in ("claude", "claude:work"):
        providers.build(app, b).mark_worked(app)
    app.settings.set("brain.main", "claude")
    until = time.time() + 3600
    fallback.cool(app, "claude:work", providers.Result(providers.Verdict.RATE_LIMITED, retry_after_s=3600))
    text = selfdoc.refresh(app)
    assert "Claude Code (work) [claude:work]" in text and "Claude accounts: Claude Code [claude]" in text
    assert "at its limit, skipped until" in text and str(ca.folder(app, "work")) not in text
    assert fallback.cooling(app, "claude:work") >= until - 5
    out = app.modules["chat"]._brain(None, "")
    assert "Claude accounts: Claude Code, Claude Code (work)" in out and "Claude Code (work) is at its limit" in out


def test_the_receipt_names_the_account():
    from kurooto.core import jobs as jobs_mod

    b = ClaudeCode(exe="claude", account="work", name="Work")
    line = jobs_mod.receipt(b, "high", 42, None, [], model="claude-opus-4-5-20251101")
    assert line == "Claude Code (Work) · opus-4.5 · high · 42 s · did nothing through Kurooto"


# ------------------------------------------------------------------------------------- setup page, Settings
def test_setup_adds_signs_in_tests_renames_and_removes(app, fakes, monkeypatch):
    from kurooto.web.api import Api

    api = Api(app)
    opened = []
    monkeypatch.setattr(api.prereqs, "open_signin", lambda key, env=None: opened.append((key, env)) or (True, "ok"))
    code, r = api.post("brain/claude-accounts/add", {"name": "work"})
    assert code == 200 and r["ok"] and r["id"] == "claude:work"
    assert opened == [("claude", {"CLAUDE_CONFIG_DIR": str(ca.folder(app, "work"))})]  # its own sign-in window
    code, st = api.get("state")
    assert st["claude_accounts"][0]["id"] == "claude:work" and "Anthropic's terms" in st["claude_terms"]
    monkeypatch.setenv("FAKE_CLI_MODE", "ok")
    app.settings.set("brain.main", "agy")
    code, t = api.post("brain/test", {"which": "claude:work"})
    assert t["ok"] and app.settings.get("brain.main") == "agy"  # testing it doesn't make it your main AI
    assert ca.rows(app)[0]["working"]
    code, r = api.post("brain/claude-accounts/rename", {"work": "Day job"})  # Settings' box
    assert r["ok"] and providers.label("claude:work") == "Claude Code (Day job)"
    code, r = api.post("brain/claude-accounts/signin", {"id": "claude:work"})
    assert r["ok"] and len(opened) == 2
    # Settings: its own section; brain.main and brain.fallback offer it
    secs = {s["section"]: s for s in api._settings()["sections"]}
    assert secs["claude_accounts"]["values"]["work"] == "Day job" and secs["claude_accounts"]["remove"]
    assert "claude_accounts" not in secs["brain"]["values"]
    assert ["claude:work", "Claude Code (Day job)"] in secs["brain"]["choices"]["main"]
    assert api.post("brain", {"main": "claude:work"})[0] == 200 and app.settings.get("brain.main") == "claude:work"
    app.settings.set("brain.fallback", ["claude:work", "agy"])
    # removing: only after a yes, and only Kurooto's folder
    code, r = api.post("brain/claude-accounts/remove", {"id": "claude:work"})
    assert code == 400 and ca.folder(app, "work").is_dir()
    code, r = api.post("brain/claude-accounts/remove", {"id": "claude:work", "yes": True})
    assert r["ok"] and "It was your main AI" in r["message"]
    assert not ca.folder(app, "work").exists() and ca.accounts(app) == []
    assert app.settings.get("brain.main") == "" and app.settings.get("brain.fallback") == ["agy"]
    assert not (app.paths.state / "claude-work-worked.json").exists()
    assert api.post("brain/claude-accounts/remove", {"id": "claude:work", "yes": True})[0] == 400


@pytest.mark.skipif(sys.platform == "win32", reason="the Linux terminal path")
def test_the_sign_in_window_gets_the_accounts_folder(tmp_path, monkeypatch):
    import subprocess

    from kurooto.core import prereqs as pr

    exe = tmp_path / "claude"
    exe.write_text("#!/bin/sh\n")
    exe.chmod(0o755)
    p = pr.Prereqs(tmp_path, tmp_path, os="linux")
    monkeypatch.setattr(p.items["claude"], "find", lambda: str(exe))
    monkeypatch.setattr(pr.shutil, "which", lambda t: "/usr/bin/xterm" if t == "xterm" else None)
    started = []

    class P:
        pid = 999999

    monkeypatch.setattr(subprocess, "Popen", lambda args, **kw: started.append((args, kw)) or P())
    monkeypatch.setattr("kurooto.core.children.keep", lambda pid: None)
    ok, _ = p.open_signin("claude", env={"CLAUDE_CONFIG_DIR": "/k/data/claude-accounts/work"})
    args, kw = started[0]
    assert ok and args == ["xterm", "-e", "env", "CLAUDE_CONFIG_DIR=/k/data/claude-accounts/work", str(exe)]
    assert kw["env"]["CLAUDE_CONFIG_DIR"] == "/k/data/claude-accounts/work"
    p.open_signin("claude")  # the usual sign-in: as before
    assert started[1][0] == ["xterm", "-e", str(exe)] and started[1][1]["env"] is None


def test_backups_leave_the_sign_ins_out_unless_secrets(app):
    from kurooto.modules.backups import sources

    ca.add(app, "work")
    (ca.folder(app, "work") / ".credentials.json").write_text("{}")
    names = [n for n, _ in sources(app.paths, None, notes=False, secrets=False, index=False)]
    assert not any("claude-accounts" in n for n in names)
    names = [n for n, _ in sources(app.paths, None, notes=False, secrets=True, index=False)]
    assert "data/claude-accounts/work/.credentials.json" in names


# ------------------------------------------------------------------------------------------------- the CLI
def test_kurooto_ai_lists_adds_renames_and_removes(app, monkeypatch, capsys):
    from kurooto.cli import main

    monkeypatch.setattr("shutil.which", lambda name, *a, **k: None)  # no Claude Code: it says how to sign in later
    assert main(["ai", "accounts"]) == 0 and "No extra Claude accounts" in capsys.readouterr().out
    assert main(["ai", "add-claude", "lab"]) == 0
    out = capsys.readouterr().out
    assert "Added Claude Code (lab) (its id: claude:lab)" in out and "Anthropic's terms" in out
    assert main(["ai", "rename-claude", "lab", "Lab two"]) == 0
    assert main(["ai", "accounts"]) == 0 and "claude:lab" in capsys.readouterr().out
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    assert main(["ai", "remove-claude", "lab"]) == 1 and ca.folder(app, "lab").is_dir()  # no yes, no removal
    assert main(["ai", "remove-claude", "Lab two", "--yes"]) == 0 and not ca.folder(app, "lab").exists()
    assert main(["ai", "remove-claude", "lab", "--yes"]) == 1

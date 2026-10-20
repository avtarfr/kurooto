"""0.1.2: agy can't use tools unattended. Text-only work tells it so; when agy (or another agent program) can't do a
request, a saved Gemini key answers instead, and the other way round when agy has worked here before."""

import sys
from pathlib import Path

import pytest

import kurooto.providers as providers
from kurooto.app import App
from kurooto.core.jobs import DENIED_HELP
from kurooto.providers import agy as agy_mod
from kurooto.providers import openai_compat
from kurooto.providers.agy import Agy, has_worked, mark_worked
from kurooto.providers.base import TEXT_ONLY, Task, Verdict
from kurooto.web.api import Api
from tests.fakes.openai import FakeOpenAI

FAKE_AGY = [sys.executable, str(Path(__file__).parents[1] / "fakes" / "fake_agy.py")]


@pytest.fixture
def env(tmp_path, monkeypatch):
    """agy (a fake) as the main brain, and a fake Gemini service that a saved key would reach."""
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))  # agy's own settings (the setup test) stay in the sandbox
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    gem = FakeOpenAI(key="gem-key")
    gem.answer = "From Gemini."
    orig = providers.build
    monkeypatch.setattr(providers, "build", lambda a, w: Agy(exe=FAKE_AGY) if w == "agy" else orig(a, w))
    app = App()
    app.settings.set("brain.main", "agy")
    app.settings.set("brain.base_urls", {"gemini": gem.base})
    sent = []
    app.notifier.send = lambda text, **kw: sent.append(text)
    yield app, gem, sent, monkeypatch
    app.close()
    gem.close()


def run(app, prompt="what's due?", **kw):
    jid = app.jobs.submit(prompt, effort="low", **kw)
    app.jobs.run_next()
    return app.jobs.get(jid)


@pytest.mark.skip(reason="0.5.1 disabled agy rolling over to Gemini key to protect free-tier limits")
def test_agy_refuses_then_the_gemini_key_answers(env):
    app, gem, sent, mp = env
    mp.setenv("FAKE_AGY_MODE", "denied")
    app.secrets.set("gemini.api_key", gem.key)
    job = run(app)
    assert job.status == "ok" and job.brain == "gemini" and job.result == "From Gemini."
    assert sent[-1].endswith("From Gemini.\n\n(Answered with your Gemini key: agy couldn't do this unattended.)")


@pytest.mark.skip(reason="0.5.1 disabled agy rolling over to Gemini key to protect free-tier limits")
@pytest.mark.parametrize("mode", ["limit", "auth", "crash", "silent"])
def test_other_agy_failures_go_to_the_key_too(env, mode):
    app, gem, sent, mp = env
    mp.setenv("FAKE_AGY_MODE", mode)
    app.secrets.set("gemini.api_key", gem.key)
    job = run(app)
    assert job.brain == "gemini" and job.status == "ok" and "(Answered with your Gemini key: agy " in sent[-1]


def test_no_key_says_what_to_do(env):
    app, gem, sent, mp = env
    mp.setenv("FAKE_AGY_MODE", "denied")
    job = run(app)
    assert job.status == "failed" and job.verdict == "denied" and sent[-1].endswith(DENIED_HELP)
    assert gem.requests == []


@pytest.mark.skip(reason="0.5.1 disabled agy rolling over to Gemini key to protect free-tier limits")
def test_a_set_fallback_goes_first_and_no_brain_runs_twice(env):
    app, gem, sent, mp = env
    mp.setenv("FAKE_AGY_MODE", "denied")
    app.secrets.set("gemini.api_key", gem.key)
    other = FakeOpenAI(key="other")
    other.mode = "500"  # (a 429 would wait out its Retry-After once in the tool loop)
    try:
        app.secrets.set("custom.api_key", other.key)
        app.settings.set("brain.base_urls", {"gemini": gem.base, "custom": other.base})
        app.settings.set("brain.models", {"custom": {"low": "m", "medium": "m", "high": "m"}})
        app.settings.set("brain.fallback", "custom")
        job = run(app)
        assert job.brain == "gemini" and len(other.requests) == 1 and len(gem.requests) == 1
        app.settings.set("brain.fallback", "gemini")  # the fallback is the key itself: it's tried once
        gem.mode = "500"
        job = run(app)
        assert job.status == "failed" and len(gem.requests) == 2
    finally:
        other.close()


def test_no_fallback_on_timeout(env, monkeypatch):
    app, gem, sent, mp = env
    app.secrets.set("gemini.api_key", gem.key)
    mp.setenv("FAKE_AGY_MODE", "slow")
    monkeypatch.setattr(Agy, "grace_s", 0)
    app.settings.set("brain.timeout_min", {"low": 0, "medium": 0, "high": 0})
    job = run(app)
    assert job.verdict == "timeout" and gem.requests == []


def test_the_key_hands_over_to_agy_once_agy_has_worked(env):
    app, gem, sent, mp = env
    app.secrets.set("gemini.api_key", gem.key)
    app.settings.set("brain.main", "gemini")
    gem.mode = "429"
    mp.setattr(openai_compat.time, "sleep", lambda s: None)  # the tool loop's one wait for Retry-After
    mp.setenv("FAKE_AGY_MODE", "ok")
    job = run(app)  # agy never answered here: not used
    assert job.status == "failed" and job.brain == "gemini"
    mark_worked(app.paths.state)
    job = run(app, "and tomorrow?")
    assert job.status == "ok" and job.brain == "agy" and job.result.endswith("and tomorrow?")
    assert sent[-1].endswith("(Answered with agy: your Gemini key hit its limit.)")
    gem.mode = "401"
    run(app, "x")
    assert sent[-1].endswith("(Answered with agy: your Gemini key stopped working.)")


def test_text_only_work_tells_agy_to_use_no_tools(env):
    app, gem, sent, mp = env
    mp.setenv("FAKE_AGY_MODE", "prompt")
    job = run(app, "summarise this", text_only=True, quiet=True)
    assert job.result.startswith(TEXT_ONLY)
    assert not run(app, "file my notes", quiet=True).result.startswith(TEXT_ONLY)  # tool work stays as it was
    assert Agy(exe=FAKE_AGY).complete("hi").text.startswith(TEXT_ONLY)  # quick checks and the nightly look back
    app.settings.set("brain.main", "gemini")  # agy as the stand-in carries it too
    app.secrets.set("gemini.api_key", gem.key)
    gem.mode = "500"
    mark_worked(app.paths.state)
    job = run(app, "summarise again", text_only=True, quiet=True)
    assert job.brain == "agy" and job.result.startswith(TEXT_ONLY)


@pytest.mark.skip(reason="0.5.1 disabled agy rolling over to Gemini key to protect free-tier limits")
def test_profile_build_is_text_only_and_says_who_answered(env):
    app, gem, sent, mp = env
    mp.setenv("FAKE_AGY_MODE", "denied")
    app.secrets.set("gemini.api_key", gem.key)
    gem.answer = "## In brief\nLikes maths.\n\n## Details\nMore."
    app.about.add("ChatGPT", "x" * 300)
    app.about.merge()
    row = app.jobs._db.execute("select text_only from jobs order by created desc limit 1").fetchone()
    assert row[0] == 1
    app.jobs.run_next()
    profile = app.about.profile_file.read_text(encoding="utf-8")
    assert "Likes maths." in profile and "Answered with" not in profile  # the note isn't written into the profile
    assert sent[-1].endswith("(Answered with your Gemini key: agy couldn't do this unattended.)")


def test_a_successful_agy_run_or_test_is_remembered(env):
    app, gem, sent, mp = env
    mp.setenv("FAKE_AGY_MODE", "ok")
    assert not has_worked(app.paths.state)
    run(app)
    assert has_worked(app.paths.state)
    agy_mod.worked_file(app.paths.state).unlink()
    assert Api(app).post("brain/test", {"which": "agy"})[1]["ok"] and has_worked(app.paths.state)


def test_long_prompts_go_through_a_file(tmp_path, monkeypatch):
    monkeypatch.setattr(agy_mod, "ARG_LIMIT", 100)
    monkeypatch.setenv("FAKE_AGY_MODE", "prompt")
    ws = tmp_path / "notes"
    ws.mkdir()
    r = Agy(exe=FAKE_AGY).run(Task(prompt="x" * 500, cwd=ws, timeout_s=60, text_only=True))
    assert r.verdict == Verdict.OK and len(r.text) < 300 and "Read that one file" in r.text
    name = r.text.split("the file ")[1].split(" ")[0]
    req = ws / ".kurooto" / "requests"
    assert name.startswith(".kurooto/requests/") and not (ws / name).exists()  # removed after the run
    assert (req / ".gitignore").read_text(encoding="utf-8") == "*\n"
    short = Agy(exe=FAKE_AGY).run(Task(prompt="short", cwd=ws, timeout_s=60))
    assert short.text == "short"


def test_the_wizard_recommends_the_gemini_key(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    app = App()
    try:
        rows = Api(app)._brains()
        assert [(r["id"], r["recommended"]) for r in rows[:2]] == [("agy", True), ("gemini", False)]
        assert sum(r["recommended"] for r in rows) == 1
    finally:
        app.close()
    from importlib import resources

    js = resources.files("kurooto.web").joinpath("static", "setup.js").read_text(encoding="utf-8")
    assert "AGY_NOTE" in js and "GEMINI_TERMS" in js and "18 or older" in js


def test_text_only_jobs_get_no_tools(env):
    app, gem, sent, mp = env
    seen = []

    class Spy:
        id, label, kind = "spy", "Spy", "api"

        def available(self):
            return True, ""

        def run(self, task):
            from kurooto.providers.base import Result

            seen.append(task)
            return Result(Verdict.OK, "fine")

    orig = providers.build
    mp.setattr(providers, "build", lambda a, w: Spy() if w == "spy" else orig(a, w))
    app.settings.set("brain.main", "spy")
    run(app, "summarise", text_only=True, quiet=True)
    run(app, "file it", quiet=True)
    assert seen[0].text_only and seen[0].tools == [] and seen[0].mcp is None
    assert not seen[1].text_only and seen[1].tools and seen[1].mcp

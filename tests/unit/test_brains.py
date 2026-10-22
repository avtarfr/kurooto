import os
import sys
from pathlib import Path

import pytest

from kurooto.providers import effort
from kurooto.providers.agy import Agy, clean
from kurooto.providers.base import Task, Verdict
from kurooto.providers.openai_compat import OpenAICompat
from tests.fakes.openai import FakeOpenAI

FAKE_AGY = [sys.executable, str(Path(__file__).parents[1] / "fakes" / "fake_agy.py")]


@pytest.fixture
def api():
    f = FakeOpenAI()
    yield f
    f.close()


@pytest.mark.parametrize(
    "mode,verdict",
    [
        ("ok", Verdict.OK),
        ("denied", Verdict.DENIED),
        ("limit", Verdict.RATE_LIMITED),
        ("auth", Verdict.AUTH),
        ("signed-out", Verdict.AUTH),
        ("silent", Verdict.EMPTY),
        ("crash", Verdict.ERROR),
    ],
)
def test_agy_verdicts(mode, verdict, monkeypatch):
    monkeypatch.setenv("FAKE_AGY_MODE", mode)
    r = Agy(exe=FAKE_AGY).run(Task(prompt="what's due?", effort="high", timeout_s=60))
    assert r.verdict == verdict, r
    if mode == "ok":
        assert r.text == "answer from gemini-3.8-flash-high: what's due?"


def test_agy_timeout_kills_it(monkeypatch):
    monkeypatch.setenv("FAKE_AGY_MODE", "slow")
    a = Agy(exe=FAKE_AGY)
    a.grace_s = 0
    r = a.run(Task(prompt="x", timeout_s=2))
    assert r.verdict == Verdict.TIMEOUT and r.seconds < 30


@pytest.mark.skipif(
    os.name == "nt", reason="the POSIX pseudo-terminal path; ConPTY is exercised on Windows CI separately"
)
def test_agy_through_a_pseudo_terminal(monkeypatch):
    monkeypatch.setenv("FAKE_AGY_MODE", "ok")
    r = Agy(exe=FAKE_AGY, io_mode="pty").run(Task(prompt="hello there", effort="low", timeout_s=60))
    assert r.verdict == Verdict.OK and r.text.endswith("hello there")


def test_ansi_is_cleaned():
    assert clean("\x1b[1;32mDone\x1b[0m\r\n\x1b]0;title\x07ok") == "Done\nok"


def test_missing_agy():
    a = Agy(exe=None)
    a.exe = None
    assert a.available() == (False, "agy isn't installed")


def test_openai_compat_answers_and_failures(api):
    b = OpenAICompat("custom", api.key, base_url=api.base, models={"low": "fast", "medium": "smart", "high": "smart"})
    assert b.available() == (True, "")
    r = b.run(Task(prompt="capital of France?", effort="low", context="be brief"))
    assert r.verdict == Verdict.OK and r.text == "Paris." and api.requests[-1]["model"] == "fast"
    assert api.requests[-1]["messages"][0] == {"role": "system", "content": "be brief"}
    for mode, v in (
        ("429", Verdict.RATE_LIMITED),
        ("401", Verdict.AUTH),
        ("empty", Verdict.EMPTY),
        ("500", Verdict.ERROR),
    ):
        api.mode = mode
        assert b.complete("x").verdict == v, mode
    api.mode = "429"
    assert b.complete("x").retry_after_s == 30
    api.mode = "ok"
    assert b.list_models() == ["fast", "smart"]


def test_gemini_preset_sends_reasoning_effort(api):
    b = OpenAICompat("gemini", api.key, base_url=api.base)
    b.run(Task(prompt="derive it", effort="high"))
    assert api.requests[-1]["reasoning_effort"] == "high" and api.requests[-1]["model"] == "gemini-flash-latest"


def test_unreachable_service_is_an_error():
    b = OpenAICompat("custom", "k", base_url="http://127.0.0.1:9/v1", models={"medium": "m"})
    assert b.complete("x", timeout=3).verdict in (Verdict.ERROR, Verdict.TIMEOUT)


@pytest.mark.parametrize(
    "prompt,want",
    [
        ("high: what's due", "high"),
        ("low: explain this proof", "low"),
        ("make revision notes for chapter 3", "high"),
        ("what's due tomorrow", "medium"),
    ],
)
def test_effort_rules(prompt, want):
    assert effort.pick(prompt) == want


def test_effort_classifier_and_guard():
    assert effort.pick("what's due", lambda q: "Low.") == "low"
    assert effort.pick("remind me to add the assignment", lambda q: "low") == "medium"
    assert effort.pick("compare these two theorems", lambda q: "I think HIGH") == "high"
    assert effort.pick("anything", lambda q: (_ for _ in ()).throw(RuntimeError())) == "medium"


FAKE_CLI = [sys.executable, str(Path(__file__).parents[1] / "fakes" / "fake_cli.py")]


@pytest.mark.parametrize("mode,verdict", [("ok", Verdict.OK), ("limit", Verdict.RATE_LIMITED), ("auth", Verdict.AUTH)])
def test_claude_code(mode, verdict, monkeypatch, tmp_path):
    from kurooto.providers.claude import ClaudeCode

    monkeypatch.setenv("FAKE_CLI_MODE", mode)
    r = ClaudeCode(exe=FAKE_CLI).run(Task(prompt="say hi", cwd=tmp_path, timeout_s=60))
    assert r.verdict == verdict
    if mode == "ok":
        assert r.text == "claude says: say hi"


def test_a_retired_ai_is_cleared_from_the_settings_not_left_as_the_main_one(tmp_path, monkeypatch):
    from kurooto import providers
    from kurooto.app import App

    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    app = App()
    try:
        app.settings.set("brain.main", "codex")
        app.settings.set("brain.fallback", "agy")
        assert providers.drop_retired(app) == ["codex"]
        assert app.settings.get("brain.main") == "" and app.settings.get("brain.fallback") == "agy"
        assert providers.build(app, "codex") is None and "codex" not in providers.CHOICES
    finally:
        app.close()


def test_a_gemini_key_tries_the_next_model_of_the_family_when_one_is_used_up():
    from kurooto.providers.openai_compat import OpenAICompat
    from tests.fakes.openai import FakeOpenAI

    fake = FakeOpenAI()
    try:
        fake.mode_by_model = {"gemini-flash-latest": "429", "gemini-flash-lite-latest": "429"}
        fake.answer = "from the third model"
        b = OpenAICompat("gemini", fake.key, base_url=fake.base)
        r = b.complete("hello", effort="medium", timeout=20)
        assert r.ok and r.text == "from the third model"
        assert [q["model"] for q in fake.requests] == [
            "gemini-flash-latest",
            "gemini-flash-lite-latest",
            "gemini-2.5-flash",
        ]
        assert "gemini-2.5-flash" in r.usage["note"] and "gemini-flash-latest" in r.usage["note"]
        b.alternatives = ["gemini-flash-latest"]  # nothing left to try: the first model's limit message stays
        fake.mode_by_model = {}
        fake.mode = "429"
        assert b.complete("hi", effort="medium", timeout=20).verdict == Verdict.RATE_LIMITED
    finally:
        fake.close()


def test_other_brains_do_not_switch_models_on_a_limit():
    from kurooto.providers.openai_compat import OpenAICompat

    assert OpenAICompat("custom", "k", base_url="http://x/v1").alternatives == []
    assert OpenAICompat("ollama", "k").alternatives == []

"""The terms review: FreeLLMAPI isn't offered any more (one set up earlier keeps working, shown as custom), and the
setup page says plainly what a free Gemini key and agy mean."""

import json
import re
from importlib import resources

import pytest

from kurooto import providers
from kurooto.app import App
from kurooto.core.prereqs import Prereqs
from kurooto.providers.base import Verdict
from kurooto.web.api import Api
from tests.fakes.openai import FakeOpenAI

SETUP = resources.files("kurooto.web").joinpath("static", "setup.js").read_text(encoding="utf-8")


def js_const(name: str) -> str:
    """A string constant of setup.js, its "..." + "..." parts joined."""
    body = re.search(rf"const {name} = (.*?);\n", SETUP, re.S).group(1)
    return "".join(json.loads(m) for m in re.findall(r'"(?:[^"\\]|\\.)*"', body))


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    a = App()
    yield a
    a.close()


def test_freellmapi_is_not_offered(app):
    ids = [b["id"] for b in Api(app)._brains()]
    assert "freellmapi" not in ids and "custom" in ids and ids[:2] == ["agy", "gemini"]
    assert "freellmapi" not in Prereqs(app.paths.app, app.paths.cache).items
    assert "FreeLLMAPI" not in SETUP and "freellmapi.com" not in SETUP


def test_a_freellmapi_brain_set_up_earlier_keeps_working_as_custom(app):
    ai = FakeOpenAI()
    try:
        app.secrets.set("freellmapi.api_key", ai.key)
        app.settings.set("brain.base_urls", {"freellmapi": ai.base})
        app.settings.set("brain.models", {"freellmapi": {"low": "m", "medium": "m", "high": "m"}})
        app.settings.set("brain.main", "freellmapi")
        b = providers.build(app, "freellmapi")
        assert b.label == "Another OpenAI-compatible service" and b.available() == (True, "")
        assert b.complete("capital of France?").verdict == Verdict.OK
        rows = {r["id"]: r for r in Api(app)._brains()}
        assert rows["freellmapi"]["label"] == "Another OpenAI-compatible service" and rows["freellmapi"]["ready"]
        assert not rows["freellmapi"]["recommended"]
        assert Api(app).post("brain", {"main": "freellmapi"})[1]["ok"]  # the wizard re-saving it is fine
        assert providers.CHOICES["freellmapi"] == providers.CHOICES["custom"]
    finally:
        ai.close()


def test_the_wizard_says_what_a_free_gemini_key_means():
    for words in (
        "improve its products",
        "human reviewers may read it",
        "18 or older",
        "the EEA, the UK and Switzerland you need a paid key",
        "Phone calls and voice notes always go through Gemini",
        "If you don't want that, use a paid key.",
    ):
        assert words in js_const("GEMINI_TERMS"), words
    assert SETUP.count("geminiTerms()") == 3  # defined once, shown on the brain card and the key box


def test_gemini_is_recommended_and_agy_keeps_its_honest_note(app):
    note = js_const("AGY_NOTE")
    assert "never touches its sign-in token" in note and "some risk to your Google account" in note
    assert "Google recommends a Gemini API key" in note
    assert SETUP.count("AGY_NOTE") == 2
    rows = Api(app)._brains()
    assert [(r["id"], r["recommended"]) for r in rows[:2]] == [("agy", True), ("gemini", False)]
    assert [r["id"] for r in rows] == ["agy", "gemini", "codex", "claude", "ollama", "custom"]
    assert sum(r["recommended"] for r in rows) == 1

"""Quick win 4: the try-it box on the setup page. Once the AI answers, what's typed there goes through the same handler
as a Telegram message, before Telegram is set up; answers come back to the page only."""

from __future__ import annotations

from pathlib import Path

import pytest

from kurooto.app import App
from kurooto.web.api import Api
from tests.fakes.openai import FakeOpenAI


def with_ai(app, ai):
    app.secrets.set("custom.api_key", ai.key)
    app.settings.set("brain.base_urls", {"custom": ai.base})
    app.settings.set("brain.models", {"custom": {"low": "fast", "medium": "smart", "high": "smart"}})
    app.settings.set("brain.main", "custom")


@pytest.fixture
def fresh(tmp_path, monkeypatch):
    """A new install at the setup page's AI step: an AI that works, nothing turned on, no Telegram."""
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    ai = FakeOpenAI()
    app = App()
    with_ai(app, ai)
    yield app, Api(app), ai
    ai.close()
    app.close()


def test_a_reminder_works_before_telegram(fresh, monkeypatch):
    from kurooto.core import notify

    app, api, _ = fresh
    assert app.enabled() == []
    code, r = api.post("tryit", {"text": "remind me in 2 minutes to stretch"})
    assert code == 200 and r["job"] is None
    assert r["replies"][0].startswith("I'll remind you") and r["replies"][0].endswith("stretch")
    jobs = app.scheduler.jobs("reminders:")
    assert len(jobs) == 1 and not app.is_on("reminders")  # it answered without being turned on
    shown = []
    monkeypatch.setattr(notify.desktop, "notify", lambda title, text, urgent=False: shown.append(text))
    app.scheduler.actions["reminders.fire"](jobs[0].payload)
    assert shown == ["Reminder: stretch"]  # no Telegram yet: it pops up on this computer
    app2 = App()  # Kurooto restarted before the reminder was due, Reminders still off: it still fires
    try:
        assert "reminders.fire" in app2.scheduler.actions and not app2.is_on("reminders")
    finally:
        app2.close()


def test_a_question_goes_to_the_ai_and_comes_back_to_the_page(fresh):
    app, api, ai = fresh
    code, r = api.post("tryit", {"text": "what's the capital of France?"})
    assert code == 200 and r["replies"] == [] and r["job"]
    assert app.jobs.run_next() == r["job"]
    code, j = api.get("job", {"id": r["job"]})
    assert j["status"] == "ok" and j["answer"].endswith("Paris.")
    assert not app.is_on("chat")


def test_other_features_answer_only_when_on(fresh):
    app, api, _ = fresh
    code, r = api.post("tryit", {"text": "I have problem set 3 due fri 17:00"})
    assert r["job"]  # Deadlines is off: the AI gets it, as on Telegram
    assert (
        not (app.paths.state / "deadlines.json").exists()
        or "problem set" not in (app.paths.state / "deadlines.json").read_text()
    )


def test_it_needs_a_working_ai_and_some_text(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    app = App()
    try:
        api = Api(app)
        code, r = api.post("tryit", {"text": "hello"})
        assert code == 409 and "test it first" in r["error"]
        ai = FakeOpenAI()
        with_ai(app, ai)
        assert api.post("tryit", {"text": "   "})[0] == 400
        ai.close()
    finally:
        app.close()


def test_with_telegram_on_nothing_from_the_box_goes_there(env):
    ai = FakeOpenAI()
    try:
        with_ai(env.app, ai)
        env.on("chat")
        before = len(env.fake.texts())
        code, r = Api(env.app).post("tryit", {"text": "what's the capital of France?"})
        assert env.app.jobs.run_next() == r["job"]
        assert len(env.fake.texts()) == before  # the answer is for the page only
        assert env.say("/help").startswith("Kurooto, your assistant")  # Telegram itself is unchanged
    finally:
        ai.close()


def test_the_setup_page_shows_the_box_once_the_ai_works():
    js = (Path(__file__).resolve().parents[2] / "src/kurooto/web/static/setup.js").read_text(encoding="utf-8")
    assert "if (brain.ready) box.append(tryBox());" in js and 'api("tryit", { text })' in js
    assert "job?id=" in js

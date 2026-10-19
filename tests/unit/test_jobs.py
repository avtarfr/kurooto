import pytest

from kurooto.app import App
from tests.fakes.openai import FakeOpenAI
from tests.fakes.telegram import FakeTelegram


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    tg_fake, ai = FakeTelegram(), FakeOpenAI()
    app = App()
    app.settings.set("telegram.api_base", tg_fake.base)
    tg = app.modules["telegram"]
    link = tg.pair_start(tg_fake.token)
    tg_fake.message(f"/start {link['code']}")
    tg.pair_poll(wait=0)
    app.enable("telegram")
    app.secrets.set("custom.api_key", ai.key)
    app.settings.set("brain.base_urls", {"custom": ai.base})
    app.settings.set("brain.models", {"custom": {"low": "fast", "medium": "smart", "high": "smart"}})
    app.settings.set("brain.main", "custom")
    yield app, tg, tg_fake, ai
    tg_fake.close()
    ai.close()
    app.close()


def test_chat_needs_a_brain(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    app = App()
    try:
        assert app.enable("chat") == (False, "pick an AI brain first")
    finally:
        app.close()


def test_question_to_answer_on_telegram(env):
    app, tg, fake, ai = env
    assert app.enable("chat") == (True, "Chat with your AI is on")
    tg._update(tg.api(), {"update_id": 50, "message": fake.message("what's the capital of France?")}, {7})
    assert fake.texts()[-1] == "On it."
    assert app.jobs.run_next() is not None
    answer = fake.texts()[-1]
    assert answer.startswith("[Another OpenAI-compatible service · medium] what's the capital") and answer.endswith(
        "Paris."
    )
    sent = [p for m, p in fake.sent if m == "sendMessage"][-1]
    assert sent["reply_parameters"]["message_id"]  # it answers the question it was asked
    assert "running unattended" in ai.requests[-1]["messages"][0]["content"]


def test_fallback_on_rate_limit_and_one_warning(env):
    app, tg, fake, ai = env
    fb = FakeOpenAI(key="sk-other")
    try:
        app.secrets.set("ollama.api_key", fb.key)
        app.settings.set("brain.base_urls", {"custom": ai.base, "ollama": fb.base})
        app.settings.set("brain.models", {"custom": {"medium": "smart"}, "ollama": {"medium": "qwen3:4b"}})
        app.settings.set("brain.fallback", "ollama")
        ai.mode, fb.answer = "429", "from the fallback"
        for _ in range(2):
            app.jobs.submit("hello")
            app.jobs.run_next()
        texts = fake.texts()
        assert sum("usage limit" in t for t in texts) == 1  # told once, not every time
        assert texts[-1].endswith("from the fallback") and "Ollama on this computer" in texts[-1]
    finally:
        fb.close()


def test_failures_are_explained_not_dumped(env):
    app, tg, fake, ai = env
    ai.mode = "401"
    app.jobs.submit("hello")
    app.jobs.run_next()
    texts = fake.texts()
    assert any("isn't signed in any more" in t for t in texts)
    assert "invalid api key" not in " ".join(texts)
    job = app.jobs.recent(1)[0]
    assert job.status == "failed" and job.verdict == "auth"


def test_long_answers_come_as_a_document(env):
    app, tg, fake, ai = env
    ai.answer = "word " * 3000
    app.jobs.submit("write a lot", effort="high")
    app.jobs.run_next()
    assert any(m == "sendDocument" for m, p in fake.sent)
    assert "[…the full answer is attached]" in fake.texts()[-1]


def test_interrupted_jobs_run_again_after_restart(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    app = App()
    jid = app.jobs.submit("x")
    assert app.jobs._claim() == jid  # it was running when the computer shut down
    app.close()
    app2 = App()
    try:
        assert app2.jobs.get(jid).status == "queued"
    finally:
        app2.close()

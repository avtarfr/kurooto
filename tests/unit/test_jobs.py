import asyncio
import os

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
    app.jobs._db.execute("update jobs set runner=? where id=?", (f"{os.getpid()}:1.00", jid))  # that process is gone
    app.close()
    app2 = App()
    try:
        assert app2.jobs.get(jid).status == "running"  # opening the queue changes nothing
        stop = asyncio.Event()
        stop.set()
        asyncio.run(app2.jobs.worker(stop))  # the daemon's worker starts: it runs again
        assert app2.jobs.get(jid).status == "queued"
    finally:
        app2.close()


def test_doctor_leaves_a_running_job_alone(tmp_path, monkeypatch, capsys):
    from kurooto import cli

    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    app = App()  # the daemon, in the middle of a request
    try:
        jid = app.jobs.submit("a long request")
        assert app.jobs._claim() == jid
        cli.doctor(as_json=True)  # builds its own App while the job runs
        other = App()
        assert other.jobs.recover() == 0  # even a second worker leaves a live runner's job alone
        other.close()
        assert app.jobs.get(jid).status == "running"
        app.jobs._db.execute("update jobs set runner=NULL where id=?", (jid,))  # from before runners were noted
        assert app.jobs.recover() == 1 and app.jobs.get(jid).status == "queued"
    finally:
        app.close()


def test_reads_from_other_threads_never_lose_a_job(tmp_path, monkeypatch):
    """The web page polls jobs (About you, /jobs) while the worker runs them, on one shared connection."""
    import threading

    from kurooto import providers
    from kurooto.providers.base import Result, Verdict

    class Quick:
        id, label, kind = "quick", "Quick", "api"

        def available(self):
            return True, ""

        def run(self, task):
            return Result(Verdict.OK, "done")

    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    monkeypatch.setattr(providers, "build", lambda a, w: Quick() if w == "quick" else None)
    app = App()
    try:
        app.settings.set("brain.main", "quick")
        ids = [app.jobs.submit(f"job {i}", quiet=True, effort="low") for i in range(40)]
        stop, missing = threading.Event(), []

        def poll():
            while not stop.is_set():
                for jid in ids:
                    if app.jobs.get(jid) is None:
                        missing.append(jid)
                app.jobs.recent(20)

        threads = [threading.Thread(target=poll) for _ in range(4)]
        for t in threads:
            t.start()
        try:
            while app.jobs.run_next():
                pass
        finally:
            stop.set()
            for t in threads:
                t.join()
        assert missing == [] and all(app.jobs.get(j).status == "ok" for j in ids)
    finally:
        app.close()

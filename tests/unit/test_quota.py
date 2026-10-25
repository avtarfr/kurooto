"""Free-tier reserve (core/quota.py): limits learned from 429s, background work waiting past the reserve and running
after the reset, your own requests first, the model here as the fallback, and the plain line."""

import datetime as dt
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

import pytest

import kurooto.providers as providers
from kurooto.app import App
from kurooto.core.quota import daily, day_end, hints
from kurooto.providers.agy import log_requests_since
from kurooto.providers.base import Brain, Result, Task, Verdict
from kurooto.providers.effort import QUESTION
from tests.fakes.openai import FakeOpenAI

T = dt.datetime(2026, 10, 20, 10, 0, tzinfo=dt.UTC).timestamp()  # 03:00 in California: Google's day is young
FLASH, LITE = "gemini:flash", "gemini:lite"


def google_429(per="Day", value="250", model="gemini-2.5-flash", wrap=True):
    """What Google's Gemini API answers when a free limit is reached (the OpenAI-compatible endpoint wraps it in a
    list)."""
    err = {
        "error": {
            "code": 429,
            "message": "You exceeded your current quota, please check your plan and billing details.\n* Quota "
            "exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, "
            f"limit: {value}, model: {model}\nPlease retry in 39.2s.",
            "status": "RESOURCE_EXHAUSTED",
            "details": [
                {
                    "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                    "violations": [
                        {
                            "quotaMetric": "generativelanguage.googleapis.com/generate_content_free_tier_requests",
                            "quotaId": f"GenerateRequestsPer{per}PerProjectPerModel-FreeTier",
                            "quotaDimensions": {"location": "global", "model": model},
                            "quotaValue": value,
                        }
                    ],
                },
                {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "39s"},
            ],
        }
    }
    return [err] if wrap else err


class Clock:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t


class FakeBrain(Brain):
    """A brain that answers from a script (Results), counting each request like the real ones do."""

    kind = "api"

    def __init__(self, bid, *script):
        self.id, self.label = bid, f"Fake {bid}"
        self.models = {"low": "lite", "medium": "flash", "high": "flash"}
        self.script, self.calls = list(script), []

    def available(self):
        return True, ""

    def run(self, task: Task) -> Result:
        self.calls.append(task.prompt)
        r = self.script.pop(0) if self.script else Result(Verdict.OK, f"answer from {self.id}")
        self.metered(self.models.get(task.effort) or self.models["medium"], None if r.ok else r)
        return r

    def complete(self, prompt, system="", effort="low", timeout=60):
        return self.run(Task(prompt=prompt, effort=effort))


def limited(body=None):
    body = body if body is not None else google_429()
    return Result(Verdict.RATE_LIMITED, "", 0.1, json.dumps(body)[:500], usage={"limit": hints(json.dumps(body))})


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    brains = {"gemini": FakeBrain("gemini"), "ollama": FakeBrain("ollama")}
    orig = providers._build
    monkeypatch.setattr(providers, "_build", lambda a, w: brains[w] if w in brains else orig(a, w))
    app = App()
    clock = Clock(T)
    app.quota.clock = clock
    app.quota.log_folder = tmp_path / "no-agy-logs"
    app.power.current = "normal"  # background work runs now, on battery or not
    app.settings.set("brain.main", "gemini")
    sent = []
    app.notifier.send = lambda text, **kw: sent.append(text)
    yield SimpleNamespace(app=app, q=app.quota, gem=brains["gemini"], local=brains["ollama"], clock=clock, sent=sent)
    app.close()


def events(app, kind):
    f = app.paths.state / "events.jsonl"
    rows = [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines()] if f.exists() else []
    return [r for r in rows if r["kind"] == kind]


def used(q, pool, n):
    for _ in range(n):
        q.record(pool, "ok")


# ------------------------------------------------------------------------------------------ reading a 429
def test_hints_read_googles_answers():
    h = hints(json.dumps(google_429()), retry_after=30)
    assert (h["per"], h["limit"], h["model"]) == ("day", 250, "gemini-2.5-flash") and daily(h) is True
    h = hints(json.dumps(google_429(per="Minute", value="10", wrap=False)))
    assert (h["per"], h["limit"], h["retry_s"]) == ("minute", None, 39) and daily(h) is False
    h = hints("Error: quota exceeded. Your quota will reset after 3h 10m.")
    assert h["retry_s"] == 3 * 3600 + 600 and daily(h) is True
    h = hints("Usage limit reached; resets at 12:30 UTC.", at=T)
    assert h["reset_at"] == dt.datetime(2026, 10, 20, 12, 30, tzinfo=dt.UTC).timestamp() and daily(h) is True
    assert daily(hints("Error: RESOURCE_EXHAUSTED: quota exceeded")) is None  # it doesn't say: counted as the day's
    assert daily(hints("rate limited, please retry in 20s")) is False


# ------------------------------------------------------------------------------------------ learning
def test_learns_googles_number_and_the_reset(env):
    q = env.q
    used(q, FLASH, 5)
    q.record(FLASH, "rate_limited", json.dumps(google_429()))
    s = q.status(FLASH)
    end = day_end(FLASH, T)
    assert (s["used"], s["limit"], s["source"], s["until"]) == (5, 250, "google", end)
    assert dt.datetime.fromtimestamp(end, dt.UTC).hour == 7  # midnight in California is 07:00 UTC in October
    assert q.line(FLASH) == f"Google's free limit for today is used up, resets {q.when(end)}; reminders still work."
    assert events(env.app, "quota_limit")[-1]["limit"] == 250
    env.clock.t = end + 1  # Google's new day: the count starts again, the limit stays known
    s = q.status(FLASH)
    assert (s["used"], s["limit"], s["until"]) == (0, 250, None)


def test_learns_the_count_when_no_number_is_given_and_ignores_per_minute_limits(env):
    q = env.q
    used(q, FLASH, 12)
    q.record(FLASH, "rate_limited", json.dumps(google_429(per="Minute", value="10")))
    assert q.status(FLASH)["limit"] is None and not q.used_up(FLASH)  # a per-minute limit passes by itself
    q.record(FLASH, "rate_limited", "Quota exceeded for quota metric 'Requests' and limit 'Requests per day'")
    s = q.status(FLASH)
    assert (s["limit"], s["source"]) == (12, "count") and q.used_up(FLASH)


def test_an_answer_before_the_reset_unlearns_a_guess(env):
    q, pool = env.q, "custom:smart"
    used(q, pool, 3)
    q.record(pool, "rate_limited", "RESOURCE_EXHAUSTED")  # no hint: taken as the day's limit, reset estimated
    s = q.status(pool)
    assert s["limit"] == 3 and s["until_src"] == "estimate"
    assert q.line(pool, "My service").startswith(
        f"My service's limit for today is used up, resets {q.when(day_end(pool, T), about=True)}; "
    )
    q.record(pool, "rate_limited", "RESOURCE_EXHAUSTED")  # asked again while used up: nothing new learned
    q.record(pool, "ok")  # it answers again: that wasn't the day's limit
    s = q.status(pool)
    assert (s["limit"], s["until"], s["used"]) == (None, None, 4)
    assert events(env.app, "quota_back")


def test_your_own_number_wins(env):
    env.app.settings.set("quota.limits", {FLASH: 20})
    used(env.q, FLASH, 13)
    assert env.q.wait_until(FLASH) is None
    used(env.q, FLASH, 1)  # 14 of 20: the 70% reserve
    assert env.q.wait_until(FLASH) == day_end(FLASH, T)
    assert env.q.status(FLASH)["source"] == "setting"
    env.app.settings.set("quota.on", False)
    assert env.q.wait_until(FLASH) is None


def test_a_learned_limit_is_soft_and_a_tiny_count_never_replaces_it(env):
    q, pool = env.q, "custom:smart"
    used(q, pool, 400)
    q.record(pool, "rate_limited", "RESOURCE_EXHAUSTED")  # learned from the count: 400
    assert q.status(pool)["limit"] == 400
    env.clock.t = q.status(pool)["until"] + 1  # it comes back; the count starts again
    q.record(pool, "ok")
    used(q, pool, 3)
    q.record(pool, "rate_limited", "RESOURCE_EXHAUSTED")  # a hit with a tiny count: not the limit
    assert q.status(pool)["limit"] == 400
    env.clock.t = q.status(pool)["until"] + 1
    q.record(pool, "ok")
    used(q, pool, 300)  # 75% of a learned 400: a measure only, so background work doesn't wait
    assert q.wait_until(pool) is None
    assert "soft: only a measure" in q.text()
    env.app.settings.set("quota.soft", "off")  # the old reserve, if you want it
    assert q.wait_until(pool) is not None


# ------------------------------------------------------------------------------------------ the queue
def test_background_waits_past_the_reserve_and_runs_after_the_reset(env):
    app, q, gem = env.app, env.q, env.gem
    app.settings.set("quota.limits", {FLASH: 10})
    used(q, FLASH, 7)
    bg = app.jobs.submit("digest the class posts", effort="medium", background=True, quiet=True)
    fg = app.jobs.submit("what's due tomorrow?", effort="medium")
    assert app.jobs.run_next() == bg  # the older job comes first, and waits
    assert app.jobs.get(bg).status == "queued" and gem.calls == []
    assert app.jobs.run_next() == fg  # your own request still goes
    assert app.jobs.get(fg).status == "ok" and gem.calls == ["what's due tomorrow?"]
    assert app.jobs.run_next() is None and app.jobs.waiting() == 1
    assert events(app, "quota_reserve")[0]["pool"] == FLASH and events(app, "job_deferred")[0]["job"] == bg
    assert "1 background request waits for a reset." in q.text()
    env.clock.t = day_end(FLASH, T) + 61  # Google's new day
    assert app.jobs.run_next() == bg
    assert app.jobs.get(bg).status == "ok" and app.jobs.waiting() == 0
    assert q.status(FLASH)["used"] == 1


def test_a_used_up_limit_is_tried_last_and_said_plainly(env):
    app, q, gem, local = env.app, env.q, env.gem, env.local
    q.record(FLASH, "rate_limited", json.dumps(google_429()))
    app.settings.set("brain.models", {"ollama": {"low": "small", "medium": "small", "high": "small"}})
    app.settings.set("brain.fallback", "ollama")
    jid = app.jobs.submit("hello", effort="medium")
    app.jobs.run_next()
    assert app.jobs.get(jid).brain == "ollama" and gem.calls == [] and local.calls == ["hello"]
    app.settings.set("brain.fallback", "")  # no fallback: it's tried, and the answer is one plain line
    gem.script = [limited()]
    jid = app.jobs.submit("hello again", effort="medium")
    app.jobs.run_next()
    line = q.line(FLASH)
    assert app.jobs.get(jid).verdict == "rate_limited" and env.sent[-1].endswith(line)
    assert line.startswith("Google's free limit for today is used up, resets ")
    assert any(t.startswith("Google's free limit") for t in env.sent[:-1])  # the once-an-hour notice says it too


def test_background_moves_to_the_model_here_and_waits_when_it_cant(env):
    app, q, gem, local = env.app, env.q, env.gem, env.local
    app.settings.set("quota.limits", {FLASH: 10})
    app.settings.set("quota.local", "background")
    app.settings.set("brain.models", {"ollama": {"low": "small", "medium": "small", "high": "small"}})
    used(q, FLASH, 7)
    a = app.jobs.submit("rank these papers", effort="medium", background=True, quiet=True)
    app.jobs.run_next()
    assert app.jobs.get(a).brain == "ollama" and app.jobs.get(a).status == "ok" and gem.calls == []
    local.script = [Result(Verdict.ERROR, detail="connection refused")]
    b = app.jobs.submit("rank more papers", effort="medium", background=True, quiet=True)
    app.jobs.run_next()
    assert app.jobs.get(b).status == "queued" and app.jobs.waiting() == 1  # never dropped
    app.settings.set("quota.local", "quick")  # the default: background work waits instead of moving
    c = app.jobs.submit("and these", effort="medium", background=True, quiet=True)
    app.jobs.run_next()
    assert app.jobs.get(c).status == "queued" and local.calls == ["rank these papers", "rank more papers"]
    app.settings.set("quota.on", False)  # undo: what waited goes at once, on the AI you picked
    assert app.jobs.run_next() == b and app.jobs.run_next() == c and app.jobs.waiting() == 0
    assert gem.calls == ["rank more papers", "and these"]


def test_an_answer_again_brings_waiting_work_back(env):
    app, q = env.app, env.q
    used(q, FLASH, 4)
    q.record(FLASH, "rate_limited", "Error: RESOURCE_EXHAUSTED")  # no hint: the day's limit, about midnight
    bg = app.jobs.submit("weekly research digest", effort="medium", background=True, quiet=True)
    app.jobs.run_next()
    assert app.jobs.waiting() == 1
    fg = app.jobs.submit("quick question", effort="medium")
    app.jobs.run_next()  # it answers: the limit wasn't used up after all
    assert app.jobs.get(fg).status == "ok" and app.jobs.waiting() == 0
    assert app.jobs.run_next() == bg and app.jobs.get(bg).status == "ok"


def test_effort_picks_move_off_a_kept_limit(env):
    app, q, gem, local = env.app, env.q, env.gem, env.local
    app.settings.set("brain.classify", "main")
    app.settings.set("quota.limits", {LITE: 10})
    app.settings.set("brain.models", {"ollama": {"low": "small", "medium": "small", "high": "small"}})
    used(q, LITE, 7)
    local.script = [Result(Verdict.OK, "low")]
    jid = app.jobs.submit("when is the next linear-algebra class?")
    app.jobs.run_next()
    assert local.calls[0].startswith(QUESTION) and gem.calls == ["when is the next linear-algebra class?"]
    assert app.jobs.get(jid).effort == "low"
    app.settings.set("quota.local", "off")  # nothing moves: the rules pick
    app.jobs.submit("when is the next linear-algebra class?")
    app.jobs.run_next()
    assert len(local.calls) == 1 and app.jobs.recent(1)[0].effort == "medium"


def test_nightly_look_back_waits_for_the_reset(env):
    app, q, gem = env.app, env.q, env.gem
    app.settings.set("quota.limits", {FLASH: 10, LITE: 10})
    used(q, FLASH, 7)
    used(q, LITE, 7)
    retro = app.modules["retro"]
    assert retro.run(nightly=True) == 0 and gem.calls == []
    job = app.scheduler.get("retro:after-reset")
    assert job.action == "retro.after_reset" and job.next_run == pytest.approx(day_end(FLASH, T) + 60, abs=1)
    assert dt.datetime.fromisoformat(job.payload["since"]) < dt.datetime.now()
    retro.run()  # /lookback now: you asked, so it goes
    assert len(gem.calls) == 1


# ------------------------------------------------------------------------------------------ where it shows
def test_usage_shows_the_limits(env):
    app, q = env.app, env.q
    used(q, FLASH, 5)
    q.record(FLASH, "rate_limited", json.dumps(google_429()))
    used(q, LITE, 3)
    app.settings.set("quota.limits", {"gemini:pro": 50})
    text = q.text()
    assert f"Gemini key, flash: used up (5 requests), back {q.when(day_end(FLASH, T))}." in text
    assert "Gemini key, lite: 3 requests; the limit isn't known yet" in text
    assert "Gemini key, pro: 0 of 50 requests (0%, your setting); background work waits from 35." in text
    from kurooto.web import tools_api

    code, body = tools_api.get(app, "usage", {"days": "3"})
    assert code == 200 and {r["pool"] for r in body["quota"]} == {FLASH, LITE, "gemini:pro"}
    assert body["waiting"] == 0


def test_agy_logs_count_every_run(env, tmp_path):
    q = env.q
    logs = tmp_path / "agy-logs"
    logs.mkdir()
    (logs / "cli-20261019_2300.log").write_bytes(b"streamGenerateContent\n" * 9)
    os.utime(logs / "cli-20261019_2300.log", (T - 86400, T - 86400))  # yesterday's: not counted
    (logs / "cli-20261020_0300.log").write_bytes(b"POST streamGenerateContent\n" * 4)
    os.utime(logs / "cli-20261020_0300.log", (T, T))
    assert log_requests_since(T - 3600, logs) == 4 and log_requests_since(T, tmp_path / "none") is None
    q.log_folder = logs
    q.record("agy", "rate_limited", "Error: RESOURCE_EXHAUSTED: quota exceeded")
    s = q.status("agy")
    assert (s["used"], s["unit"], s["limit"], s["until_src"]) == (4, "agy-log", 4, "estimate")
    assert q.line("agy").startswith("agy's limit for today is used up, resets ") and " about " in q.line("agy")


# ------------------------------------------------------------------------------------------ real providers
def test_a_real_gemini_429_is_counted_learned_and_said(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    ai = FakeOpenAI(key="gem-key")
    app = App()
    try:
        app.secrets.set("gemini.api_key", ai.key)
        app.settings.set("brain.base_urls", {"gemini": ai.base})
        app.settings.set("brain.main", "gemini")
        sent = []
        app.notifier.send = lambda text, **kw: sent.append(text)
        app.jobs.submit("hello", effort="medium")
        app.jobs.run_next()
        pool = "gemini:gemini-flash-latest"
        assert app.quota.status(pool)["used"] == 1
        ai.mode, ai.limit_body = "429", google_429(value="20")
        app.jobs.submit("hello again", effort="medium")
        app.jobs.run_next()
        s = app.quota.status(pool)
        assert (s["limit"], s["source"], s["model"]) == (20, "google", "gemini-2.5-flash") and s["until"]
        assert sent[-1].endswith(app.quota.line(pool))
    finally:
        app.close()
        ai.close()


def test_a_voice_note_on_a_used_up_limit_says_it_plainly(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length") or 0))
            body = json.dumps(google_429(wrap=False)).encode()
            self.send_response(429)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    app = App()
    try:
        app.secrets.set("gemini.api_key", "k")
        app.settings.set("voice_notes.api_base", f"http://127.0.0.1:{server.server_address[1]}")
        note = tmp_path / "note.ogg"
        note.write_bytes(b"OggS")
        with pytest.raises(RuntimeError) as e:
            app.modules["voice_notes"].transcribe(note)
        assert str(e.value) == app.quota.line("gemini:gemini-flash-latest")
        assert str(e.value).startswith("Google's free limit for today is used up, resets ")
    finally:
        app.close()
        server.shutdown()
        server.server_close()

"""The offline helper (core/helper.py): a small model on this computer for quick decisions after a speed test, the
offer after two weeks, and the internet being down: quick things answered here, the rest waiting in the queue and
running when it's back, never dropped. Ollama and the network are fakes; no model is downloaded."""

from __future__ import annotations

import datetime as dt
import json
import re
import time
import urllib.error

import pytest

from kurooto.core import egress
from kurooto.core import helper as helper_mod
from kurooto.modules.base import Intent, Module
from kurooto.providers import effort
from tests.fakes.openai import FakeOpenAI

TAG = "qwen2.5:1.5b-instruct"


class FakeModel:
    """Stands in for Ollama's /api/generate: answers by a rule per prompt, records what it was asked."""

    def __init__(self):
        self.asked: list[str] = []
        self.rule = lambda prompt: "low"

    def __call__(self, prompt, tokens, timeout):
        self.asked.append(prompt)
        return self.rule(prompt)


def make_ready(app, monkeypatch, model: FakeModel | None = None) -> FakeModel:
    model = model or FakeModel()
    h = app.helper
    monkeypatch.setattr(h, "_generate", model)
    monkeypatch.setattr(app.modules["local_models"], "have", lambda: {TAG})
    app.settings.set("local_helper.on", True)
    h._update(test={"ok": True, "model": TAG, "at": time.time(), "seconds": 0.6})
    return model


def internet_down():
    for host in ("api.telegram.org", "generativelanguage.googleapis.com"):
        egress.seen(host, urllib.error.URLError(OSError("Temporary failure in name resolution")))


def internet_back():
    egress.seen("api.telegram.org")


@pytest.fixture
def remote(env, monkeypatch):
    """Chat on, with an AI out on the internet (a fake service; the helper is told it isn't on this computer)."""
    ai = FakeOpenAI()
    app = env.app
    app.secrets.set("custom.api_key", ai.key)
    app.settings.set("brain.base_urls", {"custom": ai.base})
    app.settings.set("brain.models", {"custom": {"low": "fast", "medium": "smart", "high": "smart"}})
    app.settings.set("brain.main", "custom")
    env.on("chat")
    monkeypatch.setattr(app.helper, "here", lambda brain: False)
    yield env, ai
    ai.close()


# ------------------------------------------------------------------------------------------- the model
def test_the_table_names_a_small_model_for_the_processor(env):
    m = env.app.helper.model()
    assert m["tag"] == TAG and m["size_gb"] < 1.5
    env.app.settings.set("local_helper.model", "gemma3:1b")
    assert env.app.helper.model()["tag"] == "gemma3:1b"


def test_speed_test_passes_fast_and_fails_slow(env, monkeypatch):
    h = env.app.helper
    model = FakeModel()
    model.rule = lambda p: "yes"
    monkeypatch.setattr(h, "_generate", model)
    ticks = iter([0.0, 0.7, 10.0, 10.9, 20.0, 20.8])
    monkeypatch.setattr(h, "timer", lambda: next(ticks))
    ok, secs = h.speed_test()
    assert ok and secs == pytest.approx(0.8) and len(model.asked) == 4  # a warm-up, then three timed
    assert h.state()["test"]["ok"] and h.state()["test"]["model"] == TAG
    ticks = iter([0.0, 3.0, 10.0, 12.5, 20.0, 23.0])
    monkeypatch.setattr(h, "timer", lambda: next(ticks))
    ok, secs = h.speed_test()
    assert not ok and secs == pytest.approx(3.0) and not h.tested()
    model.rule = lambda p: None  # no answer at all
    assert h.speed_test()[0] is False


def fake_ollama(app, monkeypatch, have=(), room_ok=True):
    lm = app.modules["local_models"]
    got = {"pulled": [], "removed": [], "have": set(have)}
    monkeypatch.setattr(lm.prereqs.items["ollama"], "find", lambda: "/x/ollama")
    monkeypatch.setattr(
        lm.prereqs,
        "room",
        lambda keys, extra_gb=0: {"ok": room_ok, "need_gb": extra_gb, "free_gb": 3.0, "margin_gb": 5},
    )
    monkeypatch.setattr(lm, "serve", lambda: True)
    monkeypatch.setattr(lm, "have", lambda: set(got["have"]))

    def pull(tag, size, progress=print, feature="", by=""):
        got["pulled"].append(tag)
        got["have"].add(tag)
        return True, ""

    def remove(tag):
        got["removed"].append(tag)
        got["have"].discard(tag)
        return True

    monkeypatch.setattr(lm, "pull", pull)
    monkeypatch.setattr(lm, "remove", remove)
    return got


def test_setup_turns_it_on_only_when_the_speed_test_passes(env, monkeypatch):
    app, h = env.app, env.app.helper
    got = fake_ollama(app, monkeypatch)
    monkeypatch.setattr(h, "speed_test", lambda: (True, 0.9))
    ok, said = h.setup(progress=lambda s: None)
    assert ok and got["pulled"] == [TAG] and app.settings.get("local_helper.on") is True
    assert "0.9 s" in said

    app.settings.set("local_helper.on", False)
    got["have"].clear()
    monkeypatch.setattr(h, "speed_test", lambda: (False, 3.2))
    ok, said = h.setup(progress=lambda s: None)
    assert not ok and "too slow" in said and "3.2 s" in said and "removed again" in said
    assert got["removed"] == [TAG] and app.settings.get("local_helper.on") is False

    got["have"].add(TAG)  # a model you had already is never removed
    ok, said = h.setup(progress=lambda s: None)
    assert not ok and got["removed"] == [TAG] and "removed" not in said


def test_setup_checks_the_space_first(env, monkeypatch):
    got = fake_ollama(env.app, monkeypatch, room_ok=False)
    ok, said = env.app.helper.setup(progress=lambda s: None)
    assert not ok and "Not enough space" in said and not got["pulled"]


# ------------------------------------------------------------------------------------- quick decisions
def test_not_ready_means_the_rules_decide(env):
    h = env.app.helper
    assert not h.ready() and h.classifier() is None and h.pick("x", [{"score": 1, "means": "x"}]) is None
    assert env.app.jobs._classifier(None) is None


def test_effort_goes_to_the_helper_where_the_rules_would_decide(env, monkeypatch):
    model = make_ready(env.app, monkeypatch)
    model.rule = lambda p: "High."
    classify = env.app.jobs._classifier(None)
    assert classify is not None and effort.pick("compare the two proofs", classify) == "high"
    model.rule = lambda p: "low"
    assert effort.pick("remind me to call the bank", classify) == "medium"  # an action is never a quick lookup
    model.rule = lambda p: None  # slow or failed: the rules
    assert effort.pick("what is a group", classify) == "medium"


def test_yes_no_reads_short_replies_only(env, monkeypatch):
    model = make_ready(env.app, monkeypatch)
    h = env.app.helper
    model.rule = lambda p: "yes"
    assert h.yes_no("Still true?", "yeah, still is") is True
    model.rule = lambda p: "no"
    assert h.yes_no("Still true?", "not really") is False
    model.rule = lambda p: "other"
    assert h.yes_no("Still true?", "it's 9 now") is None
    assert h.yes_no("Still true?", "well it depends on the week and also on the weather") is None  # long: the rules


class Plans(Module):
    id = "plans_test"
    title = "Plans (test)"

    def intents(self):
        return [
            Intent(
                "plan_today",
                "what's my plan today",
                lambda t: {} if re.fullmatch(r"(?i)what'?s my plan today\??", t) else None,
                lambda msg, s: "Plan for today: gym.",
                questions=True,
            ),
            Intent(
                "day_plan",
                "what's my day plan",
                lambda t: {} if re.fullmatch(r"(?i)what'?s my day plan\??", t) else None,
                lambda msg, s: "Day plan: study.",
                questions=True,
            ),
        ]


def test_the_helper_picks_the_request_when_no_pattern_is_sure(env, monkeypatch):
    env.app.modules["plans_test"] = Plans(env.app)
    env.on("plans_test")
    model = make_ready(env.app, monkeypatch)
    model.rule = lambda p: "2" if "1: what's my day plan" in p else "0"
    assert env.say("whats my plan") == "Plan for today: gym."
    assert any(e.get("via") == "helper" for e in env.app.events.tail(5, {"intent"}))
    model.rule = lambda p: "0"  # none of them: two readings, as before (core/repair.py)
    assert env.say("whats my plan").startswith("Did you mean")


# --------------------------------------------------------------------------------------------- offline
def test_offline_is_known_from_its_own_traffic(env):
    h = env.app.helper
    assert not h.offline()
    egress.seen("127.0.0.1", OSError("refused"))  # this computer doesn't count
    egress.seen("api.telegram.org", urllib.error.URLError("down"))
    assert not h.offline()  # one host could be that host
    egress.seen("generativelanguage.googleapis.com", TimeoutError())
    assert h.offline() and h.holds()
    assert not egress.net_down(time.time() + egress.NET_FRESH_S + 1)  # stale: no longer believed
    egress.seen("api.github.com", urllib.error.HTTPError("u", 404, "no", None, None))  # an answer, even a no
    assert not h.offline() and not egress.failed_since(0)
    internet_down()
    env.app.settings.set("local_helper.offline", False)
    assert h.offline() and not h.holds()


def test_requests_wait_for_the_internet_and_run_when_it_is_back(remote):
    env, ai = remote
    app = env.app
    internet_down()
    assert env.say("summarise the history of topology for me") == (
        "No internet connection right now: it waits and runs as soon as it's back."
    )
    assert app.jobs.run_next() is None  # waiting, not tried
    jid = app.jobs.active()[0].id
    assert app.jobs.held() == 1 and "for the internet connection" in app.jobs.line(app.jobs.get(jid))
    app.jobs._db.execute("update jobs set held_until=0 where id=?", (jid,))  # its next look: still down
    n = len(env.fake.texts())
    assert app.jobs.run_next() == jid and app.jobs.get(jid).status == "queued" and not ai.requests
    assert len(env.fake.texts()) == n  # told once
    assert app.helper.tick() == "down"
    internet_back()
    assert app.helper.tick() == "back"
    assert env.fake.texts()[-1].startswith("The internet is back: running what waited for it")
    assert app.jobs.run_next() == jid and app.jobs.get(jid).status == "ok"
    answer = env.fake.texts()[-1]
    assert answer.startswith("[Another OpenAI-compatible service") and "Paris." in answer
    assert "(It waited for the internet connection from " in answer


def test_a_request_that_finds_the_internet_gone_waits_and_is_told_once(remote, monkeypatch):
    env, ai = remote
    app = env.app
    from kurooto.providers.openai_compat import OpenAICompat

    def gone(self, path, body, timeout):
        egress.seen("api.example.org", urllib.error.URLError(OSError("Network is unreachable")))
        raise urllib.error.URLError(OSError("Network is unreachable"))

    monkeypatch.setattr(OpenAICompat, "_post", gone)
    jid = app.jobs.submit("hello there", reply_to=None)
    assert app.jobs.run_next() == jid
    assert app.jobs.get(jid).status == "queued"
    said = env.fake.texts()[-1]
    assert said == 'No internet connection right now: "hello there" waits and runs as soon as it\'s back.'


def test_a_lost_connection_waits_and_is_never_handed_to_a_fallback(remote, monkeypatch):
    """With brains-self's fallbacks: an AI that fails because the internet went isn't followed by the next one."""
    from kurooto import providers
    from kurooto.providers.base import Brain, Result, Verdict
    from kurooto.providers.openai_compat import OpenAICompat

    env, ai = remote
    app = env.app
    tried = []

    class Other(Brain):
        id, label, kind = "agy", "agy", "api"

        def available(self):
            return True, ""

        def run(self, task):
            tried.append(task.prompt)
            return Result(Verdict.OK, text="answered")

    orig = providers.build
    monkeypatch.setattr(providers, "build", lambda a, w: Other() if w == "agy" else orig(a, w))

    def gone(self, path, body, timeout):
        egress.seen("api.example.org", urllib.error.URLError(OSError("Network is unreachable")))
        raise urllib.error.URLError(OSError("Network is unreachable"))

    monkeypatch.setattr(OpenAICompat, "_post", gone)
    app.settings.set("brain.fallback", ["agy"])
    jid = app.jobs.submit("hello there", reply_to=None)
    assert app.jobs.run_next() == jid
    assert app.jobs.get(jid).status == "queued" and not tried  # held for the internet, agy not tried


def test_the_receipt_says_the_helper_decided(remote, monkeypatch):
    env, ai = remote
    app = env.app
    model = make_ready(app, monkeypatch)
    model.rule = lambda p: "high"
    app.settings.set("jobs.receipt", True)
    jid = app.jobs.submit("what is a group")  # the rules aren't sure: the helper decides
    assert app.jobs.run_next() == jid and app.jobs.get(jid).status == "ok"
    assert app.jobs.receipt(jid).startswith(f"decided by {TAG}, answered by ")


def test_one_that_waited_too_long_ends_with_a_message(remote):
    env, ai = remote
    app = env.app
    internet_down()
    jid = app.jobs.submit("write my essay")
    app.jobs.run_next()
    app.jobs._db.execute("update jobs set held=?, held_until=0 where id=?", (time.time() - 25 * 3600, jid))
    app.jobs.run_next()
    assert app.jobs.get(jid).status == "failed"
    assert "It waited for the internet connection for 24 h and didn't run" in env.fake.texts()[-1]


def test_an_ai_on_this_computer_still_runs_offline(env):
    ai = FakeOpenAI()
    try:
        app = env.app
        app.secrets.set("custom.api_key", ai.key)
        app.settings.set("brain.base_urls", {"custom": ai.base})  # 127.0.0.1: this computer
        app.settings.set("brain.models", {"custom": {"medium": "smart"}})
        app.settings.set("brain.main", "custom")
        internet_down()
        jid = app.jobs.submit("hello")
        assert app.jobs.run_next() == jid and app.jobs.get(jid).status == "ok"
    finally:
        ai.close()


def test_offline_a_quick_question_is_answered_here_with_a_line(remote, monkeypatch):
    env, ai = remote
    model = make_ready(env.app, monkeypatch)
    model.rule = lambda p: "low" if "How much reasoning" in p else "Paris is the capital of France."
    internet_down()
    said = env.say("what is the capital of france")
    assert said.startswith("Paris is the capital of France.") and "offline helper answered" in said
    assert not env.app.jobs.active()
    model.rule = lambda p: "low" if "How much reasoning" in p else "CANNOT"  # it can't: it waits instead
    assert env.say("what is in my calendar").startswith("No internet connection right now")
    internet_back()
    assert env.say("what is the capital of france") == "On it."  # online: your AI, as always


# --------------------------------------------------------------------------------------------- the offer
def write_events(app, kind, days_ago):
    with open(app.events.file, "a", encoding="utf-8") as f:
        for d in days_ago:
            ts = (dt.datetime.now() - dt.timedelta(days=d)).isoformat()
            f.write(json.dumps({"ts": ts, "kind": kind, "pool": "gemini:x"}) + "\n")


@pytest.fixture
def due(env, monkeypatch):
    app = env.app
    app.settings.set("setup.done", True)
    app.helper._update(since=time.time() - 15 * 86400)
    (app.paths.state / "hardware.json").write_text(
        json.dumps({"machine": {"ram_gb": 8}, "recommendation": {"local_models": []}})
    )
    fake_ollama(app, monkeypatch)
    return env


def test_offered_after_two_weeks_when_the_free_limit_runs_short(due, monkeypatch):
    env = due
    h = env.app.helper
    write_events(env.app, "quota_reserve", [1, 2])
    assert h.why_offer() is None  # two days isn't often
    write_events(env.app, "quota_limit", [3])
    assert h.why_offer() == "limit" and h.maybe_offer()
    sent = [p for m, p in env.fake.sent if m == "sendMessage" and "reply_markup" in p][-1]
    assert "ran short on 3 of the last 14 days" in sent["text"] and TAG in sent["text"]
    data = [b["callback_data"] for row in sent["reply_markup"]["inline_keyboard"] for b in row]
    assert data[0].startswith("lh:") and data[0].endswith(":install") and data[1].endswith(":later")
    assert not h.maybe_offer()  # once; Not now asks again a month later at most
    assert env.press(data[1]) == "OK. /helper on sets it up any time."
    started = []
    monkeypatch.setattr(h, "_in_background", lambda fn, label: started.append(label))
    assert env.press(data[0]).startswith("Setting up the offline helper") and started


def test_offered_when_the_internet_often_drops_and_not_on_a_graphics_card(due):
    env = due
    h = env.app.helper
    t = time.time()
    h._update(outages=[[t - d * 86400, t - d * 86400 + 900] for d in (1, 4, 9)])
    assert h.why_offer() == "offline"
    (env.app.paths.state / "hardware.json").write_text(
        json.dumps({"recommendation": {"local_models": [{"key": "helper-small", "tag": "q", "size_gb": 2.5}]}})
    )
    assert h.why_offer() is None
    env.app.settings.set("local_helper.offer", False)
    assert h.why_offer() is None


def test_not_before_two_weeks(due):
    h = due.app.helper
    h._update(since=time.time() - 3 * 86400)
    write_events(due.app, "quota_reserve", [0, 1, 2])
    assert h.why_offer() is None


def test_outages_are_counted_when_the_internet_comes_back(env, monkeypatch):
    h = env.app.helper
    clock = [1000.0]
    monkeypatch.setattr(h, "clock", lambda: clock[0])
    monkeypatch.setattr(h, "offline", lambda: True)
    assert h.tick() == "down"
    clock[0] += 900
    monkeypatch.setattr(h, "offline", lambda: False)
    assert h.tick() == "back"
    assert h.state()["outages"] == [[1000, 1900]]


def test_helper_command(env, monkeypatch):
    assert "The offline helper is off" in env.say("/helper")
    make_ready(env.app, monkeypatch)
    internet_down()
    said = env.say("/helper")
    assert said.startswith(f"The offline helper is on: {TAG}.") and "0.6 s" in said and "internet is down" in said
    assert env.say("/helper off").startswith("The offline helper is off.")
    assert env.app.settings.get("local_helper.on") is False
    assert helper_mod.RETRY_S > 0


def test_telegram_alone_not_answering_is_not_the_internet(env):
    pres, h = env.app.presence, env.app.helper
    for _ in range(2):
        pres.net_failed("telegram", OSError("unreachable"))
    assert pres.net_down() and h.offline() and not h.sure()
    egress.seen("generativelanguage.googleapis.com")  # something else answered since: Telegram's problem, not the net
    assert not h.offline()


def test_a_request_that_waited_tries_again_unless_the_internet_is_down_for_certain(remote):
    env, ai = remote
    app = env.app
    for _ in range(2):
        app.presence.net_failed("telegram", OSError("unreachable"))
    jid = app.jobs.submit("hello")
    app.jobs.run_next()
    assert app.jobs.get(jid).status == "queued" and not ai.requests  # held the first time
    app.jobs._db.execute("update jobs set held_until=0 where id=?", (jid,))
    app.jobs.run_next()  # its own request is the check: the AI answers, so it runs
    assert app.jobs.get(jid).status == "ok" and ai.requests


# ------------------------------------------------------------------------------- 0.9.3: a changed model
def test_a_changed_model_is_speed_tested_again_by_itself(env, monkeypatch):
    """(0.9.3, a fix) The speed test on file was for an old model, so the helper stayed unusable without a word and
    Voice's local judge quietly dropped every unclear statement for days. Now a changed (or gone) model is tested
    again by itself, once an hour at most, and only when the model in use is here."""
    app, h = env.app, env.app.helper
    model = make_ready(app, monkeypatch)
    model.rule = lambda p: "yes"
    h._update(test={"ok": True, "model": "llama3.2:1b", "at": time.time(), "seconds": 0.6})  # an old model's test
    assert not h.tested() and not h.ready() and h.retest_due()
    ticks = iter([0.0, 0.5, 1.0, 1.5, 2.0, 2.5])
    monkeypatch.setattr(h, "timer", lambda: next(ticks))
    assert h.maybe_retest(wait=True)
    assert h.tested() and h.ready() and not h.retest_due()
    ev = [e for e in app.events.tail(20) if e.get("kind") == "helper_retest"]
    assert ev and ev[-1]["ok"] is True


def test_a_failed_retest_stays_on_file_and_is_said(env, monkeypatch):
    """A model that fails its test here has a test on file for itself: not retried by itself (/helper test does)."""
    app, h = env.app, env.app.helper
    model = make_ready(app, monkeypatch)
    model.rule = lambda p: None  # no answer
    h._update(test={"ok": True, "model": "llama3.2:1b", "at": time.time(), "seconds": 0.6})
    assert h.maybe_retest(wait=True) and not h.tested()
    monkeypatch.setattr(h, "clock", lambda: time.time() + helper_mod.RETEST_S + 5)
    assert not h.retest_due()
    assert "hasn't passed its speed test" in h.status()
    app.settings.set("local_helper.on", False)  # off: never
    assert not h.retest_due()


def test_a_retest_that_couldn_t_finish_is_tried_again_after_the_hour(env, monkeypatch):
    app, h = env.app, env.app.helper
    make_ready(app, monkeypatch)
    h._update(test={"ok": True, "model": "llama3.2:1b", "at": time.time(), "seconds": 0.6})
    h._update(retest={"model": TAG, "at": time.time()})  # started, never got as far as writing its result
    assert not h.retest_due()
    monkeypatch.setattr(h, "clock", lambda: time.time() + helper_mod.RETEST_S + 5)
    assert h.retest_due()


def test_no_retest_while_the_model_in_use_isn_t_here(env, monkeypatch):
    app, h = env.app, env.app.helper
    make_ready(app, monkeypatch)
    monkeypatch.setattr(app.modules["local_models"], "have", lambda: {"llama3.2:1b"})
    h._update(test={"ok": True, "model": "llama3.2:1b", "at": time.time(), "seconds": 0.6})
    assert not h.retest_due()

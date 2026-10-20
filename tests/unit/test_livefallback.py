"""When Gemini Live won't take a call (calls/fallback.py, data/worker/web/fallback.js): the shared JS helpers (Google's
errors, Live retries with model rotation), the Live models and voice modes the call line is told, the count of Live
failures for `kurooto doctor`, turn-by-turn turns answered here by a quick brain (never an agent program), and the
call going on as text on Telegram, with its transcript reaching the check-in's journal. The call line's side is in
tests/integration/test_livefallback_line.py."""

from __future__ import annotations

import datetime as dt
import json
import shutil
import subprocess
import time
from pathlib import Path

import pytest

import kurooto
from kurooto.core.state import jload, jsave
from kurooto.modules.calls import fallback
from tests.fakes.openai_tools import ScriptedOpenAI, call

WORKER = Path(kurooto.__file__).parent / "data" / "worker"


@pytest.mark.skipif(not shutil.which("node"), reason="needs Node")
def test_the_shared_fallback_helpers():
    js = Path(__file__).parent.parent / "js" / "fallback.mjs"
    r = subprocess.run(
        ["node", str(js), str(WORKER / "web" / "fallback.js")], capture_output=True, text=True, timeout=60
    )
    assert r.returncode == 0, r.stderr
    assert "fallback ok" in r.stdout


def esbuild(*args: str) -> subprocess.CompletedProcess:
    """The Worker's esbuild: its own program, or (where npm left a launcher script) through Node."""
    exe = WORKER / "node_modules" / "esbuild" / "bin" / "esbuild"
    for cmd in ([str(exe)], ["node", str(exe)]):
        try:
            r = subprocess.run([*cmd, *args], cwd=WORKER, capture_output=True, text=True, timeout=120)
        except OSError:
            continue
        if r.returncode == 0:
            return r
    return r


@pytest.mark.skipif(
    not shutil.which("node") or not (WORKER / "node_modules" / "esbuild").is_dir(), reason="needs Node and esbuild"
)
def test_the_call_page_retries_live_then_goes_turn_by_turn_then_to_telegram(tmp_path):
    """The real call page, bundled with a fake Live API, in Node with a stub page, call line and speech."""
    js = Path(__file__).parent.parent / "js"
    out = tmp_path / "callpage-app.mjs"
    r = esbuild(
        "web/app.js",
        "--bundle",
        "--format=esm",
        "--target=es2020",
        "--platform=neutral",
        f"--alias:@google/genai={js / 'fake-genai.mjs'}",
        f"--outfile={out}",
        "--log-level=warning",
    )
    assert r.returncode == 0, r.stderr
    r = subprocess.run(["node", str(js / "callpage.mjs"), str(out)], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr + r.stdout
    assert "callpage ok" in r.stdout


def calls_on(app):
    """Phone calls counted as on (its call line isn't needed here), started as the daemon does."""
    app.settings.set("modules.enabled", [*(app.settings.get("modules.enabled") or []), "calls"])
    calls = app.modules["calls"]
    calls.start()
    return calls


# ------------------------------------------------------------------------------- models and voice modes
def test_live_models_in_order_and_what_the_line_is_told(env):
    calls = env.app.modules["calls"]
    assert calls.live_models() == [
        "gemini-3.8-live",
        "gemini-3.1-flash-live-preview",
        "gemini-2.5-flash-native-audio-latest",
    ]
    # the setup's model as set up; the others what any Live model takes: waiting tools, a voice they know
    assert calls.live_profiles() == {
        "gemini-3.8-live": {},
        "gemini-3.1-flash-live-preview": {"non_blocking": False, "voice": ""},
        "gemini-2.5-flash-native-audio-latest": {"non_blocking": False, "voice": ""},
    }
    env.app.settings.set("calls.voice", "Kore")
    env.app.settings.set("calls.voice_by_model", {"gemini-2.5-flash-native-audio-latest": "Aoede", "x": 1})
    p = calls.live_profiles()
    assert p["gemini-3.1-flash-live-preview"]["voice"] == "Kore"
    assert p["gemini-2.5-flash-native-audio-latest"] == {"non_blocking": False, "voice": "Aoede"}
    env.app.settings.set("calls.voice", "SomeOldVoice")  # not one the other models know: Google's default there
    assert calls.live_profiles()["gemini-3.1-flash-live-preview"]["voice"] == ""
    env.app.settings.set("calls.voice_by_model", {"gemini-3.8-live": "Puck"})
    assert calls.live_profiles()["gemini-3.8-live"] == {"voice": "Puck"}
    env.app.settings.set("calls.live_models", ["gemini-live-b", "gemini-3.8-live", "bad id; drop", "gemini-live-c"])
    assert calls.live_models() == ["gemini-3.8-live", "gemini-live-b", "gemini-live-c"]
    env.app.settings.set("calls.live_models", "gemini-live-b")  # typed as one name
    assert calls.live_models() == ["gemini-3.8-live", "gemini-live-b"]
    msg = calls.state_message()
    assert msg["live"]["models"] == ["gemini-3.8-live", "gemini-live-b"]
    assert msg["live"]["profiles"]["gemini-live-b"]["non_blocking"] is False
    assert msg["live"]["text_model"] == "gemini-flash-latest" and msg["live"]["voice"] == "auto"
    assert "turn by turn" in msg["texts"]["turns"] and "Telegram" in msg["texts"]["text_call"]
    assert msg["config"]["_model"] == "gemini-3.8-live"  # the first, as before (older call lines read only this)


def test_voice_mode_per_kind_of_call(env):
    calls = env.app.modules["calls"]
    assert calls.voice_for("checkins:evening:2026-10-20") == "auto"
    env.app.settings.set("calls.voice_mode", "live")
    env.app.settings.set(
        "calls.voice_by_kind",
        {"alarm": "phone", "checkins": "phone", "checkins:evening": "live", "reminder": "phone", "outgoing": "Phone"},
    )
    assert calls.voice_for("alarm:next") == "phone"
    assert calls.voice_for("checkins:night:2026-10-20") == "phone"
    assert calls.voice_for("checkins:evening:2026-10-20") == "live"  # the more exact kind wins
    assert calls.voice_for("weekly:review:2026-10-18") == "live"  # not named: voice_mode
    assert calls.voice_for("") == "phone" and calls.voice_for("held-abc123") == "phone"  # plain reminder calls
    assert calls.voice_for(outgoing=True) == "phone"
    env.app.settings.set("calls.voice_mode", "nonsense")
    assert calls.voice_for("weekly:review:x") == "auto"
    # the link and the call line's copy of the schedule say it, so a call placed while this computer is off does too
    env.app.settings.set("calls.worker", {"url": "https://line.example"})
    env.app.secrets.set("calls.call_secret", "s" * 64)
    assert "v=phone" in calls.link("Wake up", since="123", voice=calls.voice_for("alarm:next"))
    calls.schedule(dt.datetime.now() + dt.timedelta(hours=1), "a reminder")
    assert [c["voice"] for c in calls.schedule_list()] == ["phone"]


# ---------------------------------------------------------------------------------------------- health
def test_live_failures_are_counted_for_doctor(env):
    app = env.app
    calls = calls_on(app)
    assert calls.doctor_checks() == [("voice service", True, "Gemini Live: no failures in the last 7 days")]
    calls.on_event({"name": "live_failed", "model": "gemini-3.8-live", "code": 503, "status": "UNAVAILABLE"})
    calls.on_event({"name": "live_failed", "model": "gemini-live-b", "code": 503, "stage": "connect"})
    calls.on_event({"name": "live_recovered", "model": "gemini-live-b", "attempt": 3})
    calls.on_event({"name": "call_fallback", "layer": "turns", "why": "live"})
    calls.on_event({"name": "call_fallback", "layer": "telegram", "why": "no_speech"})
    old = (dt.datetime.now() - dt.timedelta(days=9)).isoformat()  # queued while the computer was off, long ago
    calls.on_event({"name": "live_failed", "model": "x", "code": 503, "at": old})
    (name, ok, detail) = calls.doctor_checks()[0]
    assert ok is None  # a note: Google's outage isn't yours to fix
    assert detail.startswith("Gemini Live failed 2 times in 7 days (last ") and "503" in detail
    assert "gemini-live-b" in detail and "1 got through on a retry" in detail and "no longer" not in detail
    assert "1 went on turn by turn" in detail and "1 went on text on Telegram" in detail
    assert calls.status()["live"]["failed"] == 2
    from kurooto import diagnostics

    rows = {n: (o, d) for n, o, d in diagnostics.more_checks(app)}
    assert rows["Phone calls: voice service"] == (None, detail)
    kinds = [json.loads(ln)["kind"] for ln in (app.paths.state / "events.jsonl").read_text().splitlines()]
    assert kinds.count("call_live_failed") == 3 and "call_fallback" in kinds and "call_live_recovered" in kinds
    # a model in the list that Google says doesn't exist: told, until a call gets through on it
    calls.on_event({"name": "live_failed", "model": "gemini-2.5-flash-native-audio-latest", "code": 404})
    calls.on_event({"name": "live_failed", "model": "not-in-the-list", "code": 404, "status": "NOT_FOUND"})
    gone = calls.doctor_checks()[0][2]
    assert gone.endswith(
        "; gemini-2.5-flash-native-audio-latest no longer exists (Google said not found): take it out of "
        "calls.live_models"
    )
    calls.on_event({"name": "live_recovered", "model": "gemini-2.5-flash-native-audio-latest", "attempt": 2})
    assert "no longer exist" not in calls.doctor_checks()[0][2]


# ----------------------------------------------------------------------------------------- turn by turn
def gemini_brain(env, fake):
    env.app.secrets.set("gemini.api_key", "gem-key")
    env.app.settings.set("brain.base_urls", {"gemini": fake.base})


def test_a_turn_is_answered_by_a_quick_brain_with_the_calls_instructions_and_tools(env):
    app = env.app
    calls = calls_on(app)
    app.settings.set("brain.main", "agy")  # never used for a turn: seconds just to start
    app.settings.set("you.name", "Sam")
    fake = ScriptedOpenAI(
        [
            {"tool_calls": [call("write_note", {"slug": "inbox/call-idea", "text": "Ask about the lab report"})]},
            {"content": "**Done.** I noted the lab report.\n- anything else?"},
        ]
    )
    try:
        gemini_brain(env, fake)
        history = [
            {"role": "user", "text": "[The call just connected. Speak first: greet them and get straight to it.]"},
        ]
        code, out = calls.handle_request(
            "POST", "/turn", json.dumps({"history": history, "purpose": "Evening debrief"}).encode()
        )
        assert code == 200, out
        assert out == {"reply": "Done. I noted the lab report. anything else?", "brain": "gemini"}
        first = fake.requests[0]
        assert first["model"] == "gemini-flash-latest"  # calls.text_model, not the brain's usual model
        prompt = first["messages"][-1]["content"]
        assert "Sam's personal assistant" in prompt and "Evening debrief" in prompt and "turn by turn" in prompt
        assert "pending_items, already called for you" in prompt  # the first answer knows what's due
        assert prompt.rstrip().endswith("nothing else.") and "[The call just connected." in prompt
        assert any(t["function"]["name"] == "write_note" for t in first["tools"])
        assert "Ask about the lab report" in (app.workspace / "inbox" / "call-idea.md").read_text()
        # later turns carry the call so far, and don't brief again
        fake.script = [{"content": "Night then."}]
        history += [{"role": "model", "text": "Hi Sam, how did today go?"}, {"role": "user", "text": "Fine, tired."}]
        code, out = calls.handle_request("POST", "/turn", json.dumps({"history": history}).encode())
        assert code == 200 and out["reply"] == "Night then."
        prompt = fake.requests[-1]["messages"][-1]["content"]
        assert "Kurooto: Hi Sam, how did today go?\nSam: Fine, tired." in prompt
        assert "pending_items, already called" not in prompt
    finally:
        fake.close()


def test_a_turn_with_no_quick_brain_or_a_failing_one_leaves_it_to_the_call_line(env):
    calls = calls_on(env.app)
    body = json.dumps({"history": [{"role": "user", "text": "hello"}]}).encode()
    env.app.settings.set("brain.main", "agy")
    assert calls.handle_request("POST", "/turn", body)[0] == 503  # no Gemini key: the call line's Gemini answers
    fake = ScriptedOpenAI([("http", 500, {"error": {"message": "boom"}})])
    try:
        gemini_brain(env, fake)
        assert calls.handle_request("POST", "/turn", body)[0] == 502
        assert calls.handle_request("POST", "/turn", b'{"history": []}')[0] == 400
    finally:
        fake.close()


def test_a_turn_can_use_the_model_on_this_computer(env):
    calls = calls_on(env.app)
    local = ScriptedOpenAI([{"content": "From the laptop."}])
    try:
        env.app.secrets.set("ollama.api_key", "ollama")
        env.app.settings.set("brain.base_urls", {"ollama": local.base})
        env.app.settings.set("brain.models", {"ollama": {"low": "small", "medium": "small", "high": "small"}})
        env.app.settings.set("calls.turn_brain", "local")
        body = json.dumps({"history": [{"role": "user", "text": "hi"}]}).encode()
        assert calls.handle_request("POST", "/turn", body) == (200, {"reply": "From the laptop.", "brain": "ollama"})
    finally:
        local.close()


# --------------------------------------------------------------------------------------------- on Telegram
@pytest.fixture
def text_call(env):
    """Phone calls on, check-ins on (their journal), the AI a scripted OpenAI-style service."""
    app = env.app
    fake = ScriptedOpenAI([{"content": "Hi Sam! How did today go?"}])
    app.secrets.set("custom.api_key", fake.key)
    app.settings.set("brain.base_urls", {"custom": fake.base})
    app.settings.set("brain.models", {"custom": {"low": "fast", "medium": "smart", "high": "smart"}})
    app.settings.set("brain.main", "custom")
    app.settings.set("you.name", "Sam")
    env.on("checkins")
    calls = calls_on(app)
    yield env, calls, fake
    fake.close()


def test_a_call_goes_on_as_text_and_its_transcript_becomes_the_journal(text_call):
    env, calls, fake = text_call
    app = env.app
    day = app.modules["checkins"].day_of()
    since = str(int(time.time()))
    jsave(
        calls.dir / "rings.json",
        {since: {"reason": "Evening debrief", "key": f"checkins:evening:{day.isoformat()}", "at": time.time()}},
    )
    lines = [{"who": "Kurooto", "text": "Hi Sam"}, {"who": "Sam", "text": "The lab went well"}]
    out = calls.handle_request(
        "POST",
        "/textcall",
        json.dumps({"purpose": "Evening debrief", "since": since, "why": "no_speech", "lines": lines}).encode(),
    )
    assert out[0] == 200 and out[1]["ok"] and out[1]["where"] == "telegram"
    cid = out[1]["id"]
    head = env.fake.texts()[-1]
    assert "couldn't go on by voice (this phone can't turn speech into text)" in head and "Evening debrief" in head
    assert app.jobs.run_next()  # the AI's first message, through the queue like any request
    assert env.fake.texts()[-1] == "Hi Sam! How did today go?"
    prompt = fake.requests[-1]["messages"][-1]["content"]
    assert "text messages on Telegram" in prompt and "Sam: The lab went well" in prompt
    assert "[The call moved to text messages" in prompt
    kb = [p for m, p in env.fake.sent if m == "sendMessage"][-1]["reply_markup"]["inline_keyboard"]
    assert kb[0][0]["callback_data"] == f"callchat:{cid}:end"
    # a plain message (not a reply) is part of the call; so is a reply
    fake.script = [{"content": "Nice. Anything that slipped?"}]
    env.say("Finished the problem set, skipped the reading")
    assert app.jobs.run_next() and env.fake.texts()[-1] == "Nice. Anything that slipped?"
    assert "Sam: Finished the problem set" in fake.requests[-1]["messages"][-1]["content"]
    fake.script = [{"content": "Got it, goodnight."}]
    env.reply_to_last("Just the reading")
    assert app.jobs.run_next() and env.fake.texts()[-1] == "Got it, goodnight."
    # two messages while it's answering: one more answer, with both
    fake.script = [{"content": "First."}, {"content": "Second, with both."}]
    env.say("one more thing")
    env.say("and another")
    assert app.jobs.run_next() and app.jobs.run_next()
    assert app.jobs.run_next() is None
    assert "and another" in fake.requests[-1]["messages"][-1]["content"]
    # End: the transcript is kept, and the check-in writes the journal from what Sam said
    assert env.press(f"callchat:{cid}:end") == "Call ended."
    saved = sorted((calls.dir / "transcripts").glob("*.txt"))[-1].read_text()
    assert saved.startswith("# Evening debrief (text on Telegram)\n") and "Sam: Just the reading" in saved
    journal = next((app.workspace / "journal").glob("*.md")).read_text()
    assert "The lab went well" in journal and "Just the reading" in journal and "goodnight" not in journal
    # over: messages go back to normal, and a reply to the old call says it's over
    before = len(env.fake.texts())
    env.say("/help")
    assert len(env.fake.texts()) > before and calls.textcall.open_one() is None
    assert env.press(f"callchat:{cid}:end") == "That call is over already."


def test_a_text_call_ends_when_quiet_and_a_late_one_only_says_so(text_call):
    env, calls, fake = text_call
    out = calls.textcall.start({"purpose": "", "why": "live"})
    assert "(the voice service is down)" in env.fake.texts()[-1]
    assert env.app.jobs.run_next()
    assert "[They called you, and the voice failed" in fake.requests[-1]["messages"][-1]["content"]
    d = jload(calls.textcall.file, {})
    d[out["id"]]["last"] = time.time() - fallback.TEXT_IDLE_S - 10
    jsave(calls.textcall.file, d)
    calls.textcall.idle({"cid": out["id"]})
    assert env.fake.texts()[-1] == "Ended the call (no messages for 20 minutes)."
    assert calls.textcall.get(out["id"])["state"] == "ended"
    old = (dt.datetime.now() - dt.timedelta(hours=3)).isoformat()
    calls.on_event({"name": "text_call", "purpose": "Wake-up call", "why": "no_speech", "at": old})
    assert env.fake.texts()[-1].startswith("A call couldn't connect by voice while this computer was off: Wake-up")
    assert calls.textcall.open_one() is None
    calls.on_event({"name": "text_call", "purpose": "Quiz", "why": "no_mic", "at": dt.datetime.now().isoformat()})
    assert "(the microphone isn't available)" in env.fake.texts()[-1] and calls.textcall.open_one()


def test_the_turn_prompt_keeps_notes_out_of_what_was_said(env):
    calls = env.app.modules["calls"]
    lines, note = fallback._history_lines(
        calls,
        [
            {"role": "user", "text": "hi"},
            {"role": "user", "text": "[Task finished] (done) Request: x\nResult: y"},
            {"role": "model", "text": "Your task is done."},
            {"role": "user", "text": "[Approval needed] id=1: send it? (answer with answer_approval)"},
        ],
    )
    assert [x["who"] for x in lines] == ["You", "(note)", "Kurooto"] and note.startswith("[Approval needed]")
    assert fallback.spoken("## Plan\n1. **eat**\n2. [sleep](http://x)") == "Plan eat sleep"

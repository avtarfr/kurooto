"""When Gemini Live won't take a call, end to end on this computer: the real Worker under `wrangler dev`, the real
connector and Phone calls feature, fake Gemini (its token endpoint answering 503 UNAVAILABLE, as it did, and its text
model), ntfy and Web Push (see test_call_line.py for the setup).

The token for the next Live model, Live failures counted here, a turn-by-turn turn answered by this computer's quick
AI, or by Gemini on the call line when this computer can't (with the call's tools), the call handed to Telegram, and,
with this computer off, turns answered on the line with a tool queued for later and the Telegram handover waiting
until it's back. Ring links say how the call listens (calls.voice_mode).
"""

from __future__ import annotations

import json

import pytest

from kurooto.modules.calls import line
from tests.fakes.openai_tools import ScriptedOpenAI
from tests.integration.test_call_line import Loop, pytestmark, wait, world  # noqa: F401 (the shared fixture)


@pytest.fixture(scope="module")
def lf(world):  # noqa: F811
    app, calls, ln = world["app"], world["calls"], world["line"]
    calls.start()  # its then-actions and timers, as the daemon does
    app.settings.set("modules.enabled", [*(app.settings.get("modules.enabled") or []), "calls"])
    app.settings.set("calls.live_models", ["gemini-test-live-b", "gemini-test-gone"])
    app.settings.set("calls.voice", "Kore")
    app.settings.set("calls.voice_by_model", {"gemini-test-live-b": "Puck"})
    p = calls.pair_start()
    code, got = ln.call("POST", "/pair/claim", {"code": p["code"], "kind": "android", "name": "Test phone"})
    assert code == 200, got
    world["key"] = got["device"]
    calls.connector.poke()  # push the new model list
    models = ["gemini-test-live", "gemini-test-live-b", "gemini-test-gone"]

    def pushed():
        t = ln.call("POST", "/token", {"model": "nope", "announce": False}, key=got["device"])[1]
        return t.get("models") == models and "speechConfig" in (t.get("config") or {})

    wait(pushed, 20, "the model list and voice on the line")
    brain = ScriptedOpenAI([{"content": "Hello from your computer."}])
    app.settings.set("brain.base_urls", {"gemini": brain.base})  # the quick AI for turns here (your Gemini key)
    world["brain"] = brain
    yield world
    brain.close()


def test_a_503_is_answered_as_retryable_and_the_next_model_works(lf):
    ln, cloud, calls, key = lf["line"], lf["cloud"], lf["calls"], lf["key"]
    cloud.live_down = {"gemini-test-live"}
    try:
        code, t = ln.call("POST", "/token", {"purpose": "Evening debrief", "since": ""}, key=key)
        assert code == 503
        assert t["live"] is True and t["retry"] is True and t["code"] == 503 and t["status"] == "UNAVAILABLE"
        assert t["models"] == ["gemini-test-live", "gemini-test-live-b", "gemini-test-gone"]
        assert t["model"] == "gemini-test-live"
        assert "The service is currently unavailable." in t["error"]
        wait(lambda: calls.live.summary()["failed"] >= 1, 15, "the failure counted here")
        assert calls.live.summary()["last"]["stage"] == "token"
        code, t = ln.call("POST", "/token", {"purpose": "Evening debrief", "model": "gemini-test-live-b"}, key=key)
        assert code == 200 and t["model"] == "gemini-test-live-b" and t["models"][1] == "gemini-test-live-b"
        assert "gemini-test-live-b" in json.dumps(cloud.tokens[-1]["body"]) and "_models" not in json.dumps(t["config"])
        code, t = ln.call("POST", "/token", {"model": "not-on-the-list"}, key=key)
        assert code == 503 and t["model"] == "gemini-test-live"  # only models from the list
    finally:
        cloud.live_down = set()


def test_each_model_gets_a_session_it_takes_and_a_gone_one_is_told(lf):
    ln, cloud, calls, key = lf["line"], lf["cloud"], lf["calls"], lf["key"]

    def setup(body):
        return json.dumps(body["body"])

    code, t = ln.call("POST", "/token", {"model": "gemini-test-live", "announce": False}, key=key)
    assert code == 200
    assert {d.get("behavior") for d in t["config"]["tools"][0]["functionDeclarations"]} == {"NON_BLOCKING"}
    assert t["config"]["speechConfig"]["voiceConfig"]["prebuiltVoiceConfig"]["voiceName"] == "Kore"
    assert "NON_BLOCKING" in setup(cloud.tokens[-1]) and '"Kore"' in setup(cloud.tokens[-1])
    # another model: tools that wait (native-audio models refuse NON_BLOCKING), and the voice picked for it
    code, t = ln.call("POST", "/token", {"model": "gemini-test-live-b", "announce": False}, key=key)
    assert code == 200
    assert not any("behavior" in d for d in t["config"]["tools"][0]["functionDeclarations"])
    assert t["config"]["speechConfig"]["voiceConfig"]["prebuiltVoiceConfig"]["voiceName"] == "Puck"
    assert "NON_BLOCKING" not in setup(cloud.tokens[-1]) and '"Puck"' in setup(cloud.tokens[-1])
    cloud.live_errors = {
        "gemini-test-gone": (404, "NOT_FOUND", "models/gemini-test-gone is not found for API version v1alpha"),
        "gemini-test-live-b": (400, "INVALID_ARGUMENT", "Invalid value at 'setup.generation_config'"),
    }
    try:
        code, t = ln.call("POST", "/token", {"model": "gemini-test-gone", "announce": False}, key=key)
        assert code == 503 and t["code"] == 404 and t["bad_model"] is True and t["retry"] is False
        code, t = ln.call("POST", "/token", {"model": "gemini-test-live-b", "announce": False}, key=key)
        assert code == 503 and t["bad_model"] is True  # another model refusing the session: try the next
        cloud.live_errors = {"gemini-test-live": (400, "INVALID_ARGUMENT", "bad")}
        code, t = ln.call("POST", "/token", {"announce": False}, key=key)
        assert code == 503 and t["bad_model"] is False  # the first one: that's the setup, not the model
    finally:
        cloud.live_errors = {}
    wait(lambda: "gemini-test-gone no longer exists" in calls.doctor_checks()[0][2], 15, "the doctor note")
    assert "take it out of calls.live_models" in calls.doctor_checks()[0][2]


def test_the_call_page_reports_what_it_saw(lf):
    ln, calls, key = lf["line"], lf["calls"], lf["key"]
    n = calls.live.summary()
    for body in (
        {"what": "failed", "model": "gemini-test-live", "code": 1011, "stage": "start"},
        {"what": "recovered", "model": "gemini-test-live-b", "attempt": 2},
        {"what": "fallback", "layer": "turns", "why": "live"},
    ):
        assert ln.call("POST", "/call-report", body, key=key) == (200, {"ok": True})
    assert ln.call("POST", "/call-report", {"what": "anything"}, key=key)[0] == 400
    wait(lambda: calls.live.summary()["fallbacks"].get("turns", 0) > n["fallbacks"].get("turns", 0), 15, "reports")
    s = calls.live.summary()
    assert s["failed"] == n["failed"] + 1 and s["recovered"] == n["recovered"] + 1
    assert "went on turn by turn" in calls.doctor_checks()[0][2]


def test_a_turn_goes_to_this_computer_and_then_to_gemini_on_the_line(lf):
    ln, cloud, brain, key, app = lf["line"], lf["cloud"], lf["brain"], lf["key"], lf["app"]
    hist = [{"role": "user", "text": "[The call just connected. Speak first.]"}]
    code, r = ln.call("POST", "/turn", {"history": hist, "purpose": "Evening debrief", "announce": True}, key=key)
    assert code == 200 and r == {"reply": "Hello from your computer.", "via": "computer"}
    assert "Evening debrief" in brain.requests[-1]["messages"][-1]["content"]
    wait(lambda: '"layer": "turns"' in (app.paths.state / "events.jsonl").read_text(), 10, "the call answered")
    # this computer's AI fails: Gemini on the line answers, with the call's instructions and tools
    brain.script = [("http", 500, {"error": {"message": "down"}})]
    n = len(cloud.generate)
    cloud.gen_script = [
        {"call": ("search_notes", {"query": "eigenvalues"})},
        {"text": "**Det(A - tI) = 0**, per your notes."},
    ]
    code, r = ln.call("POST", "/turn", {"history": hist + [{"role": "user", "text": "eigenvalues?"}]}, key=key)
    assert code == 200 and r == {"reply": "Det(A - tI) = 0, per your notes.", "via": "line", "offline": False}
    first, second = cloud.generate[n]["body"], cloud.generate[n + 1]["body"]
    assert "gemini-flash-latest:generateContent" in cloud.generate[n]["path"]
    assert "turn by turn" in json.dumps(first["systemInstruction"]) and "Sam's personal assistant" in json.dumps(first)
    decls = first["tools"][0]["functionDeclarations"]
    assert any(d["name"] == "pending_items" for d in decls) and not any("behavior" in d for d in decls)
    answer = second["contents"][-1]["parts"][0]["functionResponse"]
    assert answer["name"] == "search_notes" and "courses/linear-algebra" in json.dumps(answer)  # this computer's tool
    brain.script = [{"content": "Hello from your computer."}]


def test_the_call_moves_to_telegram(lf):
    ln, key, sent, app = lf["line"], lf["key"], lf["sent"], lf["app"]
    lines = [{"who": "Sam", "text": "is it working"}]
    code, r = ln.call(
        "POST", "/text-call", {"purpose": "Quiz", "why": "no_speech", "lines": lines, "announce": True}, key=key
    )
    assert code == 200 and r["ok"] and r["where"] == "telegram" and r["id"]
    wait(lambda: any("can't turn speech into text" in m.text for m in sent), 10, "the first message")
    m = [m for m in sent if "can't turn speech into text" in m.text][-1]
    assert m.map_kind == "callchat" and m.map_ref == r["id"]
    assert app.modules["calls"].textcall.get(r["id"])["lines"] == lines
    app.modules["calls"].textcall.end(r["id"], "you ended it")


def test_ring_links_say_how_the_call_listens(lf):
    ln, calls, cloud, sec, app = lf["line"], lf["calls"], lf["cloud"], lf["sec"], lf["app"]
    app.settings.set("calls.voice_by_kind", {"reminder": "phone"})
    calls.connector.poke()
    n0 = len(cloud.ntfy)
    calls.ring("Stretch")
    wait(lambda: len(cloud.ntfy) > n0, 20, "the ring")
    inner = json.loads(line.open_k1(sec["NTFY_KEY"], cloud.ntfy[-1]["message"]))
    assert "&v=phone#" in inner["click"]
    assert wait(lambda: ln.call("GET", "/status", key=lf["key"])[1].get("voice"), 10, "status") == "auto"
    app.settings.set("calls.voice_by_kind", {})


def test_with_this_computer_off_turns_are_answered_on_the_line_and_telegram_waits(lf):
    ln, cloud, key, app, calls = lf["line"], lf["cloud"], lf["key"], lf["app"], lf["calls"]
    lf["loop"].halt()
    wait(lambda: ln.call("GET", "/status", key=key)[1]["computer"] == "offline", 20, "offline")
    n = len(cloud.generate)
    cloud.gen_script = [
        {"call": ("schedule_call", {"when": "in 3 hours", "reason": "the essay"})},
        {"text": "Done: I'll call you about the essay."},
    ]
    code, r = ln.call("POST", "/turn", {"history": [{"role": "user", "text": "call me in 3 hours"}]}, key=key)
    assert code == 200 and r == {"reply": "Done: I'll call you about the essay.", "via": "line", "offline": True}
    assert "OFF right now" in json.dumps(cloud.generate[n]["body"]["systemInstruction"])
    said = cloud.generate[n + 1]["body"]["contents"][-1]["parts"][0]["functionResponse"]["response"]["result"]
    assert "Saved" in said  # queued for when the computer is back
    code, r = ln.call("POST", "/text-call", {"purpose": "Wake-up call", "why": "no_mic"}, key=key)
    assert code == 200 and r == {"ok": True, "queued": True}
    lf["loop"] = Loop(app)
    wait(lambda: calls.connector.connected, 30, "reconnect")
    wait(lambda: any(j.payload.get("reason") == "the essay" for j in app.scheduler.jobs("calls:ring:")), 15, "queue")
    wait(lambda: any("microphone isn't available" in m.text for m in lf["sent"]), 15, "the Telegram handover")
    cid = calls.textcall.open_one()
    assert cid and calls.textcall.get(cid)["purpose"] == "Wake-up call"
    calls.textcall.end(cid, "you ended it")

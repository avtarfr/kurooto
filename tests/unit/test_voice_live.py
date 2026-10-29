"""Live at the desk (voice.listen.live, modules/voice/live.py): an owner's turn the gate admitted is answered by Gemini
Live, its sound played through Voice's Speaker; nothing else ever connects. A fake Live server on this computer
stands in for Google (asyncio websockets on 127.0.0.1): no real API, microphone, camera or speaker is touched."""

# ruff: noqa: F811 (the fixtures imported from test_voice are taken as arguments)

import asyncio
import base64
import json
import threading
import time

import pytest

from kurooto.core import nearby
from kurooto.modules.voice import live as live_mod
from kurooto.modules.voice.gate import Heard
from kurooto.modules.voice.portal import UNSURE_NOTICE as UNSURE
from kurooto.modules.voice.speakerid import Verdict
from tests.unit.test_voice import Engine, Speakers, voice  # noqa: F401 (pytest fixtures)

KEY = "AIzaFAKE-desk-test-key-000"
SOUND = bytes(range(256)) * 125  # 32000 bytes: one second at 16 kHz, standing for the stretch
ANSWER = b"\x01\x02" * 12000  # half a second at 24 kHz


class FakeLive:
    """Gemini Live's BidiGenerateContent, as much of it as a desk turn uses. mode: speak, silent, refuse, tool,
    interrupt."""

    def __init__(self, mode="speak", tool=("hold_calls", {"until": "18:00"})):
        self.mode, self.tool = mode, tool
        self.paths, self.keys, self.setups, self.turns, self.tool_responses = [], [], [], [], []
        self.closed = threading.Event()
        self.starts = 0
        self.tasks = set()
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.loop.run_forever, daemon=True)
        self.thread.start()
        self.server = asyncio.run_coroutine_threadsafe(self._serve(), self.loop).result(5)
        self.port = self.server.sockets[0].getsockname()[1]
        self.url = f"ws://127.0.0.1:{self.port}/ws/live"

    async def _serve(self):
        from websockets.asyncio.server import serve

        return await serve(self._handler, "127.0.0.1", 0)

    def stop(self):
        async def down():
            for t in self.tasks:
                t.cancel()
            self.server.close()
            await self.server.wait_closed()

        asyncio.run_coroutine_threadsafe(down(), self.loop).result(5)
        self.loop.call_soon_threadsafe(self.loop.stop)

    async def _handler(self, ws):
        self.paths.append(ws.request.path)
        self.keys.append(ws.request.headers.get("x-goog-api-key"))
        setup = json.loads(await ws.recv())["setup"]
        self.setups.append(setup)
        if self.mode == "refuse":
            await ws.close(1011, "unavailable")
            return
        await ws.send(json.dumps({"setupComplete": {}}).encode())  # Google sends binary frames
        got = asyncio.Event()
        audio = bytearray()
        try:
            async for raw in ws:
                m = json.loads(raw)
                ri = m.get("realtimeInput") or {}
                if "audio" in ri:
                    assert ri["audio"]["mimeType"] == "audio/pcm;rate=16000"
                    audio += base64.b64decode(ri["audio"]["data"])
                if "activityStart" in ri:
                    self.starts += 1
                    busy = [t for t in self.tasks if not t.done()]
                    for t in busy:  # as Google does: a new activity interrupts the answer being made
                        t.cancel()
                    if busy:
                        await ws.send(json.dumps({"serverContent": {"interrupted": True}}))
                if "activityEnd" in ri:
                    self.turns.append(bytes(audio))
                    audio.clear()
                    t = asyncio.create_task(self._answer(ws, got))
                    self.tasks.add(t)
                    t.add_done_callback(self.tasks.discard)
                if "toolResponse" in m:
                    self.tool_responses.append(m["toolResponse"])
                    got.set()
        except Exception:
            pass
        finally:
            self.closed.set()

    async def _answer(self, ws, got):
        def sc(**kw):
            return json.dumps({"serverContent": kw})

        def sound(pcm):
            return sc(modelTurn={"parts": [{"inlineData": {"mimeType": "audio/pcm;rate=24000",
                                                           "data": base64.b64encode(pcm).decode()}}]})  # fmt: skip

        if self.mode == "silent":
            return
        await ws.send(sc(inputTranscription={"text": "what's due this week"}))
        if self.mode in ("tool", "tool_then_silent", "tool_slow"):
            name, args = self.tool
            await ws.send(json.dumps({"toolCall": {"functionCalls": [{"id": "fc1", "name": name, "args": args}]}}))
            if self.mode == "tool_slow":  # (0.9.3) the turn the tool call closed, then its answer 3 s after the result
                await ws.send(sc(turnComplete=True))
            await asyncio.wait_for(got.wait(), 10)
            if self.mode == "tool_then_silent":  # (0.8.18) it acted, then never spoke
                return
            if self.mode == "tool_slow":
                await asyncio.sleep(3.0)
        if self.mode == "interrupt":
            await ws.send(sound(b"\x05\x00" * 48000))  # two seconds: still playing when it's interrupted
            await asyncio.sleep(0.3)
            await ws.send(sc(interrupted=True))
            await asyncio.sleep(0.1)
            await ws.send(sound(b"\x09\x00" * 4800))  # after the interruption: never played
            await ws.send(sc(turnComplete=True))
            return
        if self.mode == "slow":  # (0.9.2) still making the answer when it's talked over
            await ws.send(sound(ANSWER))
            await asyncio.sleep(2.0)
            await ws.send(sound(ANSWER))
            await ws.send(sc(turnComplete=True))
            return
        if self.mode == "chunks":  # (0.9.2) as Google streams it: many small chunks (0.1 s each)
            for _ in range(25):
                await ws.send(sound(b"\x03\x00" * 2400))
            await ws.send(sc(turnComplete=True))
            return
        if self.mode == "json":  # (0.9.2) it read a tool's result out
            await ws.send(sc(outputTranscription={"text": '{"now": "Thursday", "due_soon": []}'}))
            await ws.send(sound(ANSWER))
            await ws.send(sc(turnComplete=True))
            return
        await ws.send(sc(outputTranscription={"text": "It's due "}))
        await ws.send(sound(ANSWER))
        await ws.send(sc(outputTranscription={"text": "Friday."}))
        await ws.send(sound(ANSWER))
        await ws.send(sc(turnComplete=True))


class Output:
    """An add-on's output (a phone's speaker): records each piece and its rate; never plays."""

    def __init__(self, block_s=0.0):
        self.got, self.block_s, self.stops = [], block_s, []

    def __call__(self, pcm, sr, stop):
        self.got.append((pcm, sr))
        if self.block_s:
            self.stops.append(stop.wait(self.block_s))
        return True


@pytest.fixture
def lv(voice, monkeypatch):
    """Voice with Voice ID saying "owner", the real portal and ask_brain, the usual way faked (it answers at once,
    recorded), the voice made here recorded, and Live pointed at a fake server."""
    v = voice
    engine = Engine()
    monkeypatch.setattr(v, "tts", lambda: (engine, ""))
    v.engine = engine
    v.speaker.player = Speakers()
    v.out = Output()
    v.add_output(v.out)
    v.portal.send = v.ask_brain
    v.portal.speak = v._portal_speak
    v.who = Verdict("owner", "your voice", 0.9, 2.0)
    monkeypatch.setattr(v.voiceid, "on", lambda: True)
    monkeypatch.setattr(v.voiceid, "check", lambda *a, **k: v.who)
    monkeypatch.setattr(v, "face_gate", lambda: ("on", ""))  # Face presence on and enrolled, the camera looking
    v.text_way = []

    def handle(msg):
        v.text_way.append(msg.text)
        msg.respond("The usual way.")

    monkeypatch.setattr(v.app, "handle", handle)
    v.app.secrets.set("gemini.api_key", KEY)
    v.app.settings.set("voice.listen.live", True)
    monkeypatch.setattr(live_mod, "FIRST_S", 1.0)
    servers = []

    def fake(mode="speak", **kw):
        s = FakeLive(mode, **kw)
        servers.append(s)
        monkeypatch.setattr(live_mod, "LIVE_URL", s.url)
        return s

    v.fake = fake
    yield v
    v.live.close()
    for s in servers:
        s.stop()


def say(v, text="Kurooto, what's due this week?", faced=True, wake=False):
    end = time.monotonic()
    if faced:  # a face close to the camera and facing it while it was said
        nearby.set_facing(v.app, 1, 1, at=end - 0.5)
    return v.hear(Heard(speech=True, wake=wake, text=text, seconds=1.0, ended_at=end), SOUND)


def events(v, kind):
    return [e for e in v.app.events.tail(300) if e.get("kind") == kind]


# --------------------------------------------------------------------------------------------- the way in
def test_an_owners_addressed_turn_goes_to_live_and_its_sound_plays_through_the_speaker(lv, monkeypatch):
    srv = lv.fake()
    recorded = []
    chat = lv.app.modules["chat"]
    monkeypatch.setattr(lv.app, "is_on", lambda mid: True)
    monkeypatch.setattr(chat, "record_turn", lambda prompt, reply, jid="": recorded.append((prompt, reply)))
    reply = say(lv)
    assert reply == "It's due Friday."
    assert srv.turns == [SOUND]  # the stretch itself, in 250 ms messages
    assert lv.text_way == [] and lv.engine.said == []  # neither the usual AI nor the voice made here
    assert lv.out.got and all(sr == 24000 for _, sr in lv.out.got)
    assert b"".join(p for p, _ in lv.out.got) == ANSWER * 2
    assert recorded == [("what's due this week", "It's due Friday.")]  # the chat history carries it
    shown = [m for m in lv.app.live.sent if m["kind"] == "voice_text"]
    assert shown[-1]["text"] == "It's due Friday."
    assert any(m["kind"] == "voice_speak" for m in lv.app.live.sent)  # the being shows it speaking
    (ev,) = events(lv, "voice_timing")
    assert ev["live"] == 1 and ev["sent_ms"] <= ev["audio_ms"] <= ev["play_ms"]
    assert not lv.speaker.busy


def test_the_setup_is_the_calls_one_for_the_desk_and_the_key_never_in_the_address(lv):
    srv = lv.fake()
    say(lv)
    (setup,) = srv.setups
    assert setup["model"] == "models/" + lv.app.modules["calls"].live_models()[0]
    assert setup["generationConfig"]["responseModalities"] == ["AUDIO"]
    si = setup["systemInstruction"]["parts"][0]["text"]
    assert "%%NOW%%" not in si and "live voice call" not in si and "every call" not in si
    assert live_mod.DESK in si
    names = {d["name"] for d in setup["tools"][0]["functionDeclarations"]}
    assert {"search_notes", "call_now", "hold_calls"} <= names
    assert all("behavior" not in d for d in setup["tools"][0]["functionDeclarations"])
    assert setup["realtimeInputConfig"]["automaticActivityDetection"]["disabled"] is True
    assert srv.keys == [KEY] and KEY not in srv.paths[0]
    assert KEY not in json.dumps(lv.app.events.tail(300))


def test_chatter_unaddressed_guest_and_unsure_turns_never_connect(lv):
    srv = lv.fake()
    lv.judge.answers = ['{"class": "chatter", "confidence": 0.9}']
    assert lv.hear(Heard(speech=True, text="did you see the match last night", seconds=1.0), SOUND) is None
    lv.app.settings.set("voice.speaker_id.gate", False)  # the words are judged first, then the voice
    for decision in ("guest", "unsure"):
        lv.portal.close("test")
        lv.who = Verdict(decision, "not you", 0.2, 2.0)
        say(lv)
    assert len(lv.text_way) == 2  # the guest and the unsure voice: the usual way (chat only)
    assert srv.setups == [] and srv.turns == []


def test_without_voice_id_it_goes_the_usual_way(lv, monkeypatch):
    srv = lv.fake()
    monkeypatch.setattr(lv.voiceid, "on", lambda: False)
    assert say(lv) == "The usual way."
    assert srv.setups == []


def test_the_switch_off_is_the_old_path(lv):
    srv = lv.fake()
    lv.app.settings.set("voice.listen.live", False)
    assert say(lv) == "The usual way."
    assert lv.engine.said == ["The usual way."]
    assert srv.setups == [] and lv.live._pcm is None


# ------------------------------------------------------------------------------------------- the session
def test_follow_up_turns_reuse_the_session_and_the_portal_closing_closes_it(lv):
    srv = lv.fake()
    assert say(lv) == "It's due Friday."
    assert lv.portal.open
    assert say(lv, "And what about next week?") == "It's due Friday."
    assert len(srv.setups) == 1 and len(srv.turns) == 2
    assert not srv.closed.is_set()
    lv.portal.close("silence")
    assert srv.closed.wait(5)
    assert lv.live.sess is None
    say(lv)  # a new conversation: a new session
    assert len(srv.setups) == 2


# ----------------------------------------------------------------------------------------------- fallback
def test_a_refused_connection_falls_back_to_the_usual_way(lv):
    srv = lv.fake("refuse")
    assert say(lv) == "The usual way."
    assert lv.engine.said == ["The usual way."]  # spoken by the voice made here: never silence
    models = lv.app.modules["calls"].live_models()
    assert len(srv.setups) == len(models)  # each model in turn
    ev = events(lv, "voice_live")
    assert ev[-1]["fallback"] is True and ev[-1]["stage"] == "setup"
    assert set(lv.live.bad) == set(models)


def test_nothing_to_connect_to_falls_back(lv, monkeypatch):
    monkeypatch.setattr(live_mod, "LIVE_URL", "ws://127.0.0.1:9/ws/live")  # nothing listens there
    assert say(lv) == "The usual way."
    assert events(lv, "voice_live")[-1]["stage"] == "connect"


def test_no_key_falls_back(lv, monkeypatch):
    lv.fake()
    monkeypatch.setattr(lv.app.secrets, "get", lambda name, default=None: None)
    assert say(lv) == "The usual way."
    assert events(lv, "voice_live")[-1]["stage"] == "no key"


def test_no_first_sound_in_time_falls_back(lv, monkeypatch):
    srv = lv.fake("silent")
    monkeypatch.setattr(live_mod, "FIRST_S", 0.3)
    t0 = time.monotonic()
    assert say(lv) == "The usual way."
    assert time.monotonic() - t0 < 4
    assert srv.turns == [SOUND] and events(lv, "voice_live")[-1]["stage"] == "first sound"
    assert lv.live.sess is None and srv.closed.wait(5)


# ---------------------------------------------------------------------------------------------------- tools
def test_a_tool_call_runs_through_calls_run_tool(lv, monkeypatch):
    srv = lv.fake("tool")
    calls = lv.app.modules["calls"]
    ran = []
    done = "No calls until 18:00."
    monkeypatch.setattr(calls, "run_tool", lambda name, args, since="": ran.append((name, args)) or done)
    assert say(lv) == "It's due Friday."
    assert ran == [("hold_calls", {"until": "18:00"})]
    (resp,) = srv.tool_responses
    assert resp["functionResponses"] == [{"id": "fc1", "name": "hold_calls", "response": {"result": done}}]


def test_a_tool_run_then_a_failure_isn_t_done_again_the_usual_way(lv, monkeypatch):
    """(0.8.18) Live ran order_groceries, then no sound came: the usual way ran the request again and the second order
    said "An order is already going". Now the tool's own answer is said, and nothing goes to the AI or the add-ons."""
    lv.fake("tool_then_silent", tool=("order_groceries", {"items": "bread", "app": "zepto"}))
    monkeypatch.setattr(live_mod, "FIRST_S", 0.5)
    calls = lv.app.modules["calls"]
    ran = []
    started = "Filling your Zepto cart: bread. I'll ask you to approve."
    monkeypatch.setattr(calls, "run_tool", lambda name, args, since="": ran.append(name) or started)
    assert say(lv, "Kurooto, order bread from zepto") == live_mod.ACTED  # (0.9.2) a set line, never its result
    assert ran == ["order_groceries"] and lv.text_way == []  # never the usual way: no second order
    assert " ".join(lv.engine.said) == live_mod.ACTED  # said by the voice made here (0.9.2: its first clause first)
    ev = events(lv, "voice_live")[-1]
    assert ev["stage"] == "first sound" and ev["fallback"] is False and ev["tools"] == 1


def test_a_slow_tool_then_a_slow_answer_is_waited_for(lv, monkeypatch):
    """(0.9.3, a fix) Live called a tool and the turn fell back to the voice made here 2.1 s later, before Live had
    the result and spoke. Now the wait stops while the tool runs (2.5 s here) and starts again in full (FIRST_S) when
    the result is sent; the turnComplete sent with the tool call isn't the answer's end. Live answers 3 s after."""
    srv = lv.fake("tool_slow")
    monkeypatch.setattr(live_mod, "FIRST_S", 5.0)
    calls = lv.app.modules["calls"]
    monkeypatch.setattr(calls, "run_tool", lambda name, args, since="": time.sleep(2.5) or "No calls until 18:00.")
    assert say(lv) == "It's due Friday."
    assert lv.text_way == [] and lv.engine.said == []  # never the usual way, never the voice made here
    assert len(srv.tool_responses) == 1
    ev = events(lv, "voice_live")[-1]
    assert ev["stage"] == "answered"


def test_a_guarded_tool_asks_instead_of_running(lv, monkeypatch):
    srv = lv.fake("tool", tool=("call_now", {"reason": "the lab"}))
    calls = lv.app.modules["calls"]
    ran, placed = [], []
    monkeypatch.setattr(calls, "run_tool", lambda name, args, since="": ran.append(name))
    monkeypatch.setattr(calls, "place", lambda *a, **k: placed.append(a))
    say(lv)
    assert ran == [] and placed == []
    asked = lv.app.ask.pending(kind="approval", source="tap")
    assert len(asked) == 1 and (asked[0].get("hook_payload") or {}).get("tool") == "call_now"
    result = srv.tool_responses[0]["functionResponses"][0]["response"]["result"]
    assert result.startswith("Not done yet")


def test_live_can_never_answer_an_approval_at_the_desk(lv, monkeypatch):
    """(0.8.17) answer_approval came with the call's tools: a guarded action Live asked for could be approved by Live
    itself, no Voice ID, no tap. It isn't offered, and asked for anyway it only points to the tap."""
    from kurooto.modules.voice import live as live_mod

    calls = lv.app.modules["calls"]
    ran = []
    monkeypatch.setattr(calls, "run_tool", lambda name, args, since="": ran.append(name))
    out = lv.live.run_tool("answer_approval", {"id": "x", "decision": "Approve"})
    assert ran == [] and "tap" in out
    assert "answer_approval" in live_mod.DESK_NEVER
    assert "Voice ID recognised their voice" in live_mod.DESK and "never see the camera" in live_mod.DESK


# -------------------------------------------------------------------------------------------- interrupted
def test_live_interrupted_stops_playback(lv):
    srv = lv.fake("interrupt")
    lv.out.block_s = 3.0  # a phone playing the piece: it waits for the stop
    t0 = time.monotonic()
    say(lv)
    assert time.monotonic() - t0 < 2.5  # stopped, not played out
    assert lv.out.stops and lv.out.stops[0] is True  # the piece playing was told to stop
    assert all(b"\x09\x00" not in p for p, _ in lv.out.got)  # what came after the interruption never played
    assert lv.engine.said == []  # not said again by the voice made here
    assert srv.turns == [SOUND]


# ------------------------------------------------------------------------------- only when looked at, too
def test_the_wake_word_turn_without_a_face_goes_the_usual_way(lv):
    srv = lv.fake()
    assert say(lv, "Kurooto what's due this week", faced=False, wake=True) == "The usual way."
    assert lv.engine.said == ["The usual way."] and srv.setups == []


def test_a_blind_camera_with_fallback_voice_goes_the_usual_way(lv, monkeypatch):
    srv = lv.fake()
    monkeypatch.setattr(lv, "face_gate", lambda: ("blind", "paused"))
    assert lv.setting("listen.need_face_fallback") == "voice"
    assert say(lv, faced=False) == "The usual way."
    assert srv.setups == []


def test_need_face_off_goes_the_usual_way(lv, monkeypatch):
    srv = lv.fake()
    monkeypatch.setattr(lv, "face_gate", lambda: ("off", ""))
    assert say(lv) == "The usual way."
    assert srv.setups == []


def test_a_face_seen_for_the_turn_goes_to_live(lv):
    srv = lv.fake()
    assert say(lv, faced=True) == "It's due Friday."
    assert len(srv.turns) == 1


# ------------------------------------------------------------------------------------- after the turn (0.9.0)
def test_a_live_turn_is_noticed_like_a_typed_message(lv, monkeypatch):
    """L36: a Live turn counts as a message from you (message_in) and goes past the same observers App.handle runs;
    voice.listen.live_after off keeps only the message_in."""
    from kurooto.core import infer, threads
    from kurooto.mind import pest, tone

    lv.fake()
    seen = []
    monkeypatch.setattr(tone, "seen", lambda app, t: seen.append(("tone", t)))
    monkeypatch.setattr(pest, "heard", lambda app, t: seen.append(("pest", t)))
    monkeypatch.setattr(infer, "observe", lambda app, t, via="chat": seen.append(("infer", t, via)))
    monkeypatch.setattr(threads, "observe", lambda app, t, via="chat": seen.append(("threads", t)))
    assert say(lv) == "It's due Friday."
    assert [e["via"] for e in events(lv, "message_in")][-1] == "voice_live"
    assert [s[0] for s in seen] == ["tone", "pest", "infer", "threads"]
    assert seen[2] == ("infer", "what's due this week", "voice_live")
    lv.app.settings.set("voice.listen.live_after", False)
    seen.clear()
    n = len(events(lv, "message_in"))
    say(lv)
    assert seen == [] and len(events(lv, "message_in")) == n + 1  # the message_in itself is a fix, never off


# ------------------------------------------------------------------------------ everyone (0.9.2, live_everyone)
@pytest.fixture
def ev(lv, monkeypatch):
    """Live with voice.listen.live_everyone on; non-owner turns judged by words first (as Voice ID's gate off does);
    the guest path's hourly count starts empty."""
    from kurooto.core import guest

    lv.app.settings.set("voice.listen.live_everyone", True)
    lv.app.settings.set("voice.speaker_id.gate", False)
    lv.app.settings.set("you.name", "Mira Okafor")
    monkeypatch.setattr(guest, "_times", {})
    return lv


MOON = "Kurooto, how far away is the moon?"


def _who(v, decision):
    v.who = Verdict(decision, "not you" if decision != "owner" else "your voice", 0.2, 2.0)


def test_everyone_an_owners_turn_without_a_face_goes_to_his_session(ev, monkeypatch):
    srv = ev.fake()
    monkeypatch.setattr(ev, "face_gate", lambda: ("off", ""))  # let through without a face seen
    assert say(ev, MOON, faced=False) == "It's due Friday."
    (setup,) = srv.setups
    si = setup["systemInstruction"]["parts"][0]["text"]
    assert live_mod.DESK_ANY in si and live_mod.DESK not in si  # it doesn't claim a face was seen
    assert {"search_notes", "hold_calls"} <= {d["name"] for d in setup["tools"][0]["functionDeclarations"]}
    assert ev.live.sess is not None and ev.live.gsess is None


def test_everyone_an_unsure_turn_gets_a_guest_session_with_nothing_of_the_owners(ev, monkeypatch):
    srv = ev.fake()
    recorded, after = [], []
    monkeypatch.setattr(ev.app.modules["chat"], "record_turn", lambda *a, **k: recorded.append(a))
    monkeypatch.setattr(ev.app, "after_turn", lambda *a, **k: after.append(a))
    _who(ev, "unsure")
    reply = say(ev, MOON, faced=False)
    assert reply.endswith("It's due Friday.")
    assert ev.text_way == [] and ev.engine.said == []  # Live said it; nothing went the usual way
    (setup,) = srv.setups
    assert "tools" not in setup
    si = setup["systemInstruction"]["parts"][0]["text"]
    assert "NOT its owner" in si and live_mod.GUEST_DESK in si
    assert "Mira" not in si and "Okafor" not in si  # nothing of his: not even his name
    assert UNSURE in si  # the tell_guests line, once
    assert recorded == [] and after == []  # never his chat history or Brain
    assert ev.live.gsess is not None and ev.live.sess is None
    (ans,) = [e for e in events(ev, "voice_live") if e["stage"] == "answered"]
    assert ans["who"] == "guest" and set(ans) <= {"kind", "ts", "stage", "model", "turns", "who", "at", "id"}


def test_everyone_a_guests_tool_call_never_runs(ev, monkeypatch):
    srv = ev.fake("tool", tool=("call_now", {"reason": "the lab"}))
    calls = ev.app.modules["calls"]
    ran = []
    monkeypatch.setattr(calls, "run_tool", lambda name, args, since="": ran.append(name))
    monkeypatch.setattr(ev.live, "run_tool", lambda name, args: ran.append(name))
    _who(ev, "guest")
    say(ev, MOON)
    assert ran == [] and ev.app.ask.pending(kind="approval", source="tap") == []
    (resp,) = srv.tool_responses
    assert resp["functionResponses"][0]["response"]["result"] == live_mod.NO_TOOLS


def test_everyone_the_owners_verified_turn_switches_back_and_never_shares_the_guest_session(ev):
    srv = ev.fake()
    _who(ev, "unsure")
    say(ev, MOON)
    g = ev.live.gsess
    _who(ev, "owner")
    assert say(ev, MOON) == "It's due Friday."
    assert ev.live.gsess is None and g.closed  # the guest session ended before his turn
    assert ev.live.sess is not None and ev.live.sess is not g
    assert len(srv.setups) == 2 and "tools" not in srv.setups[0] and "tools" in srv.setups[1]
    _who(ev, "guest")
    say(ev, MOON)  # someone else again: a new guest session, never his
    assert len(srv.setups) == 3 and "tools" not in srv.setups[2]
    assert ev.live.gsess is not ev.live.sess


def test_everyone_the_guest_rules_come_first(ev, monkeypatch):
    from kurooto.core import guest

    srv = ev.fake()
    _who(ev, "guest")
    monkeypatch.setattr(guest, "kind", lambda app, text: "action" if "alarm" in text else "")
    say(ev, "Kurooto, set an alarm for seven")
    assert ev.text_way and srv.setups == []  # the usual way refuses it, as the text guest path does
    ev.portal.close("test")
    ev.app.settings.set("voice.speaker_id.guest_per_hour", 1)
    say(ev, MOON)
    ev.portal.close("test")
    n = len(ev.text_way)
    say(ev, MOON)  # over the hour's cap: the usual way (which says it's busy)
    assert len(srv.setups) == 1 and len(ev.text_way) == n + 1


def test_everyone_a_failed_guest_session_goes_the_usual_way_and_isnt_counted_twice(ev):
    from kurooto.core import guest

    ev.fake("refuse")
    _who(ev, "guest")
    reply = say(ev, MOON)
    assert "The usual way." in reply and ev.engine.said
    assert not guest._times.get(id(ev.app))  # given back: the usual way counts it
    assert events(ev, "voice_live")[-1]["fallback"] is True


def test_everyone_without_voice_id_every_turn_is_a_guests(ev, monkeypatch):
    srv = ev.fake()
    monkeypatch.setattr(ev.voiceid, "on", lambda: False)
    assert say(ev, MOON) == "It's due Friday."
    assert "tools" not in srv.setups[0]


def test_everyone_owner_only_at_all_never_connects(ev):
    srv = ev.fake()
    ev.app.settings.set("voice.speaker_id.mode", "owner_only_at_all")
    _who(ev, "guest")
    say(ev, MOON)
    assert srv.setups == []


def test_everyone_off_keeps_the_old_rules(ev, monkeypatch):
    srv = ev.fake()
    ev.app.settings.set("voice.listen.live_everyone", False)
    _who(ev, "unsure")
    say(ev, MOON)
    assert srv.setups == [] and len(ev.text_way) == 1
    ev.portal.close("test")
    _who(ev, "owner")
    monkeypatch.setattr(ev, "face_gate", lambda: ("off", ""))  # let through without a face seen
    assert say(ev, MOON) == "The usual way."  # and an owner's turn still needs the face
    assert srv.setups == []


# ------------------------------------------------------------------------- 0.9.2: tool results, talking over it
def test_a_read_then_a_failure_goes_the_usual_way_and_never_says_the_result(lv, monkeypatch):
    """ "can you hear me?": Live called pending_items, then no sound came, and the tool's JSON was said and shown as
    the answer. A tool that only reads is safe to do again: the usual way answers; the result is never the answer."""
    lv.fake("tool_then_silent", tool=("pending_items", {}))
    monkeypatch.setattr(live_mod, "FIRST_S", 0.5)
    calls = lv.app.modules["calls"]
    data = {"now": "Thursday 29 October", "checkins_today": [], "due_soon": [{"title": "Organic Chemistry"}]}
    monkeypatch.setattr(calls, "run_tool", lambda name, args, since="": data)
    reply = say(lv, "Kurooto, can you hear me?")
    assert reply == "The usual way." and lv.engine.said == ["The usual way."]
    assert "due_soon" not in json.dumps(lv.app.live.sent) and "{" not in "".join(lv.engine.said)
    ev = events(lv, "voice_live")[-1]
    assert ev["fallback"] is True and ev["tools"] == 1


def test_words_that_read_as_a_tools_json_are_never_the_shown_answer(lv, monkeypatch):
    lv.fake("json")
    recorded = []
    monkeypatch.setattr(lv.app.modules["chat"], "record_turn", lambda *a, **k: recorded.append(a))
    assert say(lv) == live_mod.ALOUD
    assert "due_soon" not in json.dumps(lv.app.live.sent) and recorded == []


def test_the_setup_says_results_are_data_and_a_greeting_needs_no_tool(lv):
    srv = lv.fake()
    say(lv)
    si = srv.setups[0]["systemInstruction"]["parts"][0]["text"]
    assert live_mod.TOOL_RULES in si and "can you hear me" in si


def test_an_answer_cut_off_is_interrupted_at_googles_end_too(lv):
    """Barge-in or a stop cut the answer: Live is told an activity started (which interrupts the answer it's still
    making), and the next turn's sound continues that activity instead of starting another."""
    srv = lv.fake("slow")
    lv.out.block_s = 3.0
    threading.Timer(0.3, lv.speaker.stop).start()  # talked over: it stops
    say(lv)
    for _ in range(100):
        if srv.starts == 2:
            break
        time.sleep(0.02)
    assert srv.starts == 2 and lv.live.sess.active  # the turn's own, then the interruption
    lv.out.block_s = 0
    say(lv, "And what about next week?")
    assert srv.starts == 2 and len(srv.turns) == 2 and not lv.live.sess.active


# ------------------------------------------------------------------------ 0.9.2: an add-on's output, gapless
class Timed:
    """An add-on's output that plays in real time (sleeps the piece's length), recording each piece's size and when
    its call began and ended; with ahead_s it takes the next piece before the one playing ends."""

    def __init__(self, ahead_s=0.0):
        if ahead_s:
            self.ahead_s = ahead_s
        self.calls = []
        self.end = 0.0  # a piece handed early starts when the one before it ends (as Web Audio's start(when))
        self.lock = threading.Lock()

    def __call__(self, pcm, sr, stop):
        t0 = time.monotonic()
        with self.lock:
            self.end = max(t0, self.end) + len(pcm) / 2 / sr
            end = self.end
        stop.wait(max(0.0, end - t0))
        self.calls.append((len(pcm), t0, time.monotonic(), stop.is_set()))
        return True


def test_lives_small_chunks_go_to_an_add_on_output_in_pieces_of_about_a_second(lv):
    lv.fake("chunks")
    out = Timed()
    lv.add_output(out)  # the newest output first: it takes the sound
    say(lv)
    sizes = [n for n, *_ in sorted(out.calls, key=lambda c: c[1])]
    assert sum(sizes) == 25 * 4800  # all of it, flushed at the end
    assert sizes[0] >= live_mod.OUT_FIRST_PIECE and all(n >= live_mod.OUT_PIECE for n in sizes[1:-1])
    assert len(sizes) <= 3  # 2.5 s in three pieces at most, not 25


def test_a_gapless_output_gets_the_next_piece_before_the_one_playing_ends(voice):
    sp = voice.speaker
    out = Timed(ahead_s=0.3)
    voice.add_output(out)
    piece = b"\x01\x00" * 12000  # 0.5 s at 24 kHz
    t0 = time.monotonic()
    with sp.lock:
        sp.busy = True
        for _ in range(4):
            assert sp.say_piece(piece, 24000)
        sp.drain()
        sp.busy = False
    took = time.monotonic() - t0
    calls = sorted(out.calls, key=lambda c: c[1])
    assert len(calls) == 4
    for a, b in zip(calls, calls[1:], strict=False):
        assert b[1] < a[2]  # handed over while the one before was still playing: no gap to fetch it in
    assert took >= 0.5 and not sp._ahead  # drain waited for the last one to play


def test_a_stop_reaches_every_piece_handed_ahead(voice):
    sp = voice.speaker
    out = Timed(ahead_s=2.5)
    voice.add_output(out)
    with sp.lock:
        sp.busy = True
        sp.say_piece(b"\x01\x00" * 24000, 24000)  # 1 s each: both handed over at once
        sp.say_piece(b"\x01\x00" * 24000, 24000)
        sp.stop()
        sp.drain(5)
        sp.busy = False
    assert len(out.calls) == 2 and all(c[3] for c in out.calls)  # both told to stop

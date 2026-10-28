"""Voice speed (0.8.16, modules/voice/fast.py): each turn timed from the last word (numbers only), the soft
acknowledgement while the AI thinks, the answer spoken as it's written (Claude Code's stream-json, an API's
server-sent events, through the queue's turn_options), a quicker AI for plain chat, and the warm-up. Fakes only: no
sound device, microphone, camera or model is touched, and no real AI is asked."""

# ruff: noqa: F811 (the fixtures imported from test_voice are taken as arguments)

import json
import math
import struct
import sys
import threading
import time

import pytest

from kurooto.modules.voice import fast
from kurooto.modules.voice.gate import Heard
from kurooto.providers import claude as claude_mod
from kurooto.providers.base import Task
from tests.unit.test_voice import Engine, Speakers, Tts, voice  # noqa: F401 (pytest fixtures)


class Listener:
    def running(self):
        return True

    def stop(self):
        pass


@pytest.fixture
def sv(voice, monkeypatch):
    """Voice with a speech engine that records what it's given, this computer's player faked, the real portal path."""
    engine = Engine()
    monkeypatch.setattr(voice, "tts", lambda: (engine, ""))
    voice.app.settings.set("voice.speak.join_sentences", False)
    voice.speaker.player = Speakers()
    voice.engine = engine
    voice.portal.send = voice.ask_brain
    voice.portal.speak = voice._portal_speak
    return voice


def events(v, kind):
    return [e for e in v.app.events.tail(200) if e.get("kind") == kind]


def queued_job(v, monkeypatch, answer="It's due Friday.", wait=None):
    """app.handle as Chat would: one request queued (so turn_options applies); the wait for it faked."""

    def handle(msg):
        msg.job = v.app.jobs.submit(msg.text, quiet=True)

    monkeypatch.setattr(v.app, "handle", handle)
    monkeypatch.setattr(v, "_wait_job", wait or (lambda msg, stream=None: answer))


# ------------------------------------------------------------------------------------------------------ timing
def test_a_turn_is_timed_from_the_last_word_in_numbers_only(sv, monkeypatch):
    queued_job(sv, monkeypatch)
    sv.hear(Heard(speech=True, text="Kurooto, what's due this week?", ended_at=time.monotonic() - 1.0))
    (ev,) = events(sv, "voice_timing")
    for k in ("text_ms", "gate_ms", "sent_ms", "first_text_ms", "answer_ms", "audio_ms", "play_ms"):
        assert isinstance(ev[k], int) and ev[k] >= 1000, k
    assert ev["text_ms"] <= ev["gate_ms"] <= ev["sent_ms"] <= ev["answer_ms"] <= ev["audio_ms"] <= ev["play_ms"]
    assert "face_ms" in ev and ev["streamed"] == 0
    assert all(isinstance(v, (int, float)) for k, v in ev.items() if k not in ("kind", "at", "ts", "t"))
    assert "due" not in json.dumps(ev)  # never words
    med = sv.speed()
    assert med["turns"] == 1 and med["play_ms"] == ev["play_ms"]
    assert sv.status()["speed"]["turns"] == 1
    assert "Speed (median of 1 turn, from your last word)" in sv._cmd(None, "")


def test_timing_is_its_own_switch(sv, monkeypatch):
    sv.app.settings.set("voice.listen.timing", False)
    queued_job(sv, monkeypatch)
    sv.hear(Heard(speech=True, text="Kurooto, what's due this week?", ended_at=time.monotonic()))
    assert events(sv, "voice_timing") == [] and sv.speed()["turns"] == 0
    assert "Speed" not in sv._cmd(None, "")


def test_medians_and_the_line():
    rows = [{"text_ms": 500, "play_ms": 4000}, {"text_ms": 700, "play_ms": 6000}, {"text_ms": 900}]
    med = fast.medians(rows)
    assert med == {"turns": 3, "text_ms": 700, "play_ms": 6000}
    assert fast.line(med) == "Speed (median of 3 turns, from your last word): words 0.7 s, playing 6.0 s."
    assert fast.line(fast.medians([])) == ""


def test_the_face_check_doesnt_wait_when_a_face_was_already_seen(sv, monkeypatch):
    from kurooto.core import nearby
    from kurooto.modules.voice.gate import ADDRESSED, Decision

    monkeypatch.setattr(sv, "face_gate", lambda: ("on", ""))
    waited = []
    sv._face_sleep = waited.append
    end = time.monotonic()  # just ended: its whole window is still ahead
    nearby.set_facing(sv.app, 1, 1, at=end - 0.5)  # a face close and facing it while it was said
    turn = {"end": end}
    d = sv._timed_face_check(Heard(speech=True, seconds=2.0, ended_at=end), Decision(ADDRESSED, 0.9, "its name"), turn)
    assert d.addressed and waited == [] and turn["face_ms"] < 200


# ------------------------------------------------------------------------------------------------ streaming
def test_the_answer_is_spoken_as_it_is_written(sv, monkeypatch):
    spoke_early = threading.Event()

    def wait(msg, stream=None):
        tell = sv.app.jobs.hooks[msg.job]["on_text"]
        tell(("0:claude", "m1"), "Sure.")  # no sentence ends yet: nothing is said
        time.sleep(0.05)
        assert sv.engine.said == []
        tell(("0:claude", "m1"), "Sure. The lab")
        for _ in range(200):
            if sv.engine.said:
                spoke_early.set()
                break
            time.sleep(0.01)
        tell(("0:claude", "m1"), "Sure. The lab is at nine. Bring")
        return "Sure. The lab is at nine. Bring the report."

    queued_job(sv, monkeypatch, wait=wait)
    reply = sv.hear(Heard(speech=True, text="Kurooto, when is the lab?", ended_at=time.monotonic()))
    assert reply == "Sure. The lab is at nine. Bring the report."
    assert spoke_early.is_set()  # it began speaking before the answer was finished
    assert sv.engine.said == ["Sure.", "The lab is at nine.", "Bring the report."]  # each once, in order
    (ev,) = events(sv, "voice_timing")
    assert ev["streamed"] == 1 and ev["first_text_ms"] <= ev["answer_ms"]
    assert not sv.speaker.busy


def test_words_before_a_tool_call_are_their_own_message(sv, monkeypatch):
    def wait(msg, stream=None):
        tell = sv.app.jobs.hooks[msg.job]["on_text"]
        tell(("0:claude", "m1"), "Let me check your notes. ")
        tell(("0:claude", "m2"), "It's at nine. ")
        return "It's at nine."

    queued_job(sv, monkeypatch, wait=wait)
    sv.hear(Heard(speech=True, text="Kurooto, when is the lab?", ended_at=time.monotonic()))
    assert sv.engine.said == ["Let me check your notes.", "It's at nine."]


def test_a_stand_ins_answer_is_spoken_whole(sv, monkeypatch):
    def wait(msg, stream=None):
        sv.app.jobs.hooks[msg.job]["on_text"](("0:claude", "m1"), "Half an answer. ")
        return "Another AI answered this."

    queued_job(sv, monkeypatch, wait=wait)
    sv.hear(Heard(speech=True, text="Kurooto, what's up?", ended_at=time.monotonic()))
    assert sv.engine.said == ["Half an answer.", "Another AI answered this."]


def test_without_streaming_the_answer_is_spoken_at_the_end(sv, monkeypatch):
    sv.app.settings.set("voice.speak.stream", False)
    seen = {}

    def wait(msg, stream=None):
        seen["hooks"] = dict(sv.app.jobs.hooks.get(msg.job) or {})
        return "It's at nine."

    queued_job(sv, monkeypatch, wait=wait)
    sv.hear(Heard(speech=True, text="Kurooto, when is the lab?", ended_at=time.monotonic()))
    assert "on_text" not in seen["hooks"] and "on_start" in seen["hooks"]
    assert sv.engine.said == ["It's at nine."]


def test_stopping_mid_answer_says_nothing_more_and_stops_waiting(sv, monkeypatch):
    st = fast.Stream(sv.speaker, {})
    st.cancel()
    msg = type("M", (), {"job": sv.app.jobs.submit("a question", quiet=True)})()
    t0 = time.monotonic()
    assert sv._wait_job(msg, st) == ""  # the request is still queued: it stops waiting at once
    assert time.monotonic() - t0 < 2
    st.feed("k", "More words. ")
    st.finish("More words.")
    assert sv.engine.said == []


def test_the_stream_waits_for_a_code_block_and_keeps_the_length_limit(sv):
    sv.app.settings.set("voice.speak.max_chars", 30)
    st = fast.Stream(sv.speaker, {})
    st.feed("k", "Run this. ```x = 1. y = 2. ")
    assert st.raw == ["Run this. "]  # the code block isn't cut in the middle
    st.feed("k", "Run this. ```x = 1. y = 2.``` It prints three. And then a lot more is said. ")
    st.finish("Run this. ```x = 1. y = 2.``` It prints three. And then a lot more is said.")
    assert sv.engine.said[-1] == "The rest is on screen."
    assert sum(len(p) for p in sv.engine.said[:-1]) <= 30 + len("Run this.")


def test_the_first_clause_is_spoken_before_its_sentence_ends(sv):
    """(0.8.17) Nothing said yet: a clause 20 characters or more in goes first; after that, whole sentences."""
    st = fast.Stream(sv.speaker, {})
    st.feed("k", "Well, ")
    assert st.raw == []  # too short to go alone
    st.feed("k", "Mostly reading about Fourier series, and ")
    assert st.raw == ["Mostly reading about Fourier series, "]
    st.feed("k", "Mostly reading about Fourier series, and some tea, honestly")
    assert st.raw == ["Mostly reading about Fourier series, "]  # later clauses wait for their sentence
    st.finish("Mostly reading about Fourier series, and some tea, honestly.")
    assert " ".join("".join(st.raw).split()) == "Mostly reading about Fourier series, and some tea, honestly."


def test_a_spoken_turn_s_routing_is_timed_and_skips_button_offers(sv, monkeypatch):
    """(0.8.17) App.handle marks its steps on a spoken turn (numbers in voice_timing); the offers that are only
    buttons (two close readings, a feature that's off) aren't waited for by voice."""
    from kurooto.core import repair, turnon
    from kurooto.modules.base import Incoming

    offered = []
    monkeypatch.setattr(repair, "offer", lambda *a, **k: offered.append("repair"))
    monkeypatch.setattr(turnon, "offer", lambda *a, **k: offered.append("turnon"))
    msg = Incoming(text="something nobody understands at all", via="voice", voice=True, timing={},
                   respond=lambda *a, **k: None)  # fmt: skip
    sv.app.handle(msg)
    assert {"mind", "intents"} <= set(msg.timing) and all(isinstance(v, float) for v in msg.timing.values())
    assert offered == []  # never offered by voice
    typed = Incoming(text="something nobody understands at all", via="telegram", respond=lambda *a, **k: None)
    sv.app.handle(typed)
    assert typed.timing is None and offered  # only spoken turns are timed; typed ones still get the offers


# --------------------------------------------------------------------------------------------- acknowledgement
def test_the_tone_is_short_soft_and_clickless():
    pcm = fast.tone(24000)
    xs = struct.unpack(f"<{len(pcm) // 2}h", pcm)
    assert len(xs) == int(24000 * 0.24)
    assert abs(xs[0]) < 50 and abs(xs[-1]) < 50
    assert max(abs(x) for x in xs) / 32768 < 0.15
    rms = math.sqrt(sum(x * x for x in xs) / len(xs)) / 32768
    assert 0.01 < rms < 0.08


class Out:
    def __init__(self):
        self.got = []

    def __call__(self, pcm, sr, stop):
        self.got.append((len(pcm), sr))
        return True


def test_the_acknowledgement_plays_through_the_same_output_unless_the_answer_is_coming(sv):
    out = Out()
    sv.add_output(out)
    sv._ack_sleep = lambda s: None
    turn = {"end": time.monotonic()}
    sv._ack_play("tone", turn)
    assert out.got == [(len(fast.tone()), fast.ACK_RATE)] and "ack" in turn
    assert "play" not in turn  # the acknowledgement isn't the answer's first sound
    sv._ack_play("tone", {"answer": 1.0})
    assert len(out.got) == 1


def test_the_acknowledgement_is_only_for_heard_turns_and_has_a_switch(sv, monkeypatch):
    started = []
    monkeypatch.setattr(sv, "_ack_play", lambda how, turn: started.append(how))
    real_thread = threading.Thread

    class Now(real_thread):
        def start(self):
            self.run()

    monkeypatch.setattr(threading, "Thread", Now)
    sv._ack({})
    assert started == []  # not listening (a typed or test turn): no sound
    sv.listener = Listener()
    sv._ack({})
    assert started == ["tone"]
    sv.app.settings.set("voice.speak.ack", "off")
    sv._ack({})
    assert started == ["tone"]
    sv.listener = None


def test_the_word_is_made_once_and_the_tone_stands_in(sv, monkeypatch):
    sv._ack_sleep = lambda s: None
    a = sv._ack_sound("word")
    b = sv._ack_sound("word")
    assert a is b and sv.engine.said == [fast.ACK_WORD]
    monkeypatch.setattr(sv, "tts", lambda: (None, "no voice"))
    assert sv._ack_sound("word")[1] == fast.ACK_RATE


# ----------------------------------------------------------------------------------------- a faster brain
def test_only_plain_chat_counts(voice):
    app = voice.app
    for text in ("tell me a joke", "why is the sky blue", "how far is the moon"):
        assert fast.chat_only(app, text), text
    for text in ("what's due tomorrow", "remind me at six", "/voice", "open my notes", "what's the weather", ""):
        assert not fast.chat_only(app, text), text


def test_turn_options_pin_the_first_request_only(voice):
    jobs = voice.app.jobs
    with jobs.turn_options(brain="ollama", text_only=True, effort="low", on_start=print) as got:
        first = jobs.submit("tell me a joke", quiet=True)
        second = jobs.submit("something else", quiet=True)
    third = jobs.submit("and after", quiet=True)
    assert got["jid"] == first
    row = lambda j: jobs._read("select brain_req, text_only, effort_req from jobs where id=?", (j,))  # noqa: E731
    assert tuple(row(first)) == ("ollama", 1, "low")
    assert tuple(row(second)) == (None, 0, "auto") and tuple(row(third)) == (None, 0, "auto")
    assert set(jobs.hooks[first]) == {"on_start"} and second not in jobs.hooks


def test_fast_brain_picks_and_same_changes_nothing(voice, monkeypatch):
    from kurooto import providers

    class Local:
        id = "ollama"

    monkeypatch.setattr(providers, "local", lambda app: Local())
    assert voice._fast_choice("tell me a joke") is None  # "same": your AI as before
    voice.app.settings.set("voice.listen.fast_brain", "local")
    assert voice._fast_choice("tell me a joke") == ("ollama", {"brain": "ollama", "text_only": True, "effort": "low"})
    assert voice._fast_choice("what's due tomorrow") is None  # needs your things: the main AI
    monkeypatch.setattr(providers, "local", lambda app: None)
    assert voice._fast_choice("tell me a joke") is None


def test_fastest_tries_each_then_keeps_the_quickest(monkeypatch):
    pick = fast.FastPick()
    cands = [("gemini", {"brain": "gemini"}), ("ollama", {"brain": "ollama"}), ("main", {"text_only": True})]
    monkeypatch.setattr(fast.FastPick, "candidates", staticmethod(lambda app: cands))
    assert pick.pick(None)[0] == "gemini"
    pick.note("gemini", 1.5)
    assert pick.pick(None)[0] == "ollama"
    pick.note("ollama", 0.6)
    pick.note("main", 3.0)
    assert pick.pick(None)[0] == "ollama"
    for _ in range(3):
        pick.note("ollama", 4.0)
    assert pick.pick(None)[0] == "gemini"  # it got slower: the median moves


# ------------------------------------------------------------------------------------------------- warm-up
def test_listening_start_warms_the_engines_once(sv, monkeypatch):
    class Stt:
        def __init__(self):
            self.n = 0

        def text(self, pcm):
            self.n += 1
            return ""

    stt = Stt()
    monkeypatch.setattr(sv, "stt", lambda: stt)
    sv._stt_key = ("base", "", "Kurooto")
    sv._tts_key = ("kokoro", "", 1.0)
    for _ in range(2):
        sv._warm_stt()
        sv._warm_voice()
    assert stt.n == 1 and sv.engine.said == ["Okay."]  # made, never played
    assert sv.speaker.player.got == []
    assert {e["part"] for e in events(sv, "voice_warm")} == {"transcriber", "voice"}


def test_warm_up_has_switches(sv, monkeypatch):
    calls = []
    monkeypatch.setattr(sv, "_warm_voice", lambda: calls.append("voice"))
    monkeypatch.setattr(sv, "_warm_brain", lambda: calls.append("brain"))
    real_thread = threading.Thread

    class Now(real_thread):
        def start(self):
            self.run()

    monkeypatch.setattr(threading, "Thread", Now)
    sv.app.settings.set("voice.listen.warm_up", False)
    sv.app.settings.set("voice.listen.warm_brain", False)
    sv._warm()
    assert calls == [] and sv._work.empty()
    sv.app.settings.set("voice.listen.warm_up", True)
    sv.app.settings.set("voice.listen.warm_brain", True)
    sv._warm()
    assert calls == ["voice", "brain"] and sv._work.get_nowait() is not None
    sv._warm()  # the brain at most every WARM_BRAIN_S
    assert calls == ["voice", "brain", "voice"]


# ----------------------------------------------------------------------------------- Claude Code's stream-json
def stream_lines():
    ev = lambda e: json.dumps({"type": "stream_event", "event": e})  # noqa: E731
    return [
        json.dumps({"type": "system", "subtype": "init"}),
        ev({"type": "message_start", "message": {"id": "m1"}}),
        ev({"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Let me look. "}}),
        json.dumps(
            {"type": "assistant", "message": {"id": "m1", "content": [{"type": "text", "text": "Let me look. "}]}}
        ),
        json.dumps(
            {
                "type": "assistant",
                "parent_tool_use_id": "t1",
                "message": {"id": "s1", "content": [{"type": "text", "text": "a subagent"}]},
            }
        ),  # fmt: skip
        ev({"type": "message_start", "message": {"id": "m2"}}),
        ev({"type": "content_block_delta", "delta": {"type": "text_delta", "text": "It's at"}}),
        ev({"type": "content_block_delta", "delta": {"type": "text_delta", "text": " nine."}}),
        "not json",
        json.dumps(
            {
                "type": "result",
                "result": "It's at nine.",
                "total_cost_usd": 0.001,
                "modelUsage": {"claude-haiku": {"costUSD": 0.001}},
            }
        ),  # fmt: skip
    ]


def test_stream_json_lines_become_messages():
    got = []
    lines = claude_mod.Lines(lambda k, t: got.append((k, t)))
    for line in stream_lines():
        lines.line(line)
    assert got == [("m1", "Let me look. "), ("m2", "It's at"), ("m2", "It's at nine.")]
    whole = []
    lines = claude_mod.Lines(lambda k, t: whole.append((k, t)))  # without partial messages: each whole message
    lines.line(json.dumps({"type": "assistant", "message": {"id": "a", "content": [{"type": "text", "text": "Hi."}]}}))
    lines.line(json.dumps({"type": "assistant", "message": {"id": "a", "content": [{"type": "tool_use"}]}}))
    assert whole == [("a", "Hi.")]


def test_claude_code_streams_only_when_asked(tmp_path, monkeypatch):
    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path / "home"))
    script = tmp_path / "fake_claude.py"
    script.write_text(
        "import sys, time\n"
        "sys.stdin.read()\n"
        f"lines = {stream_lines()!r}\n"
        "for i, line in enumerate(lines):\n"
        "    print(line, flush=True)\n"
        "    if i == 2:\n"
        "        time.sleep(0.4)\n",
        encoding="utf-8",
    )
    brain = claude_mod.ClaudeCode(exe=[sys.executable, str(script)])
    plain = brain.args(Task(prompt="hi", cwd=tmp_path), tmp_path)
    assert "stream-json" not in plain and "--include-partial-messages" not in plain
    got = []
    task = Task(prompt="hi", cwd=tmp_path, timeout_s=60, on_text=lambda k, t: got.append((time.monotonic(), k, t)))
    assert "--include-partial-messages" in brain.args(task, tmp_path)
    t0 = time.monotonic()
    res = brain.run(task)
    t1 = time.monotonic()
    assert res.ok and res.text == "It's at nine." and res.model == "claude-haiku"
    assert [x[1:] for x in got] == [("m1", "Let me look. "), ("m2", "It's at"), ("m2", "It's at nine.")]
    assert got[0][0] - t0 < t1 - t0 - 0.3  # the first words came before the program had finished


def test_stream_run_kills_at_the_timeout(tmp_path):
    script = tmp_path / "slow.py"
    script.write_text("import time\nprint('one', flush=True)\ntime.sleep(30)\n", encoding="utf-8")
    seen = []
    t0 = time.monotonic()
    r = claude_mod.stream_run([sys.executable, str(script)], input="", timeout=1, on_line=seen.append)
    assert r.code is None and seen == ["one\n"] and time.monotonic() - t0 < 15


# ------------------------------------------------------------------------------- an API's server-sent events
def test_an_api_streams_through_the_queue(tmp_path, monkeypatch):
    from kurooto.app import App
    from tests.fakes.openai import FakeOpenAI

    monkeypatch.setenv("KUROOTO_HOME", str(tmp_path))
    ai = FakeOpenAI()
    ai.answer = "The moon is far. About 384,000 km."
    app = App()
    try:
        app.secrets.set("custom.api_key", ai.key)
        app.settings.set("brain.base_urls", {"custom": ai.base})
        app.settings.set("brain.models", {"custom": {"low": "fast", "medium": "smart", "high": "smart"}})
        app.settings.set("brain.main", "custom")
        got, started = [], []
        tell = lambda k, t: got.append((k, t))  # noqa: E731
        with app.jobs.turn_options(on_text=tell, on_start=started.append, effort="low", text_only=True):
            jid = app.jobs.submit("how far is the moon", quiet=True)
        assert app.jobs.run_next() == jid
        job = app.jobs.get(jid)
        assert job.status == "ok" and job.result == "The moon is far. About 384,000 km."
        assert started == ["custom"] and ai.requests[-1]["stream"] is True
        assert got[-1] == (("0:custom", "fast"), "The moon is far. About 384,000 km.") and len(got) > 2
        assert jid not in app.jobs.hooks  # dropped when it ended
        app.jobs.submit("no listener", quiet=True)
        app.jobs.run_next()
        assert "stream" not in ai.requests[-1]  # nobody listening: not streamed
    finally:
        ai.close()
        app.close()

"""0.9.2 latency: the turn record (turn_log, /voice turns, p50/p90), the stage deadline, Live's prewarm, breaker,
heard-you cue, resume and spoken cap, waiting on unfinished words, a short first piece, background work's priority,
and voice.listen.fast_live with its gain measured against fakes. No real Google, microphone, camera or speaker."""

# ruff: noqa: F811 (the fixtures imported from the voice tests are taken as arguments)

import asyncio
import json
import os
import subprocess
import time

import pytest

from kurooto.core import nearby, proc
from kurooto.modules.face import watch as watch_mod
from kurooto.modules.voice import fast, trace
from kurooto.modules.voice import live as live_mod
from kurooto.modules.voice import shape as shape_mod
from kurooto.modules.voice.gate import Heard
from kurooto.modules.voice.speakerid import Verdict
from tests.unit.test_voice import Stt, voice  # noqa: F401 (pytest fixtures)
from tests.unit.test_voice_live import ANSWER, SOUND, FakeLive, events, lv, say  # noqa: F401


def wait_for(cond, s=5.0):
    end = time.monotonic() + s
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.02)
    return cond()


class SlowSetup(FakeLive):
    """Google taking `delay` seconds to answer the setup (connecting and setting up a session)."""

    def __init__(self, mode="speak", delay=0.6, late=0.0, **kw):
        self.delay, self.late = delay, late
        super().__init__(mode, **kw)

    async def _handler(self, ws):
        await asyncio.sleep(self.delay)
        await super()._handler(ws)

    async def _answer(self, ws, got):
        if self.late:
            await asyncio.sleep(self.late)
        await super()._answer(ws, got)


def use(lv, monkeypatch, srv):
    monkeypatch.setattr(live_mod, "LIVE_URL", srv.url)
    lv._servers = [*getattr(lv, "_servers", []), srv]
    return srv


@pytest.fixture
def lvx(lv):
    yield lv
    for s in getattr(lv, "_servers", []):
        s.stop()


# -------------------------------------------------------------------------------------------- the turn record
def test_each_turn_leaves_one_numbers_only_row(lv):
    srv = lv.fake()
    lv.judge.answers = ['{"class": "chatter", "confidence": 0.9}']
    lv.hear(Heard(speech=True, text="did you see the match", seconds=1.0, ended_at=time.monotonic()), SOUND)
    say(lv)
    rows = lv.turn_log
    assert [r["seq"] for r in rows] == [1, 2]
    assert rows[0]["gate"] == "chatter" and rows[0]["path"] == "dropped"
    r = rows[1]
    assert r["gate"] == "addressed" and r["face"] == "seen" and r["path"] == "live"
    assert r["id_verdict"] == "owner" and r["id_score"] == 0.9
    assert {"seq", "gate", "face", "id_verdict", "id_score"} <= set(r)
    assert r["sent_ms"] <= r["play_ms"] and "load" in r and srv.turns
    assert "match" not in json.dumps(rows) and "due" not in json.dumps(rows)  # never words
    table = lv._cmd(None, "turns")
    assert "addressed" in table and "chatter" in table and "live" in table
    st = lv.status()
    assert st["turns"][-1]["seq"] == 2 and "p50_p90" in st["speed"]
    lv.app.settings.set("voice.listen.trace", False)
    say(lv)
    assert len(lv.turn_log) == 2 and "off" in lv._cmd(None, "turns")


def test_a_face_turned_down_and_the_off_state_are_named(lv, monkeypatch):
    lv.fake()
    # a frame, nobody facing it
    monkeypatch.setattr(lv, "_face_sleep", lambda s: None)
    end = time.monotonic() - 4
    nearby.set_facing(lv.app, 1, 0, at=end - 0.3)
    lv.hear(Heard(speech=True, text="Kurooto, what's due?", seconds=1.0, ended_at=end), SOUND)
    assert lv.turn_log[-1]["face"] == "none" and lv.turn_log[-1]["gate"] == "chatter"
    monkeypatch.setattr(lv, "face_gate", lambda: ("off", ""))
    say(lv, faced=False)
    assert lv.turn_log[-1]["face"] == "off"


def test_percentiles_and_spread():
    assert trace.percentile([5, 1, 3, 2, 4], 0.5) == 3 and trace.percentile([1, 2, 3, 4, 10], 0.9) == 10
    rows = [{"play_ms": x, "sent_ms": x // 2} for x in (1000, 2000, 3000, 4000, 9000)]
    sp = fast.spread(rows)
    assert sp["play"] == [3000, 9000] and sp["sent"][0] == 1500
    assert "first sound 3.0 / 9.0 s" in fast.spread_line(sp, 5)


# ----------------------------------------------------------------------------------------- the stage deadline
def test_a_turn_judged_too_late_says_lost_you_and_sends_nothing(lv):
    srv = lv.fake()
    lv.app.settings.set("voice.listen.stage_deadline_s", 8)
    end = time.monotonic() - 9  # its words took 9 s to come through (a busy machine)
    nearby.set_facing(lv.app, 1, 1, at=end - 0.5)
    assert lv.hear(Heard(speech=True, text="Kurooto, what's due?", seconds=1.0, ended_at=end), SOUND) is None
    assert srv.setups == [] and lv.text_way == [] and lv.engine.said == [live_mod_lost()]
    assert lv.portal.open and lv.turn_log[-1]["path"] == "lost" and lv.lost_count == 1
    assert events(lv, "voice_lost")[-1]["ms"] >= 9000
    lv.app.settings.set("voice.listen.stage_deadline_s", 0)  # off: answered however late
    lv.portal.close("test")
    nearby.set_facing(lv.app, 1, 1, at=end - 0.5)
    assert lv.hear(Heard(speech=True, text="Kurooto, what's due?", seconds=1.0, ended_at=end), SOUND)


def live_mod_lost():
    from kurooto.modules.voice import LOST

    return LOST


# ------------------------------------------------------------------------------------------------ prewarm
def test_his_face_looking_opens_live_ahead_and_his_turn_uses_it(lvx, monkeypatch):
    lv = lvx
    srv = use(lv, monkeypatch, SlowSetup(delay=0.3))
    lv.app.settings.set("voice.listen.live_prewarm", True)
    monkeypatch.setattr(lv, "_look_why", lambda: "")
    nearby.set_owner(lv.app, True, True, None)
    lv.look_tick()
    assert wait_for(lambda: lv.live.sess is not None and lv.live.sess.warm)
    assert len(srv.setups) == 1 and srv.turns == []  # connected and set up: no sound
    assert say(lv) == "It's due Friday."
    assert len(srv.setups) == 1 and srv.turns == [SOUND]
    (ev,) = events(lv, "voice_timing")
    assert ev["live_warm"] == 1 and ev["live_open_ms"] < 100  # no connect on the turn's time
    assert lv.live.warm_count == 1


def test_never_on_someone_elses_face_and_an_unused_one_closes(lvx, monkeypatch):
    lv = lvx
    srv = use(lv, monkeypatch, SlowSetup(delay=0.0))
    lv.app.settings.set("voice.listen.live_prewarm", True)
    monkeypatch.setattr(lv, "_look_why", lambda: "")
    nearby.set_owner(lv.app, False, False, None)  # a face, not his
    nearby.set_look(lv.app, True)  # (anyone's look still opens a talk, as before)
    lv.look_tick()
    time.sleep(0.2)
    assert srv.setups == [] and lv.live.sess is None
    nearby.set_owner(lv.app, True, True, None)
    lv.look_tick()
    assert wait_for(lambda: lv.live.sess is not None)
    monkeypatch.setattr(live_mod, "PREWARM_IDLE_S", 0.0)
    lv.live.tick()
    assert lv.live.sess is None and srv.closed.wait(5)
    lv.app.settings.set("voice.listen.live_prewarm", False)
    assert lv.live.prewarm("face") is False


def test_prewarm_is_rate_capped(lvx, monkeypatch):
    lv = lvx
    use(lv, monkeypatch, SlowSetup(delay=0.0))
    lv.app.settings.set("voice.listen.live_prewarm", True)
    opened = 0
    for _ in range(live_mod.PREWARM_MAX + 3):
        if lv.live.prewarm("face"):
            opened += 1
            assert wait_for(lambda: lv.live._warming is None)
        lv.live.close()
    assert opened == live_mod.PREWARM_MAX


# ------------------------------------------------------------------------------------------------ breaker
def test_two_failed_opens_rest_live_and_a_probe_ends_it(lv, monkeypatch):
    srv = lv.fake("refuse")
    lv.app.settings.set("voice.live.breaker.on", True)
    for _ in range(2):
        lv.portal.close("test")
        assert say(lv) == "The usual way."
    assert lv.live.resting() and "Live resting" in lv.live.line()
    n = len(srv.setups)
    lv.portal.close("test")
    t0 = time.monotonic()
    assert say(lv) == "The usual way."
    assert len(srv.setups) == n and time.monotonic() - t0 < 1.0  # no connection tried, no wait
    assert lv.status()["live"]["resting"] is True
    ok = lv.fake()
    lv.live._probe_at = 0
    lv.live.tick()
    assert wait_for(lambda: not lv.live.resting())
    assert ok.setups == [{"model": ok.setups[0]["model"]}]  # the probe's setup: a model name, nothing else
    lv.portal.close("test")
    assert say(lv) == "It's due Friday."


def test_a_slow_first_sound_never_trips_it(lv, monkeypatch):
    lv.fake("silent")
    monkeypatch.setattr(live_mod, "FIRST_S", 0.3)
    lv.app.settings.set("voice.live.breaker.on", True)
    for _ in range(3):
        lv.portal.close("test")
        say(lv)
    assert not lv.live.resting()


# ------------------------------------------------------------------------------------------- heard-you cue
def test_the_cue_plays_when_live_is_slow_and_never_when_it_answers_at_once(lvx, monkeypatch):
    lv = lvx
    use(lv, monkeypatch, SlowSetup(delay=0.0, late=1.2))
    monkeypatch.setattr(live_mod, "FIRST_S", 3.0)
    lv.app.settings.set("voice.live.ack", True)
    assert say(lv) == "It's due Friday."
    tone = fast.tone(fast.ACK_RATE)
    assert lv.out.got[0] == (tone, fast.ACK_RATE)  # the cue, then Live's answer
    assert b"".join(p for p, _ in lv.out.got[1:]) == ANSWER * 2
    assert any(m["kind"] == "voice_ack" for m in lv.app.live.sent)
    lv.out.got.clear()
    lv.portal.close("test")
    use(lv, monkeypatch, SlowSetup(delay=0.0))
    say(lv)
    assert all(p != tone for p, _ in lv.out.got)  # answered within 0.6 s: no cue
    lv.out.got.clear()
    lv.portal.close("test")
    use(lv, monkeypatch, SlowSetup(delay=0.0, late=1.2))
    monkeypatch.setattr(lv, "cue_quiet", lambda: True, raising=False)
    say(lv)
    assert all(p != tone for p, _ in lv.out.got)  # a quiet room: shown, not played


# ------------------------------------------------------------------------------------------------- resume
class Resumable(FakeLive):
    async def _answer(self, ws, got):
        await ws.send(json.dumps({"sessionResumptionUpdate": {"newHandle": f"h{len(self.setups)}", "resumable": True}}))
        await super()._answer(ws, got)


def test_his_session_resumes_across_closings_and_a_guests_never(lvx, monkeypatch):
    lv = lvx
    srv = use(lv, monkeypatch, Resumable())
    lv.app.settings.set("voice.live.resume", True)
    lv.app.settings.set("voice.speaker_id.gate", False)  # the words first, as for the other Live tests of guests
    say(lv)
    assert srv.setups[0]["sessionResumption"] == {}
    lv.portal.close("silence")
    say(lv)
    assert srv.setups[1]["sessionResumption"] == {"handle": "h1"}
    lv.portal.close("silence")
    lv.app.settings.set("voice.listen.live_everyone", True)
    lv.who = Verdict("guest", "not you", 0.2, 2.0)
    say(lv, "Kurooto, how far away is the moon?")
    assert "sessionResumption" not in srv.setups[2]
    monkeypatch.setattr(live_mod, "RESUME_S", 0.0)
    assert lv.live._resume_handle() is None


# --------------------------------------------------------------------------------------------- spoken cap
class Long(FakeLive):
    async def _answer(self, ws, got):
        def sc(**kw):
            return json.dumps({"serverContent": kw})

        text = "First sentence here. The second one goes on for a while longer. Third. Fourth one too."
        await ws.send(sc(outputTranscription={"text": text}))
        for _ in range(8):  # four seconds of sound in half-second pieces
            data = __import__("base64").b64encode(b"\x07\x00" * 12000).decode()
            await ws.send(sc(modelTurn={"parts": [{"inlineData": {"mimeType": "audio/pcm;rate=24000", "data": data}}]}))
        await ws.send(sc(turnComplete=True))


def test_lives_long_answer_stops_at_a_sentence_end_and_the_rest_is_shown(lvx, monkeypatch):
    lv = lvx
    use(lv, monkeypatch, Long())
    lv.app.settings.set("voice.live.spoken_max_s", 1.0)
    reply = say(lv)
    assert reply.endswith("Fourth one too.")  # all of it on screen
    played = sum(len(p) for p, _ in lv.out.got) / 48000
    assert 1.0 <= played < 3.5  # stopped past the cap, at a sentence end, not the whole 4 s
    assert events(lv, "voice_timing")[-1]["capped"] == 1
    assert live_mod.cap_at(0, 100, "", 50) is None and live_mod.cap_at(60, 100, "", 50) == 60


# ------------------------------------------------------------------------------------ unfinished, first piece
def test_unfinished_words_wait_longer():
    assert fast.unfinished("I need to buy milk and") and fast.unfinished("so,") and fast.unfinished("call mum, um")
    assert not fast.unfinished("what's due tomorrow?") and not fast.unfinished("that's all")


def test_the_early_end_waits_on_unfinished_words(voice, monkeypatch):
    e = fast.Early(voice)
    monkeypatch.setattr(voice, "_early_text", lambda pcm, flags: "remind me to call mum and")
    voice.app.settings.set("voice.listen.wait_unfinished", True)
    e.pause(b"\x01" * 4096, b"\x01" * 4)
    assert e.end_ms(4096) in (None, fast.Early.UNFINISHED_MS)  # still being written out: held, not ended
    e.got["done"].wait(2)
    assert e.end_ms(4096) == fast.Early.UNFINISHED_MS
    voice.app.settings.set("voice.listen.wait_unfinished", False)
    e.pause(b"\x01" * 8192, b"\x01" * 8)
    e.got["done"].wait(2)
    assert e.end_ms(8192) is None  # off: 0.7 s as before


def test_a_long_first_sentence_is_said_from_its_first_clause():
    long = "When you get a moment tomorrow morning, check the lab booking page for the spectrometer slots and the room."
    assert shape_mod.first_short([long, "Then reply."]) == [long[:39], long[40:], "Then reply."]
    assert shape_mod.first_short(["Short one.", long]) == ["Short one.", long]
    assert shape_mod.first_short(["x" * 100]) == ["x" * 100]  # no clause: left whole


# --------------------------------------------------------------------------------------- background priority
def test_background_programs_run_nicer():
    if os.name != "posix":
        pytest.skip("POSIX niceness")
    p = subprocess.Popen(["sleep", "5"])
    try:
        before = os.getpriority(os.PRIO_PROCESS, p.pid)
        assert proc.run_nicer(p.pid)
        assert os.getpriority(os.PRIO_PROCESS, p.pid) == min(19, before + proc.BACKGROUND_NICE)
    finally:
        p.kill()
        p.wait()
    assert proc.run_nicer(p.pid) is False  # gone: never raises


# ------------------------------------------------------------------------------------- face: looking, talking
class _F:
    def __init__(self, mouth_y, width=40.0):
        self.landmarks = [(100.0, 100.0), (160.0, 100.0), (130.0, 130.0), (130 - width / 2, mouth_y),
                          (130 + width / 2, mouth_y)]  # fmt: skip


def test_the_mouth_numbers_and_talking():
    a, b = watch_mod._mouth(_F(160.0)), watch_mod._mouth(_F(166.0))
    assert a == (1.0, 0.6667) and b[0] > a[0]
    app = type("A", (), {})()
    t = time.monotonic()
    nearby.set_owner(app, True, True, None, at=t - 1.0)
    nearby.set_owner(app, True, True, 0.01, at=t - 0.8)
    assert nearby.owner_attending(app, t - 2) == (True, None)  # one change: can't tell
    nearby.set_owner(app, True, True, 0.09, at=t - 0.6)
    assert nearby.owner_attending(app, t - 2) == (True, True)
    assert nearby.owner_attending(app, t - 0.7) == (True, None)
    nearby.set_owner(app, True, False, 0.01, at=t - 0.4)
    nearby.set_owner(app, True, False, 0.01, at=t - 0.2)
    assert nearby.owner_attending(app, t - 0.5) == (False, False)
    assert not nearby.owner_looking_now(app)
    nearby.set_owner(app, False, True, 0.5)  # not his face: never looking, no mouth
    assert nearby.owner_attending(app, time.monotonic() - 0.1) == (False, None)


# ------------------------------------------------------------------------------------------- fast_live
def _fast_turn(lv, monkeypatch, text, fast_on):
    """One stretch the way the listener hands it over: its start, a first pause (Early), 0.4 s more of quiet, its
    end; his face looking and talking throughout. Returns ms from the end to Live's first sound playing."""
    stt = Stt()
    stt.said = text
    monkeypatch.setattr(lv, "stt", lambda: stt)
    lv.app.settings.set("voice.listen.fast_live", fast_on)
    lv._stretch_start()
    t = time.monotonic()
    for i, mv in enumerate((None, 0.08, 0.02, 0.09)):
        nearby.set_owner(lv.app, True, True, mv, at=t - 0.2 + i * 0.05)
    nearby.set_facing(lv.app, 1, 1, at=t + 0.05)
    flags = b"\x01" * (len(SOUND) // 1024)
    lv.early.pause(SOUND, flags)
    time.sleep(0.4)
    tail = bytes(12800)
    end = time.monotonic()
    lv.hear(Heard(speech=True, seconds=1.4, ended_at=end), SOUND + tail, flags + b"\x00" * (len(tail) // 1024))
    return events(lv, "voice_timing")[-1]["play_ms"]


def test_fast_live_opens_live_and_judges_while_he_speaks(lvx, monkeypatch):
    """The measured gain: Google's connect and setup (0.6 s here) and the local model's judgement (0.4 s here) happen
    during the stretch instead of after it."""
    lv = lvx
    slow = []

    def judge(prompt):
        slow.append(1)
        time.sleep(0.4)
        return '{"class": "addressed", "confidence": 0.95}'

    lv.judge = judge
    times = {}
    for on in (False, True):
        lv.portal.close("test")
        lv.live.close()
        use(lv, monkeypatch, SlowSetup(delay=0.6))
        n = len(slow)
        times[on] = _fast_turn(lv, monkeypatch, "I think the moon is getting further away", on)
        assert len(slow) - n == 1  # judged once: at the pause, not again at the end
    assert times[True] + 500 < times[False], times  # at least half a second sooner
    assert lv.turn_log[-1]["path"] == "live" and lv.turn_log[-1]["id_early"] == 1
    lv._latency_measured = times  # for the log


def test_fast_live_never_sends_what_the_gate_didnt_judge_addressed(lvx, monkeypatch):
    lv = lvx
    srv = use(lv, monkeypatch, SlowSetup(delay=0.0))
    lv.judge = lambda prompt: '{"class": "chatter", "confidence": 0.95}'
    stt = Stt()
    stt.said = "did you see the match last night"
    monkeypatch.setattr(lv, "stt", lambda: stt)
    lv.app.settings.set("voice.listen.fast_live", True)
    lv._stretch_start()
    t = time.monotonic()
    for i, mv in enumerate((None, 0.08, 0.09)):
        nearby.set_owner(lv.app, True, True, mv, at=t - 0.2 + i * 0.05)
    flags = b"\x01" * (len(SOUND) // 1024)
    lv.early.pause(SOUND, flags)
    time.sleep(0.3)
    lv.hear(Heard(speech=True, seconds=1.3, ended_at=time.monotonic()), SOUND + bytes(9216), flags + bytes(9))
    assert wait_for(lambda: lv.live._warming is None)
    assert srv.turns == []  # Live may be open (no sound); nothing it heard was sent
    assert lv.turn_log[-1]["gate"] == "chatter"


def test_fast_live_off_never_opens_live_at_a_pause(lvx, monkeypatch):
    lv = lvx
    srv = use(lv, monkeypatch, SlowSetup(delay=0.0))
    lv.app.settings.set("voice.listen.fast_live", False)
    lv._stretch_start()
    t = time.monotonic()
    for i, mv in enumerate((None, 0.08, 0.09)):
        nearby.set_owner(lv.app, True, True, mv, at=t - 0.2 + i * 0.05)
    lv.early.pause(SOUND, b"\x01" * 31)
    time.sleep(0.3)
    assert srv.setups == [] and lv.live._warming is None

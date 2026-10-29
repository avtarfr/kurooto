"""Voice degrade (0.9.2, voice.degrade): "ears source lost" (modules/voice/ears.py) and the Piper rung. Scenes from the
desk tape (tests/fakes/ears.py) play through ears.Ears and the real audio.Listener: a named microphone that stalls,
sends only digital silence, ends or stops being listed is replaced by this computer's default one within its lost
time, and taken back when it's listed again. No sound device, microphone or model is touched."""

# ruff: noqa: F811 (the fixtures imported from test_voice are taken as arguments)

import threading
import time

import pytest

from kurooto.modules.voice import audio
from kurooto.modules.voice.ears import Ears
from tests.fakes.ears import Scene, Tape
from tests.unit.test_voice import Speakers, Tts, voice  # noqa: F401 (pytest fixtures)

BODY = "Kurooto-body-mic"


def run(ears: Ears, seconds: float) -> list[bytes]:
    """Read the ears' frames on a thread for `seconds`, then close them."""
    got: list[bytes] = []

    def read():
        for f in ears.frames():
            got.append(f)

    t = threading.Thread(target=read, daemon=True)
    t.start()
    time.sleep(seconds)
    ears.close()
    t.join(2)
    assert not t.is_alive()
    return got


def wait_for(cond, s: float = 3.0) -> bool:
    end = time.monotonic() + s
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.02)
    return cond()


@pytest.mark.parametrize("how", ["stall", "zeros", "end"])
def test_a_lost_source_carries_on_from_the_laptop_mic(how):
    tape = Tape({BODY: Scene().voice(0.5).unplug(how), "": Scene().voice(4.0)}, speed=4.0)
    told = []
    ears = Ears(BODY, make=tape.make, probe=tape.probe, on_change=told.append, lost_s=0.3)
    got = []
    t = threading.Thread(target=lambda: got.extend(ears.frames()), daemon=True)
    t0 = time.monotonic()
    t.start()
    assert wait_for(lambda: told == ["lost"], 3.0), told
    took = time.monotonic() - t0
    assert ears.lost and ears.device == "" and tape.opened == [BODY, ""]
    assert took < 0.5 / 4 + 0.3 + 1.0 + 0.6  # the scene's sound, then the lost time (with the opening's grace)
    n = len(got)
    assert wait_for(lambda: len(got) > n + 5)  # frames keep coming, from the default microphone now
    ears.close()
    t.join(2)
    assert not t.is_alive()


def test_gone_from_the_list_counts_as_lost_and_listed_again_goes_back():
    tape = Tape({BODY: Scene().voice(30.0), "": Scene().voice(30.0)}, speed=1.0)
    told = []
    ears = Ears(BODY, make=tape.make, probe=tape.probe, on_change=told.append, lost_s=5.0, probe_s=0.2)
    t = threading.Thread(target=lambda: [None for _ in ears.frames()], daemon=True)
    t.start()
    time.sleep(0.3)
    assert told == [] and ears.device == BODY
    tape.listed[BODY] = False  # unplugged: the sound system no longer lists it (even though sound still came)
    assert wait_for(lambda: told == ["lost"])
    assert ears.device == ""
    tape.listed[BODY] = True  # plugged back in
    assert wait_for(lambda: told == ["lost", "back"])
    assert ears.device == BODY and tape.opened == [BODY, "", BODY]
    ears.close()
    t.join(2)


def test_cant_tell_from_the_list_means_silence_alone_decides():
    tape = Tape({BODY: Scene().voice(4.0), "": Scene().voice(4.0)}, speed=1.0)
    ears = Ears(BODY, make=tape.make, probe=lambda d: None, lost_s=5.0, probe_s=0.1)
    run(ears, 0.5)
    assert not ears.lost and tape.opened == [BODY]


def test_the_laptop_mic_failing_too_is_reported_to_the_listener():
    tape = Tape({BODY: Scene().unplug("end"), "": Scene().unplug("end")})
    ears = Ears(BODY, make=tape.make, probe=tape.probe, lost_s=0.2)
    with pytest.raises(RuntimeError):
        for _ in ears.frames():
            pass
    assert ears.lost and tape.opened == [BODY, ""]


def test_through_the_real_listener_speech_before_and_after_the_unplug_is_heard():
    """The desk tape through audio.Listener (Energy VAD): one stretch from the body mic, it's unplugged (stall), and
    the next stretch comes from this computer's microphone."""
    tape = Tape(
        {BODY: Scene().quiet(0.3).voice(1.0).quiet(1.0).unplug("stall"), "": Scene().quiet(0.6).voice(1.0).quiet(2.0)},
        speed=4.0,
    )
    told, heard = [], []
    ears = Ears(BODY, make=tape.make, probe=tape.probe, on_change=told.append, lost_s=0.4)
    lis = audio.Listener(ears, audio.Energy(), None, on_speech=lambda pcm, woke, secs, flags=b"": heard.append(secs))
    lis.start()
    try:
        assert wait_for(lambda: len(heard) >= 2, 6.0), (heard, told)
    finally:
        lis.stop()
    # 1 s each, with the pre-roll and the quiet that ended it
    assert told[:1] == ["lost"] and all(1.0 <= s < 2.5 for s in heard[:2]), heard
    assert lis.error == ""


# ------------------------------------------------------------------------------------------------ in Voice
def test_voice_uses_ears_only_with_the_switch_and_a_named_microphone(voice):
    assert voice.app.settings.get("voice.degrade.ears") is False  # off by default: it changes which mic listens
    assert type(voice._ears_mic()) is audio.Mic
    voice.app.settings.set("voice.listen.device", BODY)
    assert type(voice._ears_mic()) is audio.Mic
    voice.app.settings.set("voice.degrade.ears", True)
    assert isinstance(voice._ears_mic(), Ears)
    voice.app.settings.set("voice.listen.device", "")
    assert type(voice._ears_mic()) is audio.Mic  # the default microphone has nothing to fall back to


def test_voice_id_and_the_status_follow_the_microphone_in_use(voice):
    class Lis:
        def __init__(self, mic):
            self.mic = mic

        def running(self):
            return True

        def stop(self):
            pass

    voice.app.settings.set("voice.listen.device", BODY)
    voice.app.settings.set("voice.degrade.ears", True)
    ears = Ears(BODY, make=Tape({}).make)
    voice.listener = Lis(ears)
    assert voice.ears_device() == BODY and voice.voiceid.mic_now() == BODY and voice.degrade_line() == ""
    ears.lost = True
    voice._ears_changed("lost")
    assert voice.ears_device() == "" and voice.voiceid.mic_now() != BODY  # the default's print, not the body's
    assert "ears source lost" in voice.degrade_line() and "ears source lost" in voice.line()
    st = voice.status()["degrade"]
    assert st["ears_lost"] is True and st["losses"] == 1
    ev = [e for e in voice.app.events.tail(50) if e.get("kind") == "voice_ears"]
    assert ev and ev[-1]["state"] == "lost" and BODY not in str(ev[-1])  # when, never which device
    voice.listener = None


# --------------------------------------------------------------------------------------------- the Piper rung
class Breaks(Tts):
    name = "kokoro"

    def __init__(self, after=0):
        self.after, self.n = after, 0

    def synth(self, text):
        self.n += 1
        if self.n > self.after:
            raise RuntimeError("onnx went away")
        return super().synth(text)


class Piper(Tts):
    name = "piper"

    def __init__(self):
        self.said = []

    def synth(self, text):
        self.said.append(text)
        return super().synth(text)


@pytest.fixture
def rung(voice, monkeypatch):
    voice.speaker.player = Speakers()
    voice.app.settings.set("voice.speak.join_sentences", False)
    kokoro, piper = Breaks(after=1), Piper()
    state = {"kokoro": kokoro, "piper_here": True}

    def load(engine, key):
        if engine == "kokoro":
            return (state["kokoro"], "") if state["kokoro"] is not None else (None, "Kokoro didn't load: OSError")
        return None, ""

    monkeypatch.setattr(voice, "_load_tts", load)

    def missing(keys):
        return ["model:piper"] if "model:piper" in keys and not state["piper_here"] else []

    monkeypatch.setattr(voice.parts, "missing", missing)
    from kurooto.modules.voice import audio as audio_mod

    monkeypatch.setattr(audio_mod, "Piper", lambda path, rate=1.0: piper, raising=False)
    monkeypatch.setattr(voice.parts, "importable", lambda: None)
    voice.rung_state, voice.piper = state, piper
    return voice


def test_kokoro_failing_mid_answer_hands_the_rest_to_piper(rung):
    rung.say("One. Two. Three.", wait=True)
    assert rung.piper.said == ["Two.", "Three."]  # the first was said by Kokoro, the rest by Piper
    assert rung.voice_rung == "piper" and "speaking with Piper" in rung.degrade_line()
    rung.say("Four.", wait=True)  # Kokoro isn't tried again for a while
    assert rung.piper.said[-1] == "Four."


def test_no_piper_set_up_means_captions_and_nothing_is_fetched(rung):
    rung.rung_state["kokoro"] = None  # Kokoro doesn't load
    rung.rung_state["piper_here"] = False
    ok, why = rung.say("Hello there.", wait=True)
    assert not ok and rung.voice_rung == "captions" and rung.piper.said == []
    shown = [m for m in rung.app.live.sent if m["kind"] == "voice_text"]
    assert shown[-1]["text"] == "Hello there."  # on screen all the same


def test_the_piper_rung_has_its_own_switch(rung):
    rung.app.settings.set("voice.degrade.piper", False)
    rung.say("One. Two.", wait=True)
    assert rung.piper.said == [] and rung.voice_rung == ""

"""Barge-in (voice.listen.barge_in, modules/voice/barge.py): talking over Kurooto stops it. Its own voice coming back
through the room never does; the owner's voice (Voice ID, closer to him than to Kurooto's own voice print) or a stretch
clearly louder than the expected echo whose words aren't its own does, and what was said then is a told-off stop, a new
turn, or it listens. Fakes only: synthetic sound with markers (test_voiceid.pcm), a fake VAD, transcriber, speech
engine and clock; no microphone, speaker or model is touched."""

# ruff: noqa: F811 (the fixtures imported from test_voice are taken as arguments)

import threading
import time
from types import SimpleNamespace

import pytest

from kurooto.modules.voice import audio
from kurooto.modules.voice import barge as barge_mod
from tests.unit.test_voice import Output, Speakers, Stt, hear, vid, voice  # noqa: F401 (pytest fixtures)
from tests.unit.test_voiceid import pcm

KUROOTO = 9  # the synthetic voice that stands for Kurooto's own (Kokoro's) voice
FRAME = audio.FRAME * 2  # bytes


class Clock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


class OwnTts:
    """Kurooto's speech engine: everything it says is in "its own voice" (the marker of voice 9)."""

    name = "kokoro"

    def synth(self, text):
        return bytes(pcm(KUROOTO, 50, seconds=2.0, pre_s=0).pcm), 16000


def frames(b: bytes):
    for i in range(0, len(b) - FRAME + 1, FRAME):
        yield b[i : i + FRAME]


class Rig:
    """Voice with barge-in run by hand: a fake clock, checks on the caller's thread, what it plays registered as
    playing, and the microphone's frames fed one by one with the VAD's answer."""

    def __init__(self, v, monkeypatch):
        self.v, self.b = v, v.barge
        self.b.sync = True
        self.clock = self.b.clock = Clock()
        self.stops = []  # it went quiet: stopped, or held while what cut in is written out (Speaker.hold)
        real, hold = v.speaker.stop, v.speaker.hold
        v.speaker.stop = lambda: (self.stops.append(1), real())[1]
        v.speaker.hold = lambda: (self.stops.append(1), hold())[1]
        v.listener = SimpleNamespace(running=lambda: True, stop=lambda: None, error="")
        monkeypatch.setattr(v, "tts", lambda: (OwnTts(), ""))
        self.stt = Stt()
        monkeypatch.setattr(v, "stt", lambda: self.stt)

    def playing(self, seconds=12.0, level=6000):
        """Kurooto starts saying something (what it plays, at its level)."""
        self.b.speaking(["The forecast for tomorrow is light rain in the morning, clearing by noon."])
        self.b.played(bytes(pcm(KUROOTO, 1, seconds=seconds, level=level, pre_s=0).pcm), 16000)

    def feed(self, sound: bytes, p: float):
        for f in frames(sound):
            self.b.feed(f, p)
            self.clock.t += audio.FRAME / audio.RATE

    def quiet(self, seconds=1.0):
        self.feed(bytes(int(seconds * 16000) * 2), 0.0)

    def echo(self, seconds=1.5, utt=1):
        """Its own voice coming back through the room: a third as loud as played."""
        self.feed(bytes(pcm(KUROOTO, utt, seconds=seconds, level=2000, pre_s=0).pcm), 0.9)

    def queued(self):
        out = []
        while not self.v._work.empty():
            out.append(self.v._work.get_nowait())
        return out


@pytest.fixture
def rig(voice, monkeypatch):
    return Rig(voice, monkeypatch)


@pytest.fixture
def vrig(vid, monkeypatch):  # Voice ID on, the owner (voice 1) enrolled
    r = Rig(vid.v, monkeypatch)
    r.stt = vid.stt_fake
    monkeypatch.setattr(vid.v, "stt", lambda: r.stt)
    return r


def barges(v):
    return [e for e in v.app.events.tail(50) if e.get("kind") == "voice_barge"]


# --------------------------------------------------------------------------------------------- its own echo
def test_its_own_echo_never_stops_it(vrig):
    r = vrig
    r.stt.said = "The forecast for tomorrow is light rain in the morning"
    r.playing()
    for utt in (1, 2, 3):
        r.echo(2.0, utt)
        r.quiet(0.8)
    assert r.stops == [] and r.queued() == [] and r.b.count == 0
    assert r.b.gain() is not None and 0.2 < r.b.gain() < 0.5  # the echo's share was learned: about a third


def test_its_own_echo_without_voice_id_never_stops_it_even_loud(rig):
    """Played louder than it was learned at: louder echo, but its words are its own, so it isn't a barge-in."""
    r = rig
    r.playing()
    r.echo(1.5)
    r.quiet(0.8)
    r.stt.said = "light rain in the morning, clearing by noon"
    r.feed(bytes(pcm(KUROOTO, 2, seconds=1.5, level=12000, pre_s=0).pcm), 0.9)
    r.quiet(0.8)
    assert r.stops == [] and r.queued() == []
    assert r.stt.calls  # it was loud enough to be written out, and the words were its own


# ----------------------------------------------------------------------------------------- the owner's voice
def test_the_owner_s_voice_stops_it_and_becomes_a_turn(vrig):
    r = vrig
    v = r.v
    r.playing()
    r.echo(1.0)
    r.quiet(0.8)
    assert r.stops == []
    r.stt.said = ""
    r.feed(bytes(pcm(1, 7, seconds=1.0, level=3000, pre_s=0).pcm), 0.9)  # no louder than the echo: his voice
    assert r.stops and not r.stt.calls  # stopped by the voice alone, before anything was written out
    r.quiet(0.8)
    (item,) = r.queued()
    assert item[4]["how"] == barge_mod.VOICE
    r.stt.said = "What about the weekend?"
    assert v.barge_turn(item[0], item[3], item[4]) == "Sure."
    assert v.portal.send.got == [("What about the weekend?", "owner")]  # a turn, as his (context: the chat)
    assert v.portal.open and barges(v)[-1]["outcome"] == "turn" and barges(v)[-1]["how"] == "voice"
    assert "weekend" not in str(barges(v))


def test_too_little_speech_isnt_checked_by_voice(vrig):
    r = vrig
    r.playing()
    r.echo(1.0)
    r.quiet(0.8)
    r.feed(bytes(pcm(1, 7, seconds=0.4, level=3000, pre_s=0).pcm), 0.9)  # under 0.6 s and no louder than the echo
    r.quiet(0.8)
    assert r.stops == [] and r.queued() == []


def test_a_told_off_phrase_mid_speech_stops_it_without_a_reply(vrig):
    r = vrig
    v = r.v
    assert hear(v, "Kurooto, what's the forecast?") == "Sure."
    assert v.portal.open
    asked = list(v.portal.send.got)
    r.playing()
    r.echo(1.0)
    r.quiet(0.8)
    r.feed(bytes(pcm(1, 8, seconds=1.0, level=3000, pre_s=0).pcm), 0.9)
    r.quiet(0.8)
    (item,) = r.queued()
    r.stt.said = "stop talking"
    assert v._work_one(*item) is None
    assert v.portal.send.got == asked  # nothing more sent
    assert not v.portal.open and barges(v)[-1]["outcome"] == "told off"
    assert [e for e in v.app.events.tail(50) if e["kind"] == "voice_misfire"]


def test_anything_else_stops_it_and_listens(vrig):
    r = vrig
    v = r.v
    v.app.settings.set("voice.listen.follow_s", 20)
    r.playing()
    r.echo(1.0)
    r.quiet(0.8)
    r.feed(bytes(pcm(1, 9, seconds=1.0, level=3000, pre_s=0).pcm), 0.9)
    r.quiet(0.8)
    (item,) = r.queued()
    r.stt.said = "hmm I was thinking about Saturday"
    assert v._work_one(*item) is None
    assert v.portal.send.got == []  # a statement: not sent
    assert v.portal.open and v.portal.answered and barges(v)[-1]["outcome"] == "listen"
    assert hear(v, "I think Saturday works better") == "Sure."  # the conversation goes on without its name
    assert v.portal.send.got == [("I think Saturday works better", "owner")]


def test_someone_else_s_voice_doesnt_stop_it_unless_loud(vrig):
    r = vrig
    r.playing()
    r.echo(1.0)
    r.quiet(0.8)
    r.stt.said = "pass me the charger"
    r.feed(bytes(pcm(5, 1, seconds=1.0, level=2500, pre_s=0).pcm), 0.9)  # another voice, at the echo's loudness
    r.quiet(0.8)
    assert r.stops == [] and r.queued() == []


# ------------------------------------------------------------------------------------------- loudness, words
def test_without_voice_id_a_loud_stretch_with_its_own_words_stops_it(rig):
    r = rig
    v = r.v
    v.portal.send = lambda text, who=None: "It's ten past nine."
    r.playing()
    r.echo(1.0)
    r.quiet(0.8)
    r.stt.said = "what time is it"
    r.feed(bytes(pcm(5, 1, seconds=1.0, level=12000, pre_s=0).pcm), 0.9)  # clearly louder than the echo
    assert r.stops
    r.quiet(0.8)
    (item,) = r.queued()
    assert item[4]["how"] == barge_mod.LOUD
    assert v.barge_turn(item[0], item[3], item[4]) == "It's ten past nine."
    assert barges(v)[-1] == {**barges(v)[-1], "how": "loud", "outcome": "turn"}


def test_loud_noise_with_no_words_doesnt_stop_it(rig):
    r = rig
    r.playing()
    r.echo(1.0)
    r.quiet(0.8)
    r.stt.said = ""
    r.feed(bytes(pcm(5, 1, seconds=1.0, level=12000, pre_s=0).pcm), 0.9)
    r.quiet(0.8)
    assert r.stops == [] and r.queued() == []


def test_the_echo_words_check():
    b = barge_mod.Barge(SimpleNamespace())
    b._said.extend(["The forecast for tomorrow is light rain.", "It clears by noon."])
    assert not b.words_ok("light rain tomorrow")
    assert not b.words_ok("thank you")  # what transcribers make up from noise
    assert b.words_ok("wait, what about Sunday")
    assert b.words_ok("stop")  # told off: always taken


def test_the_expected_echo_follows_what_s_played_with_a_lag():
    clock = Clock()
    b = barge_mod.Barge(SimpleNamespace(), clock=clock)
    b._pieces.append((100.0, barge_mod.FRAME_S, [0.0] * 10 + [0.5] * 10 + [0.0] * 50))
    assert b.expected(100.1) == 0.0
    assert b.expected(100.5) == 0.5
    assert b.expected(101.3) == 0.5  # still within the lag after it went quiet
    assert b.expected(102.0) == 0.0
    assert b.expected(200.0) == 0.0


# ---------------------------------------------------------------------------------------- the switch, outputs
def test_the_switch_off_is_the_old_behaviour(voice, monkeypatch):
    voice.app.settings.set("voice.listen.barge_in", False)
    voice.listener = SimpleNamespace(running=lambda: True, stop=lambda: None, error="")
    voice.speaker.busy = True
    assert not voice.barge.wants()
    fed, got = [], []
    monkeypatch.setattr(voice.barge, "feed", lambda f, p: fed.append(1))

    class Mic:
        def frames(self):
            yield from frames(bytes(pcm(1, 1, seconds=2.0).pcm) + bytes(32000))

        def close(self):
            pass

    class Vad:
        def __init__(self):
            self.n = 0

        def prob(self, f):
            return 0.9

        def reset(self):
            pass

    li = audio.Listener(Mic(), Vad(), None, on_speech=lambda *a: got.append(a), hold=voice.speaker.holding,
                        barge=voice.barge)  # fmt: skip
    li._run()
    assert fed == [] and got == []  # dropped while it speaks, as before
    voice.app.settings.set("voice.listen.barge_in", True)
    li = audio.Listener(Mic(), Vad(), None, on_speech=lambda *a: got.append(a), hold=voice.speaker.holding,
                        barge=voice.barge)  # fmt: skip
    li._run()
    assert len(fed) > 50 and got == []  # handed to barge-in instead; never a turn of its own
    voice.speaker.busy = False


def test_the_switch_off_records_nothing(voice):
    voice.app.settings.set("voice.listen.barge_in", False)
    voice.listener = SimpleNamespace(running=lambda: True, stop=lambda: None, error="")
    voice.barge.speaking(["Hello there."])
    voice.barge.played(b"\x01\x00" * 1600, 16000)
    assert not voice.barge._said and not voice.barge._pieces


def test_an_output_on_another_device_is_stopped_by_its_stop_event(vrig, monkeypatch):
    r = vrig
    v = r.v
    v.app.settings.set("voice.speak.join_sentences", False)
    v.speaker.player = Speakers()
    out = Output(v, block=True)
    v.add_output(out)
    t = threading.Thread(target=v.say, args=("One. Two. Three.",), kwargs={"wait": True}, daemon=True)
    t.start()
    assert out.started.wait(5)
    assert r.b._pieces  # what the phone plays is tracked as playing
    r.echo(1.0)
    r.quiet(0.8)
    r.feed(bytes(pcm(1, 7, seconds=1.0, level=3000, pre_s=0).pcm), 0.9)
    assert out.stopped == [True] and v.speaker.held()  # quiet at once, held while what cut in is written out
    r.quiet(0.8)
    (item,) = r.queued()
    r.stt.said = "stop talking"
    assert v._work_one(*item) is None
    t.join(5)
    assert not t.is_alive()
    assert len(out.got) == 1 and v.speaker.player.got == []  # nothing more, nowhere else
    for _ in range(100):
        if not v.speaker.busy:
            break
        time.sleep(0.01)
    assert not v.speaker.busy


def test_a_cut_in_that_isnt_for_it_resumes_from_the_cut_sentence(vrig):
    """(0.8.17) "mm", a cough, someone else: it said the cut sentence again from its start and went on, where it used
    to stop for good and leave the answer half said."""
    r = vrig
    v = r.v
    v.app.settings.set("voice.speak.join_sentences", False)
    v.speaker.player = Speakers()
    cut = threading.Event()
    got = []

    def out(pcm_, sr, stop):  # the first sentence plays until it's cut; the rest play out
        got.append(pcm_)
        if len(got) == 1:
            cut.set()
            assert stop.wait(5)
        return True

    v.add_output(out)
    t = threading.Thread(target=v.say, args=("One. Two. Three.",), kwargs={"wait": True}, daemon=True)
    t.start()
    assert cut.wait(5)
    r.echo(1.0)
    r.quiet(0.8)
    r.feed(bytes(pcm(1, 9, seconds=1.0, level=3000, pre_s=0).pcm), 0.9)
    assert r.stops and v.speaker.held()
    r.quiet(0.8)
    (item,) = r.queued()
    r.stt.said = "mm hmm"
    assert v._work_one(*item) is None
    t.join(5)
    assert not t.is_alive()
    assert len(got) == 4 and got[0] == got[1]  # "One" cut, "One" again from its start, then "Two" and "Three"
    assert barges(v)[-1]["outcome"] == "resumed" and v.portal.send.got == []
    assert not v.speaker.held()


def test_held_and_never_settled_it_stops(vrig, monkeypatch):
    from kurooto.modules import voice as voice_mod

    monkeypatch.setattr(voice_mod, "HOLD_MAX_S", 0.05)
    sp = vrig.v.speaker
    sp.busy = True
    sp.hold()
    assert not sp._wait_held() and sp._cancel.is_set() and not sp.held()


def test_its_own_voice_print_is_made_once_in_memory(vrig):
    r = vrig
    calls = []
    real = OwnTts.synth
    OwnTts.synth = lambda self, text: (calls.append(text), real(self, text))[1]
    try:
        r.playing()
        r.playing()
        assert r.b.own_print() and calls == [barge_mod.OWN_PHRASE]
    finally:
        OwnTts.synth = real
    assert "own" not in str(sorted(p.name for p in r.v.app.paths.state.rglob("*")))


def test_status_shows_the_switch_and_a_count(rig):
    st = rig.v.status()["barge_in"]
    assert st == {"on": True, "since_start": 0}


def test_checks_run_on_their_own_thread(vrig):
    """As in use: the listener's thread only cuts and hands on; the voice check runs on barge-in's own thread."""
    r = vrig
    r.b.sync = False
    r.playing()
    r.echo(1.0)
    r.quiet(0.8)
    r.feed(bytes(pcm(1, 7, seconds=1.5, level=3000, pre_s=0).pcm), 0.9)
    for _ in range(300):
        if r.stops:
            break
        time.sleep(0.01)
    assert r.stops
    r.quiet(0.8)
    (item,) = r.queued()
    assert item[4]["how"] == barge_mod.VOICE and r.b._thread is not None and r.b._thread.name == "voice-barge"

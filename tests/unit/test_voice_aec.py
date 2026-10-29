"""Echo cancelling (0.9.3, voice.listen.aec, modules/voice/aec.py): Kurooto's own voice taken out of the microphone's
sound before barge-in, the VAD and Voice ID hear it, on a desk where one phone both plays and hears.

Fakes only (tests/fakes/echo.py): a made-up speech-like far end through a phone-like echo path (a delay with jitter,
the echo 3 dB louder than played, a thin speaker, early reflections), the room's noise, frames that arrive late and
in bursts, and a made-up "owner" voice talking over it. The canceller itself is the system's libspeexdsp through
ctypes; the tests that need it skip where it isn't installed. No microphone, speaker or model is touched."""

# ruff: noqa: F811 (the fixtures imported from test_voice are taken as arguments)

import array
import math
import time
from types import SimpleNamespace

import pytest

from kurooto.modules.voice import aec as aec_mod
from kurooto.modules.voice import audio
from kurooto.modules.voice import barge as barge_mod
from kurooto.modules.voice import speakerid as sid
from tests.fakes.echo import RATE, Desk, erle, speechlike
from tests.unit.test_voice import Speakers, vid, voice  # noqa: F401 (pytest fixtures)
from tests.unit.test_voice_barge import Rig, barges, rig  # noqa: F401 (a pytest fixture)

HAVE, WHY = aec_mod.available()
needs_lib = pytest.mark.skipif(not HAVE, reason=f"no libspeexdsp here: {WHY}")
OWNER_F0, KUROOTO_F0 = 120.0, 210.0
VAD_FLOOR = 0.005  # the fake VAD: speech above -46 dBFS (Silero goes by the sound, not its level)


def steady(desk: Desk, out: array.array, skip_first_s: float = 1.5, skip_piece_s: float = 0.0) -> float:
    """The ERLE on the far-end-only part, after the first skip_first_s of echo (convergence) and, for each piece
    with a delay of its own, its first skip_piece_s (measured there, passed through untouched)."""
    mask = list(desk.echo_only)
    for j in range(len(mask)):
        if desk.near_at[j]:
            mask[j] = False
    first = desk.starts[0]
    for j in range(first, min(len(mask), first + int(skip_first_s * RATE))):
        mask[j] = False
    for s in desk.starts[1:]:
        for j in range(max(0, s - int(0.1 * RATE)), min(len(mask), s + int(skip_piece_s * RATE))):
            mask[j] = False
    return erle(desk.samples(), out, mask)


def reply(desk: Desk, seed: int, pieces: int = 4) -> Desk:
    """A reply in pieces handed to a gapless output, each 0.3 s before the last ends."""
    for k in range(pieces):
        p = speechlike(2.8, f0=KUROOTO_F0, seed=seed + k)
        desk.play(0.3 if not k else desk._end - 0.3, p, chain=k > 0)
    return desk


def run(desk: Desk, on_frame=None, on_piece=None, **kw):
    a = aec_mod.Aec(clock=lambda: desk.now, **kw)
    placed = []

    def ref(pcm, sr):
        a.reference(pcm, sr, remote=True)
        placed.append(a._segs[-1][0])
        if on_piece is not None:
            on_piece(pcm, sr)

    def proc(frame):
        y = a.process(frame)
        if on_frame is not None:
            on_frame(y)
        return y

    return a, desk.run(proc, ref), placed


# ------------------------------------------------------------------------------------------------ the library
def test_a_missing_library_is_said_not_raised():
    lib, why = aec_mod.load(("libkurooto-no-such-speexdsp.so.9",))
    assert lib is None and "speexdsp" in why


@needs_lib
def test_the_far_end_is_resampled_to_the_microphone_s_rate():
    lib, _ = aec_mod.load()
    sr = 24000
    tone = array.array("h", (int(8000 * math.sin(2 * math.pi * 1000 * i / sr)) for i in range(sr)))
    y = aec_mod.resample(lib, tone.tobytes(), sr)
    assert abs(len(y) - RATE) <= 1
    mid = y[2000:14000]
    rms = math.sqrt(sum(v * v for v in mid) / len(mid))
    assert abs(rms - 8000 / math.sqrt(2)) < 300  # the level kept; nothing lost to the filter at 1 kHz


# ---------------------------------------------------------------------------------------------- cancelling
@needs_lib
def test_a_gapless_reply_through_the_phone_is_cancelled_20_db():
    """A reply in pieces handed to a gapless output (each handed 0.3 s before the last ends): one delay for the
    reply (280 ms, its jitter drawn once), the echo 3 dB louder than played, frames late by up to 40 ms in bursts."""
    desk = reply(Desk(13.0, delay_ms=280, gain_db=3, jitter_ms=60, seed=3), 20)
    a, out, _placed = run(desk)
    e = steady(desk, out)
    print(f"gapless reply: steady ERLE {e:.1f} dB, delay {a.status()['delay_ms']} ms, CPU {a.cpu_ms:.2f} ms/frame")
    assert e >= 20.0
    assert abs(a.status()["delay_ms"] - (desk.starts[0] / RATE - 0.3) * 1000) < 25  # (+ the frames' lateness)


@needs_lib
def test_sentences_with_their_own_jitter_are_each_measured_and_cancelled():
    """One clip per sentence (no gapless output): each comes back with its own delay, 280 +- 30 ms. Each one's delay
    is measured on its first 0.2 s (passed through untouched meanwhile) to within a few samples, and the rest of
    it is cancelled at least 20 dB."""
    desk = Desk(14.0, delay_ms=280, gain_db=3, jitter_ms=30, seed=7)
    t = 0.3
    for k in range(4):
        p = speechlike(2.8, f0=KUROOTO_F0, seed=10 + k)
        desk.play(t, p)
        t += len(p) / RATE + 0.05
    centers = []
    a = None

    def piece(_pcm, _sr):
        return None

    a, out, placed = run(desk, on_piece=piece)
    e = steady(desk, out, skip_piece_s=0.6)
    print(f"sentence clips: steady ERLE {e:.1f} dB, CPU {a.cpu_ms:.2f} ms/frame, estimates {a.estimates}")
    assert e >= 20.0
    # the last sentence's delay as measured (the alignment) is within 4 samples of where its echo really started
    centers.append(a._center)
    assert abs((desk.starts[-1] - placed[-1]) - a._center) <= 4


@needs_lib
def test_cpu_per_20_ms_frame_is_small():
    """The canceller's cost per listener frame (32 ms), scaled to 20 ms, while it plays: under 2 ms (plain Python
    delay tracking included; speex itself is ~0.1 ms)."""
    desk = Desk(8.0, delay_ms=300, gain_db=0, jitter_ms=0, seed=5)
    desk.play(0.3, speechlike(7.0, f0=KUROOTO_F0, seed=4))
    a, _out, _p = run(desk)
    per20 = a.cpu_ms * 20 / 32
    print(f"CPU: {a.cpu_ms:.3f} ms per 32 ms frame, {per20:.3f} ms per 20 ms")
    assert per20 < 2.0


@needs_lib
def test_nothing_played_passes_the_sound_through_untouched():
    desk = Desk(2.0, seed=1).talk(0.5, speechlike(1.0, f0=OWNER_F0, seed=2, level_db=-26))
    a, out, _p = run(desk)
    assert out.tobytes() == desk.samples()[: len(out)].tobytes()
    assert not a.running and a.cpu_ms == 0.0


@needs_lib
def test_a_cut_drops_what_wasn_t_played():
    clock = SimpleNamespace(t=10.0)
    a = aec_mod.Aec(clock=lambda: clock.t)
    a.process(bytes(1024))
    a.reference(speechlike(2.0, seed=1).tobytes(), RATE)
    clock.t += 0.5
    a.cut()
    ((i0, x),) = a._segs
    assert abs(len(x) - 0.5 * RATE) < 600 and a._ref_end_t <= clock.t


# ------------------------------------------------------------------------------------------------- barge-in
class Barging:
    """Voice ID on and enrolled, its model faked: a stretch embeds as the owner's voice print when his made-up voice
    is most of its sound (the share of its energy his own signal explains, at its place in the stream: what a real
    voice print sees), else as Kurooto's own. Barge-in is fed the listener's frames (cleaned or not) with an energy
    VAD, as the listener would while it speaks."""

    def __init__(self, vid, monkeypatch):
        self.r = r = Rig(vid.v, monkeypatch)
        r.stt = vid.stt_fake
        monkeypatch.setattr(vid.v, "stt", lambda: r.stt)
        c = sid.from_b64(vid.template()["centroid"])
        own = [-x for x in c]
        monkeypatch.setattr(vid, "embed", lambda pcm: c if self.his_share(pcm) >= 0.5 else own)
        monkeypatch.setattr(r.b, "own_print", lambda: own)
        r.stt.said = ""  # nothing written out: only the voice check can cut in
        self.voiced = []
        self.heard = array.array("h")  # what barge-in was handed so far
        self.lat = 0

    def his_share(self, pcm: bytes) -> float:
        n = len(pcm) // 2
        end = len(self.heard)
        lat = self.lat  # the suppressor's block of delay
        x = self.heard[end - n : end]
        o = self.near[end - n - lat : end - lat]
        xo = sum(map(lambda p, q: p * q, x, o))
        xx = sum(v * v for v in x)
        oo = sum(v * v for v in o)
        return xo * xo / (xx * oo) if xx and oo else 0.0

    def on_piece(self, pcm, sr):
        self.r.clock.t = 100.0 + self.desk.now
        if not self.voiced:
            self.r.b.speaking(["The forecast for tomorrow is light rain in the morning, clearing by noon."])
            self.voiced.append(1)
        self.r.b.played(pcm, sr, remote=True)

    def on_frame(self, y: bytes):
        self.heard.frombytes(y)
        self.r.clock.t = 100.0 + self.desk.now
        self.r.b.feed(y, 1.0 if barge_mod.rms(y) > VAD_FLOOR else 0.0)

    def scene(self, near: bool) -> Desk:
        self.desk = d = reply(Desk(12.0, delay_ms=280, gain_db=3, jitter_ms=0, seed=11), 30)
        self.near = array.array("h", bytes(2 * d.n))
        if near:  # the owner talks over it 6 s in, 9 dB under the echo
            his = speechlike(1.6, f0=OWNER_F0, seed=99, level_db=-26)
            d.talk(6.0, his)
            self.near[int(6.0 * RATE) : int(6.0 * RATE) + len(his)] = his
        return d


@needs_lib
def test_barge_in_fires_on_the_owner_over_a_cancelled_echo(vid, monkeypatch):
    bg = Barging(vid, monkeypatch)
    desk = bg.scene(near=True)
    a = aec_mod.Aec(clock=lambda: desk.now)
    bg.r.v.aec, bg.lat = a, a.can.latency
    fired = []
    real_hold = bg.r.v.speaker.hold
    monkeypatch.setattr(bg.r.v.speaker, "hold", lambda: (fired.append(desk.now), real_hold())[1])

    def ref(pcm, sr):
        a.reference(pcm, sr, remote=True)
        bg.on_piece(pcm, sr)

    def proc(frame):
        y = a.process(frame)
        bg.on_frame(y)
        return y

    desk.run(proc, ref)
    assert fired and 6.0 <= fired[0] <= 8.5  # while he talked (6.0-7.6 s), not before
    assert barges(bg.r.v) or bg.r.b.count >= 1  # what he said was handed on as a barge-in


@needs_lib
def test_its_own_echo_alone_never_barges_in_once_cancelled(vid, monkeypatch):
    bg = Barging(vid, monkeypatch)
    desk = bg.scene(near=False)
    a = aec_mod.Aec(clock=lambda: desk.now)
    bg.r.v.aec = a
    fired = []
    monkeypatch.setattr(bg.r.v.speaker, "hold", lambda: fired.append(desk.now))

    def ref(pcm, sr):
        a.reference(pcm, sr, remote=True)
        bg.on_piece(pcm, sr)

    def proc(frame):
        y = a.process(frame)
        bg.on_frame(y)
        return y

    desk.run(proc, ref)
    assert fired == []


def test_without_cancelling_his_voice_under_the_echo_never_barges_in(vid, monkeypatch):
    """What the desk measured: the echo at or above the level played, his voice under it; the raw stream's pitch is
    Kurooto's, so the voice check never fires (the reason for the canceller)."""
    bg = Barging(vid, monkeypatch)
    desk = bg.scene(near=True)
    fired = []
    monkeypatch.setattr(bg.r.v.speaker, "hold", lambda: fired.append(desk.now))
    desk.run(lambda f: (bg.on_frame(f), f)[1], bg.on_piece)
    assert fired == []


def test_barge_expects_the_residual_while_cancelling(rig):
    """Cancelling: the residual's share is learned from every frame while it plays (not speech frames only), its
    90th percentile; and the raw echo's share is kept apart."""
    r = rig
    r.v.aec = SimpleNamespace(cancelling=lambda: True)
    r.playing(level=6000)
    quiet = bytes(array.array("h", [180, -180] * (audio.FRAME // 2)).tobytes())  # ~0.0055: the residual
    for _ in range(40):
        r.b.feed(quiet, 0.0)
        r.clock.t += audio.FRAME / audio.RATE
    g = r.b.gain(True)
    assert g is not None and r.b.gain() is None  # the raw share wasn't touched
    assert 0.02 < g < 0.06  # 0.0055 against the playback's ~0.18


# ---------------------------------------------------------------------------------------------- in Voice
def test_the_switch_and_the_missing_library(voice, monkeypatch):
    v = voice
    v.app.settings.set("voice.listen.on", True)
    v.app.settings.set("voice.listen.aec", "off")
    assert v._new_aec() is None and v.aec_why == "" and v.aec_line() == ""
    assert {n: ok for n, ok, _d in v.doctor_checks()}["Voice echo cancelling"] is None
    v.app.settings.set("voice.listen.aec", "auto")
    monkeypatch.setattr(aec_mod, "available", lambda: (False, "the speexdsp library isn't on this computer"))
    assert v._new_aec() is None
    assert "unavailable" in v.aec_line() and "speexdsp" in v.aec_line()
    ok, detail = {n: (o, d) for n, o, d in v.doctor_checks()}["Voice echo cancelling"]
    assert ok is None and "listening works without it" in detail
    assert v.status()["aec"]["mode"] == "auto"


class PhoneOut:
    """An add-on's output that takes every piece (never plays)."""

    def __call__(self, pcm, sr, stop):
        return True


class FakeAec:
    def __init__(self):
        self.refs, self.cuts, self.frames = [], 0, 0

    def reference(self, pcm, sr, remote=False, seed_ms=None):
        self.refs.append((len(pcm), sr, remote, seed_ms))

    def cut(self):
        self.cuts += 1

    def process(self, frame):
        self.frames += 1
        return bytes(len(frame))  # all taken out

    def status(self):
        return {
            "running": True,
            "delay_ms": 290,
            "aligned_ms": 290,
            "erle_db": 24.0,
            "cpu_ms": 0.4,
            "estimates": [1, 1],
        }

    def cancelling(self):
        return True

    def close(self):
        pass


def test_auto_takes_the_reference_only_with_an_add_on_output_and_its_measured_delay(voice):
    v = voice
    v.speaker.player = Speakers()
    v.aec = fa = FakeAec()
    v.app.settings.set("voice.listen.aec", "auto")
    v.speaker._play(b"\x10\x00" * 4000, 24000)  # this computer's speakers: not in auto
    assert fa.refs == []
    out = PhoneOut()
    out.echo_delay_ms = lambda: 310  # an add-on that measured its own echo
    v.add_output(out)
    v.speaker._play(b"\x10\x00" * 4000, 24000)
    assert fa.refs == [(8000, 24000, True, 310.0)]
    v.app.settings.set("voice.listen.aec", "on")
    v.speaker.stop()
    assert fa.cuts == 1
    v.app.settings.set("voice.listen.aec", "off")
    v.speaker._cancel.clear()
    v.speaker._play(b"\x10\x00" * 4000, 24000)
    assert len(fa.refs) == 1


def test_the_listener_hears_the_cleaned_sound_first():
    """Every frame goes through the canceller before the levels, barge-in and the VAD."""
    fa = FakeAec()
    seen = []

    class Mic:
        def frames(self):
            for _ in range(3):
                yield b"\x00\x40" * audio.FRAME

        def close(self):
            pass

    class Vad:
        def prob(self, frame):
            seen.append(("vad", frame))
            return 0.0

        def reset(self):
            pass

    lis = audio.Listener(Mic(), Vad(), None, on_speech=lambda *a: None, on_level=lambda f: seen.append(("lvl", f)),
                         aec=fa)  # fmt: skip
    lis._run()
    assert fa.frames == 3 and seen and all(f == bytes(len(f)) for _k, f in seen)


def test_a_failing_canceller_is_dropped_and_the_sound_goes_on():
    class Bad(FakeAec):
        def process(self, frame):
            raise RuntimeError("boom")

    got = []

    class Mic:
        def frames(self):
            for _ in range(2):
                yield b"\x00\x40" * audio.FRAME

        def close(self):
            pass

    lis = audio.Listener(Mic(), audio.Energy(), None, on_speech=lambda *a: None, on_level=got.append, aec=Bad())
    lis._run()
    assert lis.aec is None and lis.aec_error == "RuntimeError" and len(got) == 2


def test_status_and_line_show_the_numbers(voice):
    v = voice
    v.app.settings.set("voice.listen.on", True)
    v.aec = FakeAec()
    assert v.aec_line() == "echo cancelling on add-on outputs (echo 290 ms, 24 dB down)"
    time.sleep(0)


# ----------------------------------------------------------------- 0.9.3 fixes beside it: the judge, his voice
def test_a_local_judge_that_can_t_run_is_said_in_voice_and_doctor(voice, monkeypatch):
    """(0.9.3, a fix) The offline helper on but its speed test for another model: judge() answered None for days
    and every look-opened statement was dropped as chatter, silently. Now /voice and doctor say so."""
    v = voice
    v.app.settings.set("voice.listen.on", True)
    h = v.app.helper
    v.app.settings.set("local_helper.on", True)
    h._update(test={"ok": True, "model": "llama3.2:1b", "at": time.time(), "seconds": 0.6})
    ok, why = v.judge_state()
    assert ok is False and "speed test" in why
    assert "the local judge can't run" in v.line()
    rows = {name: (ok_, d) for name, ok_, d in v.doctor_checks()}
    assert rows["Voice local judge"][0] is False
    v.app.settings.set("voice.listen.model_judge", False)
    assert v.judge_state() == (None, "") and "local judge" not in v.line()


def test_his_unsure_phone_turn_is_not_a_second_voice(voice, monkeypatch):
    """(0.9.3, a fix) Voice ID unsure but above the guest line (his voice through the phone's microphone), only his
    face in view: the careful calls and conversation mode don't take it for someone else. Another face in view, or
    a score under the guest line, still does."""
    from kurooto.core import nearby
    from kurooto.modules.voice import gate as gate_mod
    from kurooto.modules.voice.speakerid import Verdict

    v = voice
    who = Verdict("unsure", "not sure", 0.55, 2.0)
    v.voiceid.last_above = True
    nearby.set_view(v.app, 1, True)
    ctx = gate_mod.Context()
    v._moment(ctx, who)
    assert ctx.likely_owner and not ctx.unconfirmed()
    nearby.set_view(v.app, 2, False)  # someone else in view
    ctx = gate_mod.Context()
    v._moment(ctx, who)
    assert not ctx.likely_owner and ctx.unconfirmed()
    nearby.set_view(v.app, 1, True)
    v.voiceid.last_above = False  # under the guest line
    ctx = gate_mod.Context()
    v._moment(ctx, who)
    assert not ctx.likely_owner and ctx.unconfirmed()
    v.voiceid.last_above = True
    ctx = gate_mod.Context()
    v._moment(ctx, Verdict("guest", "someone else", 0.1, 2.0))
    assert not ctx.likely_owner and ctx.unconfirmed()

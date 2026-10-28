"""Voice's playing and recording internals (audio.py, 0.8.16): one thread owns each stream, a stop from another thread
never touches it, a microphone that goes away is opened again, and the PipeWire backend's command lines. Fakes only:
no sound device, no microphone, no speaker."""

from __future__ import annotations

import io
import threading
import time
from types import SimpleNamespace

import pytest

from kurooto.modules.voice import audio

FRAME_B = audio.FRAME * 2


class Stream:
    """A fake PortAudio stream that fails the test's checks (in `bad`) when two threads are inside it at once, when
    it's used after close, or when a thread other than its opener stops or closes it."""

    def __init__(self, sd, **kw):
        self.sd, self.kw = sd, kw
        self.owner = threading.current_thread()
        self.inside = 0
        self.closed = False
        self.active = False
        self.calls: list[tuple[str, str]] = []
        self._feeder: threading.Thread | None = None
        self._halt = threading.Event()
        sd.streams.append(self)
        sd.open_now += 1
        sd.most_open = max(sd.most_open, sd.open_now)
        if sd.open_error is not None:  # never opened: nothing to close
            err, sd.open_error = sd.open_error, None
            self.closed = True
            sd.open_now -= 1
            raise err

    def _enter(self, name: str) -> None:
        me = threading.current_thread()
        self.calls.append((name, me.name))
        if self.closed:
            self.sd.bad.append(f"{name} on a closed stream")
        if self.inside:
            self.sd.bad.append(f"{name} while another call was inside")
        if name in ("stop", "abort", "close") and me is not self.owner:
            self.sd.bad.append(f"{name} from {me.name}, not the stream's own thread")
        self.inside += 1

    def _leave(self) -> None:
        self.inside -= 1

    def start(self):
        self._enter("start")
        try:
            self.active = True
            cb = self.kw.get("callback")
            if cb is not None:
                self._feeder = threading.Thread(target=self._feed, args=(cb,), daemon=True)
                self._feeder.start()
        finally:
            self._leave()

    def _feed(self, cb):
        """PortAudio's own thread: frames to the callback until stopped, or until the device 'goes away'."""
        n = 0
        while not self._halt.is_set():
            if self.sd.die_after is not None and n >= self.sd.die_after:
                self.sd.die_after = None
                self.active = False  # the device vanished: the stream stops by itself
                return
            cb(bytes([1, 0]) * audio.FRAME, audio.FRAME, None, None)
            n += 1
            time.sleep(0.002)

    def write(self, data):
        self._enter("write")
        try:
            self.sd.written.append(len(data))
            time.sleep(0.01)
        finally:
            self._leave()

    def _halt_feeder(self):
        self._halt.set()
        if self._feeder is not None:
            self._feeder.join(1)
        self.active = False

    def stop(self):
        self._enter("stop")
        try:
            self._halt_feeder()
        finally:
            self._leave()

    def abort(self):
        self._enter("abort")
        try:
            self._halt_feeder()
        finally:
            self._leave()

    def close(self):
        self._enter("close")
        try:
            self._halt_feeder()
            if not self.closed:
                self.sd.open_now -= 1
            self.closed = True
        finally:
            self._leave()


class FakeSD:
    def __init__(self):
        self.streams: list[Stream] = []
        self.bad: list[str] = []
        self.written: list[int] = []
        self.open_error: Exception | None = None
        self.die_after: int | None = None
        self.open_now = self.most_open = 0

    def RawInputStream(self, **kw):  # noqa: N802 (sounddevice's name)
        return Stream(self, **kw)

    def RawOutputStream(self, **kw):  # noqa: N802
        return Stream(self, **kw)

    def query_devices(self, kind=None):
        return {"name": "Fake mic"}


@pytest.fixture
def sd(monkeypatch):
    fake = FakeSD()
    monkeypatch.setattr(audio, "_sd", lambda: fake)
    monkeypatch.setattr(audio, "REOPEN_S", 0.01)
    monkeypatch.setattr(audio, "REOPEN_MAX_S", 0.02)
    monkeypatch.setattr(audio, "STALL_S", 0.3)
    return fake


class Vad:
    def prob(self, frame):
        return 0.0

    def reset(self):
        pass


def wait_for(cond, s=3.0):
    end = time.monotonic() + s
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.005)
    return False


# ------------------------------------------------------------------------------------------- the microphone
def test_stop_from_another_thread_never_touches_the_stream(sd):
    heard = []
    lis = audio.Listener(audio.Mic(backend="portaudio"), Vad(), None, on_speech=lambda *a: None, on_level=heard.append)
    lis.start()
    assert wait_for(lambda: len(heard) > 5)
    lis.stop()  # this (the test's) thread: only asks
    assert not lis.running()  # joined: the reader closed its own stream before stop() returned
    (st,) = sd.streams
    assert st.closed and sd.bad == []
    assert {who for name, who in st.calls if name in ("abort", "close")} == {"voice-listen"}
    assert all(len(f) == FRAME_B for f in heard) and lis.error == ""


def test_many_stops_racing_the_reader(sd):
    """The old crash: close() under a running read. Many starts and stops from the main thread, none may reach a
    stream from outside its reader."""
    for _ in range(15):
        lis = audio.Listener(audio.Mic(backend="portaudio"), Vad(), None, on_speech=lambda *a: None)
        lis.start()
        time.sleep(0.003)
        lis.stop()
        lis.mic.close()  # twice, as Voice may
    assert wait_for(lambda: all(s.closed for s in sd.streams))
    assert sd.bad == []


def test_a_microphone_that_goes_away_is_opened_again(sd):
    sd.die_after = 5
    heard = []
    mic = audio.Mic(backend="portaudio")
    lis = audio.Listener(mic, Vad(), None, on_speech=lambda *a: None, on_level=heard.append)
    lis.start()
    assert wait_for(lambda: mic.reopened == 1 and len(heard) > 20)
    lis.stop()
    assert len(sd.streams) == 2 and all(s.closed for s in sd.streams) and sd.bad == [] and lis.error == ""


def test_a_microphone_that_never_opens_is_reported(sd):
    sd.open_error = RuntimeError("Error opening InputStream")
    lis = audio.Listener(audio.Mic(backend="portaudio"), Vad(), None, on_speech=lambda *a: None)
    lis._run()  # on this thread: it ends at once with the error, for Voice to tell and retry later
    assert "Error opening InputStream" in lis.error


def test_one_that_stays_gone_is_reported_after_a_few_tries(sd, monkeypatch):
    sd.die_after = 3
    mic = audio.Mic(backend="portaudio")

    real = sd.RawInputStream

    def gone(**kw):
        if len(sd.streams) >= 1:
            sd.open_error = OSError("device unavailable")
        return real(**kw)

    monkeypatch.setattr(sd, "RawInputStream", gone)
    lis = audio.Listener(mic, Vad(), None, on_speech=lambda *a: None)
    lis._run()
    assert "device unavailable" in lis.error
    assert len(sd.streams) == 1 + audio.REOPEN_TRIES and all(s.closed for s in sd.streams) and sd.bad == []


def test_a_named_number_is_sounddevices_device_number(sd):
    mic = audio.Mic("3", backend="portaudio")
    it = mic.frames()
    next(it)
    it.close()
    assert sd.streams[0].kw["device"] == 3 and sd.streams[0].closed


# --------------------------------------------------------------------------------------------- the player
def test_stopping_playback_from_another_thread(sd):
    p = audio.Player("portaudio")
    assert p.how == "sounddevice"
    t = threading.Thread(target=p.play, args=(b"\x00\x00" * 16000 * 5, 16000), name="voice-speak")
    t.start()
    assert wait_for(lambda: len(sd.written) >= 2)
    p.stop()
    t.join(2)
    assert not t.is_alive()
    (st,) = sd.streams
    assert st.closed and sd.bad == [] and len(sd.written) < 100  # 5 s is 100 pieces of 50 ms: cut short
    assert [n for n, _ in st.calls][-2:] == ["abort", "close"]


def test_a_finished_sentence_drains_and_closes(sd):
    p = audio.Player("portaudio")
    p.play(b"\x00\x00" * 1600, 16000)  # 0.1 s: two pieces
    (st,) = sd.streams
    assert sd.written == [1600, 1600] and [n for n, _ in st.calls] == ["start", "write", "write", "stop", "close"]


def test_two_threads_playing_take_turns(sd):
    p = audio.Player("portaudio")
    ts = [threading.Thread(target=p.play, args=(b"\x00\x00" * 4000, 16000)) for _ in range(3)]
    for t in ts:
        t.start()
    for t in ts:
        t.join(3)
    assert len(sd.streams) == 3 and all(s.closed for s in sd.streams) and sd.bad == []
    assert sd.most_open == 1  # one after another, never two at once


# ------------------------------------------------------------------------------------- the PipeWire backend
@pytest.fixture
def linux(monkeypatch):
    tools = {"pw-play", "pw-record", "parec", "paplay"}
    monkeypatch.setattr(audio.sys, "platform", "linux")
    monkeypatch.setattr(audio.shutil, "which", lambda p: f"/usr/bin/{p}" if p in tools else None)
    return tools


def test_auto_picks_pipewire_when_it_runs(linux, monkeypatch, tmp_path):
    (tmp_path / "pipewire-0").touch()
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    monkeypatch.delenv("PIPEWIRE_REMOTE", raising=False)
    monkeypatch.delenv("PIPEWIRE_RUNTIME_DIR", raising=False)
    assert audio.backend("auto") == "pipewire"
    assert audio.backend("auto", device="USB mic") == "portaudio"  # sounddevice's name: kept on sounddevice
    assert audio.backend("portaudio") == "portaudio" and audio.backend("PipeWire ") == "pipewire"
    (tmp_path / "pipewire-0").unlink()
    assert audio.backend("auto") == "portaudio"  # PipeWire not running
    assert audio.Player("auto").how in ("sounddevice", "pw-play", "paplay", "aplay")
    linux.discard("pw-record")
    (tmp_path / "pipewire-0").touch()
    assert audio.backend("auto") == "portaudio"  # its tools missing


def test_record_command_lines(linux):
    a = audio.Mic(backend="pipewire").record_args()
    assert a == [
        "pw-record", "--raw", "--format", "s16", "--rate", "16000", "--channels", "1", "--latency", "32ms", "-",
    ]  # fmt: skip
    a = audio.Mic("alsa_input.usb-mic", backend="pipewire").record_args()
    assert a[-3:] == ["--target", "alsa_input.usb-mic", "-"]
    assert "--target" not in audio.Mic("USB mic", backend="auto").record_args()  # sounddevice's name isn't PipeWire's
    linux.discard("pw-record")
    a = audio.Mic("alsa_input.usb-mic", backend="pipewire").record_args()
    assert a == [
        "parec",
        "--raw",
        "--format=s16le",
        "--rate=16000",
        "--channels=1",
        "--latency-msec=32",
        "--device=alsa_input.usb-mic",
    ]
    linux.discard("parec")
    assert audio.Mic(backend="pipewire").record_args() is None


class Proc:
    """A fake child: its stdout gives `data` then ends; terminate() ends it at once."""

    made: list[Proc] = []

    def __init__(self, args, stdin=None, stdout=None, stderr=None, data=b""):
        self.args = args
        self.returncode = None
        self.terminated = False
        self.stdout = io.BytesIO(data) if stdout is not None else None
        self.stdin = io.BytesIO() if stdin is not None else None
        Proc.made.append(self)

    def poll(self):
        if self.stdin is not None and self.stdin.closed and self.returncode is None:
            self.returncode = 0  # a player ends once its input does
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = -15

    def kill(self):
        self.returncode = -9

    def wait(self, timeout=None):
        if self.returncode is None:
            self.returncode = 0
        return self.returncode


def test_pw_play_command_line_and_stop(linux, monkeypatch):
    Proc.made = []
    monkeypatch.setattr(audio.subprocess, "Popen", Proc)
    p = audio.Player("pipewire")
    assert p.how == "pw-play"
    p.play(b"\x00\x00" * 100, 24000)
    (proc,) = Proc.made
    assert proc.args == [
        "pw-play", "--raw", "--format", "s16", "--rate", "24000", "--channels", "1", "--latency", "50ms", "-",
    ]  # fmt: skip
    p._proc = proc = Proc(["pw-play"], stdin=True)
    p.stop()  # from this thread: the child ended by its own pid
    assert proc.terminated


def test_the_recorder_is_started_again_when_it_ends(linux, monkeypatch):
    Proc.made = []
    chunks = [b"\x01\x00" * audio.FRAME * 3, b"\x02\x00" * audio.FRAME * 2]

    def popen(args, **kw):
        return Proc(args, data=chunks.pop(0) if chunks else b"", **kw)

    monkeypatch.setattr(audio.subprocess, "Popen", popen)
    monkeypatch.setattr(audio, "REOPEN_S", 0.001)
    monkeypatch.setattr(audio, "REOPEN_MAX_S", 0.002)
    mic = audio.Mic(backend="pipewire")
    got = []
    with pytest.raises(RuntimeError, match="pw-record stopped without sound"):
        for f in mic.frames():
            got.append(f)
    assert len(got) == 5 and mic.reopened == 1 and len(Proc.made) == 2 + audio.REOPEN_TRIES
    assert Proc.made[0].args[0] == "pw-record"


def test_close_from_another_thread_ends_the_recorder(linux, monkeypatch):
    mic = audio.Mic(backend="pipewire")
    proc = SimpleNamespace(poll=lambda: None, terminate=lambda: setattr(proc, "done", True), done=False)
    mic._proc = proc
    mic.close()
    assert proc.done and mic._closed.is_set()


def test_a_recorder_that_never_gives_sound_is_reported(linux, monkeypatch):
    monkeypatch.setattr(audio.subprocess, "Popen", lambda args, **kw: Proc(args, **kw))
    lis = audio.Listener(audio.Mic(backend="pipewire"), Vad(), None, on_speech=lambda *a: None)
    lis._run()
    assert "pw-record stopped without sound" in lis.error


# ------------------------------------------------------------------------------------- auto gain (0.8.17)
def _tone(level: int, frames: int = 10) -> bytes:
    import math as _m

    return b"".join(int(level * _m.sin(i / 3)).to_bytes(2, "little", signed=True) for i in range(audio.FRAME * frames))


def test_gain_needs_speech_above_the_room_s_noise():
    g = audio.Gain(6)
    assert g.loud_enough(_tone(100, 1))  # nothing known about the room yet: yes
    for _ in range(200):
        g.quiet(_tone(800, 1))  # a noisy room
    assert not g.loud_enough(_tone(1000, 1))  # barely above it
    assert g.loud_enough(_tone(3000, 1))  # clearly above it
    assert g.status()["noise_db"] is not None


def test_gain_brings_a_quiet_stretch_up_but_never_down_or_past_full_scale():
    g = audio.Gain()
    quiet = _tone(300)
    up = g.level(quiet, b"\x01" * 10)
    assert len(up) == len(quiet) and g.gain == audio.Gain.MOST  # 300 -> as far as 8x allows
    loud = _tone(20000)
    assert g.level(loud, b"\x01" * 10) == loud and g.gain == 1.0  # never turned down
    peaky = _tone(2000) + _tone(30000, 1)
    out = g.level(peaky, b"\x01" * 11)
    import array as _a

    a = _a.array("h")
    a.frombytes(out)
    assert max(a) <= 32767 * 0.96  # never clipped

"""The sound side of Voice: speaking (Kokoro or Piper), playing, the microphone, voice activity (Silero), writing
out speech (faster-whisper) and the wake word (openWakeWord). Every engine is imported only when it's used, from
the packages parts.py installed; nothing here is needed for Kurooto to start, and nothing here reaches the internet.

Sound from the microphone stays in memory: a rolling pre-roll of under a second, and the stretch of speech being
cut out, which is handed to the transcriber and then dropped. Nothing is ever written to disk.

Playing: sounddevice when it has an output device; else PipeWire's pw-play, PulseAudio's paplay or ALSA's aplay
(Linux), afplay (macOS, from a temporary WAV file of the reply, deleted after), winsound (Windows, from memory).
Recording: sounddevice; else pw-record or parec (Linux)."""

from __future__ import annotations

import collections
import io
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import wave
from collections.abc import Callable, Iterator
from pathlib import Path

RATE = 16000  # the microphone, the VAD, the transcriber and the wake word all work at 16 kHz mono
FRAME = 512  # samples per VAD frame (32 ms): Silero v5's size at 16 kHz
WAKE_CHUNK = 1280  # samples per wake-word step (80 ms): openWakeWord's size


def _np():
    import numpy

    return numpy


# ------------------------------------------------------------------------------------------------- speaking
class Kokoro:
    name = "kokoro"

    def __init__(self, model: Path, voices: Path, voice: str = "", rate: float = 1.0):
        from kokoro_onnx import Kokoro as K  # noqa: N814

        self.k = K(str(model), str(voices))
        self.voice = voice or "af_heart"
        self.rate = rate

    def synth(self, text: str) -> tuple[bytes, int]:
        np = _np()
        lang = "en-gb" if self.voice[:1] == "b" else "en-us"
        samples, sr = self.k.create(text, voice=self.voice, speed=float(self.rate), lang=lang)
        pcm = (np.clip(np.asarray(samples, dtype="float32"), -1, 1) * 32767).astype("<i2").tobytes()
        return pcm, int(sr)


class Piper:
    name = "piper"

    def __init__(self, model: Path, rate: float = 1.0):
        from piper import PiperVoice

        self.v = PiperVoice.load(str(model))
        self.rate = rate

    def synth(self, text: str) -> tuple[bytes, int]:
        scale = 1.0 / max(0.5, min(2.0, float(self.rate)))
        sr = int(getattr(getattr(self.v, "config", None), "sample_rate", 22050))
        if hasattr(self.v, "synthesize_stream_raw"):  # piper-tts 1.2
            return b"".join(self.v.synthesize_stream_raw(text, length_scale=scale)), sr
        try:  # piper-tts 1.3: chunks of audio
            from piper import SynthesisConfig

            chunks = list(self.v.synthesize(text, syn_config=SynthesisConfig(length_scale=scale)))
        except ImportError:
            chunks = list(self.v.synthesize(text))
        if chunks:
            sr = int(getattr(chunks[0], "sample_rate", sr))
        return b"".join(getattr(c, "audio_int16_bytes", b"") for c in chunks), sr


# --------------------------------------------------------------------------------------------------- playing
def wav_bytes(pcm: bytes, sr: int) -> bytes:
    b = io.BytesIO()
    with wave.open(b, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm)
    return b.getvalue()


class Player:
    """Plays 16-bit mono sound through the default output, by whatever this computer has."""

    def __init__(self):
        self.how = self.detect()
        self._proc: subprocess.Popen | None = None
        self._stop = threading.Event()

    @staticmethod
    def detect() -> str:
        try:
            import sounddevice as sd

            sd.query_devices(kind="output")
            return "sounddevice"
        except Exception:
            pass
        if sys.platform.startswith("linux"):
            for prog in ("pw-play", "paplay", "aplay"):
                if shutil.which(prog):
                    return prog
        if sys.platform == "darwin" and shutil.which("afplay"):
            return "afplay"
        if sys.platform == "win32":
            return "winsound"
        return ""

    def play(self, pcm: bytes, sr: int) -> None:
        self._stop.clear()
        how = self.how
        if how == "sounddevice":
            import sounddevice as sd

            np = _np()
            sd.play(np.frombuffer(pcm, dtype="<i2"), sr)
            while sd.get_stream().active and not self._stop.is_set():
                time.sleep(0.05)
            if self._stop.is_set():
                sd.stop()
            return
        if how == "winsound":
            import winsound  # type: ignore[import-not-found]

            winsound.PlaySound(wav_bytes(pcm, sr), winsound.SND_MEMORY)
            return
        if how == "afplay":
            fd, name = tempfile.mkstemp(suffix=".wav", prefix="kurooto-say-")
            try:
                with os.fdopen(fd, "wb") as f:
                    f.write(wav_bytes(pcm, sr))
                self._run(["afplay", name], b"")
            finally:
                Path(name).unlink(missing_ok=True)
            return
        args = {
            "pw-play": ["pw-play", "--format", "s16", "--rate", str(sr), "--channels", "1", "-"],
            "paplay": ["paplay", "--raw", "--format=s16le", f"--rate={sr}", "--channels=1"],
            "aplay": ["aplay", "-q", "-t", "raw", "-f", "S16_LE", "-r", str(sr), "-c", "1", "-"],
        }.get(how)
        if not args:
            raise RuntimeError("no way to play sound on this computer")
        self._run(args, pcm)

    def _run(self, args: list[str], data: bytes) -> None:
        p = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self._proc = p
        try:
            if data and p.stdin:
                try:
                    p.stdin.write(data)
                except BrokenPipeError:
                    pass
            if p.stdin:
                p.stdin.close()
            while p.poll() is None:
                if self._stop.is_set():
                    p.terminate()  # its own child, by its exact pid
                    break
                time.sleep(0.05)
            p.wait(timeout=5)
        finally:
            self._proc = None

    def stop(self) -> None:
        self._stop.set()


# ---------------------------------------------------------------------------------------------- microphone
def microphone() -> tuple[bool | None, str]:
    """Is there a microphone? (True, its name) / (False, why) / (None, "can't tell") without sounddevice or tools."""
    try:
        import sounddevice as sd

        d = sd.query_devices(kind="input")
        return True, str(d.get("name") or "the default microphone")
    except ImportError:
        pass
    except Exception as e:
        return False, f"no microphone found ({type(e).__name__})"
    if sys.platform.startswith("linux") and shutil.which("pactl"):
        try:
            out = subprocess.run(
                ["pactl", "list", "short", "sources"], capture_output=True, text=True, timeout=5
            ).stdout.splitlines()
        except (OSError, subprocess.SubprocessError):
            return None, "can't tell"
        mics = [ln.split("\t")[1] for ln in out if "\t" in ln and ".monitor" not in ln]
        return (True, mics[0]) if mics else (False, "no microphone found")
    return None, "can't tell"


class Mic:
    """16 kHz mono 16-bit frames of FRAME samples, as bytes, until close()."""

    def __init__(self, device: str = ""):
        self.device = device or None
        self._proc: subprocess.Popen | None = None
        self._stream = None
        self._closed = threading.Event()

    def frames(self) -> Iterator[bytes]:
        try:
            import sounddevice as sd

            self._stream = sd.RawInputStream(
                samplerate=RATE, channels=1, dtype="int16", blocksize=FRAME, device=self.device
            )
            self._stream.start()
            while not self._closed.is_set():
                data, _overflowed = self._stream.read(FRAME)
                yield bytes(data)
            return
        except ImportError:
            pass
        args = None
        if sys.platform.startswith("linux"):
            if shutil.which("pw-record"):
                args = ["pw-record", "--format", "s16", "--rate", str(RATE), "--channels", "1", "-"]
            elif shutil.which("parec"):
                args = ["parec", "--raw", "--format=s16le", f"--rate={RATE}", "--channels=1"]
        if not args:
            raise RuntimeError("no way to record sound: sounddevice isn't installed and no pw-record or parec")
        self._proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        size = FRAME * 2
        while not self._closed.is_set() and self._proc.stdout:
            data = self._proc.stdout.read(size)
            if not data:
                break
            yield data

    def close(self) -> None:
        self._closed.set()
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
        if self._proc is not None and self._proc.poll() is None:
            self._proc.terminate()  # its own child, by its exact pid


# ---------------------------------------------------------------------------------------- voice activity
class Silero:
    """Silero VAD (ONNX) frame by frame: the probability that a FRAME of sound is speech."""

    def __init__(self, model: Path):
        import onnxruntime as ort

        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 1
        opts.inter_op_num_threads = 1
        self.s = ort.InferenceSession(str(model), sess_options=opts, providers=["CPUExecutionProvider"])
        self.inputs = {i.name for i in self.s.get_inputs()}
        self.reset()

    def reset(self) -> None:
        np = _np()
        self.state = np.zeros((2, 1, 128), dtype="float32")
        self.h = np.zeros((2, 1, 64), dtype="float32")
        self.c = np.zeros((2, 1, 64), dtype="float32")
        self.context = np.zeros(64, dtype="float32")

    def prob(self, frame: bytes) -> float:
        np = _np()
        x = np.frombuffer(frame, dtype="<i2").astype("float32") / 32768.0
        sr = np.array(RATE, dtype="int64")
        if "state" in self.inputs:  # v5: 64 samples of context before each frame
            inp = np.concatenate([self.context, x])[None, :]
            out, self.state = self.s.run(None, {"input": inp, "state": self.state, "sr": sr})
            self.context = x[-64:]
        else:  # v4
            out, self.h, self.c = self.s.run(None, {"input": x[None, :], "sr": sr, "h": self.h, "c": self.c})
        return float(np.asarray(out).reshape(-1)[0])


class Energy:
    """A stand-in when Silero isn't there: loud enough counts as speech (much worse at telling noise apart)."""

    def __init__(self, floor: float = 0.02):
        self.floor = floor

    def reset(self) -> None:
        pass

    def prob(self, frame: bytes) -> float:
        import array
        import math

        a = array.array("h")
        a.frombytes(frame)
        rms = math.sqrt(sum(x * x for x in a) / max(1, len(a))) / 32768
        return 1.0 if rms > self.floor else 0.0


# ----------------------------------------------------------------------------------------- writing it out
class Whisper:
    """faster-whisper on the processor. `hint` (the assistant's name) is its initial prompt and hotword, so an
    unusual name is written the way it's spelled more often (names.py catches the rest)."""

    def __init__(self, model_dir: Path, language: str = "", hint: str = ""):
        from faster_whisper import WhisperModel

        self.m = WhisperModel(str(model_dir), device="cpu", compute_type="int8")
        self.language = language or None
        self.hint = hint.strip()

    def text(self, pcm: bytes) -> str:
        np = _np()
        audio = np.frombuffer(pcm, dtype="<i2").astype("float32") / 32768.0
        kw = dict(language=self.language, beam_size=1, vad_filter=False, condition_on_previous_text=False)
        if self.hint:
            kw["initial_prompt"] = f"{self.hint}."
            kw["hotwords"] = self.hint
        try:
            segs, _info = self.m.transcribe(audio, **kw)
        except TypeError:  # a faster-whisper before hotwords (1.0.2)
            kw.pop("hotwords", None)
            segs, _info = self.m.transcribe(audio, **kw)
        return " ".join(s.text.strip() for s in segs).strip()


# ---------------------------------------------------------------------------------------------- wake word
class Wake:
    def __init__(self, model: Path, melspec: Path, embedding: Path):
        from openwakeword.model import Model

        try:
            self.m = Model(
                wakeword_models=[str(model)],
                inference_framework="onnx",
                melspec_model_path=str(melspec),
                embedding_model_path=str(embedding),
            )
        except TypeError:  # an openwakeword without those arguments: its own copies
            self.m = Model(wakeword_models=[str(model)], inference_framework="onnx")

    def score(self, chunk: bytes) -> float:
        np = _np()
        scores = self.m.predict(np.frombuffer(chunk, dtype="<i2"))
        return float(max(scores.values(), default=0.0))

    def reset(self) -> None:
        try:
            self.m.reset()
        except Exception:
            pass


# ------------------------------------------------------------------------------------------------- listener
class Listener:
    """Cuts the microphone's sound into stretches of speech and hands each one on (with whether the wake word fired),
    on a thread of its own. `hold()` true (Kurooto speaking): sound is dropped, so it doesn't hear itself."""

    START, STOP = 0.5, 0.35  # speech probability to start a stretch, and below which counts as quiet
    END_MS = 700  # this much quiet ends a stretch
    PRE_MS = 320  # sound kept from before the start (the rolling buffer)
    MAX_S = 15  # a stretch is cut here at the latest

    def __init__(
        self,
        mic: Mic,
        vad,
        wake: Wake | None,
        on_speech: Callable[..., None],  # (sound, woke, seconds, flags): flags is the VAD's 1/0 per FRAME
        on_level: Callable[[bytes], None] | None = None,
        on_start: Callable[[], None] | None = None,
        hold: Callable[[], bool] = lambda: False,
        wake_threshold: float = 0.5,
    ):
        self.mic, self.vad, self.wake = mic, vad, wake
        self.on_speech, self.on_level, self.on_start, self.hold = on_speech, on_level, on_start, hold
        self.wake_threshold = wake_threshold
        self.thread: threading.Thread | None = None
        self.error = ""
        self._stop = threading.Event()

    def start(self) -> None:
        self.thread = threading.Thread(target=self._run, name="voice-listen", daemon=True)
        self.thread.start()

    def running(self) -> bool:
        return self.thread is not None and self.thread.is_alive()

    def stop(self) -> None:
        self._stop.set()
        self.mic.close()

    def _run(self) -> None:
        frame_ms = FRAME * 1000 / RATE
        pre: collections.deque[bytes] = collections.deque(maxlen=max(1, int(self.PRE_MS / frame_ms)))
        buf: bytearray | None = None
        flags = bytearray()  # (voice id) speech or not, per frame of buf: speech seconds and the noise floor
        quiet = 0
        wake_buf = bytearray()
        woke_at = 0.0
        try:
            for frame in self.mic.frames():
                if self._stop.is_set():
                    break
                if self.on_level is not None:
                    self.on_level(frame)
                if self.hold():
                    pre.clear()
                    buf, quiet = None, 0
                    flags = bytearray()
                    wake_buf.clear()
                    self.vad.reset()
                    continue
                if self.wake is not None:
                    wake_buf += frame
                    while len(wake_buf) >= WAKE_CHUNK * 2:
                        if self.wake.score(bytes(wake_buf[: WAKE_CHUNK * 2])) >= self.wake_threshold:
                            woke_at = time.monotonic()
                            self.wake.reset()
                        del wake_buf[: WAKE_CHUNK * 2]
                p = self.vad.prob(frame)
                if buf is None:
                    if p >= self.START:
                        flags = bytearray(len(pre)) + b"\x01"
                        buf = bytearray(b"".join(pre)) + frame
                        pre.clear()
                        quiet = 0
                        if self.on_start:
                            self.on_start()
                    else:
                        pre.append(frame)
                    continue
                buf += frame
                flags.append(1 if p >= self.START else 0)
                quiet = quiet + 1 if p < self.STOP else 0
                if quiet * frame_ms >= self.END_MS or len(buf) >= self.MAX_S * RATE * 2:
                    seconds = len(buf) / (RATE * 2)
                    woke = time.monotonic() - woke_at <= seconds + 2
                    audio, cut = bytes(buf), bytes(flags)
                    buf, quiet, flags = None, 0, bytearray()
                    self.vad.reset()
                    self.on_speech(audio, woke, seconds, cut)
                    del audio
                    if woke:
                        woke_at = 0.0
        except Exception as e:
            self.error = f"{type(e).__name__}: {e}"[:300]
        finally:
            self.mic.close()

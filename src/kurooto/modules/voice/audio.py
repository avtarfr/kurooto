"""The sound side of Voice: speaking (Kokoro or Piper), playing, the microphone, voice activity (Silero), writing
out speech (faster-whisper) and the wake word (openWakeWord). Every engine is imported only when it's used, from
the packages parts.py installed; nothing here is needed for Kurooto to start, and nothing here reaches the internet.

Sound from the microphone stays in memory: a rolling pre-roll of under a second, and the stretch of speech being
cut out, which is handed to the transcriber and then dropped. Nothing is ever written to disk.

Two ways in and out (voice.audio.backend): "pipewire" plays through pw-play and records through pw-record, child
processes, so no audio library runs inside Kurooto; "portaudio" uses sounddevice (PortAudio). "auto", the default,
picks pipewire on Linux when PipeWire is running and its tools are installed (and no sounddevice microphone was named),
else portaudio. Playing otherwise falls back to pw-play, PulseAudio's paplay or ALSA's aplay (Linux), afplay (macOS,
from a temporary WAV file of the reply, deleted after), winsound (Windows, from memory). Recording otherwise falls back
to pw-record or parec (Linux).

Threads (the 0.8.10-0.8.14 crash): a PortAudio stream is opened, read or written, stopped and closed only by the one
thread that plays or reads it. stop() and close() from any other thread only set a flag (and end a child process);
closing a stream under another thread's blocking read freed ALSA's memory while it was in use, and the daemon died
in snd_pcm_poll_descriptors_revents."""

from __future__ import annotations

import array
import collections
import io
import os
import queue
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

BACKENDS = ("auto", "portaudio", "pipewire")
REOPEN_S = 1.0  # a microphone that went away is opened again after this long, doubling up to REOPEN_MAX_S
REOPEN_MAX_S = 8.0
REOPEN_TRIES = 6  # this many tries in a row without sound and the Listener reports it (Voice tries again later)
STALL_S = 3.0  # an open microphone silent this long has gone (a PipeWire source removed); real silence still flows
QUEUE_FRAMES = 64  # about 2 s the reader may fall behind PortAudio's callback before the oldest frames are dropped
JOIN_S = 0.5  # Listener.stop waits this long for its reader to close its own stream
STT_THREADS = 4  # (0.9.2, a fix) the transcriber's threads (faster-whisper's own default could be every core)
TTS_THREADS = 2  # (0.9.2, a fix) Kokoro's threads (onnxruntime's default is every core); CAM++ has 2 (speakerid.py)
PLAY_CHUNK_S = 0.05  # written to the output this much at a time, so a stop takes effect within about 50 ms


def _np():
    import numpy

    return numpy


def _sd():
    """sounddevice, imported when first needed (tests put a fake here)."""
    import sounddevice

    return sounddevice


def pipewire_running() -> bool:
    """Linux with pw-play and pw-record installed and this user's PipeWire socket present."""
    if not sys.platform.startswith("linux") or not (shutil.which("pw-play") and shutil.which("pw-record")):
        return False
    remote = os.environ.get("PIPEWIRE_REMOTE") or "pipewire-0"
    if os.path.isabs(remote):
        return os.path.exists(remote)
    run = os.environ.get("PIPEWIRE_RUNTIME_DIR") or os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    return os.path.exists(os.path.join(run, remote))


def backend(choice: str = "auto", device: str = "") -> str:
    """voice.audio.backend made concrete: "portaudio" or "pipewire". auto keeps portaudio when a microphone was named,
    since voice.listen.device holds sounddevice's names, which PipeWire doesn't know."""
    c = str(choice or "auto").strip().lower()
    if c in ("portaudio", "pipewire"):
        return c
    return "pipewire" if not device and pipewire_running() else "portaudio"


# ------------------------------------------------------------------------------------------------- speaking
class Kokoro:
    name = "kokoro"

    def __init__(self, model: Path, voices: Path, voice: str = "", rate: float = 1.0):
        from kokoro_onnx import Kokoro as K  # noqa: N814

        self.k = None
        if hasattr(K, "from_session"):  # (0.9.2, a fix) TTS_THREADS threads, not every core
            try:
                import onnxruntime as ort

                opts = ort.SessionOptions()
                opts.intra_op_num_threads = TTS_THREADS
                opts.inter_op_num_threads = 1
                sess = ort.InferenceSession(str(model), sess_options=opts, providers=["CPUExecutionProvider"])
                self.k = K.from_session(sess, str(voices))
            except Exception:
                self.k = None
        if self.k is None:
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

    def __init__(self, backend: str = "auto"):
        self.choice = str(backend or "auto")
        self.how = self.detect(self.choice)
        self._proc: subprocess.Popen | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()  # one sound at a time: its stream belongs to the play() holding this

    @staticmethod
    def detect(choice: str = "auto") -> str:
        if backend(choice) == "pipewire" and shutil.which("pw-play"):
            return "pw-play"
        try:
            sd = _sd()
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
        with self._lock:
            self._stop.clear()
            self._play(pcm, sr)

    def _play(self, pcm: bytes, sr: int) -> None:
        how = self.how
        if how == "sounddevice":
            self._play_stream(pcm, sr)
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
        pw = ["pw-play", "--raw", "--format", "s16", "--rate", str(sr), "--channels", "1", "--latency", "50ms", "-"]
        args = {
            "pw-play": pw,
            "paplay": ["paplay", "--raw", "--format=s16le", f"--rate={sr}", "--channels=1"],
            "aplay": ["aplay", "-q", "-t", "raw", "-f", "S16_LE", "-r", str(sr), "-c", "1", "-"],
        }.get(how)
        if not args:
            raise RuntimeError("no way to play sound on this computer")
        self._run(args, pcm)

    def _play_stream(self, pcm: bytes, sr: int) -> None:
        """A stream of its own, opened, written and closed on this thread only. sounddevice's play() and stop() share
        one module-wide stream that any thread could close under another's feet."""
        sd = _sd()
        step = max(1, int(sr * PLAY_CHUNK_S)) * 2
        stream = sd.RawOutputStream(samplerate=sr, channels=1, dtype="int16")
        try:
            stream.start()
            for i in range(0, len(pcm), step):
                if self._stop.is_set():
                    break
                stream.write(pcm[i : i + step])
            if self._stop.is_set():
                stream.abort()  # drops what's queued
            else:
                stream.stop()  # lets what's queued finish
        finally:
            stream.close()

    def _run(self, args: list[str], data: bytes) -> None:
        p = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self._proc = p
        try:
            if data and p.stdin:
                try:  # a piece at a time: a whole answer would block here, deaf to stop(), until nearly played
                    for i in range(0, len(data), 4096):
                        if self._stop.is_set():
                            break
                        p.stdin.write(data[i : i + 4096])
                except (BrokenPipeError, ValueError):
                    pass
            if p.stdin:
                try:
                    p.stdin.close()
                except BrokenPipeError:
                    pass
            while p.poll() is None:
                if self._stop.is_set():
                    p.terminate()  # its own child, by its exact pid
                    break
                time.sleep(0.05)
            p.wait(timeout=5)
        finally:
            self._proc = None

    def stop(self) -> None:
        """From any thread. A PortAudio stream is never touched here: the playing thread sees the flag and aborts and
        closes its own. A player child is ended at once, by its exact pid (no native code shared, so that's safe)."""
        self._stop.set()
        p = self._proc
        if p is not None and p.poll() is None:
            try:
                p.terminate()
            except OSError:
                pass


# ---------------------------------------------------------------------------------------------- microphone
def microphone() -> tuple[bool | None, str]:
    """Is there a microphone? (True, its name) / (False, why) / (None, "can't tell") without sounddevice or tools."""
    try:
        sd = _sd()
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
    """16 kHz mono 16-bit frames of FRAME samples, as bytes, until close(). The thread that iterates frames() alone
    opens, reads and closes the stream or the recorder; close() from another thread only asks it to stop (and ends a
    recorder child, which wakes its read). A microphone that goes away is opened again after a pause."""

    def __init__(self, device: str = "", backend: str = "auto"):
        self.device = device or None
        self.choice = str(backend or "auto")
        self._proc: subprocess.Popen | None = None
        self._closed = threading.Event()
        self.reopened = 0  # times it was opened again after going away

    def how(self) -> str:
        return backend(self.choice, self.device or "")

    def frames(self) -> Iterator[bytes]:
        src = None
        if self.how() == "portaudio":
            try:
                src = self._portaudio(_sd())
            except ImportError:
                src = None
        if src is None:
            src = self._recorder()
        size = FRAME * 2
        buf = bytearray()
        try:
            for data in src:
                buf += data
                while len(buf) >= size:
                    yield bytes(buf[:size])
                    del buf[:size]
        finally:
            src.close()  # this thread: the stream or recorder is closed by the one that read it

    def _sd_device(self):
        d = self.device
        return int(d) if isinstance(d, str) and d.strip().isdigit() else d  # "3": sounddevice's device number 3

    def _portaudio(self, sd) -> Iterator[bytes]:
        """Callback mode: PortAudio's own thread fills a queue and this thread never sits inside a blocking PortAudio
        call, so its stop and close (here, in finally) never race a read."""
        fails, heard = 0, False
        while not self._closed.is_set():
            q: queue.Queue[bytes] = queue.Queue(maxsize=QUEUE_FRAMES)
            stream = None
            try:
                stream = sd.RawInputStream(
                    samplerate=RATE,
                    channels=1,
                    dtype="int16",
                    blocksize=FRAME,
                    device=self._sd_device(),
                    callback=_queue_callback(q),
                )
                stream.start()
            except Exception:
                _shut(stream)
                if not heard:
                    raise  # never worked: the Listener reports it and Voice tries again later
                fails += 1
                if fails >= REOPEN_TRIES:
                    raise
                self._closed.wait(min(REOPEN_MAX_S, REOPEN_S * 2 ** (fails - 1)))
                continue
            got = False
            try:
                last = time.monotonic()
                while not self._closed.is_set():
                    try:
                        data = q.get(timeout=0.1)
                    except queue.Empty:
                        if not stream.active or time.monotonic() - last > STALL_S:
                            break  # it went away: closed below, opened again after a pause
                        continue
                    last = time.monotonic()
                    if not got and heard:
                        self.reopened += 1
                    got = heard = True
                    fails = 0
                    yield data
            finally:
                _shut(stream)
            if self._closed.is_set():
                return
            if not got:
                fails += 1
                if not heard or fails >= REOPEN_TRIES:
                    raise RuntimeError("the microphone stopped sending sound")
            self._closed.wait(min(REOPEN_MAX_S, REOPEN_S * 2 ** max(0, fails - 1)))

    def record_args(self) -> list[str] | None:
        """The recorder's command line: pw-record, else parec (Linux). A device is passed on only when PipeWire was
        chosen by name, since voice.listen.device otherwise holds sounddevice's names."""
        if not sys.platform.startswith("linux"):
            return None
        target = str(self.device) if self.device and self.choice.strip().lower() == "pipewire" else ""
        if shutil.which("pw-record"):
            args = [
                "pw-record",
                "--raw",
                "--format",
                "s16",
                "--rate",
                str(RATE),
                "--channels",
                "1",
                "--latency",
                "32ms",
            ]
            if target:
                args += ["--target", target]
            return args + ["-"]
        if shutil.which("parec"):
            args = ["parec", "--raw", "--format=s16le", f"--rate={RATE}", "--channels=1", "--latency-msec=32"]
            if target:
                args.append(f"--device={target}")
            return args
        return None

    def _recorder(self) -> Iterator[bytes]:
        """A recorder child read on this thread; when it ends by itself (PipeWire restarted, the source went), a new
        one is started after a pause."""
        args = self.record_args()
        if not args:
            raise RuntimeError("no way to record sound: sounddevice isn't installed and no pw-record or parec")
        fails, heard = 0, False
        while not self._closed.is_set():
            p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            self._proc = p
            got = False
            try:
                while not self._closed.is_set() and p.stdout:
                    data = p.stdout.read(FRAME * 2)
                    if not data:
                        break
                    if not got and heard:
                        self.reopened += 1
                    got = heard = True
                    fails = 0
                    yield data
            finally:
                self._proc = None
                _end(p)
            if self._closed.is_set():
                return
            if not got:
                fails += 1
                if not heard or fails >= REOPEN_TRIES:
                    raise RuntimeError(f"{args[0]} stopped without sound (exit {p.returncode})")
            self._closed.wait(min(REOPEN_MAX_S, REOPEN_S * 2 ** max(0, fails - 1)))

    def close(self) -> None:
        """From any thread: asks the reader to stop. A PortAudio stream is never touched here (the reader closes it
        within 0.1 s); a recorder child is ended, by its exact pid, so its blocked read returns."""
        self._closed.set()
        p = self._proc
        if p is not None and p.poll() is None:
            try:
                p.terminate()
            except OSError:
                pass


def _queue_callback(q: queue.Queue):
    """PortAudio's callback (its own thread): the frame into the queue, the oldest dropped when the reader is behind."""

    def cb(indata, _frames, _time, _status) -> None:
        data = bytes(indata)
        try:
            q.put_nowait(data)
        except queue.Full:
            try:
                q.get_nowait()
                q.put_nowait(data)
            except (queue.Empty, queue.Full):
                pass

    return cb


def _shut(stream) -> None:
    """Stops and closes a stream, on the thread that owns it."""
    if stream is None:
        return
    for step in ("abort", "close"):
        try:
            getattr(stream, step)()
        except Exception:
            pass


def _end(p: subprocess.Popen) -> None:
    """Ends a child of ours by its exact pid, and reaps it."""
    if p.poll() is None:
        try:
            p.terminate()
            p.wait(timeout=2)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait(timeout=2)
        except OSError:
            pass
    if p.stdout:
        try:
            p.stdout.close()
        except OSError:
            pass


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

        try:  # (0.9.2, a fix) a fixed number of threads, so it never fights Kokoro and CAM++ for every core
            self.m = WhisperModel(str(model_dir), device="cpu", compute_type="int8", cpu_threads=STT_THREADS)
        except TypeError:
            self.m = WhisperModel(str(model_dir), device="cpu", compute_type="int8")
        self.language = language or None
        self.hint = hint.strip()
        self.lock = threading.Lock()  # one stretch at a time (as the model's one worker does): its wait is measured
        self.last_wait = 0.0  # (0.9.2) seconds the last call waited for another stretch to finish

    def text(self, pcm: bytes) -> str:
        t0 = time.monotonic()
        with self.lock:
            self.last_wait = time.monotonic() - t0
            return self._text(pcm)

    def _text(self, pcm: bytes) -> str:
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


# ------------------------------------------------------------------------------------------------ auto gain
def _rms(a: array.array) -> float:
    return (sum(x * x for x in a) / max(1, len(a))) ** 0.5 / 32768


class Gain:
    """(voice.listen.auto_gain, 0.8.17) Hearing that follows the room, inside Kurooto only (the system's microphone
    volume is never changed, so calls and other apps hear as before):

    - **The noise floor:** the loudness of what isn't speech, followed over a few seconds. Speech starts a stretch only
      when it is at least `snr_db` above it, so a noisy room asks for a clearer voice and a quiet one hears a soft one.
    - **One level:** a stretch is brought to TARGET loudness (its speech only, never turned down, at most MOST times,
      never clipped) before it's written out, so a quiet or far voice reads as well as a near one.

    Numbers only: nothing is kept but the floor and the last gain."""

    TARGET = 0.08  # the speech's RMS (0..1) a stretch is brought to, about -22 dBFS
    MOST = 8.0  # at most this many times louder
    NOISE_S = 4.0  # the floor follows the room over about this long
    FLOOR = 0.002  # the floor is never taken as lower than this (about -54 dBFS)

    def __init__(self, snr_db: float = 6.0):
        self.snr = 10 ** (max(0.0, float(snr_db)) / 20)
        self.noise: float | None = None
        self.gain = 1.0

    def quiet(self, frame: bytes) -> None:
        """A frame that isn't speech: the floor follows it."""
        a = array.array("h")
        a.frombytes(frame[: len(frame) - len(frame) % 2])
        r = _rms(a)
        k = min(1.0, FRAME / RATE / self.NOISE_S)
        self.noise = r if self.noise is None else self.noise + k * (r - self.noise)

    def loud_enough(self, frame: bytes) -> bool:
        """Clearly above the room's noise (nothing known about the room yet: yes)."""
        if self.noise is None:
            return True
        a = array.array("h")
        a.frombytes(frame[: len(frame) - len(frame) % 2])
        return _rms(a) >= max(self.FLOOR, self.noise) * self.snr

    def level(self, pcm: bytes, flags: bytes = b"") -> bytes:
        """The stretch at one level: its speech frames' loudness (flags: the VAD's 1/0 per FRAME) set the gain."""
        a = array.array("h")
        a.frombytes(pcm[: len(pcm) - len(pcm) % 2])
        if not a:
            return pcm
        speech = array.array("h")
        for i, f in enumerate(flags):
            if f:
                speech.extend(a[i * FRAME : (i + 1) * FRAME])
        r = _rms(speech if len(speech) else a)
        peak = max(1, max(a), -min(a))
        g = min(self.MOST, self.TARGET / r if r > 0 else 1.0, 0.95 * 32767 / peak)
        if g <= 1.05:
            self.gain = 1.0
            return pcm
        self.gain = round(g, 2)
        out = array.array("h", (int(x * g) for x in a))
        return out.tobytes()

    def status(self) -> dict:
        import math

        noise = None if self.noise is None else round(20 * math.log10(max(self.noise, 1e-6)), 1)
        return {"noise_db": noise, "gain": self.gain}


EARLY_MS = 300  # (voice.listen.early) a pause this long hands the stretch so far on early


# ------------------------------------------------------------------------------------------------- listener
class Listener:
    """Cuts the microphone's sound into stretches of speech and hands each one on (with whether the wake word fired),
    on a thread of its own. `hold()` true (Kurooto speaking): sound is dropped, so it doesn't hear itself; unless
    `barge` (barge.py, voice.listen.barge_in) wants it: then each frame and its speech probability go there instead,
    which tells Kurooto's own voice coming back from you talking over it."""

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
        barge=None,
        gain: Gain | None = None,
        early=None,
        aec=None,
    ):
        self.gain = gain  # voice.listen.auto_gain: the room's noise floor and one level (Gain)
        # (0.9.3, voice.listen.aec) every frame through aec.process() first: its own voice taken out before the VAD,
        # barge-in, Voice ID and the levels hear it; one that fails is dropped (the sound goes on as heard)
        self.aec = aec
        self.aec_error = ""
        # (voice.listen.early, 0.8.17) at a first short pause the stretch so far goes to early.pause(pcm, flags), and
        # early.end_ms(nbytes) may end the stretch sooner than END_MS when what was said there is finished
        self.early = early
        self.mic, self.vad, self.wake = mic, vad, wake
        self.on_speech, self.on_level, self.on_start, self.hold = on_speech, on_level, on_start, hold
        self.wake_threshold = wake_threshold
        self.barge = barge
        self.thread: threading.Thread | None = None
        self.error = ""
        self._stop = threading.Event()

    def start(self) -> None:
        self.thread = threading.Thread(target=self._run, name="voice-listen", daemon=True)
        self.thread.start()

    def running(self) -> bool:
        return self.thread is not None and self.thread.is_alive()

    def stop(self) -> None:
        """From another thread: asks the reader to stop, then waits briefly for it to close its own stream, so a new
        Listener doesn't open the device while this one still holds it."""
        self._stop.set()
        self.mic.close()
        t = self.thread
        if t is not None and t is not threading.current_thread() and t.is_alive():
            t.join(JOIN_S)

    def _run(self) -> None:
        frame_ms = FRAME * 1000 / RATE
        pre: collections.deque[bytes] = collections.deque(maxlen=max(1, int(self.PRE_MS / frame_ms)))
        buf: bytearray | None = None
        flags = bytearray()  # (voice id) speech or not, per frame of buf: speech seconds and the noise floor
        quiet = 0
        spoke = 0  # (early) bytes of buf up to its last speech frame
        paused = -1  # (early) the `spoke` the last early.pause() was handed
        wake_buf = bytearray()
        woke_at = 0.0
        barging = False
        frames = None
        try:
            frames = self.mic.frames()
            for frame in frames:
                if self._stop.is_set():
                    break
                if self.aec is not None:
                    try:
                        frame = self.aec.process(frame)
                    except Exception as e:
                        self.aec, self.aec_error = None, f"{type(e).__name__}"[:100]
                if self.on_level is not None:
                    self.on_level(frame)
                if self.barge is not None and self.barge.wants():  # Kurooto speaking: barge.py hears for it
                    if not barging:
                        pre.clear()
                        buf, quiet, flags = None, 0, bytearray()
                        wake_buf.clear()
                        self.vad.reset()
                        barging = True
                    if self.barge.feed(frame, self.vad.prob(frame)):
                        self.vad.reset()
                    continue
                if barging:
                    barging = False
                    self.vad.reset()
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
                    if self.gain is not None and p < self.STOP:
                        self.gain.quiet(frame)
                    if p >= self.START and (self.gain is None or self.gain.loud_enough(frame)):
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
                end_ms = self.END_MS
                if self.early is not None:
                    if not quiet:
                        spoke = len(buf)
                    elif quiet * frame_ms >= EARLY_MS and paused != spoke:
                        paused = spoke
                        n = spoke // (FRAME * 2)
                        pre_, pf = bytes(buf[:spoke]), bytes(flags[:n])
                        self.early.pause(self.gain.level(pre_, pf) if self.gain is not None else pre_, pf)
                    if quiet:
                        end_ms = self.early.end_ms(spoke) or end_ms
                if quiet * frame_ms >= end_ms or len(buf) >= self.MAX_S * RATE * 2:
                    seconds = len(buf) / (RATE * 2)
                    woke = time.monotonic() - woke_at <= seconds + 2
                    audio, cut = bytes(buf), bytes(flags)
                    if self.gain is not None:
                        audio = self.gain.level(audio, cut)
                    buf, quiet, flags = None, 0, bytearray()
                    spoke, paused = 0, -1
                    self.vad.reset()
                    self.on_speech(audio, woke, seconds, cut)
                    del audio
                    if woke:
                        woke_at = 0.0
        except Exception as e:
            self.error = f"{type(e).__name__}: {e}"[:300]
        finally:
            self.mic.close()
            close = getattr(frames, "close", None)  # here, on the reading thread: the stream is closed by its reader
            if close is not None:
                try:
                    close()
                except Exception:
                    pass

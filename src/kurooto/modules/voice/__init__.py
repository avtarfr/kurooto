"""Voice: talk and listen (0.8.8). Kurooto speaks through this computer's speakers with a voice made here (Kokoro,
or Piper), and, when you turn listening on, hears the room through the microphone, all on this computer.

What it hears goes through the gate (gate.py): voice activity, its name (names.py: as Whisper may spell it; your own
openWakeWord model too, if you give one), the words written out here
(faster-whisper) and, when the rules can't tell, the model on this computer. Noise and people talking to each other
are dropped on the spot: their words are never stored, logged or sent. Only speech the gate decides is said to
Kurooto opens the portal (portal.py), and only those turns go to the AI you picked, like a chat message; the answer
comes back as text on the dashboard and aloud. The portal closes at once when what follows isn't to Kurooto, or after
voice.listen.close_s seconds of nothing said to it.

Listening stops while you're on a call, while Kurooto is paused, at night if you turn voice.listen.night off, on
battery in saver mode, and when muted (/voice mute, `kurooto voice mute`, POST /api/voice/mute). Sound never
touches the disk.

The dashboard: GET /api/voice (state, engines, switches), POST /api/voice/say {text}, POST /api/voice/mute {on},
POST /api/voice/shape {text} (shape.py), and the live stream's {"t": "voice"} messages: voice_state, voice_level,
voice_text, voice_speak, voice_heard (docs/wiki/dev/voice.md).

Voice ID (0.8.10, voiceid.py; voice.speaker_id.on, off by default): only the owner's voice can make Kurooto act; any
other voice, or one it isn't sure of, can only chat (core/guest.py). Its own page is /voice-id; /voice id and /voice
enrol are typed only, never by voice.

Hooks for add-ons (0.8.12): listen_once(timeout_s) takes the next stretch of speech, any voice, through this listener,
written out here and handed to the add-on only (never the gate, the portal or the AI); guest_reply(text, name) is one
chat turn through the guest path (core/guest.py: no tools, none of the owner's data). Switches voice.addons.listen and
voice.addons.chat."""

from __future__ import annotations

import asyncio
import queue
import threading
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave
from kurooto.modules.base import Command, Incoming, Module
from kurooto.modules.voice import shape as shape_mod
from kurooto.modules.voice.gate import ADDRESSED, CHATTER, NOISE, Gate, Heard
from kurooto.modules.voice.parts import KOKORO_VOICES, STT_MODELS, Parts
from kurooto.modules.voice.portal import Portal
from kurooto.modules.voice.voiceid import NO_VOICE, VoiceID

if TYPE_CHECKING:
    from collections.abc import Callable

    from kurooto.app import App

    Output = Callable[[bytes, int, threading.Event], bool]

register_defaults(
    "voice",
    {
        "speak": {
            "on": True,  # Kurooto speaks through this computer's speakers (while Voice is on)
            "engine": "kokoro",  # the voice made on this computer: kokoro (natural, ~0.55 GB), piper (lighter) or off
            "voice": "",  # Kokoro's voice (af_heart, af_bella, am_michael, bf_emma, bm_george ...); empty: af_heart
            "rate": 1.0,  # speaking speed: 1.0 normal, 0.8 slower, 1.2 faster
            "what": "voice",  # what's read aloud: voice (answers to what you said aloud), all (every AI answer) or off
            "max_chars": 800,  # a longer answer is read this far, then "the rest is on screen"
            "numbers_as_words": True,  # say times, dates, money, versions and units as a person would (only aloud)
        },
        "listen": {
            "on": False,  # listen through the microphone, all on this computer; only turns said to Kurooto leave
            "wake_word": "",  # a wake word model of your own (an openWakeWord .onnx path); empty: its name wakes it
            "wake_threshold": 0.5,  # how sure the wake word model must be (0 to 1)
            "name_variants": [],  # more spellings of its name to accept (Whisper's mishearings of Kurooto are built in)
            "model_judge": True,  # when the rules can't tell, the model on this computer judges (off: rules only)
            "threshold": 0.7,  # the local model's confidence below which speech counts as not said to Kurooto
            "close_s": 8,  # seconds with nothing said to it before the conversation closes
            "after_speak_s": 6,  # a question or request this many seconds after it spoke counts as an answer to it
            "night": True,  # listen during the night hours too (off: it stops for availability.night)
            "calls": False,  # keep listening during a phone call (off: it stops while you're on one)
            "stt_model": "base",  # the transcriber's size: tiny (75 MB), base (145 MB) or small (484 MB, better)
            "language": "",  # the language you speak, e.g. en or hi; empty: worked out each time
            "device": "",  # the microphone: empty is the system's default; a name or number from sounddevice
            "levels": True,  # send the microphone's loudness to the dashboard for its waveform (numbers only)
            "conversation_mode": True,  # with Voice ID: while another voice is here, only its name opens a talk
            "conversation_s": 60,  # conversation mode lasts this many seconds after the last other voice
            "conversation_follow_s": 4,  # in conversation mode, a reply to what it said counts only this soon after
        },
        "speaker_id": {
            "on": False,  # Voice ID: only your voice can make Kurooto act; others can only chat (enrol first)
            "mode": "owner_only_acts",  # owner_only_acts (others may chat) or owner_only_at_all (others: one line)
            "model": "campplus-en",  # campplus-en (English, most accurate) or campplus-multi; a change: enrol again
            "strictness": "normal",  # relaxed, normal or strict (turns you away more often; strangers almost never)
            "threshold": 0.0,  # 0: worked out from your own samples; a number overrides it (held to 0.30 to 0.95)
            "margin": 0.05,  # the "not sure" band just below the threshold; not sure counts as not you
            "min_speech_s": 1.0,  # shorter than this is too short to tell (it counts as not sure)
            "carry": True,  # a short reply right after a turn it knew was you counts as you (not if clearly not)
            "carry_s": 15,  # how long after your last recognised turn a short reply may carry it
            "gate": True,  # check the voice before writing words out: others not calling it are never transcribed
            "tell_guests": True,  # once per conversation, tell others they can chat but only you can make it act
            "guest_brain": "main",  # who answers others: main (your AI, none of your data) or local (this computer)
            "guest_per_hour": 20,  # at most this many answers to others an hour
            "adapt": False,  # improve over time: turns it was very sure were you refine your voice print (undo)
            "adapt_max": 40,  # at most this many learned turns are kept (oldest replaced)
            "adapt_per_day": 10,  # at most this many learned turns a day
            "spoken_enrol": True,  # during enrolment Kurooto says each step aloud (off: the page shows it only)
        },
        "addons": {
            "listen": True,  # an add-on may take one stretch of speech at a time (written out here, never sent)
            "chat": True,  # an add-on may have Kurooto chat with someone through the guest path (no tools, no data)
        },
    },
)

LOOPBACK = ("127.0.0.1", "localhost", "::1")
MIC_CHECK_S = 30
JOB_WAIT_S = 600
RETRY_S = 60  # a microphone that failed is tried again after this long
ONCE_MAX_S = 60.0  # listen_once waits at most this long for speech to start
ONCE_WORK_S = 30.0  # and this long more for a stretch it took to be written out


class Speaker:
    """Speaks text sentence by sentence: the next sentence is made while this one plays, so speech starts as soon
    as the first sentence is ready."""

    def __init__(self, v: Voice):
        self.v = v
        self.lock = threading.Lock()
        self.busy = False
        self.until = 0.0  # it finished speaking at (monotonic) + a short tail: the microphone ignores until then
        self.player = None
        self._cancel = threading.Event()  # stop()/mute: ends the sentence loop and is the stop an output is handed
        self._outputs: list[list] = []  # [fn, failed already], newest first (add_output)
        self._out_lock = threading.Lock()  # registration only; never held while sound plays

    def add_output(self, fn: Output) -> Callable[[], None]:
        entry = [fn, False]
        with self._out_lock:
            self._outputs.insert(0, entry)

        def remove() -> None:
            with self._out_lock:
                self._outputs[:] = [e for e in self._outputs if e is not entry]  # by identity: fn may be added twice

        return remove

    def say(self, text: str, wait: bool = True) -> tuple[bool, str]:
        tts, why = self.v.tts()
        if tts is None:
            return False, why
        if not wait:
            threading.Thread(target=self._speak, args=(tts, text), name="voice-say", daemon=True).start()
            return True, "Speaking."
        self._speak(tts, text)
        return True, "Spoken."

    def _speak(self, tts, text: str) -> None:
        limit = int(self.v.setting("speak.max_chars") or 800)
        parts = shape_mod.sentences(text, numbers=bool(self.v.setting("speak.numbers_as_words")))
        out, n = [], 0
        for p in parts:
            if n + len(p) > limit and out:
                out.append("The rest is on screen.")
                break
            out.append(p)
            n += len(p)
        if not out:
            return
        with self.lock:
            self.busy = True
            self._cancel.clear()
            pool = ThreadPoolExecutor(1, thread_name_prefix="voice-tts")
            try:
                fut = pool.submit(tts.synth, out[0])
                for i in range(len(out)):
                    pcm, sr = fut.result()
                    if i + 1 < len(out):
                        fut = pool.submit(tts.synth, out[i + 1])
                    if self._cancel.is_set():
                        break
                    self.v.publish("voice_speak", samples=shape_mod.from_pcm(pcm, sr), rate=shape_mod.RATE)
                    self._play(pcm, sr)
            except Exception as e:
                self.v.app.events.emit("voice_failed", part="speaking", error=f"{type(e).__name__}: {e}"[:300])
            finally:
                pool.shutdown(wait=False, cancel_futures=True)
                self.busy = False
                self.until = time.monotonic() + 0.4

    def _play(self, pcm: bytes, sr: int) -> None:
        """One sentence: the newest output that takes it, else this computer's speakers. Runs inside _speak (busy),
        so holding() covers an output's whole play exactly as the Player's."""
        with self._out_lock:
            outs = list(self._outputs)
        for entry in outs:
            if self._cancel.is_set():
                return
            try:
                if entry[0](pcm, sr, self._cancel):
                    return
            except Exception as e:  # counts as "can't now"; told once per output, not per sentence
                if not entry[1]:
                    entry[1] = True
                    self.v.app.events.emit("voice_failed", part="output", error=f"{type(e).__name__}: {e}"[:300])
        if self._cancel.is_set():  # stopped while an output played: not finished here instead
            return
        if self.player is None:
            from kurooto.modules.voice.audio import Player

            self.player = Player()
        self.player.play(pcm, sr)

    def stop(self) -> None:
        self._cancel.set()
        if self.player is not None:
            self.player.stop()

    def holding(self) -> bool:
        return self.busy or time.monotonic() < self.until


class Voice(Module):
    id = "voice"
    title = "Voice: talk and listen"
    description = (
        "Kurooto speaks with a voice made on this computer and, if you turn listening on, hears you: a local model "
        "tells noise and people talking from you talking to it."
    )
    privacy = (
        "Speaking and listening run on this computer; sound is never saved. Only what you say to Kurooto (its name, "
        "the conversation it's in, or the local model's judgement) goes to the AI you picked; the rest is dropped."
    )
    heavy = True  # on battery in saver mode, listening waits for the charger
    setup_notes = (
        (
            "Fetch the voice and listening parts (Python packages into Kurooto's own folder, and the models)",
            "dashboard → Features → Voice: talk and listen → Set up",
            "turn Voice off; delete the voice folder in Kurooto's app folder (`kurooto paths`, app)",
        ),
        (
            "A microphone, for listening (voice.listen.on); your system's sound settings pick the default",
            "your system's sound settings",
            "voice.listen.on off, or /voice mute",
        ),
    )

    def __init__(self, app: App):
        super().__init__(app)
        self.parts = Parts(app.paths.app / "voice", app.paths.app)
        self.file = app.paths.state / "voice.json"
        self.speaker = Speaker(self)
        self.portal = Portal(
            send=self.ask_brain,
            speak=self._portal_speak,
            publish=self.publish,
            close_s=float(self.setting("listen.close_s") or 8),
            on_change=self._portal_changed,
            listening=lambda: self.listener is not None and self.listener.running(),
        )
        self.listener = None
        self.heard = {NOISE: 0, CHATTER: 0, ADDRESSED: 0}  # counts since Kurooto started; never what was said
        self.last_state: dict = {"state": "off", "portal": False, "listening": False, "why": ""}
        self.blocked_why = "off"
        self._tts = None
        self._tts_key: tuple = ()
        self._stt = None
        self._stt_key: tuple = ()
        self._jobs: dict[str, threading.Event] = {}
        self._watching = False
        self._work: queue.Queue = queue.Queue(maxsize=3)
        self._worker: threading.Thread | None = None
        self._mic: tuple[float, tuple] = (0.0, (None, ""))
        self._level_buf = bytearray()
        self.mic_error = ""
        self._retry_at = 0.0
        self.voiceid = VoiceID(self)  # (voice id) the owner's voice: voiceid.py
        self._once: dict | None = None  # listen_once's hold: the next stretch goes to it, not to hear()
        self._once_lock = threading.Lock()  # one holder at a time

    # ------------------------------------------------------------------------------------------- the parts
    def wants(self) -> list[str]:
        """The parts the switches as they are need: "pkg:<key>" and "model:<key>" (parts.py)."""
        keys = []
        engine = self.setting("speak.engine") or "kokoro"
        if self.setting("speak.on") and engine in ("kokoro", "piper"):
            keys += ["pkg:audio", f"pkg:{engine}", f"model:{engine}"]
        if self.setting("listen.on"):
            size = self.setting("listen.stt_model") or "base"
            keys += ["pkg:audio", "pkg:listen", "model:vad", f"model:whisper-{size if size in STT_MODELS else 'base'}"]
            if str(self.setting("listen.wake_word") or "").strip():  # your own model: openWakeWord to run it
                keys += ["pkg:wake", "model:wake-common"]
        if self.setting("speaker_id.on"):  # (voice id) listening's parts (enrolment checks the phrase) and the model
            size = self.setting("listen.stt_model") or "base"
            keys += ["pkg:audio", "pkg:listen", "model:vad", f"model:whisper-{size if size in STT_MODELS else 'base'}"]
            keys += ["pkg:voiceid", f"model:{self.voiceid.model_part()}"]
        return list(dict.fromkeys(keys))

    def ready(self) -> tuple[bool, str]:
        missing = self.parts.missing(self.wants())
        if missing:
            return False, f"needs setting up (downloads about {self.parts.size_gb(missing):g} GB)"
        return True, ""

    def setup(self, progress=print) -> tuple[bool, str]:
        if self.setting("listen.on"):
            from kurooto.modules.voice.audio import microphone

            has, name = microphone()
            if has is False:
                progress(f"✗ {name}: listening needs a microphone; speaking is set up anyway")
        from kurooto.core.prereqs import Prereqs

        free = lambda: Prereqs.free_gb(self.parts.root)  # noqa: E731
        return self.parts.install(self.wants(), progress, free_gb=free)

    def health(self) -> tuple[bool, str]:
        ok, why = self.ready()
        if not ok:
            return ok, why
        if self.setting("listen.on"):
            has, name = self.microphone()
            if has is False:
                return False, name
            if self.mic_error:
                return False, f"the microphone stopped: {self.mic_error}"
        vid = self.voiceid.health()  # (voice id) on but no voice print, its key unreadable, its model failed
        if vid is not None:
            return vid
        return True, self.line()

    def health_check(self):
        from kurooto.core.health import Check

        def probe(net: bool):
            ok, why = self.health()
            return ok, why

        return Check("voice", "Voice", module="voice", probe=probe, help="Features → Voice: talk and listen → Set up")

    def line(self) -> str:
        """One line for /health and /voice: what it does now."""
        engine = self.setting("speak.engine") or "kokoro"
        speak = f"speaks with {engine.capitalize()}" if self.setting("speak.on") and engine != "off" else "silent"
        vid = self.voiceid.line()  # (voice id) its state, on the being's ear too
        tail = f"; {vid}" if vid else ""
        if not self.setting("listen.on"):
            return f"{speak}; not listening (voice.listen.on is off){tail}"
        if self.blocked_why:
            return f"{speak}; not listening: {self.blocked_why}{tail}"
        own = " or your wake word" if str(self.setting("listen.wake_word") or "").strip() else ""
        return f"{speak}; listening here (its name{own} wakes it){tail}"

    def microphone(self) -> tuple:
        at, res = self._mic
        if at == 0 or time.monotonic() - at > MIC_CHECK_S:
            self.parts.importable()
            from kurooto.modules.voice.audio import microphone

            res = microphone()
            self._mic = (time.monotonic(), res)
        return res

    # ------------------------------------------------------------------------------------------- engines
    def tts(self):
        """The speech engine, loaded once: (engine, "") or (None, why not)."""
        if not self.setting("speak.on"):
            return None, "speaking is off (voice.speak.on)"
        engine = self.setting("speak.engine") or "kokoro"
        if engine not in ("kokoro", "piper"):
            return None, "no speech engine (voice.speak.engine is off)"
        if self.parts.missing([f"pkg:{engine}", f"model:{engine}"]):
            return None, f"{engine.capitalize()} isn't set up yet (Features → Voice → Set up)"
        key = (engine, self.setting("speak.voice") or "", float(self.setting("speak.rate") or 1.0))
        if self._tts is None or self._tts_key != key:
            self.parts.importable()
            from kurooto.modules.voice import audio

            try:
                if engine == "kokoro":
                    self._tts = audio.Kokoro(
                        self.parts.path("kokoro-v1.0.onnx"), self.parts.path("voices-v1.0.bin"), key[1], key[2]
                    )
                else:
                    self._tts = audio.Piper(self.parts.path("en_US-lessac-medium.onnx"), key[2])
            except Exception as e:
                self.app.events.emit("voice_failed", part="speech engine", error=f"{type(e).__name__}: {e}"[:300])
                return None, f"{engine.capitalize()} didn't load: {type(e).__name__}"
            self._tts_key = key
        return self._tts, ""

    def stt(self):
        size = self.setting("listen.stt_model") or "base"
        size = size if size in STT_MODELS else "base"
        key = (size, self.setting("listen.language") or "", self.app.name)
        if self._stt is None or self._stt_key != key:
            self.parts.importable()
            from kurooto.modules.voice.audio import Whisper

            self._stt = Whisper(self.parts.path(f"whisper-{size}"), key[1], hint=self.app.name)
            self._stt_key = key
        return self._stt

    # -------------------------------------------------------------------------------------- the dashboard
    def publish(self, kind: str, **fields) -> None:
        """To open dashboard pages only, as {"t": "voice", "kind": ...}: never into the event log."""
        if kind == "voice_state":
            self.last_state = {k: fields.get(k) for k in ("state", "portal", "listening", "why")}
        live = getattr(self.app, "live", None)
        if live is not None:
            try:
                live.push({"t": "voice", "kind": kind, **fields})
            except Exception:
                pass

    def _portal_changed(self, is_open: bool, why: str) -> None:
        self.app.events.emit("voice_portal", open=is_open, why=why)  # when and why only, never words
        if not is_open:
            self.voiceid.portal_closed()  # (voice id) a guest's turns of this conversation are dropped

    def _level(self, frame: bytes) -> None:
        if not self.setting("listen.levels"):
            return
        self._level_buf += frame
        if len(self._level_buf) < 3200:  # 100 ms at 16 kHz
            return
        data, self._level_buf = bytes(self._level_buf), bytearray()
        live = getattr(self.app, "live", None)
        if live is not None and live.watched():
            self.publish("voice_level", levels=shape_mod.levels(data, 5), rate=shape_mod.RATE)

    def _heard_wave(self, audio: bytes | None) -> None:
        """A stretch that wasn't a turn (chatter, noise, not to it): its loudness outline only, never words, so the
        page's waveform moves for speech that wasn't for Kurooto too. Same switch as the live levels."""
        live = getattr(self.app, "live", None)
        if not audio or not self.setting("listen.levels") or live is None or not live.watched():
            return
        self.publish("voice_heard", samples=shape_mod.envelope(audio), addressed=False)

    def status(self) -> dict:
        s = self.setting
        missing = self.parts.missing(self.wants())
        player = ""
        if self.app.is_on(self.id):
            from kurooto.modules.voice.audio import Player

            self.parts.importable()
            player = Player.detect()
        return {
            "on": self.app.is_on(self.id),
            **self.last_state,
            "muted": self.muted(),
            "blocked": self.blocked_why,
            "line": self.line(),
            "speak": {
                "on": bool(s("speak.on")),
                "engine": s("speak.engine"),
                "voice": s("speak.voice") or ("af_heart" if s("speak.engine") == "kokoro" else ""),
                "rate": s("speak.rate"),
                "what": s("speak.what"),
                "player": player,
                "speaking": self.speaker.busy,
            },
            "listen": {
                "on": bool(s("listen.on")),
                "wake_word": s("listen.wake_word"),
                "stt_model": s("listen.stt_model"),
                "close_s": s("listen.close_s"),
                "night": bool(s("listen.night")),
                "calls": bool(s("listen.calls")),
                "microphone": self.microphone()[1] if s("listen.on") and self.app.is_on(self.id) else "",
            },
            "engines": {
                "kokoro": not self.parts.missing(["pkg:kokoro", "model:kokoro"]),
                "piper": not self.parts.missing(["pkg:piper", "model:piper"]),
                "whisper": self.parts.has_package("listen"),
                "vad": self.parts.has_model("vad"),
                "wake": self.parts.has_package("wake"),
            },
            "missing": missing,
            "missing_gb": self.parts.size_gb(missing),
            "heard": dict(self.heard),
            "choices": {"voices": list(KOKORO_VOICES), "stt_models": list(STT_MODELS)},
            "speaker_id": {  # (voice id) counts and words only; GET /api/voice/id has the rest
                "on": self.voiceid.on(),
                "enrolled": self.voiceid.enrolled(),
                "who": dict(self.voiceid.who),
                "last": self.voiceid.last_word,
            },
        }

    def shape(self, text: str) -> dict:
        """POST /api/voice/shape: the text's waveform outline (shape.py), from the speech engine when it's here."""
        text = (text or "")[: shape_mod.MAX_CHARS]
        words = bool(self.setting("speak.numbers_as_words"))  # the shape of what's said, numbers and all
        if self.app.is_on(self.id):
            tts, _why = self.tts()
            if tts is not None:
                try:
                    pcm = b""
                    sr = 24000
                    for part in shape_mod.sentences(text, numbers=words) or [text]:
                        got, sr = tts.synth(part)
                        pcm += got
                    if pcm:
                        return shape_mod.payload(shape_mod.from_pcm(pcm, sr), "tts")
                except Exception:
                    pass
        rate = float(self.setting("speak.rate") or 1.0)
        return shape_mod.payload(shape_mod.estimate(shape_mod.spoken(text, words), rate), "estimate")

    # ----------------------------------------------------------------------------------------- the switches
    def muted(self) -> bool:
        return bool((jload(self.file, {}) or {}).get("muted"))

    def mute(self, on: bool | None = None) -> str:
        """Mute (stop listening, stop speaking) or unmute; None flips it."""
        on = (not self.muted()) if on is None else bool(on)
        data = jload(self.file, {}) or {}
        data["muted"] = on
        jsave(self.file, data)
        if on:
            self.speaker.stop()
            self.portal.close("muted")
            self._stop_listening("muted")
        self.app.events.emit("voice_mute", on=on)
        return "Muted: not listening or speaking until /voice unmute." if on else "Unmuted."

    def blocked(self) -> str:
        """Why it may not listen now ("" when it may)."""
        if self.voiceid.capturing:  # (voice id) enrolment or a test has the microphone
            return self.voiceid.capturing
        if not self.setting("listen.on"):
            return "listening is off"
        if self.muted():
            return "muted"
        if self.app.power.current == "paused":
            return "Kurooto is paused"
        if not self.app.power.may_run(self):
            return "on battery (saver mode)"
        if not self.setting("listen.calls") and self._on_call():
            return "you're on a call"
        if not self.setting("listen.night") and self._night():
            return "night hours"
        if self.parts.missing(  # (voice id) its own parts missing: every voice is unsure (fail closed), still heard
            [
                k
                for k in self.wants()
                if k not in {"pkg:wake", "pkg:voiceid"} and not k.startswith(("model:wake", "model:voiceid"))
            ]
        ):
            return "not set up yet"
        return ""

    def _on_call(self) -> bool:
        from kurooto.web.tools_api import live_call

        try:
            return live_call(self.app)
        except Exception:
            return False

    def _night(self) -> bool:
        from kurooto.core.clock import now

        try:
            return self.app.availability.night(now()) is not None
        except Exception:
            return False

    # ------------------------------------------------------------------------------------------- hearing
    def gate(self) -> Gate:
        return Gate(
            [self.app.name, "Kurooto"],  # the name you gave it, and its own (the mishearings of both: names.py)
            judge=self.judge,
            threshold=float(self.setting("listen.threshold") or 0.7),
            close_s=float(self.setting("listen.close_s") or 8),
            after_speak_s=float(self.setting("listen.after_speak_s") or 6),
            use_model=bool(self.setting("listen.model_judge")),
            variants=list(self.setting("listen.name_variants") or []),
        )

    def judge(self, prompt: str) -> str | None:
        """The model on this computer, and only there: Ollama at a loopback address, else the offline helper."""
        from kurooto import providers

        brain = providers.local(self.app)
        host = urllib.parse.urlparse(str(getattr(brain, "base_url", "") or "")).hostname if brain else None
        if brain is not None and host in LOOPBACK:
            r = brain.complete(prompt, effort="low", timeout=20)
            return r.text if r.ok else None
        helper = getattr(self.app, "helper", None)
        if helper is not None and helper.ready():
            return helper._generate(prompt, 40, 8)  # Ollama on this computer (core/helper.py)
        return None

    def _write_out(self, pcm: bytes) -> str:
        try:
            return self.stt().text(pcm)
        except Exception as e:
            self.app.events.emit("voice_failed", part="writing out", error=f"{type(e).__name__}"[:100])
            return ""

    def hear(self, h: Heard, audio: bytes | None = None, flags: bytes = b"") -> str | None:
        """One stretch of sound, from the listener (or a test): written out here when it's speech, judged, and either
        dropped or taken through the portal. Returns Kurooto's reply when there was one.

        With Voice ID on, the voice is checked too (voiceid.py). With its gate (voice.speaker_id.gate) that comes
        first: someone else's voice that isn't calling Kurooto, with no conversation open, is dropped as chatter and
        never written out (only its first and last two seconds are, to hear the name). With conversation mode
        (voice.listen.conversation_mode) every stretch of speech is checked too, so another voice is noticed even with
        the gate off; with both off, only turns the gate calls addressed are checked."""
        if self.blocked() or not self.app.is_on(self.id):
            return None
        self.portal.close_s = float(self.setting("listen.close_s") or 8)
        self.portal.state("hearing")
        vid = self.voiceid
        on = vid.on()
        who = None
        if on:
            self.portal.mode = vid.mode()
            self.portal.tell_guests = bool(vid.s("tell_guests", True))
            if not h.speech_s:
                h.speech_s = sum(1 for f in flags if f) * 512 / 16000 if flags else h.seconds
        gate_first = bool(vid.s("gate", True))
        if on and (gate_first or self.setting("listen.conversation_mode")) and h.speech and audio is not None:
            who = vid.check(audio, h.speech_s, h.voices)  # (voice id) who, before the words
            if gate_first and who.decision != "owner" and not h.wake and not self.portal.open:
                g = self.gate()
                edges = _edges(audio)
                heard = self._write_out(edges)
                if edges is audio:  # short: that was all of it
                    h.text = heard
                elif not g.called(heard):
                    heard = ""  # dropped: someone else, not to it, never written out in full
                if not h.text and not heard:
                    self._heard_wave(audio)
                    del audio
                    self.heard[CHATTER] = self.heard.get(CHATTER, 0) + 1
                    from kurooto.modules.voice.gate import Decision

                    self.portal.take(h, Decision(CHATTER, 0.9, "someone else, not to it"))
                    self.portal.state("listening", CHATTER)
                    return None
                heard = ""
        if h.speech and not h.text and audio is not None:
            h.text = self._write_out(audio)
        g = self.gate()
        ctx = self.portal.context()
        if on and self.setting("listen.conversation_mode"):  # (voice id) people talking: only its name opens it
            guests_here = who is not None and who.decision == "guest" and vid.others_lately() >= 3
            ctx.conversation = vid.conversation() or guests_here
            ctx.follow_s = float(self.setting("listen.conversation_follow_s") or 4)
        d = g.decide(h, ctx)
        self.heard[d.klass] = self.heard.get(d.klass, 0) + 1
        if not d.addressed:
            self._heard_wave(audio)
            del audio
            h.text = ""  # dropped here: never stored, logged or sent
            was_open = self.portal.open
            self.portal.take(h, d)
            if not was_open:
                self.portal.state("listening", d.klass)
            return None
        said = g.matcher.uncall(h.text) if h.wake or d.why == "its name" else h.text  # the call itself isn't sent
        if on and who is None and said and audio is not None:  # (voice id) the gate first is off: addressed only
            who = vid.check(audio, h.speech_s, h.voices)
        del audio
        if on and who is None and said:  # nothing to check it with: unsure (fail closed)
            from kurooto.modules.voice.speakerid import UNSURE, Verdict

            who = Verdict(UNSURE, "no sound to check")
        if who is not None:
            self.publish("voice_state", state="addressed", portal=True, listening=True, why=d.why, who=who.word)
        return self.portal.take(h, d, text=said, who=who)

    def ask_brain(self, text: str, who=None) -> str:
        """An addressed turn to your AI, like a chat message (spoken style); its answer as text. who: Voice ID's
        verdict, which travels with the message (Incoming.speaker); not the owner's goes to core/guest.py."""
        replies: list[str] = []
        msg = Incoming(
            text=text,
            via="voice",
            voice=True,
            respond=lambda t, buttons=None: replies.append(str(t)),
            speaker=who.decision if who is not None else "",
            speaker_by="voice" if who is not None else "",
        )
        self.app.handle(msg)
        if who is not None and who.decision != "owner":  # (voice id) a guest's turn: kept in memory for this talk only
            gid = getattr(msg, "job", None)
            try:
                answer = self._wait_job(msg) if gid else "\n".join(replies)
            finally:
                if gid:  # its words leave the request list once answered (or given up on)
                    try:
                        self.app.jobs.forget_guest(gid)
                    except Exception as e:
                        self.app.events.emit("voice_failed", part="guest words", error=f"{type(e).__name__}"[:100])
            if answer:
                self.voiceid.heard_guest(text, answer)
            return answer
        jid = getattr(msg, "job", None)
        if not jid:
            return "\n".join(replies)
        answer = self._wait_job(msg)
        chat = self.app.modules.get("chat")
        if chat is not None and answer and chat.owns(jid):  # the conversation goes on, as a typed one does
            try:
                chat.record_turn(self.app.jobs.get(jid).prompt, answer)
            except Exception:
                pass
        return answer

    def _wait_job(self, msg: Incoming) -> str:
        jid = msg.job
        done = self._jobs.setdefault(jid, threading.Event())
        try:
            end = time.monotonic() + JOB_WAIT_S
            while time.monotonic() < end:
                j = self.app.jobs.get(jid)
                if j is None or j.status in ("ok", "failed") or self.portal_cut():
                    break
                done.wait(0.5)
            j = self.app.jobs.get(jid)
        finally:
            self._jobs.pop(jid, None)
        if j is None or j.status != "ok":
            return "I couldn't get an answer just now." if j is not None and j.status == "failed" else ""
        return (j.result or "").strip()

    def _portal_speak(self, text: str) -> None:
        """The portal's reply, aloud: not when muted or turned off meanwhile (the text is on the dashboard)."""
        if not self.portal_cut():
            self.speaker.say(text, wait=True)

    def portal_cut(self) -> bool:
        return not self.app.is_on(self.id) or self.muted()

    def _job_done(self, job, result, info) -> None:
        ev = self._jobs.get(job.id)
        if ev is not None:
            ev.set()
            return
        away = getattr(self.app, "away_from_desk", None)
        if away is not None and self.app.settings.get("face.away.hold_desktop") and away():
            return  # stepped away from the desk (Face presence): the answer stays on screen, not read to an empty room
        if (
            self.app.is_on(self.id)
            and self.setting("speak.what") == "all"
            and not self.muted()
            and getattr(job, "lane", "you") == "you"
            and not job.quiet
            and not getattr(job, "background", False)
            and getattr(result, "ok", False)
            and getattr(result, "text", "")
        ):
            self.speaker.say(result.text, wait=False)

    def add_output(self, fn: Output) -> Callable[[], None]:
        """Play Kurooto's voice elsewhere (an add-on: another device). fn(pcm, sr, stop) gets each sentence's 16-bit
        mono PCM, newest output first, instead of this computer's speakers; it blocks until the sound has played (or
        `stop` is set: /voice stop, mute, Voice off) and returns True, or False when it can't now (the next output,
        finally the speakers, play it). Raising counts as False (voice_failed part="output", once). It runs on the
        speaking thread while holding() is true, so the microphone doesn't hear Kurooto. Returns remove()."""
        return self.speaker.add_output(fn)

    def say(self, text: str, wait: bool = False) -> tuple[bool, str]:
        """Speak this now (POST /api/voice/say, /voice say)."""
        if not self.app.is_on(self.id):
            return False, "Voice is off."
        if self.muted():
            return False, "Voice is muted (/voice unmute)."
        text = (text or "").strip()[:4000]
        if not text:
            return False, "Nothing to say."
        self.publish("voice_text", who="kurooto", text=text)
        return self.speaker.say(text, wait=wait)

    def greet(self, text: str, listen_s: float, talk: bool = True) -> tuple[bool, str]:
        """Face presence's greeting (0.8.10): shown, spoken (waiting for it to finish), then, when `talk` and listening
        is on and not blocked, the conversation opens for listen_s seconds (Portal.invite). (False, why) when it can't
        speak; (True, "talk") when the conversation opened; (True, why not) when only spoken. Never sent anywhere."""
        if not self.app.is_on(self.id):
            return False, "Voice is off"
        if self.muted():
            return False, "Voice is muted"
        tts, why = self.tts()
        if tts is None:
            return False, why or "Voice can't speak"
        self.publish("voice_text", who="kurooto", text=text)
        ok, why = self.speaker.say(text, wait=True)
        if not ok:
            return False, why
        if not talk:
            return True, "spoken"
        blocked = self.blocked()
        if blocked:
            return True, f"spoken; not listening: {blocked}"
        self.portal.invite(text, listen_s)
        return True, "talk"

    # ---------------------------------------------------------------------------------------- running
    def start(self) -> None:
        if not self._watching:
            self.app.jobs.watchers.append(self._job_done)
            self._watching = True

    def stop(self) -> None:
        super().stop()
        self.portal.close("turned off")
        self.speaker.stop()
        self._stop_listening("turned off")
        self._tts = self._stt = None
        if self.voiceid.session is not None:  # (voice id) an enrolment ends with Voice
            self.voiceid.session.command("stop")
        self.voiceid.drop_model()

    async def background(self, stop: asyncio.Event) -> None:
        try:
            while not stop.is_set():
                why = self.blocked()
                if why != self.blocked_why:
                    self.blocked_why = why
                    self.app.events.emit("voice_listening", on=not why, why=why)
                if why:
                    self.portal.close(why)
                    self._stop_listening(why)
                elif self.listener is None or not self.listener.running():
                    self._start_listening()
                if not self.voiceid.on():  # (voice id) switched off: its model goes at once
                    self.voiceid.drop_model()
                s = self.voiceid.session
                if s is not None and self.muted():  # mute ends an enrolment
                    s.command("stop")
                self.portal.tick()
                try:
                    await asyncio.wait_for(stop.wait(), timeout=1)
                except TimeoutError:
                    pass
        finally:
            self._stop_listening("stopped")

    def _start_listening(self) -> None:
        if self.listener is not None and self.listener.error:  # the microphone failed: told once, tried again later
            self.mic_error, self.listener = self.listener.error, None
            self.app.events.emit("voice_failed", part="microphone", error=self.mic_error)
            self._retry_at = time.monotonic() + RETRY_S
        if time.monotonic() < self._retry_at:
            return
        self.parts.importable()
        from kurooto.modules.voice import audio

        try:
            vad = audio.Silero(self.parts.path("silero_vad.onnx")) if self.parts.has_model("vad") else audio.Energy()
            wake = None
            ww = str(self.setting("listen.wake_word") or "")
            model = Path(ww).expanduser() if ww.strip() else None  # your own openWakeWord model, when you gave one
            if model is not None and model.is_file() and self.parts.has_package("wake"):
                wake = audio.Wake(
                    model, self.parts.path("melspectrogram.onnx"), self.parts.path("embedding_model.onnx")
                )
            self.stt()  # loaded before the microphone opens: the first words aren't kept waiting
        except Exception as e:
            self.app.events.emit("voice_failed", part="listening", error=f"{type(e).__name__}: {e}"[:300])
            self.mic_error = f"couldn't start listening: {type(e).__name__}"
            self._retry_at = time.monotonic() + RETRY_S
            return
        self.mic_error = ""
        if self._worker is None or not self._worker.is_alive():
            self._worker = threading.Thread(target=self._work_loop, name="voice-hear", daemon=True)
            self._worker.start()
        self.listener = audio.Listener(
            audio.Mic(str(self.setting("listen.device") or "")),
            vad,
            wake,
            on_speech=self._heard_audio,
            on_level=self._level,
            on_start=lambda: self.portal.state("hearing"),
            hold=lambda: self.speaker.holding() or self.portal.busy,
            wake_threshold=float(self.setting("listen.wake_threshold") or 0.5),
        )
        self.listener.start()
        self.portal.state("addressed" if self.portal.open else "listening")

    def _stop_listening(self, why: str) -> None:
        if self.listener is not None:
            self.listener.stop()
            self.listener = None
            self._level_buf = bytearray()
            self.publish("voice_state", state="off", portal=self.portal.open, listening=False, why=why)
        while not self._work.empty():  # sound not yet written out is dropped
            try:
                self._work.get_nowait()
            except queue.Empty:
                break

    def _heard_audio(self, pcm: bytes, woke: bool, seconds: float, flags: bytes = b"") -> None:
        """From the listener's thread: queued for writing out (the oldest dropped when it can't keep up)."""
        try:
            self._work.put_nowait((pcm, woke, seconds, flags))
        except queue.Full:
            try:
                self._work.get_nowait()
                self._work.put_nowait((pcm, woke, seconds, flags))
            except (queue.Empty, queue.Full):
                pass

    def _work_loop(self) -> None:
        while True:
            self._work_one(*self._work.get())

    def _work_one(self, pcm: bytes, woke: bool, seconds: float, flags: bytes = b"") -> None:
        """One stretch from the listener: an add-on's listen_once takes it while it holds, else hear()."""
        try:
            slot = self._once
            if slot is not None and not slot["done"].is_set():
                self._take_once(slot, pcm, seconds, flags)
            else:
                self.hear(Heard(speech=True, wake=woke, seconds=seconds), pcm, flags)
        except Exception as e:
            self.app.events.emit("voice_failed", part="hearing", error=f"{type(e).__name__}"[:100])
        finally:
            del pcm

    # -------------------------------------------------------------------------------------- hooks for add-ons
    def listen_once(self, timeout_s: float = 8.0) -> tuple[str, list[float] | None, float] | None:
        """The next stretch of speech, any voice and without its name, for an add-on: (text, the voice's numbers or
        None, seconds of speech), or None (nothing said within timeout_s, listening blocked or muted, the portal
        open, another holder, voice.addons.listen off). Written out here; never sent to the gate, the portal or the
        AI, never kept. Blocks the caller (call it from the add-on's own thread); the stretch is written out on
        Voice's own hearing thread meanwhile. The voice's numbers come from Voice ID's model when its parts are set
        up (Voice ID itself may be off)."""
        if not self.app.is_on(self.id) or not self.setting("addons.listen") or self.blocked():
            return None
        if self.listener is None or not self.listener.running() or self.portal.open or self.portal.busy:
            return None
        if not self._once_lock.acquire(blocking=False):
            return None
        slot: dict = {"done": threading.Event(), "taken": False, "got": None, "since": time.monotonic()}
        try:
            self._once = slot
            end = time.monotonic() + max(0.5, min(float(timeout_s or 8.0), ONCE_MAX_S))
            while not slot["done"].wait(0.2):
                if self.blocked() or self.portal_cut():
                    break
                if not slot["taken"] and time.monotonic() > end:
                    break
                if slot["taken"] and time.monotonic() > end + ONCE_WORK_S:
                    break
        finally:
            slot["done"].set()  # a stretch arriving after this goes to hear() as usual
            self._once = None
            self._once_lock.release()
        return slot["got"]

    def _take_once(self, slot: dict, pcm: bytes, seconds: float, flags: bytes) -> None:
        """listen_once's stretch, on the hearing thread: written out and, when Voice ID's parts are here, embedded.
        A stretch with no words (noise) is skipped: it keeps waiting."""
        slot["taken"] = True
        try:
            self._heard_wave(pcm)  # the waveform moves as for any speech
            text = self._write_out(pcm).strip()
            if not text:
                return
            speech_s = sum(1 for f in flags if f) * 512 / 16000 if flags else float(seconds or 0)
            emb = None
            if not self.voiceid.missing_parts():
                try:
                    emb = list(self.voiceid.embed(pcm))
                except Exception:
                    emb = None
            if not slot["done"].is_set():
                slot["got"] = (text, emb, round(speech_s, 2))
                slot["done"].set()
        finally:
            slot["taken"] = slot["got"] is not None
            del pcm

    def guest_reply(self, text: str, name: str | None = None, history: list | None = None) -> str | None:
        """One chat turn with someone who isn't the owner, for an add-on: core/guest.py's sealed path (no tools, no
        MCP, none of the owner's notes, memory or history; refusals for commands, actions and his things; the hourly
        cap; voice.speaker_id.guest_brain picks who answers). `name`: theirs, as context; `history`: the add-on's own
        last (said, answer) pairs, at most 4 used (the owner's conversation's turns are never mixed in). Blocks until
        the answer (call it from the add-on's own thread). None when Voice or voice.addons.chat is off."""
        if not self.app.is_on(self.id) or not self.setting("addons.chat"):
            return None
        text = (text or "").strip()[:1500]
        if not text:
            return None
        from kurooto.core import guest

        replies: list[str] = []
        msg = Incoming(
            text=text,
            via="voice",
            voice=True,
            respond=lambda t, buttons=None: replies.append(str(t)),
            speaker="guest",
            speaker_by="addon",
        )
        guest.handle(self.app, msg, name=name or "", turns=[tuple(x)[:2] for x in (history or [])][-4:])
        gid = getattr(msg, "job", None)
        try:
            answer = self._wait_job(msg) if gid else "\n".join(replies)
        finally:
            if gid:  # its words leave the request list once answered (or given up on)
                try:
                    self.app.jobs.forget_guest(gid)
                except Exception as e:
                    self.app.events.emit("voice_failed", part="guest words", error=f"{type(e).__name__}"[:100])
        return answer.strip() or None

    # ----------------------------------------------------------------------------------------- commands
    def commands(self) -> list[Command]:
        return [
            Command(
                "voice",
                "Voice: what it's doing; mute, unmute, stop (stop speaking), say <text>; id (Voice ID), enrol",
                self._cmd,
                usage="/voice [mute|unmute|stop|say <text>|id [test|retrain|undo today|undo all|forget]|"
                "enrol [again|stop]]",
            )
        ]

    def callbacks(self) -> dict:
        return self.voiceid.callbacks()  # vid: Forget my voice / Keep it (a data.delete button, core/tap.py)

    # ------------------------------------------------------------------------------------------- Voice ID
    def card(self) -> dict:
        vid = self.voiceid
        if not vid.on():
            line = "Voice ID: off (only your voice can make it act, once it's on and knows your voice)"
        elif vid.enrolled():
            t = vid.template() or {}
            line = f"Voice ID: on · knows your voice ({len(t.get('samples') or [])} samples, " + (
                f"{(t.get('report') or {}).get('grade', '?')})"
            )
        else:
            line = "Voice ID: on · doesn't know your voice yet"
        return {
            "lines": [line],
            "toggles": [
                {"id": "speaker_id.on", "label": "Voice ID: only your voice can make it act", "on": vid.on()},
                {"id": "speaker_id.adapt", "label": "Voice ID: improve over time", "on": bool(vid.s("adapt"))},
            ],
        }

    def card_action(self, act: str, value) -> str:
        if act not in ("speaker_id.on", "speaker_id.adapt"):
            return "There's no such part."
        self.app.settings.set(f"voice.{act}", bool(value))
        self.app.events.emit("voiceid_switch", part=act.split(".")[1], on=bool(value))
        if act == "speaker_id.on" and value and not self.voiceid.enrolled():
            return "Voice ID is on, but it doesn't know your voice yet: open Your voice (Voice ID) to enrol."
        name = "Voice ID" if act == "speaker_id.on" else "Improving over time"
        return f"{name}: {'on' if value else 'off'}."

    def _cmd_id(self, msg: Incoming | None, arg: str) -> str | None:
        vid = self.voiceid
        word, _, rest = (arg or "").strip().partition(" ")
        word = word.lower()
        if word in ("", "status"):
            st = vid.status()
            r = st["report"] or {}
            lines = [vid.line() or "Voice ID: off (voice.speaker_id.on)"]
            if st["enrolled"]:
                th = st["thresholds"] or {}
                lines.append(
                    f"{st['samples']['total']} samples, {r.get('grade', '?')}; thresholds: long "
                    f"{th.get('long', {}).get('accept')}, short {th.get('short', {}).get('accept')}"
                )
                lt = st["last_test"]
                if lt:
                    lines.append(
                        f"Last test ({lt.get('day')}): you {lt.get('me_passed', 0)} of {lt.get('me_tries', 0)}, "
                        f"someone else turned away {lt.get('other_passed', 0)} of {lt.get('other_tries', 0)}"
                    )
            w = st["who"]
            lines.append(f"Since start: {w['owner']} you, {w['guest']} someone else, {w['unsure']} unsure; "
                         f"{st['guest_turns']} guest turns answered.")  # fmt: skip
            lines.append("/voice enrol, /voice id test, retrain, undo today|all, forget; the page: /voice-id")
            return "\n".join(lines)
        if word == "test":
            r = vid.test("me")
            if not r.get("ok"):
                return r.get("message")
            said = {"owner": "That was you", "unsure": "Not sure it was you", "guest": "That was someone else"}
            return f"{said[r['decision']]}, score {r['score']:.2f}."
        if word == "retrain":
            return vid.train(session=None).get("message")
        if word == "undo":
            which = rest.strip().lower()
            if which not in ("today", "all"):
                return "/voice id undo today, or /voice id undo all"
            return vid.undo_adapt(which)["message"]
        if word == "forget":
            text = "Forget your voice? The voice print and its key are deleted; you'd enrol again to use Voice ID."
            if msg is not None:
                msg.reply(text, buttons=[[("Forget my voice", "vid:0:forget"), ("Keep it", "vid:0:keep")]])
                return None
            return text
        return "/voice id [test|retrain|undo today|undo all|forget]"

    def _cmd_enrol(self, arg: str) -> str:
        a = (arg or "").strip().lower()
        if a in ("stop", "keep", "pause"):
            return self.voiceid.session_cmd(a)["message"]
        r = self.voiceid.start_session(own_words="own" in a, fresh="again" in a.split())  # again: start over
        if not r.get("ok"):
            return r["message"]
        return (
            f"{r['message']} Follow the prompts at the computer (spoken, and on the Your voice page, /voice-id). "
            "/voice enrol stop stops; /voice enrol keep keeps what's done for later."
        )

    def _cmd(self, msg: Incoming, arg: str) -> str | None:
        word, _, rest = (arg or "").strip().partition(" ")
        word = word.lower()
        if word in ("id", "enrol", "enroll"):  # (voice id) typed only: never by voice, whoever's voice it is
            if msg is not None and (msg.via == "voice" or msg.voice):
                return NO_VOICE
            return self._cmd_id(msg, rest) if word == "id" else self._cmd_enrol(rest)
        if word == "mute":
            return self.mute(True)
        if word == "unmute":
            return self.mute(False)
        if word == "stop":
            self.speaker.stop()
            return "Stopped speaking."
        if word == "say":
            ok, why = self.say(rest, wait=False)
            return "Saying it." if ok else why
        h = self.heard
        ok, why = self.ready()
        return (
            f"Voice: {self.line()}" + ("" if ok else f"\n{why}") + ("\nMuted." if self.muted() else "")
            + f"\nHeard since start: {h[ADDRESSED]} to me, {h[CHATTER]} chatter, {h[NOISE]} noise (words of the last "
            "two are never kept)."
            + "\n/voice mute, /voice unmute, /voice stop, /voice say <text>; /voice id (Voice ID), /voice enrol"
        )  # fmt: skip


def _edges(pcm: bytes, seconds: float = 2.0) -> bytes:
    """(voice id) The first and last `seconds` of the sound with a short silence between: enough to hear its name
    called, first or last, without writing out the rest. Short sound comes back whole (the same object)."""
    n = int(seconds * 16000) * 2
    if len(pcm) <= 2 * n + 16000:
        return pcm
    return pcm[:n] + bytes(6400) + pcm[-n:]

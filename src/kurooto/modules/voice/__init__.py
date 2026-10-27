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
voice.addons.chat.

Listening better (0.8.13): careful calls when someone else may be talking (voice.listen.careful_name, chatter_s), the
conversation going on without its name (voice.listen.follow_s), being told off (voice.listen.told_off: it stops,
closes the conversation, notes a misfire), and the gate learning at night from how its turns went
(voice.listen.learn_nightly, learn.py). Voice ID gets Face presence's help (voice.speaker_id.face_assist) and keeps a
"not sure" voice the owner's in a conversation he opened (voice.speaker_id.carry_talk).

Barge-in (voice.listen.barge_in, barge.py): while Kurooto speaks, the microphone isn't dropped any more; your voice
(Voice ID) or a stretch clearly louder than its own echo stops it at once, and what you said is then a told-off stop, a
new turn in the same conversation, or it just listens.

Only someone in front of it (voice.listen.need_face, on by default; it does something only while Face presence is on
and enrolled): a turn may be addressed, by any rule but the wake word, only when Face presence saw a face close to the
camera (voice.listen.face_near of the owner's usual desk face height) and facing it (voice.listen.face_yaw_deg) during
the stretch or within FACE_AFTER_S of its end (core/nearby.py keeps the times and counts only). Else it's chatter ("no
one facing it nearby"): a roommate on a phone call across the room isn't answered. While Voice listens it holds the
camera (Face.hold_watch, core=True), never past Face presence's own pauses; when the camera can't see,
voice.listen.need_face_fallback says what happens: "voice" (the voice rules alone) or "none" (nothing answered by voice
until it can). Told-off phrases are always heard; typed /voice commands never go through here."""

from __future__ import annotations

import asyncio
import queue
import threading
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto.core import nearby
from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave
from kurooto.modules.base import Command, Incoming, Module
from kurooto.modules.voice import shape as shape_mod
from kurooto.modules.voice.barge import Barge
from kurooto.modules.voice.gate import (
    ADDRESSED,
    CHATTER,
    NOISE,
    TOLD_OFF,
    Context,
    Decision,
    Gate,
    Heard,
    asks,
    told_off,
)
from kurooto.modules.voice.learn import NIGHT_AT, Learner
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
            "join_sentences": True,  # short sentences spoken together (up to ~200 characters), not each on its own
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
            "careful_name": True,  # someone else may be talking: its name counts only said first, as a call
            "chatter_s": 60,  # speech not to it this recent (any voice) makes it careful with its name
            "follow_s": 20,  # after it answers, what the same voice says this soon counts, statements too (0: off)
            "told_off": True,  # "stop", "not you", "never mind" right after it opened or spoke: it stops and closes
            "learn_nightly": True,  # learn at night from turns that went well or were told off (numbers only)
            "barge_in": True,  # talk over Kurooto to stop it: your voice (Voice ID) or louder than its own echo
            "need_face": True,  # with Face presence on: answer only someone close to the camera and facing it
            "face_near": 0.5,  # close: a face at least this share of your usual desk face height (0.5: twice as far)
            "face_yaw_deg": 35,  # facing: turned at most this many degrees away from the camera
            "need_face_fallback": "voice",  # the camera can't see (paused, covered, busy): voice (its rules) or none
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
            "face_assist": True,  # a "not sure" voice counts as you while Face presence sees only your face
            "carry_talk": True,  # a "not sure" voice stays you in a conversation you opened (with carry)
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
# voice.listen.need_face: who's in front of it
FACE_HOLD = "voice: who's talking"  # the camera hold's reason, shown on Face presence's card
FACE_HOLD_S = 30.0  # each hold lasts this long (a crash can't keep the camera), renewed every FACE_RENEW_S
FACE_RENEW_S = 10.0
FACE_BEFORE_S = 0.5  # a frame this soon before the stretch began counts (frames come about a second apart)
FACE_AFTER_S = 1.5  # a frame this soon after it ended counts
FACE_SLOW_S = 2.0  # no frame in the stretch at all (3 s apart on battery): wait this much longer for one
NO_FACE = "no one facing it nearby"
BLIND = "the camera can't see: not answering by voice"
FACE_FREE = ("the wake word",)  # rules a face isn't needed for (told off never opens anything, so it needs none)


class Speaker:
    """Speaks text a piece at a time (a sentence, or short ones joined: shape.join): the next piece is made while this
    one plays, so speech starts as soon as the first piece is ready."""

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
        if self.v.setting("speak.join_sentences"):
            out = shape_mod.join(out)
        if not out:
            return
        try:  # barge-in: what it's about to say (the echo's words), and its own voice print made if wanted
            self.v.barge.speaking(out)
        except Exception:
            pass
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
                        pcm += pause_after(tts, out[i], sr)
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
        try:  # barge-in: what's played and when, for the echo's expected level (numbers only)
            self.v.barge.played(pcm, sr)
        except Exception:
            pass
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
        self.learner = Learner(app.paths.state / "voice")  # (0.8.13) the gate's learned veto: learn.py
        self._pending: dict | None = None  # the last addressed turn, until it's known how it went (memory only)
        self.misfires = 0  # told off since start (a count)
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
        self.barge = Barge(self)  # talking over it while it speaks: barge.py
        self._once: dict | None = None  # listen_once's hold: the next stretch goes to it, not to hear()
        self._once_lock = threading.Lock()  # one holder at a time
        self._face_hold_at = 0.0  # (need_face) when the camera hold was last renewed; 0: not held
        self._face_sleep = time.sleep  # (need_face) waiting for a frame; tests replace it
        self.face_counts = {"no_face": 0, "blind": 0}  # (need_face) turns it turned down since start: counts only

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
        learned = self.learned_line()
        if learned:
            tail += f"; {learned}"
        if not self.setting("listen.on"):
            return f"{speak}; not listening (voice.listen.on is off){tail}"
        if self.blocked_why:
            return f"{speak}; not listening: {self.blocked_why}{tail}"
        own = " or your wake word" if str(self.setting("listen.wake_word") or "").strip() else ""
        face = self.face_line()
        face = f"; {face}" if face else ""
        return f"{speak}; listening here (its name{own} wakes it){face}{tail}"

    def face_line(self) -> str:
        """(need_face) "" when it doesn't apply; else whether the camera sees, and the fallback when it can't."""
        state, why = self.face_gate()
        if state == "off":
            return ""
        if state == "on":
            return "answers only someone facing it"
        rules = "using voice rules" if self._fallback() == "voice" else "not answering by voice"
        return f"needs a face: camera paused ({why}), {rules}" if why else f"needs a face: camera not looking, {rules}"

    def learned_line(self) -> str:
        """(0.8.13) What the gate learned, numbers only ("" with nothing learned or learn_nightly off)."""
        if not self.setting("listen.learn_nightly"):
            return ""
        st = self.learner.status()
        if not st["rows"] and not self.misfires:
            return ""
        acting = "acting" if st["active"] else "not acting yet"
        return (f"learned from {st['rows']} turns ({st['misfires']} misfires), {acting}; "
                f"{self.misfires} told off and {st['vetoes']} held back since start")  # fmt: skip

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
        face_state, face_why = self.face_gate()
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
                "face_learned": self.voiceid.face_learned,
            },
            "learned": {**self.learner.status(), "on": bool(s("listen.learn_nightly")), "misfires_now": self.misfires},
            "barge_in": {"on": bool(s("listen.barge_in")), "since_start": self.barge.count},
            "need_face": {  # (0.8.13) words and counts only
                "on": bool(s("listen.need_face")),
                "state": face_state,
                "why": face_why,
                "fallback": self._fallback(),
                "held": bool(self._face_hold_at),
                "seen_s": self._face_seen_s(),  # seconds since a face close and facing it was last seen
                **self.face_counts,
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
                    parts = shape_mod.sentences(text, numbers=words)
                    if self.setting("speak.join_sentences"):
                        parts = shape_mod.join(parts)
                    parts = parts or [text]
                    for i, part in enumerate(parts):
                        got, sr = tts.synth(part)
                        pcm += got + (pause_after(tts, part, sr) if i + 1 < len(parts) else b"")
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
            veto=self.learner.veto if self.setting("listen.learn_nightly") else None,
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
        self._moment(ctx, who)
        d = g.decide(h, ctx)
        if d.why == TOLD_OFF:
            self._told_off(h, audio)
            return None
        d = self.face_check(h, d)
        self.heard[d.klass] = self.heard.get(d.klass, 0) + 1
        if not d.addressed:
            self._heard_wave(audio)
            del audio
            h.text = ""  # dropped here: never stored, logged or sent
            was_open = self.portal.open
            self.portal.take(h, d)
            if not was_open:
                self.portal.state("listening", d.klass)
            if not self.portal.open:  # how that turn went stays unknown: not learned from
                self._pending = None
                vid.take_face()
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
        self._went_well(who)
        row = {**d.feats}
        if who is not None:  # checked after the decision: the row gets the verdict all the same
            row["speaker"], row["score"] = who.decision, who.score
        face = vid.take_face() if on else None
        reply = self.portal.take(h, d, text=said, who=who)
        if self.portal.open:
            self._pending = {"row": row, "session": self.portal.session, "who": who.decision if who else "",
                             "face": face}  # fmt: skip
        return reply

    # ----------------------------------------------------------------------------- 0.8.13: the moment, told off
    def _moment(self, ctx: Context, who) -> None:
        """What the gate needs to know of the moment beyond the portal: the switches, Kurooto speaking, the faces in
        view (Face presence, core/nearby.py) and, with Voice ID, whose voice this is."""
        s = self.setting
        ctx.careful = bool(s("listen.careful_name"))
        ctx.chatter_s = float(s("listen.chatter_s") or 60)
        ctx.follow_window_s = float(s("listen.follow_s") or 0)
        ctx.told_off = bool(s("listen.told_off"))
        self.portal.follow_s = ctx.follow_window_s
        ctx.speaking = self.speaker.holding()
        if ctx.speaking:  # an output (a phone) may still be playing it: it hasn't finished speaking yet
            ctx.since_spoke_s = 0.0
        try:
            got = nearby.view(self.app)
        except Exception:
            got = None
        ctx.faces = got[0] if got is not None else None
        if who is not None:
            ctx.speaker, ctx.speaker_score = who.decision, who.score
            p = self.portal
            if p.open and p.last_who:  # the voice it answered last, and that opened the talk
                ctx.same_speaker = who.decision == p.last_who and who.decision == p.opener

    # ------------------------------------------------------------------- need_face: only someone in front of it
    def _face(self):
        """Face presence, when need_face applies: the switch on, Face presence on and enrolled. Else None."""
        if not self.setting("listen.need_face") or not self.app.is_on("face"):
            return None
        face = self.app.modules.get("face")
        try:
            return face if face is not None and face.enrolled() and not face.reenrol_needed() else None
        except Exception:
            return None

    def face_gate(self) -> tuple[str, str]:
        """("off", "") need_face doesn't apply (the voice rules as before); ("on", "") the camera may look;
        ("blind", why) Face presence is paused or the camera can't be used (why: its pause reason)."""
        face = self._face()
        if face is None:
            return "off", ""
        try:
            why = face.pause_reason()
        except Exception:
            why = "Face presence can't say"
        return ("blind", why) if why else ("on", "")

    def _face_seen_s(self) -> float | None:
        at = nearby.last_facing(self.app)
        return None if at is None else round(time.monotonic() - at, 1)

    def _fallback(self) -> str:
        how = str(self.setting("listen.need_face_fallback") or "voice").strip().lower()
        return "none" if how == "none" else "voice"

    def face_check(self, h: Heard, d: Decision) -> Decision:
        """An addressed turn stays addressed only when a face close to the camera and facing it was seen during the
        stretch or within FACE_AFTER_S of its end (core/nearby.py); else it's chatter. The wake word needs no face,
        and neither does the request right after it. When the camera can't see: need_face_fallback."""
        if not d.addressed or d.why in FACE_FREE:
            return d
        if d.why == "right after it was called" and self.portal.opened_why in FACE_FREE:
            return d
        state, _why = self.face_gate()
        if state == "off":
            return d
        if state == "on":
            end = h.ended_at if h.ended_at is not None else time.monotonic()
            lo, hi = end - max(float(h.seconds or 0), 0.0) - FACE_BEFORE_S, end + FACE_AFTER_S
            while True:
                looked, ok = nearby.facing(self.app, lo, hi)
                limit = hi
                if not looked:  # no frame in the stretch yet: a slow camera gets a little longer
                    limit = hi + FACE_SLOW_S
                    looked, ok = nearby.facing(self.app, lo, limit)
                if ok:
                    return d
                left = limit - time.monotonic()
                if left <= 0:
                    break
                self._face_sleep(min(0.1, left))
            if looked:
                self.face_counts["no_face"] += 1
                return self._not_to_it(d, NO_FACE)
        if self._fallback() == "voice":  # paused, busy, covered, or no frame came: the voice rules alone
            return d
        self.face_counts["blind"] += 1
        return self._not_to_it(d, BLIND)

    @staticmethod
    def _not_to_it(d: Decision, why: str) -> Decision:
        out = Decision(CHATTER, 0.9, why, d.name, d.where, d.careful)
        out.feats = dict(d.feats)
        return out

    def _face_hold(self) -> None:
        """(need_face) While Voice listens, keep Face presence's camera looking (renewed); released otherwise."""
        face = self._face()
        listening = self.listener is not None and self.listener.running() and not self.blocked_why
        if face is None or not listening:
            self._face_release()
            return
        now = time.monotonic()
        if not self._face_hold_at or now - self._face_hold_at >= FACE_RENEW_S:
            try:
                held = face.hold_watch(FACE_HOLD, FACE_HOLD_S, core=True)
            except Exception:
                held = False
            self._face_hold_at = now if held else 0.0

    def _face_release(self) -> None:
        if not self._face_hold_at:
            return
        self._face_hold_at = 0.0
        face = self.app.modules.get("face")
        if face is not None:
            try:
                face.release_watch(FACE_HOLD)
            except Exception:
                pass

    def _went_well(self, who) -> None:
        """An addressed turn in the same conversation, from the same voice: the turn before it went well (a row
        labelled 1), and a face-confirmed one may now refine the voice print (voiceid.learn_face)."""
        pend, self._pending = self._pending, None
        if pend is None or not self.portal.open or pend["session"] != self.portal.session:
            return
        if pend["who"] != (who.decision if who is not None else ""):
            return
        if self.setting("listen.learn_nightly"):
            try:
                self.learner.record(pend["row"], 1)
            except OSError as e:
                self.app.events.emit("voice_failed", part="learning", error=f"{type(e).__name__}"[:100])
        if pend["face"] is not None:
            self.voiceid.learn_face(pend["face"])

    def _told_off(self, h: Heard, audio: bytes | None) -> None:
        """Told off ("stop", "not you" ...) right after it opened or spoke: stop speaking at once, close the talk, no
        reply; a misfire event (the rules, never words) and, with learn_nightly, a training row labelled 0."""
        self.speaker.stop()
        self._heard_wave(audio)
        h.text = ""
        p = self.portal
        pend, self._pending = self._pending, None
        if pend is not None and pend["session"] != p.session:
            pend = None
        turn = pend["row"].get("rule") if pend is not None else ""
        self.misfires += 1
        self.heard[CHATTER] = self.heard.get(CHATTER, 0) + 1
        self.app.events.emit("voice_misfire", rule=(p.opened_why if p.open else "") or turn or "speaking", turn=turn)
        if pend is not None and self.setting("listen.learn_nightly"):
            try:
                self.learner.record(pend["row"], 0)
            except OSError as e:
                self.app.events.emit("voice_failed", part="learning", error=f"{type(e).__name__}"[:100])
        self.voiceid.take_face()  # a face-assisted turn that was told off is never learned from
        if not p.close("told off"):
            p.state("listening", "told off")

    def barge_turn(self, pcm: bytes, flags: bytes, how: dict, ended_at: float | None = None) -> str | None:
        """(barge.py) A stretch that talked over Kurooto; it has already stopped speaking. Written out here, then: a
        told-off phrase -> the told-off path (no reply); a question or a request -> a new turn in the same
        conversation (the chat's context carries); anything else -> it listens, the conversation open for
        voice.listen.follow_s. Returns the reply when there was one. An event with how and what came of it, never
        words."""
        if self.blocked() or not self.app.is_on(self.id):
            return None
        self.speaker.stop()  # already stopped; a piece that slipped through is ended too
        seconds = len(pcm) / 32000
        speech_s = sum(1 for f in flags if f) * 512 / 16000 if flags else seconds
        h = Heard(speech=True, seconds=seconds, speech_s=speech_s, ended_at=ended_at)
        h.text = self._write_out(pcm)
        g = self.gate()
        self._pending = None  # the interrupted turn: how it went isn't known, nothing learned from it
        outcome = "listen"
        reply = None
        if self.setting("listen.told_off") and told_off(h.text, g.matcher):
            outcome = "told off"
            self._told_off(h, pcm)
        else:
            said = g.matcher.uncall(h.text).strip()
            who = None
            vid = self.voiceid
            if vid.on():
                from kurooto.modules.voice import barge as barge_mod
                from kurooto.modules.voice.speakerid import OWNER, Verdict

                if how.get("how") == barge_mod.VOICE:  # checked against its own voice already: you
                    who = Verdict(OWNER, barge_mod.OWN_WHY, how.get("score"), speech_s)
                else:  # never learned from: its own voice may be in it
                    who = vid.check(pcm, speech_s, adapt=False)
            d = self.face_check(h, Decision(ADDRESSED, 0.9, "barged in")) if said and asks(said) else None
            if d is not None and not d.addressed:  # (need_face) nobody in front of it: chatter, the talk closes
                outcome = "no face"
                self.heard[CHATTER] = self.heard.get(CHATTER, 0) + 1
                h.text = ""
                self.portal.take(h, d)
            elif d is not None:
                outcome = "turn"
                self.heard[ADDRESSED] = self.heard.get(ADDRESSED, 0) + 1
                if who is not None:
                    self.publish("voice_state", state="addressed", portal=True, listening=True, why="barged in",
                                 who=who.word)  # fmt: skip
                reply = self.portal.take(h, Decision(ADDRESSED, 0.9, "barged in"), text=said, who=who)
            else:
                h.text = ""  # not sent: dropped here
                self.portal.listen_on("barged in", who.decision if who is not None else "")
        del pcm
        self.app.events.emit("voice_barge", how=how.get("how", ""), outcome=outcome)
        return reply

    def learn_nightly(self, payload=None) -> dict | None:
        """The nightly fit (learn.py), on a thread of its own: numbers only into the event."""
        if not self.setting("listen.learn_nightly"):
            return None
        out = self.learner.train()
        self.app.events.emit(
            "voice_learned", rows=out["rows"], good=out["good"], misfires=out["misfires"], active=out["active"]
        )
        return out

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
        """Play Kurooto's voice elsewhere (an add-on: another device). fn(pcm, sr, stop) gets each piece's 16-bit
        mono PCM at the engine's own rate `sr` (a sentence, or short ones joined), newest output first, instead of
        this computer's speakers; it blocks until the sound has played (or `stop` is set: /voice stop, mute, Voice
        off) and returns True, or False when it can't now (the next output,
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
        self.every("learn", NIGHT_AT, self.learn_nightly, thread=True)  # (0.8.13) while you sleep: learn.py
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
                self._face_hold()
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
            barge=self.barge,
        )
        self.listener.start()
        self.portal.state("addressed" if self.portal.open else "listening")

    def _stop_listening(self, why: str) -> None:
        self._face_release()
        if self.listener is not None:
            self.listener.stop()
            self.listener = None
            self._level_buf = bytearray()
            self.barge.reset()
            self.publish("voice_state", state="off", portal=self.portal.open, listening=False, why=why)
        while not self._work.empty():  # sound not yet written out is dropped
            try:
                self._work.get_nowait()
            except queue.Empty:
                break

    def _heard_audio(
        self, pcm: bytes, woke: bool, seconds: float, flags: bytes = b"", barge: dict | None = None
    ) -> None:
        """From the listener's thread: queued for writing out (the oldest dropped when it can't keep up). barge: the
        stretch talked over Kurooto (barge.py), with how it was noticed."""
        ended = time.monotonic()  # (need_face) when the stretch ended: the face must be seen around then
        try:
            self._work.put_nowait((pcm, woke, seconds, flags, barge, ended))
        except queue.Full:
            try:
                self._work.get_nowait()
                self._work.put_nowait((pcm, woke, seconds, flags, barge, ended))
            except (queue.Empty, queue.Full):
                pass

    def _work_loop(self) -> None:
        while True:
            self._work_one(*self._work.get())

    def _work_one(
        self,
        pcm: bytes,
        woke: bool,
        seconds: float,
        flags: bytes = b"",
        barge: dict | None = None,
        ended: float | None = None,
    ) -> None:
        """One stretch from the listener: a barge-in goes to barge_turn(); an add-on's listen_once takes it while it
        holds, else hear()."""
        try:
            slot = self._once
            if barge is not None:
                self.barge_turn(pcm, flags, barge, ended)
            elif slot is not None and not slot["done"].is_set():
                self._take_once(slot, pcm, seconds, flags)
            else:
                self.hear(Heard(speech=True, wake=woke, seconds=seconds, ended_at=ended), pcm, flags)
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
            + (f"\nLearned: {self.learned_line()}." if self.learned_line() else "")
            + "\n/voice mute, /voice unmute, /voice stop, /voice say <text>; /voice id (Voice ID), /voice enrol"
        )  # fmt: skip


def pause_after(tts, part: str, sr: int) -> bytes:
    """The silence after a piece when another follows (16-bit, at the piece's rate). kokoro-onnx trims the silence at
    both ends of what it makes and puts a pause back only between the batches it joins itself (0.25 s after a
    sentence, 0.1 s after a clause), so pieces made one at a time ran into each other with no breath between; this is
    its own pause, put back. Piper keeps its silence, so it gets none."""
    if getattr(tts, "name", "") != "kokoro":
        return b""
    return bytes(2 * int(sr * (0.25 if part.rstrip()[-1:] in ".!?" else 0.1)))


def _edges(pcm: bytes, seconds: float = 2.0) -> bytes:
    """(voice id) The first and last `seconds` of the sound with a short silence between: enough to hear its name
    called, first or last, without writing out the rest. Short sound comes back whole (the same object)."""
    n = int(seconds * 16000) * 2
    if len(pcm) <= 2 * n + 16000:
        return pcm
    return pcm[:n] + bytes(6400) + pcm[-n:]

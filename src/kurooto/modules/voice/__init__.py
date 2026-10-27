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
voice_text, voice_speak (docs/wiki/dev/voice.md)."""

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

if TYPE_CHECKING:
    from kurooto.app import App

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
        },
    },
)

LOOPBACK = ("127.0.0.1", "localhost", "::1")
MIC_CHECK_S = 30
JOB_WAIT_S = 600
RETRY_S = 60  # a microphone that failed is tried again after this long


class Speaker:
    """Speaks text sentence by sentence: the next sentence is made while this one plays, so speech starts as soon
    as the first sentence is ready."""

    def __init__(self, v: Voice):
        self.v = v
        self.lock = threading.Lock()
        self.busy = False
        self.until = 0.0  # it finished speaking at (monotonic) + a short tail: the microphone ignores until then
        self.player = None
        self._cancel = threading.Event()

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
        parts = shape_mod.sentences(text)
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
                if self.player is None:
                    from kurooto.modules.voice.audio import Player

                    self.player = Player()
                fut = pool.submit(tts.synth, out[0])
                for i in range(len(out)):
                    pcm, sr = fut.result()
                    if i + 1 < len(out):
                        fut = pool.submit(tts.synth, out[i + 1])
                    if self._cancel.is_set():
                        break
                    self.v.publish("voice_speak", samples=shape_mod.from_pcm(pcm, sr), rate=shape_mod.RATE)
                    self.player.play(pcm, sr)
            except Exception as e:
                self.v.app.events.emit("voice_failed", part="speaking", error=f"{type(e).__name__}: {e}"[:300])
            finally:
                pool.shutdown(wait=False, cancel_futures=True)
                self.busy = False
                self.until = time.monotonic() + 0.4

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
        if not self.setting("listen.on"):
            return f"{speak}; not listening (voice.listen.on is off)"
        if self.blocked_why:
            return f"{speak}; not listening: {self.blocked_why}"
        own = " or your wake word" if str(self.setting("listen.wake_word") or "").strip() else ""
        return f"{speak}; listening here (its name{own} wakes it)"

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
        }

    def shape(self, text: str) -> dict:
        """POST /api/voice/shape: the text's waveform outline (shape.py), from the speech engine when it's here."""
        text = (text or "")[: shape_mod.MAX_CHARS]
        if self.app.is_on(self.id):
            tts, _why = self.tts()
            if tts is not None:
                try:
                    pcm = b""
                    sr = 24000
                    for part in shape_mod.sentences(text) or [text]:
                        got, sr = tts.synth(part)
                        pcm += got
                    if pcm:
                        return shape_mod.payload(shape_mod.from_pcm(pcm, sr), "tts")
                except Exception:
                    pass
        rate = float(self.setting("speak.rate") or 1.0)
        return shape_mod.payload(shape_mod.estimate(shape_mod.clean(text), rate), "estimate")

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
        if self.parts.missing([k for k in self.wants() if k != "pkg:wake" and not k.startswith("model:wake")]):
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

    def hear(self, h: Heard, audio: bytes | None = None) -> str | None:
        """One stretch of sound, from the listener (or a test): written out here when it's speech, judged, and either
        dropped or taken through the portal. Returns Kurooto's reply when there was one."""
        if self.blocked() or not self.app.is_on(self.id):
            return None
        self.portal.close_s = float(self.setting("listen.close_s") or 8)
        self.portal.state("hearing")
        if h.speech and not h.text and audio is not None:
            try:
                h.text = self.stt().text(audio)
            except Exception as e:
                self.app.events.emit("voice_failed", part="writing out", error=f"{type(e).__name__}"[:100])
                h.text = ""
        del audio
        g = self.gate()
        d = g.decide(h, self.portal.context())
        self.heard[d.klass] = self.heard.get(d.klass, 0) + 1
        if not d.addressed:
            h.text = ""  # dropped here: never stored, logged or sent
            was_open = self.portal.open
            self.portal.take(h, d)
            if not was_open:
                self.portal.state("listening", d.klass)
            return None
        said = g.matcher.uncall(h.text) if h.wake or d.why == "its name" else h.text  # the call itself isn't sent
        return self.portal.take(h, d, text=said)

    def ask_brain(self, text: str) -> str:
        """An addressed turn to your AI, like a chat message (spoken style); its answer as text."""
        replies: list[str] = []
        msg = Incoming(text=text, via="voice", voice=True, respond=lambda t, buttons=None: replies.append(str(t)))
        self.app.handle(msg)
        jid = getattr(msg, "job", None)
        if not jid:
            return "\n".join(replies)
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
        answer = (j.result or "").strip()
        chat = self.app.modules.get("chat")
        if chat is not None and answer and chat.owns(jid):  # the conversation goes on, as a typed one does
            try:
                chat.record_turn(j.prompt, answer)
            except Exception:
                pass
        return answer

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

    def _heard_audio(self, pcm: bytes, woke: bool, seconds: float) -> None:
        """From the listener's thread: queued for writing out (the oldest dropped when it can't keep up)."""
        try:
            self._work.put_nowait((pcm, woke, seconds))
        except queue.Full:
            try:
                self._work.get_nowait()
                self._work.put_nowait((pcm, woke, seconds))
            except (queue.Empty, queue.Full):
                pass

    def _work_loop(self) -> None:
        while True:
            pcm, woke, seconds = self._work.get()
            try:
                self.hear(Heard(speech=True, wake=woke, seconds=seconds), pcm)
            except Exception as e:
                self.app.events.emit("voice_failed", part="hearing", error=f"{type(e).__name__}"[:100])
            finally:
                del pcm

    # ----------------------------------------------------------------------------------------- commands
    def commands(self) -> list[Command]:
        return [
            Command(
                "voice",
                "Voice: what it's doing; mute, unmute, stop (stop speaking), say <text>",
                self._cmd,
                usage="/voice [mute|unmute|stop|say <text>]",
            )
        ]

    def _cmd(self, msg: Incoming, arg: str) -> str:
        word, _, rest = (arg or "").strip().partition(" ")
        word = word.lower()
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
            + "\n/voice mute, /voice unmute, /voice stop, /voice say <text>"
        )  # fmt: skip

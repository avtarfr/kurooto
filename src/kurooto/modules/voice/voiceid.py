"""Voice ID, the part of Voice that knows its owner's voice (0.8.10; voice.speaker_id.*, off by default).

With voice.speaker_id.on, each stretch of speech Voice hears is scored against the owner's enrolled voice print
(speakerid.py) and gets a verdict: owner, unsure or guest. It travels with the message as Incoming.speaker, and
App.handle sends anything that isn't the owner's to core/guest.py: chat only, no actions, none of his data. Unsure
counts as not the owner. With voice.speaker_id.gate on (the default once Voice ID is on), the verdict comes before the
words are written out: a voice that isn't his, not calling Kurooto by name and not in a conversation with it, is
dropped as chatter without being transcribed (only its first and last two seconds are, to hear the name).

Enrolment (enrol.py) runs here, on the computer's own microphone, started only by the owner (/voice enrol typed, or
the Your voice page at /voice-id); never by voice, the AI or a schedule. Training is a template and calibrated
thresholds over a pretrained model, not a network trained here. The template is sealed (core/biometric.py,
state/voiceid/template.bin, key biometric.voice.key) and forgotten with /voice id forget, the page, `kurooto voice id
forget` or /forget all. Sound is never written to disk; a score is never logged or put on the live stream.

Face assist (0.8.13, voice.speaker_id.face_assist): when Face presence sees exactly one face just now and it's the
owner's (core/nearby.py's view, set by Face presence each frame), a "not sure" score (inside the margin) counts as the
owner. A score below the margin stays someone else, two voices stay unsure, and strict turns it off. With "improve
over time" on (adapt), such a turn that went well (the owner carried on talking, nothing told off) may be added to the
voice print like a very sure turn, its embedding only, under the same caps, drift guard and undo (learn_face()).
The talk carry (voice.speaker_id.carry_talk) keeps a "not sure" voice the owner's in a conversation he opened.

Per microphone (0.9.2, devices.py; voice.speaker_id.per_device): through a microphone the print wasn't enrolled on,
turns proven his (his face alone in view, one voice, 2 s of speech; or a "that was me" tap) give that microphone its
own print, used after his one-time yes (a message with Use it / No, /voice id mics, the page). Until then "improve over
time" leaves the enrolled print alone there (a fix). "That was me" (voice.speaker_id.claim): a "not sure" turn's sound
is held in memory for claim_s (never written); a tap on an add-on's device (Voice.tapped) within that time, with his
face recognised alone, re-runs it as his (the hearing thread, check() hands it the owner's verdict once) and may keep
its vector as a sample (a microphone's own, or "improve over time" under its caps)."""

from __future__ import annotations

import datetime as dt
import queue
import threading
import time
from collections import deque
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from kurooto.core import biometric, nearby
from kurooto.core.biometric import BioStore, Locked
from kurooto.modules.voice import devices, enrol
from kurooto.modules.voice import speakerid as sid
from kurooto.modules.voice.parts import KOKORO_VOICES, VOICEID_MODELS

if TYPE_CHECKING:
    from kurooto.modules.voice import Voice

MODES = ("owner_only_acts", "owner_only_at_all")
STRICTNESS = ("relaxed", "normal", "strict")
OTHERS_RECENT_S = 120  # non-owner voices this recent count towards "people keep talking here"
TEST_S = 15
NO_VOICE = "That can't be done by voice: type it or use the dashboard."
SYNTH_PHRASES = enrol.PHRASES[:3]
SPEAKER_TAIL_S = 1.0  # (0.9.2) speech this soon after Kurooto spoke may be its own voice: never a microphone's sample
CLAIM_WHY = "you said it was you"  # (0.9.2) a claimed turn's verdict


def today() -> str:
    return dt.date.today().isoformat()


class VoiceID:
    def __init__(self, v: Voice):
        self.v = v
        self.app = v.app
        self.store = BioStore(v.app, "voice")
        self.lock = threading.RLock()
        self._tpl: dict | None = None
        self._loaded = False
        self.locked_why = ""
        self.embed_fn: Callable[[bytes], list] | None = None  # set by tests (a fake model); else the Embedder
        self._embedder = None
        self._emb_model = ""
        self.model_error = ""
        self._banks: dict[str, sid.Bank | None] = {}
        self._synthetic: dict[str, list] = {}
        self.who = {sid.OWNER: 0, sid.GUEST: 0, sid.UNSURE: 0}  # since start; never voices
        self.last_word = ""  # the last turn's decision word, for the ear
        self.guest_turns: deque[tuple[str, str]] = deque(maxlen=4)  # this portal session's guest turns, memory only
        self.guest_count = 0  # guest turns answered since start (a count only)
        self._others: deque[float] = deque(maxlen=50)  # times only
        self.session: enrol.Session | None = None
        self._thread: threading.Thread | None = None
        self.capturing = ""  # "enrolling your voice" / "testing your voice": Voice's own listener waits
        self.capture_with: Callable[[float, threading.Event], enrol.Cut | None] | None = None  # tests: a fake mic
        self.stt_fn: Callable[[bytes], str] | None = None  # tests: a fake transcriber
        self.pending: dict | None = None  # a built template waiting for "Use it anyway" (weak)
        self.previous: dict | None = None  # the template before the last build (Undo, within the session)
        self.last_result: dict = {}  # the last build's report (numbers only)
        self.last_test: dict | None = None
        self._face_last: tuple | None = None  # (vector, verdict, voices) of the last face-assisted turn, memory only
        self.face_learned = 0  # face-confirmed turns added to the voice print since start (a count)
        # (0.9.2) per microphone: who opens another microphone than voice.listen.device (the "ears source lost"
        # failover) sets its name here, "" when it's that one again, so the right print is used and learned
        self.capture_device = ""
        self._claim: dict | None = None  # (0.9.2) the last "not sure" turn: its sound and vector, memory only
        self._claim_timer: threading.Timer | None = None
        self._forced: tuple | None = None  # (0.9.2) (the claimed sound, the owner's verdict): check() hands it once
        self._building: set[str] = set()  # microphones whose print is being built

    # ------------------------------------------------------------------------------------------- settings
    def s(self, key: str, default: Any = None) -> Any:
        v = self.v.setting(f"speaker_id.{key}", default)
        return default if v is None else v

    def on(self) -> bool:
        return bool(self.s("on"))

    def model(self) -> str:
        m = str(self.s("model") or "campplus-en")
        return m if m in VOICEID_MODELS else "campplus-en"

    def model_part(self) -> str:
        return VOICEID_MODELS[self.model()][0]

    def model_sha(self) -> str:
        files = self.v.parts.table.get(self.model_part()) or []
        return files[0].sha256 if files else ""

    def rules(self) -> dict:
        strict = self.s("strictness") == "strict"
        carry = bool(self.s("carry", True)) and not strict
        return {
            "min_speech_s": float(self.s("min_speech_s", 1.0)),
            "carry": carry,
            "carry_s": float(self.s("carry_s", 15)),
            "strict": strict,
            "face_assist": bool(self.s("face_assist", True)) and not strict,
            "carry_talk": carry and bool(self.s("carry_talk", True)),
            # the talk carry lasts as long as the conversation window, at least carry_s
            "carry_talk_s": max(float(self.s("carry_s", 15)), float(self.v.setting("listen.follow_s") or 0)),
        }

    def face_owner(self) -> bool:
        """Face presence sees exactly one face just now, and it's the owner's (core/nearby.py)."""
        try:
            got = nearby.view(self.app)
        except Exception:
            return False
        return got is not None and got[0] == 1 and got[1]

    def mode(self) -> str:
        m = str(self.s("mode") or MODES[0])
        return m if m in MODES else MODES[0]

    # ------------------------------------------------------------------------------------------ the template
    def template(self) -> dict | None:
        with self.lock:
            if not self._loaded:
                try:
                    self._tpl = self.store.load()
                    self.locked_why = ""
                except Locked as e:
                    self._tpl, self.locked_why = None, str(e)
                    self.app.events.emit("voiceid_locked")
                self._loaded = True
            return self._tpl

    def thresholds(self, t: dict) -> sid.Thresholds:
        """The stored calibration with the manual threshold (voice.speaker_id.threshold) as it is set now."""
        base = sid.Thresholds.from_dict(t.get("calibrated") or t.get("thresholds") or {})
        return sid.override(base, float(self.s("threshold", 0.0) or 0.0), float(self.s("margin", 0.05)))

    def enrolled(self) -> bool:
        t = self.template()
        return bool(t and t.get("centroid") and t.get("report"))

    def _save(self, tpl: dict) -> None:
        with self.lock:
            tpl["updated"] = today()
            self.store.save(tpl)
            self._tpl, self._loaded, self.locked_why = tpl, True, ""

    def bank(self) -> sid.Bank | None:
        m = self.model()
        if m not in self._banks:
            self._banks[m] = sid.read_bank(sid.bank_path(m))
        return self._banks[m]

    def bank_problem(self) -> str:
        b = self.bank()
        if b is None or not b.rows:
            return "the impostor set for this model isn't in this version of Kurooto yet"
        if str(b.meta.get("model_sha256") or "") != self.model_sha():
            return "the impostor set doesn't match this model; update Kurooto"
        return ""

    # ---------------------------------------------------------------------------------------------- the model
    def missing_parts(self) -> list[str]:
        return self.v.parts.missing(["pkg:audio", "pkg:listen", "pkg:voiceid", f"model:{self.model_part()}"])

    def embed(self, pcm: bytes) -> list[float]:
        if self.embed_fn is not None:
            return sid.normalize(self.embed_fn(pcm))
        with self.lock:
            if self._embedder is None or self._emb_model != self.model():
                if self.missing_parts():
                    raise RuntimeError("Voice ID's parts aren't set up")
                self.v.parts.importable()
                try:
                    path = self.v.parts.path(VOICEID_MODELS[self.model()][1])
                    self._embedder = sid.Embedder(path)
                    self._emb_model, self.model_error = self.model(), ""
                except Exception as e:
                    self._embedder = None
                    self.model_error = f"{type(e).__name__}"
                    self.app.events.emit("voice_failed", part="voice id", error=f"{type(e).__name__}: {e}"[:300])
                    raise
            emb = self._embedder
        return emb.embed(pcm)

    def drop_model(self) -> None:
        with self.lock:
            self._embedder = None
            self._emb_model = ""

    def problem(self) -> str:
        """Why turns can't be checked now ("" when they can): every turn is then unsure (fail closed)."""
        t = self.template()
        if self.locked_why:
            return "locked"
        if not t or not t.get("report") or not t.get("centroid"):
            return "no voice print"
        if t.get("model") != self.model():
            return "enrolled with another model"
        if self.model_error:
            return "model failed"
        return ""

    # -------------------------------------------------------------------------------------------- hearing
    def check(self, pcm: bytes, speech_s: float, voices: int | None = None, adapt: bool = True) -> sid.Verdict:
        """One stretch of speech: owner, unsure or guest. The sound isn't kept; the score never leaves here. adapt
        False: never learned from (a stretch spoken over Kurooto's own voice, barge.py)."""
        f = self._forced
        if f is not None and f[0] is pcm:  # (0.9.2) a claimed turn: his, said by a tap with his face in view
            self._forced = None
            v = f[1]
            self.who[v.decision] = self.who.get(v.decision, 0) + 1
            self.last_word = v.word
            self._face_last = None
            return v
        p = self.v.portal
        ctx = sid.Ctx(
            portal_session=p.session,
            last_owner_at=p.last_owner_at,
            last_owner_session=p.last_owner_session,
            now=p.clock(),
            voices=voices,
            portal_open=p.open,
            face_owner=bool(self.s("face_assist", True)) and self.face_owner(),
        )
        missing = self.problem()
        t = self.template() if not missing else None
        dev = self.device()
        pr, on_dev = self._print_for(t, dev) if t else (None, "")  # (0.9.2) this microphone's own, once it's on
        ver = sid.Verifier(
            self.embed if not missing else None,
            sid.from_b64(pr["centroid"]) if pr else None,
            self.thresholds(pr) if pr else None,
        )
        v = ver.check(pcm, speech_s, ctx, missing=missing, **self.rules())
        self.who[v.decision] = self.who.get(v.decision, 0) + 1
        self.last_word = v.word
        if v.decision == sid.GUEST:
            self._others.append(time.monotonic())
            if self.v.setting("listen.conversation_mode"):
                biometric.note_others(self.app, float(self.v.setting("listen.conversation_s") or 60))
        if t is not None and ver.last is not None and adapt and self.s("adapt"):
            if on_dev:
                self._adapt_device(t, on_dev, ver.last, v, voices)
            elif devices.enrolled_on(t, dev):  # (0.9.2, a fix) another microphone without its own print: frozen
                self._adapt(t, ver.last, v, voices)
        if t is not None and ver.last is not None and adapt and not on_dev:
            self._bootstrap(t, dev, ver.last, v, voices, speech_s)
        self._face_last = (list(ver.last), v, voices) if v.assisted and ver.last is not None else None
        if ver.last is not None and adapt and v.decision == sid.UNSURE and v.score is not None:
            self._hold_claim(pcm, ver.last, v, dev, voices)
        ver.last = None
        return v

    def take_face(self) -> tuple | None:
        """The last turn's face-assisted vector (and its verdict), once: Voice holds it until the turn went well."""
        got, self._face_last = self._face_last, None
        return got

    def learn_face(self, got: tuple | None) -> bool:
        """A face-confirmed turn went well: with adapt and face_assist on, it may refine the voice print (Adapter's
        caps, drift guard and undo apply; the entry is marked face)."""
        if not got or not self.on() or not self.s("adapt") or not self.s("face_assist", True):
            return False
        e, v, voices = got
        with self.lock:
            t = self.template()
            if not t or self.problem():
                return False
            dev = self.device()
            _pr, on_dev = self._print_for(t, dev)
            if on_dev:  # (0.9.2) this microphone's own print learns instead
                return self._adapt_device(t, on_dev, e, v, voices, face=True)
            if not devices.enrolled_on(t, dev):  # (0.9.2, a fix) frozen on a microphone without its own print
                return False
            a = sid.Adapter(self.bank(), str(self.s("strictness") or "normal"), float(self.s("margin", 0.05)),
                            float(self.s("threshold", 0.0) or 0.0))  # fmt: skip
            work = dict(t)
            took, why = a.consider(
                work, e, v, voices, today(), int(self.s("adapt_per_day", 10)), int(self.s("adapt_max", 40)), face=True
            )
            if why == "drift" and not t.get("drift_stopped"):
                self._save(work)
                self.app.events.emit("voiceid_adapt_stopped")
            if took:
                self._save(work)
                self.face_learned += 1
                self.app.events.emit("voiceid_adapted", count=len(work.get("adapted") or []), face=True)
            return took

    # ------------------------------------------------------------------------- per microphone (0.9.2)
    def device(self) -> str:
        """The microphone listening now, as devices.key() names it."""
        return devices.key(self.capture_device or self.mic_now())

    def per_device(self) -> bool:
        return bool(self.s("per_device", True))

    def _print_for(self, t: dict, dev: str) -> tuple[dict, str]:
        """The print to score with: this microphone's own when it's in use (and the dev), else the enrolled one."""
        if self.per_device() and not devices.enrolled_on(t, dev):
            d = devices.entry(t, dev)
            if devices.usable(d):
                return d["print"], dev  # type: ignore[index]
        return t, ""

    def device_bank(self) -> tuple[sid.Bank | None, str]:
        """The impostors heard through a simulated phone channel when they ship for this model, else the plain set."""
        m = self.model()
        k = f"{m}-phone"
        if k not in self._banks:
            b = sid.read_bank(sid.bank_path(m, "phone"))
            self._banks[k] = b if b is not None and str(b.meta.get("model_sha256") or "") == self.model_sha() else None
        b = self._banks[k]
        return (b, "phone") if b is not None and b.rows else (self.bank(), "plain")

    def _speaker_near(self) -> bool:
        sp = self.v.speaker
        try:
            return bool(sp.busy or sp.holding() or time.monotonic() < sp.until + SPEAKER_TAIL_S)
        except Exception:
            return True

    def _bootstrap(self, t: dict, dev: str, e: list, v: sid.Verdict, voices: int | None, speech_s: float) -> None:
        """A turn through a microphone without its own print, proven his: his face alone in view at that moment, one
        voice, BOOT_SPEECH_S of speech, nothing of Kurooto's own voice around it. Its vector becomes a sample."""
        if not self.per_device() or devices.enrolled_on(t, dev) or not devices.learning(devices.entry(t, dev)):
            return
        if speech_s < devices.BOOT_SPEECH_S or (voices is not None and voices >= 2):
            return
        if self._speaker_near() or not self.face_owner():
            return
        self._add_device_sample(dev, e, "face", int(self.s("per_device_per_day", 10)))

    def _add_device_sample(self, dev: str, e: list, how: str, per_day: int) -> bool:
        with self.lock:
            t = self.template()
            if not t or self.problem():
                return False
            devs = dict(t.get("devices") or {})
            d = dict(devs.get(dev) or devices.new())
            took, _why = devices.add(d, e, how, today(), per_day)
            if not took:
                return False
            devs[dev] = d
            self._save({**t, "devices": devs})
            build = devices.due(d) and dev not in self._building
            if build:
                self._building.add(dev)
        self.app.events.emit("voiceid_device_sample", n=len(d["samples"]), how=how)
        if build:  # off the hearing thread: a turn never waits for it
            threading.Thread(target=self._build_device, args=(dev,), daemon=True, name="voiceid-device").start()
        return True

    def _build_device(self, dev: str) -> None:
        try:
            with self.lock:
                t = self.template()
                if not t or self.problem() or not devices.entry(t, dev):
                    return
                d = dict(devices.entry(t, dev) or {})
            bank, channel = self.device_bank()
            if bank is None or not bank.rows:
                return
            strictness, margin = str(self.s("strictness") or "normal"), float(self.s("margin", 0.05))
            # outside the lock: a turn's check never waits for the calibration
            grade = devices.build(d, bank, channel, strictness, margin, float(self.s("threshold", 0.0) or 0.0))
            if not grade:
                return
            with self.lock:
                t = self.template()
                now = devices.entry(t, dev) if t else None
                if not t or now is None or not devices.learning(now):  # forgotten, or answered, meanwhile
                    return
                d["samples"] = now.get("samples") or d["samples"]  # any taken meanwhile stay (the next build uses them)
                ask = d["state"] == "ready" and not d.get("asked")
                if ask:
                    d["asked"] = True
                self._save({**t, "devices": {**(t.get("devices") or {}), dev: d}})
            self.app.events.emit("voiceid_device_built", grade=grade, samples=int(d["built_n"]), bank=channel)
            if ask:
                self._ask_device(dev, d)
        except Exception as e:
            self.app.events.emit("voice_failed", part="voice id microphone", error=f"{type(e).__name__}"[:100])
        finally:
            self._building.discard(dev)

    def _ask_device(self, dev: str, d: dict) -> None:
        """The one-time yes: a message with Use it / No (Calm's reason voice.id_device)."""
        r = (d.get("print") or {}).get("report") or {}
        self.app.notify(
            f"Voice ID has learned how you sound through {dev} from {d.get('built_n')} turns it was sure were you "
            f"(your face alone in view, or you said so); its print there is {r.get('grade', 'fair')}. Use it to know "
            "you on that microphone? Until you say yes it uses your enrolled print there and doesn't change it. Only "
            "numbers are kept, sealed like your voice print.",
            kind="info",
            why="voice.id_device",
            setting="voice.speaker_id.per_device",
            about="Voice ID on another microphone",
            buttons=[[("Use it", f"vid:{devices.ref(dev)}:devuse"), ("No", f"vid:{devices.ref(dev)}:devno")]],
        )

    def device_answer(self, which: str, act: str) -> dict:
        """use / no / forget for a microphone (its name, ref or number in /voice id mics). Typed, a button or the
        page; never by voice."""
        with self.lock:
            t = self.template()
            if not t or self.problem() in ("locked", "no voice print"):
                return {"ok": False, "message": "There's no voice print."}
            devs = dict(t.get("devices") or {})
            names = list(devs)
            dev = next((n for n in names if which in (n, devices.ref(n))), None)
            if dev is None and which.isdigit() and 0 < int(which) <= len(names):
                dev = names[int(which) - 1]
            if dev is None:
                return {"ok": False, "message": "No such microphone: /voice id mics lists them."}
            d = dict(devs[dev])
            if act == "forget":
                devs.pop(dev)
                msg = f"Forgot what it learned through {dev}; it starts learning there again."
            elif act == "use":
                if not (d.get("print") or {}).get("centroid"):
                    return {"ok": False, "message": f"There's no print for {dev} yet ({len(d.get('samples') or [])} "
                            f"of {sid.MIN_SAMPLES} turns)."}  # fmt: skip
                devices.decide(d, True)
                devs[dev] = d
                msg = f"It now knows you through {dev} by its own print."
            elif act == "no":
                devices.decide(d, False)
                devs[dev] = d
                msg = f"Not used, and dropped: it won't learn through {dev} (/voice id mic forget to start again)."
            else:
                return {"ok": False, "message": "use, no or forget."}
            self._save({**t, "devices": devs})
        self.app.events.emit("voiceid_device", act=act)
        return {"ok": True, "message": msg}

    def devices_view(self) -> list[dict]:
        t = self.template() or {}
        now = self.device() if self.app.is_on("voice") else ""
        return [devices.view(n, d, now) for n, d in (t.get("devices") or {}).items()]

    def _adapt_device(self, t: dict, dev: str, e: list, v: sid.Verdict, voices: int | None, face: bool = False) -> bool:
        """Improve over time on a microphone's own print (the same caps, drift guard and undo as the enrolled one's,
        against the impostors it was built with)."""
        with self.lock:
            d = dict(devices.entry(t, dev) or {})
            pr = dict(d.get("print") or {})
            if not pr.get("centroid"):
                return False
            bank = self.device_bank()[0] if pr.get("bank") == "phone" else self.bank()
            a = sid.Adapter(bank, str(self.s("strictness") or "normal"), float(self.s("margin", 0.05)),
                            float(self.s("threshold", 0.0) or 0.0))  # fmt: skip
            took, why = a.consider(pr, e, v, voices, today(), int(self.s("adapt_per_day", 10)),
                                   int(self.s("adapt_max", 40)), face=face)  # fmt: skip
            if took or (why == "drift" and not (d.get("print") or {}).get("drift_stopped")):
                d["print"] = pr
                self._save({**t, "devices": {**(t.get("devices") or {}), dev: d}})
            if took:
                self.app.events.emit("voiceid_adapted", count=len(pr.get("adapted") or []), device=True)
            return took

    # ---------------------------------------------------------------------------- "that was me" (0.9.2)
    def _hold_claim(self, pcm: bytes, e: list, v: sid.Verdict, dev: str, voices: int | None) -> None:
        """A "not sure" turn: its sound and vector, in memory for claim_s only, for a tap that says it was him."""
        self._drop_claim()
        if not self.s("claim", True) or (voices is not None and voices >= 2):
            return
        hold = float(self.s("claim_s", 10) or 10)
        self._claim = {"pcm": bytearray(pcm), "e": list(e), "v": v, "dev": dev, "at": time.monotonic(), "s": hold}
        tm = threading.Timer(hold + 1.0, self._drop_claim)
        tm.daemon = True
        self._claim_timer = tm
        tm.start()

    def _drop_claim(self) -> None:
        c, self._claim = self._claim, None
        if c is not None:
            c["pcm"][:] = bytes(len(c["pcm"]))  # zeroed, never written anywhere
        tm, self._claim_timer = self._claim_timer, None
        if tm is not None and tm is not threading.current_thread():
            tm.cancel()

    def claim(self) -> tuple[bool, str, bytes | None, float]:
        """A tap within claim_s of a "not sure" turn, with only his face in view: the turn was his. Its vector may be
        kept (a microphone's own sample, or "improve over time" under its caps), the claim is counted (claim_per_day)
        and its sound comes back to be heard again, his: check() hands that sound the owner's verdict once.
        (ok, why not, the sound, seconds of speech)."""
        c = self._claim
        if not self.on() or not self.s("claim", True):
            return False, "off", None, 0.0
        if c is None or time.monotonic() - c["at"] > c["s"]:
            return False, "nothing to claim", None, 0.0
        if not self.face_owner():
            return False, "not with only your face in view", None, 0.0
        with self.lock:
            t = self.template()
            if not t or self.problem():
                return False, "no voice print", None, 0.0
            dev, day = c["dev"], today()
            got = dict(t.get("claimed") or {})
            n = int(got.get("n") or 0) if got.get("day") == day else 0
            if n >= int(self.s("claim_per_day", 5)):
                return False, "enough claims for today", None, 0.0
            self._save({**t, "claimed": {"day": day, "n": n + 1}})
        self._claim = None
        v: sid.Verdict = c["v"]
        e = c["e"]
        took = False
        if v.speech_s >= devices.CLAIM_SPEECH_S:
            t = self.template() or {}
            _pr, on_dev = self._print_for(t, dev)
            if self.per_device() and not on_dev and not devices.enrolled_on(t, dev):
                took = self._add_device_sample(dev, e, "claim", int(self.s("claim_per_day", 5)))
            elif self.s("adapt"):
                mine = sid.Verdict(sid.OWNER, CLAIM_WHY, v.score, v.speech_s, v.short, assisted=True)
                took = self.learn_face((e, mine, None))
        pcm = bytes(c["pcm"])
        c["pcm"][:] = bytes(len(c["pcm"]))
        self._forced = (pcm, sid.Verdict(sid.OWNER, CLAIM_WHY, v.score, v.speech_s, v.short, assisted=True))
        self.app.events.emit("voiceid_claimed", kept=took)
        return True, "", pcm, v.speech_s

    def others_lately(self) -> int:
        now = time.monotonic()
        return sum(1 for x in self._others if now - x <= OTHERS_RECENT_S)

    def conversation(self) -> bool:
        """Conversation mode: another voice (or a second face) here lately. Only its name opens the portal then."""
        return bool(self.on() and self.v.setting("listen.conversation_mode") and biometric.others_present(self.app))

    def _adapt(self, tpl: dict, e: list, v: sid.Verdict, voices: int | None) -> None:
        a = sid.Adapter(self.bank(), str(self.s("strictness") or "normal"), float(self.s("margin", 0.05)),
                        float(self.s("threshold", 0.0) or 0.0))  # fmt: skip
        work = dict(tpl)
        took, why = a.consider(
            work, e, v, voices, today(), int(self.s("adapt_per_day", 10)), int(self.s("adapt_max", 40))
        )
        if why == "drift" and not tpl.get("drift_stopped"):
            self._save(work)
            self.app.events.emit("voiceid_adapt_stopped")
        if took:
            self._save(work)
            self.app.events.emit("voiceid_adapted", count=len(work.get("adapted") or []))

    def heard_guest(self, said: str, answer: str) -> None:
        """A guest's turn and its answer: kept for this portal session only (the next turns' context), never
        written down; only the count lasts."""
        self.guest_turns.append((said[:400], answer[:600]))
        self.guest_count += 1
        self.app.events.emit("voiceid_guest_turn")

    def portal_closed(self) -> None:
        self.guest_turns.clear()

    # ---------------------------------------------------------------------------------------- the status
    def mic_now(self) -> str:
        dev = str(self.v.setting("listen.device") or "")
        if dev:
            return dev
        try:
            has, name = self.v.microphone()
        except Exception:
            return ""
        return name if has else ""

    def line(self) -> str:
        if not self.on():
            return ""
        if self.capturing:
            return f"Voice ID: {self.capturing}"
        why = self.problem()
        if why == "locked":
            return "Voice ID: on, but its key can't be read (every voice can only chat)"
        if why == "no voice print":
            return "Voice ID: on · doesn't know your voice yet: enrol on the Your voice page"
        if why == "enrolled with another model":
            return "Voice ID: on · enrolled with another model: enrol again"
        t = self.template() or {}
        r = t.get("report") or {}
        out = f"Voice ID: on · knows your voice ({len(t.get('samples') or [])} samples, {r.get('grade', '?')})"
        if why == "model failed":
            out += " · its model didn't load (every voice can only chat)"
        if self.conversation():
            out += " · conversation: staying out"
        if self.last_word:
            out += f" · last: {self.last_word}"
        mic = t.get("mic") or ""
        now = self.mic_now() if self.v.setting("listen.on") else ""
        if mic and now and mic != now:
            out += f" · enrolled with {mic}, listening with {now}: add a few samples with this microphone"
        return out

    def health(self) -> tuple[bool, str] | None:
        """A Voice ID problem for /health, or None."""
        if not self.on():
            return None
        if self.locked_why:
            return False, "Voice ID's key can't be read: every voice can only chat (the Your voice page)"
        if not self.enrolled():
            return False, "Voice ID is on but doesn't know your voice yet: enrol on the Your voice page"
        if self.model_error:
            return False, "Voice ID's model didn't load: every voice can only chat"
        return None

    def status(self) -> dict:
        """GET /api/voice/id: counts, grades, thresholds and the test's scores; never a vector."""
        t = self.template() or {}
        r = t.get("report") or {}
        by: dict[str, int] = {}
        for x in t.get("samples") or []:  # prompts answered (free speech's three windows are one)
            if not x.get("window"):
                by[x.get("cond") or "other"] = by.get(x.get("cond") or "other", 0) + 1
        missing = self.missing_parts()
        adapted = t.get("adapted") or []
        return {
            "on": self.on(),
            "voice_on": self.app.is_on("voice"),
            "listen_on": bool(self.v.setting("listen.on")),
            "mode": self.mode(),
            "model": self.model(),
            "models": list(VOICEID_MODELS),
            "strictness": str(self.s("strictness") or "normal"),
            "threshold": float(self.s("threshold", 0.0) or 0.0),
            "margin": float(self.s("margin", 0.05)),
            "enrolled": self.enrolled(),
            "locked": bool(self.locked_why),
            "problem": self.problem() if self.on() else "",
            "line": self.line(),
            "grade": r.get("grade"),
            "samples": {"total": len(t.get("samples") or []), "by_cond": by},
            "conditions": [{"cond": c.key, "label": c.label, "samples": c.samples} for c in enrol.CONDITIONS],
            "thresholds": t.get("thresholds"),
            "calibrated": t.get("calibrated"),
            "report": _numbers_only(r),
            "pending": _numbers_only(self.pending["report"]) if self.pending else None,
            "can_undo": self.previous is not None,
            "last_test": t.get("last_test"),
            "test": self.last_test,
            "dates": {"created": t.get("created"), "updated": t.get("updated")},
            "enrolled_model": t.get("model"),
            "adapt": {
                "on": bool(self.s("adapt")),
                "count": len(adapted),
                "cap": int(self.s("adapt_max", 40)),
                "today": sum(1 for a in adapted if a.get("day") == today()),
                "last": max((a.get("day") or "" for a in adapted), default=None),
                "drift_stopped": bool(t.get("drift_stopped")),
                "face": sum(1 for a in adapted if a.get("face")),  # (0.8.13) of them, face-confirmed turns
            },
            "face_assist": bool(self.s("face_assist", True)),
            "per_device": self.per_device(),  # (0.9.2) per microphone: counts, states, grades; never a vector
            "devices": self.devices_view(),
            "claim": bool(self.s("claim", True)),
            "mic": {"enrolled": t.get("mic") or "", "now": self.mic_now() if self.app.is_on("voice") else ""},
            "ready": not missing,
            "missing": missing,
            "missing_gb": self.v.parts.size_gb(missing),
            "bank": self.bank_problem() or "ok",
            "synthetic": bool(self._synthetic.get(self.model())),
            "who": dict(self.who),
            "guest_turns": self.guest_count,
            "session": self.session.view() if self.session is not None else None,
            "capturing": self.capturing,
        }

    # ------------------------------------------------------------------------------------------- capture
    def _mic_capture(self, max_s: float) -> tuple[Callable[[float, threading.Event], enrol.Cut | None], Callable]:
        """A capture function on the computer's microphone (Voice's own device and VAD), and its closer."""
        if self.capture_with is not None:
            return self.capture_with, lambda: None
        self.v.parts.importable()
        from kurooto.modules.voice import audio

        q: queue.Queue = queue.Queue(maxsize=2)
        began = [0.0]  # when the stretch being heard now began (0: none)

        def on_start() -> None:
            began[0] = time.monotonic()

        def on_speech(pcm: bytes, _woke: bool, _seconds: float, flags: bytes = b"") -> None:
            began[0] = 0.0
            try:
                q.put_nowait(enrol.Cut(bytearray(pcm), bytes(flags)))
            except queue.Full:
                pass

        vad = audio.Silero(self.v.parts.path("silero_vad.onnx")) if self.v.parts.has_model("vad") else audio.Energy()
        lis = audio.Listener(
            audio.Mic(str(self.v.setting("listen.device") or ""), str(self.v.setting("audio.backend") or "auto")),
            vad,
            None,
            on_speech=on_speech,
            on_start=on_start,
            on_level=self.v._level,  # noqa: SLF001 (the meter on the page)
            hold=self.v.speaker.holding,
        )
        lis.MAX_S = max(lis.MAX_S, max_s)
        lis.start()

        def capture(timeout: float, cancel: threading.Event) -> enrol.Cut | None:
            """What's said, if it starts within `timeout`: speech that began in time is waited for to its end (a
            stretch ends after a short quiet, or at MAX_S). Before, a sentence still going at the timeout was lost and
            the test said it heard nothing."""
            end = time.monotonic() + timeout
            while not cancel.is_set():
                now = time.monotonic()
                if now >= end and not (began[0] and now < began[0] + lis.MAX_S + 2):
                    break
                if lis.error:
                    raise RuntimeError(lis.error)
                try:
                    return q.get(timeout=0.2)
                except queue.Empty:
                    continue
            return None

        def close() -> None:
            lis.stop()
            while not q.empty():
                try:
                    q.get_nowait().release()
                except queue.Empty:
                    break

        return capture, close

    def _say(self, text: str) -> None:
        if self.s("spoken_enrol", True) and not self.v.muted():
            try:
                self.v.speaker.say(text, wait=True)
            except Exception:
                pass

    def _stt(self, pcm: bytes) -> str:
        return self.v.stt().text(pcm)

    # ------------------------------------------------------------------------------------------ enrolment
    def can_enrol(self) -> str:
        """Why enrolment can't start now ("" when it can)."""
        if not self.app.is_on("voice"):
            return "Voice is off: turn it on first (Features → Voice)."
        if self.v.muted():
            return "Voice is muted: /voice unmute first."
        if self.missing_parts() and self.capture_with is None:
            gb = self.v.parts.size_gb(self.missing_parts())
            return f"Voice ID needs setting up first (about {gb:g} GB): Features → Voice → Set up, with Voice ID on."
        if self.capture_with is None:
            has, _name = self.v.microphone()
            if has is False:
                return "No microphone found: Voice ID needs the one Kurooto listens with."
        if self.capturing and self.session is None:
            return f"Busy: {self.capturing}."
        return ""

    def start_session(self, own_words: bool = False, conds: list[str] | None = None, fresh: bool = False) -> dict:
        """Start (or continue) enrolment. Samples kept for later are resumed; conds: just these (Add samples).
        fresh: start over (re-enrol), the whole plan from nothing; the voice print in use stays in use until the new
        one is built, and Undo puts it back."""
        with self.lock:
            if self.session is not None and self.session.state not in ("done", "stopped", "kept"):
                if self.session.state == "paused":
                    self.session.command("continue")
                return {"ok": True, "session": self.session.view(), "message": "Enrolment is going on."}
            why = self.can_enrol()
            if why:
                return {"ok": False, "message": why}
            t = self.template()
            if self.locked_why:
                return {"ok": False, "message": "Voice ID's key can't be read: forget and enrol again."}
            existing = []
            if t and t.get("model") == self.model() and not fresh:
                existing = [{"e": sid.from_b64(x["e"]), "s": sid.from_b64(x["s"]) if x.get("s") else None,
                             "cond": x.get("cond"), "day": x.get("day")} for x in t.get("samples") or []]  # fmt: skip
            again = fresh or bool(t and t.get("reenrol"))  # starting over, or going on with a start-over kept
            if fresh:
                conds = None
            if existing and conds is None and t and t.get("report") and not again:  # enrolled: Add samples
                conds = ["other"]
            lang = str(self.v.setting("listen.language") or "")
            self.capturing = "enrolling your voice"
            self.v.portal.close("enrolling your voice")
            self.v._stop_listening("enrolling your voice")  # noqa: SLF001
            try:
                capture, close = self._mic_capture(30)
            except Exception as e:
                self.capturing = ""
                return {"ok": False, "message": f"Couldn't open the microphone: {type(e).__name__}"}
            self.session = enrol.Session(
                capture=capture,
                embed=self.embed,
                stt=self.stt_fn or self._stt,
                speak=self._say,
                publish=self.v.publish,
                name=self.app.name,
                own_words=bool(own_words) or (lang not in ("", "en")) or self.model() == "campplus-multi",
                conds=conds,
                existing=existing,
            )
            self.session.fresh = again  # type: ignore[attr-defined]
            self._thread = threading.Thread(target=self._run_session, args=(self.session, close), daemon=True,
                                            name="voice-enrol")  # fmt: skip
            self._thread.start()
            self.app.events.emit("voiceid_session", state="started", conds=len(self.session.plan))
            return {"ok": True, "session": self.session.view(), "message": "Enrolment started at the computer."}

    def _run_session(self, s: enrol.Session, close: Callable) -> None:
        try:
            end = s.run()
        except Exception as e:
            s.state, s.message = "stopped", f"The microphone stopped: {type(e).__name__}"
            end = "stopped"
        finally:
            close()
        try:
            if end == "kept":
                self._keep(s)
            elif end == "done":
                out = self.train(session=s)
                self._say(out.get("spoken") or out.get("message") or "")
        finally:
            self.capturing = ""
            self.app.events.emit("voiceid_session", state=end)

    def _keep(self, s: enrol.Session) -> None:
        """Keep for later: the vectors so far, sealed, no report (the session resumes from them)."""
        t = self.template() or {}
        samples = [_pack(x) for x in s.existing + s.samples]
        if not samples:
            return
        built = {}  # adding samples to a voice print in use: it stays in use (centroid, thresholds) until a Retrain
        if t.get("centroid") and t.get("report") and t.get("model") == self.model():
            keys = ("centroid", "centroid_enrolled", "thresholds", "calibrated", "genuine", "report", "adapted")
            built = {k: t[k] for k in (*keys, "drift_stopped") if k in t}
        again = bool(getattr(s, "fresh", False))  # a start-over kept for later: its samples replace the old ones
        if again and t.get("report") and not t.get("reenrol"):
            self.previous = t  # Undo (this run) brings the old samples back too
        self._save({**self._base(t), **built, "samples": samples, "report": built.get("report"),
                    **({"reenrol": True} if again else {})})  # fmt: skip

    def session_cmd(self, action: str, own_words: bool = False) -> dict:
        if action in ("start", "continue"):
            return self.start_session(own_words)
        if action == "again":  # start over (re-enrol)
            return self.start_session(own_words, fresh=True)
        s = self.session
        if s is None:
            return {"ok": False, "message": "No enrolment is going on."}
        if action not in ("pause", "stop", "keep"):
            return {"ok": False, "message": "Pause, stop, keep or continue."}
        s.command(action)
        return {"ok": True, "session": s.view(), "message": {"pause": "Paused.", "stop": "Stopped.",
                                                             "keep": "Kept for later."}[action]}  # fmt: skip

    def skip(self, cond: str) -> dict:
        s = self.session
        if s is None or s.cond is None or s.cond.key != cond:
            return {"ok": False, "message": "That step isn't the current one."}
        s.command("skip")
        return {"ok": True, "session": s.view()}

    # -------------------------------------------------------------------------------------------- train
    def _base(self, t: dict) -> dict:
        return {
            "model": self.model(),
            "model_sha256": self.model_sha(),
            "mic": t.get("mic") or self.mic_now(),
            "created": t.get("created") or today(),
            "samples": t.get("samples") or [],
            "adapted": [],
            "last_test": t.get("last_test"),
        }

    def synthetic(self) -> list:
        """30 synthetic impostors (3 phrases in each of Kokoro's 10 voices), made in memory, never played or saved;
        only when Kokoro is set up, so nothing extra is fetched."""
        m = self.model()
        if m in self._synthetic:
            return self._synthetic[m]
        if self.v.parts.missing(["pkg:kokoro", "model:kokoro"]) or self.embed_fn is not None:
            return []
        out = []
        try:
            self.v.parts.importable()
            from kurooto.modules.voice import audio

            k = audio.Kokoro(self.v.parts.path("kokoro-v1.0.onnx"), self.v.parts.path("voices-v1.0.bin"))
            for voice in KOKORO_VOICES:
                k.voice = voice
                for p in SYNTH_PHRASES:
                    pcm, sr = k.synth(p)
                    out.append(self.embed(resample(pcm, sr)))
                    del pcm
        except Exception as e:
            self.app.events.emit("voice_failed", part="voice id synthetic", error=f"{type(e).__name__}"[:100])
            out = []
        self._synthetic[m] = out
        return out

    def train(self, use_anyway: bool = False, session: enrol.Session | None = None) -> dict:
        """Build the template from the samples (the session's and those kept), calibrate, and save it when it's
        good or fair (weak: only with use_anyway). Typed or the page; never by voice."""
        with self.lock:
            if use_anyway and self.pending is not None:
                return self._use(self.pending, "Saved as you asked.")
            prob = self.bank_problem()
            if prob:
                return {"ok": False, "message": f"Can't build your voice print: {prob}."}
            t = self.template()
            if self.locked_why:
                return {"ok": False, "message": "Voice ID's key can't be read: forget and enrol again."}
            s = session or self.session
            if s is not None:
                raw = s.existing + s.samples
            else:
                if not t or t.get("model") != self.model():
                    return {"ok": False, "message": "Nothing to build from: enrol first (/voice enrol or the page)."}
                raw = [{"e": sid.from_b64(x["e"]), "s": sid.from_b64(x["s"]) if x.get("s") else None,
                        "cond": x.get("cond"), "day": x.get("day")} for x in t.get("samples") or []]  # fmt: skip
            conds = {x.get("cond") for x in raw}
            if len(raw) < sid.MIN_SAMPLES or any(c not in conds for c in sid.NEED_CONDS) or len(conds) < sid.MIN_CONDS:
                return {
                    "ok": False,
                    "message": f"Not enough to build yet ({len(raw)} samples from {len(conds)} conditions): it needs "
                    f"{sid.MIN_SAMPLES} at least, from 3 conditions, your normal voice and short requests among them.",
                }
            try:
                res = sid.calibrate(
                    raw,
                    self.bank(),
                    self.synthetic(),
                    str(self.s("strictness") or "normal"),
                    float(self.s("margin", 0.05)),
                    float(self.s("threshold", 0.0) or 0.0),
                )
            except ValueError as e:
                return {"ok": False, "message": str(e)}
            built = {
                **self._base(t or {}),
                "samples": [_pack(x) for x in raw],
                "centroid": sid.to_b64(res["centroid"]),
                "centroid_enrolled": sid.to_b64(res["centroid"]),
                "thresholds": res["thresholds"].to_dict(),
                "calibrated": res["calibrated"].to_dict(),
                "genuine": res["genuine"],
                "report": res["report"],
                "drift_stopped": False,
            }
            r = res["report"]
            self.last_result = _numbers_only(r)
            self.app.events.emit("voiceid_trained", grade=r["grade"], samples=r["n"], dropped=r["dropped"])
            if r["grade"] == "weak":
                self.pending = built
                return {
                    "ok": True,
                    "saved": False,
                    "report": _numbers_only(r),
                    "message": f"Built, but it's weak: {r['advice'] or 'add more samples.'} Use it anyway, or add "
                    "samples.",
                    "spoken": "Done, but it's weak. Add more samples on the page, or use it anyway there.",
                }
            return self._use(built, f"Built and saved: it's {r['grade']}.")

    def _use(self, built: dict, message: str) -> dict:
        self.previous = self.template()
        self.pending = None
        self._save(built)
        self.session = None if self.session is not None and self.session.state in ("done", "stopped") else self.session
        r = built["report"]
        return {
            "ok": True,
            "saved": True,
            "report": _numbers_only(r),
            "message": message + (f" {r['advice']}" if r.get("advice") else ""),
            "spoken": f"Done: it's {r['grade']}. Try it on the page: Test.",
        }

    def undo_build(self) -> dict:
        """Back to the template before the last build (within this run of Kurooto)."""
        with self.lock:
            if self.previous is None:
                return {"ok": False, "message": "Nothing to undo."}
            prev, self.previous = self.previous, None
            self._save(prev)
            return {"ok": True, "message": "Back to your previous voice print."}

    # ---------------------------------------------------------------------------------------------- test
    def test(self, who: str) -> dict:
        """One live try at the computer ("me" or "other"), or the synthetic voices' best score."""
        with self.lock:
            t = self.template()
            why = self.problem()
            if why:
                return {"ok": False, "message": {"locked": "Voice ID's key can't be read.",
                                                 "no voice print": "Enrol first: there's no voice print to test.",
                                                 }.get(why, f"Can't test: {why}.")}  # fmt: skip
            th = self.thresholds(t)
            if who == "synthetic":
                syn = self.synthetic()
                if not syn:
                    return {"ok": False, "message": "The synthetic check needs Kokoro set up (Features → Voice)."}
                c = sid.from_b64(t["centroid"])
                scores = [sid.dot(x, c) for x in syn]
                best = max(scores)
                passed = sum(1 for x in scores if x >= th.long.accept)
                self._record_test(t, "synthetic", passed == 0)
                return {"ok": True, "score": round(best, 3), "decision": sid.OWNER if passed else sid.GUEST,
                        "why": f"{passed} of {len(scores)} synthetic voices would pass", "thresholds": th.to_dict(),
                        "speech_s": None, "short": False}  # fmt: skip
            if who not in ("me", "other"):
                return {"ok": False, "message": "Test as me, other or synthetic."}
            if self.capturing:
                return {"ok": False, "message": f"Busy: {self.capturing}."}
            why = self.can_enrol()
            if why:
                return {"ok": False, "message": why}
            self.capturing = "testing your voice"
            self.v.portal.close("testing your voice")
            self.v._stop_listening("testing your voice")  # noqa: SLF001
        cut = None
        try:
            capture, close = self._mic_capture(TEST_S)
            try:
                cut = capture(TEST_S, threading.Event())
            finally:
                close()
            if cut is None:
                return {"ok": False, "message": "I didn't hear anything: try again."}
            chk = enrol.quality(cut, enrol.Condition("test", "", "", 1, 0.8), only_heard=True)
            if not chk.ok:
                return {"ok": False, "message": chk.reason}
            lo, hi = enrol.speech_span(cut)
            score = sid.dot(self.embed(bytes(cut.pcm[lo:hi])), sid.from_b64(t["centroid"]))
            v = sid.decide(score, th, cut.speech_s, None, **{**self.rules(), "carry": False})
        except Exception as e:
            return {"ok": False, "message": f"The test didn't work: {type(e).__name__}"}
        finally:
            if cut is not None:
                cut.release()
            self.capturing = ""
        good = v.decision == (sid.OWNER if who == "me" else sid.GUEST) or (who == "other" and v.decision == sid.UNSURE)
        self._record_test(self.template() or t, who, good)
        out = {
            "ok": True,
            "score": round(score, 3),
            "decision": v.decision,
            "why": v.why,
            "thresholds": th.to_dict(),
            "speech_s": round(v.speech_s, 1),
            "short": v.short,
            "pass": good,
        }
        self.last_test = {k: out[k] for k in ("score", "decision", "why", "speech_s", "short", "pass")} | {"as": who}
        return out

    def _record_test(self, t: dict, who: str, good: bool) -> None:
        lt = dict(t.get("last_test") or {})
        if lt.get("day") != today():
            lt = {"day": today(), "me_tries": 0, "me_passed": 0, "other_tries": 0, "other_passed": 0,
                  "synthetic_passed": None}  # fmt: skip
        if who == "synthetic":
            lt["synthetic_passed"] = bool(good)
        else:
            lt[f"{who}_tries"] = lt.get(f"{who}_tries", 0) + 1
            lt[f"{who}_passed"] = lt.get(f"{who}_passed", 0) + int(good)
        self._save({**t, "last_test": lt})

    # ------------------------------------------------------------------------------------- improve, forget
    def undo_adapt(self, which: str) -> dict:
        with self.lock:
            t = self.template()
            if not t or not t.get("report"):
                return {"ok": False, "message": "There's no voice print.", "count": 0}
            work = dict(t)
            a = sid.Adapter(self.bank(), str(self.s("strictness") or "normal"), float(self.s("margin", 0.05)),
                            float(self.s("threshold", 0.0) or 0.0))  # fmt: skip
            n = a.undo(work, "today" if which == "today" else "all", today())
            self._save(work)
            self.app.events.emit("voiceid_adapt_undone", which=which, count=n)
            left = len(work.get("adapted") or [])
            return {"ok": True, "message": f"Dropped {n} learned turn{'s' if n != 1 else ''}.", "count": left}

    def forget(self) -> str:
        """Delete the template and its key, end any session, clear what's in memory."""
        with self.lock:
            if self.session is not None:
                self.session.command("stop")
            self.session = None
            self.pending = self.previous = None
            self.last_test = None
            had = self.store.forget()
            self._tpl, self._loaded, self.locked_why = None, True, ""
            self.guest_turns.clear()
            self._face_last = None
            self._drop_claim()
            self._forced = None
            self.drop_model()
        learner = getattr(self.v, "learner", None)  # (0.8.13) the gate's learned turns hold Voice ID's scores too
        if learner is not None:
            learner.forget()
        self.app.events.emit("voiceid_forgotten")
        return (
            "Forgot your voice: the voice print and its key are deleted. Nothing of it was ever sent anywhere."
            if had
            else "There was no voice print to forget."
        )

    def callbacks(self) -> dict:
        return {"vid": self._button}

    def _button(self, ref: str, act: str) -> str:
        if act == "forget":
            return self.forget()[:190]
        if act in ("devuse", "devno"):  # (0.9.2) a microphone's own print: the one-time yes
            return self.device_answer(ref, "use" if act == "devuse" else "no")["message"][:190]
        return "Kept."

    def add_file(self, path: str) -> dict:
        ok, msg = self.v.parts.add_file(path)
        self.app.events.emit("voice_part_added", ok=ok)
        return {"ok": ok, "message": msg}


def _pack(x: dict) -> dict:
    out = {"e": sid.to_b64(x["e"]), "cond": x.get("cond") or "other", "day": x.get("day") or today()}
    if x.get("s"):
        out["s"] = sid.to_b64(x["s"])
    if x.get("window"):
        out["window"] = x["window"]
    return out


def _numbers_only(r: dict | None) -> dict | None:
    if not r:
        return None
    return {k: v for k, v in r.items() if not (isinstance(v, list) and len(v) > 30)}


def resample(pcm: bytes, sr: int) -> bytes:
    """16-bit mono at sr to 16 kHz (linear), for synthetic voices only."""
    if sr == 16000:
        return pcm
    import numpy as np

    x = np.frombuffer(pcm, dtype="<i2").astype("float32")
    n = int(len(x) * 16000 / sr)
    y = np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x)
    return y.astype("<i2").tobytes()

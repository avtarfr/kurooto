"""Voice ID's enrolment (0.8.10): the guided capture of the owner's voice, driver-agnostic.

The plan (CONDITIONS): six conditions, 19 prompts, 21 vectors in about five minutes. Each sample is checked before it
counts (quality(), then voice_checks() once it has its vector), and a rejected one says why, with its number. The
sound of a sample stays in memory: its vectors (the whole utterance's, and a 1.5 s crop's for short turns) are made,
then the buffer is zeroed and dropped before the next prompt. The transcript used for the phrase check is dropped too.

Session runs the plan with whatever drives it: `capture(timeout_s, cancel)` gives one cut-out stretch of speech (a
Cut, with its VAD flags) or None; `speak(text)` says a step (or does nothing); `stt(pcm)` writes it out (the phrase
check and the control words); `embed(pcm)` makes a vector. Voice drives it from the computer's own microphone
(voiceid.py); the tests drive it with fakes. Control words (stop, skip, repeat, pause, continue) are heard only inside
a session the owner started himself, and a control word is never a sample."""

from __future__ import annotations

import datetime as dt
import math
import random
import re
import threading
import time
from array import array
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from kurooto.modules.voice import speakerid as sid

RATE = 16000
FRAME = 512  # the listener's VAD frame (audio.FRAME)
FRAME_S = FRAME / RATE
CLIP = 32440  # 0.99 of full scale
TIMEOUT_S = 20  # waiting for speech after a prompt
IDLE_S = 600  # a paused session ends after this long


@dataclass(frozen=True)
class Condition:
    key: str
    label: str  # what the page and the voice say
    how: str  # the spoken instruction before its first prompt
    samples: int
    min_speech: float  # "heard anything": seconds of speech at least


CONDITIONS: tuple[Condition, ...] = (
    Condition("normal", "Normal voice, usual distance", "Normal voice, at your usual distance.", 5, 1.5),
    Condition("quiet", "Quiet voice", "Now a quiet voice, from the same place.", 3, 1.5),
    Condition("far", "Far from the microphone", "Now step back about two metres, or across the room.", 3, 1.5),
    Condition("noise", "With noise around", "Now put on some music, a fan or the TV, low.", 3, 1.5),
    Condition("calls", "Short requests", "Now short requests, the way you'd really ask me.", 4, 0.8),
    Condition("free", "Free speech", "Last one: talk for about ten seconds, about anything.", 1, 8.0),
)
BY_KEY = {c.key: c for c in CONDITIONS}
OTHER = Condition("other", "More samples", "Say each sentence the way you usually talk to me.", 3, 1.5)
TOTAL_VECTORS = 21  # five conditions' samples, plus three windows of the free speech

PHRASES = (
    "The kettle clicked off while the rain kept tapping on the window.",
    "Seven bright orange kites drifted over the quiet harbour.",
    "Could you move my reading slot to just after lunch?",
    "Thick fog rolled down the valley before the morning bus.",
    "A small brown dog chased the yellow ball across the park.",
    "Please bring the green folder and two sharp pencils tomorrow.",
    "The old clock in the hall struck nine with a heavy chime.",
    "We watched the storm clouds gather above the distant hills.",
    "Her bicycle bell rang twice as she turned the corner.",
    "Fresh bread and warm soup were waiting on the kitchen table.",
    "The museum opens late on Thursdays during the summer months.",
    "A gentle breeze carried the smell of jasmine through the yard.",
    "Remember to water the plants before you leave for the station.",
    "The children built a sandcastle with a moat and four towers.",
    "Quiet footsteps echoed down the long marble corridor.",
    "My cousin bought a blue scooter with a basket on the front.",
    "The train was delayed because of heavy snow near the bridge.",
    "Every Sunday the market fills with mangoes and ripe papayas.",
    "The lecture on prime numbers ran twenty minutes over time.",
    "A pair of herons stood perfectly still in the shallow pond.",
    "Turn left at the bakery, then walk past the blue gate.",
    "The violinist tuned her strings before the concert began.",
    "Six jars of honey sat in a neat row on the shelf.",
    "Lightning flashed and the whole street went dark for a moment.",
    "The recipe calls for a pinch of salt and a spoon of sugar.",
    "Our neighbour's parrot whistles the same tune every morning.",
    "Pack a warm jacket because the nights get very cold up there.",
    "The library returned my overdue books without a fine.",
    "Twelve boats sailed out of the bay at sunrise.",
    "The puzzle had a thousand pieces and most of them were sky.",
    "Watch out for the loose step near the top of the stairs.",
    "Steam rose slowly from the cups of strong black coffee.",
    "The gardener trimmed the hedge into the shape of a rabbit.",
    "A long queue formed outside the cinema for the new film.",
    "Bright paper lanterns swayed above the busy night market.",
    "The physics lab smells faintly of oil and warm metal.",
    "Five crows argued loudly on the telephone wire outside.",
    "The cricket match stopped twice because of light rain.",
    "Grandfather kept his maps rolled up inside a leather tube.",
    "The bus driver waved as we ran to catch the last ride home.",
)
CALL_PHRASES = (
    "{name}, what's on tomorrow?",
    "{name}, remind me at six.",
    "{name}, how long until my next class?",
    "{name}, what's due this week?",
    "{name}, set a timer for ten minutes.",
    "{name}, read me my notes from today.",
    "{name}, what time is it?",
    "{name}, add milk to my list.",
)
TOPICS = ("your morning", "a place you like", "what you did yesterday", "a meal you enjoy", "your plans for the week")
CONTROL = ("stop", "skip", "repeat", "pause", "continue")
STOP_WORDS = set(
    "the a an and or but of to in on at for with by from up over before after while just my your our their his her "
    "its is was were be been are you me we they it this that these those as into than then there here could would "
    "should can will please".split()
)


# --------------------------------------------------------------------------------------------- the sound
@dataclass
class Cut:
    """One stretch of speech the listener cut out: the sound (a bytearray, so it can be zeroed) and the VAD's verdict
    per FRAME (1 speech, 0 not)."""

    pcm: bytearray
    flags: bytes = b""

    @property
    def speech_s(self) -> float:
        return sum(1 for f in self.flags if f) * FRAME_S if self.flags else len(self.pcm) / (2 * RATE)

    def release(self) -> None:
        """Zero the sound and let it go (before the next prompt)."""
        self.pcm[:] = bytes(len(self.pcm))
        self.pcm = bytearray()


def _samples(pcm: bytes | bytearray) -> array:
    a = array("h")
    a.frombytes(bytes(pcm[: len(pcm) - len(pcm) % 2]))
    return a


def _db(rms: float) -> float:
    return 20 * math.log10(max(rms, 1e-7))


def stats(cut: Cut) -> dict:
    """Speech level, noise floor (the pre-roll and the gaps), clipping and speech length, in numbers only."""
    a = _samples(cut.pcm)
    n = len(a)
    flags = cut.flags or bytes([1]) * max(1, math.ceil(n / FRAME))
    sp = sq = 0.0
    ns_sq, ns_n, sp_n = 0.0, 0, 0
    frame_rms = []
    for i, f in enumerate(flags):
        chunk = a[i * FRAME : (i + 1) * FRAME]
        if not chunk:
            break
        e = math.fsum(x * x for x in chunk)
        frame_rms.append(math.sqrt(e / len(chunk)) / 32768)
        if f:
            sq += e
            sp_n += len(chunk)
        else:
            ns_sq += e
            ns_n += len(chunk)
    sp = math.sqrt(sq / sp_n) / 32768 if sp_n else 0.0
    if ns_n:
        noise = math.sqrt(ns_sq / ns_n) / 32768
    else:  # no gaps: the quietest tenth of the frames
        q = sorted(frame_rms)[: max(1, len(frame_rms) // 10)]
        noise = math.fsum(q) / len(q) if q else 0.0
    clipped = sum(1 for x in a if x >= CLIP or x <= -CLIP) / n if n else 0.0
    return {
        "speech_s": round(cut.speech_s, 2),
        "level_db": round(_db(sp), 1),
        "noise_db": round(_db(noise), 1),
        "snr_db": round(_db(sp) - _db(noise), 1),
        "clipped": clipped,
    }


@dataclass
class Check:
    ok: bool
    reason: str = ""
    numbers: dict = field(default_factory=dict)


def content_words(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z']+", (text or "").lower()) if len(w) >= 3 and w not in STOP_WORDS]


@dataclass
class Ref:
    """Condition 1's medians: the reference the other conditions are checked against."""

    level_db: float | None = None
    noise_db: float | None = None


def quality(
    cut: Cut,
    cond: Condition,
    ref: Ref | None = None,
    transcript: str | None = None,
    prompt: str | None = None,
    own_words: bool = False,
    only_heard: bool = False,
) -> Check:
    """The sound's checks, in order; the first that fails is the reason. only_heard: a test's try ("heard anything")."""
    n = stats(cut)
    s = n["speech_s"]
    if s < cond.min_speech:
        what = "talk for about ten seconds" if cond.key == "free" else "say the whole sentence"
        return Check(False, f"Too short: I heard {s:.1f} s of speech; {what}.", n)
    if only_heard:
        return Check(True, "", n)
    if n["clipped"] >= 0.001:
        return Check(False, "Too loud: it clipped. Move back a little or speak softer.", n)
    if n["level_db"] < -45:
        return Check(False, f"Too quiet ({n['level_db']:.0f} dB): come closer or speak up.", n)
    need = 4 if cond.key == "noise" else 8
    if n["snr_db"] < need:
        return Check(False, f"Too much noise around you (speech only {n['snr_db']:.0f} dB above it).", n)
    if transcript is not None and prompt and not own_words and cond.key not in ("free",):
        want = content_words(prompt.replace("{name}", ""))
        heard = set(content_words(transcript))
        if want and sum(1 for w in want if w in heard) / len(want) < 0.5:
            return Check(False, "I didn't hear the sentence (heard something else): try again.", n)
    ref = ref or Ref()
    if cond.key in ("quiet", "far") and ref.level_db is not None and n["level_db"] > ref.level_db - 4:
        if cond.key == "quiet":
            return Check(False, "That sounded as loud as your normal voice: say it more quietly.", n)
        return Check(False, "That sounded as close as before: step back about two metres.", n)
    if cond.key == "noise" and ref.noise_db is not None and n["noise_db"] < ref.noise_db + 6:
        return Check(False, "I couldn't hear any background noise: put on some music, a fan or the TV, low.", n)
    if cond.key == "calls" and s > 3.5:
        return Check(False, "That was long for a quick request: keep it short, the way you'd ask me.", n)
    return Check(True, "", n)


def voice_checks(e: Sequence[float], accepted: Sequence[Sequence[float]]) -> Check:
    """Once the sample has its vector: one voice, his (from the 4th sample on), and not a copy of an earlier one."""
    for prev in accepted:
        if sid.dot(e, prev) >= 0.98:
            return Check(False, "That's identical to an earlier sample (a recording?); say it live.")
    if len(accepted) >= 3:
        c = sid.normalize(sid.mean(accepted))
        if sid.dot(e, c) < 0.30:
            return Check(False, "That doesn't sound like your other samples. Was it someone else? Try again.")
    return Check(True)


# ---------------------------------------------------------------------------------------------- crops
def speech_span(cut: Cut) -> tuple[int, int]:
    """Byte offsets of the first and last speech frame (the whole sound without flags)."""
    if not cut.flags or not any(cut.flags):
        return 0, len(cut.pcm)
    first = next(i for i, f in enumerate(cut.flags) if f)
    last = len(cut.flags) - 1 - next(i for i, f in enumerate(reversed(cut.flags)) if f)
    return first * FRAME * 2, min(len(cut.pcm), (last + 1) * FRAME * 2)


def crop(pcm: bytes | bytearray, lo: int, hi: int, seconds: float) -> bytes:
    """`seconds` of sound from the middle of [lo, hi) (all of it when shorter)."""
    want = int(seconds * RATE) * 2
    if hi - lo <= want:
        return bytes(pcm[lo:hi])
    mid = (lo + hi) // 2
    a = max(lo, mid - want // 2)
    a -= a % 2
    return bytes(pcm[a : a + want])


def windows(cut: Cut, seconds: float = 3.0, count: int = 3) -> list[bytes]:
    """`count` windows of `seconds` across the speech (free speech gives three vectors)."""
    lo, hi = speech_span(cut)
    want = int(seconds * RATE) * 2
    if hi - lo < want * count:
        step = max(2, ((hi - lo) - want) // max(1, count - 1))
    else:
        step = ((hi - lo) - want) // max(1, count - 1)
    out = []
    for i in range(count):
        a = lo + i * step
        a -= a % 2
        out.append(bytes(cut.pcm[a : min(hi, a + want)]))
    return out


def control_word(text: str) -> str:
    """A control word said on its own (at most three words): stop, skip, repeat, pause, continue; else ""."""
    w = re.findall(r"[a-z]+", (text or "").lower())
    if not w or len(w) > 3:
        return ""
    for c in CONTROL:
        if c in w:
            return c
    if "again" in w:
        return "repeat"
    return ""


# -------------------------------------------------------------------------------------------- the session
NUMBERS = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen \
seventeen eighteen nineteen twenty twenty-one".split()


def spoken_number(n: int) -> str:
    return NUMBERS[n] if 0 <= n < len(NUMBERS) else str(n)


class Session:
    """The enrolment's state machine. States: ready, listening (waiting for a sample), checking, paused, done (the
    plan is through: build next), stopped (ended without building), kept (saved for later)."""

    def __init__(
        self,
        *,
        capture: Callable[[float, threading.Event], Cut | None],
        embed: Callable[[bytes], Sequence[float]],
        stt: Callable[[bytes], str] | None = None,
        speak: Callable[[str], None] = lambda _t: None,
        publish: Callable[..., None] = lambda _kind, **_f: None,
        name: str = "Kurooto",
        own_words: bool = False,
        conds: Sequence[str] | None = None,
        existing: Sequence[dict] = (),
        rng: random.Random | None = None,
        clock: Callable[[], float] = time.monotonic,
        timeout_s: float = TIMEOUT_S,
        idle_s: float = IDLE_S,
    ):
        self.capture, self.embed, self.stt, self.speak, self.publish = capture, embed, stt, speak, publish
        self.name = name or "Kurooto"
        self.own_words = own_words
        self.rng = rng or random.Random()  # noqa: S311 (which sentence to say, nothing secret)
        self.clock = clock
        self.timeout_s, self.idle_s = timeout_s, idle_s
        keys = [c for c in (conds or [c.key for c in CONDITIONS]) if c in BY_KEY or c == "other"]
        self.plan: list[Condition] = [BY_KEY.get(k, OTHER) for k in keys]
        self.existing = [dict(s) for s in existing]  # samples kept from before (add samples, resume)
        self.samples: list[dict] = []  # accepted now: {e, s, cond, day}
        self.attempts: list[dict] = []  # {n, cond, ok, reason, numbers}
        self.skipped: list[str] = []
        self.ref = Ref()
        self._levels: list[float] = []
        self._noises: list[float] = []
        self.state = "ready"
        self.cond_i = 0
        self.prompt = ""
        self.message = ""
        self.cancel = threading.Event()
        self._cmd: str = ""
        self._wake = threading.Event()
        self._used: set[str] = set()
        self.timeouts = 0
        self.held = 0  # buffers released (zeroed), for the tests

    # -------------------------------------------------------------------------------------------- outside
    def command(self, what: str) -> None:
        """From the page or a command: pause, continue, skip, stop, keep."""
        self._cmd = what
        if what in ("stop", "keep", "pause", "skip"):
            self.cancel.set()
        self._wake.set()

    @property
    def cond(self) -> Condition | None:
        return self.plan[self.cond_i] if 0 <= self.cond_i < len(self.plan) else None

    def done_in(self, key: str) -> int:
        return sum(1 for s in self.samples + self.existing if s.get("cond") == key and not s.get("window"))

    def vectors(self) -> int:
        return len(self.samples) + len(self.existing)

    def need(self) -> int:
        return sum(c.samples + (2 if c.key == "free" else 0) for c in self.plan)

    def enough(self) -> tuple[bool, str]:
        """12 vectors at least, from 3 conditions or more, normal and calls among them."""
        allv = self.samples + self.existing
        conds = {s.get("cond") for s in allv}
        if len(allv) < sid.MIN_SAMPLES:
            return False, f"{len(allv)} of the {sid.MIN_SAMPLES} samples it needs at least"
        missing = [c for c in sid.NEED_CONDS if c not in conds]
        if missing:
            return False, "it needs samples of " + " and ".join(sid.CONDITION_WORDS[c] for c in missing)
        if len(conds) < sid.MIN_CONDS:
            return False, f"it needs samples from {sid.MIN_CONDS} conditions at least"
        return True, ""

    def view(self) -> dict:
        """For the page and the live stream: counts, the prompt and the attempts (never sound, vectors or words)."""
        c = self.cond
        return {
            "state": self.state,
            "cond": c.key if c else None,
            "cond_label": c.label if c else "",
            "prompt": self.prompt,
            "message": self.message,
            "done": self.vectors(),
            "need": self.need() + len(self.existing),
            "by_cond": {k.key: self.done_in(k.key) for k in self.plan},
            "plan": [{"cond": k.key, "label": k.label, "samples": k.samples} for k in self.plan],
            "skipped": list(self.skipped),
            "attempts": self.attempts[-12:],
        }

    def _tell(self) -> None:
        v = self.view()
        self.publish("voiceid_session", **{k: v[k] for k in ("state", "cond", "prompt", "done", "need")})

    # ------------------------------------------------------------------------------------------- prompts
    def _phrase(self, c: Condition) -> str:
        if c.key == "calls":
            pool = [p.format(name=self.name) for p in CALL_PHRASES]
        elif c.key == "free":
            return f"Talk for about ten seconds about {self.rng.choice(TOPICS)}."
        else:
            pool = list(PHRASES)
        left = [p for p in pool if p not in self._used] or pool
        p = self.rng.choice(left)
        self._used.add(p)
        if self.own_words and c.key not in ("calls", "free"):
            return f"Say a sentence or two about {self.rng.choice(TOPICS)}, in your own words."
        return p

    # ----------------------------------------------------------------------------------------------- run
    def run(self) -> str:
        """Walk the plan until it's done, stopped, kept or paused for too long. Returns the final state."""
        self.speak(
            "Voice enrolment. I'll ask for about twenty short sentences in a few different ways; it takes about five "
            "minutes. Say 'stop' to stop, 'skip' to skip a step, 'repeat' to hear it again."
            if len(self.plan) > 1
            else "More samples. Say 'stop' to stop."
        )
        while self.cond is not None:
            c = self.cond
            if self.done_in(c.key) >= c.samples:
                self.cond_i += 1
                continue
            first = self.done_in(c.key) == 0
            self.prompt = self._phrase(c)
            said = self.prompt if c.key == "free" or self.own_words else f"Say: {self.prompt}"
            self.speak(f"{c.how} {said}" if first else said)
            if not self._take(c):
                break
        if self.state in ("stopped", "kept"):
            self._tell()
            return self.state
        self.state, self.prompt = "done", ""
        self._tell()
        total = self.vectors()
        self.speak(f"That's all {spoken_number(total)}." if total <= 21 else f"That's {total} samples.")
        return self.state

    def _take(self, c: Condition) -> bool:
        """One prompt until it's answered with an accepted sample, skipped or repeated. False: the session ends."""
        while True:
            if not self._control():
                return False
            if self._cmd == "skip":
                self._cmd = ""
                self._skip(c)
                return True
            self.state, self.message = "listening", ""
            self._tell()
            self.cancel.clear()
            cut = self.capture(self.timeout_s, self.cancel)
            if cut is None:
                if self._cmd:
                    continue
                self.timeouts += 1
                if self.timeouts >= 2:
                    self.state, self.message = "paused", "Paused after two prompts with nothing heard."
                    self._tell()
                    self.speak("I'm pausing. Continue on the page, or send /voice enrol.")
                    if not self._wait():
                        return False
                    self.timeouts = 0
                    self.speak(self.prompt if self.cond and self.cond.key == "free" else f"Say: {self.prompt}")
                continue
            self.timeouts = 0
            try:
                verdict = self._sample(c, cut)
            finally:
                cut.release()
                self.held += 1
                del cut
            if verdict == "control":
                continue
            if verdict == "repeat":
                self.speak(self.prompt if c.key == "free" else f"Say: {self.prompt}")
                continue
            if verdict == "ok":
                return True

    def _control(self) -> bool:
        cmd = self._cmd
        if cmd in ("stop", "keep"):
            self.state = "kept" if cmd == "keep" else "stopped"
            return False
        if cmd == "pause":
            self._cmd = ""
            self.state = "paused"
            self._tell()
            return self._wait()
        return True

    def _wait(self) -> bool:
        """Paused: until continue (True) or stop, keep, or idle_s (False)."""
        end = self.clock() + self.idle_s
        while self.clock() < end:
            self._wake.wait(0.2)
            self._wake.clear()
            cmd = self._cmd
            if cmd in ("continue", "skip"):
                if cmd == "continue":
                    self._cmd = ""
                self.state = "listening"
                return True
            if cmd in ("stop", "keep"):
                self.state = "kept" if cmd == "keep" else "stopped"
                return False
        self.state = "stopped"
        self.message = "Ended after ten minutes paused."
        return False

    def _skip(self, c: Condition) -> None:
        if c.key == "normal":
            self.message = "Your normal voice can't be skipped: it's the reference for the rest."
            self.speak(self.message)
            return
        self.skipped.append(c.key)
        self.cond_i += 1

    def _sample(self, c: Condition, cut: Cut) -> str:
        """Check one sample; on a pass, make its vectors. "ok", "rejected", "control" or "repeat"."""
        self.state = "checking"
        text = ""
        if self.stt is not None:
            try:
                text = self.stt(bytes(cut.pcm)) or ""
            except Exception:
                text = ""
        word = control_word(text)
        if word:
            text = ""
            if word == "repeat":
                return "repeat"
            if word in ("pause", "stop", "skip"):
                self.command(word)
            return "control"
        chk = quality(
            cut, c, self.ref, transcript=text if self.stt is not None else None, prompt=self.prompt,
            own_words=self.own_words,
        )  # fmt: skip
        text = ""
        if chk.ok:
            day = dt.date.today().isoformat()
            lo, hi = speech_span(cut)
            pieces = windows(cut) if c.key == "free" else [bytes(cut.pcm[lo:hi])]
            vecs = []
            for i, p in enumerate(pieces):
                e = sid.normalize(self.embed(p))
                vc = voice_checks(e, [s["e"] for s in self.samples + self.existing] + [v["e"] for v in vecs])
                if not vc.ok:
                    chk = Check(False, vc.reason, chk.numbers)
                    break
                s_crop = crop(p, 0, len(p), 1.5)
                vecs.append({"e": e, "s": sid.normalize(self.embed(s_crop)), "cond": c.key, "day": day,
                             **({"window": i} if i else {})})  # fmt: skip
            if chk.ok:
                self.samples += vecs
        n = len(self.attempts) + 1
        nums = {k: chk.numbers.get(k) for k in ("level_db", "snr_db", "speech_s") if k in chk.numbers}
        self.attempts.append({"n": n, "cond": c.key, "ok": chk.ok, "reason": chk.reason, "numbers": nums})
        self.publish("voiceid_attempt", cond=c.key, ok=chk.ok, reason=chk.reason, **nums)
        if not chk.ok:
            self.message = f"#{n}: {chk.reason}"
            self.speak(f"{chk.reason.split(':')[0].split('.')[0]}. Once more.")
            return "rejected"
        if c.key == "normal":
            self._levels.append(chk.numbers.get("level_db", -30.0))
            self._noises.append(chk.numbers.get("noise_db", -60.0))
            self.ref = Ref(sid.median(self._levels), sid.median(self._noises))
        left = c.samples - self.done_in(c.key)
        self.message = f"#{n}: got it."
        self.speak(f"Got it. {spoken_number(left).capitalize()} more." if left > 0 else "Got it.")
        return "ok"

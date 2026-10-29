"""Barge-in (voice.listen.barge_in): you can cut Kurooto off while it speaks.

Before this, the listener dropped every sound while Kurooto spoke (Speaker.holding()), so it wouldn't hear itself and
take its own words for a turn; only /voice stop could end a long answer. Now, while it speaks, the microphone's sound
comes here instead of being dropped. It is cut into stretches of speech as usual, and a stretch counts as you barging
in only when one of two checks says it isn't Kurooto's own voice coming back through the room:

- **The voice** (Voice ID on and enrolled): at least MIN_SPEECH_S of speech whose voice print scores in your accept
  band (the same thresholds as a turn) and is closer to you than to Kurooto's own voice by SELF_MARGIN. Kurooto's own
  voice print is made once, in memory, from a phrase its speech engine says silently (never played or saved).
- **The loudness, then the words** (always; the only check without Voice ID): the stretch is clearly louder than the
  echo expected from what's being played just then (the playback's own level, tracked here, times the echo's
  measured share of it), and its words, written out here, aren't just what Kurooto is saying (a told-off phrase is
  always taken).

When a check passes, Kurooto goes quiet at once (Speaker.hold(): this computer's player and an add-on output's
stop event for the piece playing); the rest of the stretch is still taken, and the whole of it then goes to
Voice.barge_turn(): told off -> stop (the told-off path), a question or a request -> stop, and a new turn in the same
conversation, anything else ("mm", a cough, no face) -> Speaker.release(): it says the cut piece again from its start
and goes on (0.8.17; the conversation stays open for voice.listen.follow_s).

Played elsewhere (0.9.2, a fix): when the answer plays on an add-on's output (a phone that also hears for Kurooto),
its echo comes back later (the sound goes over the network, then the microphone's sound back), so the expected echo
looks back REMOTE_LAG_S instead of ECHO_LAG_S. And when the echo is hardly heard at all (the phone's or the system's
own echo cancelling: under QUIET_SHARE of the frames while it plays held speech, over QUIET_MIN of them), the
loudness check has nothing to learn from, so a third check takes it: at least MIN_SPEECH_S of speech whose written-out
words aren't mostly what Kurooto is saying ("quiet echo").

Echo cancelled (0.9.3, voice.listen.aec): while the listener's echo canceller is bringing the echo down (aec.py's
cancelling()), what's heard here is the cleaned sound, so the loudness check expects the residual, not the raw echo:
the residual's share of the playback's level is learned from every frame heard while it plays outside a stretch (not
only speech frames: the residual is mostly too quiet for the VAD), its RES_PCT percentile (the residual comes in
bursts where the filter lags), and a stretch is loud at RES_X times that (about 6 dB). The raw-echo share is kept
apart and used again when cancelling isn't working (a new piece's first moments, the library missing, the switch off).

Sound stays in memory, as everywhere in Voice: the stretch being cut and the pre-roll; levels of what's played are
numbers only. Nothing here is logged but how it was noticed and what it led to (never words)."""

from __future__ import annotations

import array
import collections
import math
import queue
import threading
import time
from typing import TYPE_CHECKING

from kurooto.modules.voice import speakerid as sid

if TYPE_CHECKING:
    from kurooto.modules.voice import Voice

RATE = 16000
FRAME = 512  # the listener's frame (32 ms at 16 kHz)
FRAME_S = FRAME / RATE
START, STOP = 0.5, 0.35  # the listener's own speech thresholds
END_MS = 700  # quiet that ends a stretch (as the listener)
PRE_MS = 320
MAX_S = 15

MIN_SPEECH_S = 0.6  # the voice check needs at least this much speech
RECHECK_S = 0.5  # a stretch still going is checked again after this much more speech
SELF_MARGIN = 0.10  # closer to the owner's voice print than to Kurooto's own by at least this
ECHO_LAG_S = 0.8  # the echo may come this late (a phone playing it, the room): the window of expected level
ECHO_AHEAD_S = 0.05
REMOTE_LAG_S = 2.0  # (0.9.2) played on an add-on's output (a phone): its echo may come back this late
QUIET_MIN = 90  # (0.9.2) frames heard while it plays (~3 s) before "the echo is quiet" can be said
QUIET_SHARE = 0.25  # and under this share of them held speech: echo cancelling at work
EXPECT_MIN = 0.01  # playback quieter than this (RMS, 0..1) doesn't teach the echo's share
GAIN_FRAMES = 125  # the echo's share: the median over this many speech frames heard while it plays (~4 s)
GAIN_MIN = 15  # and needs this many before the loudness check can say anything (~0.5 s)
LOUD_X = 2.5  # "clearly louder": this many times the expected echo (about 8 dB)
FLOOR = 0.01  # and above this level in any case
LOUD_MIN_S = 0.3  # at least this much loud speech
LOUD_SHARE = 0.5  # and at least this share of the stretch's speech
RES_PCT = 0.9  # (0.9.3, cancelled) the residual's expected share: this percentile of the frames heard while it plays
RES_X = 2.0  # and a stretch is loud at this many times it
ECHO_WORDS = 0.6  # written-out words this much made of what Kurooto is saying are its own echo
OWN_PHRASE = "This is how I sound when I talk, so I can tell my own voice from yours when we both speak."

VOICE, LOUD, QUIET = "voice", "loud", "quiet echo"
OWN_WHY = "your voice, over its own"


def rms(pcm: bytes) -> float:
    """The level of 16-bit mono sound, 0..1."""
    try:
        import numpy as np

        x = np.frombuffer(pcm[: len(pcm) - len(pcm) % 2], dtype="<i2").astype("float32")
        return float(np.sqrt(np.mean(x * x)) / 32768.0) if len(x) else 0.0
    except ImportError:
        a = array.array("h")
        a.frombytes(pcm[: len(pcm) - len(pcm) % 2])
        return math.sqrt(sum(x * x for x in a) / max(1, len(a))) / 32768.0


def levels(pcm: bytes, sr: int, step_s: float = FRAME_S) -> list[float]:
    """The level of each step_s of what's played (numbers only: the echo's expected loudness)."""
    n = max(2, int(sr * step_s) * 2)
    return [rms(pcm[i : i + n]) for i in range(0, len(pcm), n)]


class Barge:
    def __init__(self, v: Voice, clock=time.monotonic):
        self.v, self.clock = v, clock
        self.lock = threading.Lock()
        self.sync = False  # tests: checks run on the caller's thread
        self.count = 0  # barge-ins since start (a count only)
        self._pieces: collections.deque[tuple[float, float, list[float], float]] = collections.deque(maxlen=64)
        self._while_played: collections.deque[bool] = collections.deque(maxlen=300)  # (0.9.2) speech heard or not
        self._quiet_sid = -1  # (0.9.2) the stretch that began while the echo was quiet
        self._ratios: collections.deque[float] = collections.deque(maxlen=GAIN_FRAMES)
        self._res: collections.deque[float] = collections.deque(maxlen=GAIN_FRAMES)  # (0.9.3) the residual's share
        self._said: collections.deque[str] = collections.deque(maxlen=12)  # what it's saying, for the echo words
        self._own: dict[tuple, list[float]] = {}  # Kurooto's own voice print, per engine/voice/model; memory only
        self._jobs: queue.Queue = queue.Queue(maxsize=4)
        self._thread: threading.Thread | None = None
        self._sid = 0
        self._confirmed: dict | None = None  # {"sid", "how", "score"}: the stretch that barged in
        self._pending = 0  # checks in flight for the current stretch
        self._reset_stretch()

    # ------------------------------------------------------------------------------------------- switches
    def on(self) -> bool:
        return bool(self.v.setting("listen.barge_in"))

    def listening(self) -> bool:
        li = self.v.listener
        return self.on() and li is not None and li.running()

    def reset(self) -> None:
        """Listening stopped: the stretch and the echo's share are dropped."""
        with self.lock:
            self._reset_stretch()
            self._ratios.clear()
            self._res.clear()
            self._while_played.clear()
            self._confirmed = None

    def _reset_stretch(self) -> None:
        self._buf: bytearray | None = None
        self._flags = bytearray()
        self._loud = 0
        self._quiet = 0
        self._checked_s = 0.0
        self._pre: collections.deque[bytes] = collections.deque(maxlen=max(1, int(PRE_MS / (FRAME_S * 1000))))

    # ----------------------------------------------------------------------------------- what's being played
    def speaking(self, pieces: list[str]) -> None:
        """Speaker: it's about to say these pieces. Their words are kept (memory only) for the echo words check, and
        its own voice print is made now if the voice check will want it."""
        if not self.listening():
            return
        with self.lock:
            self._said.extend(p for p in pieces if p)
        if self._voice_ready(own=False) is not None and self._own_key() not in self._own:
            self._submit(("own",))

    def played(self, pcm: bytes, sr: int, remote: bool = False) -> None:
        """Speaker: this piece starts playing now (here, or on another device: remote, its echo comes later)."""
        if not pcm or not sr or not self.listening():
            return
        lv = levels(pcm, sr)
        with self.lock:
            self._pieces.append((self.clock(), FRAME_S, lv, REMOTE_LAG_S if remote else ECHO_LAG_S))

    def expected(self, now: float) -> float:
        """The loudest the echo of what's played could be now: the playback's level over the last ECHO_LAG_S."""
        best = 0.0
        hi = now + ECHO_AHEAD_S
        for start, step, lv, lag in list(self._pieces):
            lo = now - lag
            end = start + step * len(lv)
            if end < lo or start > hi:
                continue
            i0 = max(0, int((lo - start) / step))
            i1 = min(len(lv), int((hi - start) / step) + 1)
            if i1 > i0:
                best = max(best, max(lv[i0:i1]))
        return best

    def echo_quiet(self) -> bool:
        """(0.9.2) While it plays, the microphone has hardly heard speech (echo cancelling at work)."""
        n = len(self._while_played)
        return n >= QUIET_MIN and sum(self._while_played) < QUIET_SHARE * n

    def gain(self, cancelled: bool = False) -> float | None:
        """The echo's share of the playback's level, as heard here (the median: robust to you talking over it);
        cancelled (0.9.3): the residual's, its RES_PCT percentile."""
        if cancelled:
            if len(self._res) < GAIN_MIN:
                return None
            xs = sorted(self._res)
            return xs[min(len(xs) - 1, int(RES_PCT * len(xs)))]
        if len(self._ratios) < GAIN_MIN:
            return None
        xs = sorted(self._ratios)
        return xs[len(xs) // 2]

    def cancelled(self) -> bool:
        """(0.9.3) The listener's echo canceller is bringing the echo down now: what's heard here is cleaned."""
        a = getattr(self.v, "aec", None)
        try:
            return a is not None and bool(a.cancelling())
        except Exception:
            return False

    # ------------------------------------------------------------------------------------------ the listener
    def wants(self) -> bool:
        """Should the listener hand this frame here? While Kurooto speaks, and while a stretch that barged in (or is
        being checked) goes on after it stopped. Off: never (the listener drops sound while it speaks, as before)."""
        if not self.on():
            return False
        with self.lock:
            busy = self._buf is not None and (self._pending > 0 or self._is_confirmed())
            if self.v.speaker.holding() or busy:
                return True
            if self._buf is not None:  # it stopped by itself mid-stretch: the stretch (echo in it) is dropped
                self._reset_stretch()
            return False

    def _is_confirmed(self) -> bool:
        return self._confirmed is not None and self._confirmed["sid"] == self._sid

    def feed(self, frame: bytes, p: float) -> bool:
        """One frame and the VAD's speech probability. True when a stretch ended (the listener resets its VAD)."""
        now = self.clock()
        level = rms(frame)
        action = None
        ended = False
        cancelled = self.cancelled()
        with self.lock:
            expect = self.expected(now)
            confirmed = self._is_confirmed()
            if cancelled:  # (0.9.3) the residual's share: every frame while it plays, outside a stretch
                if expect >= EXPECT_MIN and self._buf is None and not confirmed:
                    self._res.append(level / expect)
            elif expect >= EXPECT_MIN and p >= START and not confirmed:  # speech heard while it plays: its echo
                self._ratios.append(level / expect)
            if expect >= EXPECT_MIN:  # (0.9.2) how much speech the microphone hears while it plays (its echo, mostly)
                if p >= START and self._buf is None:  # this frame starts a stretch: was the echo quiet before it?
                    self._quiet_sid = self._sid + 1 if self.echo_quiet() else -1
                self._while_played.append(p >= START)
            g = self.gain(cancelled)
            loud = g is not None and level > max(FLOOR, (RES_X if cancelled else LOUD_X) * g * expect)
            if self._buf is None:
                if p >= START:
                    self._sid += 1
                    self._flags = bytearray(len(self._pre)) + b"\x01"
                    self._buf = bytearray(b"".join(self._pre)) + frame
                    self._pre.clear()
                    self._loud = int(loud)
                    self._quiet = 0
                    self._checked_s = 0.0
                    self._pending = 0
                else:
                    self._pre.append(frame)
                return False
            self._buf += frame
            speech = p >= START
            self._flags.append(1 if speech else 0)
            self._loud += int(speech and loud)
            self._quiet = self._quiet + 1 if p < STOP else 0
            speech_s = sum(self._flags) * FRAME_S
            if self._quiet * FRAME_S * 1000 >= END_MS or len(self._buf) >= MAX_S * RATE * 2:
                action, ended = self._end(speech_s), True
            elif not confirmed and not self._pending:
                due = not self._checked_s or speech_s - self._checked_s >= RECHECK_S
                if due and (speech_s >= MIN_SPEECH_S or self._loud * FRAME_S >= LOUD_MIN_S):
                    self._checked_s = speech_s
                    self._pending += 1
                    action = ("job", ("check", self._sid, bytes(self._buf), bytes(self._flags), speech_s,
                                      self._loud, False))  # fmt: skip
        if action is not None:  # never with the lock held: a check may stop the speaker, a hand-on queues
            if action[0] == "hand":
                self._hand_on(*action[1:])
            else:
                self._submit(action[1])
        return ended

    def _end(self, speech_s: float) -> tuple | None:
        """(lock held) A stretch ended: handed on when it barged in, else checked once more whole, else dropped."""
        pcm, flags, sid_, loud = bytes(self._buf or b""), bytes(self._flags), self._sid, self._loud
        confirmed, pending = self._is_confirmed(), self._pending
        self._reset_stretch()
        if confirmed:
            how, self._confirmed = dict(self._confirmed or {}), None
            return ("hand", pcm, flags, how)
        if pending or speech_s >= LOUD_MIN_S:
            return ("job", ("check", sid_, pcm, flags, speech_s, loud, True))
        return None

    # --------------------------------------------------------------------------------------------- checking
    def _submit(self, job: tuple) -> None:
        if self.sync:
            self._run(job)
            return
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._loop, name="voice-barge", daemon=True)
            self._thread.start()
        try:
            self._jobs.put_nowait(job)
        except queue.Full:  # behind: this check is skipped (the next one, or the whole stretch, is checked)
            self._settled(job)

    def _loop(self) -> None:
        while True:
            self._run(self._jobs.get())

    def _settled(self, job: tuple) -> None:
        """A check of the stretch still going is no longer in flight."""
        if job[0] == "check" and not job[6]:
            with self.lock:
                if job[1] == self._sid:
                    self._pending = max(0, self._pending - 1)

    def _run(self, job: tuple) -> None:
        """On the checking thread (or the caller's, sync): its own voice print, or one check of a stretch."""
        try:
            if job[0] == "own":
                self.own_print()
                return
            _, sid_, pcm, flags, speech_s, loud, final = job
            with self.lock:
                got = dict(self._confirmed) if self._confirmed and self._confirmed["sid"] == sid_ else None
            stop = False
            if got is None:
                with self.lock:
                    quiet = self._quiet_sid == sid_
                how, score = self.check(pcm, speech_s, loud, quiet=quiet)
                if how:
                    got, stop = {"sid": sid_, "how": how, "score": score}, True
            with self.lock:
                if got is not None:
                    self._confirmed = None if final else got
            if stop:
                self.v.speaker.hold()  # quiet at once; Voice.barge_turn() then stops it or carries on
                self.v.publish("voice_state", state="hearing", portal=self.v.portal.open, listening=True,
                               why="barged in")  # fmt: skip
            if final and got is not None:
                self._hand_on(pcm, flags, got)
        except Exception as e:
            self.v.app.events.emit("voice_failed", part="barge-in", error=f"{type(e).__name__}"[:100])
        finally:
            self._settled(job)

    def check(self, pcm: bytes, speech_s: float, loud: int, quiet: bool = False) -> tuple[str, float | None]:
        """("voice", score) / ("loud", None) / ("quiet echo", None) when this is someone talking over Kurooto, ("",
        None) when it may be its own voice coming back. quiet: the stretch began while its echo was hardly heard."""
        ready = self._voice_ready()
        if ready is not None and speech_s >= MIN_SPEECH_S:
            centroid, th, own = ready
            e = self.v.voiceid.embed(pcm)
            owner, itself = sid.dot(e, centroid), sid.dot(e, own)
            if owner >= th.pick(speech_s).accept and owner - itself >= SELF_MARGIN:
                return VOICE, owner
        if loud * FRAME_S >= LOUD_MIN_S and loud >= LOUD_SHARE * max(1.0, speech_s / FRAME_S):
            if self.words_ok(self.v._write_out(pcm)):
                return LOUD, None
        elif quiet and speech_s >= MIN_SPEECH_S and self.words_ok(self.v._write_out(pcm)):
            return QUIET, None
        return "", None

    def words_ok(self, text: str) -> bool:
        """Words written out from a loud stretch: real words, and not mostly what Kurooto is saying."""
        from kurooto.modules.voice.gate import made_up, told_off, words

        w = words(text).split()
        if not w or made_up(text):
            return False
        if told_off(text):
            return True
        with self.lock:
            said = set(words(" ".join(self._said)).split())
        return sum(1 for x in w if x in said) < ECHO_WORDS * len(w)

    # --------------------------------------------------------------------------------- Voice ID and its own
    def _voice_ready(self, own: bool = True) -> tuple | None:
        """(the owner's centroid, thresholds, Kurooto's own print) when the voice check can run, else None."""
        vid = self.v.voiceid
        if not vid.on() or vid.problem() or (vid.embed_fn is None and vid.missing_parts()):
            return None
        t = vid.template()
        if not t or not t.get("centroid"):
            return None
        mine = self.own_print() if own else []
        if own and not mine:
            return None
        return sid.from_b64(t["centroid"]), vid.thresholds(t), mine

    def _own_key(self) -> tuple:
        return (tuple(self.v._tts_key), self.v.voiceid.model())

    def own_print(self) -> list[float]:
        """Kurooto's own voice print: a phrase said silently by its speech engine, resampled and embedded once, kept
        in memory only (never played or saved). [] when it can't be made (no engine, Voice ID's model missing)."""
        key = self._own_key()
        got = self._own.get(key)
        if got is not None:
            return got
        try:
            tts, _why = self.v.tts()
            if tts is None:
                return []
            from kurooto.modules.voice.voiceid import resample

            pcm, sr = tts.synth(OWN_PHRASE)
            e = list(self.v.voiceid.embed(resample(pcm, sr)))
        except Exception as e_:
            self.v.app.events.emit("voice_failed", part="barge-in own voice", error=f"{type(e_).__name__}"[:100])
            return []
        self._own[self._own_key()] = e
        return e

    # -------------------------------------------------------------------------------------------- handing on
    def _hand_on(self, pcm: bytes, flags: bytes, how: dict) -> None:
        """The stretch that barged in, to Voice's hearing thread (barge_turn), like any stretch: never blocks."""
        self.count += 1
        self.v._heard_audio(pcm, False, len(pcm) / (RATE * 2), flags, barge=how)

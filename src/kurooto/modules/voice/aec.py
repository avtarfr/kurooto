"""Echo cancelling (0.9.3, voice.listen.aec): the microphone's sound with Kurooto's own voice taken out, before the
listener's VAD, barge-in and Voice ID hear it.

Why: on a desk where the speaker and the microphone are one phone (an add-on's output and its microphone brought in as
a source), the speaker sits ~2 cm from the microphone: its echo comes back 0.2-0.4 s after the sound is handed over,
at or above the level played, and the phone's own echo cancelling doesn't touch a media stream. Barge-in then can't
tell you from its echo. This takes the echo out with an adaptive filter, so barge-in hears what's left: you.

How:
- **The far end.** Speaker._play hands every piece it plays (Kokoro or Piper, the heard-you sound, Gemini Live's
  pieces; after the output stage, so exactly what's played) to `reference(pcm, sr)`. It is resampled to the
  microphone's 16 kHz (speexdsp's resampler, quality 5) and placed on the microphone's own sample timeline: a piece
  handed over while the one before is still playing (a gapless output) starts where that one ends.
- **The timeline.** Each microphone frame's arrival time maps the clock to the microphone's sample count: the least
  late frame of the last two seconds sets it (frames come in bursts and late, never early).
- **The delay.** Where the echo of a sample turns up: seeded from the output's `echo_delay_ms` (an add-on that measured
  it, e.g. a sweep), else a guess (REMOTE_GUESS_MS on an add-on's output, LOCAL_GUESS_MS on this computer's speakers),
  then estimated live every EST_EVERY_S while it plays: the loudness envelopes of the microphone and of what's played
  (blocks of SUB samples) cross-correlated over 0..MAX_LAG_S. The far end is fed to the filter MARGIN_S earlier than
  the delay and the filter is TAIL_S long, so an echo anywhere within about +-MARGIN_S of the delay (the phone path's
  jitter, drift) is inside it; only a move past SHIFT_S (seen twice) moves the alignment.
- **The filter.** speexdsp's multi-delay block canceller (speex_echo_cancellation) on SUB-sample blocks, then its
  residual echo suppressor (speex_preprocess with the echo state; its noise suppression, AGC, VAD and dereverb off,
  so only the echo's leftovers are pushed down). While nothing has been played for a while it isn't run at all: the
  sound passes through untouched.

Through ctypes only: libspeexdsp (BSD) where the system has it; nothing is installed. Without it (or without the
setting) the sound passes as before, and /voice and `kurooto doctor` say why. Nothing is stored: the far end and the
microphone's last seconds are in memory only; what's reported is numbers (the delay, an ERLE estimate: how far the
echo was brought down, in dB)."""

from __future__ import annotations

import array
import collections
import ctypes
import ctypes.util
import math
import operator
import sys
import threading
import time
from collections.abc import Callable

RATE = 16000
SUB = 256  # speex's block (16 ms); the listener's 512-sample frames are two
TAIL_S = 0.25  # the filter's length: the room's tail and the jitter left after the delay is tracked
MARGIN_S = 0.04  # the far end goes in this much before the tracked delay (early jitter)
MAX_LAG_S = 1.5  # the coarse search: the delay is looked for up to this
EST_WIN_S = 1.5  # over this much of the microphone's sound (loudness envelopes, SUB blocks)
EST_EVERY_S = 0.5  # this often while it plays
EST_MIN = 0.45  # the envelopes' correlation at its peak must reach this to count
EST_ACTIVE = 0.3  # and what's played must sound in at least this share of the window
AGREE_S = 0.04  # two coarse estimates this close agree (a move past FINE_S needs two)
FINE_S = 0.15  # the fine search: +-this around the coarse delay, on the waveform (the phone path's jitter)
FINE_WIN_S = 0.5  # over the last this much
FINE_MIN = 0.35  # its normalised peak must reach this
FINE_MOVE = 2  # a new piece's fine delay this many samples off the alignment moves it (the echo path stays put)
DRIFT_MOVE = 16  # within a piece, two fine delays that agree (DRIFT_AGREE) this far off move it (drift)
DRIFT_AGREE = 3
DEC = 8  # the fine search's first pass: every DEC samples summed (2 kHz)
REFINE = 160  # then sample by sample within this of its best (10 ms: a low voice's pitch period and more)
REFINE_WIN_S = 0.12  # over the last this much
DRIFT_S = 0.02  # the look for drift while it plays: +-this around the alignment
DRIFT_REFINE = 24
FIRST_S = 0.2  # a new piece (not continuing the last): its delay is measured this long into its echo; until then
# the filter isn't shown it (it would learn the echo path at the wrong place), then that stretch is gone over again
REPLAY_S = 0.6  # at most this much
REMOTE_GUESS_MS = 300  # an add-on's output (a phone) before anything is measured
LOCAL_GUESS_MS = 60  # this computer's speakers
IDLE_S = 1.0  # after the last far-end sample's echo (+ the tail), the filter stops running
MAP_LEAK = 0.0005  # the clock-to-samples map may drift this much a second (s/s: clocks apart, 500 ppm)
MAP_JUMP_S = 0.05  # every frame of the last MAP_S this much later than the map: a gap in the sound, mapped anew
MAP_S = 2.0
KEEP_S = 6.0  # the far end and the envelopes are kept this long behind the microphone
SUPPRESS_DB = -40  # the residual echo suppressor's depth with no one talking
SUPPRESS_ACTIVE_DB = -15  # and while someone talks over it (double talk)
NOISE_DB = -1  # the room's noise is let down by at most this (the suppressor runs for the echo only)
REF_ACTIVE = 0.003  # a block of what's played over this level (RMS, 0..1) counts as sounding
CONVERGED_DB = 10.0  # an ERLE estimate this high: cancelling is working (barge-in expects the residual)

# speexdsp's request numbers (speex_echo.h, speex_preprocess.h)
ECHO_SET_SAMPLING_RATE = 24
PP_SET_DENOISE, PP_SET_AGC, PP_SET_DEREVERB, PP_SET_NOISE_SUPPRESS = 0, 2, 8, 18
PP_SET_ECHO_SUPPRESS, PP_SET_ECHO_SUPPRESS_ACTIVE, PP_SET_ECHO_STATE = 20, 22, 24

_NAMES = {"linux": ("libspeexdsp.so.1", "libspeexdsp.so"), "darwin": ("libspeexdsp.1.dylib", "libspeexdsp.dylib"),
          "win32": ("libspeexdsp.dll", "speexdsp.dll", "libspeexdsp-1.dll")}  # fmt: skip
_lib_lock = threading.Lock()
_lib: tuple | None = None  # (CDLL or None, why)


def load(names: tuple[str, ...] | None = None):
    """(lib, "") or (None, why): libspeexdsp through ctypes, typed; tried once per process (names: tests)."""
    global _lib
    with _lib_lock:
        if _lib is not None and names is None:
            return _lib
        got = _open(names)
        if names is None:
            _lib = got
        return got


def _open(names):
    cands = list(names) if names is not None else []
    if names is None:
        found = ctypes.util.find_library("speexdsp")
        if found:
            cands.append(found)
        cands += _NAMES.get(sys.platform, _NAMES["linux"])
    for n in cands:
        try:
            lib = ctypes.CDLL(n)
            _type(lib)
            return lib, ""
        except (OSError, AttributeError):
            continue
    return None, "the speexdsp library isn't on this computer (libspeexdsp)"


def _type(lib) -> None:
    vp, i16p = ctypes.c_void_p, ctypes.POINTER(ctypes.c_int16)
    lib.speex_echo_state_init.argtypes, lib.speex_echo_state_init.restype = [ctypes.c_int, ctypes.c_int], vp
    lib.speex_echo_state_destroy.argtypes, lib.speex_echo_state_destroy.restype = [vp], None
    lib.speex_echo_cancellation.argtypes = [vp, i16p, i16p, i16p]
    lib.speex_echo_cancellation.restype = None
    lib.speex_echo_ctl.argtypes, lib.speex_echo_ctl.restype = [vp, ctypes.c_int, vp], ctypes.c_int
    lib.speex_preprocess_state_init.argtypes = [ctypes.c_int, ctypes.c_int]
    lib.speex_preprocess_state_init.restype = vp
    lib.speex_preprocess_state_destroy.argtypes, lib.speex_preprocess_state_destroy.restype = [vp], None
    lib.speex_preprocess_run.argtypes, lib.speex_preprocess_run.restype = [vp, i16p], ctypes.c_int
    lib.speex_preprocess_ctl.argtypes, lib.speex_preprocess_ctl.restype = [vp, ctypes.c_int, vp], ctypes.c_int
    lib.speex_resampler_init.argtypes = [ctypes.c_uint32] * 4 + [ctypes.POINTER(ctypes.c_int)]
    lib.speex_resampler_init.restype = vp
    lib.speex_resampler_destroy.argtypes, lib.speex_resampler_destroy.restype = [vp], None
    u32p = ctypes.POINTER(ctypes.c_uint32)
    lib.speex_resampler_process_int.argtypes = [vp, ctypes.c_uint32, i16p, u32p, i16p, u32p]
    lib.speex_resampler_process_int.restype = ctypes.c_int
    lib.speex_resampler_skip_zeros.argtypes, lib.speex_resampler_skip_zeros.restype = [vp], ctypes.c_int


def available() -> tuple[bool, str]:
    lib, why = load()
    return lib is not None, why


def _i16(b: bytes) -> array.array:
    a = array.array("h")
    a.frombytes(b[: len(b) - len(b) % 2])
    if sys.byteorder != "little":
        a.byteswap()
    return a


def _bytes(a: array.array) -> bytes:
    if sys.byteorder != "little":
        a = array.array("h", a)
        a.byteswap()
    return a.tobytes()


def resample(lib, pcm: bytes, sr: int, rate: int = RATE) -> array.array:
    """16-bit mono at sr to `rate` (speexdsp's resampler, quality 5, its delay taken out)."""
    x = _i16(pcm)
    if sr == rate or not x:
        return x
    err = ctypes.c_int(0)
    st = lib.speex_resampler_init(1, int(sr), int(rate), 5, ctypes.byref(err))
    if not st:
        raise RuntimeError(f"resampler {err.value}")
    try:
        lib.speex_resampler_skip_zeros(st)
        n_out = int(len(x) * rate / sr) + 64
        src = (ctypes.c_int16 * (len(x) + 256))(*x)  # zeros after: the filter's tail flushed out
        dst = (ctypes.c_int16 * n_out)()
        il, ol = ctypes.c_uint32(len(x) + 256), ctypes.c_uint32(n_out)
        lib.speex_resampler_process_int(st, 0, src, ctypes.byref(il), dst, ctypes.byref(ol))
        out = array.array("h", dst[: min(ol.value, int(round(len(x) * rate / sr)))])
    finally:
        lib.speex_resampler_destroy(st)
    return out


class Canceller:
    """speexdsp's echo canceller and residual echo suppressor, SUB samples at a time."""

    def __init__(self, lib, frame: int = SUB, tail: int = int(TAIL_S * RATE), rate: int = RATE, suppress=True):
        self.lib, self.frame = lib, frame
        self.st = lib.speex_echo_state_init(frame, tail)
        r = ctypes.c_int(rate)
        lib.speex_echo_ctl(self.st, ECHO_SET_SAMPLING_RATE, ctypes.byref(r))
        self.pp = None
        if suppress:
            self.pp = lib.speex_preprocess_state_init(frame, rate)
            # speex folds the echo's leftovers into its noise gain, so that runs, but noise itself is let down by
            # NOISE_DB at most (next to nothing): Silero and Voice ID hear the room as before
            ctl = ((PP_SET_DENOISE, 1), (PP_SET_NOISE_SUPPRESS, NOISE_DB), (PP_SET_AGC, 0), (PP_SET_DEREVERB, 0),
                   (PP_SET_ECHO_SUPPRESS, SUPPRESS_DB), (PP_SET_ECHO_SUPPRESS_ACTIVE, SUPPRESS_ACTIVE_DB))  # fmt: skip
            for req, val in ctl:
                v = ctypes.c_int(val)
                lib.speex_preprocess_ctl(self.pp, req, ctypes.byref(v))
            lib.speex_preprocess_ctl(self.pp, PP_SET_ECHO_STATE, ctypes.c_void_p(self.st))
        self.latency = frame if suppress else 0  # the suppressor's overlap: its output comes one block later
        T = ctypes.c_int16 * frame
        self._rec, self._play, self._out = T(), T(), T()

    def run(self, mic: array.array, far: array.array) -> array.array:
        """One block: the microphone's SUB samples and the far end aligned with them; the cleaned block."""
        n = self.frame
        ctypes.memmove(self._rec, mic.buffer_info()[0], 2 * n)
        ctypes.memmove(self._play, far.buffer_info()[0], 2 * n)
        self.lib.speex_echo_cancellation(self.st, self._rec, self._play, self._out)
        if self.pp is not None:
            self.lib.speex_preprocess_run(self.pp, self._out)
        out = array.array("h", bytes(2 * n))
        ctypes.memmove(out.buffer_info()[0], self._out, 2 * n)
        return out

    def close(self) -> None:
        if self.pp is not None:
            self.lib.speex_preprocess_state_destroy(self.pp)
            self.pp = None
        if self.st:
            self.lib.speex_echo_state_destroy(self.st)
            self.st = None


def _energy(a, i: int, n: int) -> float:
    """The mean square of a[i:i+n] (0..1 scale)."""
    s = a[i : i + n]
    return sum(v * v for v in s) / (max(1, len(s)) * 1073741824.0)


class Aec:
    """The listener's echo canceller. `reference()` from the speaker's thread, `process()` from the listener's; both
    under one lock (a reference is resampled before it). `on_report(dict)`: once a spell of playing has ended, its
    numbers (delay_ms, erle_db, frames, cpu_ms)."""

    def __init__(self, lib=None, clock: Callable[[], float] = time.monotonic, on_report=None,
                 margin_s: float = MARGIN_S, tail_s: float = TAIL_S):  # fmt: skip
        if lib is None:
            lib, why = load()
            if lib is None:
                raise RuntimeError(why)
        self.lib, self.clock, self.on_report = lib, clock, on_report
        self.margin_s, self.tail_s = margin_s, tail_s
        self.lock = threading.Lock()
        self.can = Canceller(lib, tail=int(tail_s * RATE))
        self.n = 0  # microphone samples seen
        self._cands: collections.deque[tuple[float, float]] = collections.deque()  # (now, index - now * RATE)
        self._base: float | None = None  # microphone sample index = base + t * RATE
        self._base_t = 0.0
        self._hist = array.array("h")  # the microphone's last seconds before cancelling (memory only)
        self._hist0 = 0  # the index of its first sample
        self._segs: list[tuple[int, array.array]] = []  # (start index on the timeline, far-end samples)
        self._ref_end_t = 0.0  # when the far end handed over so far ends playing (clock)
        self._ref_end_i = -(10**12)  # its last sample's index on the timeline
        self._mic_env: dict[int, float] = {}  # block (SUB) -> mean square, the microphone before cancelling
        self._ref_env: dict[int, float] = {}  # block -> mean square, what's played
        self.seed_ms: float | None = None
        self.remote = False
        self.delay_ms: float | None = None  # the measured delay (None: not yet)
        self._align = 0  # the far end is fed this many samples late (delay - margin)
        self._center: int | None = None  # the delay (samples) the alignment is centred on
        self._pending: float | None = None  # a coarse move past FINE_S, waiting for a second that agrees
        self._hold: int | None = None  # a new piece's start on the timeline: held back from the filter till measured
        self._hold_tries = 0
        self._held_from: int | None = None  # the first microphone sample passed through untouched while held
        self._drift: int | None = None  # a fine delay past DRIFT_MOVE, waiting for a second that agrees
        self._next_est = 0
        self.running = False  # the filter runs (something played lately)
        self._spell = {"frames": 0, "erles": []}
        self.erle_db: float | None = None  # the last spell's estimate
        self.cpu_ms = 0.0  # the mean time per listener frame while running
        self._cpu = [0.0, 0]
        self.estimates = [0, 0]  # (coarse, fine) estimates that counted

    # ------------------------------------------------------------------------------------------ the far end
    def reference(self, pcm: bytes, sr: int, remote: bool = False, seed_ms: float | None = None) -> None:
        """Speaker: this piece is handed over to play now (exactly as played). A piece handed over while the last
        one still plays (a gapless output) goes on where it ends."""
        if not pcm or not sr:
            return
        x = resample(self.lib, pcm, sr)
        if not x:
            return
        now = self.clock()
        with self.lock:
            if self._base is None:  # no microphone frame yet: nowhere to put it
                return
            self.remote = remote
            if seed_ms is not None and seed_ms > 0:
                self.seed_ms = float(seed_ms)
            chained = 0 < self._ref_end_t - now < 30
            start_t = self._ref_end_t if chained else now
            # a gapless piece goes on at the last one's end sample, whatever the clock map did meanwhile
            i0 = self._ref_end_i if chained else int(round(self._base + start_t * RATE))
            self._ref_end_t = start_t + len(x) / RATE
            self._segs.append((i0, x))
            self._ref_end_i = max(self._ref_end_i, i0 + len(x))
            for b in range(-(-i0 // SUB), (i0 + len(x)) // SUB):
                self._ref_env[b] = self._ref_env.get(b, 0.0) + _energy(x, b * SUB - i0, SUB)
            if self._center is None:
                guess = self.seed_ms or (REMOTE_GUESS_MS if remote else LOCAL_GUESS_MS)
                self._realign(int(guess * RATE / 1000))
            if not chained:  # its own start: its delay may differ (the phone path's jitter): measured first
                self._hold, self._hold_tries = i0, 0
                self._next_est = max(self.n, i0 + self._center + int(FIRST_S * RATE))

    def cut(self) -> None:
        """Speaker: playing stopped now (held, stopped): what wasn't played yet is dropped from the far end."""
        now = self.clock()
        with self.lock:
            if self._base is None:
                return
            cut = int(round(self._base + now * RATE))
            keep = []
            for i0, x in self._segs:
                if i0 >= cut:
                    continue
                keep.append((i0, x[: cut - i0] if i0 + len(x) > cut else x))
            self._segs = keep
            for b in [b for b in self._ref_env if b * SUB >= cut]:
                del self._ref_env[b]
            self._ref_end_i = min(self._ref_end_i, cut)
            self._ref_end_t = min(self._ref_end_t, now)

    def _far(self, i: int, n: int, upto: int | None = None) -> array.array:
        """The far end's samples i..i+n on the timeline (zeros where nothing was played, and from `upto` on)."""
        out = array.array("h", bytes(2 * n))
        end = i + n if upto is None else min(i + n, upto)
        for i0, x in self._segs:
            a, b = max(i, i0), min(end, i0 + len(x))
            if a < b:
                out[a - i : b - i] = x[a - i0 : b - i0]
        return out

    # --------------------------------------------------------------------------------------- the microphone
    def process(self, frame: bytes) -> bytes:
        """Listener: one microphone frame (16 kHz, 16-bit mono), cleaned when anything was played lately."""
        now = self.clock()
        mic = _i16(frame)
        n = len(mic)
        with self.lock:
            i = self.n
            self.n += n
            self._map(now)
            self._hist.extend(mic)
            for k in range(0, n - n % SUB, SUB):  # the envelope (before cancelling), on the global block grid
                if (i + k) % SUB == 0:
                    self._mic_env[(i + k) // SUB] = _energy(mic, k, SUB)
            if not self._active(i, n):
                if self.running:
                    self._end_spell()
                self._prune()
                return frame
            t0 = time.perf_counter()
            if not self.running:
                self._flush()
            if self.n >= self._next_est:
                self._next_est = self.n + int(EST_EVERY_S * RATE)
                self._estimate(i)
            if self._hold is not None and self._held_from is None and i + n > self._hold + self._align:
                self._held_from = i
            if self._held_from is not None:  # held: passed through as heard, the filter shown it once measured
                return frame
            out = array.array("h")
            far = self._far(i - self._align, n)
            for k in range(0, n - n % SUB, SUB):
                m, f = mic[k : k + SUB], far[k : k + SUB]
                y = self.can.run(m, f)
                out.extend(y)
                self._stats(m, f, y)
            out.extend(mic[n - n % SUB :])
            self._prune()
            self._cpu[0] += (time.perf_counter() - t0) * 1000
            self._cpu[1] += 1
            self.cpu_ms = self._cpu[0] / self._cpu[1]
        return _bytes(out)

    def _map(self, now: float) -> None:
        """The clock-to-samples map, from frames' arrivals: frames come late (and in bursts), never early, so the
        least late one sets it; it may slide back by MAP_LEAK a second (two clocks apart), and is set anew when every
        frame of the last MAP_S came MAP_JUMP_S later than it says (sound lost on the way). Kept steady otherwise:
        the far end's place on the timeline mustn't wander, or the filter's echo path does."""
        c = self.n - now * RATE
        self._cands.append((now, c))
        while self._cands and now - self._cands[0][0] > MAP_S:
            self._cands.popleft()
        if self._base is None:
            self._base, self._base_t = c, now
            return
        leaked = self._base - MAP_LEAK * RATE * max(0.0, now - self._base_t)
        if c > leaked:
            self._base, self._base_t = c, now
        elif now - self._cands[0][0] >= MAP_S * 0.9 and max(v for _t, v in self._cands) < leaked - MAP_JUMP_S * RATE:
            self._base, self._base_t = max(v for _t, v in self._cands), now

    def _active(self, i: int, n: int) -> bool:
        """Anything played whose echo may be in samples i..i+n (with the filter's tail and some slack)."""
        if not self._segs:
            return False
        first = min(s[0] for s in self._segs)
        return i + n - self._align >= first - SUB and i - self._align <= self._ref_end_i + (self.tail_s + IDLE_S) * RATE

    def _flush(self) -> None:
        """Starting again after a pause: the filter's far-end history emptied (its learned echo path is kept)."""
        z = array.array("h", bytes(2 * SUB))
        for _ in range(int(self.tail_s * RATE) // SUB + 1):
            self.can.run(z, z)
        self.running = True

    def _stats(self, m, f, y) -> None:
        if _energy(f, 0, len(f)) < REF_ACTIVE**2:
            return
        em, ey = _energy(m, 0, len(m)), _energy(y, 0, len(y))
        self._spell["frames"] += 1
        if em > 1e-7:
            self._spell["erles"].append(10 * math.log10(em / max(ey, 1e-12)))

    def _end_spell(self) -> None:
        self.running = False
        sp, self._spell = self._spell, {"frames": 0, "erles": []}
        if sp["frames"] < 10:
            return
        e = sorted(sp["erles"])
        self.erle_db = round(e[len(e) // 2], 1) if e else None  # the median block: double talk doesn't drag it
        rep = {"delay_ms": None if self.delay_ms is None else int(round(self.delay_ms)), "erle_db": self.erle_db,
               "frames": sp["frames"], "cpu_ms": round(self.cpu_ms, 3)}  # fmt: skip
        if self.on_report is not None:
            try:
                self.on_report(rep)
            except Exception:
                pass

    def erle_now(self) -> float | None:
        """The ERLE of this spell so far (median block), else the last spell's."""
        e = self._spell["erles"]
        if len(e) >= 10:
            s = sorted(e[-200:])
            return s[len(s) // 2]
        return self.erle_db

    def cancelling(self) -> bool:
        """Running now and bringing the echo down (barge-in then expects the residual, not the raw echo)."""
        e = self.erle_now()
        return self.running and self._held_from is None and e is not None and e >= CONVERGED_DB

    # ---------------------------------------------------------------------------------------------- the delay
    def _realign(self, delay: int) -> None:
        self._center = int(delay)
        self._align = max(0, self._center - int(self.margin_s * RATE))

    def _estimate(self, now_i: int) -> None:
        """The delay: coarse from the loudness envelopes (0..MAX_LAG_S), then fine on the waveform around it; the
        alignment follows the fine delay (so the filter's echo path stays where it learned it), and a coarse move
        too far for the fine search once two agree. A new piece held back: measured on its own start, then let in
        (and its start gone over again)."""
        if self._hold is not None:
            self._first(now_i)
            return
        coarse = estimate(self._mic_env, self._ref_env, self.n // SUB)
        center = self._center if self._center is not None else 0
        if coarse is not None:
            self.estimates[0] += 1
            c = int(coarse[0] * RATE / 1000)
            if abs(c - center) > FINE_S * RATE:
                if self._pending is not None and abs(c - self._pending) <= AGREE_S * RATE:
                    c, self._pending = (c + int(self._pending)) // 2, None
                    got = self._fine(c, int(FINE_WIN_S * RATE))
                    self._realign(got[0] if got is not None else c)
                    self.delay_ms = self._center * 1000 / RATE
                    return
                else:
                    self._pending = c
                    self.delay_ms = c * 1000 / RATE
                    return
            else:
                self._pending = None
        got = self._fine(center, int(FINE_WIN_S * RATE), DRIFT_S, DRIFT_REFINE)  # drift: a narrow look, cheap
        if got is None:
            if coarse is not None:
                self.delay_ms = coarse[0]
            return
        d, _peak = got
        self.estimates[1] += 1
        self.delay_ms = d * 1000 / RATE
        if abs(d - center) < DRIFT_MOVE:
            self._drift = None
        elif self._drift is not None and abs(d - self._drift) <= DRIFT_AGREE:
            self._realign((d + self._drift) // 2)
            self._drift = None
        else:
            self._drift = d

    def _fine(self, center: int, w: int, span_s: float = FINE_S, refine: int = REFINE) -> tuple[int, float] | None:
        """The fine delay (samples) within +-span_s of center, over the microphone's last w samples."""
        span = int(span_s * RATE)
        end = self.n
        w = min(w, end - self._hist0)
        if w < SUB * 4:
            return None
        mic = self._hist[end - w - self._hist0 : end - self._hist0]
        lo = max(0, center - span)
        far = self._far(end - w - (center + span), w + (center + span) - lo)
        return fine(mic, far, lo, center + span, refine)

    def _first(self, stop: int) -> None:
        """A new piece's first FIRST_S of echo: its delay, then the filter shown that stretch (up to `stop`, where
        the frame being processed starts) at the right place."""
        center = self._center or 0
        got = self._fine(center, int((FIRST_S + FINE_S) * RATE))
        self._hold_tries += 1
        if got is None and self._hold_tries < 3:
            self._next_est = self.n + int(0.1 * RATE)
            return
        if got is not None:
            self.estimates[1] += 1
            self.delay_ms = got[0] * 1000 / RATE
            if abs(got[0] - center) >= FINE_MOVE:
                self._realign(got[0])
        start, self._hold, self._held_from = self._held_from, None, None
        if start is None:
            return
        start = max(start, stop - int(REPLAY_S * RATE), self._hist0)
        start = stop - (stop - start) // SUB * SUB  # whole blocks
        for j in range(start, stop, SUB):
            m = self._hist[j - self._hist0 : j - self._hist0 + SUB]
            self.can.run(m, self._far(j - self._align, SUB))

    def _prune(self) -> None:
        keep = int(KEEP_S * RATE)
        if len(self._hist) > keep + RATE:
            drop = len(self._hist) - keep
            del self._hist[:drop]
            self._hist0 += drop
        lo = self.n - keep - self._align
        if self._segs and self._segs[0][0] + len(self._segs[0][1]) < lo:
            self._segs = [(i0, x) for i0, x in self._segs if i0 + len(x) >= lo]
        if len(self._mic_env) > KEEP_S * RATE / SUB * 1.5:
            cut = lo // SUB
            for d in (self._mic_env, self._ref_env):
                for b in [b for b in d if b < cut]:
                    del d[b]

    def status(self) -> dict:
        """Numbers only: running, the delay (measured; aligned on), the ERLE, the CPU per listener frame (ms)."""
        e = self.erle_now()
        return {"running": self.running, "delay_ms": None if self.delay_ms is None else int(round(self.delay_ms)),
                "aligned_ms": None if self._center is None else int(round(self._center * 1000 / RATE)),
                "erle_db": None if e is None else round(e, 1), "cpu_ms": round(self.cpu_ms, 3),
                "estimates": list(self.estimates)}  # fmt: skip

    def close(self) -> None:
        with self.lock:
            self.can.close()


def estimate(mic_env: dict, ref_env: dict, end_block: int) -> tuple[float, float] | None:
    """(delay ms, peak correlation) of the microphone's loudness envelope against what's played, over the last
    EST_WIN_S up to end_block, lags 0..MAX_LAG_S; None when too little was played or the peak isn't clear."""
    w = int(EST_WIN_S * RATE / SUB)
    lags = int(MAX_LAG_S * RATE / SUB)
    lo = end_block - w
    m = [math.sqrt(mic_env.get(b, 0.0)) for b in range(lo, end_block)]
    r = [math.sqrt(ref_env.get(b, 0.0)) for b in range(lo - lags, end_block)]
    if sum(1 for v in r if v > REF_ACTIVE) < EST_ACTIVE * w:
        return None  # too little was played to tell
    mm = sum(m) / w
    md = [v - mm for v in m]
    sm = math.sqrt(sum(v * v for v in md))
    if sm <= 1e-9:
        return None
    best, best_lag = -2.0, 0
    for lag in range(lags + 1):
        seg = r[lags - lag : lags - lag + w]
        rm = sum(seg) / w
        sd = [v - rm for v in seg]
        ss = math.sqrt(sum(v * v for v in sd))
        if ss <= 1e-9:
            continue
        c = sum(map(operator.mul, md, sd)) / (sm * ss)
        if c > best:
            best, best_lag = c, lag
    if best < EST_MIN:
        return None
    return best_lag * SUB * 1000 / RATE, best


def _dec(a, k: int = DEC) -> list[int]:
    """Every k samples summed: a crude low-pass, and k times fewer."""
    return [sum(a[j : j + k]) for j in range(0, len(a) - k + 1, k)]


def _diff(a) -> list[int]:
    """First differences: a pre-whitening, so voiced speech's pitch doesn't give the correlation a peak per period."""
    return [a[j + 1] - a[j] for j in range(len(a) - 1)]


def fine(mic: array.array, far: array.array, lo: int, hi: int, refine: int = REFINE) -> tuple[int, float] | None:
    """The echo's delay in samples, lo..hi: mic is the last W samples, far the far end from (end - W - hi) to
    (end - lo). Searched at 1/DEC of the rate, then sample by sample within +-refine of the best on the whitened
    waveform (the last REFINE_WIN_S); None when the peak isn't clear. Plain Python: a few ms."""
    w = len(mic)
    md, fd = _dec(mic), _dec(far)
    wd = len(md)
    mn = math.sqrt(sum(map(operator.mul, md, md)))
    if mn <= 0:
        return None
    best, bk = -2.0, -1
    sq = list(map(operator.mul, fd, fd))  # the far end's energy per lag: a running sum
    run = sum(sq[:wd])
    for k in range(min((hi - lo) // DEC, len(fd) - wd) + 1):  # the slice at k: lag hi - DEC * k
        if k:
            run += sq[k + wd - 1] - sq[k - 1]
        if run <= 0:
            continue
        c = sum(map(operator.mul, md, fd[k : k + wd])) / (mn * math.sqrt(run))
        if c > best:
            best, bk = c, k
    if bk < 0 or best < FINE_MIN:
        return None
    r = min(w, int(REFINE_WIN_S * RATE))
    mw = _diff(mic[w - r :])  # the last r samples
    mn1 = math.sqrt(sum(map(operator.mul, mw, mw)))
    best1, lag1 = -2.0, hi - DEC * bk
    fw = _diff(far)
    for off in range(max(0, DEC * bk - refine), min(len(far) - w, DEC * bk + refine) + 1):
        s = fw[off + w - r : off + w - 1]
        fn = math.sqrt(sum(map(operator.mul, s, s)))
        if fn <= 0 or mn1 <= 0:
            continue
        c = sum(map(operator.mul, mw, s)) / (mn1 * fn)
        if c > best1:
            best1, lag1 = c, hi - off
    return lag1, best

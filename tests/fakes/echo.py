"""FakeEcho (0.9.3): a desk whose speaker and microphone are one phone, for echo cancelling (voice/aec.py).

Never a person's sound: `speechlike()` is a made-up voice (a glottal pulse train at a wandering pitch through two
moving formant resonators, syllables of 120-260 ms with breathy bursts, gaps between words), deterministic per seed.
`Desk` plays pieces of it as the far end (what Kurooto says) through an echo path like the phone's: a delay (the
network there and back) with per-piece jitter, a gain (the echo at or above the level played), the phone speaker's
thin sound (a high-pass) and a few early reflections; adds the near end (someone talking over it) and the room's
noise; then hands the microphone's frames to the code under test on a fake clock, each frame arriving a little late
and in bursts, as a pipe delivers them. Nothing is recorded or written anywhere.
"""

from __future__ import annotations

import array
import math
import random

RATE = 16000
FRAME = 512


def speechlike(seconds: float, f0: float = 200.0, seed: int = 1, level_db: float = -20.0) -> array.array:
    """A made-up voice: words of 2-4 syllables, each a vowel-ish formant pair over a pulse train (pitch wandering
    about f0) or a short noisy burst, words parted by short gaps; RMS of the sounding part at level_db dBFS."""
    rnd = random.Random(seed)  # noqa: S311 (a made-up voice, not a secret)
    n = int(seconds * RATE)
    out = [0.0] * n
    i = int(0.05 * RATE)
    phase = 0.0
    while i < n:
        for _ in range(rnd.randint(2, 4)):  # a word
            dur = int(rnd.uniform(0.12, 0.26) * RATE)
            f1, f2 = rnd.uniform(300, 800), rnd.uniform(900, 2300)
            noisy = rnd.random() < 0.2
            pitch0 = f0 * rnd.uniform(0.85, 1.15)
            # two resonators (biquads) at the formants
            c = []
            for f, bw in ((f1, 80.0), (f2, 120.0)):
                r = math.exp(-math.pi * bw / RATE)
                c.append((2 * r * math.cos(2 * math.pi * f / RATE), -r * r))
            y1 = [0.0, 0.0]
            y2 = [0.0, 0.0]
            for k in range(dur):
                if i + k >= n:
                    break
                env = math.sin(math.pi * k / dur) ** 0.7
                if noisy:
                    src = rnd.uniform(-1, 1) * 0.6
                else:
                    pitch = pitch0 * (1 + 0.08 * math.sin(2 * math.pi * 3 * k / RATE))
                    phase += pitch / RATE
                    src = 1.0 if phase >= 1.0 else 0.0
                    phase -= math.floor(phase)
                    src += rnd.uniform(-0.03, 0.03)
                a = src + c[0][0] * y1[0] + c[0][1] * y1[1]
                y1 = [a, y1[0]]
                b = a + c[1][0] * y2[0] + c[1][1] * y2[1]
                y2 = [b, y2[0]]
                out[i + k] = env * (0.6 * a + 0.4 * b)
            i += dur + int(rnd.uniform(0.0, 0.04) * RATE)
        i += int(rnd.uniform(0.08, 0.3) * RATE)  # between words
    loud = [v for v in out if abs(v) > 1e-6]
    rms = math.sqrt(sum(v * v for v in loud) / max(1, len(loud))) or 1.0
    k = 10 ** (level_db / 20) * 32767 / rms
    return array.array("h", (max(-32767, min(32767, int(round(v * k)))) for v in out))


def phone_path(x: array.array, gain_db: float) -> list[float]:
    """The phone speaker's thin sound (one-pole high-pass ~300 Hz) and a few early reflections, at gain_db."""
    a = math.exp(-2 * math.pi * 300 / RATE)
    hp, prev_x, prev_y = [], 0.0, 0.0
    for v in x:
        y = a * (prev_y + v - prev_x)
        hp.append(y)
        prev_x, prev_y = v, y
    taps = ((0, 1.0), (int(0.003 * RATE), 0.45), (int(0.007 * RATE), -0.3), (int(0.013 * RATE), 0.2),
            (int(0.021 * RATE), -0.1), (int(0.034 * RATE), 0.06))  # fmt: skip
    g = 10 ** (gain_db / 20)
    out = [0.0] * (len(hp) + taps[-1][0] + 1)
    for d, t in taps:
        for j, v in enumerate(hp):
            out[j + d] += g * t * v
    return out


class Desk:
    """pieces: [(seconds into the scene it's handed over, 16 kHz far-end samples)]; near: [(seconds, samples)]."""

    def __init__(self, seconds: float, delay_ms: float = 280.0, gain_db: float = 3.0, jitter_ms: float = 30.0,
                 noise_db: float = -60.0, late_ms: float = 40.0, seed: int = 7):  # fmt: skip
        self.n = int(seconds * RATE)
        self.delay_ms, self.gain_db, self.jitter_ms = delay_ms, gain_db, jitter_ms
        self.late_ms = late_ms
        self.rnd = random.Random(seed)  # noqa: S311 (the scene's jitter, not a secret)
        self.pieces: list[tuple[float, array.array]] = []
        self.near: list[tuple[float, array.array]] = []
        nl = 10 ** (noise_db / 20) * 32767
        self.mic = [self.rnd.gauss(0, nl) for _ in range(self.n)]
        self.echo_only = [False] * self.n  # samples with the echo and no near end (for the ERLE)
        self.near_at = [False] * self.n
        self.now = 0.0
        self.starts: list[int] = []  # each piece's echo starts at this microphone sample
        self._end, self._delay = 0.0, delay_ms

    def play(self, at_s: float, pcm: array.array, chain: bool = False) -> Desk:
        """A piece handed over at at_s. chain: handed over while the last one plays (a gapless output): it plays
        where that one ends, with the same delay; else it starts at once, with a delay of its own (the jitter)."""
        self.pieces.append((at_s, pcm))
        if chain and self.pieces[:-1]:
            t, delay = max(at_s, self._end), self._delay
        else:
            t, delay = at_s, self.delay_ms + self.rnd.uniform(-self.jitter_ms, self.jitter_ms)
        self._end, self._delay = t + len(pcm) / RATE, delay
        self.starts.append(int((t + delay / 1000) * RATE))
        start = self.starts[-1]
        for j, v in enumerate(phone_path(pcm, self.gain_db)):
            if 0 <= start + j < self.n:
                self.mic[start + j] += v
                self.echo_only[start + j] = abs(v) > 30 or self.echo_only[start + j]
        return self

    def talk(self, at_s: float, pcm: array.array) -> Desk:
        self.near.append((at_s, pcm))
        start = int(at_s * RATE)
        for j, v in enumerate(pcm):
            if 0 <= start + j < self.n:
                self.mic[start + j] += v
                self.near_at[start + j] = True
        return self

    def samples(self) -> array.array:
        return array.array("h", (max(-32767, min(32767, int(round(v)))) for v in self.mic))

    def run(self, process, reference, frame: int = FRAME):
        """Feeds the scene: reference(pcm, sr) at each piece's hand-over, process(frame bytes) per microphone frame
        at its (late, bursty) arrival, in time order on self.now. Returns the processed samples."""
        mic = self.samples()
        out = array.array("h")
        todo = sorted(self.pieces, key=lambda p: p[0])
        k = 0
        burst = 0
        for i in range(0, self.n - frame + 1, frame):
            t_end = (i + frame) / RATE
            if burst <= 0:  # a burst: a few frames come together, late
                burst = self.rnd.randint(1, 4)
                late = self.rnd.uniform(0, self.late_ms) / 1000
            burst -= 1
            arrive = t_end + late
            while k < len(todo) and todo[k][0] <= arrive:
                self.now = todo[k][0]
                reference(todo[k][1].tobytes(), RATE)
                k += 1
            self.now = arrive
            y = array.array("h")
            y.frombytes(process(mic[i : i + frame].tobytes()))
            out.extend(y)
        return out


def erle(mic: array.array, out: array.array, mask: list[bool], skip: int = 0) -> float:
    """10 log10 of the microphone's energy over the output's, on the samples in mask (after `skip`)."""
    a = b = 0.0
    for j in range(skip, min(len(out), len(mask))):
        if mask[j]:
            a += mic[j] * mic[j]
            b += out[j] * out[j]
    return 10 * math.log10(a / max(b, 1e-9)) if a else 0.0

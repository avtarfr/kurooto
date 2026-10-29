"""One output stage for every sound Kurooto plays (0.9.2, a fix): the voice made here (Kokoro or Piper), the "heard
you" sound, Gemini Live's answers, on this computer's speakers or an add-on's output (the Body phone). Speaker._play
runs each piece through process() before anything hears it, so the echo the barge-in expects is the sound as played.

1. Levelling: a piece's loudness (RMS over its sounding samples) is moved half way towards LEVEL_DB, at most
   STEP_DB either way (a move under CLOSE_DB isn't made), so Kokoro, Piper and Live stand at about the same level. A
   piece quieter than FLOOR_DB (a soft cue such as the tone, or a quiet tail) is left as it is. Per piece and without
   memory, so the same piece always comes out the same (a piece said again after a barge-in sounds the same).
2. The room's gain: night mode's voice.room_modes.night_db (room.py); 0 otherwise.
3. A limiter at CEILING_DB (-3 dBFS): blocks of BLOCK samples, the gain each block needs taken one block early (so it
   is down before the peak), let back up over RELEASE_S, followed sample by sample; then a hard stop at the ceiling,
   so nothing it plays clips.

16-bit mono PCM in and out, the same length. NumPy when it's there (Voice's parts bring it), else plain Python."""

from __future__ import annotations

import array
import math
import sys

LEVEL_DB = -20.0  # the level speech is moved towards (RMS, dBFS)
FLOOR_DB = -28.0  # quieter than this: left as it is
STEP_DB = 6.0  # at most this much up or down
CLOSE_DB = 0.5  # a move smaller than this isn't made (the piece is left as it is)
CEILING_DB = -3.0  # the limiter's ceiling (peak, dBFS)
SOUNDING = 64  # a sample this far from zero counts as sounding (for the RMS)
BLOCK = 64  # the limiter's block (samples)
RELEASE_S = 0.08  # the limiter lets go over this long
FULL = 32768.0
CEIL = FULL * 10 ** (CEILING_DB / 20)


def _np():
    try:
        import numpy

        return numpy
    except ImportError:
        return None


def level_db(rms: float) -> float:
    return 20 * math.log10(max(rms, 1e-9) / FULL)


def levelling_db(rms: float) -> float:
    """The levelling's gain (dB) for a piece of this loudness: 0 for one under FLOOR_DB."""
    if rms <= 0:
        return 0.0
    now = level_db(rms)
    if now < FLOOR_DB:
        return 0.0
    db = max(-STEP_DB, min(STEP_DB, (LEVEL_DB - now) / 2))
    return 0.0 if abs(db) < CLOSE_DB else db


def process(pcm: bytes, sr: int, gain_db: float = 0.0) -> bytes:
    """One piece through the stage. Odd lengths keep their last byte; empty stays empty."""
    if len(pcm) < 2:
        return pcm
    tail = pcm[-1:] if len(pcm) % 2 else b""
    body = pcm[: len(pcm) - len(tail)]
    np = _np()
    out = _with_numpy(np, body, sr, gain_db) if np is not None else _plain(body, sr, gain_db)
    return out + tail


def _with_numpy(np, body: bytes, sr: int, gain_db: float) -> bytes:
    x = np.frombuffer(body, dtype="<i2").astype(np.float64)
    loud = np.abs(x) >= SOUNDING
    rms = float(np.sqrt(np.mean(x[loud] ** 2))) if loud.any() else 0.0
    db = levelling_db(rms) + gain_db
    peak = float(np.max(np.abs(x))) if x.size else 0.0
    if db == 0.0 and peak <= CEIL:
        return body  # nothing to do: the very same bytes
    x *= 10 ** (db / 20)
    n = x.size
    nb = (n + BLOCK - 1) // BLOCK
    padded = np.zeros(nb * BLOCK)
    padded[:n] = np.abs(x)
    peaks = padded.reshape(nb, BLOCK).max(axis=1)
    need = np.minimum(1.0, CEIL / np.maximum(peaks, 1e-9))
    early = np.minimum(need, np.append(need[1:], 1.0))  # down one block before the peak
    g = _release(list(early.tolist()), sr)
    gains = np.interp(np.arange(n), np.arange(nb) * BLOCK + BLOCK / 2, np.asarray(g))
    y = np.clip(x * np.minimum(gains, early.repeat(BLOCK)[:n]), -CEIL, CEIL)
    return np.round(y).astype("<i2").tobytes()


def _release(g: list[float], sr: int) -> list[float]:
    """Instant down, back up by at most `step` a block (RELEASE_S from the deepest cut to none)."""
    step = BLOCK / max(1.0, RELEASE_S * sr)
    out, cur = [], 1.0
    for v in g:
        cur = v if v < cur else min(v, cur + step)
        out.append(cur)
    return out


def _plain(body: bytes, sr: int, gain_db: float) -> bytes:
    a = array.array("h")
    a.frombytes(body)
    if sys.byteorder != "little":
        a.byteswap()
    n = len(a)
    tot, cnt, peak = 0.0, 0, 0
    for s in a:
        m = -s if s < 0 else s
        if m > peak:
            peak = m
        if m >= SOUNDING:
            tot += s * s
            cnt += 1
    rms = math.sqrt(tot / cnt) if cnt else 0.0
    db = levelling_db(rms) + gain_db
    if db == 0.0 and peak <= CEIL:
        return body
    k = 10 ** (db / 20)
    nb = (n + BLOCK - 1) // BLOCK
    need = []
    for b in range(nb):
        p = max((abs(a[i]) for i in range(b * BLOCK, min(n, (b + 1) * BLOCK))), default=0) * k
        need.append(min(1.0, CEIL / p) if p > 0 else 1.0)
    early = [min(need[b], need[b + 1] if b + 1 < nb else 1.0) for b in range(nb)]
    g = _release(early, sr)
    out = array.array("h", bytes(2 * n))
    for i in range(n):
        pos = (i - BLOCK / 2) / BLOCK  # between the centres of blocks j and j + 1
        j = math.floor(pos)
        if j < 0:
            gi = g[0]
        elif j >= nb - 1:
            gi = g[nb - 1]
        else:
            gi = g[j] + (g[j + 1] - g[j]) * (pos - j)
        y = a[i] * k * min(gi, early[i // BLOCK])
        out[i] = int(round(CEIL if y > CEIL else (-CEIL if y < -CEIL else y)))
    if sys.byteorder != "little":
        out.byteswap()
    return out.tobytes()

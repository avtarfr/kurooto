"""Text as the outline of a waveform, for the dashboard to draw while Kurooto speaks (POST /api/voice/shape).

The shape: {"samples": [...], "rate": 50, "seconds": s, "source": "tts" | "estimate"}. `samples` are loudness values
from 0 to 1 (three decimals), RATE of them a second of speech, so sample i is at i / rate seconds.

    from_pcm()   with a speech engine on this computer: the text is spoken (into memory, never played or saved) and
                 the sound's absolute amplitude is taken in 20 ms windows (the peak of each), scaled so the loudest is 1
    estimate()   without one: worked out from the letters, the same every time for the same text and rate. Vowels
                 loud and long (a rise, a hold and a fall); voiced consonants (l m n r w v z j) medium; plosives
                 (p t k b d g) a silence then a sharp burst; sibilants and fricatives (s z f h, sh, ch, th, x) low and
                 noisy (a fixed alternating pattern); a dip between words; pauses at commas (0.16 s) and at the end
                 of sentences (0.3 s); digits like a short syllable. voice.speak.rate stretches or shrinks it.
"""

from __future__ import annotations

import array
import math
import re

from kurooto.modules.voice import numbers as numbers_mod

RATE = 50  # samples a second
VOWELS = set("aeiouy")
VOICED = set("lmnrwvzj")
PLOSIVES = set("ptkbdgcq")
SIBILANTS = set("sfhx")
PAIRS = ("sh", "ch", "th", "ph", "zh")
NOISY = (0.22, 0.31, 0.18, 0.27, 0.24)  # the sibilants' fixed "noise"
MAX_CHARS = 4000


def estimate(text: str, rate: float = 1.0) -> list[float]:
    """The deterministic shape of `text` (see the module's note)."""
    rate = min(max(float(rate or 1.0), 0.5), 2.0)
    out: list[float] = []

    def add(values) -> None:
        out.extend(values)

    t = (text or "")[:MAX_CHARS].lower()
    i = 0
    noise = 0
    while i < len(t):
        c = t[i]
        two = t[i : i + 2]
        if two in PAIRS:
            add(NOISY[(noise + k) % len(NOISY)] for k in range(3))
            noise += 3
            i += 2
            continue
        if c in VOWELS:
            n = 1
            while i + n < len(t) and t[i + n] in VOWELS:  # "oo", "ea": one longer vowel
                n += 1
            hold = 2 + n
            add([0.55, *([0.92] * (hold - 1)), 1.0 if n > 1 else 0.85, 0.6])
            i += n
            continue
        if c in VOICED:
            add([0.45, 0.5])
        elif c in PLOSIVES:
            add([0.0, 0.78])
        elif c in SIBILANTS:
            add(NOISY[(noise + k) % len(NOISY)] for k in range(3))
            noise += 3
        elif c.isdigit():
            add([0.5, 0.85, 0.85, 0.5])
        elif c.isspace():
            if out and out[-1] > 0.02:
                add([0.05])
        elif c in ",;:—–-()":
            add([0.0] * 8)
        elif c in ".!?\n":
            add([0.0] * 15)
        elif c.isalpha():  # a letter of another alphabet: a short syllable
            add([0.5, 0.8, 0.6])
        i += 1
    while out and out[-1] == 0.0:
        out.pop()
    if rate != 1.0 and out:
        n = max(1, round(len(out) / rate))
        out = [out[min(len(out) - 1, int(k * len(out) / n))] for k in range(n)]
    return [round(v, 3) for v in out]


def from_pcm(pcm: bytes, sample_rate: int) -> list[float]:
    """Loudness from 16-bit mono sound: the peak of each 1/RATE s window, scaled so the loudest is 1."""
    a = array.array("h")
    a.frombytes(pcm[: len(pcm) - len(pcm) % 2])
    step = max(1, int(sample_rate) // RATE)
    peaks = [max((abs(x) for x in a[k : k + step]), default=0) for k in range(0, len(a), step)]
    top = max(peaks, default=0)
    if not top:
        return [0.0] * len(peaks)
    return [round(p / top, 3) for p in peaks]


def levels(pcm: bytes, parts: int = 5) -> list[float]:
    """A microphone frame as a few loudness numbers (0..1, two decimals): RMS of each part, on a soft log scale."""
    a = array.array("h")
    a.frombytes(pcm[: len(pcm) - len(pcm) % 2])
    if not a:
        return []
    size = max(1, len(a) // parts)
    out = []
    for k in range(0, size * parts, size):
        chunk = a[k : k + size]
        rms = math.sqrt(sum(x * x for x in chunk) / max(1, len(chunk))) / 32768
        out.append(round(min(1.0, max(0.0, (20 * math.log10(rms + 1e-9) + 60) / 60)), 2))  # -60 dB .. 0 dB
    return out


def envelope(pcm: bytes, most: int = 120) -> list[float]:
    """A heard stretch as its loudness outline: one number per 20 ms (levels' scale), at most `most` of them."""
    n = len(pcm) // 2
    return levels(pcm, min(most, max(1, n // 320))) if n else []


def payload(samples: list[float], source: str) -> dict:
    return {"samples": samples, "rate": RATE, "seconds": round(len(samples) / RATE, 2), "source": source}


def clean(text: str) -> str:
    """Markdown and links out, for speaking and for the shape: what's said is what's read."""
    t = re.sub(r"```.*?```", " (code on screen) ", text or "", flags=re.S)
    t = re.sub(r"`([^`]*)`", r"\1", t)
    t = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"https?://\S+", "a link", t)
    t = re.sub(r"\[\[([^\]|]+)(\|([^\]]+))?\]\]", lambda m: m.group(3) or m.group(1), t)
    t = re.sub(r"^\s{0,3}(#+|[-*+]|\d+[.)])\s+", "", t, flags=re.M)
    t = re.sub(r"[*_~|>#]+", "", t)
    return re.sub(r"[ \t]+", " ", t).strip()


def spoken(text: str, numbers: bool = False) -> str:
    """clean(), and with `numbers` its numbers in words (numbers.py): the text as the voice says it, never shown."""
    t = clean(text)
    return numbers_mod.say(t) if numbers else t


def sentences(text: str, numbers: bool = False) -> list[str]:
    """Sentence by sentence, so speech starts after the first one is ready; long ones split at commas."""
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+|\n+", spoken(text, numbers)) if p.strip()]
    out = []
    for p in parts:
        while len(p) > 220:
            cut = max(p.rfind(", ", 0, 220), p.rfind("; ", 0, 220))
            cut = cut + 1 if cut > 40 else 220
            out.append(p[:cut].strip())
            p = p[cut:].strip()
        if p:
            out.append(p)
    return out

"""FakeEars (0.9.2): a desk tape for Voice's hearing. Scripted scenes are played as microphone frames through the real
pipeline (ears.Ears, audio.Listener, Voice), with no sound device: each microphone is a FakeMic fed from a scene, and
a scene can unplug its source in the middle (it stalls, sends only digital silence, or ends) to test "ears source
lost".

The sound in a scene is never a person's: "voice" segments are a made-up voiced sound (a buzz at speech level with a
syllable-rate envelope), and "say:<text>" segments are made by Kokoro, this computer's own voice, only when the
environment names its model folder (KUROOTO_TEST_KOKORO: kokoro-v1.0.onnx and voices-v1.0.bin; tests that need it skip
otherwise). Nothing is recorded and nothing is written to disk.

    tape = Tape({"Body mic": Scene().voice(1.0).quiet(0.5).unplug("stall"), "": Scene().voice(1.0)})
    ears = Ears("Body mic", make=tape.make, probe=tape.probe, lost_s=0.3)
"""

from __future__ import annotations

import math
import os
import struct
import threading
import time
from pathlib import Path

RATE = 16000
FRAME = 512


def voiced(seconds: float, level: float = 0.2) -> bytes:
    """A made-up voiced sound: a 140 Hz buzz with two formant-ish partials and a 4 Hz syllable envelope."""
    n = int(seconds * RATE)
    out = bytearray()
    for i in range(n):
        t = i / RATE
        env = 0.55 + 0.45 * math.sin(2 * math.pi * 4 * t) ** 2
        w = 2 * math.pi * t
        x = math.sin(w * 140) + 0.5 * math.sin(w * 700) + 0.3 * math.sin(w * 1200)
        out += struct.pack("<h", int(max(-1.0, min(1.0, level * env * x / 1.8)) * 32767))
    return bytes(out)


def room_noise(seconds: float, level: float = 0.002) -> bytes:
    """Quiet, never exactly zero (a real microphone's floor)."""
    n = int(seconds * RATE)
    return b"".join(struct.pack("<h", int(level * 32767 * math.sin(i * 1.7) or 1)) for i in range(n))


def kokoro_says(text: str) -> bytes | None:
    """Kokoro's own voice for `text`, at 16 kHz, when KUROOTO_TEST_KOKORO names its model folder; else None."""
    d = os.environ.get("KUROOTO_TEST_KOKORO", "")
    if not d or not (Path(d) / "kokoro-v1.0.onnx").is_file():
        return None
    from kurooto.modules.voice import audio

    k = audio.Kokoro(Path(d) / "kokoro-v1.0.onnx", Path(d) / "voices-v1.0.bin")
    pcm, sr = k.synth(text)
    if sr == RATE:
        return pcm
    import array

    a = array.array("h")
    a.frombytes(pcm)
    step = sr / RATE
    return array.array("h", (a[int(i * step)] for i in range(int(len(a) / step)))).tobytes()


class Scene:
    """What one microphone hears, in order. Ends: "end" (the recorder stops), "stall" (no more frames), "zeros"
    (digital silence, as a pipe with nothing written in), or keeps sending quiet noise (the default)."""

    def __init__(self):
        self.parts: list[bytes] = []
        self.after = "noise"

    def voice(self, seconds: float, level: float = 0.2) -> Scene:
        self.parts.append(voiced(seconds, level))
        return self

    def say(self, text: str) -> Scene:
        pcm = kokoro_says(text)
        if pcm is None:
            raise RuntimeError("Kokoro isn't here (KUROOTO_TEST_KOKORO)")
        self.parts.append(pcm)
        return self

    def quiet(self, seconds: float) -> Scene:
        self.parts.append(room_noise(seconds))
        return self

    def unplug(self, how: str = "stall") -> Scene:
        self.after = how
        return self

    def sound(self) -> bytes:
        return b"".join(self.parts)


class FakeMic:
    """A microphone on the tape: its scene's frames, paced at `speed` times real time; then its ending."""

    def __init__(self, tape: Tape, device: str):
        self.tape, self.device = tape, device
        self.closed = threading.Event()
        self.reopened = 0

    def how(self) -> str:
        return "fake"

    def close(self) -> None:
        self.closed.set()

    def frames(self):
        self.tape.opened.append(self.device)
        scene = self.tape.scenes.get(self.device)
        if scene is None:
            raise RuntimeError(f"no such microphone: {self.device!r}")
        data = scene.sound()
        pace = FRAME / RATE / self.tape.speed
        for i in range(0, len(data) - FRAME * 2 + 1, FRAME * 2):
            if self.closed.is_set():
                return
            yield data[i : i + FRAME * 2]
            time.sleep(pace)
        after = scene.after
        while not self.closed.is_set():
            if after == "end":
                return
            if after == "stall":
                self.closed.wait(0.05)
                continue
            yield bytes(FRAME * 2) if after == "zeros" else room_noise(FRAME / RATE)
            time.sleep(pace)


class Tape:
    """Several microphones by name ("" is this computer's default) and which of them the sound system lists."""

    def __init__(self, scenes: dict[str, Scene], speed: float = 4.0):
        self.scenes = dict(scenes)
        self.speed = speed
        self.listed = {name: True for name in scenes}
        self.opened: list[str] = []

    def make(self, device: str, backend: str = "auto") -> FakeMic:
        return FakeMic(self, device)

    def probe(self, device: str) -> bool | None:
        return self.listed.get(device)

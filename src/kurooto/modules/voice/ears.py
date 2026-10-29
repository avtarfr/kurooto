"""Ears source lost (0.9.2, voice.degrade.on): the microphone you named in voice.listen.device (an add-on's, say a
phone's) goes away, and listening carries on from this computer's default microphone within about two seconds instead
of stopping; when the named one is back, it goes back to it.

Ears is what audio.Listener reads instead of a plain audio.Mic (frames(), close(), how(), device, reopened). It reads
the microphone in use on a thread of its own (that thread alone opens, reads and closes it, as audio.Mic requires)
and counts the named one as lost when, for LOST_S:
  - no frames came (the source stalled),
  - only exact digital silence came (a pipe with nothing written into it; a real microphone is never all zeros), or
  - the sound system no longer lists it (present(): PipeWire/PulseAudio's sources, checked every PROBE_S).
On the default microphone it checks every PROBE_S whether the named one is listed again, and goes back to it; a named
one that's listed but still silent sends it back to the default, and the next try waits twice as long (up to
PROBE_MAX_S). on_change("lost" | "back") tells Voice, which says so in /voice and /health and has Voice ID use the
print of the microphone in use (Voice.ears_device()). Sound stays in memory, as everywhere in Voice."""

from __future__ import annotations

import queue
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterator

LOST_S = 1.5  # the named microphone silent (no frames, or only zeros) this long is lost
START_S = 1.0  # more time for it to open at first
PROBE_S = 10.0  # how often the sound system's list is checked
PROBE_MAX_S = 60.0
SOON_S = 30.0  # lost again this soon after coming back: the next try waits twice as long
QUEUE_FRAMES = 64
END = object()


def present(device: str) -> bool | None:
    """Is this microphone listed by the sound system now? None when it can't tell (no pactl, or not Linux): then only
    silence counts. Matches a source's name or its description, whole or in part (as sounddevice's names do)."""
    dev = str(device or "").strip().lower()
    if not dev or dev.isdigit() or not sys.platform.startswith("linux") or not shutil.which("pactl"):
        return None
    try:
        out = subprocess.run(["pactl", "list", "sources"], capture_output=True, text=True, timeout=3).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    names = []
    for ln in out.splitlines():
        ln = ln.strip()
        if ln.startswith(("Name:", "Description:")):
            names.append(ln.split(":", 1)[1].strip().lower())
    if not names:
        return None
    return any(dev == n or dev in n for n in names if not n.endswith(".monitor"))


class Ears:
    def __init__(
        self,
        device: str,
        backend: str = "auto",
        make: Callable | None = None,
        on_change: Callable[[str], None] | None = None,
        probe: Callable[[str], bool | None] = present,
        lost_s: float = LOST_S,
        probe_s: float = PROBE_S,
        clock: Callable[[], float] = time.monotonic,
    ):
        if make is None:
            from kurooto.modules.voice.audio import Mic

            make = Mic
        self.named = str(device or "")
        self.choice = str(backend or "auto")
        self.make = make
        self.on_change = on_change
        self.probe = probe
        self.lost_s, self.probe_s = float(lost_s), float(probe_s)
        self.clock = clock
        self.lost = False  # on this computer's default microphone now
        self.losses = 0  # times the named one was lost since this started (a count)
        self.reopened = 0
        self._wait = float(probe_s)
        self._back_at: float | None = None
        self._closed = threading.Event()
        self._mic = None
        self._lock = threading.Lock()

    @property
    def device(self) -> str:
        """The microphone in use: the named one, or "" (the default) while it's lost."""
        return "" if self.lost else self.named

    def how(self) -> str:
        from kurooto.modules.voice.audio import backend

        return backend(self.choice, self.device)

    def close(self) -> None:
        self._closed.set()
        with self._lock:
            mic = self._mic
        if mic is not None:
            mic.close()

    # ----------------------------------------------------------------------------------------------- reading
    def frames(self) -> Iterator[bytes]:
        while not self._closed.is_set():
            mic = self.make(self.device, self.choice)
            with self._lock:
                self._mic = mic
            q: queue.Queue = queue.Queue(maxsize=QUEUE_FRAMES)
            reader = threading.Thread(target=self._read, args=(mic, q), name="voice-ears", daemon=True)
            reader.start()
            try:
                why = yield from self._pump(q)
            finally:
                mic.close()
                reader.join(0.5)
                with self._lock:
                    self._mic = None
            if self._closed.is_set() or why == "closed":
                return
            if why == "failed" and self.lost:
                raise RuntimeError("this computer's microphone stopped too")
            self._switch(why)

    def _read(self, mic, q: queue.Queue) -> None:
        """On its own thread: the microphone's frames into the queue (the oldest dropped when behind); END after."""
        try:
            for f in mic.frames():
                _put(q, f)
                if self._closed.is_set():
                    break
        except Exception:
            pass
        finally:
            _put(q, END)

    def _pump(self, q: queue.Queue):
        """Frames out while the microphone in use is fine; returns why it stopped: "closed", "failed" (it ended),
        "lost" (the named one went) or "back" (the named one is listed again, from the default)."""
        now = self.clock()
        heard = now + START_S  # the last real sound (with time to open)
        probe_at = now + (self._wait if self.lost else self.probe_s)
        while not self._closed.is_set():
            try:
                f = q.get(timeout=0.1)
            except queue.Empty:
                f = None
            now = self.clock()
            if f is END:
                return "closed" if self._closed.is_set() else ("failed" if self.lost else "lost")
            if f is not None:
                if f.strip(b"\x00"):
                    heard = now
                yield f
            if not self.lost:
                if now - heard > self.lost_s:
                    return "lost"
                if now >= probe_at:
                    probe_at = now + self.probe_s
                    if self.probe(self.named) is False:
                        return "lost"
            elif now >= probe_at:
                probe_at = now + self._wait
                if self.probe(self.named):
                    return "back"
        return "closed"

    def _switch(self, why: str) -> None:
        if why == "back":
            self.lost = False
            self._back_at = self.clock()
            self._tell("back")
            return
        if why in ("lost", "failed") and not self.lost:
            self.lost = True
            self.losses += 1
            # listed again but lost again soon after: wait longer before the next try
            soon = self._back_at is not None and self.clock() - self._back_at < SOON_S
            self._wait = min(PROBE_MAX_S, self._wait * 2) if soon else self.probe_s
            self._tell("lost")

    def _tell(self, state: str) -> None:
        if self.on_change is not None:
            try:
                self.on_change(state)
            except Exception:
                pass


def _put(q: queue.Queue, item) -> None:
    try:
        q.put_nowait(item)
    except queue.Full:
        try:
            q.get_nowait()
            q.put_nowait(item)
        except (queue.Empty, queue.Full):
            pass

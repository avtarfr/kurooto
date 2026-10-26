"""The portal: the only way what's said near the computer reaches the AI you picked.

Closed (the start, and after every close), nothing leaves the computer: speech is written out and judged here
(gate.py), and words that weren't to Kurooto are dropped on the spot. A turn the gate calls addressed opens it; the
words go to your AI like a chat message (send), the answer comes back as text and is spoken (speak). It closes at
once when the next thing heard isn't addressed, or after close_s seconds with nothing said to it, and says so.
"""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable

from kurooto.modules.voice.gate import Context, Decision, Heard

UNADDRESSED_S = 60  # how far back "people have been talking nearby" looks
SORRY = "I couldn't get an answer just now."


class Portal:
    def __init__(
        self,
        send: Callable[[str], str],
        speak: Callable[[str], None],
        publish: Callable[..., None],
        clock: Callable[[], float] = time.monotonic,
        close_s: float = 8,
        on_change: Callable[[bool, str], None] | None = None,
        listening: Callable[[], bool] = lambda: True,
    ):
        self.send, self.speak, self.publish, self.clock = send, speak, publish, clock
        self.close_s = float(close_s)
        self.on_change = on_change
        self.listening = listening  # is the microphone on (for the state the dashboard shows)
        self.open = False
        self.awaiting = False
        self.busy = False
        self.last: float | None = None  # the last addressed turn or reply
        self.spoke_at: float | None = None
        self.last_reply = ""
        self._unaddressed: deque[float] = deque(maxlen=50)  # times only, never words

    # ---------------------------------------------------------------------------------------------- state
    def context(self) -> Context:
        now = self.clock()
        while self._unaddressed and now - self._unaddressed[0] > UNADDRESSED_S:
            self._unaddressed.popleft()
        return Context(
            portal_open=self.open,
            awaiting=self.open and self.awaiting,
            since_portal_s=None if self.last is None else now - self.last,
            since_spoke_s=None if self.spoke_at is None else now - self.spoke_at,
            last_reply=self.last_reply,
            unaddressed=len(self._unaddressed),
        )

    def state(self, state: str, why: str = "") -> None:
        self.publish("voice_state", state=state, portal=self.open, listening=self.listening(), why=why)

    def _set(self, is_open: bool, why: str) -> None:
        self.open = is_open
        if not is_open:
            self.awaiting = False
        if self.on_change:
            self.on_change(is_open, why)

    def close(self, why: str) -> bool:
        """Close it now (not addressed, silence, muted, a call, the night, turned off). False if it was closed."""
        if not self.open:
            return False
        self._set(False, why)
        self.last_reply = ""
        self.state("closed", why)
        return True

    def tick(self) -> None:
        """Called every second or so: close_s of nothing said to it closes it."""
        if self.open and not self.busy and self.last is not None and self.clock() - self.last > self.close_s:
            self.close("silence")

    # ----------------------------------------------------------------------------------------------- a turn
    def take(self, h: Heard, d: Decision, text: str | None = None) -> str | None:
        """What the gate decided about one stretch of speech. Only an addressed one is sent (its `text`, the words
        with the wake word taken out); anything else closes an open portal at once. Returns the reply, if any."""
        if not d.addressed:
            self._unaddressed.append(self.clock())
            self.close("not addressed")
            return None
        said = (h.text if text is None else text).strip()
        if not self.open:
            self._set(True, d.why)
        self.last = self.clock()
        if not said:  # the wake word alone: ready for the request, nothing sent anywhere
            self.awaiting = True
            self.state("addressed", d.why)
            self.speak("Yes?")
            self.spoke_at = self.last = self.clock()
            return None
        self.awaiting = False
        self.busy = True
        try:
            self.state("addressed", d.why)
            self.publish("voice_text", who="you", text=said)
            self.state("thinking")
            try:
                reply = (self.send(said) or "").strip() or SORRY
            except Exception:
                reply = SORRY
            self.publish("voice_text", who="kurooto", text=reply)
            self.state("speaking")
            try:
                self.speak(reply)
            except Exception:
                pass
            self.last_reply = reply
            self.spoke_at = self.last = self.clock()
            if self.open:
                self.state("addressed", "waiting for more")
            return reply
        finally:
            self.busy = False

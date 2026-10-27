"""The portal: the only way what's said near the computer reaches the AI you picked.

Closed (the start, and after every close), nothing leaves the computer: speech is written out and judged here
(gate.py), and words that weren't to Kurooto are dropped on the spot. A turn the gate calls addressed opens it; the
words go to your AI like a chat message (send), the answer comes back as text and is spoken (speak). It closes at
once when the next thing heard isn't addressed, or after close_s seconds with nothing said to it, and says so.

With Voice ID (0.8.10), take() gets the verdict (`who`: owner, unsure or guest) and send() gets it too, so it travels
with the message. Each opening is a new `session`; the owner's last recognised turn (`last_owner_at`,
`last_owner_session`) lets a short reply right after it carry. Not the owner: in mode owner_only_at_all nothing is
sent or shown and it says once per session "I only answer my owner's voice."; in owner_only_acts the turn goes on as
chat, and the first reply of a session to a guest (or an unsure voice) says once that only the owner can make it act.
"""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable

from kurooto.modules.voice.gate import Context, Decision, Heard

GUEST_NOTICE = "You can chat with me, but only my owner's voice can make me do things."
UNSURE_NOTICE = "I couldn't tell it was you, so I'm only chatting: say it again closer to the microphone, or type it."
AT_ALL = "I only answer my owner's voice."
AT_ALL_EVERY_S = 60

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
        self.session = 0  # (voice id) goes up each time it opens
        self.last_owner_at: float | None = None
        self.last_owner_session = -1
        self.mode = "owner_only_acts"  # voice.speaker_id.mode, set by Voice before each turn
        self.tell_guests = True
        self._told: set[str] = set()  # the notices said in this session
        self._at_all_at: float | None = None
        self._close_s_before: float | None = None  # an invite's own hold, put back when it closes

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
        if is_open and not self.open:
            self.session += 1
            self._told = set()
        self.open = is_open
        if not is_open:
            self.awaiting = False
            if self._close_s_before is not None:
                self.close_s, self._close_s_before = self._close_s_before, None
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

    def invite(self, text: str, hold_s: float) -> None:
        """Open it after Kurooto spoke first (Face presence's greeting, 0.8.10), for `hold_s` seconds. Deliberately not
        awaiting: an awaiting portal takes any speech (gate rule 5), which would send what you say to someone next to
        you to the AI. Instead the open portal's rules apply: a question or a request within close_s (rule 7), a yes or
        no when what it said ended in "?" (rule 8), the local model as usual; anything not to it closes it at once."""
        if not self.open:
            self._set(True, "greeting")
        self.awaiting = False
        if self._close_s_before is None:
            self._close_s_before = self.close_s
        self.close_s = float(hold_s)
        self.last = self.spoke_at = self.clock()
        self.last_reply = text
        self.state("addressed", "greeting")

    def tick(self) -> None:
        """Called every second or so: close_s of nothing said to it closes it."""
        if self.open and not self.busy and self.last is not None and self.clock() - self.last > self.close_s:
            self.close("silence")

    # ----------------------------------------------------------------------------------------------- a turn
    def take(self, h: Heard, d: Decision, text: str | None = None, who=None) -> str | None:
        """What the gate decided about one stretch of speech. Only an addressed one is sent (its `text`, the words
        with the wake word taken out); anything else closes an open portal at once. Returns the reply, if any.
        who: Voice ID's verdict (speakerid.Verdict), None when it's off."""
        if not d.addressed:
            self._unaddressed.append(self.clock())
            self.close("not addressed")
            return None
        said = (h.text if text is None else text).strip()
        owner = who is None or who.decision == "owner"
        if not owner and self.mode == "owner_only_at_all":  # nothing shown or sent; one line a session, said here
            if not self.open:
                self._set(True, "someone else")
            if self.tell_guests and (self._at_all_at is None or self.clock() - self._at_all_at > AT_ALL_EVERY_S):
                self._at_all_at = self.clock()  # each call opens a new session: said once a minute at most
                try:
                    self.speak(AT_ALL)
                except Exception:
                    pass
            self.close("not the owner")
            return None
        if not self.open:
            self._set(True, d.why)
        self.last = self.clock()
        if who is not None and who.decision == "owner":
            self.last_owner_at, self.last_owner_session = self.clock(), self.session
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
            if who is None:
                self.publish("voice_text", who="you", text=said)
            else:  # the decision word, never the score
                self.publish("voice_text", who="you", text=said, speaker=who.decision)
            self.state("thinking")
            try:
                reply = (self.send(said) if who is None else self.send(said, who)) or ""
                reply = reply.strip() or SORRY
            except Exception:
                reply = SORRY
            if not owner and self.tell_guests and who.decision not in self._told:  # once a session per kind
                self._told.add(who.decision)
                reply = f"{UNSURE_NOTICE if who.decision == 'unsure' else GUEST_NOTICE} {reply}"
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

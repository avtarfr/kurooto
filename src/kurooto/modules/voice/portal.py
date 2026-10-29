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

0.8.13: it remembers, in memory only, why and when it opened (`opened_why`, for a misfire), whose voice opened it and
whose turn it answered last (`opener`, `last_who`: decision words), whether its last words answered a turn
(`answered`), and when speech that wasn't to it was last heard (the gate's chatter signal). After an answer it stays
open for follow_s (voice.listen.follow_s) when that's longer than close_s, so the conversation can go on; the owner's
last recognised turn counts from when Kurooto finished answering it, so carry follows the conversation.

0.8.17 (voice.listen.look_to_talk): look() opens it because the owner looked at it, as its name alone would, but
silently (no "Yes?") and with `looked` set until something is said to it: the gate then takes the next words as if its
name came first (gate rule 5b). Voice keeps it open while he keeps looking, and closes it when he looks away before
anything was said (Voice.look_tick).

0.9.0: tapped() is the same for a tap on a device an add-on watches (the Body face), with why "tapped" and no face
needed; it closes after close_s like any opening.
"""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable

from kurooto.modules.voice.gate import LOOKED, TAPPED, Context, Decision, Heard

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
        self.follow_s = 0.0  # voice.listen.follow_s: after an answer it stays open at least this long
        self.opened_why = ""  # the rule that opened this conversation (for a misfire); never words
        self.opened_at: float | None = None
        self.opener = ""  # (voice id) the decision word of the turn that opened it ("" when Voice ID is off)
        self.last_who = ""  # (voice id) the decision word of the turn it answered last
        self.answered = False  # its last words answered a turn in this conversation
        self._chatter_at: float | None = None  # speech that wasn't to it, last heard (a time only)
        self.looked = False  # (0.8.17) opened by the owner looking at it, nothing said to it since
        self.turns = 0  # (0.9.0) turns answered since it opened (a greeting's outcome: answered or not)
        self.tapped_open = False  # (0.9.0) opened by a tap on a device (tapped()), nothing said to it since

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
            since_chatter_s=None if self._chatter_at is None else now - self._chatter_at,
            answered=self.open and self.answered,
            since_open_s=None if not self.open or self.opened_at is None else now - self.opened_at,
            looked=self.open and self.looked,
            tapped=self.open and self.tapped_open,
        )

    def state(self, state: str, why: str = "") -> None:
        self.publish("voice_state", state=state, portal=self.open, listening=self.listening(), why=why)

    def _set(self, is_open: bool, why: str) -> None:
        if is_open and not self.open:
            self.session += 1
            self._told = set()
            self.opened_why, self.opened_at = why, self.clock()
            self.opener = self.last_who = ""
            self.answered = False
            self.looked = self.tapped_open = False
            self.turns = 0  # kept after it closes, so on_change can read how the conversation went
        self.open = is_open
        if not is_open:
            self.awaiting = False
            self.answered = False
            self.looked = self.tapped_open = False
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
        self.awaiting = self.looked = False
        self.answered = False  # a greeting answers nobody: the conversation window (follow_s) doesn't start
        if self._close_s_before is None:
            self._close_s_before = self.close_s
        self.close_s = float(hold_s)
        self.last = self.spoke_at = self.clock()
        self.last_reply = text
        self.state("addressed", "greeting")

    def listen_on(self, why: str, who: str = "") -> None:
        """(barge-in) It stopped because it was talked over, with nothing to send: open (or kept open) as after an
        answer, so what the same voice says next within follow_s (or close_s) counts. who: the decision word."""
        if not self.open:
            self._set(True, why)
            self.opener = who
        self.awaiting = self.looked = False
        self.last_who = who
        self.answered = True
        self.last = self.spoke_at = self.clock()
        self.state("addressed", why)

    def look(self) -> bool:
        """(0.8.17, voice.listen.look_to_talk) The owner looked at it: open, as its name alone would, ready for what he
        says next (gate rule 5b), but silently and with nothing sent. False when it was open already (a conversation
        going on is left as it is)."""
        if self.open:
            return False
        self._set(True, LOOKED)
        self.looked = True
        self.last = self.clock()
        self.state("addressed", LOOKED)
        return True

    def tapped(self) -> bool:
        """(0.9.0) A tap on a device (an add-on's: the Body face) opens it as its name alone would, silently: the next
        words count without the name (gate rule 5b, why TAPPED), with no face needed (Voice's FACE_FREE). Voice ID's
        rules for others still apply to what's said. False when it was open already."""
        if self.open:
            return False
        self._set(True, TAPPED)
        self.tapped_open = True
        self.last = self.clock()
        self.state("addressed", TAPPED)
        return True

    def tick(self) -> None:
        """Called every second or so: close_s of nothing said to it closes it."""
        hold = max(self.close_s, self.follow_s) if self.answered else self.close_s
        if self.open and not self.busy and self.last is not None and self.clock() - self.last > hold:
            self.close("silence")

    # ----------------------------------------------------------------------------------------------- a turn
    def take(self, h: Heard, d: Decision, text: str | None = None, who=None) -> str | None:
        """What the gate decided about one stretch of speech. Only an addressed one is sent (its `text`, the words
        with the wake word taken out); anything else closes an open portal at once. Returns the reply, if any.
        who: Voice ID's verdict (speakerid.Verdict), None when it's off."""
        if not d.addressed:
            self._unaddressed.append(self.clock())
            if d.klass == "chatter":  # people talking, not to it: the gate is careful with its name for a while
                self._chatter_at = self.clock()
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
            self.opener = who.decision if who is not None else ""
        self.last_who = who.decision if who is not None else ""
        self.answered = self.looked = self.tapped_open = False
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
            self.answered = self.open
            self.turns += 1
            if who is not None and who.decision == "owner" and self.last_owner_session == self.session:
                self.last_owner_at = self.spoke_at  # carry counts from the end of the answer, not the question
            if self.open:
                self.state("addressed", "waiting for more")
            return reply
        finally:
            self.busy = False

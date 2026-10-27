"""The gate: is what the microphone heard noise, people talking to each other (chatter), or someone talking to
Kurooto (addressed)? Every step runs on this computer, and only "addressed" opens the portal (portal.py).

    1. Voice activity (Silero VAD) found no speech                       -> noise
    2. Your own wake word model fired during it, or just before (voice.listen.wake_word; off by default)
                                                                         -> addressed
    3. No words came out of it (or only what transcribers make up from silence: "thank you", "[music]")
                                                                         -> noise
    4. Its name said as a call, the default way to wake it: first ("Kurooto, ...", "hey Kurooto") or last
       ("..., Kurooto?"), spelled as Whisper may write it (names.py: known mishearings, your variants, and near
       misses by sound and spelling)                                    -> addressed
    5. Right after its name or the wake word with nothing else said, the next thing said
                                                                         -> addressed
    6. Two or more voices heard and none of the above                    -> chatter
    7. The portal is open (a conversation within voice.listen.close_s) and it's a question or a request
       (ends with "?", or starts with a question word or a request verb: "what", "can", "remind", "set" ...)
                                                                         -> addressed
    8. A question or a request within voice.listen.after_speak_s of Kurooto speaking; when what it said was a
       question, a yes or a no ("yes", "no", "sure", "go ahead") too    -> addressed
    9. Otherwise the model on this computer judges (voice.listen.model_judge), from the words and the context
       above; its answer counts only at voice.listen.threshold confidence or more. No local model: not addressed.

Conversation mode (0.8.10, with Voice ID: voice.listen.conversation_mode): while another voice (or a second face) has
been here lately, only its name (4) with a question or a request after it (or nothing: then 5), the wake word (2) and a
direct follow-up within voice.listen.conversation_follow_s of its own answer (8) count; rules 7 and 9 don't, so people
talking to each other, the owner included, are left alone ("conversation: staying out"), and "Kurooto told me..."
only mentions it.

The gate never keeps what it heard: it returns a class, a confidence and the rule that decided (never the words)."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass

from kurooto.modules.voice.names import NameMatcher

NOISE, CHATTER, ADDRESSED = "noise", "chatter", "addressed"
CLASSES = (NOISE, CHATTER, ADDRESSED)

# what speech-to-text models write for silence, breathing or music (Whisper's well-known inventions)
MADE_UP = {
    "",
    "you",
    "thank you",
    "thanks",
    "thank you for watching",
    "thanks for watching",
    "please subscribe",
    "bye",
    "music",
    "applause",
    "silence",
    "laughter",
    "so",
    "okay",
    "hmm",
    "um",
    "uh",
}
QUESTION = re.compile(
    r"^(what|what's|whats|when|where|who|whom|whose|why|how|which|is|are|am|was|were|can|could|would|will|do|does|did|"
    r"should|shall|may|have|has|had|any|got)\b",
    re.I,
)
REQUEST = re.compile(
    r"^(please\s+)?(tell|remind|set|add|open|play|stop|cancel|show|read|call|send|start|turn|make|give|find|search|"
    r"check|note|write|put|move|snooze|mute|unmute|pause|resume|help|explain|summari[sz]e|list|repeat|say|"
    r"what about|how about)\b",
    re.I,
)
REPLY = re.compile(r"^(yes|yeah|yep|yup|no|nope|okay|ok|sure|please|go ahead|do it|don't|cancel that)\b", re.I)


@dataclass
class Heard:
    """One stretch of sound the listener cut out. `text` is the local transcript (empty until written out)."""

    speech: bool  # voice activity found speech in it
    text: str = ""
    wake: bool = False  # the wake word fired during it or just before
    voices: int | None = None  # how many voices, when the listener can tell (None: it can't)
    seconds: float = 0.0
    speech_s: float = 0.0  # (voice id) seconds the VAD called speech, without the pre-roll and the tail


@dataclass
class Context:
    """What the gate knows of the moment, from the portal (nothing here is stored)."""

    portal_open: bool = False
    awaiting: bool = False  # the wake word opened the portal with nothing else said: the next words are for it
    since_portal_s: float | None = None  # seconds since the last addressed turn or reply
    since_spoke_s: float | None = None  # seconds since Kurooto last finished speaking
    last_reply: str = ""  # what it last said (for the local model's context only)
    unaddressed: int = 0  # stretches of speech in the last minute that weren't to it
    conversation: bool = False  # (voice id) people are talking with each other here: only its name opens it
    follow_s: float = 4.0  # in a conversation, a follow-up counts only this soon after it spoke


@dataclass
class Decision:
    klass: str
    confidence: float
    why: str  # the rule that decided, in words; never what was said

    @property
    def addressed(self) -> bool:
        return self.klass == ADDRESSED


PROMPT = """You decide whether speech heard near a computer is spoken TO its voice assistant, called {name}.
It was written out by a speech recogniser, so words may be wrong.

Heard: "{text}"
{context}
Answer with JSON only, like {{"class": "chatter", "confidence": 0.8}}. The classes:
- "noise": not real speech meant for anyone (a TV, music, a cough, words with no sense).
- "chatter": people talking to each other, on the phone, or to themselves; {name} mentioned in passing.
- "addressed": a request, a question or an answer meant for {name}.
When unsure, answer "chatter" with a low confidence."""


def words(text: str) -> str:
    """Lower case, punctuation out, single spaces."""
    return " ".join(re.sub(r"[^\w' ]+", " ", (text or "").lower()).split())


def made_up(text: str) -> bool:
    w = words(text)
    return w in MADE_UP or not re.search(r"[a-zऀ-ॿ؀-ۿ一-鿿]", w)


def asks(text: str, reply: bool = False) -> bool:
    """A question or a request: ends with "?", or starts like one. reply=True: a yes or a no counts too (it asked)."""
    t = (text or "").strip()
    w = words(t)
    return t.endswith("?") or bool(QUESTION.match(w) or REQUEST.match(w) or (reply and REPLY.match(w)))


class Gate:
    """judge(prompt) -> the local model's raw answer, or None when there's no local model (then: not addressed)."""

    def __init__(
        self,
        names: list[str],
        judge: Callable[[str], str | None] | None = None,
        threshold: float = 0.7,
        close_s: float = 8,
        after_speak_s: float = 6,
        use_model: bool = True,
        variants: list[str] | tuple[str, ...] = (),
    ):
        self.names = [n.lower() for n in dict.fromkeys(n.strip() for n in names if n and n.strip())]
        self.matcher = NameMatcher(self.names, variants)
        self.judge = judge
        self.threshold = float(threshold)
        self.close_s = float(close_s)
        self.after_speak_s = float(after_speak_s)
        self.use_model = use_model

    # ------------------------------------------------------------------------------------------- its name
    def called(self, text: str) -> bool:
        """Its name said as a call: first (after "hey", "ok" ...) or last, as Whisper may spell it (names.py)."""
        return self.matcher.called(text)

    def mentioned(self, text: str) -> bool:
        return self.matcher.anywhere(text)

    # ---------------------------------------------------------------------------------------- the decision
    def decide(self, h: Heard, ctx: Context | None = None) -> Decision:
        ctx = ctx or Context()
        if not h.speech:
            return Decision(NOISE, 1.0, "no speech")
        if h.wake:
            return Decision(ADDRESSED, 1.0, "the wake word")
        text = (h.text or "").strip()
        if not words(text) or (not ctx.portal_open and made_up(text)):
            return Decision(NOISE, 0.9, "no words")
        if self.called(text):
            rest = self.matcher.uncall(text) if ctx.conversation else ""
            if rest and not asks(rest):  # (voice id) in a conversation, "Kurooto told me..." only mentions it
                return Decision(CHATTER, 0.8, "conversation: only mentioned")
            return Decision(ADDRESSED, 0.95, "its name")
        if ctx.awaiting:
            return Decision(ADDRESSED, 0.9, "right after it was called")
        if (h.voices or 0) >= 2:
            return Decision(CHATTER, 0.8, "several voices, none to it")
        if ctx.conversation:  # (voice id) people talking with each other: only its name, or a reply right after it
            it_asked = ctx.last_reply.rstrip().endswith("?")
            if ctx.since_spoke_s is not None and ctx.since_spoke_s <= ctx.follow_s and asks(text, reply=it_asked):
                return Decision(ADDRESSED, 0.8, "an answer to what it said")
            return Decision(CHATTER, 0.8, "conversation: staying out")
        recent = ctx.since_portal_s is not None and ctx.since_portal_s <= self.close_s
        if ctx.portal_open and recent and asks(text):
            return Decision(ADDRESSED, 0.85, "it follows the conversation")
        it_asked = ctx.last_reply.rstrip().endswith("?")
        if ctx.since_spoke_s is not None and ctx.since_spoke_s <= self.after_speak_s and asks(text, reply=it_asked):
            return Decision(ADDRESSED, 0.8, "an answer to what it said")
        return self.ask_model(text, ctx)

    def ask_model(self, text: str, ctx: Context) -> Decision:
        if not self.use_model or self.judge is None:
            return Decision(CHATTER, 0.0, "no local model to judge: not addressed")
        lines = []
        if ctx.portal_open and ctx.since_portal_s is not None:
            lines.append(f"They were talking with {self.names[0] if self.names else 'it'} "
                         f"{ctx.since_portal_s:.0f} seconds ago.")  # fmt: skip
        if ctx.since_spoke_s is not None and ctx.since_spoke_s < 60 and ctx.last_reply:
            lines.append(f'The assistant said {ctx.since_spoke_s:.0f} seconds ago: "{ctx.last_reply[:200]}"')
        if ctx.unaddressed >= 2:
            lines.append(f"People have been talking nearby: {ctx.unaddressed} stretches of speech in the last minute.")
        if self.mentioned(text):
            lines.append("Its name is in what was heard, but not as a call at the start or end.")
        name = self.names[0].capitalize() if self.names else "the assistant"
        prompt = PROMPT.format(name=name, text=text[:400].replace('"', "'"), context="\n".join(lines))
        try:
            raw = self.judge(prompt)
        except Exception:
            raw = None
        if raw is None:
            return Decision(CHATTER, 0.0, "the local model didn't answer: not addressed")
        klass, conf = parse(raw)
        if klass == ADDRESSED and conf < self.threshold:
            return Decision(CHATTER, conf, "the local model wasn't sure enough")
        return Decision(klass, conf, "the local model")


def parse(raw: str) -> tuple[str, float]:
    """The model's {"class", "confidence"}; a bare class word counts at 0.5; anything else is chatter at 0."""
    raw = str(raw or "")
    m = re.search(r"\{.*?\}", raw, re.S)
    if m:
        try:
            d = json.loads(m.group(0))
            klass = str(d.get("class") or d.get("label") or "").strip().lower()
            conf = float(d.get("confidence", 0.5))
            if klass in CLASSES:
                return klass, max(0.0, min(1.0, conf))
        except (ValueError, TypeError, AttributeError):
            pass
    low = raw.lower()
    hits = [c for c in CLASSES if re.search(rf"\b{c}\b", low)]
    if len(hits) == 1:
        return hits[0], 0.5
    return CHATTER, 0.0

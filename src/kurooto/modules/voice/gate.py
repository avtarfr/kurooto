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

Careful calls (0.8.13, voice.listen.careful_name): when the speaker may not be the owner talking to it (Voice ID said
unsure or someone else, people talked here within voice.listen.chatter_s without talking to it, or two or more faces
are in view), rule 4 counts its name only as a call: first, spelled as the name itself or a known spelling (never only
a near miss), with a greeting before it ("hey Kurooto ..."), a question or a request after it, or nothing after it.
Its name at the end or in the middle, or a near miss, then goes on to the other rules and the model, which is told.

The conversation goes on (0.8.13, voice.listen.follow_s): after Kurooto answered, anything the same voice says within
follow_s of it finishing speaking counts (statements too), unless another voice is in the stretch. In conversation
mode this window replaces conversation_follow_s when the voice is the one that opened the talk.

Told off (0.8.13, voice.listen.told_off): "stop", "not you", "I wasn't talking to you", "shut up", "be quiet", "go
away", "never mind" within TOLD_S of the conversation opening or of Kurooto speaking -> chatter, why TOLD_OFF (Voice
stops speaking, closes the conversation and notes a misfire).

The learned veto (0.8.13, voice.listen.learn_nightly; learn.py): an addressed decision by a borderline rule (its name as
a near miss, rule 7, the conversation going on, rule 9) is turned to chatter when the model learned at night says such
turns were usually misfires. It never touches its name said first with its own or a known spelling.

The gate never keeps what it heard: it returns a class, a confidence and the rule that decided (never the words)."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field

from kurooto.modules.voice.names import EXACT, KNOWN, NEAR, NameMatcher

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

# being told off: the whole stretch (its name, a "no" or a "sorry" around it aside) is one of these
TOLD_S = 10.0  # within this long of the conversation opening, or of Kurooto speaking
TOLD_OFF = "told off"
_FILL = r"(?:no|oh|ok|okay|sorry|please|hey|um|uh|just|ugh|dude|bro|man)"
_TOLD = re.compile(
    rf"^(?:{_FILL}\s+)*(?:"
    r"stop(?:\s+(?:it|that|talking|stop))*"
    r"|not\s+you(?:\s+.*)?"  # "not you, I was talking to him"
    r"|(?:(?:i\s+)?(?:was|am)\s+not|(?:i\s+)?wasn't|(?:i\s+)?wasnt|i'm\s+not|im\s+not|not)\s+(?:even\s+)?talking\s+to\s+you"
    r"(?:\s+.*)?"
    r"|shut\s+up(?:\s+.*)?"
    r"|(?:be|keep)\s+quiet|quiet"
    r"|go\s+away"
    r"|never\s*mind(?:\s+(?:that|it))?|forget\s+it"  # "never mind, what's the weather" is a new request: not this
    rf")(?:\s+{_FILL})*$",
    re.I,
)
TOLD_MAX_WORDS = 12

# the rules a learned veto may turn down (never its name said first with its own or a known spelling)
BORDERLINE = ("it follows the conversation", "the conversation goes on", "the local model")
VETOED = "learned: usually not to it"


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
    # 0.8.13: who may be talking, and how the conversation stands (all from memory, nothing stored)
    speaker: str = ""  # (voice id) this stretch's verdict: owner, unsure, guest; "" when Voice ID can't say
    speaker_score: float | None = None  # (voice id) its score, for the learned veto only; never logged
    faces: int | None = None  # (face presence) faces in view just now; None when the camera isn't looking
    since_chatter_s: float | None = None  # seconds since speech here that wasn't to it (any voice)
    chatter_s: float = 60.0  # voice.listen.chatter_s: chatter this recent makes the gate careful with its name
    careful: bool = True  # voice.listen.careful_name
    answered: bool = False  # the conversation is open and Kurooto's last words answered a turn in it
    same_speaker: bool | None = None  # (voice id) the voice it answered and that opened the talk; None: can't tell
    follow_window_s: float = 0.0  # voice.listen.follow_s (0: off)
    since_open_s: float | None = None  # seconds since the conversation opened
    speaking: bool = False  # Kurooto is speaking now
    told_off: bool = True  # voice.listen.told_off

    def unconfirmed(self) -> bool:
        """The speaker may not be the owner talking to it: the careful calls apply."""
        if self.speaker in ("unsure", "guest"):
            return True
        if self.since_chatter_s is not None and self.since_chatter_s <= self.chatter_s:
            return True
        return (self.faces or 0) >= 2


@dataclass
class Decision:
    klass: str
    confidence: float
    why: str  # the rule that decided, in words; never what was said
    name: str = ""  # how its name was said: exact, known, near ("" when not said)
    where: str = ""  # first, last, middle
    careful: bool = False  # the careful calls applied
    feats: dict = field(default_factory=dict)  # features(): what the learned veto and the training rows see

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


def told_off(text: str, matcher: NameMatcher | None = None) -> bool:
    """Being told off: "stop", "not you", "I wasn't talking to you", "shut up", "be quiet", "go away", "never mind"
    (its name taken off first). "stop the timer" is a request, not this."""
    t = matcher.uncall(text) if matcher is not None else text
    w = words(t)
    return bool(w) and len(w.split()) <= TOLD_MAX_WORDS and bool(_TOLD.match(w))


def features(d: Decision, h: Heard, ctx: Context) -> dict:
    """One turn as numbers and flags, for the learned veto and the training rows (learn.py). Never words or sound."""
    since = ctx.since_chatter_s
    return {
        "rule": d.why,
        "name_exact": d.name in (EXACT, KNOWN),
        "name_near": d.name == NEAR,
        "where": d.where,
        "voices": h.voices,
        "speaker": ctx.speaker,
        "score": None if ctx.speaker_score is None else round(float(ctx.speaker_score), 2),
        "since_chatter_s": None if since is None else round(min(float(since), 3600.0), 1),
        "faces": ctx.faces,
        "careful": d.careful,
    }


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
        veto: Callable[[dict], bool] | None = None,
    ):
        self.names = [n.lower() for n in dict.fromkeys(n.strip() for n in names if n and n.strip())]
        self.matcher = NameMatcher(self.names, variants)
        self.judge = judge
        self.threshold = float(threshold)
        self.close_s = float(close_s)
        self.after_speak_s = float(after_speak_s)
        self.use_model = use_model
        self.veto = veto  # learn.py's model, when it has learned enough (voice.listen.learn_nightly)

    # ------------------------------------------------------------------------------------------- its name
    def called(self, text: str) -> bool:
        """Its name said as a call: first (after "hey", "ok" ...) or last, as Whisper may spell it (names.py)."""
        return self.matcher.called(text)

    def mentioned(self, text: str) -> bool:
        return self.matcher.anywhere(text)

    # ---------------------------------------------------------------------------------------- the decision
    def decide(self, h: Heard, ctx: Context | None = None) -> Decision:
        ctx = ctx or Context()
        d = self._decide(h, ctx)
        d.feats = features(d, h, ctx)
        if d.addressed and self.veto is not None and borderline(d):
            try:
                no = bool(self.veto(d.feats))
            except Exception:
                no = False
            if no:
                out = Decision(CHATTER, 0.6, VETOED, d.name, d.where, d.careful)
                out.feats = {**d.feats, "vetoed": True}
                return out
        return d

    def _decide(self, h: Heard, ctx: Context) -> Decision:
        if not h.speech:
            return Decision(NOISE, 1.0, "no speech")
        if h.wake:
            return Decision(ADDRESSED, 1.0, "the wake word")
        text = (h.text or "").strip()
        if not words(text) or (not ctx.portal_open and made_up(text)):
            return Decision(NOISE, 0.9, "no words")
        if ctx.told_off and told_off(text, self.matcher):
            just = ctx.speaking or (ctx.since_spoke_s is not None and ctx.since_spoke_s <= TOLD_S)
            if just or (ctx.portal_open and ctx.since_open_s is not None and ctx.since_open_s <= TOLD_S):
                return Decision(CHATTER, 0.95, TOLD_OFF)
        call = self.matcher.call(text)
        careful = ctx.careful and ctx.unconfirmed()
        mention = False
        if call.where in ("first", "last"):
            if careful:  # a call only: first, its own or a known spelling, and a greeting, a request or nothing after
                if call.where == "first" and call.kind != NEAR and (call.greeted or not call.rest or asks(call.rest)):
                    return Decision(ADDRESSED, 0.95, "its name", call.kind, call.where, True)
                mention = True  # on to the other rules and the model, which is told
            else:
                rest = call.rest if ctx.conversation else ""
                if rest and not asks(rest):  # (voice id) in a conversation, "Kurooto told me..." only mentions it
                    return Decision(CHATTER, 0.8, "conversation: only mentioned", call.kind, call.where)
                return Decision(ADDRESSED, 0.95, "its name", call.kind, call.where)
        n = (call.kind, call.where, careful)
        if ctx.awaiting:
            return Decision(ADDRESSED, 0.9, "right after it was called", *n)
        if (h.voices or 0) >= 2:
            return Decision(CHATTER, 0.8, "several voices, none to it", *n)
        it_asked = ctx.last_reply.rstrip().endswith("?")
        follow = ctx.follow_window_s > 0 and ctx.answered and ctx.same_speaker is not False
        if follow and (not ctx.conversation or ctx.same_speaker):  # the same voice, within the window after it spoke
            if ctx.since_spoke_s is not None and ctx.since_spoke_s <= ctx.follow_window_s:
                return Decision(ADDRESSED, 0.8, "the conversation goes on", *n)
        if ctx.conversation:  # (voice id) people talking with each other: only its name, or a reply right after it
            if ctx.since_spoke_s is not None and ctx.since_spoke_s <= ctx.follow_s and asks(text, reply=it_asked):
                return Decision(ADDRESSED, 0.8, "an answer to what it said", *n)
            return Decision(CHATTER, 0.8, "conversation: staying out", *n)
        recent = ctx.since_portal_s is not None and ctx.since_portal_s <= self.close_s
        if ctx.portal_open and recent and asks(text):
            return Decision(ADDRESSED, 0.85, "it follows the conversation", *n)
        if ctx.since_spoke_s is not None and ctx.since_spoke_s <= self.after_speak_s and asks(text, reply=it_asked):
            return Decision(ADDRESSED, 0.8, "an answer to what it said", *n)
        d = self.ask_model(text, ctx, mention=mention)
        d.name, d.where, d.careful = n
        return d

    def ask_model(self, text: str, ctx: Context, mention: bool = False) -> Decision:
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
        if mention:
            lines.append(
                "Its name is in what was heard, but people nearby may be talking to each other (or the speaker may "
                "not be its owner), so its name in passing, or something that only sounds like it, is not a call."
            )
        elif self.mentioned(text):
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


def borderline(d: Decision) -> bool:
    """An opening the learned veto may turn down: its name heard only as a near miss, rule 7, the conversation going
    on, or the local model. Never its name said first with its own or a known spelling (the cap)."""
    if d.why == "its name":
        return d.name == NEAR and not (d.where == "first" and d.name in (EXACT, KNOWN))
    return d.why in BORDERLINE


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

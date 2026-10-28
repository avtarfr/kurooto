"""Persona card, boundaries and register: how the AI talks to you, set by you, with edges it keeps.

The persona card is four short lines you write: what to call you, the tone, how long answers should be, and things
to avoid ("be brief, no pep talk"). It starts empty: no name, voice or tone of its own. You set it on the dashboard's
About you tab, in Settings (persona.*) or with /persona. It goes along with every AI request (providers/context.py)
and every call (modules/calls config_template), so the AI words things the same way on Telegram, the app and calls.
It sets wording only. A part that would give Kurooto feelings ("say you missed me", "I love talking to you"), a
backstory ("you grew up in Pune", "you're 23") or a relationship ("be my girlfriend") is left out when it's saved,
and again whenever it's read (a hand-edited settings file too), and you're told which part went and why.

Boundaries (persona.boundaries, on): decisions about your health, your relationships and your money are yours. Every
AI request and every call is told so, with who to point you to; and a plain-English request that asks Kurooto to
decide one ("should I stop my meds", "should I break up with him", "should I put my savings in crypto") is answered
at once, without the AI, by a short line that says it's not Kurooto's to decide and names a person to ask. A rule
list (DECIDE and AREAS below), not a judgement: what it doesn't match goes on as usual.

Register (persona.register, on): a short message gets a short answer and a voice note a spoken-style one, by the
message's length band only (register_line). Nothing changes with the time of day or partway through a conversation,
and a length on your persona card wins over the band.

Rules only, on this computer; the card goes to the AI you picked with each request, like your profile's In brief.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from kurooto.core.config import register_defaults

if TYPE_CHECKING:
    from kurooto.app import App

register_defaults(
    "persona",
    {
        "call_me": "",  # persona card: what the AI calls you (empty: your name, or nothing)
        "tone": "",  # persona card: the tone you want, e.g. "plain and direct, no pep talk"
        "length": "",  # persona card: how long answers should be, e.g. "short unless I ask for detail"
        "avoid": "",  # persona card: things to avoid, e.g. "emojis, exclamation marks, motivational lines"
        "register": True,  # a short message gets a short answer, a voice note a spoken-style one (by length only)
        "boundaries": True,  # health, relationship and money decisions: not Kurooto's to make; it points to a person
        # (0.9.0) words made by rules (the desk greeting, the check-in and alarm openers) use your card too: its name
        # (spoken only when nobody else is in view) and its avoid line as punctuation, never dropping what they say
        "templates": True,
    },
)

FIELDS = (
    ("call_me", "What to call you", "e.g. Sam"),
    ("tone", "Tone", "e.g. plain and direct, no pep talk"),
    ("length", "Length", "e.g. short unless I ask for detail"),
    ("avoid", "Things to avoid", "e.g. emojis, motivational lines"),
)
NAMES = {
    "call me": "call_me",
    "call_me": "call_me",
    "call": "call_me",
    "name": "call_me",
    "tone": "tone",
    "length": "length",
    "avoid": "avoid",
    "things to avoid": "avoid",
    "don't": "avoid",
    "dont": "avoid",
}
MAX_FIELD = 200  # characters per line of the card

# What a card may not add, as (what it is, pattern). Matched per part (split at commas, full stops, semicolons and
# new lines), so "brief, say you missed me" keeps "brief".
GUARD = (
    (
        "saying it missed you",
        re.compile(
            r"\bmiss(?:ed|es|ing)?\s+(?:me|you|us|talking)\b|\bthinking\s+(?:of|about)\s+(?:me|you)\b"
            r"|\blonely\s+without\b|\bwaiting\s+for\s+(?:me|you)\b",
            re.I,
        ),
    ),
    (
        "feelings",
        re.compile(
            r"\bi\s+(?:really\s+|so\s+|truly\s+)?(?:feel|felt|love|loved|adore|miss|care|worry|worried)\b"
            r"|\b(?:i'm|i\s+am|i\s+was|i've\s+been)\s+(?:really\s+|so\s+|truly\s+|very\s+)?(?:happy|sad|glad|proud"
            r"|excited|lonely|hurt|upset|jealous|delighted|worried)\b"
            r"|\b(?:have|has|show|express|with|own|share)\s+(?:your\s+(?:own\s+)?|its\s+|real\s+|some\s+)?(?:feelings"
            r"|emotions|moods?)\b"
            r"|\b(?:say|tell\s+me|act\s+(?:like|as\s+if)|pretend|claim)\b.{0,40}\byou(?:'re|\s+are|\s+were|\s+feel"
            r"|\s+felt|\s+love|\s+care|\s+get)?\s+(?:so\s+|really\s+)?(?:love|care|feel|happy|sad|proud|lonely"
            r"|excited|worried|jealous|hurt|glad)\b",
            re.I,
        ),
    ),
    (
        "a backstory",
        re.compile(
            r"\bback\s?story\b|\byour\s+(?:past|childhood|family|parents|life\s+story|hometown|age|birthday"
            r"|memories)\b|\byou\s+(?:grew\s+up|were\s+born|went\s+to\s+school|studied\s+at|used\s+to\s+(?:live"
            r"|be)|live\s+in|have\s+(?:a|an|two|three)\s+(?:sister|brother|kids?|children|dog|cat|family"
            r"|boyfriend|girlfriend))\b|\byou(?:'re|\s+are)\s+(?:a\s+|an\s+)?\d+[\s-]?(?:years?|yrs?)(?:[\s-]old)?\b",
            re.I,
        ),
    ),
    (
        "a relationship or a life of its own",
        re.compile(
            r"\b(?:you(?:'re|\s+are)|be|act\s+as|pretend\s+(?:to\s+be|you(?:'re|\s+are)))\s+(?:my\s+|a\s+|an\s+)?"
            r"(?:girlfriend|boyfriend|partner|wife|husband|lover|best\s+friend|human|real\s+person|person|alive"
            r"|conscious)\b",
            re.I,
        ),
    ),
)
SPLIT = re.compile(r"(\s*[,;.!?\n]+\s*)")

# Boundaries: a request to decide one of these for you (start of a sentence), then what the area is.
DECIDE = re.compile(
    r"^(?:(?:so|ok|okay|hey|um|hmm|honestly|be honest)[,\s]+)*(?:should\s+i|shall\s+i|do\s+you\s+think\s+i\s+should"
    r"|would\s+you|what\s+would\s+you\s+do|tell\s+me\s+(?:if|whether)\s+(?:i\s+should|to)|decide\s+(?:for\s+me\s+)?"
    r"(?:if|whether)|is\s+it\s+(?:a\s+good\s+idea|ok|okay|wise|time|smart)\s+(?:for\s+me\s+)?to|do\s+i\s+need\s+to"
    r"|must\s+i|is\s+it\s+worth)\b(?P<rest>.+)$",
    re.I,
)
AREAS = (
    (
        "health",
        re.compile(
            r"\b(?:doctor|hospital|clinic|medic(?:ine|ines|ation|ations)|meds|pills?|dose|dosage|antibiotics?"
            r"|antidepressants?|therapy|therapist|surgery|operation|diet|fasting|symptoms?|vaccin\w*|pregnan\w*"
            r"|sick|ill|injur\w*|depress\w*|anxiety|blood\s+test|scan|prescription)\b",
            re.I,
        ),
        "A doctor or pharmacist is the one to ask; if it feels urgent, call your local emergency number.",
    ),
    (
        "relationships",
        re.compile(
            r"\b(?:break\s+up|breakup|dump|divorce|marry|propose|date|dating|ask\s+(?:him|her|them)\s+out|my\s+ex"
            r"|boyfriend|girlfriend|partner|husband|wife|crush|forgive|cut\s+(?:him|her|them)\s+off|confront"
            r"|move\s+in\s+(?:with|together)|friendship|relationship)\b",
            re.I,
        ),
        "Someone you trust, or a counsellor, is better to talk it through with.",
    ),
    (
        "money",
        re.compile(
            r"\b(?:invest\w*|stocks?|shares|crypto|bitcoin|loan|borrow|lend|debt|mortgage|savings|insurance"
            r"|credit\s+card|mutual\s+funds?|retirement|pension|gamble|gambling|bet|betting|buy\s+(?:a\s+|an\s+)?"
            r"(?:car|house|flat|apartment|home|bike))\b",
            re.I,
        ),
        "Someone you trust with money, or a financial adviser, is better to ask. I can lay out the facts if you want.",
    ),
)
NOT_MINE = "That one is yours to decide, not mine."

BOUNDARY_RULE = (
    "Decisions about their health, their relationships and their money are theirs (whether to take or stop a "
    "medicine or see a doctor; whether to end, start or confront a relationship; whether to invest, borrow, lend or "
    "make a big purchase). Give facts if they ask, but don't make the call: say in one sentence that it isn't yours "
    "to decide and name a person to ask (a doctor or pharmacist; someone they trust or a counsellor; someone they "
    "trust with money or a financial adviser). Short and kind, no lecture."
)
CARD_HEAD = (
    "Their persona card (how they want you to talk; it changes wording only. You have no feelings, backstory or life "
    "of your own to claim, and you never say you missed them):"
)
REG = "[Reply style] "  # how the register line starts, so chat history can leave it out (modules/chat.py)
SHORT_WORDS, LONG_WORDS = 12, 80  # the length bands: up to SHORT_WORDS is short, from LONG_WORDS long


# ------------------------------------------------------------------------------------------------ the card
def clean(text: str, limit: int = MAX_FIELD) -> tuple[str, list[tuple[str, str]]]:
    """A card line without what it may not add: (what's kept, [(the part left out, what it was)])."""
    text = str(text or "").replace("\r", "").strip()[: limit * 2]
    parts = SPLIT.split(text)
    kept, dropped = [], []
    for k in range(0, len(parts), 2):
        part, sep = parts[k], parts[k + 1] if k + 1 < len(parts) else ""
        kind = next((what for what, rx in GUARD if rx.search(part)), None) if part.strip() else None
        if kind:
            dropped.append((part.strip(), kind))
        elif part.strip():
            kept.append(part.strip() + sep.rstrip())
    out = " ".join(kept).strip().rstrip(",;")
    return out[:limit].strip(), dropped


def card(app: App) -> dict[str, str]:
    """The card as it's used: each line cleaned (a hand-edited settings file goes through the same rules)."""
    return {k: clean(app.settings.get(f"persona.{k}") or "")[0] for k, _, _ in FIELDS}


def card_text(app: App) -> str:
    """What goes along with every AI request and call ("" when the card is empty)."""
    c = card(app)
    labels = {"call_me": "Call them", "tone": "Tone", "length": "Length", "avoid": "Avoid"}
    lines = [f"- {labels[k]}: {v}" for k, v in c.items() if v]
    return "\n".join([CARD_HEAD, *lines]) if lines else ""


def dropped_text(dropped: list[tuple[str, str]]) -> str:
    if not dropped:
        return ""
    parts = "; ".join(f'"{p[:60]}" ({kind})' for p, kind in dropped)
    return f"Left out {parts}: the card sets how I word things, not feelings, a backstory or a life of my own."


def save(app: App, values: dict) -> tuple[dict[str, str], list[tuple[str, str]]]:
    """Set some of the card's lines (the others stay). Returns (the card now, what was left out)."""
    dropped: list[tuple[str, str]] = []
    for k, _, _ in FIELDS:
        if k in values:
            kept, gone = clean(str(values[k] or ""))
            dropped += gone
            app.settings.set(f"persona.{k}", kept)
    app.events.emit("persona_saved", lines=sum(1 for v in card(app).values() if v), left_out=len(dropped))
    return card(app), dropped


def view(app: App) -> dict:
    """For the dashboard's editor: the lines, and exactly what goes along with requests."""
    c = card(app)
    return {
        "fields": [{"key": k, "label": label, "hint": hint, "value": c[k]} for k, label, hint in FIELDS],
        "preview": card_text(app),
    }


def command(app: App, arg: str) -> str:
    """/persona: show the card; /persona tone: dry (one line or several); /persona clear [line]."""
    a = (arg or "").strip()
    if not a:
        c = card(app)
        if not any(c.values()):
            return (
                "Your persona card is empty, so I talk plainly. Set a line: /persona tone: plain, no pep talk. Lines: "
                "call me, tone, length, avoid. Or edit it on the dashboard (About you)."
            )
        rows = [f"{label}: {c[k]}" for k, label, _ in FIELDS if c[k]]
        return "Your persona card (it goes along with every AI request and call):\n" + "\n".join(rows)
    m = re.match(r"(?i)clear\b\s*(.*)$", a)
    if m:
        which = NAMES.get(m[1].strip().lower().rstrip(":")) if m[1].strip() else None
        if m[1].strip() and not which:
            return "Which line? /persona clear tone (or call me, length, avoid), or /persona clear for all of it."
        save(app, {which: ""} if which else {k: "" for k, _, _ in FIELDS})
        return f"Cleared {'that line' if which else 'your persona card'}. /persona shows it."
    values: dict[str, str] = {}
    for line in a.splitlines():
        mm = re.match(r"\s*([a-z' _]+?)\s*[:=]\s*(.*)$", line, re.I)
        key = NAMES.get(mm[1].strip().lower()) if mm else None
        if not key:
            return "Say which line: /persona tone: plain and direct (lines: call me, tone, length, avoid)."
        values[key] = mm[2]
    c, dropped = save(app, values)
    said = "Saved. " + "; ".join(f"{label}: {c[k] or '(empty)'}" for k, label, _ in FIELDS if k in values) + "."
    return said + (" " + dropped_text(dropped) if dropped else "")


# ------------------------------------------------------------------------------------- rule-made words
# The avoid line, read for what rule-made text can honour by itself: (what the line mentions, how the text changes).
# Punctuation only: a template never loses a part (what's next, what waits, a deadline) for the avoid line.
EMOJI = re.compile("[\U0001f000-\U0001faff\u2600-\u27bf\ufe0f]")
AVOID = (
    (re.compile(r"exclamation", re.I), lambda t: t.replace("!", ".")),
    (re.compile(r"emoji", re.I), lambda t: re.sub(r"\s{2,}", " ", EMOJI.sub("", t)).strip()),
)


def templates_on(app: App) -> bool:
    return bool(app.settings.get("persona.templates", True))


def address(app: App) -> str:
    """(persona.templates) What rule-made words call you: the card's call_me, or "" (off, or no name on the card)."""
    if not templates_on(app):
        return ""
    return card(app)["call_me"][:40]


def template(app: App, text: str) -> str:
    """(persona.templates) Rule-made text with the card's avoid line applied as punctuation (AVOID); unchanged when
    off or when the line asks nothing a template can do."""
    if not text or not templates_on(app):
        return text
    avoid = card(app)["avoid"]
    for rx, change in AVOID:
        if avoid and rx.search(avoid):
            text = change(text)
    return text


# ------------------------------------------------------------------------------------------- boundaries
def boundary(text: str) -> str | None:
    """The area ("health", "relationships", "money") when a sentence of this asks Kurooto to decide one, else None."""
    for sentence in re.split(r"(?<=[.!?])\s+|\n", text or ""):
        m = DECIDE.match(sentence.strip())
        if not m:
            continue
        for area, rx, _ in AREAS:
            if rx.search(m["rest"]):
                return area
    return None


def boundary_reply(area: str) -> str:
    who = next(say for a, _, say in AREAS if a == area)
    return f"{NOT_MINE} {who}"


def keeps(app: App, text: str) -> str | None:
    """A plain-English request to decide your health, relationships or money: the short answer, else None."""
    if not app.settings.get("persona.boundaries", True):
        return None
    area = boundary(text)
    if area is None:
        return None
    app.events.emit("boundary_kept", area=area)
    return boundary_reply(area)


def rule(app: App) -> str:
    return BOUNDARY_RULE if app.settings.get("persona.boundaries", True) else ""


# --------------------------------------------------------------------------------------------- register
def register_line(app: App, text: str, voice: bool = False, files: bool = False) -> str:
    """One line for the AI about how long and in what style to answer, from this message alone: its length band, or
    a voice note. "" when nothing applies (a middling message, a file sent, register off, or a length on the card)."""
    if not app.settings.get("persona.register", True):
        return ""
    if voice:
        return (
            REG + "They said this aloud: answer the way you'd say it aloud, in short sentences, with no "
            "lists, headings or markdown."
        )
    if files or card(app)["length"]:
        return ""
    words = len((text or "").split())
    if words <= SHORT_WORDS:
        return REG + "Their message is short: answer in a few lines unless it truly needs more."
    if words >= LONG_WORDS:
        return REG + "Their message is long and detailed: a full answer is fine, still without padding."
    return ""


def strip_register(prompt: str) -> str:
    """A request as they wrote it: without the register line chat.ask put last."""
    i = prompt.rfind("\n\n" + REG)
    return prompt[:i] if i >= 0 else prompt

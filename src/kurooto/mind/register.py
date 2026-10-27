"""One temperament (Brain, 0.8.14, `mind.register.on`): a single register, made from Brain's own mood and arousal
(mind/status.py), that sets how much Kurooto says when it speaks up by itself, the same everywhere at once:

    what it writes unasked   an AI request it starts itself (a background lane) is told at most this many sentences
                             for anything that goes to you unasked (quiet 2, even 3, lively 4)
    the call opener          a call it placed itself opens in one short sentence (quiet), a greeting and the reason
                             (even), or two short warm sentences (lively)
    Voice's pace             what it says aloud unasked (Face presence's greeting, an add-on's line) is spoken at
                             voice.speak.rate scaled within +-8%: a little slower when quiet, quicker when lively

Never for replies to you: an answer, a call you asked for and anything said back to you keep your settings as they are.
Its mood only ever changes how much it does unprompted; it never adds a confirm step and never slows what you asked
for (a test asserts it). Off, or Brain off: "even", which changes nothing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from kurooto import mind
from kurooto.core.config import register_defaults

if TYPE_CHECKING:
    from kurooto.app import App

register_defaults(
    "mind",
    {
        "register": {
            "on": True,  # one temperament from its mood and arousal: how long its unprompted words are, Voice's pace
        }
    },
)

PART = "register"  # its switch: mind.register.on
REGISTERS = ("quiet", "even", "lively")
SENTENCES = {"quiet": 2, "even": 3, "lively": 4}
PACE = 0.08  # Voice's pace moves at most this far either way
OPENERS = {
    "quiet": "Open the call in one short sentence that says what it's for, then let them talk.",
    "even": "Open the call with a short greeting and the one thing it's for.",
    "lively": "Open the call warmly, in two short sentences: a greeting, then what it's for.",
}


def on(app: App) -> bool:
    return mind.part_on(app, "register")


def score(snap: dict) -> float:
    """-1.5 (low mood, calm) to 1.5 (high mood, roused): the mood band, nudged by arousal."""
    m = {"low": -1.0, "high": 1.0}.get(str(snap.get("mood")), 0.0)
    try:
        ar = max(0.0, min(1.0, float(snap.get("arousal") or 0.0)))
    except (TypeError, ValueError):
        ar = 0.0
    return m + (ar - 0.5)


def register(app: App, snap: dict | None = None) -> str:
    """quiet, even or lively; even with the register or Brain off."""
    if not on(app):
        return "even"
    if snap is None:
        from kurooto.mind import status

        snap = status.snapshot(app)
    s = score(snap)
    return "quiet" if s <= -0.5 else "lively" if s >= 0.75 else "even"


def sentences(app: App, snap: dict | None = None) -> int:
    return SENTENCES[register(app, snap)]


def line(app: App, lane: str = "you") -> str:
    """For an AI request Kurooto started itself (lane "bg" or "chk"): how long anything it writes for them unasked
    may be. "" for your own requests, and with the register off. No state words: only a length."""
    if lane == "you" or not on(app):
        return ""
    return f"Anything you write that goes to them without their asking: at most {sentences(app)} sentences."


def opener(app: App, asked: bool = False) -> str:
    """The call opener's length, for a call Kurooto placed itself; "" for a call you asked for, or the register off."""
    if asked or not on(app):
        return ""
    return OPENERS[register(app)]


def rate(app: App, base: float, unprompted: bool = False) -> float:
    """Voice's speaking rate: `base` (voice.speak.rate) for anything said back to you; for what it says unasked, base
    scaled within +-PACE by the register's score."""
    if not unprompted or not on(app):
        return base
    from kurooto.mind import status

    s = max(-1.0, min(1.0, score(status.snapshot(app)) / 1.5))
    return round(float(base) * (1.0 + PACE * s), 3)


__all__ = ["register", "sentences", "line", "opener", "rate", "score", "REGISTERS"]

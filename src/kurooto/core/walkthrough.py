"""Going through what waits, aloud (0.9.0, voice.answers_questions): the greeting's "Want to go through them?" gets an
answer.

After Face presence's greeting ends with that question and opens the conversation, a yes said aloud ("yes", "sure",
"go through them") starts it: Kurooto reads each waiting question in turn and your spoken words answer it
(core/ask.py: answer with via "voice"); "skip" or "later" leaves one for later, "stop" ends it. Approvals are only
named and counted: they wait for your tap on the phone or Telegram, as always (core/tap.py). Only your voice counts
(Voice ID's verdict "owner", or "" with Voice ID off), and nothing is read while someone else is here
(core/biometric.py: others_present). In memory only; it lapses after a few quiet minutes.
"""

from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kurooto.app import App
    from kurooto.modules.base import Incoming

OFFER_S = 120  # a yes this soon after the greeting's question starts it
IDLE_S = 300  # with nothing said this long, it ends by itself
YES = re.compile(r"^(?:yes|yeah|yep|sure|ok(?:ay)?|go ahead|go on|let'?s (?:do it|go)|(?:go|run) through them)\b", re.I)
SKIP = re.compile(r"^(?:skip|later|next|not now|pass)\b", re.I)
STOP = re.compile(r"^(?:stop|that'?s (?:it|all|enough)|enough|no(?:pe)?|cancel)\b", re.I)
_state: dict[int, dict] = {}


def on(app: App) -> bool:
    return bool(app.settings.get("voice.answers_questions"))


def offered(app: App) -> None:
    """The greeting just asked "Want to go through them?" (modules/face: greet)."""
    if on(app):
        _state[id(app)] = {"offered": time.monotonic(), "queue": [], "current": None, "at": time.monotonic()}


def _owner(msg: Incoming) -> bool:
    return msg.via == "voice" and msg.speaker in ("", "owner")


def _private(app: App) -> bool:
    from kurooto.core import biometric

    try:
        return biometric.others_present(app)
    except Exception:
        return False


def take(app: App, msg: Incoming, text: str) -> str | None:
    """A turn said aloud: what to say back when the walk-through takes it, else None (it goes on as usual)."""
    st = _state.get(id(app))
    if st is None or not on(app) or not _owner(msg):
        return None
    t = time.monotonic()
    if st["current"] is None and not st["queue"]:
        _state.pop(id(app), None)
        if t - st["offered"] > OFFER_S or not YES.match(text.strip()):
            return None
        return _start(app, st)
    if t - st["at"] > IDLE_S:
        _state.pop(id(app), None)
        return None
    st["at"] = t
    said = text.strip()
    if STOP.match(said):
        _state.pop(id(app), None)
        return "OK, the rest wait. /q lists them."
    qid = st["current"]
    if SKIP.match(said):
        lead = "Left for later."
    else:
        r = app.ask.answer(qid, said, "voice")
        lead = "Noted." if (r or {}).get("ok", True) else "That one was dealt with meanwhile."
    return _next(app, st, lead)


def _start(app: App, st: dict) -> str:
    if _private(app):
        return "Not with someone else here. /q lists them, or ask again when you're alone."
    qs = app.ask.pending(kind="question")
    approvals = len(app.ask.pending(kind="approval"))
    st.update(queue=[q["id"] for q in qs], current=None, at=time.monotonic())
    lead = (f"{approvals} approval{'s' if approvals != 1 else ''} wait for your tap on the phone or Telegram. "
            if approvals else "")  # fmt: skip
    if not qs:
        _state.pop(id(app), None)
        return (lead + "No questions wait.").strip()
    _state[id(app)] = st
    app.events.emit("walkthrough_started", questions=len(qs), approvals=approvals)
    return _next(app, st, lead.strip())


def _next(app: App, st: dict, lead: str) -> str:
    from kurooto.core.ask import OPEN

    while st["queue"]:
        qid = st["queue"].pop(0)
        q = app.ask.get(qid)
        if q and q.get("status") in OPEN:
            st["current"] = qid
            title = q.get("title") or "A question"
            return f"{lead} {title}: {str(q.get('text') or '')[:300]}".strip()
    _state.pop(id(app), None)
    return f"{lead} That's all of them.".strip()


def active(app: App) -> bool:
    return id(app) in _state

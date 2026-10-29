"""You're here (0.9.0): one words-free sign that the owner is around, "owner_here {via}", from whichever sense saw it.

    owner_here(app, via)    a sense saw you: "face" (Face presence saw your face), "voice" (Voice ID called a voice
                            yours, even talk that wasn't to Kurooto), "dashboard" (you used the dashboard: its buttons,
                            Ctrl+K, the journal, a capture, Study mode), "phone" (you used the phone app: its chat,
                            a button, an answer, a Today action; these fire with every phone sense off)
    last(app, desk=False)   when (time.time()) any via, or only a desk one, last said so; None never since start

Each via has its own switch, `presence.owner_here.<via>` (all on). The event goes into the log at most once every
EVENT_GAP_S per via (the time is kept in memory on every call), so the log doesn't fill up with it. It carries the via
only: never a word, a face or a voice.

Who reads it (each under its own switch, none of it holds anything back):
    mind/signals.py           your first and last sign of life of the day (ACTIVE)
    mind/presence_forecast.py at your desk now: the desk vias (face, voice, dashboard), never the phone
    mind/sleep.py             a dashboard or phone action wakes it, as a tap does (never your face or voice alone)
    mind/breaks.py            "back" when this ended Face presence's away
    Face presence             a voice or dashboard sign ends "you've stepped away" (Face.here()); it's never counted
                              as an arrival, so it never greets you
"""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING

from kurooto.core.config import register_defaults

if TYPE_CHECKING:
    from kurooto.app import App

register_defaults(
    "presence",
    {
        "owner_here": {  # (0.9.0) words-free signs you're around, read by Brain and Face presence (core/here.py)
            "face": True,  # Face presence seeing your face counts as you being here
            "voice": True,  # Voice ID calling a voice yours (even talk not to Kurooto) counts as you at the desk
            "dashboard": True,  # using the dashboard (buttons, Ctrl+K, journal, capture) counts as you at the desk
            "phone": True,  # using the phone app (chat, buttons, answers, Today) counts as you being around
        }
    },
)

EVENT = "owner_here"
VIAS = ("face", "voice", "dashboard", "phone")
DESK = ("face", "voice", "dashboard")  # at this computer; the phone may be anywhere
EVENT_GAP_S = 300.0  # the same via goes into the event log at most this often
_lock = threading.Lock()


def on(app: App, via: str) -> bool:
    return via in VIAS and bool(app.settings.get(f"presence.owner_here.{via}"))


def _table(app: App) -> dict[str, list[float]]:
    t = getattr(app, "_owner_here", None)
    if t is None:
        t = {}
        app._owner_here = t  # type: ignore[attr-defined]
    return t


def owner_here(app: App, via: str, at: float | None = None) -> bool:
    """A sense saw you (via one of VIAS). Kept in memory; into the event log once per EVENT_GAP_S, or at once when it
    ended Face presence's away (then with back=True, so breaks count it). False with the via's switch off. Never
    raises."""
    try:
        if not on(app, via):
            return False
        t = time.time() if at is None else float(at)
        back = via in ("voice", "dashboard") and _face_back(app)
        with _lock:
            row = _table(app).setdefault(via, [0.0, 0.0])  # [last seen, last logged]
            row[0] = max(row[0], t)
            due = back or t - row[1] >= EVENT_GAP_S
            if due:
                row[1] = t
        if due:
            app.events.emit(EVENT, via=via, **({"back": True} if back else {}))
        return True
    except Exception:
        return False


def _face_back(app: App) -> bool:
    """A voice or dashboard sign ends Face presence's away (no greeting: it isn't an arrival). True when it did."""
    face = app.modules.get("face")
    if face is None or not app.is_on("face"):
        return False
    try:
        return bool(face.here())
    except Exception:
        return False


def last(app: App, desk: bool = False) -> float | None:
    """When a via (desk: only face, voice, dashboard) last said you were here, as time.time(); None never."""
    with _lock:
        rows = [r[0] for v, r in _table(app).items() if (v in DESK or not desk) and r[0] > 0]
    return max(rows) if rows else None


PHONE_KINDS = ("phone_chat_op", "phone_button", "phone_answered", "phone_today_act")  # the phone app, used by you


def on_event(app: App, rec: dict) -> None:
    """Events that mean you used the phone app (modules/mind.py mirrors each event here)."""
    if str((rec or {}).get("kind") or "") in PHONE_KINDS:
        owner_here(app, "phone")


__all__ = ["owner_here", "last", "on", "on_event", "EVENT", "VIAS", "DESK"]

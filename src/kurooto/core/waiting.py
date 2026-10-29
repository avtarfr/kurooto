"""What waits for you, on one page (0.9.1): the dashboard's Waiting page, opened from the being's held count
(look.being_held_link) or the board's pages.

- The messages Calm holds (core/calm.py held_rows: the same list the phone's Today counts), each in full with why it
  waits; Send now sends them all (Calm.send_held, as the evening bundle would).
- The "while you were away" card (face.away.summary, modules/face): the pop-ups held while you were away and the talk
  box's answers that came meanwhile; its Send now shows the held pop-ups (Face.show_away).
- How many proposals wait for your tap and open questions (counts only; their own pages answer them).

Everything here is read on this computer and shown only on the dashboard; nothing is sent anywhere.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from kurooto.core.config import register_defaults

if TYPE_CHECKING:
    from kurooto.app import App

register_defaults("look", {"being_held_link": True})  # 0.9.1: the being's held count opens the Waiting page


def on(app: App) -> bool:
    return bool(app.settings.get("look.being_held_link", True))


def view(app: App) -> dict:
    if not on(app):
        return {"off": True}
    out: dict = {"held": [], "card": None, "proposals": 0, "questions": 0}
    calm = getattr(app, "calm", None)
    if calm is not None:
        try:
            out["held"] = calm.held_rows()
        except Exception as e:
            app.events.emit("waiting_failed", part="held", error=type(e).__name__)
    face = app.modules.get("face") if app.is_on("face") else None
    card = getattr(face, "away_card", None) if face is not None else None
    if card:
        out["card"] = {k: card.get(k) for k in ("at", "since", "popups", "answers", "shown")}
    try:
        from kurooto.core import proposals

        out["proposals"] = len(proposals.waiting(app))
    except Exception:
        pass
    try:
        out["questions"] = len(app.ask.pending())
    except Exception:
        pass
    return out


def send_held(app: App) -> str:
    calm = getattr(app, "calm", None)
    return calm.send_held() if calm is not None else "Nothing is waiting."


def show_away(app: App) -> str:
    face = app.modules.get("face") if app.is_on("face") else None
    if face is None or not hasattr(face, "show_away"):
        return "Nothing waits from while you were away."
    n = face.show_away()
    return f"Showed {n} pop-up{'s' if n != 1 else ''}." if n else "Cleared."

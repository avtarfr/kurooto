"""kurooto_now (0.9.0, L124, face.tools): where you are right now, in coarse words, for every AI and for calls.

At the desk or away and since when (Face presence's arrivals and departures), on a call or not, where Kurooto's
messages reach you, Voice ID's last verdict as its word, Brain's plan line (mind/plans) and the camera's state as the
Face page says it. Never pictures, who else is in view, a mood, Brain's read, tone or a sense reading (R7). It only
reports: nothing here decides or authorises anything (core/tap.py stays the only way to approve), which is why it
lives apart from core/tools.py (tests/unit/test_face.py keeps Face out of the tool and tap code).
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

from kurooto.modules.calls.tools import Tool

if TYPE_CHECKING:
    from kurooto.app import App

DESK_EVENTS = {"face_arrived": True, "face_back": True, "face_left": False}  # Face presence's comings and goings


def _clock_word(ts: str) -> str:
    try:
        t = dt.datetime.fromisoformat(ts).replace(tzinfo=None)
    except (TypeError, ValueError):
        return ""
    return f"{t:%H:%M}" if t.date() == dt.date.today() else f"{t:%a %H:%M}"


def now_view(app: App) -> dict:
    """kurooto_now's answer: coarse words only (R7). The desk from Face presence's arrivals and departures (and its
    watcher being away), the camera as Face.line() says it, a call from core/availability, the channel its messages
    take, Voice ID's last verdict as its word, and Brain's plan line (mind/plans: the milestone most at risk)."""
    out: dict = {}
    face = app.modules.get("face")
    if face is not None and app.is_on("face"):
        out["camera"] = face.line()
        last = next((e for e in reversed(app.events.tail(3000)) if e.get("kind") in DESK_EVENTS), None)
        w = getattr(face, "watcher", None)
        if last is not None:
            here = DESK_EVENTS[last["kind"]] and getattr(w, "state", "") != "away"
            since = _clock_word(last.get("ts", ""))
            out["desk"] = ("at the desk" if here else "away from the desk") + (f" since {since}" if since else "")
        else:
            out["desk"] = "away from the desk" if getattr(w, "state", "") == "away" else "not seen yet"
    else:
        out["camera"], out["desk"] = "Face presence is off", "not known (Face presence is off)"
    from kurooto.web.tools_api import live_call

    try:
        out["call"] = "on a call" if live_call(app) else "not on a call"
    except Exception:
        out["call"] = "not known"
    chans = app.notifier.channels
    tg, chat = "telegram" in chans, "chat" in chans and (app.app_main() or app.settings.get("notify.app_chat"))
    where = [w for w, on in (("Telegram", tg), ("the phone app's chat", chat)) if on]
    out["messages_go_to"] = " and ".join(where) or "this computer's notifications"
    vo = app.modules.get("voice")
    if vo is not None and app.is_on("voice"):
        word = getattr(getattr(vo, "voiceid", None), "last_word", "") or ""
        out["voice_id"] = word or "nothing heard yet"
    from kurooto.mind import plans  # "" with Brain or its plans off

    plan = plans.line(app)
    if plan:
        out["plan"] = plan
    return out


def now_tools(app: App) -> list[Tool]:
    if not app.settings.get("face.tools"):
        return []
    return [
        Tool(
            "kurooto_now",
            "Where they are right now, in a few words: at the desk or away and since when, on a call or not, where "
            "your messages reach them, Voice ID's last verdict, Brain's plan line and the camera's state.",
            lambda a: now_view(app),
            writes=False,
            hint="For 'am I at my desk?', 'is the camera on?' or before deciding how to reach them, call kurooto_now.",
        )
    ]

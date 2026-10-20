"""Try it: a chat box on the setup page, shown once your AI answers its test, so the first "remind me in 2 minutes"
works a minute later, before Telegram is set up. What you type there goes through the same handler as a Telegram
message (App.handle); the answers come back to the page and nowhere else: not to Telegram, not to your phone.

Chat and Reminders answer there even while they're off (they're turned on with Telegram, a step later); every other
feature answers only if it's on, as on Telegram. A reminder set there pops up on this computer's desktop (or on
Telegram, if it's connected by then). Requests for the AI go to the AI you picked, like any message.

    POST /api/tryit {text}   -> {ok, replies: [text, ...], job}   (a job's answer: GET /api/job?id=)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from kurooto import providers
from kurooto.modules.base import Incoming

if TYPE_CHECKING:
    from kurooto.app import App

TRY = ("chat", "reminders")  # answer in the box even while they're off
MAX_CHARS = 2000


def say(app: App, text: str) -> tuple[int, dict]:
    text = str(text or "").strip()[:MAX_CHARS]
    if not text:
        return 400, {"ok": False, "error": "Type something first."}
    main = app.settings.get("brain.main")
    brain = providers.build(app, main) if main else None
    ok, why = brain.available() if brain else (False, "no AI picked yet")
    if not ok:
        return 409, {"ok": False, "error": f"Your AI isn't working yet ({why}): test it first."}
    replies: list[str] = []
    msg = Incoming(text=text, via="setup", respond=lambda t, buttons=None: replies.append(str(t)))
    extra = [m for m in (app.modules.get(x) for x in TRY) if m is not None and not app.is_on(m.id) and m.ready()[0]]
    app.handle(msg, also=extra)
    jid = getattr(msg, "job", None)
    app.events.emit("tryit_said", job=bool(jid))
    return 200, {"ok": True, "replies": [] if jid else replies, "job": jid}

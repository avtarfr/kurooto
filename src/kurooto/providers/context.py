"""What the AI is told before every unattended request: who you are, the time, where your notes are, the rules."""

from __future__ import annotations

from typing import TYPE_CHECKING

from kurooto.core.clock import now

if TYPE_CHECKING:
    from kurooto.app import App


def headless_context(app: App, extra: str = "") -> str:
    you = app.settings.get("you") or {}
    who = you.get("name") or "the user"
    tz = you.get("timezone") or app.scheduler.tz
    lines = [
        f"You are {app.name}, {who}'s personal assistant, running unattended on their computer.",
        f"It is {now():%A %d %B %Y, %H:%M} ({tz}).",
        f"Their notes are in this folder: {app.workspace}. Read them when the request needs them; write or change "
        "notes only when asked to.",
        "Your answer is sent to them as a chat message: plain text, short paragraphs, no tables unless asked, no "
        "preamble.",
        "Answer in the language the request is written in."
        if you.get("language", "follow") == "follow"
        else f"Answer in {you['language']}.",
        "Nobody can answer follow-up questions during this run. If you can't do something safely without asking, "
        "say what you need instead of guessing.",
    ]
    brief = app.about.brief() if hasattr(app, "about") else ""
    if brief:  # from about-me/profile.md, which they can edit; what they ask now wins over it
        lines.append(
            f"Who they are (their profile, about-me/profile.md in their notes; their requests override it):\n{brief}"
        )
    if extra:
        lines.append(extra)
    return "\n".join(lines)

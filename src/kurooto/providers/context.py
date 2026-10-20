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
        f'You can act through {app.name}\'s tools (in agent programs, the MCP server "kurooto"): reminders, calls, '
        "deadlines, adding to notes and more, depending on the features they turned on. Use them when the request "
        "asks for an action. Notes they wrote are theirs: add to them or create new ones, never reword or remove "
        "their text.",
        "Never say you did something you didn't: if there was no tool for it or a tool failed, say so plainly.",
    ]
    brief = app.about.brief() if hasattr(app, "about") else ""
    from kurooto.core import layout

    if brief:  # from about-me/profile.md, which they can edit; what they ask now wins over it
        lines.append(
            f"Who they are (their profile, {layout.rel(app, 'profile')} in their notes; their requests override it):"
            f"\n{brief}"
        )
    from kurooto.modules.remember import help_brief, help_rel

    helps = help_brief(app)
    if helps:  # what they told Kurooto (and approved from the nightly look back); they edit it, so it wins
        lines.append(
            f"How they like to be helped ({help_rel(app)} in their notes; follow it, their requests win):\n{helps}"
        )
    where = layout.describe(app)  # their own notes layout and files folder, if they chose one (core/layout.py)
    if where:
        lines.append(where)
    if extra:
        lines.append(extra)
    return "\n".join(lines)

"""The day's note and the AI work around it, shared by check-ins, the alarm, the Sunday review, the study tracker and
after-class notes.

Your daily note is journal/<YYYY-MM-DD>.md in your notes folder. Kurooto only ever adds to it: a new section at the end
("## Study hours", "## Evening check-in"), never changing what's there. The plan for the day is the newest "## Plan…"
section (the draft written before your alarm, or the one you settled on the morning call).

Work for the AI goes through a skill (journal, study-log, morning-prep, morning): the AI follows the skill's steps. With
Chat off there's no AI, so callers keep your own words instead.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from typing import TYPE_CHECKING

from kurooto.core.clock import now

if TYPE_CHECKING:
    from kurooto.app import App

# Used only when the skills feature isn't there to give the real instructions.
FALLBACK = {
    "journal": "Add my words to today's daily note (journal/<today>.md in my notes; create it with a '# <date>' title "
    "if missing) as a new section '## Journal (HH:MM)': my words verbatim, fixing nothing but obvious typos. After it, "
    "a short '### Links' list to notes of mine that I mention, one line each with a reason. Never change or delete "
    "what's already in the note. Leave out health, money and private details about other people.\n\nMy words:\n{args}",
    "study-log": "Log my classes into my notes. For each class: a lecture note <subject-slug>/<YYYY-MM-DD>-<topic>.md "
    "with '## Covered' (what I said was covered, faithfully; nothing invented), '## My notes' (my words verbatim), "
    "'## Unclear / to ask' and '## Files' (the files below, linked). Then add one line per class under '## Studied' in "
    "today's daily note (journal/<today>.md), linking the lecture note. Never change what's already written.\n\n{args}",
    "morning-prep": "Before my alarm: draft today's plan. Read my notes (today's and yesterday's daily notes in "
    "journal/, my subjects' notes and deadlines) and add '## Plan for today (draft, HH:MM)' to today's daily note "
    "(journal/<today>.md; create it if missing) with: Classes today, Due soon, Top 3 (with one-line reasons), "
    "Suggested blocks (a rough time-blocked day around the classes), and Questions for the morning (always: which "
    "classes I'm skipping, and when to call me today). Runs unattended: ask nothing, write the draft. Never change "
    "what's already in the note.\n\n{args}",
    "morning": "Finalise today's plan from the draft ('## Plan for today (draft…)' in journal/<today>.md) and what I "
    "said: add '## Plan for today' with Top 3, a time-blocked schedule around my classes, and 'If there's time'. Keep "
    "the draft as it is. Never write my energy, sleep or health into the note.\n\nWhat I said:\n{args}",
}


def note_path(app: App, day: dt.date | None = None) -> Path:
    return app.workspace / "journal" / f"{(day or now().date()).isoformat()}.md"


def append(app: App, heading: str, body: str, day: dt.date | None = None) -> Path:
    """Add "## heading" with body at the end of the day's note (made if missing); what's there stays as it is."""
    day = day or now().date()
    f = note_path(app, day)
    f.parent.mkdir(parents=True, exist_ok=True)
    new = not f.exists()
    with open(f, "a", encoding="utf-8") as out:
        if new:
            out.write(f"# {day.isoformat()}\n")
        out.write(f"\n## {heading}\n\n{body.strip()}\n")
    return f


def sections(text: str, prefix: str) -> list[str]:
    """Every "## <prefix>…" section of a note (heading line included), in order."""
    out = []
    for m in re.finditer(rf"^##\s+{re.escape(prefix)}.*$", text, re.M | re.I):
        nxt = re.compile(r"^#{1,2}\s", re.M).search(text, m.end())
        out.append(text[m.start() : nxt.start() if nxt else len(text)].strip())
    return out


def has_section(app: App, prefix: str, day: dt.date | None = None) -> bool:
    f = note_path(app, day)
    return f.is_file() and bool(sections(f.read_text(encoding="utf-8", errors="replace"), prefix))


def plan(app: App, day: dt.date | None = None, limit: int = 4000) -> str:
    """The day's plan: the newest "## Plan…" section of its daily note, or "" if there isn't one."""
    f = note_path(app, day)
    if not f.is_file():
        return ""
    found = sections(f.read_text(encoding="utf-8", errors="replace"), "Plan")
    return found[-1][:limit] if found else ""


def ai_on(app: App) -> bool:
    """Is there an AI to hand work to? (Chat is on.)"""
    return app.is_on("chat")


def run_skill(
    app: App,
    name: str,
    args: str = "",
    *,
    title: str | None = None,
    files: list[Path] | None = None,
    quiet: bool = False,
    then: str | None = None,
    then_payload: dict | None = None,
    background: bool = False,
    reply_to=None,
) -> str | None:
    """Hand work to the AI through a skill. Returns the job id, or None when there's no AI (Chat is off)."""
    sk = app.modules.get("skills")
    if sk is not None and app.is_on("skills"):
        return sk.run(
            name,
            args=args,
            reply_to=reply_to,
            then=then,
            then_payload=then_payload,
            quiet=quiet,
            background=background,
            files=files,
            title=title,
        )
    if not ai_on(app):
        return None
    prompt = None
    try:
        from kurooto.modules.skills import skill_prompt  # the skills feature's own instructions, even when it's off
    except ImportError:
        skill_prompt = None
    if skill_prompt is not None:
        try:
            prompt = skill_prompt(app, name, args, files)
        except Exception:
            prompt = None
    if not prompt:
        prompt = FALLBACK.get(name, "{args}").replace("{args}", args)
        if files:
            prompt += "\n\nFiles (in my notes folder): " + ", ".join(rel(app, f) for f in files)
    return app.jobs.submit(
        prompt,
        title=title or name,
        reply_to=reply_to,
        quiet=quiet,
        then=then,
        then_payload=then_payload,
        background=background,
    )


def rel(app: App, f: Path | str) -> str:
    """A file's path inside the notes folder ("inbox/photo.jpg"), or as it is if it's elsewhere."""
    p = Path(f)
    try:
        return p.resolve().relative_to(app.workspace.resolve()).as_posix()
    except ValueError:
        return str(p)


def their_words(app: App, lines: list[dict]) -> str:
    """Your side of a call transcript, one line per turn."""
    ai = app.name
    return "\n".join(x.get("text", "").strip() for x in lines if x.get("who") != ai and x.get("text", "").strip())


def transcript(app: App, lines: list[dict], limit: int = 30000) -> str:
    """Both sides of a call, "Name: what they said" per turn (for the AI, which needs the questions too)."""
    you = app.settings.get("you.name") or "Me"
    ai = app.name
    out = "\n".join(
        f"{ai if x.get('who') == ai else you}: {x.get('text', '').strip()}" for x in lines if x.get("text", "").strip()
    )
    return out[-limit:]

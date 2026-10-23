"""Remember: tell Kurooto how you like to be helped ("remember that I hate calls before 8") and it keeps it.

What you tell it goes into your notes, in about-me/how-to-help-me.md (or where your notes layout keeps it), which you
can read and edit like any note: your edits win, and Kurooto never rewords or removes a line (except taking out one
it added itself, when you tap that line's Undo). A short version of that note goes along with every AI request
Kurooto makes, next to the "In brief" part of your profile. The nightly look back adds lines there too, but only the
ones you approve, or, with Learns from its own work on, facts you stated (keep(), under PICKED, each with an Undo).

It won't keep health, money or password details: those would travel with every AI request. Reminders and your own
notes are the place for them.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from kurooto.core import layout
from kurooto.core.clock import now
from kurooto.modules.base import Command, Incoming, Intent, Module
from kurooto.modules.calls.tools import Tool, arg

if TYPE_CHECKING:
    from pathlib import Path

    from kurooto.app import App

HELP_NOTE = "about-me/how-to-help-me.md"  # in the default notes layout; help_file() / help_rel() say where it is
TOLD = "You told me"
PICKED = "Picked up from your chats and calls"  # what Learns from its own work keeps by itself (modules/learning.py)
INTRO = (
    "# How to help me\n\n"
    "What {name} has learned about how you like to be helped. Edit it freely: what you write here wins, and {name} "
    "reads it before every AI request. It never rewords or removes a line.\n"
)
MAX_FACT = 300
REMEMBER = re.compile(r"^\s*(?:please\s+)?(?:remember|keep in mind)(?:\s+that\b|\s*:)\s*(?P<fact>.+?)\s*$", re.I)
SENSITIVE = {
    "health": re.compile(
        r"\b(?:health|medic(?:al|ine|ation)s?|meds|diagnos\w*|illness|disease|disorder|symptoms?|therap(?:y|ist)|"
        r"doctor|hospital|prescri\w+|pregnan\w*|allerg\w*|depress\w*|anxiety|adhd|insulin|blood (?:pressure|sugar)|"
        r"mental health|surgery|pills?)\b",
        re.I,
    ),
    "money": re.compile(
        r"\b(?:bank|salary|income|loans?|debts?|credit cards?|debit cards?|card number|account number|iban|"
        r"invest\w*|stocks|crypto|tax(?:es)?|rent|savings|net worth|money)\b|[$€£₹¥]\s*\d",
        re.I,
    ),
    "credentials": re.compile(
        r"\b(?:passwords?|passcodes?|passphrase|pin (?:code|number)|otp|api[ -]?keys?|tokens?|secrets?|log-?ins?|"
        r"usernames?|recovery (?:code|phrase)|seed phrase|social security|passport (?:number|no)|id number)\b",
        re.I,
    ),
}
REFUSE = (
    "I'd rather not keep that: {what} details would go along with every AI request. Your own notes (or a reminder) "
    "are a better place for it."
)
WHAT = {"health": "health", "money": "money", "credentials": "password and login"}


def sensitive(text: str) -> str | None:
    """Which kind of detail Kurooto won't keep ("health", "money", "credentials"), or None."""
    return next((k for k, rx in SENSITIVE.items() if rx.search(text or "")), None)


def help_file(app: App) -> Path:
    return layout.path(app, "how_to_help")


def help_rel(app: App) -> str:
    """The note's place in your notes, for messages ("about-me/how-to-help-me.md")."""
    return layout.rel(app, "how_to_help")


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", re.sub(r"\(\d{4}-\d{2}-\d{2}[^)]*\)", "", s.lower())).strip()


def has_line(text: str, line: str) -> bool:
    """Is this (or the same words) already a line of the note?"""
    want = _norm(line)
    return bool(want) and any(_norm(ln.lstrip("-* ")) == want for ln in text.splitlines())


def add_line(app: App, section: str, line: str) -> bool:
    """Add "- line" at the end of the note's "## section" (made if missing). False if it's there already. Nothing
    else in the note changes."""
    from kurooto.core.tools import add_to_section

    f = help_file(app)
    head = layout.frontmatter(app, "how_to_help", f, title="How to help me", bare=True)
    text = f.read_text(encoding="utf-8", errors="replace") if f.exists() else head + INTRO.format(name=app.name)
    if has_line(text, line):
        return False
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(add_to_section(text, section, f"- {line}"), encoding="utf-8")
    return True


def remove_line(app: App, line: str) -> bool:
    """Take out one line Kurooto added ("- line", exactly as it was written), for an Undo. False if it isn't there
    as written any more (you changed or removed it): then nothing changes."""
    f = help_file(app)
    try:
        text = f.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    lines = text.split("\n")
    want = f"- {line}".rstrip()
    hit = next((i for i, ln in enumerate(lines) if ln.rstrip() == want), None)
    if hit is None:
        return False
    from kurooto.core.tools import write_note_file

    write_note_file(f, "\n".join(lines[:hit] + lines[hit + 1 :]))
    return True


def keep(app: App, fact: str, via: str = "telegram", section: str = TOLD) -> tuple[str, str]:
    """Keep one fact by Remember's rules: one short line, never health, money or password details, never twice. It
    goes at the end of "## section" with today's date. (status, detail): "kept" and the line as written; "refused"
    and which kind of detail; "known"; "empty"; "long"."""
    fact = re.sub(r"\s+", " ", str(fact or "")).strip().rstrip(".")
    if not fact:
        return "empty", ""
    if len(fact) > MAX_FACT:
        return "long", ""
    kind = sensitive(fact)
    if kind:
        app.events.emit("remember_refused", what=kind, via=via)
        return "refused", kind
    fact = fact[0].upper() + fact[1:]
    line = f"{fact} ({now():%Y-%m-%d})"
    if not add_line(app, section, line):
        return "known", ""
    app.events.emit("remembered", chars=len(fact), via=via)
    return "kept", line


def help_brief(app: App, limit: int = 1500) -> str:
    """The note without its title and the standard intro, for the AI's context; cut at `limit` characters."""
    try:
        text = help_file(app).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    text = re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.S)
    text = text.replace(INTRO.format(name=app.name), "")
    lines = [ln.rstrip() for ln in text.splitlines() if not re.match(r"^#\s", ln)]
    body = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    if not re.search(r"^\s*[-*]\s+\S|^[^#\s]", body, re.M):  # only headings left: nothing to tell
        return ""
    if len(body) > limit:
        body = body[:limit].rsplit("\n", 1)[0] + f"\n(…the rest is in {help_rel(app)})"
    return body


class Remember(Module):
    id = "remember"
    title = "Remember"
    description = (
        'Tell it how you like to be helped ("remember that I hate calls before 8"); it keeps that in your notes '
        "and every AI request follows it."
    )
    requires = ("telegram",)
    privacy = (
        "Kept in your notes (about-me/how-to-help-me.md); a short version goes along with each request to the AI you "
        "picked. Health, money and password details are refused."
    )

    def remember(self, fact: str, via: str = "telegram") -> str:
        status, detail = keep(self.app, fact, via)
        if status == "empty":
            return "What should I remember? e.g. /remember I hate calls before 8"
        if status == "long":
            return f"That's long for one line (keep it under {MAX_FACT} characters); your notes suit longer things."
        if status == "refused":
            return REFUSE.format(what=WHAT[detail])
        if status == "known":
            return "I know that already."
        return f"Noted in {help_rel(self.app)}: {detail.rsplit(' (', 1)[0]}."

    # ------------------------------------------------------------------------------------------ Telegram
    def commands(self):
        return [Command("remember", "keep how you like to be helped: /remember I hate calls before 8", self._cmd)]

    def _cmd(self, msg: Incoming, arg: str) -> str:
        if arg:
            return self.remember(arg, via=msg.via)
        brief = help_brief(self.app, limit=3000)
        if not brief:
            return 'Nothing yet. /remember <how you like to be helped>, or say "remember that ...".'
        return f"What I keep in mind ({help_rel(self.app)}; edit it any time):\n\n{brief}"

    def intents(self):
        def match(text: str):
            m = REMEMBER.match(text)
            return {"fact": m["fact"]} if m and not re.match(r"(?i)to\b", m["fact"]) else None

        return [Intent("remember", "remember how you like to be helped", match, lambda m, s: self.remember(s["fact"]))]

    def help(self):
        return ['"remember that …", /remember']

    # --------------------------------------------------------------------------------------------- calls
    def call_tools(self):
        return [
            Tool(
                "remember",
                "Keep a lasting preference they state about how to help them, in their words (e.g. 'no calls "
                "before 8'). Not for tasks or dates (use reminders). Health, money and passwords are refused.",
                lambda a: self.remember(str(a.get("fact", "")), via="call"),
                {"fact": arg("the preference, one short sentence")},
                ("fact",),
                offline="queue",
                hint='When they say "remember that ..." or state a lasting preference, call remember with it.',
            )
        ]

"""Skills from solved tasks (Brain, 0.8.0 stage 12): after a task with a verified outcome, the AI abstracts it into a
candidate skill, which enters the library only after its regression cases pass.

A *verified outcome* is code or the world saying it worked, never your liking it:
  - an applied proposal whose checks (the project's tests) passed, that was not undone within 48 hours.
Health and money are never made into skills, and a task about someone else's messages isn't either.

    verified(app)         the proposals that count, not yet distilled
    distill_one(app, ep)  ask the AI for a candidate, validate it, run its regression cases, admit it at always-ask
    nightly(app)          at most two a night
"""

from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING

from kurooto.core import proposals
from kurooto.core.state import jload, jsave
from kurooto.mind.skills import library

if TYPE_CHECKING:
    from kurooto.app import App

FILE = "mind-distilled.json"
SETTLE_S = 48 * 3600
PER_NIGHT = 2
SENSITIVE = re.compile(
    r"\b(health|medical|doctor|diagnos\w*|therap\w*|medicin\w*|bank|salary|invoice|payment|credit card|loan|tax(es)?|"
    r"whatsapp|password|passwd|token)\b",
    re.I,
)


def _seen(app: App) -> list[str]:
    return list((jload(app.paths.state / FILE, {}) or {}).get("ids", []))


def _mark(app: App, pid: str) -> None:
    ids = [*_seen(app), pid][-500:]
    jsave(app.paths.state / FILE, {"ids": ids})


def verified(app: App, now: float | None = None) -> list[dict]:
    """Applied proposals old enough to trust (48 h), still applied (not undone), whose checks didn't fail, that haven't
    been distilled and aren't about health, money or other people."""
    now = now or time.time()
    done = set(_seen(app))
    out = []
    for p in proposals.every(app):
        a = p.get("applied") or {}
        if p.get("status") != "applied" or p["id"] in done or now - float(a.get("at") or now) < SETTLE_S:
            continue
        checks = p.get("checks") or {}
        if checks.get("ran") and not checks.get("ok"):
            continue
        if SENSITIVE.search(f"{p.get('title', '')} {p.get('summary', '')} {p.get('request', '')}"):
            continue
        out.append(p)
    return out


def prompt_for(p: dict) -> str:
    return (
        "A task worked out: it was applied and has held for two days. Abstract it into a reusable skill that could "
        "do the same kind of task again. Answer with JSON only, with these keys: slug (lowercase words joined by "
        "hyphens), title, when (when to use it), inputs (a list of lowercase names), steps (short numbered steps), "
        "kind "
        '("prompt"), template (the prompt, using {name} for each input), cases (at least two: each {inputs: {name: '
        "value}, expect: {contains: [words the answer must have], not_contains: [words it must not]}}). Do not copy "
        "private details into the cases.\n\n"
        f"Task: {p.get('request') or p.get('title')}\nWhat changed: {p.get('summary')}\nFiles: "
        + ", ".join(str(f.get("path")) for f in (p.get("files") or [])[:8])
    )


def ask_json(app: App, prompt: str, title: str):
    from kurooto.mind.lab.runner import ask_json as ask

    return ask(app, prompt, title)


def distill_one(app: App, p: dict, asker=None, runner=None) -> tuple[str | None, str]:
    """(slug, "") when a skill was admitted; (None, why) otherwise. The episode is marked either way: one try each."""
    raw = (asker or ask_json)(app, prompt_for(p), "Skill: distil a task")
    _mark(app, p["id"])
    if raw is None:
        return None, "the AI gave no candidate"
    slug, why = library.admit(
        app, raw, {"source": "episode", "proposal": p["id"], "applied": (p.get("applied") or {}).get("at")}, runner
    )
    if slug:
        app.notify(
            f"I learned a new skill from a task that worked: {raw.get('title') if isinstance(raw, dict) else slug}. "
            "It asks before it runs until you say otherwise.",
            kind="info",
            why="mind.skill_learned",
        )
    return slug, why


def nightly(app: App, payload: dict | None = None) -> list[str]:
    if not library.on(app):
        return []
    out = []
    for p in verified(app)[:PER_NIGHT]:
        slug, _ = distill_one(app, p)
        if slug:
            out.append(slug)
    return out


__all__ = ["verified", "distill_one", "nightly", "prompt_for"]

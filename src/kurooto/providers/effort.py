"""How hard should the AI think about a request? low, medium or high.

In order: a "high:" / "low:" prefix you typed; notes to study from (always high); a quick classifier (a small
local model, or the brain itself) if one is set up; otherwise medium. Anything that changes, schedules or
remembers something is never treated as a quick lookup.
"""

from __future__ import annotations

import re
from collections.abc import Callable

FORCED = re.compile(r"^(low|medium|med|high)\s*:\s*", re.I)
NOTES = re.compile(
    r"\b(notes?|study (material|guide|sheet)s?|revision|revise|cheat ?sheet|summar(y|ies|ise|ize)|explain|"
    r"teach me|derive|derivation|proofs?|exam prep)\b",
    re.I,
)
ACTS = re.compile(r"\b(remember|update|change|schedule|add|create|move|set|write|file|plan|delete|remind)\b", re.I)
CRITERIA = {
    "low": "a quick lookup or short factual answer: what is due, when is something, find a note, a yes/no",
    "medium": "a summary or plan from a few notes: summarise a lecture, plan my day, list what to revise",
    "high": "deep work: explain or derive maths, compare ideas, research, writing or restructuring many notes",
}
QUESTION = (
    "How much reasoning does an assistant with access to the user's notes need for this request? Answer with "
    "exactly one word: low, medium or high.\n" + "\n".join(f"{k}: {v}" for k, v in CRITERIA.items()) + "\n\nRequest: "
)


def strip_forced(prompt: str) -> tuple[str | None, str]:
    m = FORCED.match(prompt)
    if not m:
        return None, prompt
    level = m[1].lower()
    return ("medium" if level == "med" else level), prompt[m.end() :]


def pick(prompt: str, classify: Callable[[str], str | None] | None = None) -> str:
    level, prompt = strip_forced(prompt)
    if level:
        return level
    if NOTES.search(prompt):
        return "high"
    choice = None
    if classify:
        try:
            raw = (classify(QUESTION + prompt[:2000]) or "").strip().lower()
            choice = next((w for w in re.findall(r"[a-z]+", raw) if w in CRITERIA), None)
        except Exception:
            choice = None
    choice = choice or "medium"
    if choice == "low" and ACTS.search(prompt):
        choice = "medium"
    return choice

"""Graders: code first, and for what needs judgement a judge that is not the author.

`grade(instance, answer)` runs the task type's code grader. `choose_judge(producer, providers)` picks a provider other
than the one
that wrote the answer; `blind_pair(a, b, rng)` shuffles two answers behind the labels "A" and "B" so the judge can't
tell which
version is which, and `unblind` maps its pick back. A judged family would run `judge_prompt` through `choose_judge`'s
provider.
None of the first eleven task types needs one; the machinery is here, tested, for those that will.
"""

from __future__ import annotations

import random

from kurooto.mind.harness.tasks import TASK_TYPES


def grade(inst: dict, answer) -> float:
    t = TASK_TYPES[inst["type"]]
    try:
        return max(0.0, min(1.0, float(t.grade(answer, inst["key"]))))
    except Exception:  # a grader that can't read an answer scores it 0, never raises into the run
        return 0.0


def choose_judge(producer: str, providers: list[str]) -> str | None:
    """A provider other than the one that produced the answer (None when there's no other: then the answer isn't
    judged)."""
    others = [p for p in providers if p and p != producer]
    return others[0] if others else None


def blind_pair(a: str, b: str, rng: random.Random) -> tuple[dict[str, str], dict[str, str]]:
    """({"A": text, "B": text} in a random order, and which of the real ones each label is: {"A": "a"|"b", ...})."""
    flip = rng.random() < 0.5
    first, second = (b, a) if flip else (a, b)
    return {"A": first, "B": second}, {"A": "b" if flip else "a", "B": "a" if flip else "b"}


def judge_prompt(question: str, shown: dict[str, str]) -> str:
    return (
        "You are judging two answers to the same question. You don't know who wrote either. "
        "Reply with the single letter of the better one, A or B.\n\n"
        f"Question: {question}\n\nAnswer A:\n{shown['A']}\n\nAnswer B:\n{shown['B']}\n\nBetter:"
    )


def unblind(letter: str, mapping: dict[str, str]) -> str | None:
    return mapping.get(letter.strip().upper()[:1])

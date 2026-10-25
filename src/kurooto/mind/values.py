"""Learned values (Brain, 0.8.0 stage 05): tabular TD(0) over the kinds of thing Kurooto does.

    V(s)    how good a situation is, from the rewards that followed it: V(s) += alpha * delta,
            delta = r + gamma * V(s') - V(s), gamma 0.9, alpha 0.1; delta is logged each tick
    Q(s,a)  how good an action class is in a situation, updated only from actions that registered a claim first
            (stage 01 decision records), as the outcome minus the baseline (the tonic reward until a holdout exists)

The state s is a small tuple: which variable has the largest share of the drive, the time of day (a 6 hour band) and
whether
you're at the computer. Shadow first: for `mind.values.shadow_days` (21) after Brain's learning starts, values update
but
never affect a choice; after that they only rank candidates the gate and the autonomy budget (stage 06) already allow.
Learning stops while `learning_frozen` is set (the nightly self-checks, or the weekly verdict disagreeing with the sum
of rewards for two weeks).
"""

from __future__ import annotations

PART = "values"  # its switch: mind.values.on (with mind.budget.on)

ALPHA = 0.1
GAMMA = 0.9
SHADOW_DAYS = 21
BANDS = (("night", 0, 6), ("morning", 6, 12), ("afternoon", 12, 18), ("evening", 18, 24))


def band(hour: int) -> str:
    return next(name for name, lo, hi in BANDS if lo <= hour % 24 < hi)


def state(top_var: str | None, hour: int, at_computer: bool) -> str:
    return f"{top_var or 'none'}|{band(hour)}|{'at' if at_computer else 'away'}"


def klass(action: str) -> str:
    """An action's class: its kind and what it's about ("message:deadline.call" -> "message:deadline"), at most 40
    chars."""
    kind, _, what = str(action or "other").partition(":")
    return f"{kind}:{what.split('.')[0]}"[:40] if what else kind[:40]


def td_update(v: float, r: float, v_next: float, alpha: float = ALPHA, gamma: float = GAMMA) -> tuple[float, float]:
    """(the new V(s), delta)."""
    delta = r + gamma * v_next - v
    return v + alpha * delta, delta


def q_update(q: float, outcome: float, baseline: float, alpha: float = ALPHA) -> float:
    """Q(s,a) moves toward the outcome minus the baseline (what would have happened anyway)."""
    return q + alpha * ((outcome - baseline) - q)


def in_shadow(now: float, started: float | None, days: float = SHADOW_DAYS) -> bool:
    return started is None or now - started < days * 86400


def rank(candidates: list[str], q: dict[str, float]) -> list[str]:
    """Candidates best first by Q, ties and unknowns in the order given (only used once the shadow period is over)."""
    order = {c: i for i, c in enumerate(candidates)}
    return sorted(candidates, key=lambda c: (-q.get(c, 0.0), order[c]))

"""The reward (Brain, 0.8.0 stage 05): r_t = D(t) - D(t+1), the fall of the drive, in [-1, 1] with what doesn't fit
carried to the next tick. A reward module:
it may import only the reward sources and the mind's plumbing (whitelist.py, invariant I-3), so every input arrives as
an argument.

    step            one reward: the drive before, recomputed under today's setpoints, minus the drive now. Moving a
                    setpoint pays 0 (I-4); creating a deficit and then fixing it nets exactly 0 (a potential difference
                    telescopes); nothing is paid inside a stop span (I-5).
    NegativeState   the running negative mood: an EMA of the negative rewards, capped at -0.6, decaying with a 24 hour
                    half-life when nothing new is negative. Being ignored is not a variable, so it can't cause it (I-3).
    Tonic           the 7 day EMA of r (live time only: the stage 02 Integrator), which sets exploration and arousal.

Credit (who gets it) is decided by the scorekeeper, not here: a change you caused yourself updates values only; the
policy learns only from actions that registered a claim first.
"""

from __future__ import annotations

import math

from kurooto.mind import budget

PART = "budget"  # its switch: mind.budget.on
REWARD = True

CAP = -0.6
HALF_LIFE_S = 24 * 3600.0
TONIC_TAU_S = 7 * 86400.0


def step(prev_x: dict, x: dict, setp_now: dict, frozen: bool = False) -> float:
    """The raw fall of the drive for one tick, unclipped (see clip_carry). `prev_x` is scored under the setpoints of
    now, so a moved bar pays 0."""
    if frozen:
        return 0.0
    return budget.drive(prev_x, setp_now) - budget.drive(x, setp_now)


def clip_carry(raw: float, carry: float = 0.0) -> tuple[float, float]:
    """r in [-1, 1] and what's left over for the next tick. Clipping each tick by itself would break the telescoping
    that makes a deficit created and then fixed net exactly 0 (a drop of 1.5 then two recoveries of 0.75 would pay
    +0.5): the part that doesn't fit is carried, so the rewards always sum to the fall of the drive (I-4)."""
    total = raw + carry
    r = budget.clip(total)
    return r, total - r


class NegativeState:
    """value in [CAP, 0]: how bad things have been lately. Decays toward 0 with a 24 hour half-life of live time."""

    def __init__(self, value: float = 0.0, at: float | None = None):
        self.value = min(0.0, max(CAP, value))
        self.at = at

    def update(self, t: float, r: float, live_s: float | None = None) -> float:
        dt = (t - self.at) if self.at is not None else 0.0
        if live_s is not None:
            dt = live_s
        if dt > 0:
            self.value *= 0.5 ** (dt / HALF_LIFE_S)
        if r < 0:
            self.value = max(CAP, self.value + r)  # each negative reward deepens it, down to the cap
        self.at = t
        return self.value


def ema(prev: float | None, x: float, live_s: float, tau_s: float = TONIC_TAU_S) -> float:
    """One step of an exponential average over live time."""
    if prev is None:
        return x
    keep = math.exp(-max(0.0, live_s) / tau_s)
    return keep * prev + (1 - keep) * x

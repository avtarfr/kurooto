"""The reward (Brain, 0.8.0 stage 05): r_t = D(t) - D(t+1), the fall of the drive, in [-1, 1] with what doesn't fit
carried to the next tick. A reward module:
it may import only the reward sources and the mind's plumbing (whitelist.py, invariant I-3), so every input arrives as
an argument.

    step            one reward: the drive before, recomputed under today's setpoints, minus the drive now. Moving a
                    setpoint pays 0 (I-4); creating a deficit and then fixing it nets exactly 0 (a potential difference
                    telescopes); nothing is paid inside a stop span (I-5).
    Mood            the running mood M in [-1, 1], with soft walls (0.8.8, the owner's change: no cap): each reward
                    moves it M <- tanh(atanh(M) + A * r), so it gets harder to move the further out it is and can
                    reach the ends; lows and highs decay toward 0 with a 3 day half-life of live time. Being talked
                    to moves it only through the small bounded talk reward (mind/talk.py, I-3').
    Tonic           the 7 day EMA of r (live time only: the stage 02 Integrator), which sets exploration and arousal.

Credit (who gets it) is decided by the scorekeeper, not here: a change you caused yourself updates values only; the
policy learns only from actions that registered a claim first.
"""

from __future__ import annotations

import math

from kurooto.mind import budget

PART = "budget"  # its switch: mind.budget.on
REWARD = True

A = 0.5  # how far one reward moves the mood, in atanh units
HALF_LIFE_S = 3 * 86400.0  # lows and highs fade over days, not hours
EDGE = 1.0 - 1e-12  # atanh is guarded here: M can sit at the ends without becoming infinite
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


def _atanh(m: float) -> float:
    return math.atanh(max(-EDGE, min(EDGE, float(m))))


def soft(m: float, push: float) -> float:
    """One soft-walled move: tanh(atanh(M) + push), in [-1, 1]."""
    return max(-1.0, min(1.0, math.tanh(_atanh(m) + push)))


class Mood:
    """M in [-1, 1]: how things have been lately (low below 0, high above). No cap: soft walls instead."""

    def __init__(self, value: float = 0.0, at: float | None = None):
        self.value = max(-1.0, min(1.0, float(value)))
        self.at = at

    def decay(self, t: float, live_s: float | None = None) -> float:
        dt = (t - self.at) if self.at is not None else 0.0
        if live_s is not None:
            dt = live_s
        if dt > 0:
            self.value *= 0.5 ** (dt / HALF_LIFE_S)
        self.at = t
        return self.value

    def update(self, t: float, r: float, live_s: float | None = None, extra: float = 0.0) -> float:
        """Decay over the live time since the last update, then the reward's move (and `extra`, an input such as the
        body's hedonic tone, already scaled; never a reward)."""
        self.decay(t, live_s)
        if r or extra:
            self.value = soft(self.value, A * float(r) + float(extra))
        return self.value


def ema(prev: float | None, x: float, live_s: float, tau_s: float = TONIC_TAU_S) -> float:
    """One step of an exponential average over live time."""
    if prev is None:
        return x
    keep = math.exp(-max(0.0, live_s) / tau_s)
    return keep * prev + (1 - keep) * x

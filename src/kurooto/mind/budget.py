"""The body budget (Brain, 0.8.0 stage 05): a few variables about Kurooto's own state that it tries to keep near a
setpoint, and the drive: how far from them it is. Hunger and thirst, but for its promises, its health and how well it
foresees things. Nothing here is about how much you talk to it (invariant I-3): ignoring Kurooto is not a variable.

    promise_slack     the least slack over its open promises (hours to due minus hours of work), in [-1, 1]
    deadline_margin   the least slack on deadlines it has a claimed help act on, in [-1, 1] (none claimed: not measured)
    health            the share of its checks that are OK: disk free, backup age, call line, AI quota, crashes, its log
    forecast_skill    the 14-day mean of stage 04's skill scores

    D = sum_i w_i * softplus((s_i - x_i) / t_i) ** 2        over the variables that are measured

The setpoints s_i and tolerances t_i have defaults here. They change from your calendar (a deadline-heavy exam season
widens deadline_margin's tolerance) or from an approved /retro change, never from the AI that acts (invariant I-1: the
scorekeeper keeps them in its `setpoints` table).
"""

from __future__ import annotations

import math

PART = "budget"  # its switch: mind.budget.on

VARIABLES = ("promise_slack", "deadline_margin", "health", "forecast_skill")
DEFAULTS = {
    "promise_slack": {"s": 0.2, "t": 0.3},
    "deadline_margin": {"s": 0.3, "t": 0.3},
    "health": {"s": 0.95, "t": 0.15},
    "forecast_skill": {"s": 0.05, "t": 0.4},
}
WEIGHTS = {name: 1.0 for name in VARIABLES}
SEASON_TOLERANCE = 1.5  # exam season: deadline_margin may sit lower before it counts as a deficit
SLACK_SCALE_H = 24.0  # a day of slack is "plenty" (1.0), a day late is "very late" (-1.0)


def clip(v: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def slack(hours_to_due: float, hours_needed: float) -> float:
    """Slack as a number in [-1, 1]: (hours to due minus hours of work) over a day."""
    return clip((hours_to_due - hours_needed) / SLACK_SCALE_H)


def softplus(z: float) -> float:
    return z + math.log1p(math.exp(-z)) if z > 30 else math.log1p(math.exp(z)) if z > -30 else math.exp(z)


def setpoints(season: bool = False, overrides: dict | None = None) -> dict[str, dict[str, float]]:
    """The setpoints now: the defaults, a wider deadline_margin tolerance in exam season, then any approved changes."""
    out = {k: dict(v) for k, v in DEFAULTS.items()}
    if season:
        out["deadline_margin"]["t"] = round(out["deadline_margin"]["t"] * SEASON_TOLERANCE, 4)
    for k, v in (overrides or {}).items():
        if k in out and isinstance(v, dict):
            for f in ("s", "t"):
                if isinstance(v.get(f), (int, float)) and (f == "s" or v[f] > 0):
                    out[k][f] = float(v[f])
    return out


def terms(x: dict, setp: dict, w: dict | None = None) -> dict[str, float]:
    """Each measured variable's share of the drive."""
    w = w or WEIGHTS
    out = {}
    for k in VARIABLES:
        if x.get(k) is None or k not in setp:
            continue
        z = (setp[k]["s"] - float(x[k])) / max(setp[k]["t"], 1e-6)
        out[k] = w.get(k, 1.0) * softplus(z) ** 2
    return out


def drive(x: dict, setp: dict, w: dict | None = None) -> float:
    return sum(terms(x, setp, w).values())


def top(x: dict, setp: dict, w: dict | None = None) -> tuple[str | None, float]:
    """The variable with the largest share of the drive, and that share (0 when nothing is measured)."""
    t = terms(x, setp, w)
    total = sum(t.values())
    if not t or total <= 0:
        return None, 0.0
    name = max(t, key=t.get)
    return name, t[name] / total

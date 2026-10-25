"""Trust (Brain, 0.8.0 stage 06): how much Kurooto may do unasked, per class of action, learned from how you react. A
Beta(a, b) per risk class, kept by the scorekeeper in its `trust` table (invariant I-1: nothing else writes it).

    prior       R0 (9, 1)  R1 (4, 2)  R2 (2, 4)  R3 (1, 9)
    evidence    your explicit OK: a += 1 | silence: a += 0.3, only for an act in a digest you've seen | an undo: b +=
    3 |
                a complaint ("don't do that", Wrong): b += 5 -- each times the class's impact (R0 0.25, R1 1, R2 2, R3
                4)
    decay       both counts drift back toward the prior with a 30 day half-life
    the rule    act unasked only when the 10th percentile of Beta(a, b) is above the class's threshold
                (R0 0.5, R1 0.75, R2 0.9, R3 0.97); an undo also sets a 7 day cooldown on the class
Fast down, slow up: one undo outweighs ten silent passes. R3 can't be reached by a heap of trivial OKs (impact
weighting).
"""

from __future__ import annotations

import math

from kurooto.mind import risk

PART = "autonomy"  # its switch: mind.autonomy.on

HALF_LIFE_S = 30 * 86400.0
COOLDOWN_S = 7 * 86400.0
EVIDENCE = {"ok": ("a", 1.0), "silence": ("a", 0.3), "undo": ("b", 3.0), "complaint": ("b", 5.0)}


def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction for the incomplete beta function (Lentz's method)."""
    tiny = 1e-30
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 200):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 3e-12:
            break
    return h


def betainc(a: float, b: float, x: float) -> float:
    """The regularised incomplete beta function I_x(a, b): the Beta(a, b) cumulative distribution at x."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    ln = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1.0 - x)
    front = math.exp(ln)
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def percentile(a: float, b: float, p: float = 0.10) -> float:
    """The p-th percentile of Beta(a, b), by bisection on the cumulative distribution."""
    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if betainc(a, b, mid) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def decayed(a: float, b: float, a0: float, b0: float, age_s: float) -> tuple[float, float]:
    """Both counts pulled toward the prior: half of the distance is gone every 30 days."""
    keep = 0.5 ** (max(0.0, age_s) / HALF_LIFE_S)
    return a0 + (a - a0) * keep, b0 + (b - b0) * keep


def fresh(klass: str) -> dict:
    a, b = risk.PRIORS[klass]
    return {
        "a": a,
        "b": b,
        "at": 0.0,
        "cooldown_until": 0.0,
        "never": False,
        "n": {"ok": 0, "silence": 0, "undo": 0, "complaint": 0},
    }


def update(st: dict | None, klass: str, kind: str, now: float, seen: bool = True) -> dict:
    """The state after one piece of evidence: first the decay since the last one, then the evidence weighted by the
    class's
    impact. Silence counts only when `seen` (the act was in a digest you opened). An undo starts a 7 day cooldown."""
    if klass not in risk.PRIORS or kind not in EVIDENCE:
        raise ValueError("no such class or evidence")
    s = {**fresh(klass), **(st or {})}
    s["n"] = dict(s.get("n") or fresh(klass)["n"])
    a0, b0 = risk.PRIORS[klass]
    if s["at"]:
        s["a"], s["b"] = decayed(s["a"], s["b"], a0, b0, now - s["at"])
    if kind == "silence" and not seen:
        s["at"] = now
        return s
    which, w = EVIDENCE[kind]
    s[which] += w * risk.IMPACT[klass]
    s["n"][kind] = int(s["n"].get(kind, 0)) + 1
    if kind == "undo":
        s["cooldown_until"] = now + COOLDOWN_S
    s["at"] = now
    return s


def p10(st: dict | None, klass: str, now: float) -> float:
    """The 10th percentile of the class's trust as of `now` (the prior's, with nothing yet)."""
    a0, b0 = risk.PRIORS[klass]
    s = st or {}
    a, b = decayed(float(s.get("a", a0)), float(s.get("b", b0)), a0, b0, now - float(s.get("at") or now))
    return percentile(a, b, 0.10)


def may_act(st: dict | None, klass: str, now: float, thresholds: dict | None = None) -> bool:
    """Act without asking? Only for R0-R3, never in a cooldown or after "never for this kind", and only when the 10th
    percentile is above the class's threshold."""
    if klass not in risk.PRIORS:
        return False
    s = st or {}
    if s.get("never") or now < float(s.get("cooldown_until") or 0):
        return False
    t = {**risk.THRESH, **(thresholds or {})}.get(klass, 1.0)
    return p10(st, klass, now) > float(t)

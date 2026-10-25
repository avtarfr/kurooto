"""The small statistics Brain's read and forecast need (0.8.0 stage 04), in plain Python: Kurooto doesn't ship numpy and
the data is a few dozen days by a handful of features.

    ridge(X, y, lam)           least squares with a ridge penalty (the intercept isn't penalised)
    predict(beta, x)
    mad_scale(residuals)       1.4826 x the median absolute deviation (a robust standard deviation)
    robust_z(residual, scale)  residual / scale, 0 when the scale is 0
    cusum(zs, k, h)            a two-sided CUSUM on z scores: the indexes where it alarms (and restarts)
    isotonic(xs, ys)           pool-adjacent-violators: a non-decreasing fit of ys against xs, as a predictor
    gauss_logpdf, poisson_logpmf, categorical_logp
"""

from __future__ import annotations

import math
from collections.abc import Sequence

PART = "read"  # its switch: mind.read.on


def solve(a: list[list[float]], b: list[float]) -> list[float] | None:
    """Gaussian elimination with partial pivoting; None when the system is singular."""
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(m[r][c]))
        if abs(m[p][c]) < 1e-12:
            return None
        m[c], m[p] = m[p], m[c]
        for r in range(c + 1, n):
            f = m[r][c] / m[c][c]
            for k in range(c, n + 1):
                m[r][k] -= f * m[c][k]
    x = [0.0] * n
    for r in range(n - 1, -1, -1):
        x[r] = (m[r][n] - sum(m[r][k] * x[k] for k in range(r + 1, n))) / m[r][r]
    return x


def ridge(X: Sequence[Sequence[float]], y: Sequence[float], lam: float = 1.0) -> list[float] | None:
    """beta (intercept first) minimising |y - [1 X] beta|^2 + lam |beta[1:]|^2. None with no rows."""
    n = len(y)
    if n == 0 or len(X) != n:
        return None
    p = len(X[0]) + 1
    rows = [[1.0, *map(float, r)] for r in X]
    a = [[sum(r[i] * r[j] for r in rows) for j in range(p)] for i in range(p)]
    for i in range(1, p):
        a[i][i] += lam
    b = [sum(r[i] * yy for r, yy in zip(rows, y, strict=True)) for i in range(p)]
    sol = solve(a, b)
    if sol is None:  # a constant column and no penalty on the intercept can do it: a touch more ridge
        for i in range(p):
            a[i][i] += 1e-6
        sol = solve(a, b)
    return sol


def predict(beta: Sequence[float], x: Sequence[float]) -> float:
    return beta[0] + sum(b * v for b, v in zip(beta[1:], x, strict=False))


def median(v: Sequence[float]) -> float:
    s = sorted(v)
    n = len(s)
    if n == 0:
        return 0.0
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def mad_scale(res: Sequence[float]) -> float:
    m = median(res)
    return 1.4826 * median([abs(r - m) for r in res])


def robust_z(residual: float, scale: float) -> float:
    return residual / scale if scale > 1e-9 else 0.0


def cusum(zs: Sequence[float], k: float = 0.5, h: float = 4.0) -> list[int]:
    """Indexes where either side of a two-sided CUSUM passes h (it starts over after each alarm)."""
    hi = lo = 0.0
    out = []
    for i, z in enumerate(zs):
        hi = max(0.0, hi + z - k)
        lo = max(0.0, lo - z - k)
        if hi > h or lo > h:
            out.append(i)
            hi = lo = 0.0
    return out


def isotonic(xs: Sequence[float], ys: Sequence[float]):
    """A non-decreasing step function fitted to (xs, ys) by pool-adjacent-violators: returns f(x) -> float, or None
    when there's nothing to fit."""
    pts = sorted(zip(xs, ys, strict=True))
    if not pts:
        return None
    blocks: list[list[float]] = []  # [sum y, count, last x]
    for x, y in pts:
        blocks.append([float(y), 1.0, float(x)])
        while len(blocks) > 1 and blocks[-2][0] / blocks[-2][1] > blocks[-1][0] / blocks[-1][1]:
            s, c, lx = blocks.pop()
            blocks[-1][0] += s
            blocks[-1][1] += c
            blocks[-1][2] = lx
    edges = [(b[2], b[0] / b[1]) for b in blocks]

    def f(x: float) -> float:
        for last, v in edges:
            if x <= last:
                return v
        return edges[-1][1]

    return f


def gauss_logpdf(x: float, mu: float, sigma: float) -> float:
    s = max(sigma, 1e-6)
    return -0.5 * math.log(2 * math.pi * s * s) - (x - mu) ** 2 / (2 * s * s)


def poisson_logpmf(k: int, lam: float) -> float:
    lam = max(lam, 1e-6)
    return k * math.log(lam) - lam - math.lgamma(k + 1)


def categorical_logp(k: int, probs: Sequence[float]) -> float:
    if not 0 <= k < len(probs):
        return math.log(1e-6)
    return math.log(max(probs[k], 1e-6))

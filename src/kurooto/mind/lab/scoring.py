"""Scoring a batch under its pre-registration: wins, replication, nulls. The score is the replication rate.

A result is {id, config, seed, value (a number or None), ok}. The analysis is fixed before the batch (prereg.py):
a *win* beats the baseline by at least `min_effect` of it, in the objective's direction; it is *replicated* when
every one of its second-seed runs also beats the baseline, and the mean of all its runs still clears `min_effect`.
Only replicated wins are proposed. A parameter whose low and high halves differ by less than `min_effect` of the
baseline is a *null*, and is reported as prominently as a win.
"""

from __future__ import annotations

from statistics import fmean


def gain(value: float, baseline: float, direction: str) -> float:
    """The share of the baseline gained (positive is better in the objective's direction)."""
    if baseline == 0:
        return 0.0
    g = (baseline - value) / abs(baseline) if direction == "min" else (value - baseline) / abs(baseline)
    return round(g, 6)


def wins(results: list[dict], baseline: float, direction: str, min_effect: float) -> list[dict]:
    """First-seed results that beat the baseline by min_effect, best first."""
    firsts: dict[str, dict] = {}
    for r in results:
        if r.get("ok") and isinstance(r.get("value"), (int, float)) and r["id"] not in firsts:
            firsts[r["id"]] = r
    out = [r for r in firsts.values() if gain(r["value"], baseline, direction) >= min_effect]
    return sorted(out, key=lambda r: -gain(r["value"], baseline, direction))


def replicated(first: dict, repeats: list[dict], baseline: float, direction: str, min_effect: float) -> bool:
    runs = [r for r in repeats if r.get("ok") and isinstance(r.get("value"), (int, float))]
    if not runs:
        return False
    if any(gain(r["value"], baseline, direction) <= 0 for r in runs):
        return False
    mean = fmean([first["value"], *(r["value"] for r in runs)])
    return gain(mean, baseline, direction) >= min_effect


def _solve(a: list[list[float]], b: list[float]) -> list[float] | None:
    """Gaussian elimination with partial pivoting on a small system; None when it is singular."""
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(m[r][c]))
        if abs(m[piv][c]) < 1e-12:
            return None
        m[c], m[piv] = m[piv], m[c]
        for r in range(n):
            if r != c:
                f = m[r][c] / m[c][c]
                for k in range(c, n + 1):
                    m[r][k] -= f * m[c][k]
    return [m[i][n] / m[i][i] for i in range(n)]


def _scaled(values: list[float]) -> list[float]:
    """0 to 1 by rank, so a log-spaced or skewed parameter counts the same as a plain one."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    out = [0.0] * len(values)
    for rank, i in enumerate(order):
        out[i] = rank / max(1, len(values) - 1)
    return out


def param_effects(results: list[dict], space: dict, baseline: float, min_effect: float) -> dict[str, str]:
    """For each numeric parameter: "matters", "null" or "too few runs to say". The metric is fitted to all the
    parameters at once (a line, and a bend when there are enough runs), and a parameter's effect is how far the fitted
    metric moves across its tested range with the others held still, as a share of the baseline, and it only counts when
    it stands out from the scatter of the runs (three standard errors)."""
    good = [r for r in results if r.get("ok") and isinstance(r.get("value"), (int, float)) and r.get("seed", 0) == 0]
    names = [k for k in space if all(isinstance((r.get("config") or {}).get(k), (int, float)) for r in good)]
    out = {k: "too few runs to say" for k in space}
    if not names or baseline == 0:
        return out
    quad = len(good) >= 3 * len(names) + 2
    width = 1 + len(names) * (2 if quad else 1)
    if len(good) < width + 1:
        return out
    cols = {k: _scaled([float(r["config"][k]) for r in good]) for k in names}
    rows = []
    for i in range(len(good)):
        row = [1.0]
        for k in names:
            row.append(cols[k][i])
            if quad:
                row.append(cols[k][i] ** 2)
        rows.append(row)
    y = [float(r["value"]) for r in good]
    ata = [[sum(r[i] * r[j] for r in rows) + (1e-9 if i == j else 0.0) for j in range(width)] for i in range(width)]
    aty = [sum(r[i] * yy for r, yy in zip(rows, y, strict=True)) for i in range(width)]
    coef = _solve(ata, aty)
    dof = len(good) - width
    if coef is None or dof < 1:
        return out
    sse = sum((yy - sum(c * v for c, v in zip(coef, r, strict=True))) ** 2 for r, yy in zip(rows, y, strict=True))
    sigma2 = sse / dof
    inv_diag = []
    for j in range(width):
        col = _solve(ata, [1.0 if i == j else 0.0 for i in range(width)])
        inv_diag.append(col[j] if col else float("inf"))
    for n_i, k in enumerate(names):
        at = 1 + n_i * (2 if quad else 1)
        lin, bend = coef[at], coef[at + 1] if quad else 0.0
        xs = [t / 20 for t in range(21)]
        resp = [lin * x + bend * x * x for x in xs]
        big = (max(resp) - min(resp)) / abs(baseline) >= min_effect
        sure = abs(lin) > 3 * (sigma2 * inv_diag[at]) ** 0.5 or (
            quad and abs(bend) > 3 * (sigma2 * inv_diag[at + 1]) ** 0.5
        )
        out[k] = "matters" if big and sure else "null"
    return out


def rate(n_replicated: int, n_wins: int) -> float | None:
    """The replication rate: replicated wins over wins (None when there were none: that is not a rate of 0)."""
    return None if n_wins == 0 else round(n_replicated / n_wins, 4)


def analyse(rec: dict, firsts: list[dict], repeats_by_id: dict[str, list[dict]], baseline: float) -> dict:
    """The whole batch under its pre-registered analysis -> {wins, replicated, nulls, rate, n_ok, n_failed}."""
    d, eff = rec["direction"], float(rec["min_effect"])
    w = wins(firsts, baseline, d, eff)
    rep = [r for r in w if replicated(r, repeats_by_id.get(r["id"], []), baseline, d, eff)]
    space = rec.get("space") if isinstance(rec.get("space"), dict) else {}
    nulls = [k for k, v in param_effects(firsts, space, baseline, eff).items() if v == "null"]
    return {
        "n_ok": sum(1 for r in firsts if r.get("ok")),
        "n_failed": sum(1 for r in firsts if not r.get("ok")),
        "wins": [r["id"] for r in w],
        "replicated": [r["id"] for r in rep],
        "nulls": nulls,
        "rate": rate(len(rep), len(w)),
        "best": rep[0] if rep else None,
        "best_gain": gain(rep[0]["value"], baseline, d) if rep else None,
    }

"""Rollouts (Brain, 0.8.0 stage 15): Monte Carlo over the coming weeks, to date each milestone and find where it's at
risk.

Each of N rollouts draws, for every day, the hours you'll get done (from your pace by weekday, never more than the
day's free
time), scales every effort estimate by a random factor (wider for a guess than for an estimate you made), and gives
the day's
hours to the ready tasks earliest-deadline-first, a task being ready once everything it depends on is finished. Per
node it
returns the p50 and p90 finish dates and the share of rollouts that finish after the due date (never finishing counts
as late).
The suggested allocation for the coming week is the average of what earliest-deadline-first gave each task each day,
which is
the lateness-minimising schedule for those rollouts. It is a suggestion: nothing here tells you what to do.
"""

from __future__ import annotations

import datetime as dt
import math
import random
from dataclasses import dataclass
from typing import TYPE_CHECKING

from kurooto.mind.plans import pace

if TYPE_CHECKING:
    from collections.abc import Callable

    from kurooto.mind.plans.tree import Node

SIGMA_GUESS, SIGMA_SET = 0.45, 0.25
EPS = 1e-6


@dataclass
class Result:
    id: str
    title: str
    due: dt.datetime
    p50: dt.date | None
    p90: dt.date | None
    risk: float
    finished: float  # the share of rollouts that finish inside the horizon


def acyclic(nodes: list[Node]) -> dict[str, list[str]]:
    """depends_on with unknown ids and cycles dropped: {id: [ids it waits for]}."""
    ids = {n.id for n in nodes}
    deps = {n.id: [d for d in n.depends_on if d in ids and d != n.id] for n in nodes}
    done: set[str] = set()
    state: dict[str, int] = {}

    def visit(i: str, path: tuple[str, ...]) -> None:
        if state.get(i) == 2:
            return
        state[i] = 1
        keep = []
        for d in deps[i]:
            if state.get(d) == 1:  # a cycle: this edge goes
                continue
            visit(d, (*path, i))
            keep.append(d)
        deps[i] = keep
        state[i] = 2
        done.add(i)

    for n in nodes:
        visit(n.id, ())
    return deps


def quantile(sorted_days: list[float], p: float) -> float | None:
    """The p-quantile of finish days (math.inf for never); None when it falls among the ones that never finish."""
    if not sorted_days:
        return None
    k = min(len(sorted_days) - 1, max(0, math.ceil(p * len(sorted_days)) - 1))
    v = sorted_days[k]
    return None if v == math.inf else v


def simulate(
    nodes: list[Node],
    pool: dict[int, list[float]],
    today: dt.date,
    horizon_days: int,
    n: int = 1000,
    seed: int = 0,
    free: Callable[[int], float] | None = None,
) -> tuple[dict[str, Result], dict[str, list[float]]]:
    """(results by node id, the suggested hours per day for the next 7 days by node id)."""
    rng = random.Random(seed)  # noqa: S311
    deps = acyclic(nodes)
    order = sorted(nodes, key=lambda x: x.due)
    finish: dict[str, list[float]] = {x.id: [] for x in nodes}
    alloc = {x.id: [0.0] * 7 for x in nodes}
    for _ in range(max(1, n)):
        left = {
            x.id: x.left_h * math.exp(rng.gauss(0, SIGMA_GUESS if x.guessed else SIGMA_SET))
            for x in nodes
            if x.left_h > EPS
        }
        fin: dict[str, float] = {x.id: -1.0 for x in nodes if x.id not in left}  # done already: before day 0
        for d in range(horizon_days):
            avail = pace.draw(rng, pool, (today + dt.timedelta(days=d)).weekday())
            if free is not None:
                avail = min(avail, free(d))
            for x in order:
                if avail <= EPS:
                    break
                if x.id in fin or any(dep not in fin for dep in deps[x.id]):
                    continue
                give = min(left[x.id], avail)
                left[x.id] -= give
                avail -= give
                if d < 7:
                    alloc[x.id][d] += give
                if left[x.id] <= EPS:
                    fin[x.id] = float(d)
        for x in nodes:
            finish[x.id].append(fin.get(x.id, math.inf))
    results: dict[str, Result] = {}
    for x in nodes:
        days = sorted(finish[x.id])
        late = sum(1 for v in finish[x.id] if v == math.inf or today + dt.timedelta(days=v) > x.due.date())
        p50, p90 = quantile(days, 0.5), quantile(days, 0.9)
        results[x.id] = Result(
            x.id,
            x.title,
            x.due,
            today + dt.timedelta(days=p50) if p50 is not None else None,
            today + dt.timedelta(days=p90) if p90 is not None else None,
            round(late / len(days), 3),
            round(sum(1 for v in days if v != math.inf) / len(days), 3),
        )
    return results, {i: [round(h / max(1, n), 2) for h in hs] for i, hs in alloc.items()}

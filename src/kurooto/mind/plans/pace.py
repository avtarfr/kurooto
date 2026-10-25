"""Your real pace (stage 15): hours of work you actually get done on each weekday, as a distribution, not one number.

From the study tracker (hours a day, 8 weeks back) and, if the activity stream is on, the time on projects. A weekday
with
few samples is pulled toward a prior (2 hours), so a new install still plans, with wide bands. Sampling draws one of a
weekday's samples and jitters it a little.
"""

from __future__ import annotations

import datetime as dt
import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kurooto.app import App

PRIOR_H, PRIOR_N = 2.0, 3
DAYS_BACK = 56


def history(app: App, today: dt.date | None = None) -> dict[int, list[float]]:
    """{weekday: [hours on that weekday, one per past week]} from the study tracker and the activity totals."""
    today = today or dt.date.today()
    out: dict[int, list[float]] = {i: [] for i in range(7)}
    study = app.modules.get("study")
    for back in range(1, DAYS_BACK + 1):
        d = today - dt.timedelta(days=back)
        secs = 0.0
        if study is not None and app.is_on("study"):
            try:
                secs += sum(study.day(d).values())
            except Exception:  # noqa: S110
                pass
        try:
            from kurooto.mind.senses import store

            t = store.totals(app, "activity", d.isoformat())
            secs += 60 * sum(v for k, v in t.items() if k.startswith("project:"))
        except Exception:  # noqa: S110
            pass
        if secs > 0:
            out[d.weekday()].append(round(secs / 3600, 2))
    return out


def samples(app: App, today: dt.date | None = None) -> dict[int, list[float]]:
    """Each weekday's samples, with the prior mixed in when there are fewer than a handful."""
    h = history(app, today)
    return {wd: [*s, *([PRIOR_H] * max(0, PRIOR_N - len(s)))] for wd, s in h.items()}


def draw(rng: random.Random, pool: dict[int, list[float]], weekday: int) -> float:
    base = rng.choice(pool[weekday])
    return max(0.0, base * rng.uniform(0.8, 1.2))


def describe(pool: dict[int, list[float]]) -> str:
    names = "Mon Tue Wed Thu Fri Sat Sun".split()
    return ", ".join(f"{names[i]} {sum(p) / len(p):.1f} h" for i, p in sorted(pool.items()))

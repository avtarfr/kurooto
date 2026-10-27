"""The presence reward (Brain, 0.8.16): Brain is paid a little for forecasting well when you'll be at your desk and
free, and only for that: accuracy, never engagement. A reward module: it imports only the reward sources and the
mind's plumbing (whitelist.py), so every input arrives as an argument. The scorekeeper's engine (mind/engine.py) calls
it with a `presence_check` fact from mind/presence_forecast.py: three numbers, nothing else.

    p     the forecast frozen for an hour, hours before it came: the chance you'd be at your desk and free then
    y     what that hour showed (the share of its quarter-hour looks that saw you at your desk, not on a call, not in
          a class), from the activity sense and Face presence
    base  the dumb baseline: what the same hour showed yesterday (0.5 when it showed nothing)

    skill = (base - y)^2 - (p - y)^2        the Brier score it beat the baseline by, in [-1, 1]
    r     = GAIN * skill                    per hour, with the day's sum held within +-W

So a forecast no better than "same as yesterday" earns nothing, a worse one costs a little, and a whole day of
perfect forecasts pays at most W. Whether you answered Kurooto, how often you talk to it or how you feel never enter:
being at your desk is the outcome, not being with Kurooto, and nothing it does can make you more present (it never
asks you to be). It moves the running mood and the week's sum, like the talk reward; never the values or the policy.
"""

from __future__ import annotations

import time

PART = "presence_forecast"  # its switch: mind.presence_forecast.on (registered in mind/presence_forecast.py)
REWARD = True

GAIN = 0.01  # one hour's best possible skill pays this
W = 0.05  # the day's presence rewards stay within +-W
DAY_SHIFT_S = 4 * 3600  # the day starts at 04:00, like the rest of Brain's days


def day_of(t: float) -> str:
    return time.strftime("%Y-%m-%d", time.localtime(t - DAY_SHIFT_S))


def _unit(x) -> float | None:
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        return None
    x = float(x)
    return x if 0.0 <= x <= 1.0 else None


def skill(p: float, y: float, base: float) -> float:
    """How much better than the baseline the forecast did on one hour, as a difference of Brier scores."""
    return (base - y) ** 2 - (p - y) ** 2


def pay(st: dict, t: float, p, y, base) -> tuple[float, str]:
    """What one checked hour pays (r, why), updating st (the day, its sum, counts and the running Brier sums). A fact
    with a number out of [0, 1] pays nothing."""
    p, y, base = _unit(p), _unit(y), _unit(base)
    if p is None or y is None or base is None:
        return 0.0, "bad"
    day = day_of(t)
    if st.get("day") != day:
        st["day"], st["sum"] = day, 0.0
    st["n"] = int(st.get("n") or 0) + 1
    st["brier"] = round(float(st.get("brier") or 0.0) + (p - y) ** 2, 6)
    st["brier_base"] = round(float(st.get("brier_base") or 0.0) + (base - y) ** 2, 6)
    r = GAIN * skill(p, y, base)
    total = float(st.get("sum") or 0.0)
    r = max(-W - total, min(W - total, r))  # the day's sum stays within +-W
    st["sum"] = round(total + r, 6)
    return round(r, 6), "paid" if r else "capped" if abs(total) >= W else "even"

"""The evening forecast (Brain, 0.8.0 stage 04, shadow mode): at 21:00 Brain says what it expects of tomorrow,
freezes it, and the next evening measures its surprise. Computed, logged and shown in /mood; it drives nothing yet.

Per channel, fitted on the last 28 days against what the calendar asks (read.features): wake_min and study_min (a
Gaussian on the fit's residual spread), snoozes and deadline_moves (Poisson), reply_band (the share of days in each
band, smoothed). Two forecasts are kept, p(y | planned) and p(y | none), but a model of how Kurooto's own actions
change you would break invariant I-14, so there isn't one: both come from the same calendar model, and what a
planned action does is only ever measured, against days when it was withheld on purpose (the holdout), never predicted.

    fit / predict    the model, and tomorrow's parameters for each channel
    freeze           the record that goes in the log: day, planned channels, parameters, and their sha256
    surprise_of      -log p(observed) under the frozen parameters
    skill_of         log p(observed) minus log p of the baseline (the mean of the last 4 same weekdays)
    score            both, per channel, with the channels a Kurooto action touched left without a skill score (I-14)

Pure functions over plain data; the scorekeeper scores from its own copy of the frozen record and the signals it stored.

Surprise check-ins (0.8.14, `mind.checkins.surprise`, on with Brain and Check-ins): every 15 minutes the live day is
held against the forecast frozen for it. When it departs strongly, the next check-in still planned today comes now
instead of at its time (once a day, through the gate and the workspace like any check-in):
    late_wake     no sign of you with Kurooto two hours past the predicted wake time, while your phone shows you up
                  (its screen sense, when it's on)
    moved_twice   a deadline moved twice today
Never during a class on the timetable, and never while you're asleep (Brain's sleep, else the night hours).

    surprise(app, t)        which of those holds now, or None
    surprise_tick(app)      the 15-minute check that fires the check-in
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING

from kurooto import mind
from kurooto.core.config import register_defaults
from kurooto.mind import read, stats

if TYPE_CHECKING:
    from kurooto.app import App

PART = "forecast"  # its switch: mind.forecast.on

register_defaults(
    "mind",
    {"checkins": {"surprise": True}},  # a check-in comes early when the day departs strongly from the forecast
)
SURPRISE_FILE = "mind-surprise.json"
LATE_MIN = 120  # this long past the predicted wake time with no sign of you
MOVES = 2  # one deadline moved this many times in a day

CHANNELS = {
    "wake_min": "gauss",
    "snoozes": "poisson",
    "study_min": "gauss",
    "deadline_moves": "poisson",
    "reply_band": "cat",
}
BANDS = 5
SIGMA_MIN = {"wake_min": 5.0, "study_min": 5.0}
LAM_MIN = 0.05
BASE_DAYS = 4


@dataclass
class Model:
    kind: str
    beta: list | None = None
    sigma: float = 1.0
    probs: list | None = None


def fit(history: list[read.Day]) -> dict[str, Model]:
    """Each channel's model from the last WINDOW days that have it (one with under MIN_HISTORY days is left out)."""
    out: dict[str, Model] = {}
    for name, kind in CHANNELS.items():
        rows = [d for d in history[-read.WINDOW :] if name in d.sig]
        if len(rows) < read.MIN_HISTORY:
            continue
        ys = [float(d.sig[name]) for d in rows]
        if kind == "cat":
            counts = [1.0] * BANDS  # smoothed
            for y in ys:
                counts[max(0, min(BANDS - 1, int(round(y))))] += 1
            tot = sum(counts)
            out[name] = Model(kind, probs=[c / tot for c in counts])
            continue
        X = [read.features(d.load) for d in rows]
        beta = stats.ridge(X, ys, read.RIDGE)
        if beta is None:
            continue
        res = [y - stats.predict(beta, x) for x, y in zip(X, ys, strict=True)]
        sigma = max(
            stats.mad_scale(res),
            (sum(r * r for r in res) / max(1, len(res) - 1)) ** 0.5 * 0.5,
            SIGMA_MIN.get(name, 0.3),
        )
        out[name] = Model(kind, beta=beta, sigma=sigma)
    return out


def predict(models: dict[str, Model], load: dict) -> dict[str, list[float]]:
    """Tomorrow's parameters per channel: [mu, sigma] (Gaussian), [lambda] (Poisson), the band shares (categorical)."""
    x = read.features(load)
    out: dict[str, list[float]] = {}
    for name, m in models.items():
        if m.kind == "cat":
            out[name] = [round(p, 6) for p in m.probs or []]
        elif m.kind == "gauss":
            out[name] = [round(stats.predict(m.beta or [0.0], x), 4), round(m.sigma, 4)]
        else:
            out[name] = [round(max(LAM_MIN, stats.predict(m.beta or [0.0], x)), 4)]
    return out


def freeze(day: str, params: dict[str, list[float]], planned: list[str] | tuple = (), holdout: bool = False) -> dict:
    """The record for the log: day (the one being forecast), the channels a planned Kurooto action would touch, the
    parameters, whether this is a holdout day, and the sha256 of all of that. Once logged it never changes."""
    body = {
        "day": day,
        "planned": sorted({p for p in planned if p in CHANNELS}),
        "holdout": bool(holdout),
        "params": {k: [float(v) for v in vs] for k, vs in sorted(params.items())},
    }
    body["hash"] = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return body


def check(rec: dict) -> bool:
    """Does the record's hash match its contents (a frozen forecast that was changed doesn't)?"""
    body = {k: v for k, v in rec.items() if k != "hash"}
    want = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return rec.get("hash") == want


def _logp(name: str, params: list[float], y: float) -> float:
    kind = CHANNELS[name]
    if kind == "gauss":
        return stats.gauss_logpdf(y, params[0], params[1])
    if kind == "poisson":
        return stats.poisson_logpmf(max(0, int(round(y))), params[0])
    return stats.categorical_logp(int(round(y)), params)


def surprise_of(name: str, params: list[float], y: float) -> float:
    return -_logp(name, params, y)


def baseline(name: str, same_weekdays: list[float]) -> list[float] | None:
    """The comparison forecast: the mean of the last BASE_DAYS same weekdays, in the channel's own family."""
    v = same_weekdays[-BASE_DAYS:]
    if not v:
        return None
    kind = CHANNELS[name]
    mean = sum(v) / len(v)
    if kind == "gauss":
        sd = (sum((x - mean) ** 2 for x in v) / max(1, len(v) - 1)) ** 0.5
        return [mean, max(sd, SIGMA_MIN.get(name, 0.3), 1.0)]
    if kind == "poisson":
        return [max(LAM_MIN, mean)]
    counts = [1.0] * BANDS
    for x in v:
        counts[max(0, min(BANDS - 1, int(round(x))))] += 1
    tot = sum(counts)
    return [c / tot for c in counts]


def score(
    rec: dict, observed: dict[str, float], same_weekdays: dict[str, list[float]], touched: set[str] | None = None
) -> dict:
    """Per channel with an observation: {surprise, skill or None, touched}. A channel a Kurooto action touched after the
    forecast was frozen gets no skill score (I-14: nothing rewards how well it predicts what it nudged)."""
    touched = set(touched or ()) | set(rec.get("planned") or ())
    out: dict = {}
    for name, params in (rec.get("params") or {}).items():
        if name not in observed or name not in CHANNELS:
            continue
        y = float(observed[name])
        surprise = surprise_of(name, params, y)
        base = baseline(name, same_weekdays.get(name) or [])
        skill = None
        if name not in touched and base is not None:
            skill = round(_logp(name, params, y) - _logp(name, base, y), 6)
        out[name] = {"surprise": round(surprise, 6), "skill": skill, "touched": name in touched}
    return out


def mean_surprise(scores: dict) -> float | None:
    v = [c["surprise"] for c in scores.values() if math.isfinite(c["surprise"])]
    return round(sum(v) / len(v), 4) if v else None


# --------------------------------------------------------------------------------------- surprise check-ins (0.8.14)
def surprise_on(app: App) -> bool:
    return mind.on(app) and bool(app.settings.get("mind.checkins.surprise")) and app.is_on("checkins")


def frozen(app: App, day: str) -> dict | None:
    """The forecast frozen for `day` (21:00 the evening before), from the scorekeeper's tables (read-only)."""
    row = next(iter(mind.connect(app).mood_rows(f"forecast:{day}")), None)
    return (row or {}).get("meta") or None


def _phone_up(app: App, since: float) -> bool:
    try:
        from kurooto.mind.senses import phone, store

        if not phone.enabled(app, "screen"):
            return False
        return any(float(r["n"]) > 0 for r in store.events(app, "phone:screen", since))
    except Exception:
        return False


def surprise(app: App, t: dt.datetime | None = None) -> str | None:
    """What departs strongly from the forecast right now: "moved_twice", "late_wake", or None."""
    from kurooto.core.clock import now
    from kurooto.mind import signals

    t = t or now()
    lo = dt.datetime.combine(t.date(), dt.time(0)).timestamp()
    moved: Counter = Counter()
    for rec in app.events.tail(5000, {"deadline_moved"}):
        try:
            ts = dt.datetime.fromisoformat(str(rec["ts"])).timestamp()
        except (KeyError, ValueError):
            continue
        if lo <= ts <= t.timestamp():
            moved[str(rec.get("id") or "")] += 1
    if any(n >= MOVES for k, n in moved.items() if k) or moved.get("", 0) >= MOVES:
        return "moved_twice"
    params = ((frozen(app, t.date().isoformat()) or {}).get("params") or {}).get("wake_min")
    if params:
        late = (t.timestamp() - lo) / 60.0 > float(params[0]) + LATE_MIN
        if late and not signals._events(app, lo, t.timestamp(), signals.ACTIVE) and _phone_up(app, lo):  # noqa: SLF001
            return "late_wake"
    return None


def _asleep(app: App, t: dt.datetime) -> bool:
    try:
        from kurooto.mind import sleep as msleep

        if getattr(msleep, "on", lambda a: True)(app):
            return msleep.state(app) == "asleep"
    except Exception:  # noqa: S110 (no sleep yet: the night hours say it)
        pass
    try:
        return bool(app.availability.night(t))
    except Exception:
        return False


def _in_class(app: App, t: dt.datetime) -> bool:
    block = getattr(app.availability, "blockers", {}).get("subjects:class")
    try:
        return bool(block and block(t))
    except Exception:
        return False


def surprise_tick(app: App, payload: dict | None = None) -> str | None:
    """Every 15 minutes: on a strong surprise, the next check-in planned today comes now instead (once a day). Returns
    the surprise that fired one, else None."""
    if not surprise_on(app):
        return None
    from kurooto.core.clock import now
    from kurooto.core.state import jload, jsave

    t = now()
    f = app.paths.state / SURPRISE_FILE
    if (jload(f, {}) or {}).get("day") == t.date().isoformat():
        return None
    if _asleep(app, t) or _in_class(app, t):
        return None
    why = surprise(app, t)
    if why is None:
        return None
    ck = app.modules.get("checkins")
    day = ck.day_of(t)
    plan = ck.today(day)
    ahead = [
        (ck.at(day, c["time"]), name)
        for name, c in plan.items()
        if isinstance(c, dict) and c.get("status") == "planned" and c.get("time")
    ]
    ahead = [x for x in ahead if x[0] > t]
    if not ahead:
        return None
    _, name = min(ahead)
    jsave(f, {"day": t.date().isoformat(), "why": why, "name": name})
    app.scheduler.cancel(f"checkins:{name}")  # it comes now in place of its timer
    ck._fire({"name": name, "day": day.isoformat(), "early": True})  # noqa: SLF001
    app.events.emit("mind_surprise_checkin", why=why, name=name)
    return why

"""When you'll be at your desk and free (Brain, 0.8.16, `mind.presence_forecast.on`, on with Brain): a forecast for
each of the next HOURS hours, scored against what the senses then show, and paid for accuracy only.

Free means: at your desk (the activity sense saw the computer in use, or Face presence saw you, in the last quarter
hour), not on a call, not in a class on the timetable. Asleep counts as not free (the night hours, or Kurooto's sleep
window, which follows yours).

    the forecast   per hour of the week, the share of that hour's looks that found you free, pulled toward the same hour
                   on any day while there are few (a Beta-style average, K looks' worth); a class, the night, Kurooto's
                   sleep window or a call already on make an hour BLOCKED_P. Nothing seen yet: 0.5 (no opinion)
    every 15 min   one look (only when the activity sense or Face presence can see you; otherwise nothing is scored),
                   the forecast for each of the next hours frozen the first time it's made (so it's made hours ahead),
                   and each hour that's over checked: what it showed (y, the share of its looks that found you free)
                   against what was frozen (p) and against "same as yesterday" (the same hour the day before, 0.5 when
                   unseen). The three numbers go to the scorekeeper as a `presence_check`; mind/presence_reward.py pays
                   the Brier skill over the baseline, a little, bounded a day. Accuracy, never engagement: nothing here
                   counts what you said to Kurooto or whether you answered it.
    prefer(...)    (`mind.presence_forecast.prefer`, on) a time a check-in or a call Kurooto places by itself is due,
                   moved to a nearby hour you're likely free (within `within_min` minutes, 60) when the forecast thinks
                   you won't be then and a nearby hour is clearly better. Never an alarm, a reminder you set, a call
                   you asked for or a close deadline: their callers don't ask.

Kept in `<state>/mind-presence.json`: hour-of-week counts, the frozen forecasts, today's looks and the last days'
outcomes (numbers only, this computer only). /mind shows the accuracy and the next free hour.
"""

from __future__ import annotations

import datetime as dt
import threading
import time
from typing import TYPE_CHECKING

from kurooto import mind
from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave

if TYPE_CHECKING:
    from kurooto.app import App

PART = "presence_forecast"  # its switch: mind.presence_forecast.on

register_defaults(
    "mind",
    {
        "presence_forecast": {
            "on": True,  # forecast when you'll be at your desk and free, scored against what the senses show
            "prefer": True,  # its own check-ins and calls move to a nearby hour the forecast thinks you are free
            "within_min": 60,  # how far (minutes) such a check-in or call may move to a likelier hour
        }
    },
)

FILE = "mind-presence.json"
HOURS = 6  # hours ahead it forecasts
DESK_S = 15 * 60  # the computer in use, or your face seen, this recently: at your desk
BLOCKED_P = 0.02  # a class, the night, its sleep window or a call: almost surely not free
FREE_P = 0.5  # likely free from here up
MARGIN = 0.2  # a nearby hour must be this much likelier to move something there
K = 2.0  # looks' worth the same hour on any day carries in an hour-of-week cell
MIN_LOOKS = 2  # an hour with fewer looks isn't checked
KEEP_DAYS = 3  # the outcomes kept for the baseline and /mind
_lock = threading.Lock()


def on(app: App) -> bool:
    return mind.part_on(app, PART)


def prefer_on(app: App) -> bool:
    return on(app) and bool(app.settings.get("mind.presence_forecast.prefer"))


def _within(app: App) -> int:
    v = app.settings.get("mind.presence_forecast.within_min")
    return max(0, min(240, int(v))) if isinstance(v, (int, float)) and not isinstance(v, bool) else 60


def _load(app: App) -> dict:
    d = jload(app.paths.state / FILE, {}) or {}
    for k in ("cells", "hours", "frozen", "looks", "seen", "score"):
        if not isinstance(d.get(k), dict):
            d[k] = {}
    return d


def _save(app: App, d: dict) -> None:
    jsave(app.paths.state / FILE, d)


def forget(app: App) -> None:
    (app.paths.state / FILE).unlink(missing_ok=True)


def slot(t: dt.datetime) -> str:
    return t.strftime("%Y-%m-%dT%H")


def _start(s: str) -> dt.datetime:
    return dt.datetime.strptime(s, "%Y-%m-%dT%H")


# ------------------------------------------------------------------------------------------------- what's known
def _in_class(app: App, t: dt.datetime) -> bool:
    block = getattr(getattr(app, "availability", None), "blockers", {}).get("subjects:class")
    try:
        return bool(block and block(t))
    except Exception:
        return False


def _asleep(app: App, t: dt.datetime) -> bool:
    try:
        from kurooto.mind import sleep as msleep

        w = msleep.window(app, t)
        if w and w[0] <= t < w[1]:
            return True
    except Exception:  # noqa: S110 (no sleep window: the night hours below)
        pass
    try:
        return bool(app.availability.night(t))
    except Exception:
        return False


def _on_call(app: App, t: dt.datetime | None = None) -> bool:
    try:
        return bool(app.availability.on_call_until(t))
    except Exception:
        return False


def blocked(app: App, t: dt.datetime) -> str | None:
    """A reason you surely won't be free at t ("class", "asleep", "call"), or None."""
    if _in_class(app, t):
        return "class"
    if _asleep(app, t):
        return "asleep"
    if _on_call(app, t):
        return "call"
    return None


def p_free(app: App, t: dt.datetime, st: dict | None = None) -> float:
    """The chance you're at your desk and free at t: BLOCKED_P when something known says not, else the hour-of-week
    share of looks that found you free, pulled toward the same hour on any day (0.5 with nothing seen)."""
    if blocked(app, t):
        return BLOCKED_P
    st = st if st is not None else _load(app)
    a_h, n_h = (st["hours"].get(str(t.hour)) or [0.0, 0])[:2]
    p_h = (float(a_h) + 1.0) / (float(n_h) + 2.0)
    a, n = (st["cells"].get(f"{t.weekday()}-{t.hour}") or [0.0, 0])[:2]
    p = (float(a) + K * p_h) / (float(n) + K)
    return round(max(BLOCKED_P, min(1.0 - BLOCKED_P, p)), 4)


# ------------------------------------------------------------------------------------------------- what's seen
def sensing(app: App) -> bool:
    """Can anything see you at your desk? The activity sense, or Face presence."""
    try:
        from kurooto.mind.senses import activity

        if activity.on(app):
            return True
    except Exception:  # noqa: S110
        pass
    try:
        return bool(app.is_on("face"))
    except Exception:
        return False


def at_desk(app: App, t: float | None = None) -> bool | None:
    """At your desk now (the computer in use, or your face seen, in the last DESK_S)? None when nothing can tell."""
    t = time.time() if t is None else t
    can = seen = False
    try:
        from kurooto.mind.senses import activity, store

        if activity.on(app):
            can = True
            seen = bool(store.events(app, "activity", t - DESK_S))
    except Exception:  # noqa: S110
        pass
    try:
        face = app.modules.get("face") if app.is_on("face") else None
        w = getattr(face, "watcher", None) if face is not None else None
        if w is not None:
            can = True
            last = getattr(w, "last_seen_owner", None)
            clock = getattr(w, "clock", time.monotonic)
            if last is not None and clock() - float(last) <= DESK_S:
                seen = True
    except Exception:  # noqa: S110
        pass
    return seen if can else None


def free_now(app: App, t: dt.datetime | None = None) -> bool | None:
    """Free right now (at your desk, not on a call, not in a class)? None when nothing can see you."""
    t = t or now()
    desk = at_desk(app, t.timestamp())
    if desk is None:
        return None
    return bool(desk and not _on_call(app, t) and not _in_class(app, t))


# ------------------------------------------------------------------------------------------------- the tick
def tick(app: App, payload: dict | None = None) -> list[tuple[float, float, float]]:
    """Every 15 minutes: one look, the coming hours' forecasts frozen, the hours that are over checked. Returns the
    checks made [(p, y, base)]."""
    if not on(app):
        return []
    t = now()
    cur = slot(t)
    look = free_now(app, t) if sensing(app) else None
    checks: list[tuple[float, float, float]] = []
    with _lock:
        st = _load(app)
        if look is not None:
            f, n = (st["looks"].get(cur) or [0, 0])[:2]
            st["looks"][cur] = [int(f) + int(look), int(n) + 1]
        for h in range(1, HOURS + 1):
            s = slot(t + dt.timedelta(hours=h))
            if s not in st["frozen"]:
                st["frozen"][s] = p_free(app, _start(s), st)
        for s in sorted(k for k in st["looks"] if k < cur):
            f, n = st["looks"].pop(s)[:2]
            p = st["frozen"].pop(s, None)
            if int(n) < MIN_LOOKS:
                continue
            y = round(int(f) / int(n), 4)
            hour = _start(s)
            yest = st["seen"].get(slot(hour - dt.timedelta(days=1)))
            base = float(yest) if yest is not None else 0.5
            for table, key in (("cells", f"{hour.weekday()}-{hour.hour}"), ("hours", str(hour.hour))):
                a, m = (st[table].get(key) or [0.0, 0])[:2]
                st[table][key] = [round(float(a) + y, 4), int(m) + 1]
            st["seen"][s] = y
            if p is not None:
                sc = st["score"]
                sc["n"] = int(sc.get("n") or 0) + 1
                sc["brier"] = round(float(sc.get("brier") or 0.0) + (p - y) ** 2, 6)
                sc["base"] = round(float(sc.get("base") or 0.0) + (base - y) ** 2, 6)
                checks.append((float(p), y, base))
        old = slot(t - dt.timedelta(days=KEEP_DAYS))
        st["seen"] = {k: v for k, v in st["seen"].items() if k >= old}
        st["frozen"] = {k: v for k, v in st["frozen"].items() if k >= slot(t - dt.timedelta(hours=2))}
        _save(app, st)
    for p, y, base in checks:  # to the scorekeeper: three numbers, accuracy only (mind/presence_reward.py)
        mind.connect(app).report("presence_check", {"p": round(p, 4), "y": y, "base": round(base, 4)})
    if checks:
        app.events.emit("mind_presence_checked", n=len(checks))
    return checks


# ------------------------------------------------------------------------------------------------- using it
def prefer(
    app: App,
    at: dt.datetime,
    earliest: dt.datetime | None = None,
    latest: dt.datetime | None = None,
    within_min: int | None = None,
    skip: tuple[str, ...] = (),
) -> dt.datetime:
    """`at`, or a time within `within_min` of it (in quarter hours, between earliest and latest) when the forecast
    thinks you won't be free at `at` and that time is clearly likelier (by MARGIN, and FREE_P or better). `skip` names
    blockers the caller doesn't count ("asleep" for a check-in meant for bedtime). With prefer off: `at`."""
    if not prefer_on(app):
        return at
    try:
        st = _load(app)
        w = _within(app) if within_min is None else within_min

        def p(t: dt.datetime) -> float:
            why = blocked(app, t)
            if why and why not in skip:
                return BLOCKED_P
            if why:  # a blocker this caller doesn't count: the learned hours only
                a, n = (st["cells"].get(f"{t.weekday()}-{t.hour}") or [0.0, 0])[:2]
                a_h, n_h = (st["hours"].get(str(t.hour)) or [0.0, 0])[:2]
                return (float(a) + K * (float(a_h) + 1) / (float(n_h) + 2)) / (float(n) + K)
            return p_free(app, t, st)

        p0 = p(at)
        if p0 >= FREE_P:
            return at
        best, bp = at, p0
        steps = sorted(range(-(w // 15), w // 15 + 1), key=lambda k: (abs(k), -k))  # nearest first, later on a tie
        for k in steps:
            c = at + dt.timedelta(minutes=15 * k)
            if (earliest and c < earliest) or (latest and c > latest):
                continue
            pc = p(c)
            if pc > bp + 1e-9:
                best, bp = c, pc
        if best != at and bp >= FREE_P and bp - p0 >= MARGIN:
            app.events.emit("mind_presence_prefer", moved_min=int((best - at).total_seconds() // 60))
            return best
    except Exception as e:  # never in the way of what it was asked about
        app.events.emit("mind_presence_failed", error=type(e).__name__)
    return at


def next_free(app: App, t: dt.datetime | None = None, hours: int = HOURS) -> tuple[dt.datetime, float] | None:
    """The first of the next hours you're likely free (FREE_P or better), with its chance."""
    t = t or now()
    st = _load(app)
    for h in range(1, hours + 1):
        s = (t + dt.timedelta(hours=h)).replace(minute=0, second=0, microsecond=0)
        q = p_free(app, s, st)
        if q >= FREE_P:
            return s, q
    return None


def accuracy(app: App) -> dict:
    """{n, brier, base}: hours checked, the forecast's mean Brier score and the same-as-yesterday baseline's."""
    sc = _load(app)["score"]
    n = int(sc.get("n") or 0)
    if not n:
        return {"n": 0, "brier": None, "base": None}
    return {"n": n, "brier": round(float(sc["brier"]) / n, 3), "base": round(float(sc["base"]) / n, 3)}


def line(app: App) -> str:
    """For /mind: the accuracy against the baseline and the next likely-free hour. "" with it off."""
    if not on(app):
        return ""
    a = accuracy(app)
    if not a["n"]:
        head = "Presence forecast: nothing checked yet" + (
            "." if sensing(app) else " (it needs the activity sense or Face presence to see you at your desk)."
        )
    else:
        head = (
            f"Presence forecast: Brier {a['brier']:.3f} over {a['n']} hour{'s' if a['n'] != 1 else ''} "
            f"(same as yesterday: {a['base']:.3f}; lower is better)."
        )
    nf = next_free(app)
    return head + (f" Likely free next: {nf[0]:%H:%M} ({nf[1]:.0%})." if nf else "")


__all__ = ["tick", "p_free", "prefer", "free_now", "next_free", "accuracy", "line", "blocked"]

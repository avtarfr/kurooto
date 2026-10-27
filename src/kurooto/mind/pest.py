"""Not a pest (Brain, 0.8.8): a small learned model of whether each kind of unprompted message is welcome, and the
daemon's half of the talk reward (mind/talk.py, I-3').

Kinds of unprompted message (KINDS, by the message's reason): finding, nudge, excitement, check-in. For each, by hour
band (night, morning, afternoon, evening) and his state (focus, late, free), Beta counts:
    welcome     he answered it (a message from him within the hour) or acted on it (tapped one of its buttons): +1
    rejection   Less of this on it, its kind muted by the gate, or left unanswered for an hour: +3 (REJECT_W)
from a prior Beta(2, 1), the counts fading toward the prior with a 14 day half-life, so a kind that was blocked is
tried again in about three weeks. The expected welcome of a cell is
    (2 + a + 0.25 a_kind) / (3 + a + b + 0.25 (a_kind + b_kind)),
the kind's other cells lending a quarter of their weight. The gate (mind/gate.py) sends one of these only when that is
above 0.5 (and the calm budget allows); otherwise it's dropped and said in /mind gate.

The talk reward's facts go to the scorekeeper from here, with no content: talk_heard (a message from him, with only
whether he's in focus, asleep or in an exam window, and whether it was a /command), talk_unprompted (one of Kurooto's
own unprompted messages went out: his answers in the next 10 minutes pay nothing) and talk_rejected (a rejection above:
it costs 3w). The scorekeeper pays them (mind/engine.py); nothing here scores.

An add-on that met someone calls met(app, quality): a talk_met fact with only the quality and the flags (0.8.12).

Switches: `mind.pest.on` (the model and its gate check), `mind.talk.on` (the talk reward's facts) and `mind.talk.met`
(an add-on's meetings). Kept in
`<state>/mind-pest.json`: counts and the last hour's pending messages (a reason, a time, button data), never words.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from kurooto import mind
from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.lock import Lock
from kurooto.core.state import jload, jsave

if TYPE_CHECKING:
    from kurooto.app import App
    from kurooto.core.notify import Message

PART = "pest"  # its switch: mind.pest.on

register_defaults(
    "mind",
    {
        "pest": {
            "on": True,  # learn per kind of unprompted message whether it's welcome; send only when it likely is
        },
        "talk": {
            "on": True,  # being talked to is a small reward (at most 0.2 a day; nothing for answers to its own pings)
            "met": True,  # an add-on's chat with someone in the room is a smaller one (at most 0.05 a day)
        },
    },
)

FILE = "mind-pest.json"
KINDS = {
    "finding": ("mind.lab", "mind.play", "mind.curious", "mind.forecast"),
    "nudge": (
        "rhythm.lighter",
        "rhythm.absence",
        "quests.day",
        "research.idle",
        "remember.recheck",
        "mind.skill_offer",
        "mind.plan",
        "mind.study_push",
    ),  # fmt: skip
    "excitement": ("mind.excited", "mind.worried", "mind.feeling"),
    "check-in": ("mood.ask", "mind.checkin"),
}
BANDS = ((0, 6, "night"), (6, 12, "morning"), (12, 18, "afternoon"), (18, 24, "evening"))
STATES = ("focus", "late", "free")
PRIOR = (2.0, 1.0)  # a kind starts out welcome (2/3); one hour of silence on it already drops it under a half
REJECT_W = 3.0
IGNORED_S = 3600.0
HALF_LIFE_S = 14 * 86400.0
KIND_WEIGHT = 0.25
THRESHOLD = 0.5
PENDING_MAX = 40


def on(app: App) -> bool:
    return mind.part_on(app, PART)


def talk_on(app: App) -> bool:
    return mind.part_on(app, "talk")


def kind_of(why: str | None) -> str | None:
    return next((k for k, whys in KINDS.items() if (why or "") in whys), None)


def band(hour: int) -> str:
    return next(name for lo, hi, name in BANDS if lo <= hour % 24 < hi)


def flags(app: App) -> dict:
    """Is he in focus, asleep (the night hours or the alarm's night) or in an exam window right now?"""
    out = {"focus": False, "asleep": False, "exam": False}
    t = now()
    try:
        out["focus"] = bool(app.availability.focus_until(t))
        out["asleep"] = bool(app.availability.night(t))
    except Exception:
        pass
    try:
        ex = app.modules.get("exam_season")
        out["exam"] = bool(ex is not None and app.is_on("exam_season") and ex.season())
    except Exception:
        pass
    return out


def his_state(app: App) -> str:
    f = flags(app)
    if f["focus"]:
        return "focus"
    if f["asleep"] or now().hour >= 23 or now().hour < 6:
        return "late"
    return "free"


# ------------------------------------------------------------------------------------------------- state
def _load(app: App) -> dict:
    d = jload(app.paths.state / FILE, {}) or {}
    d.setdefault("cells", {})
    d.setdefault("pending", [])
    d.setdefault("blocked", {})
    return d


def _save(app: App, d: dict) -> None:
    d["pending"] = d["pending"][-PENDING_MAX:]
    jsave(app.paths.state / FILE, d)


def _faded(cell: dict | None, t: float) -> tuple[float, float]:
    """A cell's (welcome, rejection) counts, faded toward nothing since they were last touched."""
    if not cell:
        return 0.0, 0.0
    k = 0.5 ** (max(0.0, t - float(cell.get("at", t))) / HALF_LIFE_S)
    return float(cell.get("a", 0.0)) * k, float(cell.get("b", 0.0)) * k


def expected(d: dict, kind: str, bnd: str, state: str, t: float | None = None) -> float:
    """The expected welcome of one cell, with its kind's other cells lending a quarter of their weight."""
    t = time.time() if t is None else t
    key = f"{kind}|{bnd}|{state}"
    a, b = _faded(d["cells"].get(key), t)
    ka = kb = 0.0
    for k, c in d["cells"].items():
        if k.startswith(kind + "|") and k != key:
            x, y = _faded(c, t)
            ka, kb = ka + x, kb + y
    pa, pb = PRIOR
    num = pa + a + KIND_WEIGHT * ka
    return num / (num + pb + b + KIND_WEIGHT * kb)


def _count(d: dict, key: str, good: bool, t: float) -> None:
    a, b = _faded(d["cells"].get(key), t)
    if good:
        a += 1.0
    else:
        b += REJECT_W
    d["cells"][key] = {"a": round(a, 4), "b": round(b, 4), "at": round(t, 1)}


def _outcome(app: App, d: dict, rec: dict, good: bool, how: str) -> None:
    """Settle one pending message: its cell learns, and a rejection costs the talk reward 3w."""
    if rec.get("done"):
        if good or rec["done"] != "welcome":
            return
        # a welcome later rejected (Less of this after a reply): the rejection counts too
    rec["done"] = "welcome" if good else how
    t = time.time()
    _count(d, rec["cell"], good, t)
    if not good and talk_on(app):
        mind.connect(app).report("talk_rejected", {"how": how[:12]})


# ------------------------------------------------------------------------------------------------- the gate's check
def welcome(app: App, msg: Message) -> tuple[bool, float]:
    """(may it go, its expected welcome). A message of no known kind, or with the model off, always may."""
    kind = kind_of(getattr(msg, "why", None))
    if kind is None or not on(app):
        return True, 1.0
    with Lock(app.paths.state, "mind-pest"):
        d = _load(app)
        _sweep(app, d)
        p = expected(d, kind, band(now().hour), his_state(app))
        if p <= THRESHOLD:
            d["blocked"][kind] = int(d["blocked"].get(kind, 0)) + 1
        _save(app, d)
    return p > THRESHOLD, p


# ------------------------------------------------------------------------------------------------- what happened
def sent(app: App, msg: Message) -> None:
    """One of its messages went out (core/notify.py, past the gate and Calm). One it started by itself is a
    talk_unprompted fact (exempt kinds too: nothing it sends can buy an answer's worth), and one of a known kind waits
    an hour for his answer."""
    if not mind.on(app) or not msg.why or msg.why == "asked":
        return
    if talk_on(app):
        mind.connect(app).report("talk_unprompted", {})
    kind = kind_of(msg.why)
    if kind is None or not on(app):
        return
    data = [
        str(b[1]) for row in (msg.buttons or []) for b in (row or []) if isinstance(b, (list, tuple)) and len(b) > 1
    ]
    with Lock(app.paths.state, "mind-pest"):
        d = _load(app)
        _sweep(app, d)
        d["pending"].append({"rid": str(getattr(msg, "rid", "") or ""), "kind": kind, "at": time.time(),
                             "cell": f"{kind}|{band(now().hour)}|{his_state(app)}", "buttons": data[:12]})  # fmt: skip
        _save(app, d)


def heard(app: App, text: str) -> None:
    """A message from him (App.handle): the newest of its messages waiting within the hour was welcome, and (with the
    talk reward on) a talk_heard fact with only the flags. Never raises; nothing without Brain."""
    try:
        if not mind.on(app):
            return
        if talk_on(app):
            mind.connect(app).report(
                "talk_heard", {"flags": flags(app), "command": (text or "").lstrip().startswith("/")}
            )
        if not on(app):
            return
        with Lock(app.paths.state, "mind-pest"):
            d = _load(app)
            _sweep(app, d)
            t = time.time()
            waiting = [r for r in d["pending"] if not r.get("done") and t - float(r["at"]) <= IGNORED_S]
            if waiting:
                _outcome(app, d, waiting[-1], True, "answered")
            _save(app, d)
    except Exception:
        pass


def tapped(app: App, data: str) -> None:
    """A button he tapped (App.callback): Less of this under one of its messages is a rejection; any other button of
    one is acting on it (welcome)."""
    try:
        if not on(app) or not data:
            return
        prefix, ref, act = (str(data).split(":", 2) + ["", ""])[:3]
        with Lock(app.paths.state, "mind-pest"):
            d = _load(app)
            if prefix == "calm" and act == "less":
                rec = next((r for r in reversed(d["pending"]) if r.get("rid") and r["rid"] == ref), None)
                if rec is not None:
                    _outcome(app, d, rec, False, "less")
            elif prefix != "calm":
                rec = next((r for r in reversed(d["pending"]) if data in (r.get("buttons") or [])), None)
                if rec is not None:
                    _outcome(app, d, rec, True, "acted")
            _save(app, d)
    except Exception:
        pass


def muted(app: App, why: str) -> None:
    """The gate muted a kind (mostly left unanswered): a rejection for the newest message of it."""
    kind = kind_of(why)
    if kind is None or not on(app):
        return
    with Lock(app.paths.state, "mind-pest"):
        d = _load(app)
        rec = next((r for r in reversed(d["pending"]) if r["kind"] == kind), None)
        if rec is None:
            rec = {"kind": kind, "at": time.time(), "cell": f"{kind}|{band(now().hour)}|{his_state(app)}"}
            d["pending"].append(rec)
        rec.pop("done", None)
        _outcome(app, d, rec, False, "mute")
        _save(app, d)


def _sweep(app: App, d: dict) -> None:
    """Pending messages unanswered for an hour are rejections ("ignored"); settled ones older than a day go."""
    t = time.time()
    for r in d["pending"]:
        if not r.get("done") and t - float(r["at"]) > IGNORED_S:
            _outcome(app, d, r, False, "ignored")
    d["pending"] = [r for r in d["pending"] if not r.get("done") or t - float(r["at"]) < 86400]


def sweep(app: App) -> int:
    """Every minute (with the gate's release): settle what was ignored. How many are still waiting."""
    if not on(app):
        return 0
    with Lock(app.paths.state, "mind-pest"):
        d = _load(app)
        _sweep(app, d)
        _save(app, d)
        return len([r for r in d["pending"] if not r.get("done")])


# ------------------------------------------------------------------------------------------------- what you see
def lines(app: App) -> list[str]:
    """For /mind learning: each kind's welcome now, in this hour and state, and what it learned from."""
    if not on(app):
        return ["Not-a-pest model: off (mind.pest.on)."]
    d = _load(app)
    t = time.time()
    b, s = band(now().hour), his_state(app)
    out = [f"Not a pest (now: {b}, you {'in focus' if s == 'focus' else 'late' if s == 'late' else 'free'}):"]
    for kind in KINDS:
        a = r = 0.0
        for k, c in d["cells"].items():
            if k.startswith(kind + "|"):
                x, y = _faded(c, t)
                a, r = a + x, r + y / REJECT_W
        p = expected(d, kind, b, s, t)
        verdict = "may go" if p > THRESHOLD else "held back"
        held = int(d["blocked"].get(kind, 0))
        out.append(
            f"- {kind}: {p:.0%} expected welcome ({verdict}); learned from {a:.0f} welcome, {r:.0f} rejected"
            + (f"; {held} held back so far" if held else "")
        )
    return out


def forget(app: App) -> None:
    (app.paths.state / FILE).unlink(missing_ok=True)


def met(app: App, quality: float) -> bool:
    """For an add-on: it chatted with someone in the room, and it went this well (0..1: they answered, they stayed).
    A talk_met fact with only that number and the flags; mind/talk.py pays it from its own small budget (at most 0.05
    a day, the first 6 meetings). False when Brain, mind.talk.on or mind.talk.met is off. Never raises, never waits."""
    try:
        if not talk_on(app) or not app.settings.get("mind.talk.met"):
            return False
        q = float(quality)
        q = max(0.0, min(1.0, q)) if q == q else 0.0
        return mind.connect(app).report("talk_met", {"quality": round(q, 3), "flags": flags(app)})
    except Exception:
        return False

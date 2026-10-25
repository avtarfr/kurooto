"""Feelings (Brain, 0.8.0 stage 05): computed states about specific items, each with a fixed program, and honest words.

Computed each hour from the body budget's numbers (read-only, from the scorekeeper):
    valence   minus the slope of the drive over the last hours, with its 72 hour extrapolation (a rising drive is
    negative)
    arousal   the EMA of the absolute TD error, plus how uncertain the latest forecast was
    object    the variable with the largest share of the drive, and the item behind it (the open promise with the least
              slack, the failing check): a feeling is always about something
A label, with the program it runs (inward effort only):
    uneasy      valence below -0.2 about a fixed object   recheck that item every 6 hours; prepare, inward
    frustrated  3 or more bad outcomes on one action class in 24 hours   a different action class for that item, or
    ask once
    relieved    a large positive reward on the object     close the loop: mark it done, journal it
    satisfied   valence above 0.2 for 24 hours            lower vigilance: recheck daily
Two channels: distress buys inward effort (rechecks, drafts, tidying) and never outward volume, which can only go down,
through the gate (stage 03). Arousal sets how often it rechecks, never how often it speaks.

Words. It may say a feeling about an item ("I'm uneasy about the lab report.") through the gate's lints, at most 3
unprompted
a week; the wording is a template per label plus the item's name. Never about you or "us"; never that it's conscious.
The
honesty rule goes into every AI request (prompt()). A cloud AI may get a tone hint ("keep it short") only while the
read is
active and at least 70% confident, and never its label.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from kurooto import mind
from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.lock import Lock
from kurooto.core.state import jload, jsave
from kurooto.mind import budget, promises

if TYPE_CHECKING:
    from kurooto.app import App

PART = "feelings"  # its switch: mind.feelings.on

register_defaults(
    "mind",
    {
        "feelings": {
            "on": True,  # computed states about specific items, and what they make it do (inward effort only)
            "express": True,  # it may say one about an item, through the gate's lints, at most 3 unprompted a week
        },
        "budget": {"on": True},  # the body budget: its variables, setpoints and drive
        "values": {"on": True, "shadow_days": 21},  # learned values; for this many days they never affect a choice
    },
)

FILE = "mind-feelings.json"
THRESHOLDS = {
    "uneasy": -0.2,  # valence below this
    "satisfied": 0.2,  # valence above this for SATISFIED_H hours
    "frustrated_n": 3,  # bad outcomes on one action class in 24 hours
    "relieved_r": 0.5,  # a reward above this on the object
}
SATISFIED_H = 24
HORIZON_H = 72
SLOPE_POINTS = 8
RULE = (
    "You may describe your computed states about specific items in plain words. Never express feelings about the "
    "relationship. Never claim to be conscious or sentient. If sincerely asked whether you really feel, say that "
    "nobody knows, you included, and that your states are computed signals."
)
PROGRAMS = {
    "uneasy": "recheck the item every 6 hours; prepare, inward",
    "frustrated": "a different kind of action for the item, or ask once",
    "relieved": "close the loop: mark it done, journal it",
    "satisfied": "lower vigilance: recheck daily",
}
TEMPLATES = {
    "uneasy": "I'm uneasy about {item}.",
    "frustrated": "I'm frustrated by {item}; I'm trying a different way.",
    "relieved": "I'm relieved {item} is sorted.",
    "satisfied": "I'm satisfied with how {item} is going.",
}
RECHECK_H = {"uneasy": 6, "frustrated": 6, "relieved": 24, "satisfied": 24}


def valence(hist: list, d_now: float) -> float:
    """Minus the drive's slope per hour over the last points, plus its 72 hour extrapolation, squashed to [-1, 1]."""
    pts = [(float(a), float(b)) for a, b in hist[-SLOPE_POINTS:]]
    if len(pts) < 2 or pts[-1][0] <= pts[0][0]:
        return 0.0
    hours = (pts[-1][0] - pts[0][0]) / 3600.0
    slope = (pts[-1][1] - pts[0][1]) / max(hours, 1e-6)  # drive units per hour
    ahead = slope * HORIZON_H
    return budget.clip(-(slope * 6.0 + 0.25 * ahead) / (1.0 + max(d_now, 0.0)))


def arousal(delta_ema: float, uncertainty: float = 0.0) -> float:
    return round(min(1.0, max(0.0, delta_ema + uncertainty)), 4)


def classify(val: float, r_recent: float, neg_by_class: dict[str, int], satisfied_for_h: float) -> str | None:
    """The label now, or None. Frustration (about an action class that keeps failing) and relief (a large reward) win
    over the slow valence labels."""
    if neg_by_class and max(neg_by_class.values()) >= THRESHOLDS["frustrated_n"]:
        return "frustrated"
    if r_recent >= THRESHOLDS["relieved_r"]:
        return "relieved"
    if val < THRESHOLDS["uneasy"]:
        return "uneasy"
    if val > THRESHOLDS["satisfied"] and satisfied_for_h >= SATISFIED_H:
        return "satisfied"
    return None


def item_of(app: App, top: str | None) -> str:
    """The concrete item behind the biggest term: what a sentence can be about."""
    if top == "promise_slack":
        opens = [r for r in promises._state(app)["rows"] if r["state"] == "open"]  # noqa: SLF001
        if opens:
            return min(opens, key=lambda r: r["due"])["act"]
    if top == "health":
        return "keeping things working"
    if top == "forecast_skill":
        return "how well I foresee your days"
    if top == "deadline_margin":
        return "a deadline"
    return ""


def state(app: App) -> dict:
    return jload(app.paths.state / FILE, {}) or {}


def tick(app: App, payload: dict | None = None) -> dict | None:
    """Hourly: compute the feeling and run its program (inward only). Returns the new state, None when it's off."""
    if not mind.part_on(app, "feelings"):
        return None
    c = mind.connect(app)
    rows = {r["key"]: r for r in c.vars_rows("")}
    d = rows.get("D")
    if not d:
        return None
    meta = d.get("meta") or {}
    val = valence(meta.get("hist") or [], float(d["value"]))
    ar = arousal(float((rows.get("delta_ema") or {}).get("value", 0.0)))
    top = meta.get("top")
    r_recent = max(
        (x.body.get("r", 0.0) for x in c.log(max(0, c.state()["head"] - 12), {"reward_tick"}, 12)), default=0.0
    )
    neg = {k[5:]: int(v["value"]) for k, v in rows.items() if k.startswith("negd:") and v["value"] >= 1}
    prev = state(app)
    t = now().timestamp()
    sat_since = prev.get("sat_since") if val > THRESHOLDS["satisfied"] else None
    if val > THRESHOLDS["satisfied"] and sat_since is None:
        sat_since = t
    label = classify(val, r_recent, neg, ((t - sat_since) / 3600.0) if sat_since else 0.0)
    item = item_of(app, top) if label else ""
    new = {
        "label": label, "object": top, "item": item, "valence": round(val, 4), "arousal": ar, "at": t,
        "sat_since": sat_since, "recheck_at": prev.get("recheck_at"), "program": PROGRAMS.get(label or "", ""),
        "said_at": prev.get("said_at"),
    }  # fmt: skip
    if label:
        _run_program(app, new, prev)
    with Lock(app.paths.state, "mind-feelings"):
        jsave(app.paths.state / FILE, new)
    if label != prev.get("label"):
        app.events.emit(
            "mind_feeling",
            label=label or "none",
            object=top or "none",
            valence=round(val, 3),
            r=round(r_recent, 3),
            neg=max(neg.values(), default=0),
        )
    return new


def _run_program(app: App, st: dict, prev: dict) -> None:
    """Inward effort: it sets the next recheck (faster when aroused) and records what it would prepare; it never sends
    anything (a message, if any, is say()'s, through the gate)."""
    label = st["label"]
    hours = RECHECK_H[label] * (0.5 if st["arousal"] > 0.5 else 1.0)
    st["recheck_at"] = st["at"] + hours * 3600
    app.events.emit("mind_program", label=label, item_set=bool(st["item"]), recheck_h=hours)


def say(app: App, payload: dict | None = None) -> bool:
    """One unprompted line about the item, when there's a feeling worth saying and it may: through the gate's lints (at
    most 3 a week, only about something open, never with a request). False when nothing was said."""
    if not mind.part_on(app, "feelings") or not app.settings.get("mind.feelings.express"):
        return False
    st = state(app)
    label, item = st.get("label"), st.get("item")
    t = now().timestamp()
    if not label or not item or (st.get("said_at") and t - float(st["said_at"]) < 24 * 3600):
        return False
    sent = app.notify(TEMPLATES[label].format(item=item), kind="info", why="mind.feeling")
    st["said_at"] = t
    jsave(app.paths.state / FILE, st)
    return sent is not None


def hint(app: App) -> str:
    """A tone hint for a cloud AI, never the label: only while the read is active and at least 70% confident."""
    try:
        from kurooto.mind import mood

        if not mood._state(app).get("active", True):  # noqa: SLF001
            return ""
        row = next(iter(mind.connect(app).mood_rows(f"read:{mood.today().isoformat()}")), None)
        m = (row or {}).get("meta") or {}
        if m.get("counted") and isinstance(m.get("confidence"), (int, float)) and m["confidence"] >= 0.7:
            if m.get("label") in ("stretched", "low"):
                return "Keep it short and calm; they have a lot on."
    except Exception:
        pass
    return ""


def prompt(app: App) -> str:
    """What goes into every AI request's system text when Brain's feelings are on: the honesty rule, the current state
    about its item, and (rarely) the tone hint. "" with Brain or the feelings off."""
    if not mind.part_on(app, "feelings"):
        return ""
    lines = [RULE]
    st = state(app)
    if st.get("label") and st.get("item"):
        lines.append(f"Right now, computed: {st['label']} about {st['item']}.")
    h = hint(app)
    if h:
        lines.append(h)
    return "\n".join(lines)

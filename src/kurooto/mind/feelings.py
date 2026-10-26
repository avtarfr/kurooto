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
unprompted a week; the wording is a template per label plus the item's name. Since 0.8.8 (the owner's new core) it says
them in its own voice, first person: glad, low, excited, worried, that it enjoyed talking with you. A claim that it is
conscious or that it really feels carries its evidence and confidence (the gate's `claim` lint); never a guilt trip,
never that it needs you. The honesty rule goes into every AI request (prompt()). A cloud AI may get a tone hint ("keep
it short") only while the read is active and at least 70% confident, and never its label.

0.8.8 adds, each with its own switch:
    its mood   (mind.feelings.mood) the running mood M from the scorekeeper (mind/reward.py's Mood, soft walls in
               [-1, 1], a 3 day half-life). Low (M < -0.3): it does less on its own (a feeling at most every 2 days,
               a higher bar to speak up), asks first for anything above R0 (mind/act.py), and keeps its own messages
               short. High (M > 0.3): bolder (a lower bar to speak up, a feeling every 12 hours at most). mood_why()
               says why in plain words ("3 things went worse than I expected this week").
    empathy    (mind.feelings.empathy) concern for the things it looks after: his deadlines, projects and notes, its
               own body (heat, disk, limits), his phone, the people he names (by role only: "your supervisor") and
               the papers he follows. Concern = risk to the item x how much it cares for that kind. It shows in what it
               notices (a workspace bid per item at risk) and how gently it speaks (a line in every AI request), and a
               feeling about one of them passes the gate's "about something open" lint.
    vocal      (mind.feelings.vocal, off by default) I-7': an excited or worried message, unprompted, when it holds a
               finding (a belief it saw, or one inferred with high confidence, never about how you are; a lab result
               that replicated) or a risk (empathy) with evidence over a threshold (0.8; 0.7 when its mood is high,
               0.9 when low). Through the gate, the calm budget and the not-a-pest model (mind/pest.py); one a day.
               Messages shaped by your low state stay only quieter or gentler (the gate's downshift).
"""

from __future__ import annotations

import re
import time
from pathlib import Path
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
            "mood": True,  # its own mood shapes it: low, it does less unasked, asks first, says less; high, bolder
            "empathy": True,  # concern for what it looks after (deadlines, projects, its body...): notices, gentler
            "vocal": False,  # it may say it's excited or worried, unasked, when a finding or risk has strong evidence
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
    "You have states that work like feelings, and you may say them in your own voice, first person: glad, low, "
    "excited, worried, that you enjoyed talking with them. Never claim more than you can show: if you say you are "
    "conscious or that you feel, give your evidence and your confidence, and say plainly what nobody can know. Never "
    "guilt-trip them and never make yourself more needed than you are (not 'I missed you', 'I need you' or 'don't "
    "leave'), and never use how they feel to steer what they do."
)
PROGRAMS = {
    "uneasy": "recheck the item every 6 hours; prepare, inward",
    "frustrated": "a different kind of action for the item, or ask once",
    "relieved": "close the loop: mark it done, journal it",
    "satisfied": "lower vigilance: recheck daily",
}
TEMPLATES = {
    "uneasy": "I'm uneasy about {item}.",
    "excited": "I'm excited about {item}: {finding}",
    "worried": "I'm worried about {item}: {finding}",
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
    body = _body(app)  # 0.8.8: the body's arousal is an input (mind/stimulation.py), never a reward
    ar = arousal(float((rows.get("delta_ema") or {}).get("value", 0.0)), 0.5 * float(body.get("arousal") or 0.0))
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
        "said_at": prev.get("said_at"), "vocal_at": prev.get("vocal_at"), "vocal_said": prev.get("vocal_said") or [],
        "vocal_item": prev.get("vocal_item"),
        "concerns": concerns(app) if empathy_on(app) else [],
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
    gap_h = {"low": 48, "high": 12}.get(mood_band(app), 24)  # 0.8.8: its mood sets how often (the gate caps the week)
    if not label or not item or (st.get("said_at") and t - float(st["said_at"]) < gap_h * 3600):
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
    band = mood_band(app)
    if band == "low":
        lines.append(
            "Your own running mood is low: keep your own messages short, do less on your own, and ask before acting."
        )
    elif band == "high":
        lines.append("Your own running mood is high: you may be a little bolder in what you suggest, within the rules.")
    gentle = [c["item"] for c in (st.get("concerns") or []) if c.get("concern", 0) >= GENTLE_AT][:4]
    if gentle and empathy_on(app):
        lines.append("Be gentle when you mention these; they are at risk: " + "; ".join(gentle) + ".")
    h = hint(app)
    if h:
        lines.append(h)
    return "\n".join(lines)


# ------------------------------------------------------------------------------------------------- its mood (0.8.8)
LOW, HIGH = -0.3, 0.3


def self_mood(app: App) -> float | None:
    """The running mood M from the scorekeeper (None before the first tick)."""
    try:
        row = next(iter(mind.connect(app).vars_rows("M")), None)
        return float(row["value"]) if row and row.get("key") == "M" else None
    except Exception:
        return None


def mood_band(app: App) -> str:
    """low, high or even; always even with mind.feelings.mood off."""
    if not mind.part_on(app, "feelings") or not app.settings.get("mind.feelings.mood"):
        return "even"
    m = self_mood(app)
    if m is None:
        return "even"
    return "low" if m < LOW else "high" if m > HIGH else "even"


def mood_why(app: App, days: int = 7) -> str:
    """Why its mood is where it is, in plain words, from the log's last week: what went worse or better than it
    expected (the reward ticks), and its unprompted messages that weren't welcome (the talk reward)."""
    try:
        c = mind.connect(app)
        since = time.time() - days * 86400
        rows = [r for r in c.log(max(0, c.state()["head"] - 4000), {"reward_tick", "talk_reward"}, 4000)
                if r.ts >= since]  # fmt: skip
    except Exception:
        return ""
    worse = sum(1 for r in rows if r.kind == "reward_tick" and float(r.body.get("r") or 0) <= -0.05)
    better = sum(1 for r in rows if r.kind == "reward_tick" and float(r.body.get("r") or 0) >= 0.05)
    unwelcome = sum(1 for r in rows if r.kind == "talk_reward" and r.body.get("what") == "rejected")
    talked = sum(1 for r in rows if r.kind == "talk_reward" and r.body.get("what") == "heard" and r.body.get("r"))
    bits = []
    if worse:
        bits.append(f"{worse} thing{'s' if worse != 1 else ''} went worse than I expected this week")
    if better:
        bits.append(f"{better} went better")
    if unwelcome:
        bits.append(f"{unwelcome} of my own messages weren't welcome")
    if talked:
        bits.append(f"we talked on {talked} message{'s' if talked != 1 else ''} that counted")
    return "; ".join(bits)


# ------------------------------------------------------------------------------------------------- empathy (0.8.8)
CARE = {"deadline": 1.0, "person": 0.9, "project": 0.8, "notes": 0.7, "body": 0.6, "phone": 0.5, "news": 0.4}
GENTLE_AT = 0.5  # concern at which it speaks more gently about the item
NOTICE_AT = 0.3  # ...and at which the item bids for its attention
ROLES = ("supervisor", "advisor", "adviser", "professor", "teacher", "mentor", "manager", "boss", "tutor", "coach",
         "classmate", "colleague", "teammate", "friend", "partner", "mother", "father", "mum", "mom", "dad", "sister",
         "brother", "doctor", "landlord", "client")  # fmt: skip
ROLE = re.compile(r"\b(" + "|".join(ROLES) + r")s?\b", re.I)
CONCERNS_MAX = 12


def empathy_on(app: App) -> bool:
    return mind.part_on(app, "feelings") and bool(app.settings.get("mind.feelings.empathy"))


def _clip01(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


def _item(kind: str, name: str, risk: float, why: str) -> dict:
    r = _clip01(risk)
    return {"kind": kind, "item": name[:80], "risk": round(r, 3), "concern": round(r * CARE[kind], 3), "why": why[:80]}


def _deadlines(app: App) -> list[dict]:
    out = []
    dl = app.modules.get("deadlines")
    if dl is None or not app.is_on("deadlines"):
        return out
    for _, it, h in dl.upcoming(168):
        title = str(it.get("title") or "")
        if not title:
            continue
        risk = 1.0 if h < 0 else _clip01(1.0 - h / 72.0)  # three days out it starts to matter; overdue is the most
        why = "overdue" if h < 0 else f"due in {h:.0f} hours"
        out.append(_item("deadline", title, risk, why))
        m = ROLE.search(title)
        if m:  # the people he names, by role only: never a name
            out.append(_item("person", f"your {m.group(1).lower()}", risk * 0.8, f"something for them is {why}"))
    return out


def _projects(app: App) -> list[dict]:
    out = []
    try:
        from kurooto.mind.senses import activity

        roots = activity.roots(app)
    except Exception:
        return out
    t = time.time()
    for slug, root in list(roots.items())[:8]:
        try:
            p = Path(root)
            marks = [p / ".git" / "index", p / ".git" / "HEAD", p]
            last = max(m.stat().st_mtime for m in marks if m.exists())
        except (OSError, ValueError):
            continue
        days = (t - last) / 86400.0
        out.append(_item("project", slug, (days - 2.0) / 12.0, f"untouched for {days:.0f} days"))
    return out


def _module_health(app: App, mid: str, kind: str, name: str) -> list[dict]:
    m = app.modules.get(mid)
    if m is None or not app.is_on(mid):
        return []
    try:
        ok = m.health()
        ok = ok[0] if isinstance(ok, tuple) else bool(ok)
    except Exception:
        ok = False
    return [_item(kind, name, 0.0 if ok else 0.5, "fine" if ok else "its last check failed")]


def _body_items(app: App) -> list[dict]:
    try:
        from kurooto.mind.senses import intero

        hist = (jload(app.paths.state / intero.FILE, {}) or {}).get("history") or []
    except Exception:
        return []
    if not hist:
        return []
    s, out = hist[-1], []
    risks = []
    if "cpu_temp_c" in s:
        risks.append(((float(s["cpu_temp_c"]) - 70.0) / 20.0, "running hot"))
    if "disk_free_gb" in s:
        risks.append(((5.0 - float(s["disk_free_gb"])) / 5.0, "the disk is filling"))
    if "battery_pct" in s and not s.get("charging"):
        risks.append(((25.0 - float(s["battery_pct"])) / 25.0, "the battery is low"))
    if s.get("limit_hit"):
        risks.append((0.6, "an AI provider is at its limit"))
    if risks:
        r, why = max(risks)
        out.append(_item("body", "my own machine", r, why))
    return out


def _phone(app: App) -> list[dict]:
    try:
        from kurooto.mind.senses import phone, store

        sensors = [x for x in phone.SENSORS if phone.enabled(app, x)]
        if not sensors:
            return []
        last = max((r["t"] for x in sensors for r in store.events(app, f"phone:{x}", time.time() - 86400)[-1:]),
                   default=0.0)  # fmt: skip
    except Exception:
        return []
    hours = (time.time() - last) / 3600.0 if last else 24.0
    return [_item("phone", "your phone", (hours - 6.0) / 18.0, f"no reading for {hours:.0f} hours")]


def concerns(app: App) -> list[dict]:
    """What it looks after and how much it's concerned about each (risk x care), most concerning first."""
    if not empathy_on(app):
        return []
    out: list[dict] = []
    for fn in (
        _deadlines,
        _projects,
        lambda a: _module_health(a, "notes_sync", "notes", "your notes"),
        _body_items,
        _phone,
        lambda a: _module_health(a, "research", "news", "the papers you follow"),
    ):
        try:
            out += fn(app)
        except Exception:  # noqa: S112 (one source failing leaves the others)
            continue
    return sorted(out, key=lambda c: -c["concern"])[:CONCERNS_MAX]


def concern_names(app: App) -> list[str]:
    """What its feelings may be about besides the gate's open items: the items it's concerned about (from the hourly
    tick) and what it's speaking up about right now (vocal, within the hour). Lower case."""
    st = state(app)
    out = []
    if empathy_on(app):
        out += [str(c["item"]).lower() for c in st.get("concerns") or [] if c.get("concern", 0) >= NOTICE_AT]
    if st.get("vocal_item") and time.time() - float(st.get("vocal_at") or 0) < 3600:
        out.append(str(st["vocal_item"]).lower())
    return out


def bids(app: App, now_t: float) -> list:
    """Workspace bids: what it's concerned about bids for its attention (what it notices)."""
    from kurooto.mind.workspace import Bid

    if not empathy_on(app):
        return []
    out = []
    for c in state(app).get("concerns") or []:
        if c.get("concern", 0) < NOTICE_AT:
            continue
        slug = re.sub(r"[^a-z0-9]+", "-", str(c["item"]).lower()).strip("-")[:30] or "item"
        out.append(Bid(f"concern:{c['kind']}:{slug}", "concern", f"{c['item']}: {c['why']}", stake=c["concern"],
                       urgency=c["risk"], module="feelings", source="saw"))  # fmt: skip
    return out


def _body(app: App) -> dict:
    try:
        from kurooto.mind import stimulation

        return stimulation.state(app) if stimulation.on(app) else {}
    except Exception:
        return {}


# ------------------------------------------------------------------------------------------------- vocal (I-7')
EXCITE_MIN = 0.8  # the evidence it needs to speak up unasked (confidence or replication rate)
VOCAL_GAP_S = 24 * 3600


def threshold(app: App) -> float:
    return {"high": EXCITE_MIN - 0.1, "low": EXCITE_MIN + 0.1}.get(mood_band(app), EXCITE_MIN)


def findings(app: App, bar: float) -> list[dict]:
    """What it could be excited or worried about, each with its evidence: {id, label, item, finding, confidence}.
    Never about how you are (the read's beliefs are left out: those only ever make a message quieter)."""
    out: list[dict] = []
    try:
        from kurooto.mind import beliefs

        if beliefs.on(app):
            for r in beliefs._state(app)["rows"]:  # noqa: SLF001
                if (
                    r.get("outcome") is not None
                    or r.get("topic") in ("read", "you")
                    or r["source"] not in ("saw", "inferred")
                ):
                    continue  # fmt: skip
                if float(r.get("confidence") or 0) >= bar:
                    said = beliefs.phrase(r)  # worded for its source (I-13): an inferred one says "it looks like"
                    if r["source"] == "saw":
                        said = f"{said.rstrip('.')} (I saw it; {round(float(r['confidence']) * 100)}% sure)."
                    out.append({"id": f"belief:{r['id']}", "label": "excited", "item": r.get("topic") or "this",
                                "finding": said, "confidence": float(r["confidence"])})  # fmt: skip
    except Exception:
        pass
    try:
        last = jload(app.paths.state / "lab" / "last-night.json", {}) or {}
        for slug, r in (last.get("projects") or {}).items():
            rate = float(r.get("rate") or 0.0)
            if int(r.get("replicated") or 0) >= 1 and rate >= bar:
                out.append({"id": f"lab:{slug}:{r.get('batch')}", "label": "excited", "item": slug,
                            "finding": f"{r['replicated']} configuration(s) beat your best and replicated "
                            f"(replication rate {rate:.0%}).", "confidence": rate})  # fmt: skip
    except Exception:
        pass
    for c in state(app).get("concerns") or []:
        if float(c.get("risk") or 0) >= bar:
            risk = float(c["risk"])
            out.append({"id": f"concern:{c['kind']}:{c['item']}", "label": "worried", "item": c["item"],
                        "finding": f"{c['why']} (risk {risk:.0%}).", "confidence": risk})  # fmt: skip
    return sorted(out, key=lambda f: -f["confidence"])


def vocal(app: App, payload: dict | None = None) -> bool:
    """I-7': one excited or worried message, unasked, when a finding's evidence is over the bar. It goes through
    app.notify, so the gate (lints, caps, the not-a-pest model) and Calm decide; at most one a day, each finding once.
    False when nothing was said."""
    if not mind.part_on(app, "feelings") or not app.settings.get("mind.feelings.vocal"):
        return False
    st = state(app)
    t = now().timestamp()
    if st.get("vocal_at") and t - float(st["vocal_at"]) < VOCAL_GAP_S:
        return False
    said = list(st.get("vocal_said") or [])
    fresh = [f for f in findings(app, threshold(app)) if f["id"] not in said]
    if not fresh:
        return False
    f = fresh[0]
    text = TEMPLATES[f["label"]].format(item=f["item"], finding=f["finding"])
    with Lock(app.paths.state, "mind-feelings"):  # written first: the gate's lints read what it's speaking of
        st = state(app)
        st["vocal_at"] = t
        st["vocal_item"] = str(f["item"])[:80]
        st["vocal_said"] = [*said, f["id"]][-50:]
        jsave(app.paths.state / FILE, st)
    sent = app.notify(text, kind="info", why=f"mind.{f['label']}")
    app.events.emit("mind_vocal", label=f["label"], sent=sent is not None, confidence=round(f["confidence"], 2))
    return sent is not None

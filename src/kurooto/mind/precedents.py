"""Values as case law (Brain, 0.8.0 stage 17a, off by default: `mind.precedents.on`).

When Kurooto faces a judgement call between two of your values ("protect your sleep" or "finish the report", "don't
interrupt study"
or "remind you of the call") it asks you once. Your answer is a **precedent**: a short case with the situation, the
two values and
your ruling. Later, a similar situation follows the precedent without asking. When a situation fits two precedents
that point different
ways it asks again, and the new ruling refines the case law. You can read, edit and delete every case (`/precedents`).

    Precedent {id, features, values: [a, b], ruling: a | b | both | depends, note, date, source: said}
    features   {time_band, kinds: [..], proximity (none | days | hours), state_band, channel}: what the situation was
    like

Bounded: a precedent chooses between two of your values, nothing more. It can't unlock anything on the always-ask list
(mind/risk.py,
core/tap.py), and it never overrides the invariants; those questions are asked every time. A ruling of `depends`
always asks.

    judge(app, values, features, question)   follow a precedent, or ask (once), or say it must always ask
    answer(app, qid, ruling, note)           your ruling becomes a precedent
    flags(app)                               past decisions that went against a precedent, for you to rule on
"""

from __future__ import annotations

import datetime as dt
import time
import uuid
from typing import TYPE_CHECKING

from kurooto import mind
from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave
from kurooto.core.tap import GUARDED
from kurooto.mind import risk

if TYPE_CHECKING:
    from kurooto.app import App

PART = "precedents"  # its switch: mind.precedents.on
FILE = "mind-precedents.json"
RULINGS = ("a", "b", "both", "depends")
TIME_BANDS = ("night", "morning", "afternoon", "evening")
PROXIMITY = ("none", "days", "hours")
WEIGHTS = {"time_band": 0.2, "kinds": 0.3, "proximity": 0.2, "state_band": 0.15, "channel": 0.15}
CLOSE = 0.08  # two matches within this of each other, pointing different ways, are a conflict

register_defaults(
    "mind",
    {
        "precedents": {
            "on": False,  # off until you turn it on: judgement calls between your values are asked once, then followed
            "threshold": 0.75,  # how alike two situations must be for a precedent to be followed
        }
    },
)


def on(app: App) -> bool:
    return mind.part_on(app, "precedents")


def _state(app: App) -> dict:
    d = jload(app.paths.state / FILE, {}) or {}
    for k, v in (("cases", []), ("pending", {}), ("decisions", [])):
        d.setdefault(k, v)
    return d


def _save(app: App, d: dict) -> None:
    d["decisions"] = d["decisions"][-200:]
    jsave(app.paths.state / FILE, d)


def time_band(t: dt.datetime | None = None) -> str:
    h = (t or dt.datetime.now()).hour
    return "night" if h < 6 or h >= 23 else "morning" if h < 12 else "afternoon" if h < 18 else "evening"


def features(
    app: App, kinds: list[str], channel: str = "telegram", hours_to_deadline: float | None = None, state_band: str = ""
) -> dict:
    prox = (
        "none"
        if hours_to_deadline is None
        else "hours"
        if hours_to_deadline < 24
        else "days"
        if hours_to_deadline < 24 * 7
        else "none"
    )
    return {
        "time_band": time_band(),
        "kinds": sorted({str(k)[:20] for k in kinds}),
        "proximity": prox,
        "state_band": state_band[:12],
        "channel": channel[:12],
    }


def similarity(a: dict, b: dict) -> float:
    """1 for the same kind of situation, down to 0: a weighted match of the features."""
    s = WEIGHTS["time_band"] * (
        1.0
        if a.get("time_band") == b.get("time_band")
        else 0.5
        if {a.get("time_band"), b.get("time_band")} <= {"night", "evening"}
        else 0.0
    )
    ka, kb = set(a.get("kinds") or []), set(b.get("kinds") or [])
    s += WEIGHTS["kinds"] * (len(ka & kb) / len(ka | kb) if ka | kb else 1.0)
    pa, pb = PROXIMITY.index(a.get("proximity", "none")), PROXIMITY.index(b.get("proximity", "none"))
    s += WEIGHTS["proximity"] * (1.0 - abs(pa - pb) / 2)
    s += WEIGHTS["state_band"] * (1.0 if a.get("state_band", "") == b.get("state_band", "") else 0.0)
    s += WEIGHTS["channel"] * (1.0 if a.get("channel") == b.get("channel") else 0.0)
    return round(s, 4)


def _same_values(p: dict, values: tuple[str, str]) -> bool:
    return set(p["values"]) == set(values)


def _oriented(p: dict, values: tuple[str, str]) -> str:
    """The ruling as 'the first value' / 'the second value' / both / depends, for the order the caller asks in."""
    if p["ruling"] in ("both", "depends"):
        return p["ruling"]
    chosen = p["values"][0] if p["ruling"] == "a" else p["values"][1]
    return "a" if chosen == values[0] else "b"


def matches(app: App, values: tuple[str, str], feats: dict) -> list[tuple[float, dict]]:
    th = float(app.settings.get("mind.precedents.threshold") or 0.75)
    got = [(similarity(feats, p["features"]), p) for p in _state(app)["cases"] if _same_values(p, values)]
    return sorted((x for x in got if x[0] >= th), key=lambda x: -x[0])


def judge(app: App, values: tuple[str, str], feats: dict, question: str = "", action: str = "") -> dict:
    """{"decision": "a" | "b" | "both" | "ask", "follow": id | None, "why": ...}. Asks (once, with buttons) when there's
    no precedent
    close enough, when two close ones disagree, when the ruling was 'depends', or when `action` is one that always
    asks."""
    if not on(app):
        return {"decision": "ask", "follow": None, "why": "precedents are off"}
    if action and (action in GUARDED or risk.classify(action) == "ALWAYS"):
        return {"decision": "ask", "follow": None, "why": "it always asks"}  # case law can't unlock this
    ms = matches(app, values, feats)
    if ms:
        top = ms[0]
        rivals = [m for m in ms[1:] if top[0] - m[0] <= CLOSE and _oriented(m[1], values) != _oriented(top[1], values)]
        if not rivals and top[1]["ruling"] != "depends":
            return {"decision": _oriented(top[1], values), "follow": top[1]["id"], "why": "a precedent"}
        why = "two precedents disagree" if rivals else "the last ruling was 'it depends'"
        return _ask(app, values, feats, question, why, [top[1]["id"], *[r[1]["id"] for r in rivals]])
    return _ask(app, values, feats, question, "no precedent yet", [])


def _ask(app: App, values: tuple[str, str], feats: dict, question: str, why: str, refines: list[str]) -> dict:
    st = _state(app)
    qid = uuid.uuid4().hex[:8]
    st["pending"][qid] = {"values": list(values), "features": feats, "refines": refines, "at": time.time()}
    for k in list(st["pending"])[:-20]:
        st["pending"].pop(k, None)
    _save(app, st)
    a, b = values
    app.notify(
        (question or f"A judgement call: {a}, or {b}?") + f" (I'll remember what you say: {why}.)",
        kind="question",
        why="mind.precedent",
        buttons=[
            [(a[:24], f"prec:{qid}:a"), (b[:24], f"prec:{qid}:b")],
            [("Both", f"prec:{qid}:both"), ("It depends", f"prec:{qid}:depends")],
        ],
    )
    return {"decision": "ask", "follow": None, "why": why, "asked": qid}


def answer(app: App, qid: str, ruling: str, note: str = "") -> dict | None:
    """Your ruling on a question it asked: the new precedent (it replaces the ones it refines)."""
    st = _state(app)
    q = st["pending"].pop(qid, None)
    if q is None or ruling not in RULINGS:
        return None
    case = {
        "id": "c" + uuid.uuid4().hex[:7],
        "features": q["features"],
        "values": q["values"],
        "ruling": ruling,
        "note": note[:200],
        "date": dt.date.today().isoformat(),
        "source": "said",
        "refines": q["refines"],
    }
    st["cases"] = [
        c for c in st["cases"] if c["id"] not in q["refines"] or similarity(c["features"], q["features"]) < 0.999
    ] + [case]
    _save(app, st)
    return case


def button(app: App, ref: str, act: str) -> str:
    c = answer(app, ref, act)
    return "Noted: I'll remember that." if c else "That question has expired."


def cases(app: App) -> list[dict]:
    return _state(app)["cases"]


def edit(app: App, cid: str, ruling: str) -> bool:
    st = _state(app)
    c = next((x for x in st["cases"] if x["id"] == cid), None)
    if c is None or ruling not in RULINGS:
        return False
    c["ruling"], c["source"], c["date"] = ruling, "said", dt.date.today().isoformat()
    _save(app, st)
    return True


def delete(app: App, cid: str) -> bool:
    st = _state(app)
    n = len(st["cases"])
    st["cases"] = [c for c in st["cases"] if c["id"] != cid]
    _save(app, st)
    return len(st["cases"]) < n


def note_decision(app: App, values: tuple[str, str], feats: dict, chose: str, what: str = "") -> None:
    """A past decision, kept so Dreaming can check it against the case law."""
    st = _state(app)
    st["decisions"].append(
        {"values": list(values), "features": feats, "chose": chose, "what": what[:80], "at": time.time()}
    )
    _save(app, st)


def flags(app: App) -> list[dict]:
    """Past decisions that went against a precedent that matched them: for you to rule on in /retro."""
    out = []
    for d in _state(app)["decisions"]:
        ms = matches(app, tuple(d["values"]), d["features"])
        if ms and ms[0][1]["ruling"] in ("a", "b") and _oriented(ms[0][1], tuple(d["values"])) != d["chose"]:
            out.append({"decision": d, "precedent": ms[0][1]["id"]})
    return out


def listing(app: App) -> str:
    if not on(app):
        return "Precedents are off (mind.precedents.on)."
    cs = cases(app)
    if not cs:
        return "No precedents yet. When a judgement call comes up between two of your values, I ask once and remember."
    out = ["Your precedents (how I settle a call between two of your values):"]
    for c in cs:
        who = {"a": c["values"][0], "b": c["values"][1]}.get(c["ruling"], c["ruling"])
        feats = c["features"]
        out.append(
            f"- [{c['id']}] {c['values'][0]} vs {c['values'][1]}: {who} ({feats['time_band']}, "
            f"{', '.join(feats['kinds']) or 'any'}, {c['date']})" + (f": {c['note']}" if c["note"] else "")
        )
    fl = flags(app)
    if fl:
        out.append(f"{len(fl)} past decision(s) went against a precedent; /retro asks you to rule on them.")
    return "\n".join(out) + "\n/precedents edit <id> <a|b|both|depends>, /precedents delete <id>"

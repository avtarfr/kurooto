"""Deciding whether to do it or ask (Brain, 0.8.0 stage 06): the entry point for what Kurooto does on its own.

    verdict(app, action)         the class, whether trust lets it act unasked, and why
    run(app, action, fn, args)   do it, or ask first, as the verdict says; an act it did is written down for the
    Sunday digest
    record(app, action, ...)     an act it did on its own (to list with an Undo)
    evidence(app, action, kind)  your reaction (ok, undo, complaint, silence) goes to the scorekeeper's trust
    digest(app)                  "What I did on my own" every Sunday, an Undo per act and a Seen it button
    status(app)                  /autonomy

Always asks (I-8): everything in core/tap.py's GUARDED, anything unclassified, an action you said "never" for and a
class you set
to always-ask. For the rest, trust (mind/trust.py) decides: R0 acts from the start, R1 to R3 earn it from your
reactions.

Shadow, for the first `mind.autonomy.shadow_days` (21): the verdict is computed and counted ("would have done it
unasked") and
shown in /autonomy, and by default that's all: what Kurooto already does by itself keeps happening as it did, so
nothing that
works today stops until you've seen the counts. `mind.autonomy.enforce` (off) makes the verdicts bind, shadow or not:
then an
R1 or higher act it isn't trusted with asks first (Do it / Not now / Never for this kind), and always does during
shadow.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from typing import TYPE_CHECKING

from kurooto import mind
from kurooto.core.config import register_defaults
from kurooto.core.lock import Lock
from kurooto.core.state import jload, jsave
from kurooto.mind import risk, trust

if TYPE_CHECKING:
    from kurooto.app import App

PART = "autonomy"  # its switch: mind.autonomy.on

register_defaults(
    "mind",
    {
        "autonomy": {
            "on": True,  # decide what it may do unasked from your reactions, per class of action (shadow first)
            "shadow_days": 21,  # for this long its verdicts are counted and shown, not enforced
            "thresholds": {},  # your own bars per class, over the defaults: {"R1": 0.8}
            "enforce": False,  # on: its verdicts bind (it asks first for what it isn't trusted with), shadow or not
        }
    },
)

FILE = "mind-acts.json"
KEEP_ACTS = 200
DIGEST_MAX = 6
PENDING_MAX = 20
RUNNERS: dict[str, Callable[[App, object], str]] = {}  # an action's runner, so a question that waited can do it later
UNDOERS: dict[str, Callable[[App, object], str]] = {}


def register(action: str, runner: Callable | None = None, undoer: Callable | None = None) -> None:
    if runner is not None:
        RUNNERS[action] = runner
    if undoer is not None:
        UNDOERS[action] = undoer


def _state(app: App) -> dict:
    d = jload(app.paths.state / FILE, {}) or {}
    d.setdefault("started", time.time())
    for k, v in (("acts", []), ("pending", {}), ("never", []), ("always_ask", []), ("classified", {}), ("would", {})):
        d.setdefault(k, v)
    return d


def _save(app: App, d: dict) -> None:
    jsave(app.paths.state / FILE, d)


def on(app: App) -> bool:
    return mind.part_on(app, "autonomy")


def in_shadow(app: App, st: dict | None = None) -> bool:
    st = st or _state(app)
    days = app.settings.get("mind.autonomy.shadow_days")
    days = float(days) if isinstance(days, (int, float)) else 21.0
    return time.time() - float(st["started"]) < days * 86400


def klass_of(app: App, action: str, ai_class: str | None = None, st: dict | None = None) -> str:
    st = st or _state(app)
    mine = st["classified"].get(action)
    base = risk.classify(action, ai_class)
    if mine in risk.PRIORS and base == "ALWAYS" and action not in risk.all_actions():
        return mine  # an unknown action you classified yourself
    return base


def verdict(app: App, action: str, ai_class: str | None = None) -> dict:
    """{klass, do, why, would}: do is whether trust lets it act without asking right now."""
    st = _state(app)
    k = klass_of(app, action, ai_class, st)
    out = {"klass": k, "do": False, "why": "", "shadow": in_shadow(app, st)}
    if k == "ALWAYS" or action in st["never"] or k in st["always_ask"]:
        out["why"] = "it always asks" if k == "ALWAYS" else "you set this to ask first"
        return out
    rows = {r["key"]: r for r in mind.connect(app).trust_rows()}
    state = (rows.get(k) or {}).get("meta")
    th = app.settings.get("mind.autonomy.thresholds")
    ok = trust.may_act(state, k, time.time(), th if isinstance(th, dict) else None)
    out["do"] = ok
    out["why"] = "trusted with this kind" if ok else "not trusted with this kind yet"
    return out


def run(
    app: App,
    action: str,
    fn: Callable[[object], object],
    args: object = None,
    summary: str = "",
    ai_class: str | None = None,
    undo_from: Callable[[object], object] | None = None,
) -> object:
    """Do it, or ask first. Returns what fn returned, or None when it asked. With autonomy off, or while
    it
    isn't enforcing, fn runs as it always did; the verdict is counted and a done act is written down."""
    if not on(app):
        return fn(args)
    v = verdict(app, action, ai_class)
    enforce = bool(app.settings.get("mind.autonomy.enforce"))
    # it asks when trust doesn't let it act, and during shadow for everything above R0 (R0 is inward and reversible)
    needs_ask = (not v["do"]) or (v["shadow"] and v["klass"] != "R0")
    with Lock(app.paths.state, "mind-acts"):
        st = _state(app)
        w = st["would"].setdefault(v["klass"], {"done": 0, "asked": 0})
        w["asked" if needs_ask else "done"] += 1  # "would have done it unasked" / "would have asked"
        _save(app, st)
    if needs_ask and enforce:
        return _ask(app, action, v["klass"], args, summary)
    if v["klass"] == "ALWAYS":  # never by this path: the guarded actions have their own (core/tap.py)
        app.events.emit("act_always_ask", action=action[:40])
        return None
    out = fn(args)
    payload = undo_from(out) if (undo_from is not None and out) else None
    record(app, action, summary or action, {"runner": action, "payload": payload} if payload else None, v["klass"])
    return out


def _ask(app: App, action: str, klass: str, args: object, summary: str) -> None:
    pid = uuid.uuid4().hex[:8]
    with Lock(app.paths.state, "mind-acts"):
        st = _state(app)
        st["pending"][pid] = {
            "action": action,
            "args": args,
            "klass": klass,
            "summary": summary[:160],
            "at": time.time(),
        }
        for k in list(st["pending"])[:-PENDING_MAX]:
            st["pending"].pop(k, None)
        _save(app, st)
    app.notify(
        f"May I {summary or action}? ({risk.LABELS.get(klass, klass)})",
        kind="question",
        why="mind.act_ask",
        buttons=[
            [("Do it", f"aut:{pid}:do"), ("Not now", f"aut:{pid}:later"), ("Never for this kind", f"aut:{pid}:never")]
        ],
    )
    return None


def record(app: App, action: str, summary: str, undo: dict | None = None, klass: str | None = None) -> str:
    """An act it did on its own, to list in the Sunday digest (with Undo when it has one)."""
    aid = uuid.uuid4().hex[:8]
    with Lock(app.paths.state, "mind-acts"):
        st = _state(app)
        st["acts"] = [
            *st["acts"],
            {
                "id": aid,
                "action": action,
                "klass": klass or risk.classify(action),
                "summary": str(summary)[:160],
                "at": time.time(),
                "undo": undo,
                "undone": False,
                "listed": False,
                "seen": False,
            },
        ][-KEEP_ACTS:]
        _save(app, st)
    app.events.emit("mind_act", klass=(klass or risk.classify(action)), action=str(action)[:40])
    return aid


def evidence(app: App, action_or_class: str, kind: str, seen: bool = True) -> bool:
    """Your reaction to an act of this kind: ok, undo, complaint or silence. To the scorekeeper's trust."""
    k = action_or_class if action_or_class in risk.PRIORS else risk.classify(action_or_class)
    if k not in risk.PRIORS or kind not in trust.EVIDENCE:
        return False
    return mind.connect(app).report("trust_evidence", {"class": k, "evidence": kind, "seen": bool(seen)})


# -------------------------------------------------------------------------------------------------- buttons
def button(app: App, ref: str, act: str) -> str:
    """Do it / Not now / Never under a question; Undo and Seen it under the digest; Always ask under /autonomy."""
    if ref == "digest" and act == "seen":
        return _seen(app)
    if ref == "class" or act == "alwaysask":
        return _always_ask(app, ref if ref in risk.PRIORS else act)
    with Lock(app.paths.state, "mind-acts"):
        st = _state(app)
        if act == "undo":
            a = next((x for x in st["acts"] if x["id"] == ref), None)
            if a is None or a["undone"] or not a.get("undo"):
                return "That one can't be undone any more."
            undoer = UNDOERS.get(a["undo"]["runner"])
            if undoer is None:
                return "Nothing knows how to undo that."
            msg = undoer(app, a["undo"]["payload"])
            a["undone"] = True
            _save(app, st)
        else:
            p = st["pending"].pop(ref, None)
            if p is None:
                return "That question is gone."
            if act == "never":
                st["never"] = sorted({*st["never"], p["action"]})
                _save(app, st)
                evidence(app, p["klass"], "complaint")
                return f"Understood: I won't do that on my own again ({p['summary'] or p['action']})."
            if act != "do":
                _save(app, st)
                return "Alright, not now."
            _save(app, st)
    if act == "undo":
        evidence(app, a["klass"], "undo")
        return msg
    runner = RUNNERS.get(p["action"])
    if runner is None:
        return "I can't do that from here any more."
    out = runner(app, p["args"])
    evidence(app, p["klass"], "ok")
    record(app, p["action"], p["summary"], None, p["klass"])
    return str(out or "Done.")


def _seen(app: App) -> str:
    n = 0
    with Lock(app.paths.state, "mind-acts"):
        st = _state(app)
        todo = [a for a in st["acts"] if a["listed"] and not a["seen"] and not a["undone"]]
        for a in todo:
            a["seen"] = True
        _save(app, st)
    for a in todo:  # an act in a digest you opened and left alone: a little trust
        evidence(app, a["klass"], "silence", seen=True)
        n += 1
    return f"Thanks: {n} noted as fine." if n else "Nothing new to mark."


def _always_ask(app: App, klass: str) -> str:
    if klass not in risk.PRIORS:
        return "No such class."
    with Lock(app.paths.state, "mind-acts"):
        st = _state(app)
        st["always_ask"] = sorted({*st["always_ask"], klass})
        _save(app, st)
    return f"{klass} now always asks first."


# -------------------------------------------------------------------------------------------------- the digest
def digest(app: App, payload: dict | None = None) -> bool:
    """Sunday: what it did on its own this week, an Undo for each that has one, and Seen it. False when there's
    nothing."""
    if not on(app):
        return False
    since = time.time() - 7 * 86400
    with Lock(app.paths.state, "mind-acts"):
        st = _state(app)
        acts = [a for a in st["acts"] if a["at"] >= since and not a["listed"] and not a["undone"]][-DIGEST_MAX:]
        for a in acts:
            a["listed"] = True
        _save(app, st)
    if not acts:
        return False
    lines = ["What I did on my own this week:"] + [f"- {a['summary']}" for a in acts]
    rows = [[("Undo", f"aut:{a['id']}:undo")] for a in acts if a.get("undo")][:4]
    rows.append([("Seen it", "aut:digest:seen")])
    app.notify("\n".join(lines), kind="info", why="mind.act_digest", buttons=rows)
    return True


def digest_lines(app: App) -> list[str]:
    st = _state(app)
    since = time.time() - 7 * 86400
    return [a["summary"] for a in st["acts"] if a["at"] >= since and not a["undone"]]


# -------------------------------------------------------------------------------------------------- /autonomy
def bar(p: float, width: int = 10) -> str:
    n = max(0, min(width, round(p * width)))
    return "█" * n + "·" * (width - n)


def status(app: App) -> tuple[str, list]:
    if not mind.on(app):
        return "Brain is off (Features → Brain).", []
    if not on(app):
        return "Autonomy is off (mind.autonomy.on): it asks as it did before 0.8.", []
    st = _state(app)
    now = time.time()
    rows = {r["key"]: r for r in mind.connect(app).trust_rows()}
    th = {**risk.THRESH, **(app.settings.get("mind.autonomy.thresholds") or {})}
    shadow = in_shadow(app, st)
    left = max(0.0, float(app.settings.get("mind.autonomy.shadow_days") or 21) - (now - float(st["started"])) / 86400)
    lines = [
        "What Kurooto may do without asking, by kind of action (it learns from your OKs, undos and complaints):",
        (
            f"In shadow for {left:.0f} more days: it only counts what it would have done."
            if shadow
            else "Out of shadow."
        ),
    ]
    for k in ("R0", "R1", "R2", "R3"):
        s = (rows.get(k) or {}).get("meta") or {}
        p = trust.p10(s, k, now)
        n = s.get("n") or {}
        w = st["would"].get(k) or {"done": 0, "asked": 0}
        need = float(th.get(k, 1))
        seen = f"OK {n.get('ok', 0)}, undo {n.get('undo', 0)}, complaints {n.get('complaint', 0)}"
        lines.append(
            f"{k} {risk.LABELS[k]}: {bar(p)} {p:.2f} (needs {need:.2f}); {seen}; "
            f"would have done {w['done']}, asked {w['asked']}" + (" [always asks]" if k in st["always_ask"] else "")
        )
    n_always = sum(1 for c in risk.all_actions().values() if c == "ALWAYS")
    lines.append(f"Always asks: {n_always} kinds, never unlockable.")
    if st["never"]:
        lines.append("Told never: " + ", ".join(st["never"]))
    buttons = [[(f"{k}: always ask", f"aut:class:{k}") for k in ("R1", "R2", "R3")]]
    return "\n".join(lines), buttons


def classify_cmd(app: App, action: str, klass: str) -> str:
    """/autonomy classify <action> <R0|R1|R2|R3>: you classify an action nobody has."""
    klass = klass.upper()
    if klass not in risk.PRIORS or action in risk.all_actions():
        return "Say a class R0, R1, R2 or R3 for an action it doesn't know yet."
    with Lock(app.paths.state, "mind-acts"):
        st = _state(app)
        st["classified"][action[:60]] = klass
        _save(app, st)
    return f"{action}: {klass}."

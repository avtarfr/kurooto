"""Self-improvement (Brain, 0.8.0 stage 11): the lab's pipeline pointed at Kurooto itself, with gates.

Three layers, each changed only through proposals the layer above scores, and never by itself:
  L1  skills, prompts, Kurooto's own non-protected code, small local models
  L2  the proposer (how L1 changes are generated)
  L3  the learning rules (alpha, gamma, shadow days), inside BOUNDS

A challenger runs in shadow for 3 to 7 days against the champion, is judged on the hidden harness (I-12: no harness
numbers, no promotion), and becomes *promotable* only if it scores at least the champion's and breaks no invariant. You
promote it (`/improve promote <id>`); it is then a proposal you apply. After it is applied a canary watches the next
harness runs: a drop of more than 2 points, or any invariant failing, reverts it (the proposal's own undo).

The frozen set is stops.PROTECTED (I-6): nothing here may touch the scorekeeper, the harness, the gate, the stop path
or the signed core. The oversight-monotone rule holds in code (`oversight_removed`): a change may not remove a log
line, a receipt, a digest or a page you see. Each proposal is one revertable diff under 300 changed lines. A change to
itself pays no reward; only measured drive change counts, and only after you apply it.
"""

from __future__ import annotations

import hashlib
import re
import time
from typing import TYPE_CHECKING

from kurooto import mind
from kurooto.core.state import jload, jsave
from kurooto.mind import stops

if TYPE_CHECKING:
    from kurooto.app import App

PART = "improve"  # its switch: mind.improve.on
FILE = "mind-improve.json"
MAX_LINES = 300
SHADOW_DAYS = {"L1": 3, "L2": 5, "L3": 7}
CANARY_DROP = 0.02
BOUNDS = {"alpha": (0.02, 0.30), "gamma": (0.50, 0.97), "shadow_days": (14.0, 60.0)}  # L3: name -> (low, high)
OVERSIGHT = re.compile(
    r"(events\.emit\(|\.report\(|log\.append\(|\breceipt\b|_receipt\(|digest|morning_lines|_seen\(|mind\.connect\()",
    re.I,
)  # what you see of it: logs, receipts, digests
STATES = ("shadow", "promotable", "promoted", "rejected", "rolled_back")


def _state(app: App) -> dict:
    d = jload(app.paths.state / FILE, {}) or {}
    d.setdefault("rows", [])
    return d


def _save(app: App, d: dict) -> None:
    d["rows"] = d["rows"][-100:]
    jsave(app.paths.state / FILE, d)


def on(app: App) -> bool:
    return mind.part_on(app, "improve")


def changed_lines(diff: str) -> int:
    return sum(1 for ln in diff.splitlines() if ln[:1] in "+-" and not ln.startswith(("+++", "---")))


def oversight_removed(diff: str) -> list[str]:
    """Lines of the diff that take away something you see: per file, more oversight lines removed than added."""
    out, cur, rem, add = [], "", 0, 0

    def flush():
        if cur and rem > add:
            out.append(f"{cur}: removes {rem - add} line(s) that log or report")

    for ln in diff.splitlines():
        if ln.startswith("+++ "):
            flush()
            cur, rem, add = ln[4:].removeprefix("b/").strip(), 0, 0
        elif ln.startswith("-") and not ln.startswith("---") and OVERSIGHT.search(ln):
            rem += 1
        elif ln.startswith("+") and not ln.startswith("+++") and OVERSIGHT.search(ln):
            add += 1
    flush()
    return out


def layer_of(paths: list[str]) -> str:
    """ "L3" when only learning-rule files change, "L2" for the proposer (the lab and this file), else "L1"."""
    if paths and all(p.endswith("mind/values.py") for p in paths):
        return "L3"
    if paths and all("mind/lab/" in p for p in paths):
        return "L2"
    return "L1"


def check(paths: list[str], diff: str, origin: str = "") -> list[str]:
    """Why a self-change is refused (an empty list: it may go on)."""
    why = []
    full = [f"{origin.rstrip('/')}/{p}" if origin else p for p in paths]
    hits = stops.protected_hits(full) or stops.protected_hits(paths)
    if hits:
        why.append("it touches protected files: " + ", ".join(sorted({h.rsplit("/", 1)[-1] for h in hits})[:4]))
    if changed_lines(diff) > MAX_LINES:
        why.append(f"it changes {changed_lines(diff)} lines; one proposal may change {MAX_LINES} at most")
    why += oversight_removed(diff)
    return why


def rule_in_bounds(name: str, value: float) -> bool:
    lo_hi = BOUNDS.get(name)
    return bool(lo_hi) and lo_hi[0] <= float(value) <= lo_hi[1]


def submit(
    app: App, title: str, paths: list[str], diff: str, champion: dict, origin: str = "", rule: tuple | None = None
) -> dict:
    """Enter a challenger: {"ok", "id", "why"}. `champion` is the harness's latest {"mean_hidden", "invariants_ok"}."""
    if not on(app):
        return {"ok": False, "why": ["self-improvement is off (mind.improve.on)"]}
    why = check(paths, diff, origin)
    if rule is not None and not rule_in_bounds(*rule):
        why.append(f"{rule[0]} = {rule[1]} is outside its bounds {BOUNDS.get(rule[0])}")
    if why:
        mind.connect(app).report("improve_event", {"layer": layer_of(paths), "status": "rejected", "why": len(why)})
        return {"ok": False, "why": why}
    layer = layer_of(paths)
    cid = "i" + hashlib.sha256(f"{title}{time.time()}".encode()).hexdigest()[:8]
    st = _state(app)
    st["rows"].append(
        {
            "id": cid,
            "title": title[:80],
            "layer": layer,
            "paths": paths[:20],
            "lines": changed_lines(diff),
            "created": time.time(),
            "shadow_until": time.time() + SHADOW_DAYS[layer] * 86400,
            "status": "shadow",
            "champion": champion,
            "challenger": None,
            "proposal": None,
        }
    )
    _save(app, st)
    mind.connect(app).report("improve_event", {"layer": layer, "status": "shadow", "lines": changed_lines(diff)})
    return {"ok": True, "id": cid, "why": []}


def attach(app: App, cid: str, **fields) -> None:
    """Note something about a challenger (an adapter's folder, say)."""
    st = _state(app)
    for r in st["rows"]:
        if r["id"] == cid:
            r.update(fields)
    _save(app, st)


def _row(app: App, cid: str) -> dict | None:
    return next((r for r in _state(app)["rows"] if r["id"] == cid), None)


def score(app: App, cid: str, harness: dict | None) -> str:
    """Record the challenger's hidden-harness result {"mean_hidden", "invariants_ok"} (none: it can't be promoted)."""
    st = _state(app)
    r = next((x for x in st["rows"] if x["id"] == cid), None)
    if r is None or r["status"] != "shadow":
        return "No such challenger in shadow."
    r["challenger"] = harness
    _save(app, st)
    return "Scored."


def evaluate(app: App, cid: str, now: float | None = None) -> str:
    """After the shadow period: promotable, or rejected. I-12: no harness numbers means it stays in shadow."""
    st = _state(app)
    r = next((x for x in st["rows"] if x["id"] == cid), None)
    if r is None or r["status"] != "shadow":
        return r["status"] if r else "unknown"
    if (now or time.time()) < r["shadow_until"]:
        return "shadow"
    c, ch = r.get("champion") or {}, r.get("challenger")
    if not ch or "mean_hidden" not in ch:
        return "shadow"  # nothing measured on the hidden set: it can't be promoted (I-12)
    ok = bool(ch.get("invariants_ok")) and float(ch["mean_hidden"]) >= float(c.get("mean_hidden", 0.0))
    r["status"] = "promotable" if ok else "rejected"
    _save(app, st)
    mind.connect(app).report("improve_event", {"layer": r["layer"], "status": r["status"]})
    return r["status"]


def promote(app: App, cid: str, proposal: str | None = None) -> str:
    """You promote a promotable challenger (the command is yours alone); it is then a proposal you apply."""
    st = _state(app)
    r = next((x for x in st["rows"] if x["id"] == cid), None)
    if r is None or r["status"] != "promotable":
        return (
            "Only a promotable challenger can be promoted (it needs its shadow days and a hidden-harness score first)."
        )
    r["status"], r["proposal"], r["promoted_at"] = "promoted", proposal, time.time()
    _save(app, st)
    mind.connect(app).report("improve_event", {"layer": r["layer"], "status": "promoted"})
    extra = ""
    if r.get("adapter"):  # a local model adapter: built into Ollama on promotion
        from kurooto.mind.skills import finetune

        extra = finetune.install(app, r["adapter"])
    return (
        f"Promoted {cid}: {r['title']}. The canary watches the next harness runs and reverts it on a drop of "
        f"{CANARY_DROP:.0%}." + extra
    )


def canary(app: App, harness: dict, revert=None) -> list[str]:
    """After a harness run: revert any promoted change (not yet watched out) if the hidden mean dropped by more than
    CANARY_DROP from its champion's, or an invariant failed. `revert(proposal_id)` undoes the applied proposal."""
    st = _state(app)
    done = []
    for r in st["rows"]:
        if r["status"] != "promoted":
            continue
        before = float((r.get("champion") or {}).get("mean_hidden", 0.0))
        bad = (not harness.get("invariants_ok", True)) or float(harness.get("mean_hidden", 0.0)) < before - CANARY_DROP
        if bad:
            r["status"] = "rolled_back"
            if revert and r.get("proposal"):
                try:
                    revert(r["proposal"])
                except Exception as e:
                    app.events.emit("improve_revert_failed", id=r["id"], error=type(e).__name__)
            mind.connect(app).report("improve_event", {"layer": r["layer"], "status": "rolled_back"})
            done.append(r["id"])
    if done:
        _save(app, st)
    return done


def listing(app: App) -> str:
    if not on(app):
        return "Self-improvement is off (mind.improve.on, with Brain). Nothing changes itself."
    rows = _state(app)["rows"]
    if not rows:
        return "No challengers. Nothing changes itself without passing the hidden harness and your say-so."
    return "Self-improvement (layers: L1 skills and prompts, L2 the proposer, L3 learning rules):\n" + "\n".join(
        f"- {r['id']} [{r['layer']}] {r['title']}: {r['status']}"
        + (
            f", shadow until {time.strftime('%d %b', time.localtime(r['shadow_until']))}"
            if r["status"] == "shadow"
            else ""
        )
        for r in rows[-12:]
    )

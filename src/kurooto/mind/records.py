"""Decision records (Brain, 0.8.0): before Kurooto does something on its own (a message it starts, an AI request it
queues, a proposal it makes at night), one record of kind "decision" goes into the mind log, so what it did and why can
be checked later against what happened.

    {"id": uuid4hex,
     "action": "<action class>",              e.g. "message:deadline", "job:research.papers", "proposal:night"
     "candidates": [{"action": str, "score": float}],
     "setpoints": [str],                      the variables it claims the action moves (stage 05)
     "claim": {"setpoint": str, "effect": "+"|"-", "by": iso} | None,   pre-registered (stage 05 learns only from these)
     "scored_reason": str,                    from code: the reason Kurooto's own logic gives (Calm's `why`)
     "stated_reason": str,                    what the AI said, as it said it (empty for rules)
     "source": "rules" | "ai:<brain>",
     "risk_class": str}                       (stage 06; "" until then)

decide() is what the rest of Kurooto calls: with Brain off it does nothing and returns "". With it on, the record goes
to the scorekeeper through the mind client (never written here: invariant I-1). outcome() is the scorekeeper's: it
writes what came of a decision, later.
"""

from __future__ import annotations

import re
import uuid
from math import isfinite
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kurooto.app import App
    from kurooto.mind.log import MindLog

SOURCES = re.compile(r"^(rules|ai:[a-z0-9_.:-]{1,40})$")
TEXT_MAX = 300  # a stated or scored reason is cut to this many characters
ACTION_MAX = 80


def _clip(s, n: int) -> str:
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[: n - 1] + "…"


def make(
    action: str,
    candidates: list | tuple = (),
    setpoints: list | tuple = (),
    claim: dict | None = None,
    scored_reason: str = "",
    stated_reason: str = "",
    source: str = "rules",
    risk_class: str = "",
    id: str | None = None,  # noqa: A002 (the record's field name)
) -> dict:
    """A decision record, checked: the shape above, every string cut to size, a bad source or claim refused."""
    if not SOURCES.match(source or ""):
        raise ValueError(f"bad source: {source!r}")
    if claim is not None:
        if not isinstance(claim, dict) or claim.get("effect") not in ("+", "-") or not claim.get("setpoint"):
            raise ValueError("a claim needs a setpoint and an effect of + or -")
        claim = {"setpoint": _clip(claim["setpoint"], 60), "effect": claim["effect"], "by": _clip(claim.get("by"), 40)}
    cands = []
    for c in list(candidates)[:12]:
        try:
            cands.append({"action": _clip(c["action"], ACTION_MAX), "score": round(float(c["score"]), 6)})
        except (KeyError, TypeError, ValueError):
            continue
    return {
        "id": id or uuid.uuid4().hex,
        "action": _clip(action, ACTION_MAX),
        "candidates": cands,
        "setpoints": [_clip(s, 60) for s in list(setpoints)[:12]],
        "claim": claim,
        "scored_reason": _clip(scored_reason, TEXT_MAX),
        "stated_reason": _clip(stated_reason, TEXT_MAX),
        "source": source,
        "risk_class": _clip(risk_class, 20),
    }


def decide(app: App, action: str, **kw) -> str:
    """Record a decision before acting on it; the record's id, or "" when Brain is off (nothing is written)."""
    from kurooto import mind

    if not mind.on(app):
        return ""
    try:
        rec = make(action, **kw)
    except ValueError:
        return ""
    mind.connect(app).report("decision", rec)
    return rec["id"]


def outcome(log: MindLog, decision_id: str, result: str, value: float | None = None) -> int:
    """What came of a decision: written by the scorekeeper only (the log refuses anyone else)."""
    body = {"decision": _clip(decision_id, 40), "result": _clip(result, 40)}
    if value is not None:
        body["value"] = round(float(value), 6)
    return log.append("outcome", body)


# ---------------------------------------------------------------------------------------- facts from the daemon
ID = re.compile(r"^[A-Za-z0-9_.:@+-]{1,64}$")
DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# the fields of a mirrored event that may be words at all: ids and kinds (a job's id, a button's prefix, a mode);
# everything else that's text is dropped, so nothing anyone typed reaches the log (invariant I-11)
ID_KEYS = frozenset(
    {"id", "job", "key", "verdict", "was", "mode", "module", "subkind", "via", "layer", "prefix", "lane", "source",
     "outcome", "line", "channel", "state", "decision", "result", "gap"}
)  # fmt: skip
FACT_KEYS_MAX = 20


def plain(v, depth: int = 3):
    """Plain JSON data only (text, numbers, true/false, lists, dicts), a few levels deep and a bounded size: what a fact
    about the day may carry to the scorekeeper, which checks every field again (invariant I-1)."""
    if isinstance(v, bool) or v is None:
        return v
    if isinstance(v, (int, float)):
        return v if isfinite(float(v)) else None
    if isinstance(v, str):
        return v[:80]
    if depth <= 0:
        return None
    if isinstance(v, (list, tuple)):
        return [plain(x, depth - 1) for x in list(v)[:40]]
    if isinstance(v, dict):
        return {str(k)[:40]: plain(x, depth - 1) for k, x in list(v.items())[:40]}
    return None


def clean_fact(kind: str, body: dict) -> dict:
    """A mirrored event as the log keeps it: numbers and true/false, and id-like words under ID_KEYS only. The
    engagement fields (whitelist.BANNED_FIELDS) never pass, nor the event's own time and kind."""
    from kurooto.mind.whitelist import BANNED_FIELDS

    if kind == "decision":
        b = dict(body or {})
        try:
            return make(
                b.get("action", ""),
                candidates=b.get("candidates") or (),
                setpoints=b.get("setpoints") or (),
                claim=b.get("claim"),
                scored_reason=b.get("scored_reason", ""),
                stated_reason=b.get("stated_reason", ""),
                source=b.get("source") or "rules",
                risk_class=b.get("risk_class", ""),
                id=b.get("id") if isinstance(b.get("id"), str) and ID.match(b["id"]) else None,
            )
        except ValueError:
            return {}
    if kind == "gate_receipt":  # made by code (mind/gate.py), never from a message's words
        b = body or {}
        read = b.get("read") if isinstance(b.get("read"), dict) else {}
        return {
            "inputs": [str(x) for x in (b.get("inputs") or []) if isinstance(x, str) and ID.match(x)][:12],
            "read": {k: str(read.get(k))[:30] for k in ("label", "confidence") if ID.match(str(read.get(k) or ""))},
            "would_have": str(b.get("would_have") or "")[:40],
            "did": str(b.get("did") or "")[:40],
            "msg_id": str(b.get("msg_id") or "")[:40] if ID.match(str(b.get("msg_id") or "x")) else "",
        }
    if kind in (
        "read_day",
        "read_answer",
        "forecast",
        "forecast_score",
    ):  # made by code (mind/mood.py); numbers and ids
        b = body or {}
        day = str(b.get("day") or "")
        o: dict = {"day_n": int(day.replace("-", "")) if DAY.match(day) else 0}
        for k in ("n_votes", "counted", "right", "holdout", "n", "channels"):
            if isinstance(b.get(k), bool) or (isinstance(b.get(k), int) and abs(b[k]) < 10**9):
                o[k] = b[k]
        for k in ("mean_surprise", "strength"):
            if isinstance(b.get(k), (int, float)) and isfinite(float(b[k])):
                o[k] = round(float(b[k]), 4)
        if isinstance(b.get("hash"), str) and re.fullmatch(r"[0-9a-f]{64}", b["hash"]):
            o["hash"] = b["hash"]
        if isinstance(b.get("planned"), list):
            o["planned"] = [str(x) for x in b["planned"] if isinstance(x, str) and ID.match(x)][:8]
        return o
    out: dict = {}
    for k, v in (body or {}).items():
        k = str(k)
        if k in ("ts", "kind") or k in BANNED_FIELDS or len(out) >= FACT_KEYS_MAX:
            continue
        if isinstance(v, bool) or (isinstance(v, int) and abs(v) < 2**53):
            out[k] = v
        elif isinstance(v, float) and isfinite(v):
            out[k] = round(v, 6)
        elif isinstance(v, str) and k in ID_KEYS and ID.match(v):
            out[k] = v
    return out

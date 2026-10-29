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

decide / expect / outcome (0.8.14, `mind.expect.on`): every message Kurooto starts by itself records what it expects
to come of it, `"expect": {"what": "reply" | "done", "within_h": n}`: a reply for a question or check-in (3 h), done
within 2 h for a nudge. core/notify.py calls expectation() and track(); a reply from you (heard), a tap on one of its
buttons (tapped) or the time running out (sweep, every minute) closes it with outcome(app, ...): the daemon keeps the
row in `<state>/mind-records.json` (ids, reasons and numbers, never the message's words) and the scorekeeper writes the
`outcome` record (a `decision_outcome` fact).
why(app, ref) (`mind.why.on`) answers "Why this?" under a message: the plain reason, what Brain's gate and the
workspace's door did, what it expected and what came of it, and how many it has sent by itself today.
"""

from __future__ import annotations

import re
import time
import uuid
from dataclasses import replace
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
    expect: dict | None = None,
) -> dict:
    """A decision record, checked: the shape above, every string cut to size, a bad source or claim refused. An
    expectation that isn't one of EXPECTS is dropped (the record stands without it)."""
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
        **({"expect": clean_expect(expect)} if clean_expect(expect) else {}),
    }


EXPECTS = ("reply", "done")
EXPECT_MAX_H = 48.0


def clean_expect(e) -> dict | None:
    """{"what": "reply" | "done", "within_h": 0 < n <= 48}, or None."""
    if not isinstance(e, dict) or e.get("what") not in EXPECTS:
        return None
    try:
        h = float(e.get("within_h"))
    except (TypeError, ValueError):
        return None
    return {"what": e["what"], "within_h": round(h, 2)} if isfinite(h) and 0 < h <= EXPECT_MAX_H else None


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


def outcome(target: MindLog | App, decision_id: str, result: str, value: float | None = None) -> int:
    """What came of a decision. Given the mind log, the scorekeeper writes the `outcome` record (the log refuses anyone
    else). Given the app (0.8.14), the daemon closes its open expectation (a reply came, it was done, or the time ran
    out) and hands the scorekeeper a `decision_outcome` fact to write; 1 when something was closed."""
    if hasattr(target, "paths"):
        return _close(target, decision_id, result, value)
    body = {"decision": _clip(decision_id, 40), "result": _clip(result, 40)}
    if value is not None:
        body["value"] = round(float(value), 6)
    return target.append("outcome", body)


# ---------------------------------------------------------------------------------------- facts from the daemon
ID = re.compile(r"^[A-Za-z0-9_.:@+-]{1,64}$")
DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# the fields of a mirrored event that may be words at all: ids and kinds (a job's id, a button's prefix, a mode);
# everything else that's text is dropped, so nothing anyone typed reaches the log (invariant I-11)
ID_KEYS = frozenset(
    {"id", "job", "key", "verdict", "was", "mode", "module", "subkind", "via", "layer", "prefix", "lane", "source",
     "outcome", "line", "channel", "state", "decision", "result", "gap", "label", "klass", "action", "object"}
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
                expect=b.get("expect"),
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


# ---------------------------------------------------------------------------------------- the imported past (0.8.7)
# What each source of the past may hand the scorekeeper (mind/history.py reads them; Keeper.import_rows checks them
# again here): its kinds, and the few words a row may carry, each from a fixed list. Everything else that's text is
# dropped, and so is any number whose name says money or health. "events" rows are Kurooto's own events (log.mirrored)
PAST_KINDS = {
    "jobs": frozenset({"job"}),
    "deadlines": frozenset({"deadline_due", "deadline_finished"}),
    "checkins": frozenset({"checkin"}),
    "quiz": frozenset({"quiz_day"}),
    "calls": frozenset({"call"}),
    "learning": frozenset({"learning_day"}),
    "study": frozenset({"study_day"}),
}
STATES = frozenset(
    {"ok", "failed", "cancelled", "queued", "running", "done", "open", "gone", "dropped", "planned", "asked",
     "answered", "skipped", "deferred", "calling", "ringing", "missed", "realerted", "later", "held", "declined",
     "other"}
)  # fmt: skip
PAST_WORDS = {
    "effort": frozenset({"low", "medium", "high", "auto", "other"}),
    "verdict": frozenset(
        {"ok", "empty", "denied", "rate_limited", "auth", "timeout", "error", "cancelled", "stuck", "other"}
    ),
    "lane": frozenset({"you", "bg", "chk", "other"}),
    "state": STATES,
    "dkind": frozenset({"exam", "task", "quiz", "other"}),
    "checkin": frozenset({"evening", "midday", "night", "other"}),
    "via": frozenset({"request", "call"}),
}
PAST_PATTERNS = {"subj": re.compile(r"^s[0-9a-f]{8}$"), "module": re.compile(r"^[a-z][a-z0-9_]{0,23}$")}
MONEY_OR_HEALTH = re.compile(
    r"(amount|price|cost|money|rupee|inr|usd|eur|salary|balance|spent|paid|payment|fee|bill|debt|loan|income|"
    r"health|weight|pulse|heart|blood|medic|symptom|calorie|bmi)",
    re.I,
)


def past_kind_ok(source: str, kind: str) -> bool:
    if source == "events":
        from kurooto.mind.log import mirrored

        return mirrored(kind) and bool(ID.match(kind or ""))
    return kind in PAST_KINDS.get(source, ())


def clean_past(source: str, kind: str, body: dict) -> dict:
    """A row of the past as it's kept: clean_fact's rules (numbers and true/false), nothing named for money or health,
    and words only from the fixed lists (PAST_WORDS, PAST_PATTERNS): no id-like word passes just because of its field,
    so a word someone typed can't ride in under one (stricter than the live log's clean_fact)."""
    from kurooto.mind.whitelist import BANNED_FIELDS

    body = body if isinstance(body, dict) else {}
    if source == "events":  # stricter than the live log: no id-like words at all, only the fixed lists' words
        return {
            k: v
            for k, v in clean_fact(kind, body).items()
            if not MONEY_OR_HEALTH.search(k) and (not isinstance(v, str) or v in PAST_WORDS.get(k, ()))
        }
    out: dict = {}
    for k, v in body.items():
        k = str(k)
        if k in BANNED_FIELDS or MONEY_OR_HEALTH.search(k) or not ID.match(k) or len(out) >= FACT_KEYS_MAX:
            continue
        if isinstance(v, bool) or (isinstance(v, int) and abs(v) < 2**53):
            out[k] = v
        elif isinstance(v, float) and isfinite(v):
            out[k] = round(v, 4)
        elif isinstance(v, str) and (v in PAST_WORDS.get(k, ()) or (k in PAST_PATTERNS and PAST_PATTERNS[k].match(v))):
            out[k] = v
    return out


# ------------------------------------------------------------------------- decide / expect / outcome (0.8.14)
# The daemon's side: these run in Kurooto, never in the scorekeeper, so they import what they need when called.
FILE = "mind-records.json"  # in the state folder (not state/mind: that's the scorekeeper's)
ROWS_MAX = 300
KEEP_S = 7 * 86400
REPLY_H = 3.0  # a question or check-in expects a reply within this many hours (Calm calls one ignored at 3 h too)
DONE_H = 2.0  # a nudge expects to be acted on within this many hours
RESULTS = frozenset({"replied", "done", "acted", "missed", "less"})
REF = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")


def expect_on(app: App) -> bool:
    from kurooto import mind

    return mind.part_on(app, "expect")


def why_on(app: App) -> bool:
    from kurooto import mind

    return mind.part_on(app, "why")


def _load(app: App) -> dict:
    from kurooto.core.state import jload

    d = jload(app.paths.state / FILE, {}) or {}
    d.setdefault("rows", [])
    return d


def _save(app: App, d: dict) -> None:
    from kurooto.core.state import jsave

    t = time.time()
    d["rows"] = [r for r in d["rows"] if t - float(r.get("at") or 0) < KEEP_S][-ROWS_MAX:]
    jsave(app.paths.state / FILE, d)


def _lock(app: App):
    from kurooto.core.lock import Lock

    return Lock(app.paths.state, "mind-records")


def expectation(app: App, msg) -> dict | None:
    """What a message Kurooto starts by itself expects: a reply for a question or check-in, done within 2 h for a
    nudge (one that asks for your effort), nothing for a plain notice. None with `mind.expect.on` off."""
    try:
        if not expect_on(app):
            return None
        from kurooto.mind import gate, pest

        why = str(getattr(msg, "why", "") or "")
        kind = pest.kind_of(why)
        if msg.kind == "question" or msg.map_kind == "ask" or kind == "check-in" or why.startswith("checkins."):
            return {"what": "reply", "within_h": REPLY_H}
        if kind == "nudge" or gate.asks_effort(msg.text, msg.buttons):
            return {"what": "done", "within_h": DONE_H}
    except Exception:
        pass
    return None


def _gate_said(msg) -> str:
    if str(getattr(msg, "tail", "") or "").startswith("Quieter because"):
        return "Brain's gate made it quieter (the line under it says why)"
    return "it passed Brain's gate as it was"


def track(app: App, decision_id: str, msg, expect: dict | None, door: str = "") -> None:
    """Keep what "Why this?" and the outcomes need about a message that just went out: its record ids, reason, what
    the gate and the door did, its buttons' data and what it expects. Never its words. Never raises."""
    try:
        if not decision_id:
            return
        data = [str(b[1]) for row in (msg.buttons or []) for b in (row or [])
                if isinstance(b, (list, tuple)) and len(b) > 1 and isinstance(b[1], str)][:12]  # fmt: skip
        t = time.time()
        exp = clean_expect(expect)
        row = {
            "id": decision_id,
            "ref": str(getattr(msg, "rid", "") or decision_id),
            "why": str(msg.why or "")[:60],
            "kind": str(msg.kind or "")[:20],
            "at": round(t, 1),
            "expect": exp,
            "by": round(t + exp["within_h"] * 3600, 1) if exp else None,
            "door": str(door or "")[:160],
            "gate": _gate_said(msg),
            "buttons": data,
            "map": [str(msg.map_kind or "")[:20], str(msg.map_ref or "")[:64]] if msg.map_kind else None,
            "outcome": None,
        }
        with _lock(app):
            d = _load(app)
            d["rows"].append(row)
            _save(app, d)
    except Exception as e:
        app.events.emit("mind_records_failed", error=type(e).__name__)


def _close(app: App, decision_id: str, result: str, value: float | None) -> int:
    from kurooto import mind

    if result not in RESULTS or not expect_on(app):
        return 0
    with _lock(app):
        d = _load(app)
        row = next((r for r in d["rows"] if r["id"] == decision_id), None)
        if row is None or row.get("outcome"):
            return 0
        row["outcome"] = {"result": result, "at": round(time.time(), 1)}
        _save(app, d)
    body: dict = {"decision": decision_id, "result": result}
    if value is not None:
        body["value"] = round(float(value), 4)
    mind.connect(app).report("decision_outcome", body)
    return 1


def _open(d: dict, t: float) -> list[dict]:
    return [r for r in d["rows"] if r.get("expect") and not r.get("outcome") and t <= float(r.get("by") or 0)]


def heard(app: App, reply_to: dict | None = None) -> None:
    """A message from you (App.handle): it answers the question it replies to, else the newest open one that expects
    a reply. Never raises."""
    try:
        if not expect_on(app):
            return
        t = time.time()
        rows = [r for r in _open(_load(app), t) if r["expect"]["what"] == "reply"]
        if not rows:
            return
        pick = None
        if isinstance(reply_to, dict) and reply_to.get("ref") is not None:
            want = [str(reply_to.get("kind") or ""), str(reply_to.get("ref"))]
            pick = next((r for r in reversed(rows) if r.get("map") == want), None)
        outcome(app, (pick or rows[-1])["id"], "replied", 1.0)
    except Exception as e:
        app.events.emit("mind_records_failed", error=type(e).__name__)


def tapped(app: App, data: str) -> None:
    """A button you tapped (App.callback): Less of this under one of its messages closes it as unwelcome; one of the
    message's own buttons closes it as done (or as a reply, for a question). Why? closes nothing. Never raises."""
    try:
        if not expect_on(app) or not data:
            return
        prefix, ref, act = (str(data).split(":", 2) + ["", ""])[:3]
        t = time.time()
        rows = _open(_load(app), t)
        if prefix == "calm":
            r = next((r for r in rows if act == "less" and r["ref"] == ref), None)
            if r is not None:
                outcome(app, r["id"], "less", 0.0)
            return
        r = next((r for r in reversed(rows) if data in (r.get("buttons") or [])), None)
        if r is not None:
            outcome(app, r["id"], "done" if r["expect"]["what"] == "done" else "replied", 1.0)
    except Exception as e:
        app.events.emit("mind_records_failed", error=type(e).__name__)


def sweep(app: App) -> int:
    """Every minute: expectations whose time ran out close as missed. How many."""
    if not expect_on(app):
        return 0
    t = time.time()
    late = [r["id"] for r in _load(app)["rows"] if r.get("expect") and not r.get("outcome") and t > float(r["by"])]
    return sum(outcome(app, i, "missed", 0.0) for i in late)


# ------------------------------------------------------------------------------------------------ Why this?
SAID = {
    "replied": "you answered it",
    "done": "you acted on it",
    "acted": "you acted on it",
    "missed": "nothing came of it in time",
    "less": "you asked for less of these",
}


def _row(app: App, ref: str) -> dict | None:
    return next((r for r in reversed(_load(app)["rows"]) if ref in (r["ref"], r["id"])), None)


def sent_today(app: App) -> int:
    """Messages it has sent by itself today: Brain's gate's count, or Calm's when the gate is off."""
    from kurooto.core.clock import now
    from kurooto.mind import gate

    try:
        if gate.on(app):
            return int(gate._load(app)["days"].get(now().date().isoformat(), 0))  # noqa: SLF001
        calm = getattr(app, "calm", None)
        return int(calm.today()["messages"]) if calm is not None else 0
    except Exception:
        return 0


def why(app: App, message_ref: str) -> dict:
    """The long-press "Why this?" of a message Kurooto started: {"ref", "decision", "reason" (plain words), "gate"
    (what Brain's gate did), "door" (what the workspace's door did), "expect", "outcome", "sent_today", "text" (all of
    it, as lines)}. Unknown or too old: found False and a line that says so."""
    ref = str(message_ref or "")
    row = _row(app, ref) if REF.match(ref) else None
    n = sent_today(app)
    if row is None:
        text = f"Brain has no record of that message (it keeps them 7 days). It has sent {n} by itself today."
        return {"ref": ref, "found": False, "sent_today": n, "text": text}
    reason = row["why"]
    calm = getattr(app, "calm", None)
    try:
        r = calm.reason(row["why"]) if calm is not None else None
        if r is not None:
            reason = f"{calm.title_of(r.owner)}: {r.what}"
    except Exception:
        pass
    exp = row.get("expect")
    expect = ""
    if exp:
        what = "a reply" if exp["what"] == "reply" else "that you'd act on it"
        expect = f"{what} within {exp['within_h']:g} h"
    oc = (row.get("outcome") or {}).get("result")
    outcome_said = SAID.get(oc or "", "still open" if exp else "")
    door = row.get("door") or "it didn't go through the door (it was exempt, or the door was off)"
    lines = [f"Why: {reason}.", f"The gate: {row['gate']}.", f"The door: {door}."]
    if expect:
        lines.append(f"It expected {expect}: {outcome_said}.")
    lines.append(f"It has sent {n} by itself today.")
    return {"ref": row["ref"], "found": True, "decision": row["id"], "reason": reason, "gate": row["gate"],
            "door": door, "expect": expect, "outcome": oc or "", "sent_today": n, "text": "\n".join(lines)}  # fmt: skip


def why_lines(app: App, message_ref: str) -> list[str]:
    """What Brain adds to Calm's Why? answer (core/calm.py): the gate, the door and the expectation. Empty with Brain
    or `mind.why.on` off, or when it has no record of the message."""
    try:
        if not why_on(app):
            return []
        w = why(app, message_ref)
        if not w.get("found"):
            return []
        out = [f"Brain's gate: {w['gate']}.", f"The door: {w['door']}."]
        if w["expect"]:
            out.append(f"It expected {w['expect']}: {SAID.get(w['outcome'], 'still open')}.")
        link = console_link(app, w.get("decision") or "")
        if link:
            out.append(f"What it weighed, in the Brain console: {link}")
        return out
    except Exception:
        return []


def console_link(app: App, decision_id: str) -> str:
    """(0.9.0, mind.why.console_link) The dashboard address that opens this decision in the Brain console
    (web/static/home.js reads #console?d=<id>); "" when it's off or the id isn't one."""
    if not decision_id or not REF.match(decision_id) or not app.settings.get("mind.why.console_link"):
        return ""
    from kurooto.core.state import jload

    url = (jload(app.paths.state / "web.json", {}) or {}).get("url") or (
        f"http://127.0.0.1:{app.settings.get('web.port') or 8770}/"
    )
    return f"{str(url).split('#')[0]}#console?d={decision_id}"


def message_of(app: App, decision_id: str) -> dict | None:
    """(0.9.0) The message a decision sent, for the Brain console: its Calm record id and Calm's Why? answer."""
    try:
        row = _row(app, decision_id) if REF.match(decision_id or "") else None
        if row is None or row.get("id") != decision_id:
            return None
        calm = getattr(app, "calm", None)
        rec = calm.get(row["ref"]) if calm is not None else None
        why = calm.why_text(rec) if rec else ""
        return {"rid": row["ref"], "why": [ln for ln in why.splitlines() if not ln.startswith("What it weighed")]}
    except Exception:
        return None


def with_why(app: App, msg):
    """The phone app chat's copy of a message it started gets a "Why this?" button (Calm's Why?, which Telegram has
    already). Unchanged when there's no Calm record, the message is an answer to you, or `mind.why.on` is off."""
    try:
        rid = getattr(msg, "rid", None)
        if not rid or not msg.why or msg.why == "asked" or not why_on(app):
            return msg
        data = f"calm:{rid}:why"
        if any(isinstance(b, (list, tuple)) and len(b) > 1 and b[1] == data for row in msg.buttons or [] for b in row):
            return msg
        return replace(msg, buttons=[*(msg.buttons or []), [("Why this?", data)]])
    except Exception:
        return msg

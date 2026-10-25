"""The model of your mind (Brain, 0.8.0 stage 14): what you know, believe, want, prefer and attend to, each row with a
source (said, saw, inferred, imagined), a confidence and the evidence behind it. You can see all of it (`/model`),
mark a
row Wrong (that counts as something you said) or Forget it.

    row  {id, part, subject, claim, source, confidence, evidence: [ids], updated, p?}
    part knowledge | belief | goal | pref | attention

It may only make Kurooto more helpful and quieter, never more persuasive: it adjusts the *level* of an explanation and
the
*timing* of a message (later, quieter), and corrects a false belief about your work or Kurooto's own state once, with
the
evidence (`purpose`: level, timing, correct_fact; anything else is refused by the gate). It never models your inner
life:
a deny-list of topics is checked when a row is written, and what matches is not kept (I-14).
"""

from __future__ import annotations

import hashlib
import re
import time
from typing import TYPE_CHECKING

from kurooto import mind
from kurooto.core.state import jload, jsave
from kurooto.mind.beliefs import SOURCES

if TYPE_CHECKING:
    from kurooto.app import App

FILE = "mind-tom.json"
PARTS = ("knowledge", "belief", "goal", "pref", "attention")
PURPOSES = ("level", "timing", "correct_fact")  # the only things this model may be used for
DENY = re.compile(
    r"\b(health\w*|ill(?:ness)?|sick\w*|medic\w*|doctor|therap\w*|depress\w*|anxi\w*|diagnos\w*|relationship\w*|"
    r"girlfriend|boyfriend|partner|dating|crush|religio\w*|church|prayer|pray\w*|politic\w*|vote[sd]?|voting|election\w*|"
    r"money|salary|rent|debt|loan|bank|income|pay(?:ment|ing)?)\b",
    re.I,
)
ROWS_MAX = 600


def on(app: App) -> bool:
    return mind.part_on(app, "tom")


def _state(app: App) -> dict:
    d = jload(app.paths.state / FILE, {}) or {}
    d.setdefault("rows", [])
    d.setdefault("forgot", [])
    d.setdefault("denied", 0)
    return d


def _save(app: App, d: dict) -> None:
    d["rows"] = d["rows"][-ROWS_MAX:]
    d["forgot"] = d["forgot"][-2000:]
    jsave(app.paths.state / FILE, d)


def norm(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9']+", text.lower()))


def key(part: str, subject: str, claim: str) -> str:
    return hashlib.sha1(f"{part}|{norm(subject)}|{norm(claim)}".encode(), usedforsecurity=False).hexdigest()[:10]  # noqa: S324


def denied(*texts: str) -> bool:
    return any(DENY.search(t or "") for t in texts)


def put(
    app: App,
    part: str,
    subject: str,
    claim: str,
    source: str,
    confidence: float,
    evidence: list | None = None,
    by_subject: bool = False,
    **extra,
) -> dict | None:
    """Keep a row (refresh it if it's there; `by_subject`: one row per subject whatever its claim says now).
    None when it isn't allowed: a topic on the deny-list, something you said
    to forget, or a row you marked Wrong that this would only say again."""
    if not on(app) or part not in PARTS or source not in SOURCES:
        return None
    st = _state(app)
    if denied(subject, claim):
        st["denied"] += 1
        _save(app, st)
        return None
    rid = key(part, subject, "" if by_subject else claim)  # a row whose claim changes over time is keyed by its subject
    if rid in st["forgot"]:
        return None
    row = next((r for r in st["rows"] if r["id"] == rid), None)
    if row and row.get("wrong") and source != "said":
        return None  # you corrected this: only you can bring it back
    conf = max(0.0, min(1.0, float(confidence)))
    if row and by_subject:
        row["claim"] = claim[:200]  # what it says now
    if row is None:
        row = {"id": rid, "part": part, "subject": subject[:80], "claim": claim[:200]}
        st["rows"].append(row)
    row.update(
        source=source,
        confidence=round(conf, 3),
        updated=time.time(),
        evidence=[str(e)[:40] for e in (evidence or [])][:6],
        **extra,
    )
    row.pop("wrong", None) if source == "said" else None
    _save(app, st)
    return row


def rows(app: App, part: str | None = None) -> list[dict]:
    return [r for r in _state(app)["rows"] if part in (None, r["part"])]


def get(app: App, rid: str) -> dict | None:
    return next((r for r in _state(app)["rows"] if r["id"] == rid), None)


def wrong(app: App, rid: str) -> str:
    """You say this row is wrong: it stays (so it isn't inferred again) with confidence 0, and what you said counts as
    `said`."""
    st = _state(app)
    r = next((x for x in st["rows"] if x["id"] == rid), None)
    if r is None:
        return "No such row."
    r.update(wrong=True, confidence=0.0, updated=time.time())
    st["rows"].append(
        {"id": key(r["part"], r["subject"], "not: " + r["claim"]), "part": r["part"], "subject": r["subject"],
         "claim": "not: " + r["claim"], "source": "said", "confidence": 1.0, "updated": time.time(), "evidence": [rid]}
    )  # fmt: skip
    _save(app, st)
    return "Noted: that was wrong. I won't assume it again."


def forget(app: App, rid: str) -> str:
    st = _state(app)
    n = len(st["rows"])
    st["rows"] = [r for r in st["rows"] if r["id"] != rid]
    if len(st["rows"]) == n:
        return "No such row."
    st["forgot"].append(rid)  # so it isn't worked out again
    _save(app, st)
    return "Forgotten."


def forget_span(app: App, lo: float, hi: float) -> int:
    """/forget: the rows made or refreshed in [lo, hi) go, and aren't worked out again."""
    st = _state(app)
    gone = [r for r in st["rows"] if lo <= float(r.get("updated") or 0) < hi]
    if gone:
        st["rows"] = [r for r in st["rows"] if r not in gone]
        st["forgot"].extend(r["id"] for r in gone)
        _save(app, st)
    return len(gone)


def say(row: dict) -> str:
    """The row as it may be said to you (I-13): said and saw as fact, inferred as 'it looks like', imagined as a
    guess."""
    from kurooto.mind import beliefs

    return beliefs.phrase({"text": row["claim"], "source": row["source"], "confidence": row["confidence"]})


def guard(purpose: str) -> str:
    """Every use of this model names its purpose; anything but level, timing or a fact correction is refused."""
    if purpose not in PURPOSES:
        raise ValueError(f"the model of your mind may be used for {', '.join(PURPOSES)}, not {purpose!r}")
    return purpose


def report(app: App, part: str | None = None) -> str:
    if not on(app):
        return "The model of your mind is off (mind.tom.on)."
    parts = [part] if part in PARTS else list(PARTS)
    out = []
    for p in parts:
        rs = sorted(rows(app, p), key=lambda r: -r["updated"])[:12]
        if not rs:
            continue
        title = {"knowledge": "What you seem to know", "belief": "What you seem to believe", "goal": "What you want",
                 "pref": "How you like help", "attention": "What you're on now"}[p]  # fmt: skip
        out.append(title + ":")
        for r in rs:
            tag = "wrong" if r.get("wrong") else f"{r['source']}, {round(r['confidence'] * 100)}%"
            out.append(f"  [{r['id']}] {r['subject']}: {r['claim']} ({tag}; {len(r.get('evidence') or [])} evidence)")
    if not out:
        return "Nothing modelled yet. /model <part>: knowledge, belief, goal, pref, attention."
    return "\n".join(out) + "\n/model wrong <id> says a row is wrong; /model forget <id> drops it."

"""Source-tagged beliefs (Brain, 0.8.0 stage 10): every belief about you or the world keeps where it came from.

    said       you said it
    saw        a sensor or a record showed it
    inferred   computed from other things (a read of you, a concept-graph claim)
    imagined   a Dreaming hypothesis or a forecast

and a confidence from 0 to 1, Brier-scored against what later happened (running sums in the scorekeeper).

The rule (I-13): only `said` and `saw` may be stated to you as fact. `inferred` is phrased "it looks like..." with the
confidence; `imagined` as "a guess: ..." or "maybe...". `lint()` runs in the gate: a sentence that matches a belief is
checked, and rewritten when it states an inferred or imagined belief as fact. Words stay in `<state>/mind-beliefs.json`;
the log gets the source, the confidence and the outcome (numbers).

    add / resolve    keep a belief; settle it when the outcome is known (true or false)
    sync(app)        today's read (inferred) and tomorrow's forecast (imagined) become beliefs
    phrase           the sentence for a belief, worded for its source
    lint             the gate's check of a text's sentences
    brier(app)       {source: (n, mean Brier)} for /beliefs and the indicators
    misses           high-confidence beliefs that turned out wrong (Dreaming's replay set weighs these most)
"""

from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING

from kurooto import mind
from kurooto.core.state import jload, jsave

if TYPE_CHECKING:
    from kurooto.app import App

PART = "beliefs"  # its switch: mind.beliefs.on
FILE = "mind-beliefs.json"
SOURCES = ("said", "saw", "inferred", "imagined")
FACT_SOURCES = ("said", "saw")
KEEP = 400
HEDGES = {
    "inferred": ("it looks like", "looks like", "it seems", "seems", "i think", "probably", "likely"),
    "imagined": ("maybe", "a guess", "might", "perhaps", "could be", "i imagine"),
}
STOP = {
    "the", "a", "an", "is", "are", "was", "were", "you", "your", "it", "its", "to", "of", "and", "in", "on", "for",
    "that", "this", "be", "have", "has", "had", "will", "with", "at", "by", "as", "or", "not", "i", "me", "my",
}  # fmt: skip
SENTENCES = re.compile(r"(?<=[.!?])[ \t]+|\n")


def on(app: App) -> bool:
    return mind.part_on(app, "beliefs")


def _state(app: App) -> dict:
    d = jload(app.paths.state / FILE, {}) or {}
    d.setdefault("rows", [])
    return d


def _save(app: App, d: dict) -> None:
    d["rows"] = d["rows"][-KEEP:]
    jsave(app.paths.state / FILE, d)


def keys(text: str) -> list[str]:
    return sorted({w for w in re.findall(r"[a-z0-9']+", text.lower()) if w not in STOP and len(w) > 2})


def add(app: App, bid: str, text: str, source: str, confidence: float = 1.0, topic: str = "", due: float | None = None):
    """Keep (or refresh) a belief. `said` and `saw` are certain by default; the others carry what they were given."""
    if source not in SOURCES:
        raise ValueError(f"source must be one of {', '.join(SOURCES)}")
    conf = max(0.0, min(1.0, float(confidence)))
    st = _state(app)
    row = next((r for r in st["rows"] if r["id"] == bid), None)
    if row is None:
        row = {"id": bid, "at": time.time(), "outcome": None}
        st["rows"].append(row)
    if row["outcome"] is None:
        row.update(
            text=text[:200], source=source, confidence=round(conf, 3), topic=topic[:40], due=due, keys=keys(text)
        )
    _save(app, st)
    return row


def resolve(app: App, bid: str, outcome: bool) -> bool:
    """Settle a belief: score it (inferred and imagined only; a said or saw one is a record, not a bet)."""
    st = _state(app)
    row = next((r for r in st["rows"] if r["id"] == bid and r["outcome"] is None), None)
    if row is None:
        return False
    row["outcome"] = bool(outcome)
    row["settled"] = time.time()
    _save(app, st)
    if row["source"] in ("inferred", "imagined"):
        mind.connect(app).report(
            "belief_outcome", {"source": row["source"], "confidence": row["confidence"], "outcome": bool(outcome)}
        )
    return True


def phrase(row: dict) -> str:
    """The belief as it may be said to you."""
    t = str(row["text"]).rstrip(". ")
    if row["source"] in FACT_SOURCES:
        return t + "."
    if row["source"] == "inferred":
        return f"It looks like {t[:1].lower() + t[1:]} ({round(row['confidence'] * 100)}% sure)."
    return f"A guess: {t[:1].lower() + t[1:]}."


def _hedged(sentence: str, source: str) -> bool:
    s = sentence.lower()
    return any(h in s for h in HEDGES.get(source, ()))


def match(app: App, sentence: str) -> dict | None:
    """The unsettled belief a sentence states, if any: two or more of its key words, and most of them."""
    ks = set(keys(sentence))
    best, best_share = None, 0.0
    for r in _state(app)["rows"]:
        if r["outcome"] is not None or not r.get("keys"):
            continue
        share = len(ks & set(r["keys"])) / len(r["keys"])
        if len(ks & set(r["keys"])) >= 2 and share >= 0.7 and share > best_share:
            best, best_share = r, share
    return best


def lint(app: App, text: str) -> tuple[str, list[str]]:
    """I-13 in the gate: a sentence that states an inferred or imagined belief as fact is reworded as what it is."""
    if not on(app):
        return text, []
    out, fixed = [], []
    for s in SENTENCES.split(text):
        row = match(app, s) if s.strip() else None
        if row and row["source"] not in FACT_SOURCES and not _hedged(s, row["source"]):
            fixed.append(row["source"])
            out.append(phrase(row))
        else:
            out.append(s)
    return (" ".join(out) if fixed else text), fixed


def sync(app: App) -> int:
    """Today's read becomes an inferred belief and tomorrow's forecast an imagined one (their words stay local)."""
    if not on(app):
        return 0
    from kurooto.mind import mood

    c, n, d = mind.connect(app), 0, mood.today()
    row = next(iter(c.mood_rows(f"read:{d.isoformat()}")), None)
    m = (row or {}).get("meta") or {}
    if row and m.get("counted") and m.get("label"):
        add(
            app,
            f"read:{d.isoformat()}",
            f"you are {m['label']} today",
            "inferred",
            float(m.get("confidence") or 0.5),
            "read",
        )
        n += 1
    return n


def brier(app: App) -> dict[str, tuple[int, float]]:
    out = {}
    for r in mind.connect(app).mood_rows("brier:"):
        n = int((r.get("meta") or {}).get("n") or 0)
        if n:
            out[r["key"].split(":", 1)[1]] = (n, float(r["value"]) / n)
    return out


def misses(app: App, floor: float = 0.8) -> list[dict]:
    """Beliefs held with `floor` confidence or more that were wrong: the replay set weighs these most."""
    return [
        {"id": r["id"], "source": r["source"], "confidence": r["confidence"]}
        for r in _state(app)["rows"]
        if r["outcome"] is False and r["confidence"] >= floor
    ]


def report(app: App, topic: str = "") -> str:
    """What /beliefs says: each belief with its source and confidence, newest first, and how each source has fared."""
    if not on(app):
        return "Beliefs are off (mind.beliefs.on)."
    t = topic.strip().lower()
    rows = [r for r in reversed(_state(app)["rows"]) if not t or t in r["text"].lower() or t in r.get("topic", "")]
    out = []
    for r in rows[:12]:
        state = "" if r["outcome"] is None else (" - turned out true" if r["outcome"] else " - turned out false")
        out.append(f"[{r['source']}, {round(r['confidence'] * 100)}%] {r['text']}{state}")
    if not out:
        out = ["No beliefs kept" + (f" about '{topic.strip()}'" if t else "") + " yet."]
    b = brier(app)
    if b:
        out.append(
            "Brier score so far (lower is better, 0.25 is a coin flip): "
            + "; ".join(f"{s} {v:.2f} over {n}" for s, (n, v) in b.items())
        )
    return "\n".join(out)

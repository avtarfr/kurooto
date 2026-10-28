"""His mastery frontier, as a number (Brain, 0.8.14): how close a piece of text is to what he's ready to learn next.

From the model of what he knows (mind/tom/knowledge.py, Bayesian knowledge tracing per concept note), each concept gets
a grade:

    frontier   1.0   not mastered yet, and every prerequisite it has is (or, with none, he has started on it)
    near       0.5   a concept next to one on the frontier (it links to one, or one links to it)
    started    0.4   partly known, but a prerequisite isn't solid yet
    solid      0.1   mastered: little left to learn there
    unknown    0.0   nothing seen of it yet and its prerequisites aren't solid: too far ahead

    score(app, text)          the best grade among the concepts the text names (0 when it names none, or the model is
                              off): an add-on can weigh what's on screen by it
    on_frontier(slug, ...)    the rule above, for Dreaming's cards (mind/dream.py)
    grades(app)               every concept's grade, worked out at most every CACHE_S seconds

A file read and plain arithmetic: no model, nothing leaves this computer. The grades are kept in memory only.

"Learning now" (0.9.0): another feature (an add-on) may mark concepts you keep coming back to this week
(mark_learning: concept slugs and a number of days, at most LEARNING_MAX_DAYS); learning_now(app) lists the marks still
running, for Quiz's one extra card and the revision plan's top line. Kept in <state>/mind-learning.json: slugs and
dates only. Off with the model of what he knows (mind.tom.on).
"""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING

from kurooto.mind.tom import knowledge, model

if TYPE_CHECKING:
    from kurooto.app import App
    from kurooto.core.conceptgraph import Note

PART = "tom"  # a reading of the model of what he knows: off with it (mind.tom.on)
CACHE_S = 600  # the notes and the masteries change slowly; an add-on may ask many times a minute
TEXT_MAX = 20000
FRONTIER, NEAR, STARTED, SOLID, UNKNOWN = 1.0, 0.5, 0.4, 0.1, 0.0

_cache: dict[int, tuple[float, dict[str, Note], dict[str, float]]] = {}
_lock = threading.Lock()


def masteries(app: App) -> dict[str, float]:
    """Each concept's p(learned), only for concepts there is evidence about (one read of the model's file)."""
    return {r["subject"]: float(r["p"]) for r in model.rows(app, knowledge.PART) if "p" in r}


def prereqs(note: Note, notes: dict[str, Note]) -> list[str]:
    """Its typed prerequisites, or else the notes it links to (as knowledge.frontier reads them)."""
    pre = [t for t, rel in note.typed.items() if "prereq" in rel.lower()] or sorted(note.links)
    return [p for p in pre if p in notes and p != note.slug]


def on_frontier(slug: str, notes: dict[str, Note], ps: dict[str, float]) -> bool:
    """Not mastered, and ready for it: its prerequisites are all solid. One with no prerequisites in the notes counts
    only once there's evidence he has started on it (so a folder of untouched notes isn't all "frontier")."""
    if slug not in notes:
        return False
    p = ps.get(slug)
    if (p if p is not None else knowledge.P_INIT) >= knowledge.SOLID_FROM:
        return False
    pre = prereqs(notes[slug], notes)
    if not pre:
        return p is not None
    return all(ps.get(x, knowledge.P_INIT) >= knowledge.SOLID_FROM for x in pre)


def grade_all(notes: dict[str, Note], ps: dict[str, float]) -> dict[str, float]:
    front = {s for s in notes if on_frontier(s, notes, ps)}
    out: dict[str, float] = {}
    for slug, n in notes.items():
        p = ps.get(slug)
        if slug in front:
            out[slug] = FRONTIER
        elif p is not None and p >= knowledge.SOLID_FROM:
            out[slug] = SOLID
        elif (n.links & front) or any(slug in notes[f].links for f in front):
            out[slug] = NEAR
        elif p is not None:
            out[slug] = STARTED
        else:
            out[slug] = UNKNOWN
    return out


def _load(app: App) -> tuple[dict[str, Note], dict[str, float]]:
    """(the concept notes, their grades), from the cache when it's fresh."""
    t = time.monotonic()
    with _lock:
        hit = _cache.get(id(app))
        if hit is not None and t - hit[0] < CACHE_S:
            return hit[1], hit[2]
    notes = knowledge.concepts(app)
    grades = grade_all(notes, masteries(app))
    with _lock:
        _cache[id(app)] = (t, notes, grades)
    return notes, grades


def forget_cache(app: App | None = None) -> None:
    with _lock:
        if app is None:
            _cache.clear()
        else:
            _cache.pop(id(app), None)


def grades(app: App) -> dict[str, float]:
    return dict(_load(app)[1]) if model.on(app) else {}


def score(app: App, text: str) -> float:
    """How close this text is to his mastery frontier, 0 to 1: the best grade among the concepts it names. 0 when it
    names none, or Brain's model of what he knows (mind.tom.on) is off. Never raises."""
    try:
        if not text or not model.on(app):
            return 0.0
        notes, g = _load(app)
        hits = knowledge.mentions(str(text)[:TEXT_MAX], notes)
        return max((g.get(s, UNKNOWN) for s in hits), default=0.0)
    except Exception:
        return 0.0


LEARNING_FILE = "mind-learning.json"
LEARNING_MAX_DAYS = 14  # a "learning now" mark lasts at most this long unless marked again
LEARNING_MAX = 20  # concepts marked at once, at most (the latest kept)


def mark_learning(app: App, slugs: list[str], days: float = 7) -> int:
    """(0.9.0) Concepts he's learning now, from another feature (concept slugs as the notes name them, and how many
    days the mark lasts). Unknown slugs are left out. How many were marked; 0 with the model off. Never raises."""
    try:
        if not model.on(app) or not slugs:
            return 0
        from kurooto.core.lock import Lock
        from kurooto.core.state import jload, jsave

        notes = _load(app)[0]
        until = time.time() + max(0.0, min(float(days), LEARNING_MAX_DAYS)) * 86400
        got = [s for s in dict.fromkeys(str(x) for x in slugs) if s in notes]
        if not got:
            return 0
        with Lock(app.paths.state, "mind-learning"):
            d = jload(app.paths.state / LEARNING_FILE, {}) or {}
            d = {k: v for k, v in d.items() if isinstance(v, (int, float)) and v > time.time()}
            for s in got:
                d.pop(s, None)
                d[s] = round(until, 1)
            jsave(app.paths.state / LEARNING_FILE, dict(list(d.items())[-LEARNING_MAX:]))
        return len(got)
    except Exception:
        return 0


def learning_now(app: App) -> list[str]:
    """(0.9.0) The concepts marked "learning now" whose mark still runs, the latest first; [] with the model off."""
    try:
        if not model.on(app):
            return []
        from kurooto.core.state import jload

        d = jload(app.paths.state / LEARNING_FILE, {}) or {}
        t = time.time()
        return [k for k, v in reversed(list(d.items())) if isinstance(v, (int, float)) and v > t]
    except Exception:
        return []


__all__ = ["score", "on_frontier", "grades", "masteries", "prereqs", "forget_cache", "mark_learning", "learning_now"]

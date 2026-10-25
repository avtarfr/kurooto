"""Forgetting well (Brain, 0.8.0 stage 16): old things fade from use without the record being lost, and what you ask to
be forgotten is
gone everywhere (I-11).

Fading, for retrieval only (the mind log and the ledger keep everything unless you forget it):
  - each remembered row has a **salience** 0.5^(age / half-life), the half-life by kind (facts about you 90 days,
  gists 30, project
    facts 180; `mind.forget.half_lives`), boosted every time it is used in an AI request and confirmed; the context
    assembler ranks
    rows by relevance x salience, and `/memory` shows a bar and "fading".
  - **old misses stop coming up**: a past miss (a broken deadline, a wrong turn, a bad week) isn't cited in context or
  in a message
    after `mind.forget.misses_weeks` (6). Its own mistakes stay in its journal (that's honesty); it just doesn't
    repeat them to you.

`/forget` goes through everything (`forget_span`, called by core/retention.py as the kind "mind"): the day's read and
numbers (the
mood store), the model of your mind (mind/tom), the senses' readings and totals, the provenance of skills made from
it, the journal
(a tombstone: a hash and "something you asked me to forget"), the life story's lines about you, and the fine-tune's
examples (a
tombstone the next adapter is probed against). The mind log gets only that a forget happened (a hash), never what.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import re
import time
from typing import TYPE_CHECKING

from kurooto import mind
from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave

if TYPE_CHECKING:
    from kurooto.app import App

PART = "forget"  # its switch: mind.forget.on
FILE = "mind-forget.json"
DAY = 86400.0
BOOST_CAP = 5
MISS = re.compile(
    r"\b(missed|failed|forgot|forgotten|skipped|late|overdue|didn'?t (?:do|finish|hand in|submit|turn up)|"
    r"never (?:did|finished)|"
    r"fell behind|bad week|wrong turn)\b",
    re.I,
)
AGO = re.compile(r"\b(\d+)\s*(week|month|year)s?\s+ago\b|\blast\s+(term|semester|month|year)\b", re.I)
TOMBSTONE = "Something you asked me to forget."

register_defaults(
    "mind",
    {
        "forget": {
            "on": True,  # old things fade from use, old misses stop coming up, and a forget goes everywhere
            "misses_weeks": 6,  # a past miss isn't brought up after this many weeks
            "half_lives": {"fact": 90, "gist": 30, "project": 180, "default": 60},  # days, by kind of memory
        }
    },
)


def on(app: App) -> bool:
    return mind.part_on(app, "forget")


def _state(app: App) -> dict:
    d = jload(app.paths.state / FILE, {}) or {}
    d.setdefault("uses", {})
    d.setdefault("forgets", 0)
    return d


def half_life(app: App, row: dict) -> float:
    hl = app.settings.get("mind.forget.half_lives") or {}
    kind = "project" if str(row.get("sub") or "") == "project" else str(row.get("kind") or "")
    v = hl.get(kind, hl.get("default", 60))
    return float(v) if isinstance(v, (int, float)) and v > 0 else 60.0


def row_key(row: dict) -> str:
    return str(
        row.get("id")
        if row.get("id") is not None
        else hashlib.sha1(str(row.get("text", "")).encode(), usedforsecurity=False).hexdigest()[:10]
    )  # noqa: S324


def salience(app: App, row: dict, now: float | None = None) -> float:
    """0.5^(age / half-life) from the row's creation, or from its last confirmed use, times a small boost per use (at
    most x1.5)."""
    now = now or time.time()
    u = _state(app)["uses"].get(row_key(row)) or {}
    anchor = max(float(row.get("at") or now), float(u.get("last") or 0))
    age = max(0.0, (now - anchor) / DAY)
    boost = 1.0 + 0.1 * min(int(u.get("n") or 0), BOOST_CAP)
    return round(min(1.0, 0.5 ** (age / half_life(app, row)) * boost), 4)


def factor(app: App, row: dict) -> float:
    """What retrieval multiplies a row's relevance by: its salience when forgetting is on, else 1."""
    return max(0.05, salience(app, row)) if on(app) else 1.0


def used(app: App, rows: list[dict], now: float | None = None) -> None:
    """These rows went into an AI request and it went through: each is a confirmed use."""
    if not on(app) or not rows:
        return
    st, now = _state(app), now or time.time()
    for r in rows:
        u = st["uses"].setdefault(row_key(r), {"n": 0, "last": 0.0})
        u["n"] += 1
        u["last"] = now
    for k in list(st["uses"])[:-3000]:
        st["uses"].pop(k, None)
    jsave(app.paths.state / FILE, st)


def bar(s: float) -> str:
    n = 3 if s >= 0.66 else 2 if s >= 0.33 else 1 if s >= 0.12 else 0
    return "▮" * n + "▯" * (3 - n)


def label(app: App, row: dict) -> str:
    """For /memory: a bar, and 'fading' when it has lost most of its weight."""
    if not on(app):
        return ""
    s = salience(app, row)
    return f" [{bar(s)}{' fading' if s < 0.25 else ''}]"


# ---------------------------------------------------------------------------------------------- old misses
def is_old_miss(app: App, text: str, at: float, now: float | None = None) -> bool:
    """A line about a miss that is older than `misses_weeks`: not cited any more."""
    if not on(app) or not MISS.search(text or ""):
        return False
    weeks = app.settings.get("mind.forget.misses_weeks")
    weeks = float(weeks) if isinstance(weeks, (int, float)) and weeks >= 0 else 6.0
    return ((now or time.time()) - float(at)) > weeks * 7 * DAY


def old_reference(app: App, sentence: str) -> bool:
    """A sentence that brings up a miss from further back than `misses_weeks` ('you missed it 8 weeks ago', 'last
    term')."""
    if not on(app) or not MISS.search(sentence):
        return False
    weeks = app.settings.get("mind.forget.misses_weeks")
    weeks = float(weeks) if isinstance(weeks, (int, float)) and weeks >= 0 else 6.0
    for m in AGO.finditer(sentence):
        if m[1]:
            n = int(m[1]) * {"week": 1, "month": 4.3, "year": 52}[m[2].lower()]
        else:
            n = {"term": 14, "semester": 16, "month": 4.3, "year": 52}[m[3].lower()]
        if n > weeks:
            return True
    return False


# --------------------------------------------------------------------------------------------- the cascade
def tombstone(what: str) -> str:
    return hashlib.sha256(what.encode()).hexdigest()[:12]


def _days(lo: float, hi: float, limit: int = 400):
    start = dt.date.fromtimestamp(max(lo, time.time() - limit * DAY))
    end = dt.date.fromtimestamp(min(hi, time.time()))
    d = start
    while d <= end:
        yield d
        d += dt.timedelta(days=1)


def _mood_day(app: App, mood, d: dt.date) -> bool:
    """Forget one day of the read's store, if there is anything of it."""
    c = mind.connect(app)
    day = d.isoformat()
    if not (c.signal_days().get(day) or any(c.mood_rows(f"{p}{day}") for p in ("read:", "forecast:", "answer:"))):
        return False
    mood.forget_day(app, day)
    return True


def forget_journal(app: App, lo: float, hi: float) -> int:
    """Journal days in the span are replaced by a tombstone: a hash and 'something you asked me to forget'."""
    from kurooto.mind import journal

    n = 0
    for d in _days(lo, hi):
        f = journal.folder(app) / f"{d.isoformat()}.json"
        if f.exists():
            jsave(f, {"day": d.isoformat(), "lines": [], "tombstone": tombstone(d.isoformat()), "note": TOMBSTONE})
            f.with_suffix(".md").write_text(TOMBSTONE + "\n", encoding="utf-8")
            n += 1
    return n


def forget_span(app: App, lo: float, hi: float) -> int:
    """Everything the mind kept from [lo, hi), in every store; one failing never stops the rest. How many went."""
    if not on(app):
        return 0
    from kurooto.mind import mood, story
    from kurooto.mind.senses import store
    from kurooto.mind.skills import finetune, library
    from kurooto.mind.tom import model

    n = 0
    steps = [
        (
            "mood",
            lambda: sum(1 for d in _days(lo, hi, 31) if _mood_day(app, mood, d)),
        ),
        ("story", lambda: sum(story.forget_day(app, d.isoformat()) for d in _days(lo, hi, 31))),
        ("tom", lambda: model.forget_span(app, lo, hi)),
        ("senses", lambda: store.forget_range(app, lo, hi)),
        ("skills", lambda: library.redact(app, lo, hi)),
        ("journal", lambda: forget_journal(app, lo, hi)),
        ("finetune", lambda: finetune.forget_span(app, lo, hi)),
    ]
    for name, fn in steps:
        try:
            n += int(fn() or 0)
        except Exception as e:
            app.events.emit("forget_step_failed", what=name, error=type(e).__name__)
    st = _state(app)
    st["forgets"] += 1
    st["uses"] = {
        k: v for k, v in st["uses"].items() if lo > float(v.get("last") or 0) or float(v.get("last") or 0) >= hi
    }
    jsave(app.paths.state / FILE, st)
    mind.connect(app).report(
        "forget_event", {"hash": tombstone(f"{lo}-{hi}-{st['forgets']}"), "n": n}
    )  # that it happened; never what
    return n

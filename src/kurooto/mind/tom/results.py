"""Exam results you report (Brain, 0.9.0, mind.tom.from_chat): "I got 12/30 on the LA midterm" becomes evidence.

    parse(text)              (score as a fraction, what it was: "midterm"), or None for anything else
    take(app, slug, f, what) the evidence, the line in exam-prep, and an offer for more preparation time

What a result does, each part only adding:
- Brain's model of what you know (mind/tom/knowledge.py): each concept note among the course's revision topics gets a
  weighted observation (WEIGHT), right at RIGHT_FROM or above, wrong below; evidence "exam:<date>".
- The course's exam prep note, when it has one: a dated line in Kurooto's own block (`<!-- kurooto:exam-results -->`,
  core/graphwrite.py), never in your text. The lines aren't list items, so the revision plan doesn't read them as
  topics; a low score is marked as a gap there.
- Below RIGHT_FROM with an exam of that course still ahead: an offer, with a button, to plan more hours for its exams
  (Start-by's startby.exam_by_subject, up by a quarter). Nothing changes without the tap.

Grades are academic, not health or money, so they may be kept. Nothing leaves this computer.
"""

from __future__ import annotations

import datetime as dt
import math
import re
from typing import TYPE_CHECKING

from kurooto.core import graphwrite, layout
from kurooto.core.clock import now
from kurooto.core.tools import write_note_file

if TYPE_CHECKING:
    from kurooto.app import App

RIGHT_FROM = 0.6  # a score at or above this counts as a right answer for the course's concepts
WEIGHT = 0.3  # one exam says less about each concept than a quiz card on it
MAX_CONCEPTS = 20
BLOCK = "exam-results"
WHAT = r"(?:mid[- ]?terms?|mid[- ]?sems?|end[- ]?sems?|finals?|exams?|quiz(?:zes)?|tests?|papers?|assignments?)"
SCORE = re.compile(
    r"^\s*(?:i\s+)?(?:got|scored|received|have|had|made)\s+(?:a\s+|an\s+)?"
    r"(?:(?P<a>\d+(?:\.\d+)?)\s*(?:/|out of)\s*(?P<b>\d+(?:\.\d+)?)|(?P<p>\d+(?:\.\d+)?)\s*(?:%|percent))"
    rf"\s+(?:in|on|for)\s+(?:the\s+|my\s+|our\s+)?(?P<rest>.*?\b{WHAT}\b.*?)\s*[.!]?\s*$",
    re.I,
)


def parse(text: str) -> tuple[float, str, str] | None:
    """(the score, 0 to 1; the kind of exam, as said; the words naming it) or None."""
    m = SCORE.match(text or "")
    if not m:
        return None
    if m["p"] is not None:
        f = float(m["p"]) / 100
    else:
        b = float(m["b"])
        if b <= 0:
            return None
        f = float(m["a"]) / b
    if not 0 <= f <= 1:
        return None
    kind = re.search(WHAT, m["rest"], re.I)
    return round(f, 3), (kind[0].lower() if kind else "exam"), m["rest"].strip()


def concepts(app: App, slug: str) -> list[str]:
    """The course's revision topics whose note is a concept note (modules/revision.py, mind/tom/knowledge.py)."""
    from kurooto.mind.tom import knowledge

    es = app.modules.get("exam_season")
    if es is None:
        return []
    notes = knowledge.concepts(app)
    out = []
    for t in es.revision.topics(slug)[0]:
        rel = es.revision._rel(t["note"]) if t["note"] else ""  # noqa: SLF001
        if rel in notes and rel not in out:
            out.append(rel)
    return out[:MAX_CONCEPTS]


def note_line(app: App, slug: str, f: float, what: str, day: dt.date) -> bool:
    """The result as a line in Kurooto's own block of the course's exam prep note (only when the note exists)."""
    p = layout.path(app, "exam_prep", subject=slug)
    try:
        text = p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    pat = re.compile(rf"<!-- kurooto:{BLOCK}\b[^>]*-->(.*?)<!-- /kurooto:{BLOCK} -->", re.S)
    m = pat.search(text)
    old = [x for x in (m[1].strip().splitlines() if m else []) if x.strip() and not x.startswith("Results you")]
    gap = " A gap to revise." if f < RIGHT_FROM else ""
    line = f"{day.isoformat()}: {what}, {round(f * 100)}%.{gap}"
    if line in old:
        return False
    body = "\n".join(["Results you reported (Kurooto keeps this block):", *old, line][-12:])
    write_note_file(p, graphwrite.put_block(text, BLOCK, body))
    return True


def take(app: App, slug: str, f: float, what: str) -> tuple[str, str, list]:
    """Everything a reported result adds. Returns (what to tell you, an offer or "", the offer's buttons)."""
    from kurooto.mind.tom import knowledge, model

    day = now().date()
    sub = app.modules.get("subjects")
    name = sub.name_of(slug) if sub is not None else slug
    said = [f"Noted: {name} {what}, {round(f * 100)}%."]
    n = 0
    if model.on(app):
        for c in concepts(app, slug):
            if knowledge.observe(app, c, f >= RIGHT_FROM, WEIGHT, f"exam:{day.isoformat()}") is not None:
                n += 1
        if n:
            many = "s" if n != 1 else ""
            said.append(f"It counts as evidence for {n} of its concept{many} in what I think you know.")
    if note_line(app, slug, f, what, day):
        said.append(f"Added to {layout.shown(app, layout.path(app, 'exam_prep', subject=slug))}.")
    buttons: list = []
    offer = ""
    sb = app.modules.get("startby")
    if f < RIGHT_FROM and sb is not None and app.is_on("startby") and _exam_ahead(app, slug):
        h = float((sb.setting("exam_by_subject") or {}).get(slug) or (sb.setting("sizes") or {}).get("exam") or 10)
        more = float(math.ceil(h * 1.25))
        offer = f"Plan {more:g} hours for {name}'s next exams instead of {h:g}?"
        buttons = [[(f"Yes, {more:g} hours", f"mres:{slug}:{more:g}"), ("No", f"mres:{slug}:no")]]
    app.events.emit("exam_result_taken", concepts=n, low=f < RIGHT_FROM)
    return " ".join(said), offer, buttons


def _exam_ahead(app: App, slug: str) -> bool:
    dl = app.modules.get("deadlines")
    if dl is None or not app.is_on("deadlines"):
        return False
    t = now()
    for it in dl.items().values():
        if it.get("status") == "open" and it.get("kind") == "exam" and it.get("subject") == slug:
            due = it.get("due")
            try:
                when = dt.datetime.fromisoformat(due) if isinstance(due, str) else None
            except ValueError:
                when = None
            if when is None or when > t:
                return True
    return False


def button(app: App, ref: str, act: str) -> str:
    """Yes: Start-by's hours for the course's exams (startby.set_exam); No: nothing changes."""
    if act == "no":
        return "Left as it was."
    sb = app.modules.get("startby")
    if sb is None or not app.is_on("startby"):
        return "Start-by dates are off."
    try:
        h = float(act)
    except ValueError:
        return "That button is from an older message."
    return sb.set_exam(ref, h)[:190]

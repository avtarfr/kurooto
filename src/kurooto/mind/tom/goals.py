"""What you want (stage 14, part 3): your stated goals and the intentions it infers from what you do.

Stated (source said): your deadlines (an exam, an assignment), the projects you added, goals you tell it. Inferred
(source
inferred, never stated as fact: I-13): "probably working on glacier-flow" from the activity stream. They feed the
workspace's
standing goals (a goal grows more pressing as its deadline closes in) and, from stage 15, week plans.
"""

from __future__ import annotations

import datetime as dt
import re
import time
from typing import TYPE_CHECKING

from kurooto.mind.tom import model

if TYPE_CHECKING:
    from kurooto.app import App

PART = "goal"
WEEKLY = 7 * 86400


def stated(app: App, text: str, due: str = "", evidence: str = "told") -> dict | None:
    return model.put(app, PART, f"goal:{model.norm(text)[:40]}", text, "said", 1.0, [evidence], due=due)


GOAL = re.compile(
    r"(?i)^(?:my goal is to|i want to|i(?:'m| am) aiming to|i(?:'m| am) trying to|i plan to)\s+"
    r"(?P<what>.{6,140}?)(?:\s+by\s+(?P<due>[\w: -]{2,24}))?[.!]?$"
)


def heard(app: App, sentence: str) -> dict | None:
    """(0.9.0, mind.tom.from_chat) A goal you state in a message ("I want to finish the draft by Friday") becomes a
    stated goal (source said, evidence chat). None for anything else."""
    m = GOAL.match(sentence.strip())
    if not m:
        return None
    due = ""
    if m["due"]:
        from kurooto.core.clock import parse_when

        try:
            due = parse_when(m["due"]).isoformat(timespec="minutes")
        except ValueError:
            due = ""
    what = m["what"].strip() + (f" by {m['due'].strip()}" if m["due"] and not due else "")
    return stated(app, what, due, "chat")


def sync_deadlines(app: App) -> int:
    """Open exams and assignments are goals he has (from the deadlines he keeps); each is a standing goal in the
    workspace."""
    from kurooto.mind import workspace

    dl = app.modules.get("deadlines")
    if dl is None or not app.is_on("deadlines"):
        return 0
    n = 0
    for iid, it, hours in dl.upcoming(24 * 21):
        row = stated(app, f"{it.get('title', '')}", it.get("due", ""), f"deadline:{iid}")
        if row is None:
            continue
        slip = max(0.0, min(1.0, 1.0 - hours / (24 * 21)))
        workspace.set_standing(app, f"d-{iid}", str(it.get("title", ""))[:80], slip)
        n += 1
    return n


def infer_intentions(app: App) -> list[dict]:
    """From the day's activity totals: the project he has spent the most time on, hedged (never stated as fact)."""
    from kurooto.mind.senses import store

    t = store.totals(app, "activity", dt.date.today().isoformat())
    proj = sorted(((v, k.split(":", 1)[1]) for k, v in t.items() if k.startswith("project:")), reverse=True)
    out = []
    for mins, slug in proj[:2]:
        if mins >= 30:
            conf = min(0.85, 0.4 + mins / 400)
            r = model.put(
                app,
                PART,
                f"intent:{slug}",
                f"is working on {slug}",
                "inferred",
                conf,
                [f"activity:{dt.date.today()}"],
                by_subject=True,
                at=time.time(),
            )
            if r:
                out.append(r)
    return out


PAST = "history:deadlines"  # the evidence id of rows learned only from the imported past
LABELS = {"exam": "exams", "task": "assignments", "quiz": "quizzes"}


def _lead(h: float) -> str:
    v, unit = (abs(h) / 24, "days") if abs(h) >= 36 else (abs(h), "hours")
    return f"about {v:.0f} {unit} {'before' if h >= 0 else 'after'} they're due"


def from_past(app: App, min_done: int = 3) -> int:
    """How past deadlines went (mind.backfill's history, no titles): for each kind with enough done, one hedged row,
    "usually marks assignments done about 2 days before they're due (from 9)". A prior for timing, inferred, never a
    goal stated for you. How many rows were kept."""
    from kurooto.mind import history

    n = 0
    for kind, p in history.deadline_pattern(app).items():
        if kind not in LABELS or p["done"] < min_done or p["lead_h"] is None:
            continue
        conf = min(0.7, 0.3 + p["done"] / 40)
        claim = f"usually marks {LABELS[kind]} done {_lead(p['lead_h'])} (from {p['done']} past ones)"
        if model.put(app, PART, f"past {LABELS[kind]}", claim, "inferred", conf, [PAST], by_subject=True):
            n += 1
    return n


def forget_past(app: App) -> int:
    """`/mind backfill forget`: the rows learned only from the imported past go (and may be learned again after a new
    import: they aren't marked forgotten)."""
    st = model._state(app)
    keep = [r for r in st["rows"] if PAST not in (r.get("evidence") or [])]
    gone = len(st["rows"]) - len(keep)
    if gone:
        st["rows"] = keep
        model._save(app, st)
    return gone

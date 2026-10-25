"""What you want (stage 14, part 3): your stated goals and the intentions it infers from what you do.

Stated (source said): your deadlines (an exam, an assignment), the projects you added, goals you tell it. Inferred
(source
inferred, never stated as fact: I-13): "probably working on glacier-flow" from the activity stream. They feed the
workspace's
standing goals (a goal grows more pressing as its deadline closes in) and, from stage 15, week plans.
"""

from __future__ import annotations

import datetime as dt
import time
from typing import TYPE_CHECKING

from kurooto.mind.tom import model

if TYPE_CHECKING:
    from kurooto.app import App

PART = "goal"
WEEKLY = 7 * 86400


def stated(app: App, text: str, due: str = "", evidence: str = "told") -> dict | None:
    return model.put(app, PART, f"goal:{model.norm(text)[:40]}", text, "said", 1.0, [evidence], due=due)


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

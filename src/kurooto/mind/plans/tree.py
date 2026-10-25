"""Goal trees (Brain, 0.8.0 stage 15): each deadline, repository milestone and stated goal as a node with an effort
estimate.

    Node {id, title, kind (milestone | task), due, effort_h, depends_on, done_frac, source, guessed}

Sources: your deadlines (effort from Start-by's sizes, which come from what similar items took, or what you told it
once),
the milestones of a repository project, and the goals you stated (stage 14). You can change an estimate (`/plan effort
<id>
<hours>`); that one is yours and no longer a guess. A node with `done_frac` 1 is finished and drops out.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave

if TYPE_CHECKING:
    from kurooto.app import App

FILE = "mind-plans.json"
MIN_EFFORT_H = 0.25

register_defaults(
    "mind",
    {
        "plans": {
            "on": True,  # week-scale plans: milestone risks from simulated futures; a suggestion, never a push
            "weeks": 6,  # how far ahead the rollouts look
            "rollouts": 1000,  # how many simulated futures
        }
    },
)


@dataclass
class Node:
    id: str
    title: str
    kind: str  # "milestone" (an exam, a milestone) or "task"
    due: dt.datetime
    effort_h: float
    depends_on: list[str] = field(default_factory=list)
    done_frac: float = 0.0
    source: str = "deadline"
    guessed: bool = True

    @property
    def left_h(self) -> float:
        return max(0.0, self.effort_h * (1.0 - min(1.0, self.done_frac)))


def _state(app: App) -> dict:
    d = jload(app.paths.state / FILE, {}) or {}
    d.setdefault("efforts", {})
    d.setdefault("predictions", [])
    d.setdefault("last_sent", 0.0)
    return d


def set_effort(app: App, nid: str, hours: float) -> bool:
    if not re.fullmatch(r"[\w:.-]{1,60}", nid) or not (MIN_EFFORT_H <= hours <= 400):
        return False
    st = _state(app)
    st["efforts"][nid] = round(float(hours), 2)
    jsave(app.paths.state / FILE, st)
    return True


def from_deadlines(app: App, horizon_h: float) -> list[Node]:
    dl, sb = app.modules.get("deadlines"), app.modules.get("startby")
    if dl is None or not app.is_on("deadlines"):
        return []
    mine = _state(app)["efforts"]
    out = []
    for iid, it, _hours in dl.upcoming(horizon_h):
        if it.get("status") in ("done", "ignored"):
            continue
        try:
            due = dt.datetime.fromisoformat(it["due"])
        except (KeyError, ValueError):
            continue
        guessed = True
        if sb is not None and app.is_on("startby"):
            try:
                h, _kind, guessed = sb.size_of(iid, {**it, "parts": 0, "parts_done": 0})
            except Exception:
                h = 2.0
        else:
            h = 2.0
        nid = f"d:{iid}"
        if nid in mine:
            h, guessed = float(mine[nid]), False
        parts, done = int(it.get("parts") or 0), int(it.get("parts_done") or 0)
        frac = done / parts if parts else 0.0
        out.append(
            Node(
                nid,
                str(it.get("title", ""))[:80],
                "milestone" if it.get("kind") == "exam" else "task",
                due,
                max(MIN_EFFORT_H, h),
                [],
                frac,
                "deadline",
                guessed,
            )
        )
    return out


def from_repos(app: App) -> list[Node]:
    """Milestones kept on repository projects: {title, due (ISO date), effort_h?}; none are made up."""
    out = []
    try:
        from kurooto.core import repoproject

        mine = _state(app)["efforts"]
        for rec in repoproject.records(app).values():
            for i, m in enumerate(rec.get("milestones") or []):
                try:
                    due = dt.datetime.fromisoformat(str(m["due"]))
                except (KeyError, ValueError):
                    continue
                nid = f"r:{rec.get('key', '')[:30]}:{i}"
                h = float(mine.get(nid) or m.get("effort_h") or 6.0)
                out.append(
                    Node(
                        nid,
                        str(m.get("title", ""))[:80],
                        "milestone",
                        due,
                        h,
                        [],
                        float(m.get("done_frac") or 0),
                        "repo",
                        nid not in mine and not m.get("effort_h"),
                    )
                )
    except Exception:  # noqa: S110
        pass
    return out


def from_goals(app: App) -> list[Node]:
    """Goals he stated with a date (mind/tom/goals.py), that aren't already a deadline."""
    out = []
    try:
        from kurooto.mind.tom import model

        have = {n.title.lower() for n in from_deadlines(app, 24 * 60)}
        mine = _state(app)["efforts"]
        for r in model.rows(app, "goal"):
            if r["source"] != "said" or not r.get("due") or r["claim"].lower() in have:
                continue
            try:
                due = dt.datetime.fromisoformat(str(r["due"]))
            except ValueError:
                continue
            nid = f"g:{r['id']}"
            out.append(
                Node(nid, r["claim"][:80], "task", due, float(mine.get(nid) or 4.0), [], 0.0, "goal", nid not in mine)
            )
    except Exception:  # noqa: S110
        pass
    return out


def build(app: App, weeks: int | None = None) -> list[Node]:
    w = int(weeks or app.settings.get("mind.plans.weeks") or 6)
    nodes = from_deadlines(app, w * 7 * 24) + from_repos(app) + from_goals(app)
    now = dt.datetime.now()
    return sorted((n for n in nodes if n.done_frac < 1 and n.due > now - dt.timedelta(days=1)), key=lambda n: n.due)

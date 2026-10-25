"""What you're attending to now (stage 14, part 5): from the activity stream, like the attention schema of stage 10.

`now` is the window and project you're in and for how long; `deep(app)` is true when you've stayed in one project for a
while without switching. The only use is **timing**: a message that came by itself waits (up to 15 minutes) until you
switch context. It can delay or quieten, never push (the gate, I-7). `mind.tom.attention` (off) needs the activity
stream.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from kurooto.mind.senses import store
from kurooto.mind.tom import model

if TYPE_CHECKING:
    from kurooto.app import App

PART = "attention"
DEEP_S = 20 * 60
HOLD_MAX_S = 15 * 60


def on(app: App) -> bool:
    return (
        model.on(app)
        and bool(app.settings.get("mind.tom.attention"))
        and bool(app.settings.get("mind.senses.activity"))
    )


def now_state(app: App, t: float | None = None) -> dict | None:
    """{"target", "since", "project"} from the latest window events, or None."""
    t = t or time.time()
    ev = [e for e in store.events(app, "activity", t - 3600) if e["kind"] in ("window", "cwd")]
    if not ev:
        return None
    last = ev[-1]
    proj = next((e["target"].split("/")[0] for e in reversed(ev) if e["kind"] == "cwd"), "")
    return {"target": last["target"], "since": last["t"], "project": proj}


def deep(app: App, t: float | None = None) -> bool:
    s = now_state(app, t)
    return bool(s) and (t or time.time()) - s["since"] >= DEEP_S


def hold_s(app: App, t: float | None = None) -> float:
    """How long a message that came by itself should wait: while you're deep in something, up to 15 minutes; else 0."""
    if not on(app) or not deep(app, t):
        return 0.0
    model.guard("timing")
    return float(HOLD_MAX_S)


def remember(app: App) -> None:
    s = now_state(app)
    if s and on(app):
        model.put(
            app,
            PART,
            "now",
            f"in {s['target']}" + (f" ({s['project']})" if s["project"] else ""),
            "saw",
            0.8,
            [f"activity:{int(s['since'])}"],
            by_subject=True,
        )

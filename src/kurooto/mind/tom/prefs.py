"""How you like help (stage 14, part 4): the preferences it already keeps, made explicit with a source and the date
learned.

From your how-to-help-me note (source said: your own lines), and from what you undid or corrected (source inferred:
"undid its
changes to your notes twice: prefers to approve those first"). They only adjust level and timing, never framing.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from kurooto.mind.tom import model

if TYPE_CHECKING:
    from kurooto.app import App

PART = "pref"


def sync(app: App) -> int:
    n = 0
    try:
        from kurooto.modules.remember import help_brief

        for line in (help_brief(app) or "").splitlines():
            line = line.strip(" -*\t")
            if len(line) >= 8 and model.put(
                app,
                PART,
                f"help:{model.norm(line)[:30]}",
                line,
                "said",
                1.0,
                ["how-to-help-me"],
                learned=time.strftime("%Y-%m-%d"),
            ):
                n += 1
    except Exception:  # noqa: S110 (no note yet)
        pass
    return n


def from_undo(app: App, what: str) -> None:
    """He undid or corrected something of this kind: a weak, inferred preference, firmer each time."""
    r = next((x for x in model.rows(app, PART) if x["subject"] == f"undo:{what}"), None)
    times = int(r.get("times", 0)) + 1 if r else 1
    model.put(
        app,
        PART,
        f"undo:{what}",
        f"prefers to check {what} before they happen (undone {times}x)",
        "inferred",
        min(0.9, 0.3 + 0.2 * times),
        [f"undo:{what}"],
        by_subject=True,
        times=times,
    )

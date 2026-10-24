"""Brain: Kurooto's mind (0.8.0). One feature, off until you turn it on (Features → Brain), with a switch for each
part it grows (`mind.<part>.on`). Turned off, Kurooto behaves exactly as 0.7.

Everything in it is a view of two things the AI that acts can't write:
    log.py          the mind log: append-only and hash-chained, so a changed past is caught (invariant I-2)
    score.py        the scorekeeper's tables: setpoints, the body budget, values, trust
    scorekeeper.py  the separate process that alone writes both (invariant I-1)
    client.py       the read-only client the rest of Kurooto uses; its one write is report() of plain facts
    records.py      decision records: what it decided on its own, and why, before acting
    whitelist.py    what may feed reward, and the engagement signals that never may (invariant I-3)

modules/mind.py is the feature: it starts and watches the scorekeeper, mirrors events in, and has /mind.
The design and its invariants: docs/wiki/dev/mind.md.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kurooto.app import App
    from kurooto.mind.client import MindClient

MODULE = "mind"  # the feature's id: Brain is on when it's in modules.enabled (the Features list's switch)

_clients: dict[int, MindClient] = {}
_lock = threading.Lock()


def on(app: App) -> bool:
    """Is Brain on? (The spec's `mind.on`: the Features switch.)"""
    try:
        return app.is_on(MODULE)
    except Exception:
        return False


def part_on(app: App, part: str) -> bool:
    """Brain on and this part's own switch (`mind.<part>.on`) on."""
    return on(app) and bool(app.settings.get(f"mind.{part}.on"))


def connect(app: App) -> MindClient:
    """The one mind client of this app (reads, and report() for facts)."""
    from kurooto.mind.client import MindClient

    with _lock:
        c = _clients.get(id(app))
        if c is None or c.app is not app:
            c = _clients[id(app)] = MindClient(app)
        return c


def forget_client(app: App) -> None:
    with _lock:
        c = _clients.pop(id(app), None)
    if c is not None:
        c.close()

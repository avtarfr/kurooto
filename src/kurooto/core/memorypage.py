"""The dashboard's Memory page (0.9.0, look.memory_page): everything Kurooto keeps about you, in one place.

Each store already has its own command; this only reads them side by side: the memory ledger (/memory), open threads
(/threads), what was set up from what you said (/inferred), what it learned from its own work (/learned), topics you
aren't interested in, Brain's model of you (/model) and its count of what add-ons keep. Changing something stays with
those commands and their Undo, except the model of you, whose Wrong and Forget work here as on the Brain console
(mind/tom/prefs.py: console_edit, only on your click). Nothing here is sent anywhere: the page is on this computer.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from typing import TYPE_CHECKING

from kurooto.core.config import register_defaults

if TYPE_CHECKING:
    from kurooto.app import App

register_defaults("look", {"memory_page": True})  # 0.9.0: the dashboard's Memory page (Alt+U), read side by side

ROWS = 30
# add-ons say how much they keep: name -> fn(app) -> {"title", "count", "what"} (counts only, never the rows)
COUNTERS: dict[str, Callable] = {}


def register_counter(name: str, fn: Callable) -> None:
    """An add-on's own store, as a count on this page (the Body add-on's brain facts, say)."""
    COUNTERS[name] = fn


def _day(at: float) -> str:
    return f"{dt.datetime.fromtimestamp(float(at)):%d %b}"


def view(app: App) -> dict:
    if not app.settings.get("look.memory_page"):
        return {"off": True}
    out: dict = {"off": False}
    from kurooto.core import ledger, threads

    try:
        if ledger.locked(app):
            out["ledger"] = {"locked": True}
        else:
            led = ledger.of(app)
            rows = sorted(led.rows(), key=lambda r: -float(r["at"]))[:ROWS]
            out["ledger"] = {
                "counts": {ledger.NAMES.get(k, k): n for k, n in led.counts().items()},
                "rows": [{"from": ledger.label(r), "text": str(r.get("text") or "")[:200]} for r in rows],
            }
    except Exception as e:
        out["ledger"] = {"error": type(e).__name__}
    try:
        out["threads"] = [{"text": str(r["text"])[:200], "from": ledger.said(r)} for r in threads.open_threads(app)][
            :ROWS
        ]
    except Exception:
        out["threads"] = []
    try:
        from kurooto.core import infer

        items = [x for x in infer._load(app)["items"] if not x.get("undone")][-ROWS:]  # noqa: SLF001
        out["inferred"] = [{"id": x.get("id"), "day": _day(x.get("at") or 0), "text": str(x.get("line") or "")[:200]}
                           for x in reversed(items)]  # fmt: skip
    except Exception:
        out["inferred"] = []
    lm = app.modules.get("learning")
    try:
        changes = list(reversed(lm.changes()))[:ROWS] if lm else []
        out["learned"] = [
            {
                "day": str(c.get("at") or "")[:10],
                "text": str(c.get("said") or c.get("name") or c.get("kind") or "")[:200],
            }
            for c in changes
        ]
    except Exception:
        out["learned"] = []
    try:
        from kurooto.core.notinterested import ignored_topics

        out["not_interested"] = ignored_topics(app)[:ROWS]
    except Exception:
        out["not_interested"] = []
    try:
        from kurooto.mind import console

        out["model"] = console.model(app, ROWS)
    except Exception:
        out["model"] = {"rows": []}
    adds = []
    for name, fn in list(COUNTERS.items()):
        try:
            got = fn(app) or {}
            adds.append({"title": str(got.get("title") or name)[:60], "count": int(got.get("count") or 0),
                         "what": str(got.get("what") or "")[:120]})  # fmt: skip
        except Exception as e:  # one add-on's count failing leaves the rest
            app.events.emit("memory_page_failed", addon=name[:40], error=type(e).__name__)
    out["addons"] = adds
    return out

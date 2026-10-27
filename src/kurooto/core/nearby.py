"""Others nearby (0.8.10): a small shared signal, "someone besides you is at the desk", that one feature sets and others
read without depending on each other's code.

    set_others(app, source, on)   Face presence sets it ("face") when a second face is in view of the camera, and
                                  clears it when there's one face or the camera closes. Only the fact is kept, in
                                  memory: no face, no template, no picture, no count of who.
    others(app) -> bool           any source says so, within the last STALE_S seconds
    sources(app) -> list[str]

Voice (and Voice ID's conversation mode) can read it: while others are present, Kurooto stays out of a conversation
between people unless it's named. An event "nearby_others {on, source}" says when it changes (no other fields).
Nothing here authorises anything: a face never makes Kurooto act.
"""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kurooto.app import App

STALE_S = 120  # a signal not refreshed for this long no longer counts (a camera that closed without saying so)
_lock = threading.Lock()


def _table(app: App) -> dict[str, float]:
    t = getattr(app, "_nearby", None)
    if t is None:
        t = {}
        app._nearby = t  # type: ignore[attr-defined]
    return t


def set_others(app: App, source: str, on: bool) -> None:
    with _lock:
        t = _table(app)
        was = source in t
        if on:
            t[source] = time.monotonic()
        else:
            t.pop(source, None)
    if was != bool(on):
        try:
            app.events.emit("nearby_others", on=bool(on), source=source)
        except Exception:
            pass


def sources(app: App) -> list[str]:
    now = time.monotonic()
    with _lock:
        t = _table(app)
        return sorted(s for s, at in t.items() if now - at <= STALE_S)


def others(app: App) -> bool:
    return bool(sources(app))

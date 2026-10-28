"""Others nearby (0.8.10): a small shared signal, "someone besides you is at the desk", that one feature sets and others
read without depending on each other's code.

    set_others(app, source, on)   Face presence sets it ("face") when a second face is in view of the camera, and
                                  clears it when there's one face or the camera closes. Only the fact is kept, in
                                  memory: no face, no template, no picture, no count of who.
    others(app) -> bool           any source says so, within the last STALE_S seconds
    sources(app) -> list[str]

Voice (and Voice ID's conversation mode) can read it: while others are present, Kurooto stays out of a conversation
between people unless it's named. An event "nearby_others {on, source}" says when it changes (no other fields).

    set_view(app, faces, owner_alone)   (0.8.13) Face presence, each frame it looks at: how many faces are in view
                                  and whether the only one is the owner's. In memory, never an event.
    view(app) -> (faces, owner_alone) | None   that, when it's at most VIEW_S old (the camera may not be looking)

    set_facing(app, faces, facing)   (0.8.13, voice.listen.need_face) Face presence, each frame it looks at: how many
                                  faces, and how many of them are close and facing the camera (Face.close_facing).
                                  Kept in memory for FACING_KEEP_S as times and counts only: no picture, no numbers
                                  that describe a face, no identity.
    facing(app, since, until) -> (frames, frames_with_one)   the frames looked at in that stretch (monotonic times)
                                  and how many of them had a face close and facing it
    last_facing(app) -> float | None   when the last such face was seen (monotonic)

    set_look(app, on)             (0.8.17, voice.listen.look_to_talk) Face presence, each frame it looks at: whether the
                                  owner's face is close and turned to the camera within the tight look angles
                                  (Face.looking). Two times only: when this run of such frames began, and the last one.
    look(app) -> (since, last)    since: None when the last frame looked at didn't have him looking (or the camera
                                  closed); last: when he was last seen looking (monotonic), None never

Nothing here authorises anything by itself. The one narrow use of the view (Voice ID's face assist, 0.8.13,
voice.speaker_id.face_assist): a voice already scored inside its "not sure" margin counts as the owner while his face
is the only one in view. A face alone never makes Kurooto act.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kurooto.app import App

STALE_S = 120  # a signal not refreshed for this long no longer counts (a camera that closed without saying so)
VIEW_S = 5.0  # the view counts this long after the frame (Face presence looks about once a second, 3 s on battery)
FACING_KEEP_S = 60.0  # frames older than this are forgotten (a turn's window is a few seconds)
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


def set_view(app: App, faces: int, owner_alone: bool) -> None:
    with _lock:
        app._nearby_view = (int(faces), bool(owner_alone), time.monotonic())  # type: ignore[attr-defined]


def clear_view(app: App) -> None:
    with _lock:
        app._nearby_view = None  # type: ignore[attr-defined]
        app._nearby_look = (None, getattr(app, "_nearby_look", (None, None))[1])  # type: ignore[attr-defined]


def set_look(app: App, on: bool, at: float | None = None) -> None:
    """One frame looked at (at: its monotonic time, None: now): the owner looking at the camera in it or not."""
    t = time.monotonic() if at is None else float(at)
    with _lock:
        since, last = getattr(app, "_nearby_look", (None, None))
        app._nearby_look = (t if since is None else since, t) if on else (None, last)  # type: ignore[attr-defined]


def look(app: App) -> tuple[float | None, float | None]:
    with _lock:
        return getattr(app, "_nearby_look", (None, None))


def view(app: App) -> tuple[int, bool] | None:
    with _lock:
        v = getattr(app, "_nearby_view", None)
    if v is None or time.monotonic() - v[2] > VIEW_S:
        return None
    return v[0], v[1]


def _looks(app: App) -> deque:
    d = getattr(app, "_nearby_looks", None)
    if d is None:
        d = deque(maxlen=600)  # (time, faces, close and facing): at most 10 a second for a minute
        app._nearby_looks = d  # type: ignore[attr-defined]
    return d


def set_facing(app: App, faces: int, facing: int, at: float | None = None) -> None:
    """One frame looked at (at: its monotonic time, None: now)."""
    now = time.monotonic()
    t = now if at is None else float(at)
    with _lock:
        d = _looks(app)
        d.append((t, int(faces), int(facing)))
        while d and now - d[0][0] > FACING_KEEP_S:
            d.popleft()
        if facing > 0 and t >= (getattr(app, "_nearby_facing_at", None) or 0.0):
            app._nearby_facing_at = t  # type: ignore[attr-defined]


def facing(app: App, since: float, until: float | None = None) -> tuple[int, int]:
    """Frames looked at between since and until (monotonic; until None: now), and how many had a face close and
    facing the camera."""
    hi = time.monotonic() if until is None else until
    with _lock:
        rows = [r for r in _looks(app) if since <= r[0] <= hi]
    return len(rows), sum(1 for r in rows if r[2] > 0)


def last_facing(app: App) -> float | None:
    with _lock:
        return getattr(app, "_nearby_facing_at", None)

"""Natural breaks (Brain, 0.8.14, `mind.workspace.breaks`): the moments a message that came by itself may reach you
without cutting into what you're doing.

A message that won at the workspace's door (mind/workspace.py) and isn't urgent waits for one of these:
    window_switch   you moved to another window after 25+ minutes in one (`mind.workspace.break_after_min`; the
                    activity sense, mind/senses/activity.py, opt-in)
    session_end     a study session or focus time ended
    pickup          the phone was unlocked (the phone's screen sense, opt-in)
    back            you came back to the desk after being away (Face presence; 0.9.0: or your voice or the dashboard
                    ended its away, core/here.py)
    stood, left, looked     an add-on's senses, through signal(); (0.9.0, face.breaks) and Face presence on this
                    computer: face_left (with face.away.on), face_looked (a look at the camera for a second),
                    face_stood (your face well under its usual desk size)
It also goes after at most `mind.workspace.max_hold_min` (90) minutes of waiting, unless Kurooto is asleep
(mind/sleep.py, when that part is there).

When nothing here can see a break coming (no activity or phone screen sense, no Face presence, no add-on that
signalled in the last day, no study session running), waiting would only delay things, so winners go at once.

Kept in `<state>/mind-breaks.json`: the last break (when and which kind), what the polls have already seen, and counts.
Never the window's name or anything you typed: kinds and times only.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from kurooto import mind
from kurooto.core.lock import Lock
from kurooto.core.state import jload, jsave

if TYPE_CHECKING:
    from kurooto.app import App

PART = "workspace"  # its switch: mind.workspace.on, with mind.workspace.breaks
FILE = "mind-breaks.json"
KINDS = ("pickup", "stood", "left", "window_switch", "session_end", "looked", "back")
OPEN_S = 5 * 60  # a break counts as "now" this long, so the next minute's round can still use it
FRESH_S = 15 * 60  # a sensed break older than this when it's first seen (a late phone bin) is history, not a break
ADDON_DAY_S = 86400  # an add-on that signalled within a day counts as a way of seeing breaks
SIGNAL_GAP_S = 10  # the same kind signalled again within this many seconds is one break (a flood isn't many)
LABELS = {
    "pickup": "you picked up your phone",
    "stood": "you stood up",
    "left": "you stepped away",
    "window_switch": "you switched windows after a long stretch",
    "session_end": "a study session or focus time ended",
    "looked": "you looked up",
    "back": "you came back to the desk",
}
EVENTS = {  # Kurooto's own events that are breaks (or start the thing whose end will be one)
    "study_session_end": "session_end",
    "focus_ended": "session_end",
    "face_back": "back",
    "face_arrived": "back",
}
FACE_EVENTS = {"face_left": "left", "face_looked": "looked", "face_stood": "stood"}  # (0.9.0, face.breaks)


def on(app: App) -> bool:
    """Brain on, the workspace on, and its breaks switch on."""
    return mind.part_on(app, "workspace") and bool(app.settings.get("mind.workspace.breaks"))


def _load(app: App) -> dict:
    d = jload(app.paths.state / FILE, {}) or {}
    for k, v in (("last", {}), ("seen", {}), ("counts", {}), ("addon_at", 0.0), ("session", False)):
        d.setdefault(k, v)
    return d


def _save(app: App, d: dict) -> None:
    jsave(app.paths.state / FILE, d)


def _num(app: App, key: str, default: float) -> float:
    v = app.settings.get(f"mind.workspace.{key}")
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0 else default


def _mark(app: App, kind: str, at: float, addon: bool = False) -> bool:
    """Write a break down. False when it's the same kind again within SIGNAL_GAP_S (nothing new)."""
    with Lock(app.paths.state, "mind-breaks"):
        d = _load(app)
        last = d["last"] or {}
        if last.get("kind") == kind and abs(at - float(last.get("at") or 0)) < SIGNAL_GAP_S:
            return False
        if at >= float(last.get("at") or 0):
            d["last"] = {"at": round(at, 1), "kind": kind}
        d["counts"][kind] = int(d["counts"].get(kind, 0)) + 1
        if addon:
            d["addon_at"] = round(time.time(), 1)
        if kind == "session_end":
            d["session"] = False
        _save(app, d)
    return True


def signal(app: App, kind: str) -> None:
    """A natural break, from an add-on or a sense: "pickup", "stood", "left", "window_switch", "session_end",
    "looked" (or "back"). Waiting winners at the workspace's door go now, and it's an orienting jolt: the workspace
    runs a cycle at once. Never raises; does nothing with Brain or the breaks switch off, or for an unknown kind."""
    try:
        if kind not in KINDS or not on(app):
            return
        if not _mark(app, kind, time.time(), addon=True):
            return
        app.events.emit("mind_break", kind=kind)
        from kurooto.mind import workspace

        workspace.cycle(app, force=True)
        workspace.release(app)
    except Exception as e:
        app.events.emit("mind_break_failed", error=type(e).__name__)


def on_event(app: App, rec: dict) -> None:
    """Kurooto's own events (modules/mind.py passes each one): a session ending or you coming back is a break; a
    study session starting means one is coming."""
    try:
        kind = str((rec or {}).get("kind") or "")
        if kind == "study_session_start" and on(app):
            with Lock(app.paths.state, "mind-breaks"):
                d = _load(app)
                d["session"] = True
                _save(app, d)
            return
        b = EVENTS.get(kind)
        if kind in FACE_EVENTS and app.settings.get("face.breaks"):  # (0.9.0) the laptop's camera, not only add-ons'
            b = FACE_EVENTS[kind]
        if kind == "owner_here" and rec.get("back"):  # (0.9.0) your voice or the dashboard ended Face's away
            b = "back"
        if b is None or not on(app):
            return
        if _mark(app, b, time.time()):
            from kurooto.mind import workspace

            workspace.release(app)
    except Exception as e:
        app.events.emit("mind_break_failed", error=type(e).__name__)


def detect(app: App, now: float | None = None) -> list[str]:
    """The minute's look at the senses for breaks it can't be told about: a window switch after a long stretch in one
    window (the activity sense) and a phone unlock (the phone's screen sense). Returns the kinds found."""
    if not on(app):
        return []
    from kurooto.mind.senses import activity, phone, store

    t = time.time() if now is None else now
    found: list[tuple[str, float]] = []
    d = _load(app)
    seen = dict(d["seen"])
    if activity.on(app):
        since = float(seen.get("window") or (t - FRESH_S))
        rows = store.events(app, "activity", t - 6 * 3600, kind="window")
        long_s = _num(app, "break_after_min", 25.0) * 60
        for prev, cur in zip(rows, rows[1:], strict=False):
            if cur["t"] <= since:
                continue
            if cur["t"] - prev["t"] >= long_s and t - cur["t"] <= FRESH_S:
                found.append(("window_switch", cur["t"]))
        if rows:
            seen["window"] = max(since, rows[-1]["t"])
    if phone.enabled(app, "screen"):
        since = float(seen.get("unlock") or (t - FRESH_S))
        rows = [r for r in store.events(app, "phone:screen", since, kind="unlocks") if r["t"] > since and r["n"] > 0]
        for r in rows:
            if t - r["t"] <= FRESH_S:
                found.append(("pickup", t))  # a phone bin arrives late: the break is when it's seen
        if rows:
            seen["unlock"] = rows[-1]["t"]
    if seen != d["seen"]:
        with Lock(app.paths.state, "mind-breaks"):
            d = _load(app)
            d["seen"] = seen
            _save(app, d)
    out = []
    for kind, at in found:
        if _mark(app, kind, at):
            out.append(kind)
    return out


def open_now(app: App, now: float | None = None) -> str | None:
    """The kind of break happening now (within the last few minutes), or None."""
    t = time.time() if now is None else now
    last = _load(app)["last"] or {}
    at = float(last.get("at") or 0)
    return str(last.get("kind")) if last.get("kind") and -1.0 <= t - at <= OPEN_S else None  # (times are rounded)


def sensing(app: App, now: float | None = None) -> bool:
    """Can anything see a break coming? The activity or phone screen sense, Face presence, an add-on that signalled in
    the last day, or a study session running now."""
    from kurooto.mind.senses import activity, phone

    t = time.time() if now is None else now
    try:
        if activity.on(app) or phone.enabled(app, "screen") or app.is_on("face"):
            return True
    except Exception:
        pass
    d = _load(app)
    return t - float(d.get("addon_at") or 0) < ADDON_DAY_S or bool(d.get("session"))


def wait_needed(app: App, now: float | None = None) -> bool:
    """Must a non-urgent winner wait for a break? Only with breaks on and something that can see one coming."""
    return on(app) and sensing(app, now)


def max_hold_s(app: App) -> float:
    return _num(app, "max_hold_min", 90.0) * 60


def last(app: App) -> dict:
    """The last break: {"at", "kind"} (empty when there hasn't been one)."""
    return dict(_load(app)["last"] or {})


def label(kind: str | None) -> str:
    return LABELS.get(kind or "", "a break")

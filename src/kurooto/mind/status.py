"""One status stream (Brain, 0.8.14, `mind.status.on`): what Brain is like right now, as enums and numbers only, so
every face of it reads the same thing: the dashboard's being, the phone's Views, Voice's pace, add-ons (the private
Body face reads it through add_listener).

    snapshot(app)       {focus, asleep, held, uneasy, mood, arousal, top}
                          focus    bool    focus time is on (do-not-disturb, or a #focus calendar event)
                          asleep   bool    Kurooto's own sleep (mind/sleep.py) says "asleep"
                          held     int     unprompted messages waiting (the workspace arbiter's, else the gate's)
                          uneasy   str     the id of the one deadline or promise it's uneasy about ("deadline:<id>",
                                           "promise:<id>"), or None; never its title
                          mood     enum    "low", "mid" or "high": its own running mood (mind/feelings.py), never yours
                          arousal  0..1    its own arousal (feelings)
                          top      str     the kind of the first thing on its mind that isn't about you, or None
    knobs(app)          the three honest knobs: mood sets exploration, arousal responsiveness, belief calibration
                        ask-or-act (add-ons read it; play and the lab use `explore`, act.verdict uses `ask`)
    add_listener(fn)    fn(app, snap) on every change; returns remove()
    start(app) / stop   the stream: on any event (and every STALE_S anyway) the snapshot is made again, at most once a
                        second, and on a change it's pushed to open dashboard pages as {"t": "mind", "kind": "status",
                        ...} and given to the listeners. The phone's copy (modules/calls/views.py) takes snapshot() as
                        it seals each Systems copy.

Nothing here says how you are: your read, tone and mood never enter it (the mood is Kurooto's own). It stays on this
computer: the dashboard, the phone's sealed copy and add-ons running here.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import TYPE_CHECKING

from kurooto import mind
from kurooto.core.config import register_defaults

if TYPE_CHECKING:
    from kurooto.app import App

register_defaults(
    "mind",
    {
        "status": {
            "on": True
        },  # one status stream (focus, asleep, held, uneasy, mood, arousal) for every face of Brain
        "knobs": {"on": True},  # its mood sets how much it explores, arousal how fast it speaks up, calibration asking
    },
)
register_defaults(
    "look",
    {
        "being_status": True,  # the being as a glance: eyes shut in focus or asleep, the held count, one uneasy glow
        "being_mood": True,  # Brain's mood in the drawing: the fluid's tint and the heart's rhythm (quieter when low)
    },
)

PART = "status"  # its switch: mind.status.on (the knobs: mind.knobs.on)
KEYS = ("focus", "asleep", "held", "uneasy", "mood", "arousal", "top")
NEUTRAL = {"focus": False, "asleep": False, "held": 0, "uneasy": None, "mood": "mid", "arousal": 0.0, "top": None}
MOODS = ("low", "mid", "high")
MIN_GAP_S = 1.0  # pushed at most once a second
STALE_S = 15.0  # made again this often with no event (focus time ending, a deadline passing)
COIN_FLIP = 0.25  # a Brier score at or above this is no better than guessing
BRIER_MIN_N = 10  # beliefs scored before calibration counts


def on(app: App) -> bool:
    return mind.part_on(app, "status")


# ---------------------------------------------------------------------------------------------------- the parts
def _focus(app: App) -> bool:
    try:
        return app.availability.focus_until() is not None
    except Exception:
        return False


def _asleep(app: App) -> bool:
    try:
        from kurooto.mind import sleep as msleep  # (0.8.14, the sleep group) absent on its own branch
    except ImportError:
        return False
    try:
        return msleep.state(app) == "asleep"
    except Exception:
        return False


def _held(app: App) -> int:
    """The arbiter's held count when it's there, else the gate's held messages (0.8.0)."""
    from kurooto.mind import workspace

    fn = getattr(workspace, "held_count", None)
    if fn is not None:
        try:
            return max(0, int(fn(app)))
        except Exception:
            return 0
    try:
        from kurooto.mind import gate

        return len(gate._load(app)["held"]) if gate.on(app) else 0  # noqa: SLF001
    except Exception:
        return 0


def _feelings(app: App) -> dict:
    try:
        from kurooto.mind import feelings

        return feelings.state(app) if mind.part_on(app, "feelings") else {}
    except Exception:
        return {}


def _mood(app: App) -> str:
    try:
        from kurooto.mind import feelings

        return {"low": "low", "high": "high"}.get(feelings.mood_band(app), "mid")
    except Exception:
        return "mid"


def _uneasy(app: App, st: dict) -> str | None:
    """The one item it's uneasy about, as an id: the open promise with the least slack when that's what its unease is
    about, else the deadline it's most concerned for (empathy's concern at or over the notice bar)."""
    from kurooto.mind import feelings

    if st.get("label") in ("uneasy", "worried", "frustrated") and st.get("object") == "promise_slack":
        try:
            from kurooto.mind import promises

            opens = [r for r in promises._state(app)["rows"] if r.get("state") == "open"]  # noqa: SLF001
            if opens:
                return f"promise:{min(opens, key=lambda r: r['due'])['id']}"
        except Exception:
            pass
    worry = [
        c for c in st.get("concerns") or [] if c.get("kind") == "deadline" and c.get("concern", 0) >= feelings.NOTICE_AT
    ]
    if not worry:
        return None
    title = str(max(worry, key=lambda c: c.get("concern", 0)).get("item") or "")
    dl = app.modules.get("deadlines")
    if dl is None or not app.is_on("deadlines") or not title:
        return None
    try:
        for i, it, _h in dl.upcoming(168):
            if str(it.get("title") or "")[:80] == title:
                return f"deadline:{i}"
    except Exception:
        return None
    return None


def _top(app: App) -> str | None:
    try:
        from kurooto.mind import workspace

        for w in workspace.current(app):
            if not w.get("private"):
                return str(w.get("kind") or "") or None
    except Exception:
        pass
    return None


def snapshot(app: App) -> dict:
    """Brain's status now: enums and numbers only (KEYS). With Brain or the stream off, the neutral one."""
    if not on(app):
        return dict(NEUTRAL)
    st = _feelings(app)
    try:
        ar = round(max(0.0, min(1.0, float(st.get("arousal") or 0.0))), 2)
    except (TypeError, ValueError):
        ar = 0.0
    try:
        uneasy = _uneasy(app, st)
    except Exception:
        uneasy = None
    return {
        "focus": _focus(app),
        "asleep": _asleep(app),
        "held": _held(app),
        "uneasy": uneasy,
        "mood": _mood(app),
        "arousal": ar,
        "top": _top(app),
    }


# ---------------------------------------------------------------------------------------------- the three knobs
KNOBS_NEUTRAL = {
    "explore": 1.0,
    "interest_shift": 0.0,
    "respond": 0.5,
    "hold_scale": 1.0,
    "uncertainty": None,
    "ask": False,
}


def calibration(app: App) -> float | None:
    """Its beliefs' mean Brier score over every source (weighted by how many were scored), or None before
    BRIER_MIN_N were."""
    try:
        from kurooto.mind import beliefs

        rows = beliefs.brier(app)
    except Exception:
        return None
    n = sum(int(c) for c, _ in rows.values())
    if n < BRIER_MIN_N:
        return None
    return round(sum(int(c) * float(v) for c, v in rows.values()) / n, 4)


def knobs(app: App, snap: dict | None = None) -> dict:
    """The three honest knobs (`mind.knobs.on`), for the parts that use them and for add-ons:
        explore         0.5 to 1: its share of the lab's and play's nightly budget (mood low: half; never more than
                        you set)
        interest_shift  added to an add-on's interest threshold (low mood: a higher bar; high: a little lower)
        respond         0 to 1: its arousal; how soon unprompted things may go
        hold_scale      0.75 to 1.25: what a held message's longest wait is multiplied by (aroused: sooner)
        uncertainty     its beliefs' Brier score, or None before it has enough
        ask             True when that's no better than a coin flip: its own R1+ acts ask first
    Neutral with Brain or the knobs off. Nothing here touches what you asked for."""
    if not mind.part_on(app, "knobs"):
        return dict(KNOBS_NEUTRAL)
    s = snap or snapshot(app)
    mood, ar = s.get("mood", "mid"), float(s.get("arousal") or 0.0)
    unc = calibration(app)
    return {
        "explore": {"low": 0.5}.get(mood, 1.0),
        "interest_shift": {"low": 0.1, "high": -0.05}.get(mood, 0.0),
        "respond": round(ar, 2),
        "hold_scale": round(1.25 - 0.5 * ar, 3),
        "uncertainty": unc,
        "ask": unc is not None and unc >= COIN_FLIP,
    }


def explore(app: App) -> float:
    """The share of the lab's and play's budget to spend tonight (1.0 unless its mood is low)."""
    try:
        return float(knobs(app)["explore"])
    except Exception:
        return 1.0


# ------------------------------------------------------------------------------------------------- the stream
_listeners: list[Callable] = []


def add_listener(fn: Callable) -> Callable[[], None]:
    """fn(app, snap) on every change of the snapshot (add-ons: the Body face reads it). Returns remove(). A listener
    that raises is skipped that time; it never stops the stream."""
    _listeners.append(fn)
    return lambda: _listeners.remove(fn) if fn in _listeners else None


class Stream:
    """One per app: remakes the snapshot when something happens, and pushes it on a change."""

    def __init__(self, app: App):
        self.app = app
        self.last: dict | None = None
        self.pushed_at = 0.0
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._unsub: Callable | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        from kurooto.core.events import subscribe

        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._unsub = subscribe(lambda rec: self._wake.set())
        self._thread = threading.Thread(target=self._loop, name="mind-status", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._unsub is not None:
            self._unsub()
            self._unsub = None

    def poke(self) -> None:
        self._wake.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            self._wake.wait(STALE_S)
            self._wake.clear()
            if self._stop.is_set():
                break
            gap = MIN_GAP_S - (time.monotonic() - self.pushed_at)
            if gap > 0 and self._stop.wait(gap):
                break
            try:
                self.check()
            except Exception as e:  # the stream never takes Kurooto down
                self.app.events.emit("mind_status_failed", error=type(e).__name__)
                self._stop.wait(5)

    def check(self) -> bool:
        """Make the snapshot; on a change, push it. True when it was pushed."""
        if not on(self.app):
            self.last = None
            return False
        snap = snapshot(self.app)
        if snap == self.last:
            return False
        self.last = snap
        self.pushed_at = time.monotonic()
        deliver(self.app, snap)
        return True


def deliver(app: App, snap: dict) -> None:
    """To open dashboard pages (never into the event log) and to every listener."""
    live = getattr(app, "live", None)
    if live is not None:
        try:
            k = knobs(app, snap)
            knob = {x: k[x] for x in ("explore", "respond", "uncertainty")}
            live.push({"t": "mind", "kind": "status", **snap, "knobs": knob})
        except Exception:
            pass
    for fn in list(_listeners):
        try:
            fn(app, dict(snap))
        except Exception:  # noqa: S112 (one listener failing leaves the others)
            continue


_streams: dict[int, Stream] = {}
_lock = threading.Lock()


def start(app: App) -> Stream:
    with _lock:
        s = _streams.get(id(app))
        if s is None or s.app is not app:
            s = _streams[id(app)] = Stream(app)
    s.start()
    s.poke()
    return s


def stop(app: App) -> None:
    with _lock:
        s = _streams.pop(id(app), None)
    if s is not None:
        s.stop()


def poke(app: App) -> None:
    """Something changed that no event says (a setting): make the snapshot again soon."""
    s = _streams.get(id(app))
    if s is not None:
        s.poke()


# --------------------------------------------------------------------------------------- for the dashboard's tap
def uneasy_target(app: App, uid: str | None) -> dict | None:
    """What a tap on the uneasy glow opens, for this computer's own dashboard (GET /api/mind/status): the item's title
    and where it lives. Only ever asked for by your own page; the pushed status carries the id alone."""
    if not uid or ":" not in uid:
        return None
    kind, key = uid.split(":", 1)
    if kind == "deadline":
        dl = app.modules.get("deadlines")
        it = (dl.items() or {}).get(key) if dl is not None and app.is_on("deadlines") else None
        if it:
            out = {"kind": "deadline", "id": key, "title": str(it.get("title") or "")[:80], "tab": "today"}
            from kurooto.mind import study_push

            if it.get("subject") and study_push.start_timer_on(app):  # 0.9.0: Study mode opens on its subject
                out["subject"] = it["subject"]
            return out
    if kind == "promise":
        from kurooto.mind import promises

        row = next((r for r in promises._state(app)["rows"] if r.get("id") == key), None)  # noqa: SLF001
        if row:
            return {"kind": "promise", "id": key, "title": str(row.get("act") or "")[:80], "tab": "console"}
    return None


def view(app: App) -> dict:
    """GET /api/mind/status: the snapshot, the knobs, whether the being shows them, and the uneasy item's title."""
    snap = snapshot(app)
    return {
        "on": on(app),
        **snap,
        "knobs": knobs(app, snap),
        "look": {
            "status": app.settings.get("look.being_status") is not False,
            "mood": app.settings.get("look.being_mood") is not False,
        },
        "uneasy_item": uneasy_target(app, snap.get("uneasy")),
    }


def cached(app: App) -> dict:
    """The last pushed snapshot, or a fresh one (the phone's copy)."""
    s = _streams.get(id(app))
    return dict(s.last) if s is not None and s.last is not None else snapshot(app)


__all__ = ["snapshot", "knobs", "add_listener", "start", "stop", "poke", "view", "explore", "calibration"]

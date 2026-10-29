"""Phone sensors (Brain, 0.8.0 stage 13): each opt-in on the phone and here, all off by default.

The phone aggregates in 5-minute bins, seals them with the per-phone key and sends them through the call line's sealed
outbox; the line can't read them. `ingest` takes what the chat's `take` opened ({"senses": {"bins": [...]}}) and keeps
only known sensors that are switched on here, only the fields named below, only numbers and short labels.

    screen      unlocks, on_min        sleep onset, presence
    charging    on (0/1)               "asleep" with the light and stillness
    motion      still / walking / vehicle, minutes     computed on the phone ("walking to class: don't ring")
    steps       total (the day's)      the energy signal for the read
    light       dark / dim / bright    sleep detection
    places      arrive / leave of a place you saved (its label)
    headphones  on (0/1)               in a call or focused: hold the ring
    dnd         on (0/1)               respect it; learn your quiet hours
    alarm       the next alarm's time  the wake forecast
    wifi        a hash of the network the phone made itself (you label it once: /senses wifi label <id> <name>)
    usage       total screen minutes a day (never per app)
Microphone level is never collected. They feed timing (quieter) and forecasts through the gate; never a nag.
"""

from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING

from kurooto import mind
from kurooto.core.config import register_defaults
from kurooto.mind.senses import store

if TYPE_CHECKING:
    from kurooto.app import App

SENSORS = {
    "screen": {"unlocks": "n", "on_min": "n"},
    "charging": {"on": "n"},
    "motion": {"state": ("still", "walking", "vehicle"), "min": "n"},
    "steps": {"total": "n"},
    "light": {"band": ("dark", "dim", "bright")},
    "places": {"event": ("arrive", "leave"), "label": "s"},
    "headphones": {"on": "n"},
    "dnd": {"on": "n"},
    "alarm": {"at": "n"},
    "wifi": {"id": "h"},
    "usage": {"min": "n"},
}
LABEL = re.compile(r"^[\w .'-]{1,30}$")
HASH = re.compile(r"^[0-9a-f]{8,16}$")
BINS_MAX = 300
PLACE_FRESH_S = 1800  # (0.9.0) a place's arrive or leave older than this is history, not news for the desk

register_defaults(
    "mind", {"senses": {"phone": {s: False for s in SENSORS}}}
)  # each phone sensor, off until you switch it on


def enabled(app: App, sensor: str) -> bool:
    return mind.on(app) and bool(app.settings.get(f"mind.senses.phone.{sensor}"))


def clean(sensor: str, b: dict) -> tuple[str, str, float] | None:
    """One bin -> (kind, target, number), or None when it isn't something this sensor may say."""
    spec = SENSORS.get(sensor)
    if not spec:
        return None
    kind, target, num = sensor, "", 0.0
    for f, rule in spec.items():
        v = b.get(f)
        if v is None:
            continue
        if rule == "n":
            if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v:
                return None
            num, kind = float(v), f
        elif rule == "s":
            if not isinstance(v, str) or not LABEL.match(v):
                return None
            target = v
        elif rule == "h":
            if not isinstance(v, str) or not HASH.match(v):
                return None
            target = v
        elif v in rule:
            target, kind = str(v), f
        else:
            return None
    return kind, target, num


def ingest(app: App, payload: dict) -> tuple[int, dict]:
    bins = payload.get("bins") if isinstance(payload, dict) else None
    if not isinstance(bins, list):
        return 400, {"ok": False, "note": "No readings in that."}
    kept = dropped = 0
    for b in bins[:BINS_MAX]:
        sensor = str((b or {}).get("s") or "") if isinstance(b, dict) else ""
        if not enabled(app, sensor):
            dropped += 1
            continue
        c = clean(sensor, b)
        t = b.get("t")
        if (
            c is None
            or isinstance(t, bool)
            or not isinstance(t, (int, float))
            or abs(t / 1000 - time.time()) > 3 * 86400
        ):
            dropped += 1
            continue
        store.add(app, f"phone:{sensor}", c[0], c[1], c[2], t=t / 1000)
        kept += 1
        if sensor == "places" and b.get("event") in ("arrive", "leave") and time.time() - t / 1000 <= PLACE_FRESH_S:
            _place(app, str(b["event"]), t / 1000)
        if sensor == "places":
            place_hooks(app, str(b.get("event") or ""), c[1], t / 1000)
    app.events.emit("senses_phone", kept=kept, dropped=dropped)
    try:  # (0.9.0, notify.respect_phone_dnd) Do Not Disturb ended: what waited for it goes now
        if kept and enabled(app, "dnd") and not dnd_on(app):
            app.notifier.flush_dnd()
    except Exception:
        pass
    if any(_picked_up(b) for b in bins[:BINS_MAX] if isinstance(b, dict) and enabled(app, "screen")):
        from kurooto.mind import stimulation

        stimulation.jolt(app, "pickup")  # (0.8.14) the phone just picked up: an orienting jolt
    return 200, {"ok": True, "kept": kept}


def _place(app: App, event: str, at: float) -> None:
    """(0.9.0) The phone left a saved place or arrived at one: core/nearby.py's phone_out (a time only, never the
    label), then Face presence (face.away.use_places). Never raises."""
    from kurooto.core import nearby

    try:
        nearby.set_phone_out(app, event == "leave", at=at)
        face = app.modules.get("face")
        if face is not None and app.is_on("face"):
            face.phone_place(event)
    except Exception as e:
        app.events.emit("senses_failed", error=type(e).__name__)


PLACE_HOOKS = ("study", "subjects", "exam_season")  # features that may offer something on an arrival (each off)


def place_hooks(app: App, event: str, label: str, ts: float) -> None:
    """(0.9.0) A fresh arrival at or leaving of a place you saved, to the features that use it, each behind its own
    switch (study.places, subjects.attend_by_place, exam_season.debrief_at_desk): an offer you tap, never a
    record of where you were. The label stays on this computer and never goes into an AI's context."""
    if event not in ("arrive", "leave") or not label or abs(time.time() - ts) > PLACE_FRESH_S:
        return
    import datetime as dt

    t = dt.datetime.fromtimestamp(ts)
    for mid in PLACE_HOOKS:
        m = app.modules.get(mid)
        if m is None or not app.is_on(mid) or not hasattr(m, "place_event"):
            continue
        try:
            m.place_event(label, event, t)
        except Exception as e:
            app.events.emit("senses_failed", part=f"places:{mid}", error=f"{type(e).__name__}"[:80])


# ---------------------------------------------- (0.9.0) what the phone says now, for holds (core/availability.py)
FRESH_S = 15 * 60  # a reading older than this says nothing about now


def _last(app: App, sensor: str) -> dict | None:
    if not enabled(app, sensor):
        return None
    rows = store.events(app, f"phone:{sensor}", time.time() - FRESH_S)
    return rows[-1] if rows else None


def dnd_on(app: App) -> bool:
    """The phone's Do Not Disturb is on, by its last reading of the last 15 minutes. Used here only, as a hold."""
    r = _last(app, "dnd")
    return bool(r and r["n"] > 0)


def next_alarm(app: App) -> float | None:
    """The phone's own next alarm (time.time()), from its last reading of the last day; None when unknown."""
    if not enabled(app, "alarm"):
        return None
    rows = store.events(app, "phone:alarm", time.time() - 86400)
    if not rows or rows[-1]["n"] <= 0:
        return None
    at = float(rows[-1]["n"])
    return at / 1000 if at > 1e11 else at  # the phone says milliseconds


def _picked_up(b: dict) -> bool:
    """A screen bin from the last 10 minutes with the phone in use."""
    t = b.get("t")
    if b.get("s") != "screen" or isinstance(t, bool) or not isinstance(t, (int, float)):
        return False
    used = any(isinstance(b.get(f), (int, float)) and b.get(f) > 0 for f in ("unlocks", "on_min"))
    return used and abs(time.time() - t / 1000) <= 600


MOVING_FRESH_S = 600  # (0.9.0) a motion bin this old or newer still says how the phone is moving


def moving(app: App, now: float | None = None) -> str:
    """(0.9.0, calls.mode_when_moving) "walking" or "vehicle" when the phone's newest motion bin (from the last
    MOVING_FRESH_S) says so, else "". Read here only, to pick a call's voice mode and as an availability hold
    (calls.hold_moving); never told to an AI (R7)."""
    if not enabled(app, "motion"):
        return ""
    t = now or time.time()
    rows = [r for r in store.events(app, "phone:motion", t - MOVING_FRESH_S) if r.get("t", 0) <= t + 60]
    if not rows:
        return ""
    last = max(rows, key=lambda r: r.get("t", 0))
    kind = str(last.get("target") or last.get("kind") or "")
    return kind if kind in ("walking", "vehicle") else ""


def today(app: App, sensor: str) -> str:
    rows = store.events(app, f"phone:{sensor}", store.day_start())
    if not rows:
        return "nothing today"
    if sensor == "steps":
        return f"{int(max(r['n'] for r in rows))} steps"
    if sensor in ("screen", "usage", "motion"):
        tot: dict[str, float] = {}
        for r in rows:
            tot[r["target"] or r["kind"]] = tot.get(r["target"] or r["kind"], 0) + r["n"]
        return ", ".join(f"{k} {int(v)}" for k, v in tot.items())
    return f"{len(rows)} reading(s), last {time.strftime('%H:%M', time.localtime(rows[-1]['t']))}"


def label_wifi(app: App, wid: str, name: str) -> bool:
    """You say what a network code is ("home", "campus", "lab") once; it is only a label for the code."""
    from kurooto.core.state import jload, jsave

    if not HASH.match(wid) or not LABEL.match(name):
        return False
    f = app.paths.state / "mind-senses" / "wifi.json"
    d = jload(f, {}) or {}
    d[wid] = name
    f.parent.mkdir(parents=True, exist_ok=True)
    jsave(f, d)
    return True


def wifi_label(app: App, wid: str) -> str:
    from kurooto.core.state import jload

    return (jload(app.paths.state / "mind-senses" / "wifi.json", {}) or {}).get(wid, "")

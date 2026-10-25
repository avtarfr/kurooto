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
    app.events.emit("senses_phone", kept=kept, dropped=dropped)
    return 200, {"ok": True, "kept": kept}


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

"""The tone of what you write (Brain, 0.8.0 stage 04, shadow mode, off by default: `mind.tone.on`): one word per
message, from the model on this computer and nowhere else. A cloud AI never sees a tone tag or a read; from
stage 05 at most a hint ("keep it short") reaches it, never the tag.

    calm  tired  stressed  annoyed  upbeat  neutral  (a fixed prompt, about 100 tokens in, 3 out)

Three tiers, by what this computer has (core/hardware.py profile, the helper model, the battery):
    gpu    each message is tagged as it comes (on a thread of its own)
    cpu    messages wait in memory (never on disk) and are tagged once an hour
    none   no local model, or 8 GB or less on battery: no tone; /mood says "statistics only"

What's kept: the tags of the day, as numbers in `<state>/mind-tone.json`, dropped at the end of the day after the day's
mean (-1 stretched ... +1 upbeat) went to the scorekeeper as `tone_mean`. The words of a message are never written
anywhere
by this, and a message that waits for the hourly batch lives in memory only (a restart forgets it).
"""

from __future__ import annotations

import datetime as dt
import json
import threading
from typing import TYPE_CHECKING

from kurooto import mind
from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave

if TYPE_CHECKING:
    from kurooto.app import App

PART = "tone"  # its switch: mind.tone.on

register_defaults(
    "mind",
    {
        "tone": {
            "on": False,  # tag each message you write with one word, with the model on this computer only
            "calls": True,  # (0.9.0) with that on, what you said on a call is tagged too (words never kept)
        },
        "read": {
            "on": True,  # Brain's read of how you're doing, from numbers about your days (it only watches for now)
            "asks_per_week": 2,  # the most times a week it asks whether the week felt heavier than usual
        },
        "forecast": {
            "on": True,  # each evening at 21:00, what Brain expects of tomorrow, scored the next evening (shadow mode)
            "holdout": 0.10,  # the share of days a planned action is withheld on purpose, to measure what it does
        },
    },
)

TAGS = ("calm", "tired", "stressed", "annoyed", "upbeat", "neutral")
VALUE = {"upbeat": 1.0, "calm": 0.5, "neutral": 0.0, "tired": -0.5, "annoyed": -0.8, "stressed": -1.0}
PROMPT = (
    "Tone of this message in one word, one of: calm, tired, stressed, annoyed, upbeat, neutral.\nMessage: {text}\nTone:"
)
FILE = "mind-tone.json"
TEXT_MAX = 400  # characters sent to the local model
WAIT_MAX = 200  # messages waiting for the hourly batch (memory only)
_lock = threading.Lock()
_waiting: list[str] = []


def _day() -> str:
    d = now().date()
    if now().hour < 4:
        d -= dt.timedelta(days=1)
    return d.isoformat()


def model(app: App) -> str | None:
    """The helper model on this computer, if Local AI models is on and has one (no gist setting needed here)."""
    if not app.is_on("local_models"):
        return None
    lm = app.modules.get("local_models")
    try:
        have = lm.have()
        helpers = [m["tag"] for m in lm.wanted() if str(m.get("key", "")).startswith("helper")]
    except Exception:
        return None
    return next((t for t in helpers if t in have), None)


def tier(app: App) -> str:
    """gpu, cpu or none (see above)."""
    if not mind.part_on(app, "tone") or model(app) is None:
        return "none"
    try:
        from kurooto.core import hardware

        m = hardware.detect()
        prof = hardware.profile(m)
        battery = not app.power.on_ac()
    except Exception:
        return "none"
    if m.ram_gb <= 8 and battery:
        return "none"
    return "gpu" if prof in ("small-gpu", "big-gpu", "big-gpu-12") or prof.startswith("apple") else "cpu"


def tag(app: App, text: str) -> str | None:
    """One tag for one message, from the local model; None when it can't say."""
    mdl = model(app)
    if not mdl:
        return None
    body = {
        "model": mdl,
        "prompt": PROMPT.format(text=" ".join(text.split())[:TEXT_MAX]),
        "stream": False,
        "think": False,
        "options": {"temperature": 0, "num_predict": 3},
    }
    try:
        with app.modules["local_models"].api("/api/generate", body, timeout=60) as r:
            said = str(json.loads(r.read()).get("response", "")).strip().lower()
    except Exception:
        return None
    return next((t for t in TAGS if said.startswith(t)), None)


def _add(app: App, t: str) -> None:
    with _lock:
        d = jload(app.paths.state / FILE, {}) or {}
        if d.get("day") != _day():
            d = {"day": _day(), "tags": []}
        d["tags"].append(VALUE[t])
        jsave(app.paths.state / FILE, d)


def seen(app: App, text: str) -> None:
    """A message from you arrived (App.handle). gpu: tagged now, on a thread; cpu: kept in memory for the hour; else
    nothing.
    Never raises, never writes the words."""
    try:
        if not text or text.startswith("/"):
            return
        k = tier(app)
        if k == "gpu":
            threading.Thread(target=lambda: _one(app, text), name="mind-tone", daemon=True).start()
        elif k == "cpu":
            with _lock:
                _waiting.append(text)
                del _waiting[:-WAIT_MAX]
    except Exception:
        pass


def from_call(app: App, lines: list[dict]) -> int:
    """(0.9.0, mind.tone.calls) What you said on a call (Calls.save_transcript), each line as a message would be: same
    tiers, same local model, nothing kept but the day's numbers. Kurooto's own lines and "(note)" lines are left out.
    How many lines were handed on (0 with the switch, or tone, off)."""
    try:
        if not app.settings.get("mind.tone.calls") or tier(app) not in ("gpu", "cpu"):
            return 0
        yours = [str(x.get("text") or "").strip() for x in lines if x.get("who") not in (app.name, "(note)")]
        yours = [t for t in yours if t][:WAIT_MAX]
        for t in yours:
            seen(app, t)
        return len(yours)
    except Exception:
        return 0


def _one(app: App, text: str) -> None:
    t = tag(app, text)
    if t:
        _add(app, t)


def batch(app: App, payload: dict | None = None) -> int:
    """The hourly job on the cpu tier: tag what waited. How many."""
    if tier(app) != "cpu":
        with _lock:
            _waiting.clear()
        return 0
    with _lock:
        texts, _waiting[:] = list(_waiting), []
    n = 0
    for x in texts:
        t = tag(app, x)
        if t:
            _add(app, t)
            n += 1
    return n


def daily_mean(app: App, day: dt.date) -> float | None:
    """The mean tone of that day so far, from the tags kept for it; None when there are none."""
    d = jload(app.paths.state / FILE, {}) or {}
    tags = d.get("tags") or []
    if d.get("day") != day.isoformat() or not tags:
        return None
    return round(sum(tags) / len(tags), 3)


def roll(app: App, payload: dict | None = None) -> bool:
    """The end of the day: tags of an earlier day are dropped (their mean already went to the scorekeeper)."""
    f = app.paths.state / FILE
    d = jload(f, {}) or {}
    if d and d.get("day") != _day():
        f.unlink(missing_ok=True)
        return True
    return False


def forget(app: App) -> None:
    """Delete the tags and what waits (Forget this, turning the read off, turning Brain off)."""
    (app.paths.state / FILE).unlink(missing_ok=True)
    with _lock:
        _waiting.clear()

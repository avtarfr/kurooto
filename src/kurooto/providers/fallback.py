"""When an AI hits its limit, another one answers: Claude Code to agy, agy to Claude Code, either to a Gemini key.

Settings (brain.*):
    fallback        "" | "agy" | ["agy", "gemini"]: the AIs that take over, in order. One you pick (a name, or a list
                    of names; a single string from older settings still works) takes over on any failure, as before.
                    Empty: at a limit (fallback_on) the automatic order AUTO takes over: the other agent program
                    (agy or Claude Code), then a Gemini key if you saved one; the AI that failed and any that isn't set
                    up here (an agent program that hasn't answered here yet, an API brain without its key) are left
                    out. This is the one list that holds the order (the nightly policy look may tune it); there's no
                    other order setting.
    fallback_on     ["rate_limited"]: what moves a request on to the automatic order (and, for an AI you picked, a
                    timeout too): rate_limited (a usage limit: Claude's 5-hour window or weekly cap, agy's day),
                    auth (signed out), timeout. [] turns the automatic order off.

The limited AI is then skipped until its limit resets: the time it said ("resets 3pm", Google's retry hint; a minute for
a per-minute limit), else a back-off (30 min, doubling each time it's still limited, at most 5 hours), so later
requests go straight to the other one. An answer from it clears that early. Only when every AI is waiting is the
limited one tried anyway.
State: <state>/brain-limits.json ({brain: {until, src, hits, at}}); events brain_limited, brain_back.
"""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING

from kurooto.core.config import register_defaults
from kurooto.core.state import jload, jsave

if TYPE_CHECKING:
    from kurooto.app import App
    from kurooto.providers.base import Brain, Result

register_defaults(
    "brain",
    {
        "fallback_on": ["rate_limited"],  # what hands a request to the next AI: rate_limited, auth, timeout
    },
)

AUTO = ("agy", "claude", "gemini")  # with brain.fallback empty: who takes over at a limit, in this order
ON = ("rate_limited", "auth", "timeout")
FILE = "brain-limits.json"
BACKOFF_S = 30 * 60  # the first back-off when the limit doesn't say when it resets
MAX_BACKOFF_S = 5 * 3600  # Claude's window: never longer than this without a reset time
NAMES = {"agy": "agy", "claude": "Claude Code", "gemini": "your Gemini key", "ollama": "Ollama", "custom": "your AI"}
_lock = threading.Lock()


def name(bid: str) -> str:
    return NAMES.get(bid, bid)


def chosen(app: App) -> list[str]:
    """brain.fallback as a list of brain ids: the AIs you picked to take over ("" or [] = none; a single string from
    older settings is a list of one)."""
    v = app.settings.get("brain.fallback")
    if isinstance(v, str):
        v = [x.strip() for x in v.replace(",", " ").split()]
    return [str(x).strip() for x in v or [] if str(x).strip()] if isinstance(v, (list, tuple)) else []


def order(app: App) -> list[str]:
    """Who takes over, in order: the AIs you picked (brain.fallback), else the automatic order (AUTO)."""
    return chosen(app) or list(AUTO)


def triggers(app: App) -> set[str]:
    """brain.fallback_on: the verdicts that hand a request to the next AI in the order."""
    v = app.settings.get("brain.fallback_on")
    if isinstance(v, str):
        v = [v]
    got = {str(x).strip().lower() for x in v or []} & set(ON) if isinstance(v, (list, tuple, str)) else set()
    return got


def ready(app: App, bid: str) -> Brain | None:
    """The brain, built, when it's set up here: an agent program that is installed and has answered here before; an
    API brain with its key and model."""
    from kurooto import providers

    try:
        b = providers.build(app, bid)
    except Exception:
        return None
    if b is None or not b.available()[0]:
        return None
    if b.kind == "cli" and not b.has_worked(app):
        return None
    return b


def candidates(app: App, skip: set[str]) -> list[Brain]:
    """The AIs that take over, in order(), leaving out `skip` and any that isn't set up here."""
    out = []
    for bid in order(app):
        if bid in skip:
            continue
        b = ready(app, bid)
        if b is not None:
            out.append(b)
            skip = skip | {bid}
    return out


# ------------------------------------------------------------------------------------------- waiting for a reset
def _file(app: App):
    return app.paths.state / FILE


def _load(app: App) -> dict:
    d = jload(_file(app), {}) or {}
    return d if isinstance(d, dict) else {}


def reset_of(result: Result, now: float) -> float | None:
    """When a limit comes back, if the AI said: its retry time, or the reset in Google's or Claude's message."""
    hint = (result.usage or {}).get("limit") if isinstance(result.usage, dict) else None
    hint = hint if isinstance(hint, dict) else {}
    if hint.get("reset_at"):
        return float(hint["reset_at"])
    if result.retry_after_s:
        return now + float(result.retry_after_s)
    if hint.get("retry_s"):
        return now + float(hint["retry_s"])
    return None


def cool(app: App, bid: str, result: Result, now: float | None = None) -> float:
    """An AI hit its limit: it's skipped until the reset it named, else for a back-off that doubles while it stays
    limited. Returns the time it's skipped until."""
    now = time.time() if now is None else now
    at = reset_of(result, now)
    with _lock:
        d = _load(app)
        rec = d.get(bid) if isinstance(d.get(bid), dict) else {}
        hits = int(rec.get("hits") or 0) + 1 if float(rec.get("until") or 0) > now - MAX_BACKOFF_S else 1
        per = ((result.usage or {}).get("limit") or {}).get("per") if isinstance(result.usage, dict) else None
        if at is not None and at > now:
            until, src = at, "said"
        elif per == "minute":  # a per-minute limit (Google's) passes by itself
            until, src = now + 60, "minute"
        else:
            until, src = now + min(BACKOFF_S * 2 ** (hits - 1), MAX_BACKOFF_S), "backoff"
        d[bid] = {"until": until, "src": src, "hits": hits, "at": now}
        jsave(_file(app), d)
    app.events.emit("brain_limited", brain=bid, until=round(until), src=src)
    return until


def cooling(app: App, bid: str, now: float | None = None) -> float | None:
    """Until when this AI is skipped for a limit, or None."""
    now = time.time() if now is None else now
    rec = _load(app).get(bid)
    until = float(rec.get("until") or 0) if isinstance(rec, dict) else 0
    return until if until > now else None


def clear(app: App, bid: str) -> None:
    """It answered: it isn't waiting for a reset any more."""
    with _lock:
        d = _load(app)
        if bid not in d:
            return
        d.pop(bid)
        jsave(_file(app), d)
    app.events.emit("brain_back", brain=bid)


def status(app: App, now: float | None = None) -> dict[str, dict]:
    """Every AI skipped for a limit right now: {brain: {until, src}}."""
    now = time.time() if now is None else now
    return {
        k: {"until": v.get("until"), "src": v.get("src")}
        for k, v in _load(app).items()
        if isinstance(v, dict) and float(v.get("until") or 0) > now
    }


def skip_cooling(app: App, chain: list, now: float | None = None) -> tuple[list, list[tuple]]:
    """The chain without the AIs waiting for a limit's reset, and those left out ((brain, until), in order). When every
    one is waiting, nothing is left out: the limit may have come back early."""
    now = time.time() if now is None else now
    out, skipped = [], []
    for b in chain:
        until = cooling(app, b.id, now)
        if until is None:
            out.append(b)
        else:
            skipped.append((b, until))
    return (out, skipped) if out else (list(chain), [])

"""The AI brains Kurooto can use, and which one handles what.

Settings:
    brain.main       agy | claude | gemini | ollama | custom   (freellmapi: set up earlier, works as custom)
    brain.fallback   another of those, or a list of them in order, used when the main one can't answer ("": at a
                     limit, the other agent program then a Gemini key; providers/fallback.py, with brain.fallback_on)
    brain.classify   rules | main | ollama   (the quick "how hard is this" question)
    brain.effort_map      what Dreaming tuned: the effort your requests get per origin (providers/effort.py)
    brain.fallback_first  what Dreaming tuned: effort levels at which the fallback is tried before the main AI
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from kurooto.core.config import register_defaults
from kurooto.providers import fallback as fallback  # brain.fallback's order and fallback_on
from kurooto.providers.agy import Agy
from kurooto.providers.base import Brain, Result, Task, Verdict
from kurooto.providers.claude import ClaudeCode
from kurooto.providers.openai_compat import PRESETS, OpenAICompat

if TYPE_CHECKING:
    from kurooto.app import App

__all__ = ["Brain", "Result", "Task", "Verdict", "build", "local", "CHOICES", "drop_retired"]

register_defaults(
    "brain",
    {
        "main": "",
        "fallback": "",
        "classify": "rules",
        "agy": {"io_mode": "pipe"},
        "models": {},  # per brain: {"custom": {"low": ..., "medium": ..., "high": ...}}
        "base_urls": {},  # per brain, to override a preset's address
        "timeout_min": {"low": 10, "medium": 15, "high": 30},
        "effort_map": {},  # tuned while dreaming: {"low": "medium"} runs your requests rated low at medium effort
        "fallback_first": [],  # tuned while dreaming: effort levels ("high") at which your first fallback AI goes first
    },
)

CHOICES = {
    "agy": Agy.label,
    **{k: v["label"] for k, v in PRESETS.items()},
    "claude": ClaudeCode.label,
}


AGENT_PROGRAMS = ("agy", "claude")  # the AI programs that run a request with tools of their own, in order of preference
RETIRED = {"codex": "Codex"}  # AIs Kurooto no longer offers: a setting that names one is cleared (drop_retired)


def drop_retired(app: App) -> list[str]:
    """Clear brain.main / brain.fallback if they name an AI Kurooto no longer offers; the next request then says to
    choose another in Settings → AI. Returns what it cleared."""
    cleared = []
    for key in ("brain.main", "brain.fallback"):
        old = app.settings.get(key) or ""
        if isinstance(old, list):  # a list of fallbacks: only the retired ones go
            gone = [x for x in old if x in RETIRED]
            if gone:
                app.settings.set(key, [x for x in old if x not in RETIRED])
                cleared += gone
                for g in gone:
                    app.events.emit("brain_retired", brain=g, setting=key)
            continue
        if old in RETIRED:
            app.settings.set(key, "")
            cleared.append(old)
            app.events.emit("brain_retired", brain=old, setting=key)
    return cleared


def build(app: App, which: str) -> Brain | None:
    brain = _build(app, which)
    quota = getattr(app, "quota", None)
    if brain is not None and quota is not None:  # each request counts against its free limit (core/quota.py)
        brain.meter = lambda model, result: quota.count(brain, model, result)
    return brain


def local(app: App) -> Brain | None:
    """The model on this computer (Ollama, set up by Local AI models or as a brain), when there is one: quick decisions,
    and background work while a free limit is kept for you (core/quota.py)."""
    if not ((app.settings.get("brain.models") or {}).get("ollama") or {}).get("medium"):
        return None
    brain = build(app, "ollama")
    return brain if brain is not None and brain.available()[0] else None


def _build(app: App, which: str) -> Brain | None:
    if not which:
        return None
    s = app.settings
    if which == "agy":
        return Agy(io_mode=s.get("brain.agy.io_mode") or "pipe", models=s.get("brain.models.agy") or None)
    if which == "claude":
        return ClaudeCode(models=(s.get("brain.models") or {}).get("claude"), app=app)
    if which in PRESETS:
        return OpenAICompat(
            which,
            app.secrets.get(f"{which}.api_key"),
            base_url=(s.get("brain.base_urls") or {}).get(which),
            models=(s.get("brain.models") or {}).get(which),
        )
    return None

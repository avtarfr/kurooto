"""The AI brains Kurooto can use, and which one handles what.

Settings:
    brain.main       agy | codex | gemini | ollama | custom | claude   (freellmapi: set up earlier, works as custom)
    brain.fallback   another of those, used when the main one is rate-limited or signed out ("" = none)
    brain.classify   rules | main | ollama   (the quick "how hard is this" question)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from kurooto.core.config import register_defaults
from kurooto.providers.agy import Agy
from kurooto.providers.base import Brain, Result, Task, Verdict
from kurooto.providers.cli_agents import ClaudeCode, Codex
from kurooto.providers.openai_compat import PRESETS, OpenAICompat

if TYPE_CHECKING:
    from kurooto.app import App

__all__ = ["Brain", "Result", "Task", "Verdict", "build", "CHOICES"]

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
    },
)

CHOICES = {
    "agy": Agy.label,
    "codex": Codex.label,
    **{k: v["label"] for k, v in PRESETS.items()},
    "claude": ClaudeCode.label,
}


def build(app: App, which: str) -> Brain | None:
    if not which:
        return None
    s = app.settings
    if which == "agy":
        return Agy(io_mode=s.get("brain.agy.io_mode") or "pipe", models=s.get("brain.models.agy") or None)
    if which == "codex":
        return Codex(app.paths.app, models=(s.get("brain.models") or {}).get("codex"))
    if which == "claude":
        return ClaudeCode(models=(s.get("brain.models") or {}).get("claude"))
    if which in PRESETS:
        return OpenAICompat(
            which,
            app.secrets.get(f"{which}.api_key"),
            base_url=(s.get("brain.base_urls") or {}).get(which),
            models=(s.get("brain.models") or {}).get(which),
        )
    return None

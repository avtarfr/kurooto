"""The AI brains Kurooto can use, and which one handles what.

Settings:
    brain.main       agy | claude | gemini | ollama | custom   (freellmapi: set up earlier, works as custom), or an
                     extra Claude account "claude:<key>" (providers/claude_accounts.py)
    brain.fallback   another of those, or a list of them in order, used when the main one can't answer ("": at a
                     limit, the other agent program then a Gemini key; providers/fallback.py, with brain.fallback_on)
    brain.classify   rules | main | ollama   (the quick "how hard is this" question)
    brain.effort_map      what Dreaming tuned: the effort your requests get per origin (providers/effort.py)
    brain.fallback_first  what Dreaming tuned: effort levels at which the fallback is tried before the main AI
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from kurooto.core.config import register_defaults
from kurooto.providers import claude_accounts as claude_accounts  # extra Claude accounts ("claude:work")
from kurooto.providers import fallback as fallback  # brain.fallback's order and fallback_on
from kurooto.providers.agy import Agy
from kurooto.providers.base import Brain, Result, Task, Verdict
from kurooto.providers.claude import ClaudeCode
from kurooto.providers.openai_compat import PRESETS, OpenAICompat

if TYPE_CHECKING:
    from kurooto.app import App

__all__ = [
    "Brain",
    "Result",
    "Task",
    "Verdict",
    "build",
    "local",
    "sees",
    "CHOICES",
    "drop_retired",
    "label",
    "choices",
]

register_defaults(
    "brain",
    {
        "main": "",
        "fallback": "",
        "classify": "rules",
        "agy": {"io_mode": "pipe"},
        "claude": {"session": True, "session_idle_min": 10},  # (0.8.17) a conversation's Claude Code kept running
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


def label(bid: str | None, default: str | None = None) -> str:
    """An AI's name to show: CHOICES' ("Claude Code"), an extra Claude account's ("Claude Code (work)"), else the
    default (the id itself when none is given)."""
    bid = bid or ""
    if bid in CHOICES:
        return CHOICES[bid]
    if claude_accounts.is_id(bid):
        return claude_accounts.label(bid)
    return bid if default is None else default


def choices(app: App) -> dict[str, str]:
    """Every AI that can be picked here, id -> name: CHOICES, with your extra Claude accounts after Claude Code."""
    out: dict[str, str] = {}
    for k, v in CHOICES.items():
        out[k] = v
        if k == "claude":
            out.update({a.id: a.label for a in claude_accounts.accounts(app)})
    return out


def agent_programs(app: App) -> list[str]:
    """AGENT_PROGRAMS with your extra Claude accounts after Claude Code."""
    out: list[str] = []
    for k in AGENT_PROGRAMS:
        out.append(k)
        if k == "claude":
            out += claude_accounts.ids(app)
    return out


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


def sees(app: App) -> tuple[bool | None, str]:
    """Can the AI you picked (brain.main) read pictures? (True, ""), (False, what to do) or (None, a caution):
    agy, Claude Code and a Gemini key do; Ollama when its model does; another service is tried."""
    main = app.settings.get("brain.main") or ""
    brain = build(app, main)
    if brain is None:
        return False, "Pick an AI first (dashboard → Settings → AI)."
    ok, why = brain.sees()
    if ok is False:
        return False, (
            f"Your AI ({label(main)}) can't read pictures: {why}. Pick one that can in Settings → AI "
            "(agy, Claude Code, a Gemini key, or an Ollama model that reads pictures, like gemma3)."
        )
    return ok, why


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
    if claude_accounts.is_id(which):  # an extra Claude account: its own folder, its models or Claude Code's
        acc = claude_accounts.get(app, which)
        if acc is None:
            return None
        models = s.get("brain.models") or {}
        return ClaudeCode(
            models=models.get(which) or models.get("claude"),
            app=app,
            account=acc.key,
            name=acc.name,
            config_dir=claude_accounts.folder(app, acc.key),
        )
    if which in PRESETS:
        return OpenAICompat(
            which,
            app.secrets.get(f"{which}.api_key"),
            base_url=(s.get("brain.base_urls") or {}).get(which),
            models=(s.get("brain.models") or {}).get(which),
        )
    return None

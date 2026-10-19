"""Settings: defaults registered by each module, with the user's changes in config/settings.json on top.

Only the user's own changes are stored, so new defaults in an update reach everyone who hasn't changed that
setting. Keys are dotted: get("checkins.evening"), set("checkins.evening", "21:30").
"""

from __future__ import annotations

import copy
from pathlib import Path

from kurooto.core.state import jload, jsave

_DEFAULTS: dict = {}


def merge(base: dict, over: dict | None) -> dict:
    """A deep copy of `base` with `over` laid on top; nested dicts merge, anything else replaces."""
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        out[k] = merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else copy.deepcopy(v)
    return out


# your add-ons' settings.json (core/overlay.py): defaults laid between Kurooto's own and yours
_LAYER: dict = {}


def set_layer(defaults: dict | None) -> None:
    """Defaults from your add-ons folder: over the registered ones, under your own settings."""
    _LAYER.clear()
    _LAYER.update(copy.deepcopy(defaults or {}))


def register_defaults(section: str, defaults: dict) -> None:
    """A module declares its settings and their defaults under its own section."""
    _DEFAULTS[section] = merge(_DEFAULTS.get(section, {}), defaults)


class Settings:
    def __init__(self, file: Path):
        self.file = Path(file)

    def user(self) -> dict:
        return jload(self.file, {}) or {}

    def all(self) -> dict:
        return merge(merge(_DEFAULTS, _LAYER) if _LAYER else _DEFAULTS, self.user())

    def get(self, dotted: str, default=None):
        cur = self.all()
        for k in dotted.split("."):
            if not isinstance(cur, dict) or k not in cur:
                return default
            cur = cur[k]
        return cur

    def set(self, dotted: str, value):
        """Change one setting and return its previous value."""
        old = self.get(dotted)
        raw = self.user()
        cur = raw
        keys = dotted.split(".")
        for k in keys[:-1]:
            nxt = cur.get(k)
            if not isinstance(nxt, dict):
                nxt = cur[k] = {}
            cur = nxt
        cur[keys[-1]] = value
        jsave(self.file, raw)
        return old

    def reset(self, dotted: str) -> None:
        """Drop the user's value so the default applies again."""
        raw = self.user()
        cur = raw
        keys = dotted.split(".")
        for k in keys[:-1]:
            cur = cur.get(k)
            if not isinstance(cur, dict):
                return
        if keys[-1] in cur:
            del cur[keys[-1]]
            jsave(self.file, raw)

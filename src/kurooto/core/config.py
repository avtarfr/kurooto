"""Settings: defaults registered by each module, with the user's changes in config/settings.json on top.

Only the user's own changes are stored, so new defaults in an update reach everyone who hasn't changed that
setting. Keys are dotted: get("checkins.evening"), set("checkins.evening", "21:30").
"""

from __future__ import annotations

import copy
import os
from pathlib import Path

from kurooto.core.state import jload, jsave

_DEFAULTS: dict = {}


def _copy(x):
    """A deep copy of a settings value: dicts, lists and plain values the quick way (copy.deepcopy took most of a
    dashboard request's time, 0.6.1), anything else through copy.deepcopy."""
    t = type(x)
    if t is dict:
        return {k: _copy(v) for k, v in x.items()}
    if t is list:
        return [_copy(v) for v in x]
    if x is None or t in (str, int, float, bool):
        return x
    return copy.deepcopy(x)


def merge(base: dict, over: dict | None) -> dict:
    """A deep copy of `base` with `over` laid on top; nested dicts merge, anything else replaces."""
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        out[k] = merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else copy.deepcopy(v)
    return out


# your add-ons' settings.json (core/overlay.py): defaults laid between Kurooto's own and yours
_LAYER: dict = {}
# bumped whenever the defaults or the layer change, so every Settings' cached merge is made again
_GEN = [0]


def set_layer(defaults: dict | None) -> None:
    """Defaults from your add-ons folder: over the registered ones, under your own settings."""
    _LAYER.clear()
    _LAYER.update(copy.deepcopy(defaults or {}))
    _GEN[0] += 1


def register_defaults(section: str, defaults: dict) -> None:
    """A module declares its settings and their defaults under its own section."""
    _DEFAULTS[section] = merge(_DEFAULTS.get(section, {}), defaults)
    _GEN[0] += 1


class Settings:
    def __init__(self, file: Path):
        self.file = Path(file)
        # the merged settings and what they were made from: ((file's mtime, size, inode, _GEN), tree). Merging copies
        # every default, and a dashboard request asks for settings a thousand times or more (0.6.1: 10 s a request).
        self._cache: tuple | None = None

    def user(self) -> dict:
        return jload(self.file, {}) or {}

    def _merged(self) -> dict:
        """The merged tree, made again only when the file (changed here, by the CLI or by hand) or the defaults
        changed. Shared: never hand it out, only copies of its parts."""
        try:
            st = os.stat(self.file)
            key = (st.st_mtime_ns, st.st_size, st.st_ino, _GEN[0])
        except OSError:
            key = (None, None, None, _GEN[0])
        c = self._cache
        if c is not None and c[0] == key:
            return c[1]
        tree = merge(merge(_DEFAULTS, _LAYER) if _LAYER else _DEFAULTS, self.user())
        self._cache = (key, tree)
        return tree

    def all(self) -> dict:
        return _copy(self._merged())

    def get(self, dotted: str, default=None):
        cur = self._merged()
        for k in dotted.split("."):
            if not isinstance(cur, dict) or k not in cur:
                return default
            cur = cur[k]
        return _copy(cur) if isinstance(cur, (dict, list)) else cur  # the caller may change what it gets

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
        self._cache = None
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
            self._cache = None

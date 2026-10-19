"""Where Kurooto keeps things, following each OS's conventions.

    Windows   %LOCALAPPDATA%\\Kurooto\\{config,data,state,cache}    app: %LOCALAPPDATA%\\Programs\\Kurooto
    macOS     ~/Library/Application Support/Kurooto/{config,data,state,app}, ~/Library/Caches/Kurooto,
              logs in ~/Library/Logs/Kurooto
    Linux     $XDG_CONFIG_HOME/kurooto, $XDG_DATA_HOME/kurooto/data, $XDG_STATE_HOME/kurooto, $XDG_CACHE_HOME/kurooto,
              app: $XDG_DATA_HOME/kurooto/app

KUROOTO_HOME=<folder> puts everything under one folder (tests, portable installs).
"""

from __future__ import annotations

import os
import posixpath
import sys
from dataclasses import dataclass, fields
from pathlib import Path


@dataclass(frozen=True)
class Paths:
    config: Path  # settings.json and the secrets fallback file
    data: Path  # databases and the default workspace
    state: Path  # jobs, locks, wizard progress
    logs: Path
    cache: Path  # downloads; safe to delete
    app: Path  # installed versions and the launcher

    def ensure(self) -> Paths:
        for f in fields(self):
            getattr(self, f.name).mkdir(parents=True, exist_ok=True)
        return self


def paths(platform: str | None = None, env: dict | None = None, home: Path | None = None) -> Paths:
    """The folders for this machine. The arguments exist for tests."""
    platform = platform or sys.platform
    env = os.environ if env is None else env
    home = home or Path.home()

    root = env.get("KUROOTO_HOME")
    if root:
        r = Path(root)
        return Paths(r / "config", r / "data", r / "state", r / "state" / "logs", r / "cache", r / "app")

    if platform == "win32":
        local = Path(env.get("LOCALAPPDATA") or home / "AppData" / "Local")
        base = local / "Kurooto"
        return Paths(
            base / "config",
            base / "data",
            base / "state",
            base / "state" / "logs",
            base / "cache",
            local / "Programs" / "Kurooto",
        )

    if platform == "darwin":
        lib = home / "Library"
        base = lib / "Application Support" / "Kurooto"
        return Paths(
            base / "config",
            base / "data",
            base / "state",
            lib / "Logs" / "Kurooto",
            lib / "Caches" / "Kurooto",
            base / "app",
        )

    def xdg(name: str, default: Path) -> Path:
        v = env.get(name)
        return Path(v) if v and posixpath.isabs(v) else default  # XDG paths are POSIX paths

    data_home = xdg("XDG_DATA_HOME", home / ".local" / "share") / "kurooto"
    state = xdg("XDG_STATE_HOME", home / ".local" / "state") / "kurooto"
    return Paths(
        xdg("XDG_CONFIG_HOME", home / ".config") / "kurooto",
        data_home / "data",
        state,
        state / "logs",
        xdg("XDG_CACHE_HOME", home / ".cache") / "kurooto",
        data_home / "app",
    )

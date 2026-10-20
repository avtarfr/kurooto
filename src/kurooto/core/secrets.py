"""Secrets (bot tokens, API keys): the OS keychain when there is one, else a private file.

Windows Credential Manager and the macOS Keychain are used through `keyring`. On Linux without a keyring
service (common on servers and minimal desktops), and when KUROOTO_HOME is set (tests, portable installs), they
go to config/secrets.json with owner-only permissions instead. Starting from boot on Linux (core/autostart.py) keeps
them in that file too: the keychain stays locked until you log in.
"""

from __future__ import annotations

import os
from pathlib import Path

from kurooto.core.state import jload, jsave

SERVICE = "kurooto"


def _keyring():
    if os.environ.get("KUROOTO_HOME") or os.environ.get("KUROOTO_SECRETS") == "file":
        return None
    try:
        import keyring
        from keyring.backends import fail

        kr = keyring.get_keyring()
        if isinstance(kr, fail.Keyring) or "null" in type(kr).__name__.lower():
            return None
        return keyring
    except Exception:  # no backend, or it can't start
        return None


class Secrets:
    def __init__(self, config_dir: Path):
        self.file = Path(config_dir) / "secrets.json"
        self.in_file_marker = Path(config_dir) / "secrets-in-file"  # there: the file, not the keychain
        self._kr = _keyring()

    @property
    def kr(self):
        """The keychain, or None (no keychain here, or Kurooto keeps its secrets in its file)."""
        return None if self.in_file_marker.exists() else self._kr

    def keep_in_file(self, on: bool, names: list[str]) -> int:
        """on: copy these secrets from the keychain into the owner-only file and use the file from now on (the
        keychain's copies stay). off: back to the keychain, when there is one. Returns how many moved."""
        moved = 0
        if on:
            if self._kr is not None and not self.in_file_marker.exists():
                data = jload(self.file, {}) or {}
                for name in names:
                    try:
                        v = self._kr.get_password(SERVICE, name)
                    except Exception:
                        v = None
                    if v is not None:
                        data[name], moved = v, moved + 1
                jsave(self.file, data, mode=0o600)
            self.in_file_marker.write_text("Kurooto keeps its secrets in secrets.json (it starts from boot).\n")
            return moved
        if not self.in_file_marker.exists():
            return 0
        self.in_file_marker.unlink()
        if self._kr is None:
            return 0
        for name, v in (jload(self.file, {}) or {}).items():
            self.set(name, v)
            moved += name not in (jload(self.file, {}) or {})
        return moved

    def get(self, name: str) -> str | None:
        if self.kr:
            try:
                v = self.kr.get_password(SERVICE, name)
                if v is not None:
                    return v
            except Exception:
                pass
        return (jload(self.file, {}) or {}).get(name)

    def set(self, name: str, value: str) -> None:
        if self.kr:
            try:
                self.kr.set_password(SERVICE, name, value)
                self._drop_from_file(name)
                return
            except Exception:
                pass
        data = jload(self.file, {}) or {}
        data[name] = value
        jsave(self.file, data, mode=0o600)

    def delete(self, name: str) -> None:
        if self.kr:
            try:
                self.kr.delete_password(SERVICE, name)
            except Exception:
                pass
        self._drop_from_file(name)

    def names(self) -> list[str]:
        """Names stored in the file (the keychain can't be listed; modules know their own names)."""
        return sorted(jload(self.file, {}) or {})

    def _drop_from_file(self, name: str) -> None:
        data = jload(self.file, {}) or {}
        if name in data:
            del data[name]
            jsave(self.file, data, mode=0o600)

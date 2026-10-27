"""Biometric templates (0.8.10): the one place an enrolled voice print (Voice ID) or face template is kept, sealed.

Plumbing only, no model code. `BioStore(app, kind)` keeps one template per kind ("voice"; the face part can use
"face"): the file <state>/<kind>id/template.bin, AES-256-GCM sealed (a 12-byte random nonce per save, AAD
b"kurooto-biometric:<kind>:v1"), under a key held in the app's secrets as `biometric.<kind>.key` (the keychain where
there is one, the owner-only secrets file elsewhere; core/secrets.py), made on the first save and read back before
it's used, as core/ledger.py makes its key.

- `load()` is None when nothing is enrolled, and raises `Locked` when the file is there but the key can't be read or
  the file doesn't open with it (never a new key over an old template).
- `forget()` deletes the key first (what makes every old copy unreadable), then the file.
- Never in backups (modules/backups.py skips the folder and the key), profile sync (core/profile.py NEVER), the
  diagnostics bundle (the key's name is redacted; state files aren't bundled), logs, events or the live stream.

Honest limits: where the secrets live in the owner-only file (no keychain, Kurooto started from boot, KUROOTO_HOME
set), the key sits on the same disk as the template, so the seal protects only copies of the state folder made
without the config folder. On an SSD a deleted file's blocks may survive until they're reused; with the key gone they
are unreadable ciphertext. Python can't promise memory is zeroed or never swapped.

`note_others()` / `others_present()`: a small shared "someone else is here" signal, in memory only (no voices, no
faces): Voice ID notes a voice that isn't the owner's, a face part can note a second face, and Voice's conversation
mode reads it."""

from __future__ import annotations

import base64
import json
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from kurooto.core.lock import Lock

if TYPE_CHECKING:
    from kurooto.app import App

VERSION = 1


class Locked(Exception):
    """The template is there but can't be opened: its key can't be read (a locked keychain) or doesn't fit."""


def secret_name(kind: str) -> str:
    return f"biometric.{kind}.key"


BIOMETRIC_SECRETS = (secret_name("voice"), secret_name("face"))  # never backed up, synced or shown


class BioStore:
    def __init__(self, app: App | Any, kind: str):
        self.app = app
        self.kind = kind
        self.dir = Path(app.paths.state) / f"{kind}id"
        self.file = self.dir / "template.bin"
        self.key_name = secret_name(kind)
        self.aad = f"kurooto-biometric:{kind}:v1".encode()

    # --------------------------------------------------------------------------------------------- the key
    def _key(self, make: bool) -> bytes | None:
        v = self.app.secrets.get(self.key_name)
        if not v:
            if not make:
                return None
            if self.file.exists():  # never a new key over a template an older key sealed
                raise Locked("the key of your enrolled template can't be read")
            v = base64.b64encode(os.urandom(32)).decode()
            self.app.secrets.set(self.key_name, v)
            if self.app.secrets.get(self.key_name) != v:
                raise Locked("the key for your template couldn't be kept")
        try:
            k = base64.b64decode(v)
        except ValueError:
            k = b""
        if len(k) != 32:
            raise Locked("the key of your enrolled template isn't one")
        return k

    # ---------------------------------------------------------------------------------------------- use
    def exists(self) -> bool:
        return self.file.is_file()

    def seal(self, data: dict) -> bytes:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        key = self._key(make=True)
        nonce = os.urandom(12)
        raw = json.dumps({"v": VERSION, **data}, ensure_ascii=False, separators=(",", ":")).encode()
        return nonce + AESGCM(key).encrypt(nonce, raw, self.aad)

    def unseal(self, blob: bytes) -> dict:
        from cryptography.exceptions import InvalidTag
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        key = self._key(make=False)
        if key is None:
            raise Locked("the key of your enrolled template can't be read")
        try:
            out = json.loads(AESGCM(key).decrypt(blob[:12], blob[12:], self.aad))
        except (InvalidTag, ValueError) as e:
            raise Locked("your enrolled template doesn't open with its key (damaged, or from another key)") from e
        if not isinstance(out, dict):
            raise Locked("your enrolled template isn't one")
        return out

    def load(self) -> dict | None:
        """The template, or None when nothing is enrolled. Raises Locked when it's there but won't open."""
        try:
            blob = self.file.read_bytes()
        except FileNotFoundError:
            return None
        if len(blob) < 29:
            raise Locked("your enrolled template is damaged")
        return self.unseal(blob)

    def save(self, data: dict) -> None:
        with Lock(self.app.paths.state, f"biometric-{self.kind}", timeout=10):
            blob = self.seal(data)
            self.dir.mkdir(parents=True, exist_ok=True)
            try:
                os.chmod(self.dir, 0o700)
            except OSError:
                pass
            tmp = self.file.with_name(self.file.name + ".tmp")
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            try:
                with os.fdopen(fd, "wb") as f:
                    f.write(blob)
                os.replace(tmp, self.file)
            finally:
                tmp.unlink(missing_ok=True)
            try:
                os.chmod(self.file, 0o600)
            except OSError:
                pass

    def forget(self) -> bool:
        """Delete the key (first: that makes any copy unreadable), then the file. Whether anything was there."""
        had = self.exists() or bool(self.app.secrets.get(self.key_name))
        with Lock(self.app.paths.state, f"biometric-{self.kind}", timeout=10):
            self.app.secrets.delete(self.key_name)
            for f in (self.file, self.file.with_name(self.file.name + ".tmp")):
                f.unlink(missing_ok=True)
        return had


# ----------------------------------------------------------------------------- someone else is here (memory only)
_others: dict[int, float] = {}


def note_others(app: App | Any, seconds: float = 60) -> None:
    """Someone besides the owner is here (a voice that isn't his, a second face): for `seconds` from now."""
    _others[id(app)] = max(_others.get(id(app), 0.0), time.monotonic() + float(seconds))


def others_present(app: App | Any) -> bool:
    return time.monotonic() < _others.get(id(app), 0.0)

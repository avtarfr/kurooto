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
mode reads it.

Face presence (0.8.10) keeps its template in `TemplateStore(app, "face")` (<state>/face/template.bin, the secret
"face.key", a status file of counts and dates; forget() says what went), and the calibration both features share lives
here too: calibrate(genuine, impostor, far, z, floor) -> Thresholds, load_impostors(path, model_sha), the vector helpers
(dot, unit, mean_unit, pack, unpack) and npz_read / npz_write (numpy's .npz without numpy)."""

from __future__ import annotations

import ast
import base64
import io
import json
import math
import os
import struct
import time
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from kurooto.core.lock import Lock
from kurooto.core.state import jload, jsave

if TYPE_CHECKING:
    from kurooto.app import App

VERSION = 1


class Locked(Exception):
    """The template is there but can't be opened: its key can't be read (a locked keychain) or doesn't fit."""


def secret_name(kind: str) -> str:
    return f"biometric.{kind}.key"


BIOMETRIC_SECRETS = (secret_name("voice"), secret_name("face"), "face.key")  # never backed up, synced or shown
# ("face.key": Face presence's TemplateStore names its key after the feature)


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
    """A voice that isn't the owner's lately, or (Face presence, core/nearby.py) a second face at the desk."""
    if time.monotonic() < _others.get(id(app), 0.0):
        return True
    from kurooto.core import nearby

    try:
        return nearby.others(app)
    except Exception:
        return False


LO_FLOOR = 0.20  # T_lo never below this
LO_GAP = 0.10  # T_lo sits this far under T_hi: between them a face is "unsure" and counts for nothing


class TemplateStore:
    """Face presence's store (0.8.10): <state>/<feature>/template.bin under the secret "<feature>.key", with a
    status file of counts and dates. Voice ID uses BioStore above; both seal the same way (AES-256-GCM, a fresh
    nonce)."""

    def __init__(self, app: App, feature: str):
        self.app = app
        self.feature = feature
        self.dir = app.paths.state / feature
        self.file = self.dir / "template.bin"
        self.status_file = self.dir / f"{feature}.json"
        self.secret = f"{feature}.key"
        self.aad = f"kurooto-{feature}:template:v1".encode()
        self._key: bytes | None = None

    # ------------------------------------------------------------------------------------------------ the key
    def exists(self) -> bool:
        return self.file.is_file()

    def key(self) -> bytes:
        if self._key:
            return self._key
        with Lock(self.app.paths.state, f"{self.feature}-key", timeout=10):
            v = self.app.secrets.get(self.secret)
            if not v:
                if self.exists():
                    raise Locked(f"the {self.feature} template's key can't be read")
                v = base64.b64encode(os.urandom(32)).decode()
                self.app.secrets.set(self.secret, v)
                if self.app.secrets.get(self.secret) != v:
                    raise Locked(f"the {self.feature} template's key couldn't be kept")
        try:
            k = base64.b64decode(v)
        except ValueError:
            k = b""
        if len(k) != 32:
            raise Locked(f"the {self.feature} template's key isn't one")
        self._key = k
        return k

    def readable(self) -> bool:
        """The key can be read now (or none is needed yet)."""
        try:
            self.key()
            return True
        except Locked:
            return False

    # -------------------------------------------------------------------------------------------- sealing
    def seal(self, payload: dict) -> bytes:
        nonce = os.urandom(12)
        data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
        return nonce + AESGCM(self.key()).encrypt(nonce, data, self.aad)

    def unseal(self, blob: bytes) -> dict | None:
        if len(blob) < 29:
            return None
        try:
            raw = AESGCM(self.key()).decrypt(blob[:12], blob[12:], self.aad)
            out = json.loads(raw)
        except (InvalidTag, ValueError):
            return None
        return out if isinstance(out, dict) else None

    def save(self, payload: dict, status: dict | None = None) -> None:
        """The template, sealed and written atomically (owner-only), and its status file (counts and dates)."""
        self.dir.mkdir(parents=True, exist_ok=True)
        blob = self.seal(payload)
        tmp = self.file.with_name(f"{self.file.name}.tmp{os.getpid()}")
        with open(tmp, "wb") as f:
            f.write(blob)
        if os.name != "nt":
            os.chmod(tmp, 0o600)
        os.replace(tmp, self.file)
        if status is not None:
            jsave(self.status_file, status)

    def load(self) -> dict | None:
        """The template, or None (none kept, or it doesn't open with this key). Raises Locked."""
        if not self.exists():
            return None
        return self.unseal(self.file.read_bytes())

    def status(self) -> dict:
        return jload(self.status_file, {}) or {}

    def forget(self) -> list[str]:
        """The key first, then the template and the status file. What went, in words."""
        gone = []
        had_key = bool(self.app.secrets.get(self.secret))
        self.app.secrets.delete(self.secret)
        self._key = None
        if had_key:
            gone.append("the key")
        if self.file.exists():
            self.file.unlink()
            gone.append("the template")
        if self.status_file.exists():
            self.status_file.unlink()
            gone.append("its status")
        try:
            self.dir.rmdir()  # only when nothing else is left in it
        except OSError:
            pass
        return gone


# ------------------------------------------------------------------------------------------------- vectors
def dot(a, b) -> float:
    return math.fsum(x * y for x, y in zip(a, b, strict=False))


def unit(v) -> list[float]:
    n = math.sqrt(math.fsum(x * x for x in v))
    return [float(x) / n for x in v] if n > 0 else [0.0 for _ in v]


def mean_unit(vs, weights=None) -> list[float]:
    """The normalised (weighted) mean of these vectors: a centroid."""
    vs = list(vs)
    if not vs:
        return []
    w = list(weights) if weights is not None else [1.0] * len(vs)
    acc = [0.0] * len(vs[0])
    for v, k in zip(vs, w, strict=False):
        for i, x in enumerate(v):
            acc[i] += k * x
    return unit(acc)


def pack(v) -> str:
    """128 floats as base64 of float16 (inside the sealed template only)."""
    return base64.b64encode(struct.pack(f"<{len(v)}e", *[max(-65504.0, min(65504.0, float(x))) for x in v])).decode()


def unpack(s: str) -> list[float]:
    raw = base64.b64decode(s)
    return list(struct.unpack(f"<{len(raw) // 2}e", raw))


# --------------------------------------------------------------------------------------------- calibration
@dataclass
class Thresholds:
    hi: float  # at or above: it's you
    lo: float  # below: someone else; between: unsure (counts for nothing)
    far: float  # the false-accept rate asked for
    method: str  # "impostors" (calibrated on the impostor set), "floor" (no impostor set), "override" (a setting)
    impostors: int = 0  # how many impostor scores it saw
    t_far: float = 0.0  # the impostor-set cut-off before the floor

    def as_dict(self) -> dict:
        return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in asdict(self).items()}


def quantile(xs, q: float) -> float:
    s = sorted(xs)
    if not s:
        return 0.0
    if len(s) == 1:
        return float(s[0])
    pos = max(0.0, min(1.0, q)) * (len(s) - 1)
    i = int(math.floor(pos))
    j = min(i + 1, len(s) - 1)
    return float(s[i] + (s[j] - s[i]) * (pos - i))


def mean_std(xs) -> tuple[float, float]:
    xs = list(xs)
    if not xs:
        return 0.0, 0.0
    m = math.fsum(xs) / len(xs)
    var = math.fsum((x - m) ** 2 for x in xs) / len(xs)
    return m, math.sqrt(var)


def calibrate(genuine, impostor, far: float, z: float, floor: float, override: float = 0.0) -> Thresholds:
    """The two cut-offs (module docstring). `genuine` is unused for the cut-off itself (it's only measured against
    it, so your own samples never loosen the threshold); it's here so every caller passes the same evidence."""
    del genuine
    imp = list(impostor or [])
    if override and override > 0:
        hi = max(floor, float(override))  # a setting may make it stricter, never looser than the floor
        return Thresholds(hi, max(LO_FLOOR, hi - LO_GAP), far, "override", len(imp))
    if len(imp) < 20:  # too few to say anything: the floor, a little above it
        hi = floor + 0.05
        return Thresholds(hi, max(LO_FLOOR, hi - LO_GAP), far, "floor", len(imp))
    m, sd = mean_std(imp)
    t_far = max(quantile(imp, 1 - far), m + z * sd)
    hi = max(floor, t_far)
    return Thresholds(hi, max(LO_FLOOR, hi - LO_GAP), far, "impostors", len(imp), t_far)


# ------------------------------------------------------------------------------------- the impostor set (.npz)
def _npy_read(raw: bytes):
    if raw[:6] != b"\x93NUMPY":
        raise ValueError("not a .npy array")
    major = raw[6]
    if major == 1:
        (hlen,), start = struct.unpack("<H", raw[8:10]), 10
    else:
        (hlen,), start = struct.unpack("<I", raw[8:12]), 12
    header = ast.literal_eval(raw[start : start + hlen].decode("latin-1"))
    descr, shape, data = header["descr"], tuple(header["shape"]), raw[start + hlen :]
    if header.get("fortran_order"):
        raise ValueError("fortran-ordered arrays aren't read")
    n = math.prod(shape) if shape else 1
    if descr in ("<f2", "<f4", "<f8"):
        code = {"<f2": "e", "<f4": "f", "<f8": "d"}[descr]
        vals = list(struct.unpack(f"<{n}{code}", data[: n * struct.calcsize(code)]))
        if len(shape) == 2:
            return [vals[i * shape[1] : (i + 1) * shape[1]] for i in range(shape[0])]
        return vals if shape else vals[0]
    if descr.startswith("<U"):
        width = int(descr[2:])
        items = [data[i * 4 * width : (i + 1) * 4 * width].decode("utf-32-le").rstrip("\x00") for i in range(n)]
        return items if shape else items[0]
    raise ValueError(f"an array of {descr} isn't read")


def _npy_write(value) -> bytes:
    if isinstance(value, str):
        width = max(1, len(value))
        descr, shape, data = f"<U{width}", (), value.ljust(width, "\x00").encode("utf-32-le")
    else:
        rows = [list(r) for r in value]
        cols = len(rows[0]) if rows else 0
        descr, shape = "<f2", (len(rows), cols)
        flat = [max(-65504.0, min(65504.0, float(x))) for r in rows for x in r]
        data = struct.pack(f"<{len(flat)}e", *flat)
    header = f"{{'descr': '{descr}', 'fortran_order': False, 'shape': {shape!r}, }}"
    pad = 64 - (10 + len(header) + 1) % 64
    header = (header + " " * pad + "\n").encode("latin-1")
    return b"\x93NUMPY\x01\x00" + struct.pack("<H", len(header)) + header + data


def npz_read(path: Path) -> dict:
    out = {}
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            if name.endswith(".npy"):
                out[name[:-4]] = _npy_read(z.read(name))
    return out


def npz_write(path: Path, **arrays) -> None:
    """Rows of floats (as float16) and texts, in numpy's .npz format."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, value in arrays.items():
            z.writestr(f"{name}.npy", _npy_write(value))
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(buf.getvalue())


def load_impostors(path: Path, model_sha: str) -> list[list[float]] | None:
    """The bundled impostor embeddings, as unit vectors; None when the file is missing, unreadable, or was made with
    another recognition model file (its embeddings wouldn't compare)."""
    try:
        if not Path(path).is_file():
            return None
        d = npz_read(Path(path))
        if str(d.get("model_sha256") or "") != model_sha:
            return None
        emb = d.get("emb")
        if not isinstance(emb, list) or not emb or not isinstance(emb[0], list):
            return None
        return [unit(r) for r in emb]
    except (OSError, ValueError, KeyError, SyntaxError, zipfile.BadZipFile, struct.error):
        return None


__all__ = [
    "BIOMETRIC_SECRETS",
    "BioStore",
    "Locked",
    "Thresholds",
    "calibrate",
    "load_impostors",
    "npz_read",
    "npz_write",
    "dot",
    "unit",
    "mean_unit",
    "pack",
    "unpack",
    "quantile",
    "mean_std",
]

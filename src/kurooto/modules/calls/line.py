"""The call line's small pieces of cryptography, shared byte for byte with the Worker (worker.js) and the Android app
(Crypto.java); tests/fixtures/call-vectors.json pins all three to the same answers.

    k1   ntfy messages to your phones: AES-256-GCM, "k1." + base64url(nonce || ciphertext+tag)
    t1   call links made on this computer: "t1.<expires ms>.<hex HMAC-SHA256(call secret, 't1.<expires ms>')>"
    d1   a paired device's key: "d1.<8 hex id>.<64 hex secret>" (made by the Worker; only its hash is kept there)
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# no 0/O/1/I/L: easy to read out and type
CODE_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"


def b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def unb64url(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def new_key() -> str:
    """A fresh AES-256 key, standard base64 (how the Worker and the app store it)."""
    return base64.b64encode(os.urandom(32)).decode()


def seal_k1(key_b64: str, text: str, nonce: bytes | None = None) -> str:
    nonce = nonce or os.urandom(12)
    ct = AESGCM(base64.b64decode(key_b64)).encrypt(nonce, text.encode(), None)
    return "k1." + b64url(nonce + ct)


def open_k1(key_b64: str, token: str) -> str | None:
    if not token.startswith("k1."):
        return None
    try:
        raw = unb64url(token[3:])
        return AESGCM(base64.b64decode(key_b64)).decrypt(raw[:12], raw[12:], None).decode()
    except Exception:
        return None


def ticket(secret: str, hours: float = 2, now_ms: int | None = None) -> str:
    exp = int(now_ms if now_ms is not None else time.time() * 1000) + int(hours * 3600_000)
    mac = hmac.new(secret.encode(), f"t1.{exp}".encode(), hashlib.sha256).hexdigest()
    return f"t1.{exp}.{mac}"


def ticket_ok(secret: str, t: str, now_ms: int | None = None) -> bool:
    parts = t.split(".")
    if len(parts) != 3 or parts[0] != "t1" or not parts[1].isdigit() or len(parts[1]) != 13:
        return False
    if int(parts[1]) < (now_ms if now_ms is not None else time.time() * 1000):
        return False
    good = hmac.new(secret.encode(), f"t1.{parts[1]}".encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(good, parts[2])


def pair_code(n: int = 8) -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(n))


def vapid_keys() -> tuple[str, str]:
    """A Web Push (VAPID) key pair: (private key as a JWK JSON string for the Worker, public key base64url raw)."""
    k = ec.generate_private_key(ec.SECP256R1())
    n = k.private_numbers()
    x, y, d = (v.to_bytes(32, "big") for v in (n.public_numbers.x, n.public_numbers.y, n.private_value))
    jwk = {"kty": "EC", "crv": "P-256", "x": b64url(x), "y": b64url(y), "d": b64url(d), "ext": True}
    return json.dumps(jwk, separators=(",", ":")), b64url(b"\x04" + x + y)

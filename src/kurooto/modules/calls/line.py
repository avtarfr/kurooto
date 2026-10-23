"""The call line's small pieces of cryptography, shared byte for byte with the Worker (worker.js) and the Android app
(Crypto.java); tests/fixtures/call-vectors.json pins all three to the same answers.

    k1   ntfy messages to your phones: AES-256-GCM, "k1." + base64url(nonce || ciphertext+tag)
    t1   call links made on this computer: "t1.<expires ms>.<hex HMAC-SHA256(call secret, 't1.<expires ms>')>"
    d1   a paired device's key: "d1.<8 hex id>.<64 hex secret>" (made by the Worker; only its hash is kept there)
    s1   a reminder sealed for one Android phone (modules/lidsafe.py), which the Worker keeps but can't open: ECDH
         P-256 between a fresh key and the phone's own (the phone made it; its private half never leaves it), HKDF-
         SHA256 (salt: the fresh public key, info "kurooto s1") to an AES-256 key, then k1 with that key:
         "s1." + base64url(fresh public key, 65 bytes uncompressed) + "." + the k1 token without its "k1."
    f1   a file from this computer for the phone app's chat (0.5.18), kept on the call line for a day: AES-256-GCM
         with a fresh key, the raw bytes nonce || ciphertext+tag; the key goes only in the link's #fragment, which
         the call line's file page (public/file.js) opens in the phone's browser
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

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


def seal_f1(key: bytes, data: bytes, nonce: bytes | None = None) -> bytes:
    nonce = nonce or os.urandom(12)
    return nonce + AESGCM(key).encrypt(nonce, data, None)


def open_f1(key: bytes, blob: bytes) -> bytes | None:
    try:
        return AESGCM(key).decrypt(blob[:12], blob[12:], None)
    except Exception:
        return None


S1_INFO = b"kurooto s1"


def _s1_key(shared: bytes, epk: bytes) -> str:
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=epk, info=S1_INFO).derive(shared)
    return base64.b64encode(key).decode()


def seal_s1(
    phone_pub: str, text: str, eph: ec.EllipticCurvePrivateKey | None = None, nonce: bytes | None = None
) -> str:
    """Seal text for one phone, given its public key (base64url, 65 bytes uncompressed P-256). Only that phone can
    open it; raises ValueError for a key that isn't one."""
    peer = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), unb64url(phone_pub))
    eph = eph or ec.generate_private_key(ec.SECP256R1())
    epk = eph.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    k1 = seal_k1(_s1_key(eph.exchange(ec.ECDH(), peer), epk), text, nonce)
    return f"s1.{b64url(epk)}.{k1[3:]}"


def open_s1(phone: ec.EllipticCurvePrivateKey, token: str) -> str | None:
    """What the phone does (Seal.java); here for the tests."""
    parts = token.split(".")
    if len(parts) != 3 or parts[0] != "s1":
        return None
    try:
        epk = unb64url(parts[1])
        peer = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), epk)
        return open_k1(_s1_key(phone.exchange(ec.ECDH(), peer), epk), "k1." + parts[2])
    except ValueError:
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

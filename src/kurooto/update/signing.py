"""ed25519 signatures for release pointers and manifests.

The private key stays on the maintainer's laptop (never in CI); the public keys are in PUBLIC_KEYS, so a new key
can be added before the old one is retired. A document is trusted if any listed key verifies it.
"""

from __future__ import annotations

import base64
import json

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

# base64 raw public keys, newest first (a new key is added here before the old one is retired)
PUBLIC_KEYS: list[str] = ["ScONcap27e/YGb+KR8e2Oq4rkOIGTvjUbyk9Y5HcIhs="]


def canonical(doc: dict) -> bytes:
    return json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sign(doc: dict, private_key: Ed25519PrivateKey) -> str:
    return base64.b64encode(private_key.sign(canonical(doc))).decode()


def verify(doc: dict, signature: str, keys: list[str] | None = None) -> bool:
    keys = PUBLIC_KEYS if keys is None else keys
    try:
        sig = base64.b64decode(signature)
    except ValueError:
        return False
    for k in keys:
        try:
            Ed25519PublicKey.from_public_bytes(base64.b64decode(k)).verify(sig, canonical(doc))
            return True
        except (InvalidSignature, ValueError):
            continue
    return False


def public_b64(private_key: Ed25519PrivateKey) -> str:
    from cryptography.hazmat.primitives import serialization

    raw = private_key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return base64.b64encode(raw).decode()

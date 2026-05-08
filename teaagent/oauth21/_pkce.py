from __future__ import annotations

import hashlib
import secrets

from teaagent.oauth21._jwt import _b64url_encode


def generate_code_verifier(length: int = 43) -> str:
    if length < 43 or length > 128:
        raise ValueError('code verifier length must be 43-128')
    raw = secrets.token_bytes((length * 3) // 4 + 1)
    verifier = _b64url_encode(raw)[:length]
    while len(verifier) < length:
        verifier += _b64url_encode(secrets.token_bytes(32))
    return verifier[:length]


def compute_s256_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode('ascii')).digest()
    return _b64url_encode(digest)

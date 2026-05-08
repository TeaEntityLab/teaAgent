from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import time
from typing import Any, Optional

from teaagent.oauth21._types import JWTError

_REQUIRED_JWK_MEMBERS: dict[str, frozenset[str]] = {
    'EC': frozenset({'crv', 'kty', 'x', 'y'}),
    'RSA': frozenset({'e', 'kty', 'n'}),
    'oct': frozenset({'k', 'kty'}),
    'OKP': frozenset({'crv', 'kty', 'x'}),
}


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')


def _b64url_decode(s: str) -> bytes:
    pad = len(s) % 4
    if pad:
        s += '=' * (4 - pad)
    try:
        return base64.urlsafe_b64decode(s)
    except (binascii.Error, ValueError) as exc:
        raise JWTError(f'Invalid base64url: {exc}') from exc


def create_jwt(
    payload: dict[str, Any],
    key: bytes,
    *,
    header_extra: Optional[dict[str, Any]] = None,
) -> str:
    header: dict[str, Any] = {'alg': 'HS256', 'typ': 'JWT'}
    if header_extra:
        header.update(header_extra)
    header_b64 = _b64url_encode(json.dumps(header, separators=(',', ':')).encode())
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(',', ':')).encode())
    signing_input = f'{header_b64}.{payload_b64}'.encode('ascii')
    sig = hmac.new(key, signing_input, hashlib.sha256).digest()
    return f'{header_b64}.{payload_b64}.{_b64url_encode(sig)}'


def verify_jwt(
    token: str,
    key: bytes,
    *,
    aud: Optional[str] = None,
    iss: Optional[str] = None,
    allow_expired: bool = False,
) -> dict[str, Any]:
    parts = token.split('.')
    if len(parts) != 3:
        raise JWTError('Invalid JWT format')
    header_b64, payload_b64, sig_b64 = parts
    signing_input = f'{header_b64}.{payload_b64}'.encode('ascii')
    expected_sig = hmac.new(key, signing_input, hashlib.sha256).digest()
    if not hmac.compare_digest(expected_sig, _b64url_decode(sig_b64)):
        raise JWTError('Invalid JWT signature')
    payload: dict[str, Any] = json.loads(_b64url_decode(payload_b64))
    if not allow_expired and 'exp' in payload:
        exp = payload['exp']
        if isinstance(exp, (int, float)) and exp < time.time():
            raise JWTError('Token expired')
    if aud is not None and payload.get('aud') != aud:
        raise JWTError(f"Invalid audience: expected '{aud}'")
    if iss is not None and payload.get('iss') != iss:
        raise JWTError(f"Invalid issuer: expected '{iss}'")
    return payload


def decode_jwt_unsafe(token: str) -> tuple[dict[str, Any], dict[str, Any]]:
    parts = token.split('.')
    if len(parts) < 2:
        raise JWTError('Invalid JWT format')
    try:
        header: dict[str, Any] = json.loads(_b64url_decode(parts[0]))
        payload: dict[str, Any] = json.loads(_b64url_decode(parts[1]))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise JWTError(f'Invalid JWT encoding: {exc}') from exc
    return header, payload


def compute_jwk_thumbprint(jwk: dict[str, Any]) -> str:
    kty = jwk.get('kty', '')
    required = _REQUIRED_JWK_MEMBERS.get(kty)
    if required is None:
        required = frozenset({'kty'})
    canonical = {k: jwk[k] for k in sorted(jwk) if k in required}
    canonical_json = json.dumps(canonical, separators=(',', ':'), sort_keys=True)
    digest = hashlib.sha256(canonical_json.encode('ascii')).digest()
    return _b64url_encode(digest)

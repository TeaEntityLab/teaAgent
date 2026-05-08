from __future__ import annotations

import hmac
import time
from typing import Any, Optional

from teaagent.oauth21._dpop import _verify_dpop_signature
from teaagent.oauth21._jwt import compute_jwk_thumbprint, decode_jwt_unsafe, verify_jwt
from teaagent.oauth21._types import (
    _DPOP_PROOF_TYP,
    _PROOF_MAX_AGE_SECONDS,
    _TOKEN_TYPE_BEARER,
    _TOKEN_TYPE_DPOP,
    HAS_CRYPTOGRAPHY,
    InvalidDPoPError,
    OAuth21Error,
    OAuth21TokenClaims,
)


class OAuth21ResourceServer:
    def __init__(
        self,
        signing_key: str,
        issuer: str,
    ) -> None:
        if not signing_key or len(signing_key) < 16:
            raise ValueError('signing_key must be at least 16 characters')
        self._key = signing_key.encode('utf-8')
        self._issuer = issuer

    def validate_request(
        self,
        authorization_header: Optional[str],
        dpop_header: Optional[str],
        method: str,
        url: str,
    ) -> OAuth21TokenClaims:
        if not authorization_header:
            raise OAuth21Error('Missing Authorization header')
        parts = authorization_header.split(None, 1)
        if len(parts) < 2:
            raise OAuth21Error('Malformed Authorization header')
        scheme, token = parts[0], parts[1]
        if scheme not in (_TOKEN_TYPE_DPOP, _TOKEN_TYPE_BEARER):
            raise OAuth21Error(f"Unsupported auth scheme: '{scheme}'")
        claims = verify_jwt(token, self._key, iss=self._issuer)
        if scheme == _TOKEN_TYPE_DPOP or claims.get('cnf', {}).get('jkt'):
            if not HAS_CRYPTOGRAPHY:
                raise InvalidDPoPError(
                    'DPoP token validation requires the cryptography library. '
                    'Install with: pip install teaagent[oauth]'
                )
            self._validate_dpop_binding(claims, dpop_header, method, url, token)
        return OAuth21TokenClaims(
            iss=claims['iss'],
            sub=claims['sub'],
            aud=claims['aud'],
            iat=claims['iat'],
            exp=claims['exp'],
            jti=claims['jti'],
            scope=claims.get('scope', ''),
            cnf_jkt=(claims.get('cnf') or {}).get('jkt'),
            raw=claims,
        )

    def _validate_dpop_binding(
        self,
        claims: dict[str, Any],
        dpop_header: Optional[str],
        method: str,
        url: str,
        _token: str,
    ) -> None:
        token_jkt = (claims.get('cnf') or {}).get('jkt')
        if not token_jkt:
            return
        if not dpop_header:
            raise InvalidDPoPError('Missing DPoP header for DPoP-bound token')
        header, payload = decode_jwt_unsafe(dpop_header)
        if header.get('typ') != _DPOP_PROOF_TYP:
            raise InvalidDPoPError('DPoP proof has wrong typ')
        if payload.get('htm', '').upper() != method.upper():
            raise InvalidDPoPError(
                f"DPoP htm mismatch: expected '{method.upper()}', "
                f"got '{payload.get('htm', '')}'"
            )
        if payload.get('htu', '') != url:
            raise InvalidDPoPError(
                f"DPoP htu mismatch: expected '{url}', got '{payload.get('htu', '')}'"
            )
        iat = payload.get('iat', 0)
        if abs(time.time() - iat) > _PROOF_MAX_AGE_SECONDS:
            raise InvalidDPoPError('DPoP proof is too old')
        jwk = header.get('jwk')
        if not isinstance(jwk, dict):
            raise InvalidDPoPError('DPoP proof header missing jwk')
        _verify_dpop_signature(dpop_header, jwk)
        proof_jkt = compute_jwk_thumbprint(jwk)
        if not hmac.compare_digest(proof_jkt.encode(), token_jkt.encode()):
            raise InvalidDPoPError(
                'DPoP proof key does not match token confirmation key'
            )

from __future__ import annotations

from teaagent.oauth21._jwt import (
    _b64url_encode,
    compute_jwk_thumbprint,
    create_jwt,
    decode_jwt_unsafe,
    verify_jwt,
)
from teaagent.oauth21._pkce import compute_s256_challenge, generate_code_verifier
from teaagent.oauth21._resource import OAuth21ResourceServer
from teaagent.oauth21._server import OAuth21AuthorizationServer
from teaagent.oauth21._store import InMemoryOAuthStore, OAuthKeyRing, OAuthStore
from teaagent.oauth21._types import (
    _AUTHORIZATION_HEADER,
    _AUTHORIZE_PATH,
    _DPOP_HEADER,
    _DPOP_NONCE_HEADER,
    _OAUTH_METADATA_PATH,
    _TOKEN_PATH,
    _TOKEN_TYPE_DPOP,
    HAS_CRYPTOGRAPHY,
    DPoPValidationResult,
    InvalidClientError,
    InvalidDPoPError,
    InvalidGrantError,
    JWTError,
    OAuth21Client,
    OAuth21Error,
    OAuth21TokenClaims,
    OAuth21TokenResponse,
)

__all__ = [
    'HAS_CRYPTOGRAPHY',
    'JWTError',
    'InvalidClientError',
    'InvalidGrantError',
    'InvalidDPoPError',
    'OAuth21AuthorizationServer',
    'OAuth21ResourceServer',
    'OAuth21Client',
    'OAuth21TokenResponse',
    'OAuth21TokenClaims',
    'DPoPValidationResult',
    'OAuth21Error',
    'OAuthStore',
    'InMemoryOAuthStore',
    'OAuthKeyRing',
    'create_jwt',
    'verify_jwt',
    'decode_jwt_unsafe',
    '_b64url_encode',
    'compute_jwk_thumbprint',
    'generate_code_verifier',
    'compute_s256_challenge',
    '_AUTHORIZE_PATH',
    '_TOKEN_PATH',
    '_OAUTH_METADATA_PATH',
    '_DPOP_NONCE_HEADER',
    '_DPOP_HEADER',
    '_AUTHORIZATION_HEADER',
    '_TOKEN_TYPE_DPOP',
]

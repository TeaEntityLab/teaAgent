from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

try:
    from cryptography.exceptions import InvalidSignature  # noqa: F401
    from cryptography.hazmat.primitives import hashes as _crypto_hashes  # noqa: F401
    from cryptography.hazmat.primitives.asymmetric import ec as _crypto_ec  # noqa: F401
    from cryptography.hazmat.primitives.asymmetric.utils import (
        encode_dss_signature,  # noqa: F401
    )

    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False

_TOKEN_TYPE_DPOP = 'DPoP'
_TOKEN_TYPE_BEARER = 'Bearer'
_TOKEN_PATH = '/token'
_AUTHORIZE_PATH = '/authorize'
_OAUTH_METADATA_PATH = '/.well-known/oauth-authorization-server'
_DPOP_NONCE_HEADER = 'DPoP-Nonce'
_DPOP_HEADER = 'DPoP'
_AUTHORIZATION_HEADER = 'Authorization'
_DPOP_PROOF_TYP = 'dpop+jwt'

_CODE_TTL_SECONDS = 600
_DEFAULT_ACCESS_TOKEN_TTL = 3600
_NONCE_TTL_SECONDS = 300
_PROOF_MAX_AGE_SECONDS = 60


class OAuth21Error(Exception):
    pass


class JWTError(OAuth21Error):
    pass


class InvalidClientError(OAuth21Error):
    pass


class InvalidGrantError(OAuth21Error):
    pass


class InvalidDPoPError(OAuth21Error):
    pass


@dataclass(frozen=True)
class OAuth21Client:
    client_id: str
    client_secret: str
    redirect_uris: frozenset[str]
    scope: str = 'mcp'

    def validate_redirect_uri(self, uri: str) -> bool:
        return uri in self.redirect_uris


@dataclass
class _AuthorizationCode:
    code: str
    client_id: str
    redirect_uri: str
    code_challenge: str
    code_challenge_method: str
    expires_at: float
    scope: str


@dataclass(frozen=True)
class OAuth21TokenResponse:
    access_token: str
    token_type: str
    expires_in: int
    scope: str
    refresh_token: Optional[str] = None


@dataclass(frozen=True)
class OAuth21TokenClaims:
    iss: str
    sub: str
    aud: str
    iat: int
    exp: int
    jti: str
    scope: str
    cnf_jkt: Optional[str] = None
    raw: dict[str, Any] = field(repr=False, default_factory=dict)


@dataclass(frozen=True)
class DPoPValidationResult:
    valid: bool
    jkt: Optional[str] = None
    error: Optional[str] = None

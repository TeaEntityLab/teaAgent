"""OAuth 2.1 Authorization Server with DPoP support.

Zero-dependency core: JWT (HMAC-SHA256), PKCE (S256), authorization code
flow, Bearer token validation.

DPoP proof-of-possession requires the optional ``cryptography`` library::

    pip install teaagent[oauth]

When ``cryptography`` is available, DPoP proofs are validated with
ES256/RS256 asymmetric signatures via the public JWK in the proof header.
Without it, DPoP is unavailable and bearer-only token validation is used.

Specifications implemented:
- OAuth 2.1 draft (PKCE mandatory, exact redirect URI, no implicit grant)
- RFC 9449  DPoP (Demonstration of Proof-of-Possession)
- RFC 7636  PKCE (Proof Key for Code Exchange)
- RFC 7638  JWK Thumbprint
- RFC 7519  JSON Web Token (partial: HS256 only without cryptography)
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Optional cryptography import for DPoP
# ---------------------------------------------------------------------------

try:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes as _crypto_hashes
    from cryptography.hazmat.primitives.asymmetric import ec as _crypto_ec
    from cryptography.hazmat.primitives.asymmetric.utils import (
        encode_dss_signature,
    )

    HAS_CRYPTOGRAPHY = True
except ImportError:  # pragma: no cover
    HAS_CRYPTOGRAPHY = False  # pragma: no cover

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TOKEN_TYPE_DPOP = 'DPoP'
_TOKEN_TYPE_BEARER = 'Bearer'
_TOKEN_PATH = '/token'
_AUTHORIZE_PATH = '/authorize'
_OAUTH_METADATA_PATH = '/.well-known/oauth-authorization-server'
_DPOP_NONCE_HEADER = 'DPoP-Nonce'
_DPOP_HEADER = 'DPoP'
_AUTHORIZATION_HEADER = 'Authorization'
_DPOP_PROOF_TYP = 'dpop+jwt'

_CODE_TTL_SECONDS = 600  # authorization code lifetime
_DEFAULT_ACCESS_TOKEN_TTL = 3600  # 1 hour
_NONCE_TTL_SECONDS = 300  # DPoP nonce validity window
_PROOF_MAX_AGE_SECONDS = 60  # DPoP proof freshness window

# ---------------------------------------------------------------------------
# Base64url helpers (RFC 7515 Appendix C)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# JWT utilities (HMAC-SHA256)
# ---------------------------------------------------------------------------


def create_jwt(
    payload: dict[str, Any],
    key: bytes,
    *,
    header_extra: Optional[dict[str, Any]] = None,
) -> str:
    """Create a signed JWT (HS256)."""
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
    """Verify a JWT signature and claims. Returns the decoded payload."""
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
    """Decode JWT header and payload without verifying signature."""
    parts = token.split('.')
    if len(parts) < 2:
        raise JWTError('Invalid JWT format')
    header: dict[str, Any] = json.loads(_b64url_decode(parts[0]))
    payload: dict[str, Any] = json.loads(_b64url_decode(parts[1]))
    return header, payload


# ---------------------------------------------------------------------------
# JWK Thumbprint (RFC 7638)
# ---------------------------------------------------------------------------

# Required members per key type for thumbprint computation.
_THUMBPRINT_REQUIRED: dict[str, frozenset[str]] = {
    'EC': frozenset({'crv', 'kty', 'x', 'y'}),
    'RSA': frozenset({'e', 'kty', 'n'}),
    'oct': frozenset({'k', 'kty'}),
    'OKP': frozenset({'crv', 'kty', 'x'}),
}


def compute_jwk_thumbprint(jwk: dict[str, Any]) -> str:
    """Compute JWK thumbprint per RFC 7638 (SHA-256)."""
    kty = jwk.get('kty', '')
    required = _THUMBPRINT_REQUIRED.get(kty)
    if required is None:
        required = frozenset({'kty'})
    canonical = {k: jwk[k] for k in sorted(jwk) if k in required}
    canonical_json = json.dumps(canonical, separators=(',', ':'), sort_keys=True)
    digest = hashlib.sha256(canonical_json.encode('ascii')).digest()
    return _b64url_encode(digest)


# ---------------------------------------------------------------------------
# PKCE (RFC 7636, S256 only)
# ---------------------------------------------------------------------------


def generate_code_verifier(length: int = 43) -> str:
    """Generate a PKCE code verifier.

    Length must be between 43 and 128 characters.
    """
    if length < 43 or length > 128:
        raise ValueError('code verifier length must be 43–128')
    raw = secrets.token_bytes((length * 3) // 4 + 1)
    verifier = _b64url_encode(raw)[:length]
    while len(verifier) < length:
        verifier += _b64url_encode(secrets.token_bytes(32))
    return verifier[:length]


def compute_s256_challenge(verifier: str) -> str:
    """Compute the S256 code challenge from a code verifier."""
    digest = hashlib.sha256(verifier.encode('ascii')).digest()
    return _b64url_encode(digest)


# ---------------------------------------------------------------------------
# DPoP proof validation (requires cryptography)
# ---------------------------------------------------------------------------


def _jwk_to_ec_public_key(jwk: dict[str, Any]) -> Any:
    """Convert an EC JWK to a ``cryptography`` EC public key object."""
    crv_name = jwk.get('crv', '')
    if crv_name == 'P-256':
        curve: Any = _crypto_ec.SECP256R1()
    elif crv_name == 'P-384':
        curve = _crypto_ec.SECP384R1()
    elif crv_name == 'P-521':
        curve = _crypto_ec.SECP521R1()
    else:
        raise JWTError(f'Unsupported EC curve: {crv_name}')

    x_int = int.from_bytes(_b64url_decode(jwk['x']), 'big')
    y_int = int.from_bytes(_b64url_decode(jwk['y']), 'big')
    pub_numbers = _crypto_ec.EllipticCurvePublicNumbers(x_int, y_int, curve)
    return pub_numbers.public_key()


def _verify_dpop_signature(proof_jwt: str, jwk: dict[str, Any]) -> None:
    """Verify the signature of a DPoP proof JWT using the embedded JWK."""
    parts = proof_jwt.split('.')
    if len(parts) != 3:
        raise JWTError('Invalid DPoP proof format')
    signing_input = f'{parts[0]}.{parts[1]}'.encode('ascii')
    signature_bytes = _b64url_decode(parts[2])

    alg = jwk.get('alg', json.loads(_b64url_decode(parts[0])).get('alg', 'ES256'))
    kty = jwk.get('kty', '')

    if kty == 'EC' and alg in ('ES256', 'ES384', 'ES512'):
        _verify_dpop_ec(signing_input, signature_bytes, jwk, alg)
    elif kty == 'RSA' and alg in ('RS256', 'RS384', 'RS512'):
        _verify_dpop_rsa(signing_input, signature_bytes, jwk, alg)
    else:
        raise JWTError(
            f'Unsupported DPoP key type / algorithm: kty={kty} alg={alg}'
        )


def _ec_alg_to_hash(alg: str) -> Any:
    if alg == 'ES256':
        return _crypto_hashes.SHA256()
    elif alg == 'ES384':
        return _crypto_hashes.SHA384()
    else:
        return _crypto_hashes.SHA512()


def _verify_dpop_ec(
    signing_input: bytes,
    signature: bytes,
    jwk: dict[str, Any],
    alg: str,
) -> None:
    pub_key = _jwk_to_ec_public_key(jwk)
    # JWS ECDSA signature is R||S (concatenated). Convert to DER.
    key_size = pub_key.curve.key_size
    # key_size is in bits; each component is ceil(key_size/8) bytes
    byte_len = (key_size + 7) // 8
    if len(signature) != byte_len * 2:
        raise JWTError(
            f'Invalid DPoP EC signature length: {len(signature)} '
            f'(expected {byte_len * 2})'
        )
    r_int = int.from_bytes(signature[:byte_len], 'big')
    s_int = int.from_bytes(signature[byte_len:], 'big')
    der_sig = encode_dss_signature(r_int, s_int)
    try:
        pub_key.verify(der_sig, signing_input, _crypto_ec.ECDSA(_ec_alg_to_hash(alg)))
    except InvalidSignature:
        raise JWTError('Invalid DPoP proof signature') from None


def _verify_dpop_rsa(
    signing_input: bytes,
    signature: bytes,
    jwk: dict[str, Any],
    alg: str,
) -> None:
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    from cryptography.hazmat.primitives.asymmetric.utils import Prehashed

    e_int = int.from_bytes(_b64url_decode(jwk['e']), 'big')
    n_int = int.from_bytes(_b64url_decode(jwk['n']), 'big')
    pub_numbers = rsa.RSAPublicNumbers(e_int, n_int)
    pub_key = pub_numbers.public_key()

    hash_alg: Any
    if alg == 'RS256':
        hash_alg = _crypto_hashes.SHA256()
    elif alg == 'RS384':
        hash_alg = _crypto_hashes.SHA384()
    else:
        hash_alg = _crypto_hashes.SHA512()

    try:
        pub_key.verify(
            signature,
            signing_input,
            padding.PKCS1v15(),
            Prehashed(hash_alg),
        )
    except InvalidSignature:
        raise JWTError('Invalid DPoP proof signature') from None


def _encode_dpop_proof_payload(method: str, url: str, nonce: str) -> bool:
    """No-op placeholder for the client-side proof library."""
    return True


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OAuth21Client:
    """Registered OAuth 2.1 client."""

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
    """Successful token endpoint response."""

    access_token: str
    token_type: str  # 'DPoP' or 'Bearer'
    expires_in: int
    scope: str
    refresh_token: Optional[str] = None


@dataclass(frozen=True)
class OAuth21TokenClaims:
    """Decoded and validated access token claims."""

    iss: str
    sub: str
    aud: str
    iat: int
    exp: int
    jti: str
    scope: str
    cnf_jkt: Optional[str] = None  # DPoP confirmation key thumbprint
    raw: dict[str, Any] = field(repr=False, default_factory=dict)


@dataclass(frozen=True)
class DPoPValidationResult:
    """Result of validating a DPoP proof."""

    valid: bool
    jkt: Optional[str] = None  # JWK thumbprint of the proof key
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class OAuth21Error(Exception):
    """Base error for OAuth 2.1 operations."""


class JWTError(OAuth21Error):
    """JWT validation or creation error."""


class InvalidClientError(OAuth21Error):
    """Client authentication failed."""


class InvalidGrantError(OAuth21Error):
    """Authorization grant is invalid or expired."""


class InvalidDPoPError(OAuth21Error):
    """DPoP proof validation failed."""


# ---------------------------------------------------------------------------
# OAuth 2.1 Authorization Server
# ---------------------------------------------------------------------------


class OAuth21AuthorizationServer:
    """OAuth 2.1 Authorization Server (AS).

    Handles client registration, authorization code generation, and token
    exchange. DPoP-bound tokens are issued when a valid DPoP proof is
    presented at the token endpoint.
    """

    def __init__(
        self,
        signing_key: str,
        issuer: str,
        *,
        token_ttl: int = _DEFAULT_ACCESS_TOKEN_TTL,
        nonce_ttl: int = _NONCE_TTL_SECONDS,
    ) -> None:
        """Create the authorization server.

        Args:
            signing_key: A secret string used to HMAC-sign JWTs.
            issuer: The issuer URI (e.g. ``https://mcp.example.com``).
            token_ttl: Access token lifetime in seconds.
            nonce_ttl: DPoP nonce validity window in seconds.
        """
        if not signing_key or len(signing_key) < 16:
            raise ValueError('signing_key must be at least 16 characters')
        self._key = signing_key.encode('utf-8')
        self._issuer = issuer
        self._token_ttl = token_ttl
        self._nonce_ttl = nonce_ttl
        self._clients: dict[str, OAuth21Client] = {}
        self._codes: dict[str, _AuthorizationCode] = {}
        self._nonces: dict[str, float] = {}

    # -- client management --

    def register_client(
        self,
        client_id: str,
        client_secret: str,
        redirect_uris: list[str],
        *,
        scope: str = 'mcp',
    ) -> OAuth21Client:
        if client_id in self._clients:
            raise InvalidClientError(f"Client '{client_id}' already registered")
        client = OAuth21Client(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uris=frozenset(redirect_uris),
            scope=scope,
        )
        self._clients[client_id] = client
        return client

    def get_client(self, client_id: str) -> OAuth21Client:
        try:
            return self._clients[client_id]
        except KeyError as exc:
            raise InvalidClientError(f"Unknown client '{client_id}'") from exc

    @property
    def issuer(self) -> str:
        return self._issuer

    # -- authorization endpoint --

    def create_authorization_code(
        self,
        client_id: str,
        redirect_uri: str,
        code_challenge: str,
        *,
        code_challenge_method: str = 'S256',
        scope: str = 'mcp',
        state: Optional[str] = None,
    ) -> tuple[str, Optional[str]]:
        """Create an authorization code. Returns ``(redirect_url, None)``.

        The caller should redirect the user-agent to the returned URL.
        """
        client = self.get_client(client_id)
        if not client.validate_redirect_uri(redirect_uri):
            raise InvalidClientError(
                f"Redirect URI '{redirect_uri}' not registered for client '{client_id}'"
            )
        if code_challenge_method != 'S256':
            raise OAuth21Error(
                f"Unsupported code_challenge_method: '{code_challenge_method}'. "
                f'Only S256 is supported.'
            )

        code = secrets.token_urlsafe(32)
        self._codes[code] = _AuthorizationCode(
            code=code,
            client_id=client_id,
            redirect_uri=redirect_uri,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            expires_at=time.time() + _CODE_TTL_SECONDS,
            scope=scope,
        )
        self._prune_expired_codes()

        redirect_url = redirect_uri
        separator = '&' if '?' in redirect_uri else '?'
        redirect_url += f'{separator}code={code}'
        if state:
            redirect_url += f'&state={state}'
        return redirect_url, state

    # -- token endpoint --

    def exchange_code(
        self,
        code: str,
        code_verifier: str,
        *,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        dpop_proof_jwt: Optional[str] = None,
    ) -> OAuth21TokenResponse:
        """Exchange an authorization code for an access token.

        If ``dpop_proof_jwt`` is provided, the access token is DPoP-bound
        (token_type = 'DPoP') and includes a ``cnf.jkt`` claim.

        Args:
            code: The authorization code from the authorization endpoint.
            code_verifier: The PKCE code verifier.
            client_id: Authenticating client id (optional for public clients).
            client_secret: Authenticating client secret (optional).
            dpop_proof_jwt: A DPoP proof JWT for token binding.

        Returns:
            Token response with access token and metadata.
        """
        auth_code = self._consume_code(code)
        self._validate_pkce(auth_code, code_verifier)
        if client_id:
            self._validate_client(client_id, client_secret)

        cnf_jkt: Optional[str] = None
        if dpop_proof_jwt is not None:
            if not HAS_CRYPTOGRAPHY:
                raise InvalidDPoPError(
                    'DPoP requires the cryptography library. '
                    'Install with: pip install teaagent[oauth]'
                )
            cnf_jkt = self._validate_dpop_and_extract_jkt(dpop_proof_jwt)

        now = int(time.time())
        payload: dict[str, Any] = {
            'iss': self._issuer,
            'sub': auth_code.client_id,
            'aud': self._issuer,
            'iat': now,
            'exp': now + self._token_ttl,
            'jti': secrets.token_hex(16),
            'scope': auth_code.scope,
        }
        if cnf_jkt:
            payload['cnf'] = {'jkt': cnf_jkt}

        token_type = _TOKEN_TYPE_DPOP if cnf_jkt else _TOKEN_TYPE_BEARER
        access_token = create_jwt(payload, self._key)

        return OAuth21TokenResponse(
            access_token=access_token,
            token_type=token_type,
            expires_in=self._token_ttl,
            scope=auth_code.scope,
        )

    def introspect_token(self, token: str) -> OAuth21TokenClaims:
        """Verify and decode an access token. Returns validated claims."""
        payload = verify_jwt(token, self._key, iss=self._issuer)
        return OAuth21TokenClaims(
            iss=payload['iss'],
            sub=payload['sub'],
            aud=payload['aud'],
            iat=payload['iat'],
            exp=payload['exp'],
            jti=payload['jti'],
            scope=payload.get('scope', ''),
            cnf_jkt=(payload.get('cnf') or {}).get('jkt'),
            raw=payload,
        )

    # -- DPoP nonces --

    def generate_dpop_nonce(self) -> str:
        """Generate a fresh DPoP nonce."""
        nonce = secrets.token_urlsafe(24)
        self._nonces[nonce] = time.time()
        self._prune_nonces()
        return nonce

    def validate_dpop_nonce(self, nonce: str) -> bool:
        """Validate a DPoP nonce (must exist and not be expired)."""
        created = self._nonces.get(nonce)
        if created is None:
            return False
        if time.time() - created > self._nonce_ttl:
            del self._nonces[nonce]
            return False
        return True

    # -- metadata --

    def metadata(self) -> dict[str, Any]:
        """Return OAuth 2.0 Authorization Server Metadata (RFC 8414 subset)."""
        return {
            'issuer': self._issuer,
            'authorization_endpoint': f'{self._issuer}{_AUTHORIZE_PATH}',
            'token_endpoint': f'{self._issuer}{_TOKEN_PATH}',
            'token_endpoint_auth_methods_supported': [
                'client_secret_basic',
                'none',
            ],
            'code_challenge_methods_supported': ['S256'],
            'dpop_signing_alg_values_supported': (
                ['ES256', 'ES384', 'ES512', 'RS256']
                if HAS_CRYPTOGRAPHY
                else []
            ),
            'grant_types_supported': ['authorization_code'],
            'response_types_supported': ['code'],
        }

    # -- internal helpers --

    def _consume_code(self, code: str) -> _AuthorizationCode:
        auth_code = self._codes.pop(code, None)
        if auth_code is None:
            raise InvalidGrantError('Unknown or already-used authorization code')
        if auth_code.expires_at < time.time():
            raise InvalidGrantError('Authorization code expired')
        return auth_code

    def _validate_pkce(
        self, auth_code: _AuthorizationCode, code_verifier: str
    ) -> None:
        challenge = compute_s256_challenge(code_verifier)
        if not hmac.compare_digest(challenge.encode(), auth_code.code_challenge.encode()):
            raise InvalidGrantError('Invalid code_verifier: PKCE challenge mismatch')

    def _validate_client(
        self, client_id: str, client_secret: Optional[str]
    ) -> None:
        client = self.get_client(client_id)
        if client_secret is not None and not hmac.compare_digest(
            client_secret.encode('utf-8'), client.client_secret.encode('utf-8')
        ):
            raise InvalidClientError('Invalid client_secret')

    def _validate_dpop_and_extract_jkt(self, proof_jwt: str) -> str:
        """Validate a DPoP proof and return the JWK thumbprint."""
        header, payload = decode_jwt_unsafe(proof_jwt)

        if header.get('typ') != _DPOP_PROOF_TYP:
            raise InvalidDPoPError(
                f"DPoP proof typ must be '{_DPOP_PROOF_TYP}'"
            )
        jwk = header.get('jwk')
        if not isinstance(jwk, dict):
            raise InvalidDPoPError('DPoP proof header must include a jwk')

        _verify_dpop_signature(proof_jwt, jwk)

        # Validate time freshness
        iat = payload.get('iat', 0)
        if abs(time.time() - iat) > _PROOF_MAX_AGE_SECONDS:
            raise InvalidDPoPError('DPoP proof is too old')

        return compute_jwk_thumbprint(jwk)

    def _prune_expired_codes(self) -> None:
        now = time.time()
        expired = [c for c, ac in self._codes.items() if ac.expires_at < now]
        for c in expired:
            del self._codes[c]

    def _prune_nonces(self) -> None:
        now = time.time()
        expired = [
            n
            for n, created in self._nonces.items()
            if now - created > self._nonce_ttl
        ]
        for n in expired:
            del self._nonces[n]


# ---------------------------------------------------------------------------
# OAuth 2.1 Resource Server (token validation)
# ---------------------------------------------------------------------------


class OAuth21ResourceServer:
    """Validates access tokens and DPoP proofs on incoming HTTP requests.

    Call :meth:`validate_request` on each incoming request to check
    authorization and (optionally) DPoP proof-of-possession.
    """

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
        """Validate an incoming HTTP request.

        Args:
            authorization_header: Value of the ``Authorization`` header.
            dpop_header: Value of the ``DPoP`` header (required if token
                is DPoP-bound).
            method: HTTP method of the request (e.g. ``'POST'``).
            url: Full request URL (e.g. ``'https://mcp.example.com/mcp'``).

        Returns:
            Validated token claims.

        Raises:
            OAuth21Error: If validation fails.
        """
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
            self._validate_dpop_binding(
                claims, dpop_header, method, url, token
            )

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
            return  # token is not DPoP-bound

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
                f"DPoP htu mismatch: expected '{url}', "
                f"got '{payload.get('htu', '')}'"
            )
        # Check freshness
        iat = payload.get('iat', 0)
        if abs(time.time() - iat) > _PROOF_MAX_AGE_SECONDS:
            raise InvalidDPoPError('DPoP proof is too old')

        jwk = header.get('jwk')
        if not isinstance(jwk, dict):
            raise InvalidDPoPError('DPoP proof header missing jwk')

        _verify_dpop_signature(dpop_header, jwk)
        proof_jkt = compute_jwk_thumbprint(jwk)
        if not hmac.compare_digest(
            proof_jkt.encode(), token_jkt.encode()
        ):
            raise InvalidDPoPError(
                'DPoP proof key does not match token confirmation key'
            )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

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
    'create_jwt',
    'verify_jwt',
    'decode_jwt_unsafe',
    'compute_jwk_thumbprint',
    'generate_code_verifier',
    'compute_s256_challenge',
    '_AUTHORIZE_PATH',
    '_TOKEN_PATH',
    '_OAUTH_METADATA_PATH',
    '_DPOP_NONCE_HEADER',
    '_DPOP_HEADER',
    '_AUTHORIZATION_HEADER',
]


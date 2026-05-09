from __future__ import annotations

import hmac
import secrets
import time
from typing import Any, Optional

from teaagent.oauth21._dpop import _verify_dpop_signature
from teaagent.oauth21._jwt import (
    compute_jwk_thumbprint,
    create_jwt,
    decode_jwt_unsafe,
    verify_jwt,
)
from teaagent.oauth21._pkce import compute_s256_challenge
from teaagent.oauth21._store import InMemoryOAuthStore, OAuthKeyRing, OAuthStore
from teaagent.oauth21._types import (
    _CODE_TTL_SECONDS,
    _DEFAULT_ACCESS_TOKEN_TTL,
    _DPOP_PROOF_TYP,
    _NONCE_TTL_SECONDS,
    _PROOF_MAX_AGE_SECONDS,
    _TOKEN_TYPE_BEARER,
    _TOKEN_TYPE_DPOP,
    HAS_CRYPTOGRAPHY,
    InvalidClientError,
    InvalidDPoPError,
    InvalidGrantError,
    OAuth21Client,
    OAuth21Error,
    OAuth21TokenClaims,
    OAuth21TokenResponse,
    _AuthorizationCode,
)


class OAuth21AuthorizationServer:
    def __init__(
        self,
        signing_key: str,
        issuer: str,
        *,
        token_ttl: int = _DEFAULT_ACCESS_TOKEN_TTL,
        nonce_ttl: int = _NONCE_TTL_SECONDS,
        store: Optional[OAuthStore] = None,
        key_ring: Optional[OAuthKeyRing] = None,
    ) -> None:
        if not signing_key or len(signing_key) < 16:
            raise ValueError('signing_key must be at least 16 characters')
        self._key = signing_key.encode('utf-8')
        self._key_ring = key_ring or OAuthKeyRing.single(self._key)
        self._issuer = issuer
        self._token_ttl = token_ttl
        self._nonce_ttl = nonce_ttl
        self._store = store or InMemoryOAuthStore()

    def register_client(
        self,
        client_id: str,
        client_secret: str,
        redirect_uris: list[str],
        *,
        scope: str = 'mcp',
    ) -> OAuth21Client:
        if self._store.get_client(client_id) is not None:
            raise InvalidClientError(f"Client '{client_id}' already registered")
        client = OAuth21Client(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uris=frozenset(redirect_uris),
            scope=scope,
        )
        self._store.register_client(client)
        return client

    def get_client(self, client_id: str) -> OAuth21Client:
        try:
            client = self._store.get_client(client_id)
            if client is not None:
                return client
        except Exception as exc:
            raise InvalidClientError(f"Unknown client '{client_id}'") from exc
        raise InvalidClientError(f"Unknown client '{client_id}'")

    @property
    def issuer(self) -> str:
        return self._issuer

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
        client = self.get_client(client_id)
        if not client.validate_redirect_uri(redirect_uri):
            raise InvalidClientError(
                f"Redirect URI '{redirect_uri}' not registered for client '{client_id}'"
            )
        if code_challenge_method != 'S256':
            raise OAuth21Error(
                f"Unsupported code_challenge_method: '{code_challenge_method}'. "
                'Only S256 is supported.'
            )

        code = secrets.token_urlsafe(32)
        self._store.save_code(
            _AuthorizationCode(
                code=code,
                client_id=client_id,
                redirect_uri=redirect_uri,
                code_challenge=code_challenge,
                code_challenge_method=code_challenge_method,
                expires_at=time.time() + _CODE_TTL_SECONDS,
                scope=scope,
            )
        )
        self._prune_expired_codes()

        redirect_url = redirect_uri
        separator = '&' if '?' in redirect_uri else '?'
        redirect_url += f'{separator}code={code}'
        if state:
            redirect_url += f'&state={state}'
        return redirect_url, state

    def exchange_code(
        self,
        code: str,
        code_verifier: str,
        *,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        dpop_proof_jwt: Optional[str] = None,
    ) -> OAuth21TokenResponse:
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
        access_token = create_jwt(
            payload,
            self._key_ring.active_key,
            header_extra={'kid': self._key_ring.active_kid},
        )

        return OAuth21TokenResponse(
            access_token=access_token,
            token_type=token_type,
            expires_in=self._token_ttl,
            scope=auth_code.scope,
        )

    def introspect_token(self, token: str) -> OAuth21TokenClaims:
        header, _ = decode_jwt_unsafe(token)
        kid = header.get('kid')
        key = self._key_ring.key_for(kid if isinstance(kid, str) else None)
        payload = verify_jwt(token, key, iss=self._issuer)
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

    def generate_dpop_nonce(self) -> str:
        nonce = secrets.token_urlsafe(24)
        self._store.save_nonce(nonce, time.time())
        self._prune_nonces()
        return nonce

    def validate_dpop_nonce(self, nonce: str) -> bool:
        created = self._store.consume_nonce(nonce)
        if created is None:
            return False
        return time.time() - created <= self._nonce_ttl

    def metadata(self) -> dict[str, Any]:
        return {
            'issuer': self._issuer,
            'authorization_endpoint': f'{self._issuer}/authorize',
            'token_endpoint': f'{self._issuer}/token',
            'token_endpoint_auth_methods_supported': [
                'client_secret_basic',
                'none',
            ],
            'code_challenge_methods_supported': ['S256'],
            'dpop_signing_alg_values_supported': (
                ['ES256', 'ES384', 'ES512', 'RS256'] if HAS_CRYPTOGRAPHY else []
            ),
            'grant_types_supported': ['authorization_code'],
            'response_types_supported': ['code'],
        }

    def _consume_code(self, code: str) -> _AuthorizationCode:
        auth_code = self._store.consume_code(code)
        if auth_code is None:
            raise InvalidGrantError('Unknown or already-used authorization code')
        if auth_code.expires_at < time.time():
            raise InvalidGrantError('Authorization code expired')
        return auth_code

    def _validate_pkce(self, auth_code: _AuthorizationCode, code_verifier: str) -> None:
        challenge = compute_s256_challenge(code_verifier)
        if not hmac.compare_digest(
            challenge.encode(), auth_code.code_challenge.encode()
        ):
            raise InvalidGrantError('Invalid code_verifier: PKCE challenge mismatch')

    def _validate_client(self, client_id: str, client_secret: Optional[str]) -> None:
        client = self.get_client(client_id)
        if client_secret is None:
            return
        validator = getattr(self._store, 'validate_client_secret', None)
        if callable(validator):
            if not validator(client_id, client_secret):
                raise InvalidClientError('Invalid client_secret')
            return
        if not hmac.compare_digest(
            client_secret.encode('utf-8'), client.client_secret.encode('utf-8')
        ):
            raise InvalidClientError('Invalid client_secret')

    def _validate_dpop_and_extract_jkt(self, proof_jwt: str) -> str:
        header, payload = decode_jwt_unsafe(proof_jwt)
        if header.get('typ') != _DPOP_PROOF_TYP:
            raise InvalidDPoPError(f"DPoP proof typ must be '{_DPOP_PROOF_TYP}'")
        jwk = header.get('jwk')
        if not isinstance(jwk, dict):
            raise InvalidDPoPError('DPoP proof header must include a jwk')
        _verify_dpop_signature(proof_jwt, jwk)
        iat = payload.get('iat', 0)
        if abs(time.time() - iat) > _PROOF_MAX_AGE_SECONDS:
            raise InvalidDPoPError('DPoP proof is too old')
        return compute_jwk_thumbprint(jwk)

    def _prune_expired_codes(self) -> None:
        now = time.time()
        self._store.prune(now=now, code_ttl_cutoff=now, nonce_ttl=self._nonce_ttl)

    def _prune_nonces(self) -> None:
        now = time.time()
        self._store.prune(now=now, code_ttl_cutoff=now, nonce_ttl=self._nonce_ttl)

"""Bearer token auth and per-tenant authorization for HTTP surfaces."""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Union

HeaderMap = Mapping[str, Union[str, None]]


def normalize_http_headers(headers: Any) -> dict[str, str]:
    """Coerce stdlib HTTP headers to a plain string map for auth checks."""
    return {str(key): str(value) for key, value in headers.items() if value is not None}


logger = logging.getLogger(__name__)

ADMIN_TENANT_WILDCARD = '*'


def is_loopback_host(host: str) -> bool:
    """Return True for local-only bind addresses."""
    normalized = host.strip().lower()
    return normalized in {'127.0.0.1', 'localhost', '::1', '[::1]'}


def hash_token(raw: str) -> str:
    """Hash a token using PBKDF2 with a fixed salt for backward compatibility.

    Note: For new token storage, use hash_token_with_salt() which returns
    both the hash and salt for stronger security.
    """
    # Use a fixed salt for backward compatibility with existing tokens
    salt = b'teaagent-fixed-salt-v1'
    hash_obj = hashlib.pbkdf2_hmac('sha256', raw.encode('utf-8'), salt, 100000)
    return hash_obj.hex()


def hash_token_with_salt(raw: str) -> tuple[str, str]:
    """Hash a token using PBKDF2 with a random salt for stronger security.

    Returns:
        Tuple of (hash_hex, salt_hex) for storage
    """
    salt = secrets.token_bytes(16)
    hash_obj = hashlib.pbkdf2_hmac('sha256', raw.encode('utf-8'), salt, 100000)
    return hash_obj.hex(), salt.hex()


def verify_token_with_salt(raw: str, hash_hex: str, salt_hex: str) -> bool:
    """Verify a token against a salted hash.

    Args:
        raw: The raw token to verify
        hash_hex: The stored hash as hex string
        salt_hex: The stored salt as hex string

    Returns:
        True if the token matches, False otherwise
    """
    salt = bytes.fromhex(salt_hex)
    expected = hashlib.pbkdf2_hmac('sha256', raw.encode('utf-8'), salt, 100000)
    return secrets.compare_digest(expected.hex(), hash_hex)


def extract_bearer_token(headers: HeaderMap) -> str | None:
    """Parse ``Authorization: Bearer`` or ``X-TeaAgent-Token``."""
    auth = (headers.get('Authorization') or '').strip()
    if auth.lower().startswith('bearer '):
        return auth[7:].strip()
    relay = (headers.get('X-TeaAgent-Relay-Token') or '').strip()
    if relay:
        return relay
    plane = (headers.get('X-TeaAgent-Token') or '').strip()
    return plane or None


@dataclass(frozen=True)
class TokenEntry:
    """Hashed token with optional tenant scope (``None`` = admin / relay-global)."""

    token_hash: str
    tenants: frozenset[str] | None = None


@dataclass
class SurfaceAuthPolicy:
    """Resolved bearer policies for vote relay or control plane."""

    entries: list[TokenEntry] = field(default_factory=list)
    require_auth: bool = True

    def validate_token(self, raw_token: str) -> bool:
        digest = hash_token(raw_token)
        return any(
            secrets.compare_digest(digest, entry.token_hash) for entry in self.entries
        )

    def allowed_tenants(self, raw_token: str) -> frozenset[str] | None:
        """Return allowed tenant ids, ``None`` for admin (all tenants), empty if invalid."""
        digest = hash_token(raw_token)
        for entry in self.entries:
            if secrets.compare_digest(digest, entry.token_hash):
                return entry.tenants
        return frozenset()

    def can_access_tenant(self, raw_token: str, tenant_id: str) -> bool:
        scope = self.allowed_tenants(raw_token)
        if scope is None:
            return True
        if not scope:
            return False
        return ADMIN_TENANT_WILDCARD in scope or tenant_id in scope

    def is_admin(self, raw_token: str) -> bool:
        scope = self.allowed_tenants(raw_token)
        return scope is None or ADMIN_TENANT_WILDCARD in scope

    @classmethod
    def from_single_token(
        cls, raw_token: str, *, tenants: frozenset[str] | None = None
    ) -> SurfaceAuthPolicy:
        return cls(
            entries=[TokenEntry(token_hash=hash_token(raw_token), tenants=tenants)],
            require_auth=True,
        )

    @classmethod
    def from_token_file(
        cls, path: Path, *, relay_mode: bool = False
    ) -> SurfaceAuthPolicy:
        data = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(data, dict):
            raise ValueError('token file must be a JSON object')
        entries: list[TokenEntry] = []
        for index, item in enumerate(data.get('tokens', [])):
            if not isinstance(item, dict) or 'token' not in item:
                raise ValueError(f'tokens[{index}] must include "token"')
            raw = str(item['token'])
            tenants: frozenset[str] | None
            if relay_mode:
                tenants = None
            elif 'tenants' in item:
                raw_tenants = item['tenants']
                if not isinstance(raw_tenants, list):
                    raise ValueError(f'tokens[{index}].tenants must be a list')
                if ADMIN_TENANT_WILDCARD in raw_tenants:
                    tenants = None
                else:
                    tenants = frozenset(str(t) for t in raw_tenants)
            else:
                tenants = frozenset()
            entries.append(TokenEntry(token_hash=hash_token(raw), tenants=tenants))
        if not entries:
            raise ValueError('token file must define at least one token')
        return cls(entries=entries, require_auth=True)


def default_relay_token_file() -> Path | None:
    """Discover optional local relay token file (loopback hardening)."""
    import os

    env_path = os.environ.get('TEAAGENT_RELAY_TOKEN_FILE', '').strip()
    if env_path:
        path = Path(env_path)
        return path if path.is_file() else None
    for candidate in (
        Path('.teaagent/relay-tokens.json'),
        Path.home() / '.teaagent' / 'relay-tokens.json',
    ):
        if candidate.is_file():
            return candidate
    return None


def load_surface_auth_policy(
    *,
    api_token: str | None = None,
    api_token_file: Path | None = None,
    relay_mode: bool = False,
) -> SurfaceAuthPolicy | None:
    """Load policy from CLI flags; returns ``None`` when auth is disabled."""
    if api_token_file is None and relay_mode:
        api_token_file = default_relay_token_file()
    if api_token_file is not None:
        return SurfaceAuthPolicy.from_token_file(api_token_file, relay_mode=relay_mode)
    if api_token:
        return SurfaceAuthPolicy.from_single_token(
            api_token, tenants=None if relay_mode else None
        )
    return None


def authorize_request(
    policy: SurfaceAuthPolicy | None,
    headers: HeaderMap,
    *,
    tenant_id: str | None = None,
    require_admin: bool = False,
) -> tuple[bool, str]:
    """Check bearer token and optional tenant scope."""
    if policy is None or not policy.require_auth:
        return True, ''
    token = extract_bearer_token(headers)
    if not token:
        return False, 'missing bearer token'
    if not policy.validate_token(token):
        return False, 'invalid bearer token'
    if require_admin and not policy.is_admin(token):
        return False, 'admin token required'
    if tenant_id is not None and not policy.can_access_tenant(token, tenant_id):
        return False, f'token not authorized for tenant {tenant_id!r}'
    return True, ''

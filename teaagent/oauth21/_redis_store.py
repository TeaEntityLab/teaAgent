from __future__ import annotations

import hmac
import json
import time
from typing import Any, Optional

from teaagent.oauth21._store import (
    _CLIENT_SECRET_KDF,
    _hash_client_secret,
    _hash_client_secret_with_salt,
)
from teaagent.oauth21._types import OAuth21Client, _AuthorizationCode

try:
    import redis as _redis_mod

    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False

# Atomic get-and-delete via Lua — works on all Redis versions.
_LUA_CONSUME = """
local val = redis.call('GET', KEYS[1])
if val then
    redis.call('DEL', KEYS[1])
end
return val
"""


class RedisOAuthStore:
    """Cross-host OAuthStore backed by Redis.

    Clients, auth codes, and nonces are stored as JSON strings. Auth codes
    carry a TTL matching their expiry. Nonces carry a fixed TTL supplied at
    construction time. Atomic consume uses a Lua script (GET + DEL in one
    round-trip) so one-time semantics hold across multiple hosts.

    Args:
        url: Redis connection URL (default 'redis://localhost:6379').
        nonce_ttl: Seconds before a nonce expires (default 300).
        key_prefix: Namespace prefix for all Redis keys (default 'oauth:').
        _client: Pre-built Redis client for testing; omit in production.
    """

    def __init__(
        self,
        url: str = 'redis://localhost:6379',
        *,
        nonce_ttl: int = 300,
        key_prefix: str = 'oauth:',
        _client: Any | None = None,
    ) -> None:
        if _client is None and not HAS_REDIS:
            raise ImportError(
                'Redis OAuthStore requires redis-py. '
                'Install with: pip install teaagent[oauth-redis]'
            )
        self._nonce_ttl = nonce_ttl
        self._key_prefix = key_prefix
        if _client is not None:
            self._redis = _client
        else:
            self._redis = _redis_mod.Redis.from_url(url, decode_responses=True)
        self._consume_script = self._redis.register_script(_LUA_CONSUME)

    def _k(self, kind: str, ident: str) -> str:
        return f'{self._key_prefix}{kind}:{ident}'

    def register_client(self, client: OAuth21Client) -> None:
        secret_hash, salt = _hash_client_secret(client.client_secret)
        data = json.dumps(
            {
                'client_id': client.client_id,
                'client_secret_hash': secret_hash.hex(),
                'client_secret_salt': salt.hex(),
                'client_secret_kdf': _CLIENT_SECRET_KDF,
                'redirect_uris': sorted(client.redirect_uris),
                'scope': client.scope,
            }
        )
        self._redis.set(self._k('client', client.client_id), data)

    def get_client(self, client_id: str) -> Optional[OAuth21Client]:
        raw = self._redis.get(self._k('client', client_id))
        if raw is None:
            return None
        data = json.loads(raw)
        return OAuth21Client(
            client_id=data['client_id'],
            client_secret='',
            redirect_uris=frozenset(data['redirect_uris']),
            scope=data['scope'],
        )

    def validate_client_secret(self, client_id: str, client_secret: str) -> bool:
        raw = self._redis.get(self._k('client', client_id))
        if raw is None:
            return False
        data = json.loads(raw)
        if data.get('client_secret_kdf') != _CLIENT_SECRET_KDF:
            return False
        expected = bytes.fromhex(data['client_secret_hash'])
        salt = bytes.fromhex(data['client_secret_salt'])
        actual = _hash_client_secret_with_salt(client_secret, salt)
        return hmac.compare_digest(actual, expected)

    def save_code(self, code: _AuthorizationCode) -> None:
        data = json.dumps(
            {
                'code': code.code,
                'client_id': code.client_id,
                'redirect_uri': code.redirect_uri,
                'code_challenge': code.code_challenge,
                'code_challenge_method': code.code_challenge_method,
                'expires_at': code.expires_at,
                'scope': code.scope,
            }
        )
        ttl = max(1, int(code.expires_at - time.time()))
        # NX: do not overwrite an already-saved code (idempotent save).
        self._redis.set(self._k('code', code.code), data, ex=ttl, nx=True)

    def consume_code(self, code: str) -> Optional[_AuthorizationCode]:
        raw = self._consume_script(keys=[self._k('code', code)])
        if raw is None:
            return None
        data = json.loads(raw)
        return _AuthorizationCode(
            code=data['code'],
            client_id=data['client_id'],
            redirect_uri=data['redirect_uri'],
            code_challenge=data['code_challenge'],
            code_challenge_method=data['code_challenge_method'],
            expires_at=float(data['expires_at']),
            scope=data['scope'],
        )

    def save_nonce(self, nonce: str, created_at: float) -> None:
        self._redis.set(
            self._k('nonce', nonce),
            str(created_at),
            ex=self._nonce_ttl,
            nx=True,
        )

    def get_nonce(self, nonce: str) -> Optional[float]:
        raw = self._redis.get(self._k('nonce', nonce))
        return float(raw) if raw is not None else None

    def consume_nonce(self, nonce: str) -> Optional[float]:
        raw = self._consume_script(keys=[self._k('nonce', nonce)])
        return float(raw) if raw is not None else None

    def delete_nonce(self, nonce: str) -> None:
        self._redis.delete(self._k('nonce', nonce))

    def prune(self, *, now: float, code_ttl_cutoff: float, nonce_ttl: float) -> None:
        # Redis TTL handles expiration automatically; explicit prune is a no-op.
        pass

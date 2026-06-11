from __future__ import annotations

import json
import time
from typing import Any, Optional

import pytest

from teaagent.oauth21._redis_store import RedisOAuthStore
from teaagent.oauth21._types import OAuth21Client, _AuthorizationCode

# ---------------------------------------------------------------------------
# Minimal in-memory fake Redis client.
# ---------------------------------------------------------------------------


class _FakeRedis:
    """Implements the redis-py subset used by RedisOAuthStore."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self._scripts: list['_FakeScript'] = []

    def set(
        self,
        key: str,
        value: str,
        ex: Optional[int] = None,
        nx: bool = False,
    ) -> Optional[bool]:
        if nx and key in self._store:
            return None
        self._store[key] = value
        return True

    def get(self, key: str) -> Optional[str]:
        return self._store.get(key)

    def delete(self, *keys: str) -> int:
        removed = 0
        for key in keys:
            if key in self._store:
                del self._store[key]
                removed += 1
        return removed

    def register_script(self, script: str) -> '_FakeScript':
        fake = _FakeScript(self, script)
        self._scripts.append(fake)
        return fake


class _FakeScript:
    """Simulates the Lua GET-then-DEL script."""

    def __init__(self, redis: _FakeRedis, script: str) -> None:
        self._redis = redis

    def __call__(
        self, keys: list[str], args: Optional[list[Any]] = None
    ) -> Optional[str]:
        if args is None:
            args = []
        key = keys[0]
        val = self._redis.get(key)
        if val is not None:
            self._redis.delete(key)
        return val


def _make_store() -> RedisOAuthStore:
    return RedisOAuthStore(_client=_FakeRedis())


def _make_code(
    code: str = 'code-1', expires_at: Optional[float] = None
) -> _AuthorizationCode:
    return _AuthorizationCode(
        code=code,
        client_id='client-1',
        redirect_uri='https://client.example/cb',
        code_challenge='challenge',
        code_challenge_method='S256',
        expires_at=expires_at if expires_at is not None else time.time() + 600,
        scope='mcp',
    )


def test_redis_oauth_store_import_guard_raises_import_error_without_redis() -> None:
    import teaagent.oauth21._redis_store as redis_mod

    original = redis_mod.HAS_REDIS
    try:
        redis_mod.HAS_REDIS = False
        with pytest.raises(ImportError):
            RedisOAuthStore()
    finally:
        redis_mod.HAS_REDIS = original


def test_redis_oauth_store_import_guard_client_injection_bypasses_import_check() -> (
    None
):
    store = RedisOAuthStore(_client=_FakeRedis())
    assert store is not None


def test_redis_oauth_store_client_register_and_get_client() -> None:
    store = _make_store()
    client = OAuth21Client(
        client_id='c1',
        client_secret='secret-1',
        redirect_uris=frozenset(['https://client.example/cb']),
        scope='mcp',
    )
    store.register_client(client)
    retrieved = store.get_client('c1')
    assert retrieved is not None
    assert retrieved.client_id == 'c1'
    assert 'https://client.example/cb' in retrieved.redirect_uris
    assert retrieved.scope == 'mcp'


def test_redis_oauth_store_client_get_missing_client_returns_none() -> None:
    store = _make_store()
    assert store.get_client('no-such') is None


def test_redis_oauth_store_client_validate_client_secret_correct() -> None:
    store = _make_store()
    store.register_client(OAuth21Client('c1', 'my-secret', frozenset(['https://x/cb'])))
    assert store.validate_client_secret('c1', 'my-secret')


def test_redis_oauth_store_client_validate_client_secret_wrong() -> None:
    store = _make_store()
    store.register_client(OAuth21Client('c1', 'my-secret', frozenset(['https://x/cb'])))
    assert not store.validate_client_secret('c1', 'wrong')


def test_redis_oauth_store_client_validate_client_secret_unknown_client() -> None:
    store = _make_store()
    assert not store.validate_client_secret('no-such', 'anything')


def test_redis_oauth_store_client_secret_stored_as_hex_not_plaintext() -> None:
    fake = _FakeRedis()
    store = RedisOAuthStore(_client=fake)
    store.register_client(
        OAuth21Client('c1', 'plain-secret', frozenset(['https://x/cb']))
    )
    raw = fake.get('oauth:client:c1')
    assert raw is not None
    data = json.loads(raw)
    assert 'plain-secret' not in data.get('client_secret_hash', '')


def test_redis_oauth_store_client_register_client_overwrites_existing() -> None:
    store = _make_store()
    store.register_client(
        OAuth21Client('c1', 'old-secret', frozenset(['https://a/cb']))
    )
    store.register_client(
        OAuth21Client('c1', 'new-secret', frozenset(['https://b/cb']))
    )
    assert store.validate_client_secret('c1', 'new-secret')
    assert not store.validate_client_secret('c1', 'old-secret')


def test_redis_oauth_store_code_save_and_consume_code() -> None:
    store = _make_store()
    code = _make_code()
    store.save_code(code)
    result = store.consume_code(code.code)
    assert result is not None
    assert result.code == code.code
    assert result.client_id == 'client-1'
    assert result.scope == 'mcp'


def test_redis_oauth_store_code_consume_is_one_time() -> None:
    store = _make_store()
    code = _make_code()
    store.save_code(code)
    assert store.consume_code(code.code) is not None
    assert store.consume_code(code.code) is None


def test_redis_oauth_store_code_consume_missing_code_returns_none() -> None:
    store = _make_store()
    assert store.consume_code('no-such-code') is None


def test_redis_oauth_store_code_save_code_nx_does_not_overwrite() -> None:
    store = _make_store()
    original = _make_code('c1')
    duplicate = _make_code('c1')
    assert duplicate.client_id == original.client_id  # ensure it's the same key
    store.save_code(original)
    # Saving again should be a no-op (NX flag)
    store.save_code(
        _AuthorizationCode(
            code='c1',
            client_id='OTHER',
            redirect_uri='https://other/cb',
            code_challenge='x',
            code_challenge_method='S256',
            expires_at=time.time() + 600,
            scope='other',
        )
    )
    result = store.consume_code('c1')
    assert result is not None
    assert result.client_id == 'client-1'


def test_redis_oauth_store_code_prune_is_noop() -> None:
    store = _make_store()
    code = _make_code()
    store.save_code(code)
    store.prune(now=time.time(), code_ttl_cutoff=time.time() + 9999, nonce_ttl=1)
    assert store.consume_code(code.code) is not None


def test_redis_oauth_store_nonce_save_and_get_nonce() -> None:
    store = _make_store()
    store.save_nonce('n1', 1000.0)
    assert store.get_nonce('n1') == 1000.0


def test_redis_oauth_store_nonce_get_missing_nonce_returns_none() -> None:
    store = _make_store()
    assert store.get_nonce('no-such') is None


def test_redis_oauth_store_nonce_consume_nonce_is_one_time() -> None:
    store = _make_store()
    store.save_nonce('n1', time.time())
    assert store.consume_nonce('n1') is not None
    assert store.consume_nonce('n1') is None


def test_redis_oauth_store_nonce_delete_nonce() -> None:
    store = _make_store()
    store.save_nonce('n1', time.time())
    store.delete_nonce('n1')
    assert store.get_nonce('n1') is None


def test_redis_oauth_store_nonce_save_nonce_nx_preserves_original() -> None:
    store = _make_store()
    store.save_nonce('n1', 1000.0)
    store.save_nonce('n1', 9999.0)
    assert store.get_nonce('n1') == 1000.0


def test_redis_oauth_store_nonce_key_prefix_applied() -> None:
    fake = _FakeRedis()
    store = RedisOAuthStore(_client=fake, key_prefix='myapp:')
    store.save_nonce('n1', 1000.0)
    assert 'myapp:nonce:n1' in fake._store
    assert 'oauth:nonce:n1' not in fake._store


def test_redis_oauth_store_protocol_implements_oauth_store_protocol() -> None:
    store = _make_store()
    for method in (
        'register_client',
        'get_client',
        'save_code',
        'consume_code',
        'save_nonce',
        'get_nonce',
        'consume_nonce',
        'delete_nonce',
        'prune',
    ):
        assert hasattr(store, method), (
            f'RedisOAuthStore missing OAuthStore method: {method}'
        )

from __future__ import annotations

import json
import time
import unittest
from typing import Any, Optional

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


class RedisOAuthStoreImportGuardTests(unittest.TestCase):
    def test_raises_import_error_without_redis(self) -> None:
        import teaagent.oauth21._redis_store as redis_mod

        original = redis_mod.HAS_REDIS
        try:
            redis_mod.HAS_REDIS = False
            with self.assertRaises(ImportError):
                RedisOAuthStore()
        finally:
            redis_mod.HAS_REDIS = original

    def test_client_injection_bypasses_import_check(self) -> None:
        store = RedisOAuthStore(_client=_FakeRedis())
        self.assertIsNotNone(store)


class RedisOAuthStoreClientTests(unittest.TestCase):
    def test_register_and_get_client(self) -> None:
        store = _make_store()
        client = OAuth21Client(
            client_id='c1',
            client_secret='secret-1',
            redirect_uris=frozenset(['https://client.example/cb']),
            scope='mcp',
        )
        store.register_client(client)
        retrieved = store.get_client('c1')
        self.assertIsNotNone(retrieved)
        assert retrieved is not None
        self.assertEqual(retrieved.client_id, 'c1')
        self.assertIn('https://client.example/cb', retrieved.redirect_uris)
        self.assertEqual(retrieved.scope, 'mcp')

    def test_get_missing_client_returns_none(self) -> None:
        store = _make_store()
        self.assertIsNone(store.get_client('no-such'))

    def test_validate_client_secret_correct(self) -> None:
        store = _make_store()
        store.register_client(
            OAuth21Client('c1', 'my-secret', frozenset(['https://x/cb']))
        )
        self.assertTrue(store.validate_client_secret('c1', 'my-secret'))

    def test_validate_client_secret_wrong(self) -> None:
        store = _make_store()
        store.register_client(
            OAuth21Client('c1', 'my-secret', frozenset(['https://x/cb']))
        )
        self.assertFalse(store.validate_client_secret('c1', 'wrong'))

    def test_validate_client_secret_unknown_client(self) -> None:
        store = _make_store()
        self.assertFalse(store.validate_client_secret('no-such', 'anything'))

    def test_secret_stored_as_hex_not_plaintext(self) -> None:
        fake = _FakeRedis()
        store = RedisOAuthStore(_client=fake)
        store.register_client(
            OAuth21Client('c1', 'plain-secret', frozenset(['https://x/cb']))
        )
        raw = fake.get('oauth:client:c1')
        self.assertIsNotNone(raw)
        assert raw is not None
        data = json.loads(raw)
        self.assertNotIn('plain-secret', data.get('client_secret_hash', ''))

    def test_register_client_overwrites_existing(self) -> None:
        store = _make_store()
        store.register_client(
            OAuth21Client('c1', 'old-secret', frozenset(['https://a/cb']))
        )
        store.register_client(
            OAuth21Client('c1', 'new-secret', frozenset(['https://b/cb']))
        )
        self.assertTrue(store.validate_client_secret('c1', 'new-secret'))
        self.assertFalse(store.validate_client_secret('c1', 'old-secret'))


class RedisOAuthStoreCodeTests(unittest.TestCase):
    def test_save_and_consume_code(self) -> None:
        store = _make_store()
        code = _make_code()
        store.save_code(code)
        result = store.consume_code(code.code)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.code, code.code)
        self.assertEqual(result.client_id, 'client-1')
        self.assertEqual(result.scope, 'mcp')

    def test_consume_is_one_time(self) -> None:
        store = _make_store()
        code = _make_code()
        store.save_code(code)
        self.assertIsNotNone(store.consume_code(code.code))
        self.assertIsNone(store.consume_code(code.code))

    def test_consume_missing_code_returns_none(self) -> None:
        store = _make_store()
        self.assertIsNone(store.consume_code('no-such-code'))

    def test_save_code_nx_does_not_overwrite(self) -> None:
        store = _make_store()
        original = _make_code('c1')
        duplicate = _make_code('c1')
        self.assertEqual(
            duplicate.client_id, original.client_id
        )  # ensure it's the same key
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
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.client_id, 'client-1')

    def test_prune_is_noop(self) -> None:
        store = _make_store()
        code = _make_code()
        store.save_code(code)
        store.prune(now=time.time(), code_ttl_cutoff=time.time() + 9999, nonce_ttl=1)
        self.assertIsNotNone(store.consume_code(code.code))


class RedisOAuthStoreNonceTests(unittest.TestCase):
    def test_save_and_get_nonce(self) -> None:
        store = _make_store()
        store.save_nonce('n1', 1000.0)
        self.assertEqual(store.get_nonce('n1'), 1000.0)

    def test_get_missing_nonce_returns_none(self) -> None:
        store = _make_store()
        self.assertIsNone(store.get_nonce('no-such'))

    def test_consume_nonce_is_one_time(self) -> None:
        store = _make_store()
        store.save_nonce('n1', time.time())
        self.assertIsNotNone(store.consume_nonce('n1'))
        self.assertIsNone(store.consume_nonce('n1'))

    def test_delete_nonce(self) -> None:
        store = _make_store()
        store.save_nonce('n1', time.time())
        store.delete_nonce('n1')
        self.assertIsNone(store.get_nonce('n1'))

    def test_save_nonce_nx_preserves_original(self) -> None:
        store = _make_store()
        store.save_nonce('n1', 1000.0)
        store.save_nonce('n1', 9999.0)
        self.assertEqual(store.get_nonce('n1'), 1000.0)

    def test_key_prefix_applied(self) -> None:
        fake = _FakeRedis()
        store = RedisOAuthStore(_client=fake, key_prefix='myapp:')
        store.save_nonce('n1', 1000.0)
        self.assertIn('myapp:nonce:n1', fake._store)
        self.assertNotIn('oauth:nonce:n1', fake._store)


class RedisOAuthStoreProtocolTests(unittest.TestCase):
    def test_implements_oauth_store_protocol(self) -> None:

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
            self.assertTrue(
                hasattr(store, method),
                f'RedisOAuthStore missing OAuthStore method: {method}',
            )


if __name__ == '__main__':
    unittest.main()

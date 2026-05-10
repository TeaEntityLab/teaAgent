from __future__ import annotations

import time
import unittest
from typing import Any, Optional

from teaagent.oauth21._pg_store import PostgreSQLOAuthStore
from teaagent.oauth21._types import OAuth21Client, _AuthorizationCode

# ---------------------------------------------------------------------------
# Minimal in-memory fake that speaks the DB-API 2.0 subset we use.
# ---------------------------------------------------------------------------


class _FakeCursor:
    def __init__(self, store: _FakeDB) -> None:
        self._store = store
        self._result: Optional[tuple] = None

    def execute(self, sql: str, params: tuple = ()) -> None:
        self._result = self._store.execute(sql, params)

    def fetchone(self) -> Optional[tuple]:
        return self._result

    def __enter__(self) -> '_FakeCursor':
        return self

    def __exit__(self, *_: Any) -> None:
        pass


class _FakeConn:
    def __init__(self, store: '_FakeDB') -> None:
        self._store = store

    def cursor(self) -> _FakeCursor:
        return _FakeCursor(self._store)

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass

    def close(self) -> None:
        pass

    def __enter__(self) -> '_FakeConn':
        return self

    def __exit__(self, *_: Any) -> None:
        pass


class _FakeDB:
    """Minimal SQL interpreter supporting the subset used by PostgreSQLOAuthStore."""

    def __init__(self) -> None:
        self.clients: dict[str, dict] = {}
        self.codes: dict[str, dict] = {}
        self.nonces: dict[str, float] = {}

    def conn(self) -> _FakeConn:
        return _FakeConn(self)

    def execute(self, sql: str, params: tuple = ()) -> Optional[tuple]:  # noqa: C901
        sql = sql.strip()

        # Schema creation — no-op
        if sql.upper().startswith('CREATE TABLE') or sql.upper().startswith(
            'CREATE INDEX'
        ):
            return None

        # INSERT clients
        if 'INTO oauth_clients' in sql and 'INSERT' in sql.upper():
            client_id = params[0]
            self.clients[client_id] = {
                'client_id': client_id,
                'client_secret_hash': bytes(params[1]),
                'client_secret_salt': bytes(params[2]),
                'client_secret_kdf': params[3],
                'redirect_uris_json': params[4],
                'scope': params[5],
            }
            return None

        # SELECT client
        if 'FROM oauth_clients' in sql and 'SELECT' in sql.upper():
            client_id = params[0]
            row = self.clients.get(client_id)
            if row is None:
                return None
            if 'client_secret_hash' in sql:
                return (
                    row['client_secret_hash'],
                    row['client_secret_salt'],
                    row['client_secret_kdf'],
                )
            return (row['client_id'], row['redirect_uris_json'], row['scope'])

        # INSERT codes
        if 'INTO oauth_codes' in sql and 'INSERT' in sql.upper():
            code = params[0]
            self.codes[code] = {
                'code': code,
                'client_id': params[1],
                'redirect_uri': params[2],
                'code_challenge': params[3],
                'code_challenge_method': params[4],
                'expires_at': params[5],
                'scope': params[6],
            }
            return None

        # DELETE codes RETURNING
        if 'DELETE FROM oauth_codes' in sql and 'RETURNING' in sql.upper():
            code = params[0]
            row = self.codes.pop(code, None)
            if row is None:
                return None
            return (
                row['code'],
                row['client_id'],
                row['redirect_uri'],
                row['code_challenge'],
                row['code_challenge_method'],
                row['expires_at'],
                row['scope'],
            )

        # INSERT nonces
        if 'INTO oauth_nonces' in sql and 'INSERT' in sql.upper():
            nonce = params[0]
            if nonce not in self.nonces:
                self.nonces[nonce] = float(params[1])
            return None

        # SELECT nonce
        if 'FROM oauth_nonces' in sql and 'SELECT' in sql.upper():
            nonce = params[0]
            created = self.nonces.get(nonce)
            return (created,) if created is not None else None

        # DELETE nonce RETURNING
        if 'DELETE FROM oauth_nonces' in sql and 'RETURNING' in sql.upper():
            nonce = params[0]
            created = self.nonces.pop(nonce, None)
            return (created,) if created is not None else None

        # DELETE nonce (plain)
        if 'DELETE FROM oauth_nonces' in sql:
            nonce = params[0]
            self.nonces.pop(nonce, None)
            return None

        # DELETE codes (prune)
        if 'DELETE FROM oauth_codes' in sql:
            cutoff = params[0]
            expired = [c for c, row in self.codes.items() if row['expires_at'] < cutoff]
            for c in expired:
                del self.codes[c]
            return None

        return None


def _make_store() -> PostgreSQLOAuthStore:
    db = _FakeDB()
    return PostgreSQLOAuthStore('unused-dsn', _conn_factory=db.conn)


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


class PostgreSQLOAuthStoreImportGuardTests(unittest.TestCase):
    def test_raises_import_error_without_psycopg2(self) -> None:
        import teaagent.oauth21._pg_store as pg_mod

        original = pg_mod.HAS_PSYCOPG2
        try:
            pg_mod.HAS_PSYCOPG2 = False
            with self.assertRaises(ImportError):
                PostgreSQLOAuthStore('postgresql://localhost/test')
        finally:
            pg_mod.HAS_PSYCOPG2 = original

    def test_conn_factory_bypasses_import_check(self) -> None:
        db = _FakeDB()
        store = PostgreSQLOAuthStore('unused', _conn_factory=db.conn)
        self.assertIsNotNone(store)


class PostgreSQLOAuthStoreClientTests(unittest.TestCase):
    def test_register_and_get_client(self) -> None:
        store = _make_store()
        client = OAuth21Client(
            client_id='client-1',
            client_secret='secret-1',
            redirect_uris=frozenset(['https://client.example/cb']),
            scope='mcp',
        )
        store.register_client(client)
        retrieved = store.get_client('client-1')
        self.assertIsNotNone(retrieved)
        assert retrieved is not None
        self.assertEqual(retrieved.client_id, 'client-1')
        self.assertEqual(retrieved.scope, 'mcp')
        self.assertIn('https://client.example/cb', retrieved.redirect_uris)

    def test_get_missing_client_returns_none(self) -> None:
        store = _make_store()
        self.assertIsNone(store.get_client('no-such-client'))

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

    def test_client_secret_not_stored_in_plaintext(self) -> None:
        db = _FakeDB()
        store = PostgreSQLOAuthStore('unused', _conn_factory=db.conn)
        store.register_client(
            OAuth21Client('c1', 'plain-secret', frozenset(['https://x/cb']))
        )
        row = db.clients['c1']
        self.assertNotIn(b'plain-secret', row['client_secret_hash'])


class PostgreSQLOAuthStoreCodeTests(unittest.TestCase):
    def test_save_and_consume_code(self) -> None:
        store = _make_store()
        code = _make_code()
        store.save_code(code)
        result = store.consume_code(code.code)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.code, code.code)
        self.assertEqual(result.client_id, 'client-1')

    def test_consume_is_one_time(self) -> None:
        store = _make_store()
        code = _make_code()
        store.save_code(code)
        self.assertIsNotNone(store.consume_code(code.code))
        self.assertIsNone(store.consume_code(code.code))

    def test_consume_missing_code_returns_none(self) -> None:
        store = _make_store()
        self.assertIsNone(store.consume_code('no-such-code'))

    def test_prune_removes_expired_codes(self) -> None:
        store = _make_store()
        expired = _make_code('expired', expires_at=time.time() - 1)
        fresh = _make_code('fresh', expires_at=time.time() + 600)
        store.save_code(expired)
        store.save_code(fresh)
        store.prune(now=time.time(), code_ttl_cutoff=time.time(), nonce_ttl=300)
        self.assertIsNone(store.consume_code('expired'))
        self.assertIsNotNone(store.consume_code('fresh'))


class PostgreSQLOAuthStoreNonceTests(unittest.TestCase):
    def test_save_and_get_nonce(self) -> None:
        store = _make_store()
        store.save_nonce('nonce-1', 1000.0)
        self.assertEqual(store.get_nonce('nonce-1'), 1000.0)

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

    def test_save_nonce_idempotent(self) -> None:
        store = _make_store()
        store.save_nonce('n1', 1000.0)
        store.save_nonce('n1', 9999.0)
        self.assertEqual(store.get_nonce('n1'), 1000.0)


if __name__ == '__main__':
    unittest.main()

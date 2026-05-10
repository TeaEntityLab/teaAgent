from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any, Callable, Iterator, Optional

from teaagent.oauth21._store import (
    _CLIENT_SECRET_KDF,
    _hash_client_secret,
    _hash_client_secret_with_salt,
)
from teaagent.oauth21._types import OAuth21Client, _AuthorizationCode

try:
    import psycopg2
    import psycopg2.extras

    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

import hmac

_PG_SCHEMA = """
CREATE TABLE IF NOT EXISTS oauth_clients (
    client_id TEXT PRIMARY KEY,
    client_secret_hash BYTEA NOT NULL,
    client_secret_salt BYTEA NOT NULL,
    client_secret_kdf TEXT NOT NULL DEFAULT 'pbkdf2_sha256',
    redirect_uris_json TEXT NOT NULL,
    scope TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS oauth_codes (
    code TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    redirect_uri TEXT NOT NULL,
    code_challenge TEXT NOT NULL,
    code_challenge_method TEXT NOT NULL,
    expires_at DOUBLE PRECISION NOT NULL,
    scope TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_oauth_codes_expires_at ON oauth_codes (expires_at);

CREATE TABLE IF NOT EXISTS oauth_nonces (
    nonce TEXT PRIMARY KEY,
    created_at DOUBLE PRECISION NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_oauth_nonces_created_at ON oauth_nonces (created_at);
"""


class PostgreSQLOAuthStore:
    """Cross-host OAuthStore backed by PostgreSQL.

    Uses DELETE ... RETURNING for atomic one-time consume of auth codes and
    nonces, preserving one-time-use semantics across multiple processes and
    hosts sharing the same database.

    Args:
        dsn: libpq connection string or URL (e.g. 'postgresql://user:pw@host/db').
        _conn_factory: Optional callable returning a DB-API 2.0 connection.
            Intended for testing; omit in production.
    """

    def __init__(
        self,
        dsn: str,
        *,
        _conn_factory: Optional[Callable[[], Any]] = None,
    ) -> None:
        if _conn_factory is None and not HAS_PSYCOPG2:
            raise ImportError(
                'PostgreSQL OAuthStore requires psycopg2. '
                'Install with: pip install teaagent[oauth-pg]'
            )
        self._dsn = dsn
        self._conn_factory: Callable[[], Any] = _conn_factory or (
            lambda: psycopg2.connect(dsn)
        )
        self._initialize()

    @contextmanager
    def _conn(self) -> Iterator[Any]:
        conn = self._conn_factory()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _initialize(self) -> None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(_PG_SCHEMA)

    def register_client(self, client: OAuth21Client) -> None:
        secret_hash, salt = _hash_client_secret(client.client_secret)
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                    INSERT INTO oauth_clients
                        (client_id, client_secret_hash, client_secret_salt,
                         client_secret_kdf, redirect_uris_json, scope)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (client_id) DO UPDATE
                        SET client_secret_hash = EXCLUDED.client_secret_hash,
                            client_secret_salt = EXCLUDED.client_secret_salt,
                            redirect_uris_json = EXCLUDED.redirect_uris_json,
                            scope = EXCLUDED.scope
                    """,
                (
                    client.client_id,
                    secret_hash,
                    salt,
                    _CLIENT_SECRET_KDF,
                    json.dumps(sorted(client.redirect_uris)),
                    client.scope,
                ),
            )

    def get_client(self, client_id: str) -> Optional[OAuth21Client]:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                'SELECT client_id, redirect_uris_json, scope '
                'FROM oauth_clients WHERE client_id = %s',
                (client_id,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        redirect_uris = frozenset(str(u) for u in json.loads(row[1]))
        return OAuth21Client(
            client_id=str(row[0]),
            client_secret='',
            redirect_uris=redirect_uris,
            scope=str(row[2]),
        )

    def validate_client_secret(self, client_id: str, client_secret: str) -> bool:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                'SELECT client_secret_hash, client_secret_salt, client_secret_kdf '
                'FROM oauth_clients WHERE client_id = %s',
                (client_id,),
            )
            row = cur.fetchone()
        if row is None or row[2] != _CLIENT_SECRET_KDF:
            return False
        expected = bytes(row[0])
        salt = bytes(row[1])
        actual = _hash_client_secret_with_salt(client_secret, salt)
        return hmac.compare_digest(actual, expected)

    def save_code(self, code: _AuthorizationCode) -> None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                    INSERT INTO oauth_codes
                        (code, client_id, redirect_uri, code_challenge,
                         code_challenge_method, expires_at, scope)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (code) DO UPDATE SET expires_at = EXCLUDED.expires_at
                    """,
                (
                    code.code,
                    code.client_id,
                    code.redirect_uri,
                    code.code_challenge,
                    code.code_challenge_method,
                    code.expires_at,
                    code.scope,
                ),
            )

    def consume_code(self, code: str) -> Optional[_AuthorizationCode]:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                    DELETE FROM oauth_codes WHERE code = %s
                    RETURNING code, client_id, redirect_uri, code_challenge,
                              code_challenge_method, expires_at, scope
                    """,
                (code,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        return _AuthorizationCode(
            code=str(row[0]),
            client_id=str(row[1]),
            redirect_uri=str(row[2]),
            code_challenge=str(row[3]),
            code_challenge_method=str(row[4]),
            expires_at=float(row[5]),
            scope=str(row[6]),
        )

    def save_nonce(self, nonce: str, created_at: float) -> None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                'INSERT INTO oauth_nonces (nonce, created_at) VALUES (%s, %s) '
                'ON CONFLICT DO NOTHING',
                (nonce, created_at),
            )

    def get_nonce(self, nonce: str) -> Optional[float]:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                'SELECT created_at FROM oauth_nonces WHERE nonce = %s', (nonce,)
            )
            row = cur.fetchone()
        return float(row[0]) if row is not None else None

    def consume_nonce(self, nonce: str) -> Optional[float]:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                'DELETE FROM oauth_nonces WHERE nonce = %s RETURNING created_at',
                (nonce,),
            )
            row = cur.fetchone()
        return float(row[0]) if row is not None else None

    def delete_nonce(self, nonce: str) -> None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute('DELETE FROM oauth_nonces WHERE nonce = %s', (nonce,))

    def prune(self, *, now: float, code_ttl_cutoff: float, nonce_ttl: float) -> None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                'DELETE FROM oauth_codes WHERE expires_at < %s', (code_ttl_cutoff,)
            )
            cur.execute(
                'DELETE FROM oauth_nonces WHERE %s - created_at > %s',
                (now, nonce_ttl),
            )

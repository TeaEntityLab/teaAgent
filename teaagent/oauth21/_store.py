from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Protocol

from teaagent.oauth21._types import OAuth21Client, _AuthorizationCode


class OAuthStore(Protocol):
    def register_client(self, client: OAuth21Client) -> None: ...

    def get_client(self, client_id: str) -> Optional[OAuth21Client]: ...

    def save_code(self, code: _AuthorizationCode) -> None: ...

    def consume_code(self, code: str) -> Optional[_AuthorizationCode]: ...

    def save_nonce(self, nonce: str, created_at: float) -> None: ...

    def get_nonce(self, nonce: str) -> Optional[float]: ...

    def delete_nonce(self, nonce: str) -> None: ...

    def prune(
        self, *, now: float, code_ttl_cutoff: float, nonce_ttl: float
    ) -> None: ...


class InMemoryOAuthStore:
    def __init__(self) -> None:
        self.clients: dict[str, OAuth21Client] = {}
        self.codes: dict[str, _AuthorizationCode] = {}
        self.nonces: dict[str, float] = {}

    def register_client(self, client: OAuth21Client) -> None:
        self.clients[client.client_id] = client

    def get_client(self, client_id: str) -> Optional[OAuth21Client]:
        return self.clients.get(client_id)

    def save_code(self, code: _AuthorizationCode) -> None:
        self.codes[code.code] = code

    def consume_code(self, code: str) -> Optional[_AuthorizationCode]:
        return self.codes.pop(code, None)

    def save_nonce(self, nonce: str, created_at: float) -> None:
        self.nonces[nonce] = created_at

    def get_nonce(self, nonce: str) -> Optional[float]:
        return self.nonces.get(nonce)

    def delete_nonce(self, nonce: str) -> None:
        self.nonces.pop(nonce, None)

    def prune(self, *, now: float, code_ttl_cutoff: float, nonce_ttl: float) -> None:
        expired_codes = [c for c, ac in self.codes.items() if ac.expires_at < now]
        for code in expired_codes:
            del self.codes[code]
        expired_nonces = [
            nonce for nonce, created in self.nonces.items() if now - created > nonce_ttl
        ]
        for nonce in expired_nonces:
            del self.nonces[nonce]


class SQLiteOAuthStore:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()

    def register_client(self, client: OAuth21Client) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO oauth_clients
                    (client_id, client_secret, redirect_uris_json, scope)
                VALUES (?, ?, ?, ?)
                """,
                (
                    client.client_id,
                    client.client_secret,
                    json.dumps(sorted(client.redirect_uris), separators=(',', ':')),
                    client.scope,
                ),
            )

    def get_client(self, client_id: str) -> Optional[OAuth21Client]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT client_id, client_secret, redirect_uris_json, scope
                FROM oauth_clients
                WHERE client_id = ?
                """,
                (client_id,),
            ).fetchone()
        if row is None:
            return None
        redirect_uris = frozenset(str(uri) for uri in json.loads(row[2]))
        return OAuth21Client(
            client_id=str(row[0]),
            client_secret=str(row[1]),
            redirect_uris=redirect_uris,
            scope=str(row[3]),
        )

    def save_code(self, code: _AuthorizationCode) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO oauth_codes
                    (code, client_id, redirect_uri, code_challenge,
                     code_challenge_method, expires_at, scope)
                VALUES (?, ?, ?, ?, ?, ?, ?)
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
        with self._lock, self._connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute(
                """
                SELECT code, client_id, redirect_uri, code_challenge,
                       code_challenge_method, expires_at, scope
                FROM oauth_codes
                WHERE code = ?
                """,
                (code,),
            ).fetchone()
            if row is None:
                return None
            conn.execute('DELETE FROM oauth_codes WHERE code = ?', (code,))
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
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO oauth_nonces (nonce, created_at)
                VALUES (?, ?)
                """,
                (nonce, created_at),
            )

    def get_nonce(self, nonce: str) -> Optional[float]:
        with self._connect() as conn:
            row = conn.execute(
                'SELECT created_at FROM oauth_nonces WHERE nonce = ?',
                (nonce,),
            ).fetchone()
        if row is None:
            return None
        return float(row[0])

    def delete_nonce(self, nonce: str) -> None:
        with self._connect() as conn:
            conn.execute('DELETE FROM oauth_nonces WHERE nonce = ?', (nonce,))

    def prune(self, *, now: float, code_ttl_cutoff: float, nonce_ttl: float) -> None:
        with self._connect() as conn:
            conn.execute(
                'DELETE FROM oauth_codes WHERE expires_at < ?',
                (code_ttl_cutoff,),
            )
            conn.execute(
                'DELETE FROM oauth_nonces WHERE ? - created_at > ?',
                (now, nonce_ttl),
            )

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                PRAGMA journal_mode = WAL;
                CREATE TABLE IF NOT EXISTS oauth_clients (
                    client_id TEXT PRIMARY KEY,
                    client_secret TEXT NOT NULL,
                    redirect_uris_json TEXT NOT NULL,
                    scope TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS oauth_codes (
                    code TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    redirect_uri TEXT NOT NULL,
                    code_challenge TEXT NOT NULL,
                    code_challenge_method TEXT NOT NULL,
                    expires_at REAL NOT NULL,
                    scope TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_oauth_codes_expires_at
                    ON oauth_codes(expires_at);
                CREATE TABLE IF NOT EXISTS oauth_nonces (
                    nonce TEXT PRIMARY KEY,
                    created_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_oauth_nonces_created_at
                    ON oauth_nonces(created_at);
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        conn.execute('PRAGMA foreign_keys = ON')
        conn.execute('PRAGMA busy_timeout = 30000')
        return conn


@dataclass(frozen=True)
class OAuthKeyRing:
    active_kid: str
    keys: Mapping[str, bytes]

    @classmethod
    def single(cls, key: bytes, *, kid: str = 'default') -> 'OAuthKeyRing':
        return cls(active_kid=kid, keys={kid: key})

    @property
    def active_key(self) -> bytes:
        return self.keys[self.active_kid]

    def key_for(self, kid: Optional[str]) -> bytes:
        if kid and kid in self.keys:
            return self.keys[kid]
        return self.active_key

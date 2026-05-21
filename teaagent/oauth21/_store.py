from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Protocol

from teaagent.oauth21._types import OAuth21Client, _AuthorizationCode, _RefreshToken

_SQLITE_SCHEMA_VERSION = 3
_CLIENT_SECRET_KDF = 'pbkdf2_sha256'
_CLIENT_SECRET_ITERATIONS = 210_000
_CLIENT_SECRET_SALT_BYTES = 16


class OAuthStore(Protocol):
    def register_client(self, client: OAuth21Client) -> None: ...

    def get_client(self, client_id: str) -> Optional[OAuth21Client]: ...

    def save_code(self, code: _AuthorizationCode) -> None: ...

    def consume_code(self, code: str) -> Optional[_AuthorizationCode]: ...

    def save_nonce(self, nonce: str, created_at: float) -> None: ...

    def get_nonce(self, nonce: str) -> Optional[float]: ...

    def consume_nonce(self, nonce: str) -> Optional[float]: ...

    def delete_nonce(self, nonce: str) -> None: ...

    def prune(
        self, *, now: float, code_ttl_cutoff: float, nonce_ttl: float
    ) -> None: ...

    def save_refresh_token(self, record: _RefreshToken) -> None: ...

    def consume_refresh_token(self, token: str) -> Optional[_RefreshToken]: ...

    def record_refresh_reuse(
        self, token: str, family_id: str, *, expires_at: float
    ) -> None: ...

    def is_refresh_reused(self, token: str) -> bool: ...

    def get_refresh_reuse_family_id(self, token: str) -> Optional[str]: ...

    def revoke_refresh_family(self, family_id: str) -> None: ...


class InMemoryOAuthStore:
    def __init__(self) -> None:
        self.clients: dict[str, OAuth21Client] = {}
        self.codes: dict[str, _AuthorizationCode] = {}
        self.nonces: dict[str, float] = {}
        self.refresh_tokens: dict[str, _RefreshToken] = {}
        self.refresh_reuse: dict[str, tuple[str, float]] = {}

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

    def consume_nonce(self, nonce: str) -> Optional[float]:
        return self.nonces.pop(nonce, None)

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
        expired_refresh = [
            t for t, rec in self.refresh_tokens.items() if rec.expires_at < now
        ]
        for token in expired_refresh:
            del self.refresh_tokens[token]
        expired_reuse = [t for t, (_, exp) in self.refresh_reuse.items() if exp < now]
        for token in expired_reuse:
            del self.refresh_reuse[token]

    def save_refresh_token(self, record: _RefreshToken) -> None:
        self.refresh_tokens[record.token] = record

    def consume_refresh_token(self, token: str) -> Optional[_RefreshToken]:
        return self.refresh_tokens.pop(token, None)

    def record_refresh_reuse(
        self, token: str, family_id: str, *, expires_at: float
    ) -> None:
        self.refresh_reuse[token] = (family_id, expires_at)

    def is_refresh_reused(self, token: str) -> bool:
        return self.get_refresh_reuse_family_id(token) is not None

    def get_refresh_reuse_family_id(self, token: str) -> Optional[str]:
        entry = self.refresh_reuse.get(token)
        if entry is None:
            return None
        family_id, expires_at = entry
        if expires_at < time.time():
            del self.refresh_reuse[token]
            return None
        return family_id

    def revoke_refresh_family(self, family_id: str) -> None:
        for token, record in list(self.refresh_tokens.items()):
            if record.family_id == family_id:
                del self.refresh_tokens[token]
        for token, (fid, _) in list(self.refresh_reuse.items()):
            if fid == family_id:
                del self.refresh_reuse[token]


class SQLiteOAuthStore:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()

    def register_client(self, client: OAuth21Client) -> None:
        secret_hash, salt = _hash_client_secret(client.client_secret)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO oauth_clients
                    (client_id, client_secret, client_secret_hash,
                     client_secret_salt, client_secret_kdf,
                     redirect_uris_json, scope)
                VALUES (?, '', ?, ?, ?, ?, ?)
                """,
                (
                    client.client_id,
                    secret_hash,
                    salt,
                    _CLIENT_SECRET_KDF,
                    json.dumps(sorted(client.redirect_uris), separators=(',', ':')),
                    client.scope,
                ),
            )

    def get_client(self, client_id: str) -> Optional[OAuth21Client]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT client_id, redirect_uris_json, scope
                FROM oauth_clients
                WHERE client_id = ?
                """,
                (client_id,),
            ).fetchone()
        if row is None:
            return None
        redirect_uris = frozenset(str(uri) for uri in json.loads(row[1]))
        return OAuth21Client(
            client_id=str(row[0]),
            client_secret='',
            redirect_uris=redirect_uris,
            scope=str(row[2]),
        )

    def validate_client_secret(self, client_id: str, client_secret: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT client_secret_hash, client_secret_salt, client_secret_kdf
                FROM oauth_clients
                WHERE client_id = ?
                """,
                (client_id,),
            ).fetchone()
        if row is None or row[2] != _CLIENT_SECRET_KDF:
            return False
        expected = bytes(row[0])
        salt = bytes(row[1])
        actual = _hash_client_secret_with_salt(client_secret, salt)
        return hmac.compare_digest(actual, expected)

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

    def consume_nonce(self, nonce: str) -> Optional[float]:
        with self._lock, self._connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute(
                'SELECT created_at FROM oauth_nonces WHERE nonce = ?',
                (nonce,),
            ).fetchone()
            if row is None:
                return None
            conn.execute('DELETE FROM oauth_nonces WHERE nonce = ?', (nonce,))
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
            conn.execute(
                'DELETE FROM oauth_refresh_tokens WHERE expires_at < ?',
                (now,),
            )
            conn.execute(
                'DELETE FROM oauth_refresh_reuse WHERE expires_at < ?',
                (now,),
            )

    def save_refresh_token(self, record: _RefreshToken) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO oauth_refresh_tokens
                    (token, client_id, scope, expires_at, family_id, cnf_jkt)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record.token,
                    record.client_id,
                    record.scope,
                    record.expires_at,
                    record.family_id,
                    record.cnf_jkt,
                ),
            )

    def consume_refresh_token(self, token: str) -> Optional[_RefreshToken]:
        with self._lock, self._connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute(
                """
                SELECT token, client_id, scope, expires_at, family_id, cnf_jkt
                FROM oauth_refresh_tokens
                WHERE token = ?
                """,
                (token,),
            ).fetchone()
            if row is None:
                return None
            conn.execute(
                'DELETE FROM oauth_refresh_tokens WHERE token = ?',
                (token,),
            )
        return _RefreshToken(
            token=str(row[0]),
            client_id=str(row[1]),
            scope=str(row[2]),
            expires_at=float(row[3]),
            family_id=str(row[4]),
            cnf_jkt=str(row[5]) if row[5] is not None else None,
        )

    def record_refresh_reuse(
        self, token: str, family_id: str, *, expires_at: float
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO oauth_refresh_reuse
                    (token, family_id, expires_at)
                VALUES (?, ?, ?)
                """,
                (token, family_id, expires_at),
            )

    def is_refresh_reused(self, token: str) -> bool:
        return self.get_refresh_reuse_family_id(token) is not None

    def get_refresh_reuse_family_id(self, token: str) -> Optional[str]:
        with self._connect() as conn:
            row = conn.execute(
                'SELECT family_id, expires_at FROM oauth_refresh_reuse WHERE token = ?',
                (token,),
            ).fetchone()
        if row is None:
            return None
        if float(row[1]) < time.time():
            with self._connect() as conn:
                conn.execute(
                    'DELETE FROM oauth_refresh_reuse WHERE token = ?',
                    (token,),
                )
            return None
        return str(row[0])

    def revoke_refresh_family(self, family_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                'DELETE FROM oauth_refresh_tokens WHERE family_id = ?',
                (family_id,),
            )
            conn.execute(
                'DELETE FROM oauth_refresh_reuse WHERE family_id = ?',
                (family_id,),
            )

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                PRAGMA journal_mode = WAL;
                CREATE TABLE IF NOT EXISTS oauth_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS oauth_clients (
                    client_id TEXT PRIMARY KEY,
                    client_secret TEXT NOT NULL DEFAULT '',
                    client_secret_hash BLOB,
                    client_secret_salt BLOB,
                    client_secret_kdf TEXT,
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
                CREATE TABLE IF NOT EXISTS oauth_refresh_tokens (
                    token TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    expires_at REAL NOT NULL,
                    family_id TEXT NOT NULL,
                    cnf_jkt TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_oauth_refresh_tokens_expires_at
                    ON oauth_refresh_tokens(expires_at);
                CREATE INDEX IF NOT EXISTS idx_oauth_refresh_tokens_family_id
                    ON oauth_refresh_tokens(family_id);
                CREATE TABLE IF NOT EXISTS oauth_refresh_reuse (
                    token TEXT PRIMARY KEY,
                    family_id TEXT NOT NULL,
                    expires_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_oauth_refresh_reuse_expires_at
                    ON oauth_refresh_reuse(expires_at);
                """
            )
            self._migrate_clients(conn)
            conn.execute(
                """
                INSERT OR REPLACE INTO oauth_metadata (key, value)
                VALUES ('schema_version', ?)
                """,
                (str(_SQLITE_SCHEMA_VERSION),),
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        conn.execute('PRAGMA foreign_keys = ON')
        conn.execute('PRAGMA busy_timeout = 30000')
        return conn

    def _migrate_clients(self, conn: sqlite3.Connection) -> None:
        columns = {
            str(row[1])
            for row in conn.execute('PRAGMA table_info(oauth_clients)').fetchall()
        }
        if 'client_secret_hash' not in columns:
            conn.execute('ALTER TABLE oauth_clients ADD COLUMN client_secret_hash BLOB')
        if 'client_secret_salt' not in columns:
            conn.execute('ALTER TABLE oauth_clients ADD COLUMN client_secret_salt BLOB')
        if 'client_secret_kdf' not in columns:
            conn.execute('ALTER TABLE oauth_clients ADD COLUMN client_secret_kdf TEXT')
        for row in conn.execute(
            """
            SELECT client_id, client_secret
            FROM oauth_clients
            WHERE client_secret_hash IS NULL AND client_secret != ''
            """
        ).fetchall():
            secret_hash, salt = _hash_client_secret(str(row[1]))
            conn.execute(
                """
                UPDATE oauth_clients
                SET client_secret = '',
                    client_secret_hash = ?,
                    client_secret_salt = ?,
                    client_secret_kdf = ?
                WHERE client_id = ?
                """,
                (secret_hash, salt, _CLIENT_SECRET_KDF, str(row[0])),
            )


def _hash_client_secret(secret: str) -> tuple[bytes, bytes]:
    salt = secrets.token_bytes(_CLIENT_SECRET_SALT_BYTES)
    return _hash_client_secret_with_salt(secret, salt), salt


def _hash_client_secret_with_salt(secret: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac(
        'sha256',
        secret.encode('utf-8'),
        salt,
        _CLIENT_SECRET_ITERATIONS,
    )


@dataclass(frozen=True)
class OAuthKeyRing:
    active_kid: str
    keys: Mapping[str, bytes]
    rotation_window_seconds: int = 0
    deprecated_at: Mapping[str, float] = field(default_factory=dict)

    @classmethod
    def single(cls, key: bytes, *, kid: str = 'default') -> 'OAuthKeyRing':
        return cls(active_kid=kid, keys={kid: key})

    @property
    def active_key(self) -> bytes:
        return self.keys[self.active_kid]

    def rotate(self, new_kid: str, *, now: Optional[float] = None) -> 'OAuthKeyRing':
        if new_kid not in self.keys:
            raise ValueError(
                f'Cannot rotate to unknown kid {new_kid!r}; available: {list(self.keys)}'
            )
        ts = now if now is not None else time.time()
        updated: dict[str, float] = dict(self.deprecated_at)
        updated[self.active_kid] = ts
        return OAuthKeyRing(
            active_kid=new_kid,
            keys=self.keys,
            rotation_window_seconds=self.rotation_window_seconds,
            deprecated_at=updated,
        )

    def key_for(self, kid: Optional[str]) -> bytes:
        if kid and kid in self.keys:
            return self.keys[kid]
        return self.active_key

    def key_for_validation(
        self, kid: Optional[str], *, now: Optional[float] = None
    ) -> bytes:
        resolved = kid if (kid and kid in self.keys) else self.active_kid
        key = self.keys[resolved]
        if resolved != self.active_kid and self.rotation_window_seconds > 0:
            deprecated_ts = self.deprecated_at.get(resolved)
            if deprecated_ts is not None:
                elapsed = (now if now is not None else time.time()) - deprecated_ts
                if elapsed > self.rotation_window_seconds:
                    from teaagent.oauth21._types import JWTError

                    raise JWTError(
                        f'Signing key {resolved!r} is outside rotation window '
                        f'({elapsed:.0f}s > {self.rotation_window_seconds}s)'
                    )
        return key

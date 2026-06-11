from __future__ import annotations

import sqlite3
import tempfile
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from teaagent.oauth21 import (
    InvalidClientError,
    InvalidGrantError,
    OAuth21AuthorizationServer,
    SQLiteOAuthStore,
    compute_s256_challenge,
    generate_code_verifier,
)
from teaagent.oauth21._types import _AuthorizationCode

SIGNING_KEY = 'super-secret-key-at-least-16-chars'
ISSUER = 'https://issuer.example'


def _code_from_redirect(redirect_url: str) -> str:
    values = parse_qs(urlparse(redirect_url).query)
    return values['code'][0]


def test_authorization_flow_persists_across_server_instances() -> None:
    tmp_path = None
    try:
        tmp = tempfile.TemporaryDirectory()
        tmp_path = Path(tmp.name)
        store_path = tmp_path / 'oauth.sqlite3'
        verifier = generate_code_verifier()
        challenge = compute_s256_challenge(verifier)

        first = OAuth21AuthorizationServer(
            signing_key=SIGNING_KEY,
            issuer=ISSUER,
            store=SQLiteOAuthStore(store_path),
        )
        first.register_client(
            'client-1',
            'secret-1',
            ['https://client.example/callback'],
        )
        redirect_url, _ = first.create_authorization_code(
            'client-1', 'https://client.example/callback', challenge
        )

        second = OAuth21AuthorizationServer(
            signing_key=SIGNING_KEY,
            issuer=ISSUER,
            store=SQLiteOAuthStore(store_path),
        )
        token = second.exchange_code(
            _code_from_redirect(redirect_url),
            verifier,
            client_id='client-1',
            client_secret='secret-1',
        )

        assert token.token_type == 'Bearer'
        assert token.scope == 'mcp'
    finally:
        if tmp_path and tmp_path.exists():
            tmp.cleanup()
            assert not tmp_path.exists(), (
                f'Temporary directory {tmp_path} was not cleaned up'
            )
            # Verify SQLite file is cleaned up
            assert not store_path.exists(), (
                f'SQLite database {store_path} was not cleaned up'
            )


def test_client_secret_is_hashed_at_rest() -> None:
    tmp_path = None
    try:
        tmp = tempfile.TemporaryDirectory()
        tmp_path = Path(tmp.name)
        store_path = tmp_path / 'oauth.sqlite3'
        store = SQLiteOAuthStore(store_path)

        server = OAuth21AuthorizationServer(
            signing_key=SIGNING_KEY,
            issuer=ISSUER,
            store=store,
        )
        server.register_client('client-1', 'secret-1', ['https://client/cb'])

        with sqlite3.connect(store_path) as conn:
            row = conn.execute(
                """
                SELECT client_secret, client_secret_hash,
                       client_secret_salt, client_secret_kdf
                FROM oauth_clients
                WHERE client_id = 'client-1'
                """
            ).fetchone()
            schema_version = conn.execute(
                "SELECT value FROM oauth_metadata WHERE key = 'schema_version'"
            ).fetchone()[0]

        assert row[0] == ''
        assert isinstance(row[1], bytes)
        assert isinstance(row[2], bytes)
        assert row[3] == 'pbkdf2_sha256'
        assert row[1] != b'secret-1'
        assert schema_version == '3'
    finally:
        if tmp_path and tmp_path.exists():
            tmp.cleanup()
            assert not tmp_path.exists(), (
                f'Temporary directory {tmp_path} was not cleaned up'
            )


def test_hashed_client_secret_rejects_wrong_secret() -> None:
    tmp_path = None
    try:
        tmp = tempfile.TemporaryDirectory()
        tmp_path = Path(tmp.name)
        store_path = tmp_path / 'oauth.sqlite3'
        verifier = generate_code_verifier()
        challenge = compute_s256_challenge(verifier)
        server = OAuth21AuthorizationServer(
            signing_key=SIGNING_KEY,
            issuer=ISSUER,
            store=SQLiteOAuthStore(store_path),
        )
        server.register_client('client-1', 'secret-1', ['https://client/cb'])
        redirect_url, _ = server.create_authorization_code(
            'client-1', 'https://client/cb', challenge
        )

        with pytest.raises(InvalidClientError):
            server.exchange_code(
                _code_from_redirect(redirect_url),
                verifier,
                client_id='client-1',
                client_secret='wrong-secret',
            )
    finally:
        if tmp_path and tmp_path.exists():
            tmp.cleanup()
            assert not tmp_path.exists(), (
                f'Temporary directory {tmp_path} was not cleaned up'
            )


def test_authorization_code_is_consumed_once() -> None:
    tmp_path = None
    try:
        tmp = tempfile.TemporaryDirectory()
        tmp_path = Path(tmp.name)
        store_path = tmp_path / 'oauth.sqlite3'
        verifier = generate_code_verifier()
        challenge = compute_s256_challenge(verifier)
        server = OAuth21AuthorizationServer(
            signing_key=SIGNING_KEY,
            issuer=ISSUER,
            store=SQLiteOAuthStore(store_path),
        )
        server.register_client('client-1', 'secret-1', ['https://client/cb'])
        redirect_url, _ = server.create_authorization_code(
            'client-1', 'https://client/cb', challenge
        )
        code = _code_from_redirect(redirect_url)

        server.exchange_code(
            code, verifier, client_id='client-1', client_secret='secret-1'
        )

        with pytest.raises(InvalidGrantError):
            server.exchange_code(
                code,
                verifier,
                client_id='client-1',
                client_secret='secret-1',
            )
    finally:
        if tmp_path and tmp_path.exists():
            tmp.cleanup()
            assert not tmp_path.exists(), (
                f'Temporary directory {tmp_path} was not cleaned up'
            )


def test_nonce_persists_and_prunes() -> None:
    tmp_path = None
    try:
        tmp = tempfile.TemporaryDirectory()
        tmp_path = Path(tmp.name)
        store_path = tmp_path / 'oauth.sqlite3'
        store = SQLiteOAuthStore(store_path)

        store.save_nonce('fresh', time.time())
        store.save_nonce('old', time.time() - 600)

        reopened = SQLiteOAuthStore(store_path)
        assert reopened.get_nonce('fresh') is not None
        assert reopened.get_nonce('old') is not None

        reopened.prune(now=time.time(), code_ttl_cutoff=time.time(), nonce_ttl=300)

        assert reopened.get_nonce('fresh') is not None
        assert reopened.get_nonce('old') is None
    finally:
        if tmp_path and tmp_path.exists():
            tmp.cleanup()
            assert not tmp_path.exists(), (
                f'Temporary directory {tmp_path} was not cleaned up'
            )


def test_nonce_consume_is_one_time() -> None:
    tmp_path = None
    try:
        tmp = tempfile.TemporaryDirectory()
        tmp_path = Path(tmp.name)
        store = SQLiteOAuthStore(tmp_path / 'oauth.sqlite3')
        store.save_nonce('nonce-1', time.time())

        assert store.consume_nonce('nonce-1') is not None
        assert store.consume_nonce('nonce-1') is None
    finally:
        if tmp_path and tmp_path.exists():
            tmp.cleanup()
            assert not tmp_path.exists(), (
                f'Temporary directory {tmp_path} was not cleaned up'
            )


def test_authorization_server_consumes_dpop_nonce_once() -> None:
    tmp_path = None
    try:
        tmp = tempfile.TemporaryDirectory()
        tmp_path = Path(tmp.name)
        server = OAuth21AuthorizationServer(
            signing_key=SIGNING_KEY,
            issuer=ISSUER,
            store=SQLiteOAuthStore(tmp_path / 'oauth.sqlite3'),
        )
        nonce = server.generate_dpop_nonce()

        assert server.validate_dpop_nonce(nonce)
        assert not server.validate_dpop_nonce(nonce)
    finally:
        if tmp_path and tmp_path.exists():
            tmp.cleanup()
            assert not tmp_path.exists(), (
                f'Temporary directory {tmp_path} was not cleaned up'
            )


def test_prune_removes_expired_codes() -> None:
    tmp_path = None
    try:
        tmp = tempfile.TemporaryDirectory()
        tmp_path = Path(tmp.name)
        store = SQLiteOAuthStore(tmp_path / 'oauth.sqlite3')
        store.save_code(
            _AuthorizationCode(
                code='expired',
                client_id='client-1',
                redirect_uri='https://client/cb',
                code_challenge='challenge',
                code_challenge_method='S256',
                expires_at=time.time() - 1,
                scope='mcp',
            )
        )

        store.prune(now=time.time(), code_ttl_cutoff=time.time(), nonce_ttl=300)

        assert store.consume_code('expired') is None
    finally:
        if tmp_path and tmp_path.exists():
            tmp.cleanup()
            assert not tmp_path.exists(), (
                f'Temporary directory {tmp_path} was not cleaned up'
            )


def test_refresh_token_rotation_persists_across_instances() -> None:
    tmp_path = None
    try:
        tmp = tempfile.TemporaryDirectory()
        tmp_path = Path(tmp.name)
        store_path = tmp_path / 'oauth.sqlite3'
        verifier = generate_code_verifier()
        challenge = compute_s256_challenge(verifier)

        first = OAuth21AuthorizationServer(
            signing_key=SIGNING_KEY,
            issuer=ISSUER,
            store=SQLiteOAuthStore(store_path),
        )
        first.register_client(
            'client-1',
            'secret-1',
            ['https://client.example/callback'],
        )
        redirect_url, _ = first.create_authorization_code(
            'client-1', 'https://client.example/callback', challenge
        )
        code = _code_from_redirect(redirect_url)
        initial = first.exchange_code(
            code=code, code_verifier=verifier, client_id='client-1'
        )
        assert initial.refresh_token is not None

        second = OAuth21AuthorizationServer(
            signing_key=SIGNING_KEY,
            issuer=ISSUER,
            store=SQLiteOAuthStore(store_path),
        )
        rotated = second.exchange_refresh_token(
            initial.refresh_token, client_id='client-1'
        )
        assert rotated.refresh_token is not None
    finally:
        if tmp_path and tmp_path.exists():
            tmp.cleanup()
            assert not tmp_path.exists(), (
                f'Temporary directory {tmp_path} was not cleaned up'
            )


def test_invalid_json_in_redirect_uris_raises_error() -> None:
    tmp_path = None
    try:
        tmp = tempfile.TemporaryDirectory()
        tmp_path = Path(tmp.name)
        store_path = tmp_path / 'oauth.sqlite3'
        store = SQLiteOAuthStore(store_path)

        # Manually insert invalid JSON into the database
        with sqlite3.connect(store_path) as conn:
            conn.execute(
                """
                INSERT INTO oauth_clients
                    (client_id, client_secret, client_secret_hash,
                     client_secret_salt, client_secret_kdf,
                     redirect_uris_json, scope)
                VALUES (?, '', ?, ?, ?, ?, ?)
                """,
                (
                    'client-1',
                    b'hash',
                    b'salt',
                    'pbkdf2_sha256',
                    'invalid-json{',
                    'mcp',
                ),
            )

        # Should raise ValueError when trying to get the client
        with pytest.raises(ValueError) as cm:
            store.get_client('client-1')
        assert 'Invalid JSON' in str(cm.value)
    finally:
        if tmp_path and tmp_path.exists():
            tmp.cleanup()
            assert not tmp_path.exists(), (
                f'Temporary directory {tmp_path} was not cleaned up'
            )


def test_non_list_redirect_uris_raises_error() -> None:
    tmp_path = None
    try:
        tmp = tempfile.TemporaryDirectory()
        tmp_path = Path(tmp.name)
        store_path = tmp_path / 'oauth.sqlite3'
        store = SQLiteOAuthStore(store_path)

        # Insert a string instead of a list
        with sqlite3.connect(store_path) as conn:
            conn.execute(
                """
                INSERT INTO oauth_clients
                    (client_id, client_secret, client_secret_hash,
                     client_secret_salt, client_secret_kdf,
                     redirect_uris_json, scope)
                VALUES (?, '', ?, ?, ?, ?, ?)
                """,
                (
                    'client-1',
                    b'hash',
                    b'salt',
                    'pbkdf2_sha256',
                    '"https://client/cb"',
                    'mcp',
                ),
            )

        # Should raise ValueError when trying to get the client
        with pytest.raises(ValueError) as cm:
            store.get_client('client-1')
        assert 'must be a list' in str(cm.value)
    finally:
        if tmp_path and tmp_path.exists():
            tmp.cleanup()
            assert not tmp_path.exists(), (
                f'Temporary directory {tmp_path} was not cleaned up'
            )


def test_invalid_uri_format_raises_error() -> None:
    tmp_path = None
    try:
        tmp = tempfile.TemporaryDirectory()
        tmp_path = Path(tmp.name)
        store_path = tmp_path / 'oauth.sqlite3'
        store = SQLiteOAuthStore(store_path)

        # Insert an invalid URI (missing scheme)
        with sqlite3.connect(store_path) as conn:
            conn.execute(
                """
                INSERT INTO oauth_clients
                    (client_id, client_secret, client_secret_hash,
                     client_secret_salt, client_secret_kdf,
                     redirect_uris_json, scope)
                VALUES (?, '', ?, ?, ?, ?, ?)
                """,
                (
                    'client-1',
                    b'hash',
                    b'salt',
                    'pbkdf2_sha256',
                    '["not-a-valid-uri"]',
                    'mcp',
                ),
            )

        # Should raise ValueError when trying to get the client
        with pytest.raises(ValueError) as cm:
            store.get_client('client-1')
        assert 'Invalid URI format' in str(cm.value)
    finally:
        if tmp_path and tmp_path.exists():
            tmp.cleanup()
            assert not tmp_path.exists(), (
                f'Temporary directory {tmp_path} was not cleaned up'
            )

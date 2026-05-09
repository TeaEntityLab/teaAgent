from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from teaagent.oauth21 import (
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


class SQLiteOAuthStoreTests(unittest.TestCase):
    def test_authorization_flow_persists_across_server_instances(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_path = Path(tmp) / 'oauth.sqlite3'
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

            self.assertEqual(token.token_type, 'Bearer')
            self.assertEqual(token.scope, 'mcp')

    def test_authorization_code_is_consumed_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_path = Path(tmp) / 'oauth.sqlite3'
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

            with self.assertRaises(InvalidGrantError):
                server.exchange_code(
                    code,
                    verifier,
                    client_id='client-1',
                    client_secret='secret-1',
                )

    def test_nonce_persists_and_prunes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_path = Path(tmp) / 'oauth.sqlite3'
            store = SQLiteOAuthStore(store_path)

            store.save_nonce('fresh', time.time())
            store.save_nonce('old', time.time() - 600)

            reopened = SQLiteOAuthStore(store_path)
            self.assertIsNotNone(reopened.get_nonce('fresh'))
            self.assertIsNotNone(reopened.get_nonce('old'))

            reopened.prune(now=time.time(), code_ttl_cutoff=time.time(), nonce_ttl=300)

            self.assertIsNotNone(reopened.get_nonce('fresh'))
            self.assertIsNone(reopened.get_nonce('old'))

    def test_prune_removes_expired_codes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = SQLiteOAuthStore(Path(tmp) / 'oauth.sqlite3')
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

            self.assertIsNone(store.consume_code('expired'))


if __name__ == '__main__':
    unittest.main()

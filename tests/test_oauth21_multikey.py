from __future__ import annotations

import time
import unittest

from teaagent.oauth21 import (
    JWTError,
    OAuth21ResourceServer,
    OAuthKeyRing,
    create_jwt,
)


def _claims(now: int) -> dict:
    return {
        'iss': 'https://issuer.example',
        'sub': 'client',
        'aud': 'https://issuer.example',
        'iat': now,
        'exp': now + 60,
        'jti': 'unique',
        'scope': 'mcp',
    }


class OAuth21MultiKeyResourceServerTests(unittest.TestCase):
    def test_resource_server_verifies_tokens_for_all_keys_in_ring(self) -> None:
        key_v1 = b'a' * 32
        key_v2 = b'b' * 32
        ring = OAuthKeyRing(active_kid='v2', keys={'v1': key_v1, 'v2': key_v2})
        rs = OAuth21ResourceServer(
            signing_key='b' * 32,
            issuer='https://issuer.example',
            key_ring=ring,
        )
        now = int(time.time())
        token_v1 = create_jwt(_claims(now), key_v1, header_extra={'kid': 'v1'})
        token_v2 = create_jwt(_claims(now), key_v2, header_extra={'kid': 'v2'})

        claims_v1 = rs.validate_request(
            authorization_header=f'Bearer {token_v1}',
            dpop_header=None,
            method='GET',
            url='https://api.example/resource',
        )
        claims_v2 = rs.validate_request(
            authorization_header=f'Bearer {token_v2}',
            dpop_header=None,
            method='GET',
            url='https://api.example/resource',
        )
        self.assertEqual(claims_v1.sub, 'client')
        self.assertEqual(claims_v2.sub, 'client')

    def test_resource_server_rejects_token_signed_with_unknown_key(self) -> None:
        ring = OAuthKeyRing(active_kid='v1', keys={'v1': b'a' * 32})
        rs = OAuth21ResourceServer(
            signing_key='a' * 32,
            issuer='https://issuer.example',
            key_ring=ring,
        )
        rogue_key = b'r' * 32
        rogue_token = create_jwt(
            _claims(int(time.time())),
            rogue_key,
            header_extra={'kid': 'rogue'},
        )

        with self.assertRaises(JWTError):
            rs.validate_request(
                authorization_header=f'Bearer {rogue_token}',
                dpop_header=None,
                method='GET',
                url='https://api.example/resource',
            )

    def test_resource_server_rejects_token_with_kid_pointing_to_wrong_key(self) -> None:
        good_key = b'g' * 32
        ring = OAuthKeyRing(active_kid='v1', keys={'v1': good_key})
        rs = OAuth21ResourceServer(
            signing_key='g' * 32,
            issuer='https://issuer.example',
            key_ring=ring,
        )
        rogue_key = b'r' * 32
        rogue_token = create_jwt(
            _claims(int(time.time())),
            rogue_key,
            header_extra={'kid': 'v1'},
        )

        with self.assertRaises(JWTError):
            rs.validate_request(
                authorization_header=f'Bearer {rogue_token}',
                dpop_header=None,
                method='GET',
                url='https://api.example/resource',
            )


if __name__ == '__main__':
    unittest.main()

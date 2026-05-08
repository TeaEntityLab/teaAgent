from __future__ import annotations

import time
import unittest

from teaagent.oauth21 import (
    HAS_CRYPTOGRAPHY,
    InvalidClientError,
    InvalidDPoPError,
    InvalidGrantError,
    JWTError,
    OAuth21AuthorizationServer,
    OAuth21Error,
    OAuth21ResourceServer,
    compute_jwk_thumbprint,
    compute_s256_challenge,
    create_jwt,
    decode_jwt_unsafe,
    generate_code_verifier,
    verify_jwt,
)

SIGNING_KEY = 'super-secret-key-at-least-16-chars'


class JWTTests(unittest.TestCase):
    def test_create_and_verify_roundtrip(self) -> None:
        payload = {'sub': 'alice', 'iat': int(time.time()), 'iss': 'test'}
        token = create_jwt(payload, SIGNING_KEY.encode())
        claims = verify_jwt(token, SIGNING_KEY.encode(), iss='test')
        self.assertEqual(claims['sub'], 'alice')

    def test_verify_wrong_key_fails(self) -> None:
        token = create_jwt({'sub': 'alice'}, SIGNING_KEY.encode())
        with self.assertRaises(JWTError) as ctx:
            verify_jwt(token, b'wrong-key-xxxxxxxx')
        self.assertIn('signature', str(ctx.exception).lower())

    def test_verify_expired_token(self) -> None:
        payload = {'sub': 'alice', 'exp': int(time.time()) - 60}
        token = create_jwt(payload, SIGNING_KEY.encode())
        with self.assertRaises(JWTError) as ctx:
            verify_jwt(token, SIGNING_KEY.encode())
        self.assertIn('expired', str(ctx.exception).lower())

    def test_verify_allow_expired(self) -> None:
        payload = {'sub': 'alice', 'exp': int(time.time()) - 60}
        token = create_jwt(payload, SIGNING_KEY.encode())
        claims = verify_jwt(token, SIGNING_KEY.encode(), allow_expired=True)
        self.assertEqual(claims['sub'], 'alice')

    def test_verify_aud_mismatch(self) -> None:
        token = create_jwt({'sub': 'alice', 'aud': 'a'}, SIGNING_KEY.encode())
        with self.assertRaises(JWTError) as ctx:
            verify_jwt(token, SIGNING_KEY.encode(), aud='b')
        self.assertIn('audience', str(ctx.exception).lower())

    def test_verify_iss_mismatch(self) -> None:
        token = create_jwt({'sub': 'alice', 'iss': 'a'}, SIGNING_KEY.encode())
        with self.assertRaises(JWTError) as ctx:
            verify_jwt(token, SIGNING_KEY.encode(), iss='b')
        self.assertIn('issuer', str(ctx.exception).lower())

    def test_decode_jwt_unsafe(self) -> None:
        token = create_jwt(
            {'sub': 'alice', 'iss': 'x'},
            SIGNING_KEY.encode(),
            header_extra={'jwk': {'kty': 'EC'}},
        )
        header, payload = decode_jwt_unsafe(token)
        self.assertEqual(payload['sub'], 'alice')
        self.assertEqual(header['alg'], 'HS256')
        self.assertEqual(header['jwk']['kty'], 'EC')

    def test_verify_invalid_format(self) -> None:
        with self.assertRaises(JWTError):
            verify_jwt('not.a.jwt.token', SIGNING_KEY.encode())
        with self.assertRaises(JWTError):
            verify_jwt('onlytwo.parts', SIGNING_KEY.encode())


class PKCETests(unittest.TestCase):
    def test_verifier_default_length(self) -> None:
        v = generate_code_verifier()
        self.assertEqual(len(v), 43)

    def test_verifier_custom_length(self) -> None:
        for length in (48, 64, 128):
            v = generate_code_verifier(length=length)
            self.assertEqual(len(v), length)

    def test_verifier_rejects_invalid_length(self) -> None:
        with self.assertRaises(ValueError):
            generate_code_verifier(length=10)
        with self.assertRaises(ValueError):
            generate_code_verifier(length=200)

    def test_s256_challenge_matches(self) -> None:
        verifier = 'test-verifier-value'
        challenge = compute_s256_challenge(verifier)
        self.assertTrue(len(challenge) > 0)
        # Deterministic: same verifier → same challenge
        self.assertEqual(challenge, compute_s256_challenge(verifier))

    def test_verifier_challenge_roundtrip(self) -> None:
        """A valid verifier's S256 challenge should match when re-computed."""
        verifier = generate_code_verifier()
        challenge = compute_s256_challenge(verifier)
        self.assertEqual(challenge, compute_s256_challenge(verifier))


class JWKThumbprintTests(unittest.TestCase):
    def test_oct_key_thumbprint(self) -> None:
        jwk = {
            'kty': 'oct',
            'k': 'AyM1SysPpbyDfgZld3umj1qzKObwVMkoqQ-EstJQLr_T-1qS0gZH75aKtMN3Yj0iPS4hcgUuTwjAzZr1Z9CAow',
        }
        thumb = compute_jwk_thumbprint(jwk)
        self.assertTrue(len(thumb) > 0)
        # RFC 7638 example for oct key (different key, but check format)
        self.assertFalse('=' in thumb)

    def test_thumbprint_deterministic(self) -> None:
        jwk = {'kty': 'oct', 'k': 'test-key', 'extra': 'ignored'}
        t1 = compute_jwk_thumbprint(jwk)
        t2 = compute_jwk_thumbprint(jwk)
        self.assertEqual(t1, t2)

    def test_thumbprint_ignores_extra_fields(self) -> None:
        jwk1 = {'kty': 'oct', 'k': 'test-key', 'use': 'sig'}
        jwk2 = {'kty': 'oct', 'k': 'test-key', 'use': 'enc'}
        self.assertEqual(
            compute_jwk_thumbprint(jwk1),
            compute_jwk_thumbprint(jwk2),
        )


class AuthorizationServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.as_ = OAuth21AuthorizationServer(
            signing_key=SIGNING_KEY, issuer='https://mcp.test'
        )
        self.as_.register_client('client-1', 'secret-1', ['https://app.test/callback'])

    def test_register_client(self) -> None:
        client = self.as_.get_client('client-1')
        self.assertEqual(client.client_id, 'client-1')
        self.assertTrue(client.validate_redirect_uri('https://app.test/callback'))
        self.assertFalse(client.validate_redirect_uri('https://evil.test/callback'))

    def test_register_duplicate_fails(self) -> None:
        with self.assertRaises(InvalidClientError):
            self.as_.register_client(
                'client-1', 'secret-2', ['https://app.test/callback']
            )

    def test_get_unknown_client(self) -> None:
        with self.assertRaises(InvalidClientError):
            self.as_.get_client('nonexistent')

    def test_create_authorization_code(self) -> None:
        verifier = generate_code_verifier()
        challenge = compute_s256_challenge(verifier)

        redirect_url, state = self.as_.create_authorization_code(
            client_id='client-1',
            redirect_uri='https://app.test/callback',
            code_challenge=challenge,
            scope='mcp',
            state='mystate',
        )
        self.assertIn('code=', redirect_url)
        self.assertIn('state=mystate', redirect_url)
        self.assertEqual(state, 'mystate')

    def test_authorize_wrong_redirect_uri(self) -> None:
        with self.assertRaises(InvalidClientError):
            self.as_.create_authorization_code(
                client_id='client-1',
                redirect_uri='https://evil.test/callback',
                code_challenge='challenge',
            )

    def test_authorize_wrong_challenge_method(self) -> None:
        with self.assertRaises(OAuth21Error):
            self.as_.create_authorization_code(
                client_id='client-1',
                redirect_uri='https://app.test/callback',
                code_challenge='abc',
                code_challenge_method='plain',
            )

    def test_exchange_code_success_bearer(self) -> None:
        verifier = generate_code_verifier()
        challenge = compute_s256_challenge(verifier)

        redirect_url, _ = self.as_.create_authorization_code(
            client_id='client-1',
            redirect_uri='https://app.test/callback',
            code_challenge=challenge,
        )

        code = redirect_url.split('code=')[1].split('&')[0]
        token = self.as_.exchange_code(
            code=code, code_verifier=verifier, client_id='client-1'
        )
        self.assertEqual(token.token_type, 'Bearer')
        self.assertTrue(len(token.access_token) > 0)
        self.assertEqual(token.expires_in, 3600)
        self.assertEqual(token.scope, 'mcp')

        # Introspect
        claims = self.as_.introspect_token(token.access_token)
        self.assertEqual(claims.sub, 'client-1')
        self.assertEqual(claims.iss, 'https://mcp.test')
        self.assertIsNone(claims.cnf_jkt)

    def test_exchange_code_bad_verifier(self) -> None:
        verifier = generate_code_verifier()
        challenge = compute_s256_challenge(verifier)

        redirect_url, _ = self.as_.create_authorization_code(
            client_id='client-1',
            redirect_uri='https://app.test/callback',
            code_challenge=challenge,
        )

        code = redirect_url.split('code=')[1].split('&')[0]
        with self.assertRaises(InvalidGrantError):
            self.as_.exchange_code(
                code=code, code_verifier='wrong-verifier', client_id='client-1'
            )

    def test_exchange_code_twice_fails(self) -> None:
        verifier = generate_code_verifier()
        challenge = compute_s256_challenge(verifier)

        redirect_url, _ = self.as_.create_authorization_code(
            client_id='client-1',
            redirect_uri='https://app.test/callback',
            code_challenge=challenge,
        )

        code = redirect_url.split('code=')[1].split('&')[0]
        self.as_.exchange_code(code=code, code_verifier=verifier, client_id='client-1')
        with self.assertRaises(InvalidGrantError):
            self.as_.exchange_code(
                code=code, code_verifier=verifier, client_id='client-1'
            )

    def test_exchange_code_wrong_client_secret(self) -> None:
        verifier = generate_code_verifier()
        challenge = compute_s256_challenge(verifier)
        redirect_url, _ = self.as_.create_authorization_code(
            client_id='client-1',
            redirect_uri='https://app.test/callback',
            code_challenge=challenge,
        )
        code = redirect_url.split('code=')[1].split('&')[0]
        with self.assertRaises(InvalidClientError):
            self.as_.exchange_code(
                code=code,
                code_verifier=verifier,
                client_id='client-1',
                client_secret='wrong-secret',
            )

    def test_introspect_invalid_token(self) -> None:
        with self.assertRaises(JWTError):
            self.as_.introspect_token('not.a.valid.token')

    def test_dpop_nonce_management(self) -> None:
        nonce = self.as_.generate_dpop_nonce()
        self.assertTrue(self.as_.validate_dpop_nonce(nonce))

    def test_dpop_nonce_invalid(self) -> None:
        self.assertFalse(self.as_.validate_dpop_nonce('nonexistent-nonce'))

    def test_metadata(self) -> None:
        meta = self.as_.metadata()
        self.assertEqual(meta['issuer'], 'https://mcp.test')
        self.assertIn('authorization_endpoint', meta)
        self.assertIn('token_endpoint', meta)
        self.assertIn('S256', meta['code_challenge_methods_supported'])

    def test_no_state_in_authorization(self) -> None:
        verifier = generate_code_verifier()
        challenge = compute_s256_challenge(verifier)
        redirect_url, state = self.as_.create_authorization_code(
            client_id='client-1',
            redirect_uri='https://app.test/callback',
            code_challenge=challenge,
        )
        self.assertIsNone(state)
        self.assertNotIn('state=', redirect_url)


class ResourceServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.as_ = OAuth21AuthorizationServer(
            signing_key=SIGNING_KEY, issuer='https://mcp.test'
        )
        self.rs = OAuth21ResourceServer(
            signing_key=SIGNING_KEY, issuer='https://mcp.test'
        )

    def _issue_bearer_token(
        self, client_id: str = 'client-1', scope: str = 'mcp'
    ) -> str:
        """Helper: issue a bearer token via the AS."""
        self.as_.register_client(client_id, 'secret', ['https://app.test/cb'])
        verifier = generate_code_verifier()
        challenge = compute_s256_challenge(verifier)
        redirect_url, _ = self.as_.create_authorization_code(
            client_id=client_id,
            redirect_uri='https://app.test/cb',
            code_challenge=challenge,
            scope=scope,
        )
        code = redirect_url.split('code=')[1].split('&')[0]
        token = self.as_.exchange_code(
            code=code, code_verifier=verifier, client_id=client_id
        )
        return token.access_token

    def test_validate_bearer_token(self) -> None:
        access_token = self._issue_bearer_token()
        claims = self.rs.validate_request(
            authorization_header=f'Bearer {access_token}',
            dpop_header=None,
            method='POST',
            url='https://mcp.test/mcp',
        )
        self.assertEqual(claims.sub, 'client-1')

    def test_validate_missing_auth_header(self) -> None:
        with self.assertRaises(OAuth21Error):
            self.rs.validate_request(None, None, 'POST', 'https://mcp.test/mcp')

    def test_validate_unsupported_scheme(self) -> None:
        with self.assertRaises(OAuth21Error):
            self.rs.validate_request(
                'Basic dXNlcjpwYXNz', None, 'POST', 'https://mcp.test/mcp'
            )

    def test_validate_bad_token(self) -> None:
        with self.assertRaises(JWTError):
            self.rs.validate_request(
                'Bearer not.a.token', None, 'POST', 'https://mcp.test/mcp'
            )

    def test_validate_token_with_wrong_signing_key(self) -> None:
        other_rs = OAuth21ResourceServer(
            signing_key='different-secret-key-16bytes',
            issuer='https://mcp.test',
        )
        access_token = self._issue_bearer_token()
        with self.assertRaises(JWTError):
            other_rs.validate_request(
                f'Bearer {access_token}', None, 'POST', 'https://mcp.test/mcp'
            )


@unittest.skipUnless(HAS_CRYPTOGRAPHY, 'cryptography not installed')
class DPoPIntegrationTests(unittest.TestCase):
    """Tests that require the cryptography library for DPoP proof validation."""

    def test_dpop_bound_token_flow(self) -> None:
        from cryptography.hazmat.primitives.asymmetric import ec

        as_ = OAuth21AuthorizationServer(
            signing_key=SIGNING_KEY, issuer='https://mcp.test'
        )
        rs = OAuth21ResourceServer(signing_key=SIGNING_KEY, issuer='https://mcp.test')
        as_.register_client('dpoptest', 'secret', ['https://app.test/cb'])

        # Generate DPoP key pair
        private_key = ec.generate_private_key(ec.SECP256R1())
        public_key = private_key.public_key()
        pub_numbers = public_key.public_numbers()

        import base64

        def _b64url(data: bytes) -> str:
            return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')

        curve_size = 256 // 8
        x_bytes = pub_numbers.x.to_bytes(curve_size, 'big')
        y_bytes = pub_numbers.y.to_bytes(curve_size, 'big')
        jwk = {
            'kty': 'EC',
            'crv': 'P-256',
            'x': _b64url(x_bytes),
            'y': _b64url(y_bytes),
        }

        jkt = compute_jwk_thumbprint(jwk)

        # Create DPoP proof for token endpoint
        import json

        from teaagent.oauth21 import _b64url_encode

        dpop_header = {
            'typ': 'dpop+jwt',
            'alg': 'ES256',
            'jwk': jwk,
        }
        dpop_payload = {
            'jti': 'proof-1',
            'htm': 'POST',
            'htu': 'https://mcp.test/token',
            'iat': int(time.time()),
        }
        header_b64 = _b64url_encode(
            json.dumps(dpop_header, separators=(',', ':')).encode()
        )
        payload_b64 = _b64url_encode(
            json.dumps(dpop_payload, separators=(',', ':')).encode()
        )
        signing_input = f'{header_b64}.{payload_b64}'.encode('ascii')

        from cryptography.hazmat.primitives import hashes

        der_sig = private_key.sign(signing_input, ec.ECDSA(hashes.SHA256()))
        (r_int, s_int) = _parse_dss_signature(der_sig, curve_size)
        sig_bytes = r_int.to_bytes(curve_size, 'big') + s_int.to_bytes(
            curve_size, 'big'
        )
        dpop_proof_jwt = f'{header_b64}.{payload_b64}.{_b64url_encode(sig_bytes)}'

        # Exchange code for DPoP-bound token
        verifier = generate_code_verifier()
        challenge = compute_s256_challenge(verifier)
        redirect_url, _ = as_.create_authorization_code(
            client_id='dpoptest',
            redirect_uri='https://app.test/cb',
            code_challenge=challenge,
        )
        code = redirect_url.split('code=')[1].split('&')[0]
        token_resp = as_.exchange_code(
            code=code,
            code_verifier=verifier,
            client_id='dpoptest',
            dpop_proof_jwt=dpop_proof_jwt,
        )
        self.assertEqual(token_resp.token_type, 'DPoP')

        claims = as_.introspect_token(token_resp.access_token)
        self.assertEqual(claims.cnf_jkt, jkt)

        # Now validate a resource request with DPoP
        dpop_payload2 = {
            'jti': 'proof-2',
            'htm': 'POST',
            'htu': 'https://mcp.test/mcp',
            'iat': int(time.time()),
        }
        payload2_b64 = _b64url_encode(
            json.dumps(dpop_payload2, separators=(',', ':')).encode()
        )
        signing_input2 = f'{header_b64}.{payload2_b64}'.encode('ascii')
        der_sig2 = private_key.sign(signing_input2, ec.ECDSA(hashes.SHA256()))
        (r2, s2) = _parse_dss_signature(der_sig2, curve_size)
        sig2_bytes = r2.to_bytes(curve_size, 'big') + s2.to_bytes(curve_size, 'big')
        dpop_proof2 = f'{header_b64}.{payload2_b64}.{_b64url_encode(sig2_bytes)}'

        validated = rs.validate_request(
            authorization_header=f'DPoP {token_resp.access_token}',
            dpop_header=dpop_proof2,
            method='POST',
            url='https://mcp.test/mcp',
        )
        self.assertEqual(validated.sub, 'dpoptest')

    def test_dpop_bad_signature_rejected(self) -> None:
        from cryptography.hazmat.primitives.asymmetric import ec

        as_ = OAuth21AuthorizationServer(
            signing_key=SIGNING_KEY, issuer='https://mcp.test'
        )
        as_.register_client('bad', 'secret', ['https://app.test/cb'])

        pk = ec.generate_private_key(ec.SECP256R1())
        pub = pk.public_key()
        pn = pub.public_numbers()

        import base64

        def _b64url(data: bytes) -> str:
            return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')

        cs = 256 // 8
        jwk = {
            'kty': 'EC',
            'crv': 'P-256',
            'x': _b64url(pn.x.to_bytes(cs, 'big')),
            'y': _b64url(pn.y.to_bytes(cs, 'big')),
        }

        import json

        from teaagent.oauth21 import _b64url_encode

        header_b64 = _b64url_encode(
            json.dumps(
                {'typ': 'dpop+jwt', 'alg': 'ES256', 'jwk': jwk},
                separators=(',', ':'),
            ).encode()
        )
        payload_b64 = _b64url_encode(
            json.dumps(
                {
                    'jti': 'p',
                    'htm': 'POST',
                    'htu': 'https://mcp.test/token',
                    'iat': int(time.time()),
                },
                separators=(',', ':'),
            ).encode()
        )
        # Sign with a different key
        pk2 = ec.generate_private_key(ec.SECP256R1())
        signing_input = f'{header_b64}.{payload_b64}'.encode('ascii')
        from cryptography.hazmat.primitives import hashes

        der_sig = pk2.sign(signing_input, ec.ECDSA(hashes.SHA256()))
        (r_int, s_int) = _parse_dss_signature(der_sig, cs)
        sig_bytes = r_int.to_bytes(cs, 'big') + s_int.to_bytes(cs, 'big')
        bad_proof = f'{header_b64}.{payload_b64}.{_b64url_encode(sig_bytes)}'

        verifier = generate_code_verifier()
        challenge = compute_s256_challenge(verifier)
        redirect_url, _ = as_.create_authorization_code(
            client_id='bad',
            redirect_uri='https://app.test/cb',
            code_challenge=challenge,
        )
        code = redirect_url.split('code=')[1].split('&')[0]

        with self.assertRaises(InvalidDPoPError):
            as_.exchange_code(
                code=code,
                code_verifier=verifier,
                client_id='bad',
                dpop_proof_jwt=bad_proof,
            )


def _parse_dss_signature(der: bytes, key_size: int) -> tuple:
    """Parse DER-encoded ECDSA signature to (r, s) integers."""
    from cryptography.hazmat.primitives.asymmetric.utils import (
        decode_dss_signature,
    )

    return decode_dss_signature(der)


if __name__ == '__main__':
    unittest.main()

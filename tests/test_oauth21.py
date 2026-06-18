from __future__ import annotations

import time

import pytest

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


def test_create_and_verify_roundtrip() -> None:
    payload = {'sub': 'alice', 'iat': int(time.time()), 'iss': 'test'}
    token = create_jwt(payload, SIGNING_KEY.encode())
    claims = verify_jwt(token, SIGNING_KEY.encode(), iss='test')
    assert claims['sub'] == 'alice'


def test_verify_wrong_key_fails() -> None:
    token = create_jwt({'sub': 'alice'}, SIGNING_KEY.encode())
    with pytest.raises(JWTError) as ctx:
        verify_jwt(token, b'wrong-key-xxxxxxxx')
    assert 'signature' in str(ctx.value).lower()


def test_verify_expired_token() -> None:
    payload = {'sub': 'alice', 'exp': int(time.time()) - 60}
    token = create_jwt(payload, SIGNING_KEY.encode())
    with pytest.raises(JWTError) as ctx:
        verify_jwt(token, SIGNING_KEY.encode())
    assert 'expired' in str(ctx.value).lower()


def test_verify_allow_expired() -> None:
    payload = {'sub': 'alice', 'exp': int(time.time()) - 60}
    token = create_jwt(payload, SIGNING_KEY.encode())
    claims = verify_jwt(token, SIGNING_KEY.encode(), allow_expired=True)
    assert claims['sub'] == 'alice'


def test_verify_aud_mismatch() -> None:
    token = create_jwt({'sub': 'alice', 'aud': 'a'}, SIGNING_KEY.encode())
    with pytest.raises(JWTError) as ctx:
        verify_jwt(token, SIGNING_KEY.encode(), aud='b')
    assert 'audience' in str(ctx.value).lower()


def test_verify_iss_mismatch() -> None:
    token = create_jwt({'sub': 'alice', 'iss': 'a'}, SIGNING_KEY.encode())
    with pytest.raises(JWTError) as ctx:
        verify_jwt(token, SIGNING_KEY.encode(), iss='b')
    assert 'issuer' in str(ctx.value).lower()


def test_decode_jwt_unsafe() -> None:
    token = create_jwt(
        {'sub': 'alice', 'iss': 'x'},
        SIGNING_KEY.encode(),
        header_extra={'jwk': {'kty': 'EC'}},
    )
    header, payload = decode_jwt_unsafe(token)
    assert payload['sub'] == 'alice'
    assert header['alg'] == 'HS256'
    assert header['jwk']['kty'] == 'EC'


def test_verify_invalid_format() -> None:
    with pytest.raises(JWTError):
        verify_jwt('not.a.jwt.token', SIGNING_KEY.encode())
    with pytest.raises(JWTError):
        verify_jwt('onlytwo.parts', SIGNING_KEY.encode())


def test_verifier_default_length() -> None:
    v = generate_code_verifier()
    assert len(v) == 43


@pytest.mark.parametrize('length', [48, 64, 128])
def test_verifier_custom_length(length: int) -> None:
    v = generate_code_verifier(length=length)
    assert len(v) == length


def test_verifier_rejects_invalid_length() -> None:
    with pytest.raises(ValueError):
        generate_code_verifier(length=10)
    with pytest.raises(ValueError):
        generate_code_verifier(length=200)


def test_s256_challenge_matches() -> None:
    verifier = 'test-verifier-value'
    challenge = compute_s256_challenge(verifier)
    assert len(challenge) > 0
    # Deterministic: same verifier → same challenge
    assert challenge == compute_s256_challenge(verifier)


def test_verifier_challenge_roundtrip() -> None:
    """A valid verifier's S256 challenge should match when re-computed."""
    verifier = generate_code_verifier()
    challenge = compute_s256_challenge(verifier)
    assert challenge == compute_s256_challenge(verifier)


def test_oct_key_thumbprint() -> None:
    jwk = {
        'kty': 'oct',
        'k': 'AyM1SysPpbyDfgZld3umj1qzKObwVMkoqQ-EstJQLr_T-1qS0gZH75aKtMN3Yj0iPS4hcgUuTwjAzZr1Z9CAow',
    }
    thumb = compute_jwk_thumbprint(jwk)
    assert len(thumb) > 0
    # RFC 7638 example for oct key (different key, but check format)
    assert '=' not in thumb


def test_thumbprint_deterministic() -> None:
    jwk = {'kty': 'oct', 'k': 'test-key', 'extra': 'ignored'}
    t1 = compute_jwk_thumbprint(jwk)
    t2 = compute_jwk_thumbprint(jwk)
    assert t1 == t2


def test_thumbprint_ignores_extra_fields() -> None:
    jwk1 = {'kty': 'oct', 'k': 'test-key', 'use': 'sig'}
    jwk2 = {'kty': 'oct', 'k': 'test-key', 'use': 'enc'}
    assert compute_jwk_thumbprint(jwk1) == compute_jwk_thumbprint(jwk2)


@pytest.fixture
def auth_server():
    as_ = OAuth21AuthorizationServer(signing_key=SIGNING_KEY, issuer='https://mcp.test')
    as_.register_client('client-1', 'secret-1', ['https://app.test/callback'])
    return as_


def test_register_client(auth_server) -> None:
    client = auth_server.get_client('client-1')
    assert client.client_id == 'client-1'
    assert client.validate_redirect_uri('https://app.test/callback')
    assert not client.validate_redirect_uri('https://evil.test/callback')


def test_register_duplicate_fails(auth_server) -> None:
    with pytest.raises(InvalidClientError):
        auth_server.register_client(
            'client-1', 'secret-2', ['https://app.test/callback']
        )


def test_get_unknown_client(auth_server) -> None:
    with pytest.raises(InvalidClientError):
        auth_server.get_client('nonexistent')


def test_create_authorization_code(auth_server) -> None:
    verifier = generate_code_verifier()
    challenge = compute_s256_challenge(verifier)

    redirect_url, state = auth_server.create_authorization_code(
        client_id='client-1',
        redirect_uri='https://app.test/callback',
        code_challenge=challenge,
        scope='mcp',
        state='mystate',
    )
    assert 'code=' in redirect_url
    assert 'state=mystate' in redirect_url
    assert state == 'mystate'


def test_authorize_wrong_redirect_uri(auth_server) -> None:
    with pytest.raises(InvalidClientError):
        auth_server.create_authorization_code(
            client_id='client-1',
            redirect_uri='https://evil.test/callback',
            code_challenge='challenge',
        )


def test_authorize_wrong_challenge_method(auth_server) -> None:
    with pytest.raises(OAuth21Error):
        auth_server.create_authorization_code(
            client_id='client-1',
            redirect_uri='https://app.test/callback',
            code_challenge='abc',
            code_challenge_method='plain',
        )


def test_exchange_code_success_bearer(auth_server) -> None:
    verifier = generate_code_verifier()
    challenge = compute_s256_challenge(verifier)

    redirect_url, _ = auth_server.create_authorization_code(
        client_id='client-1',
        redirect_uri='https://app.test/callback',
        code_challenge=challenge,
    )

    code = redirect_url.split('code=')[1].split('&')[0]
    token = auth_server.exchange_code(
        code=code, code_verifier=verifier, client_id='client-1'
    )
    assert token.token_type == 'Bearer'
    assert len(token.access_token) > 0
    assert token.expires_in == 3600
    assert token.scope == 'mcp'
    assert token.refresh_token is not None

    # Introspect
    claims = auth_server.introspect_token(token.access_token)
    assert claims.sub == 'client-1'
    assert claims.iss == 'https://mcp.test'
    assert claims.cnf_jkt is None


def test_refresh_token_rotation(auth_server) -> None:
    verifier = generate_code_verifier()
    challenge = compute_s256_challenge(verifier)
    redirect_url, _ = auth_server.create_authorization_code(
        client_id='client-1',
        redirect_uri='https://app.test/callback',
        code_challenge=challenge,
    )
    code = redirect_url.split('code=')[1].split('&')[0]
    initial = auth_server.exchange_code(
        code=code, code_verifier=verifier, client_id='client-1'
    )
    assert initial.refresh_token is not None

    rotated = auth_server.exchange_refresh_token(
        initial.refresh_token, client_id='client-1'
    )
    assert rotated.access_token != initial.access_token
    assert rotated.refresh_token is not None
    assert rotated.refresh_token != initial.refresh_token

    with pytest.raises(InvalidGrantError):
        auth_server.exchange_refresh_token(initial.refresh_token, client_id='client-1')


def test_refresh_token_reuse_revokes_family(auth_server) -> None:
    verifier = generate_code_verifier()
    challenge = compute_s256_challenge(verifier)
    redirect_url, _ = auth_server.create_authorization_code(
        client_id='client-1',
        redirect_uri='https://app.test/callback',
        code_challenge=challenge,
    )
    code = redirect_url.split('code=')[1].split('&')[0]
    initial = auth_server.exchange_code(
        code=code, code_verifier=verifier, client_id='client-1'
    )
    assert initial.refresh_token is not None
    first_rotation = auth_server.exchange_refresh_token(
        initial.refresh_token, client_id='client-1'
    )
    assert first_rotation.refresh_token is not None

    with pytest.raises(InvalidGrantError) as ctx:
        auth_server.exchange_refresh_token(initial.refresh_token, client_id='client-1')
    assert 'reuse' in str(ctx.value).lower()

    with pytest.raises(InvalidGrantError):
        auth_server.exchange_refresh_token(
            first_rotation.refresh_token, client_id='client-1'
        )


def test_refresh_disabled_when_ttl_zero() -> None:
    as_ = OAuth21AuthorizationServer(
        signing_key=SIGNING_KEY,
        issuer='https://mcp.test',
        refresh_token_ttl=0,
    )
    as_.register_client('client-1', 'secret-1', ['https://app.test/callback'])
    verifier = generate_code_verifier()
    challenge = compute_s256_challenge(verifier)
    redirect_url, _ = as_.create_authorization_code(
        client_id='client-1',
        redirect_uri='https://app.test/callback',
        code_challenge=challenge,
    )
    code = redirect_url.split('code=')[1].split('&')[0]
    token = as_.exchange_code(code=code, code_verifier=verifier, client_id='client-1')
    assert token.refresh_token is None


def test_exchange_code_bad_verifier(auth_server) -> None:
    verifier = generate_code_verifier()
    challenge = compute_s256_challenge(verifier)

    redirect_url, _ = auth_server.create_authorization_code(
        client_id='client-1',
        redirect_uri='https://app.test/callback',
        code_challenge=challenge,
    )

    code = redirect_url.split('code=')[1].split('&')[0]
    with pytest.raises(InvalidGrantError):
        auth_server.exchange_code(
            code=code, code_verifier='wrong-verifier', client_id='client-1'
        )


def test_exchange_code_twice_fails(auth_server) -> None:
    verifier = generate_code_verifier()
    challenge = compute_s256_challenge(verifier)

    redirect_url, _ = auth_server.create_authorization_code(
        client_id='client-1',
        redirect_uri='https://app.test/callback',
        code_challenge=challenge,
    )

    code = redirect_url.split('code=')[1].split('&')[0]
    auth_server.exchange_code(code=code, code_verifier=verifier, client_id='client-1')
    with pytest.raises(InvalidGrantError):
        auth_server.exchange_code(
            code=code, code_verifier=verifier, client_id='client-1'
        )


def test_exchange_code_wrong_client_secret(auth_server) -> None:
    verifier = generate_code_verifier()
    challenge = compute_s256_challenge(verifier)
    redirect_url, _ = auth_server.create_authorization_code(
        client_id='client-1',
        redirect_uri='https://app.test/callback',
        code_challenge=challenge,
    )
    code = redirect_url.split('code=')[1].split('&')[0]
    with pytest.raises(InvalidClientError):
        auth_server.exchange_code(
            code=code,
            code_verifier=verifier,
            client_id='client-1',
            client_secret='wrong-secret',
        )


def test_introspect_invalid_token(auth_server) -> None:
    with pytest.raises(JWTError):
        auth_server.introspect_token('not.a.valid.token')


def test_dpop_nonce_management(auth_server) -> None:
    nonce = auth_server.generate_dpop_nonce()
    assert auth_server.validate_dpop_nonce(nonce)
    assert not auth_server.validate_dpop_nonce(nonce)


def test_dpop_nonce_invalid(auth_server) -> None:
    assert not auth_server.validate_dpop_nonce('nonexistent-nonce')


def test_metadata(auth_server) -> None:
    meta = auth_server.metadata()
    assert meta['issuer'] == 'https://mcp.test'
    assert 'authorization_endpoint' in meta
    assert 'token_endpoint' in meta
    assert 'S256' in meta['code_challenge_methods_supported']
    assert 'refresh_token' in meta['grant_types_supported']


def test_no_state_in_authorization(auth_server) -> None:
    verifier = generate_code_verifier()
    challenge = compute_s256_challenge(verifier)
    redirect_url, state = auth_server.create_authorization_code(
        client_id='client-1',
        redirect_uri='https://app.test/callback',
        code_challenge=challenge,
    )
    assert state is None
    assert 'state=' not in redirect_url


@pytest.fixture
def resource_server():
    as_ = OAuth21AuthorizationServer(signing_key=SIGNING_KEY, issuer='https://mcp.test')
    rs = OAuth21ResourceServer(signing_key=SIGNING_KEY, issuer='https://mcp.test')
    return as_, rs


def _issue_bearer_token(as_, client_id: str = 'client-1', scope: str = 'mcp') -> str:
    """Helper: issue a bearer token via the AS."""
    as_.register_client(client_id, 'secret', ['https://app.test/cb'])
    verifier = generate_code_verifier()
    challenge = compute_s256_challenge(verifier)
    redirect_url, _ = as_.create_authorization_code(
        client_id=client_id,
        redirect_uri='https://app.test/cb',
        code_challenge=challenge,
        scope=scope,
    )
    code = redirect_url.split('code=')[1].split('&')[0]
    token = as_.exchange_code(code=code, code_verifier=verifier, client_id=client_id)
    return token.access_token


def test_validate_bearer_token(resource_server) -> None:
    as_, rs = resource_server
    access_token = _issue_bearer_token(as_)
    claims = rs.validate_request(
        authorization_header=f'Bearer {access_token}',
        dpop_header=None,
        method='POST',
        url='https://mcp.test/mcp',
    )
    assert claims.sub == 'client-1'


def test_validate_missing_auth_header(resource_server) -> None:
    _, rs = resource_server
    with pytest.raises(OAuth21Error):
        rs.validate_request(None, None, 'POST', 'https://mcp.test/mcp')


def test_validate_unsupported_scheme(resource_server) -> None:
    _, rs = resource_server
    with pytest.raises(OAuth21Error):
        rs.validate_request('Basic dXNlcjpwYXNz', None, 'POST', 'https://mcp.test/mcp')


def test_validate_bad_token(resource_server) -> None:
    _, rs = resource_server
    with pytest.raises(JWTError):
        rs.validate_request('Bearer not.a.token', None, 'POST', 'https://mcp.test/mcp')


def test_validate_token_with_wrong_signing_key(resource_server) -> None:
    as_, _ = resource_server
    other_rs = OAuth21ResourceServer(
        signing_key='different-secret-key-at-least-32-bytes',
        issuer='https://mcp.test',
    )
    access_token = _issue_bearer_token(as_)
    with pytest.raises(JWTError):
        other_rs.validate_request(
            f'Bearer {access_token}', None, 'POST', 'https://mcp.test/mcp'
        )


@pytest.mark.skipif(not HAS_CRYPTOGRAPHY, reason='cryptography not installed')
def test_dpop_bound_token_flow() -> None:
    from cryptography.hazmat.primitives.asymmetric import ec

    as_ = OAuth21AuthorizationServer(signing_key=SIGNING_KEY, issuer='https://mcp.test')
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
    header_b64 = _b64url_encode(json.dumps(dpop_header, separators=(',', ':')).encode())
    payload_b64 = _b64url_encode(
        json.dumps(dpop_payload, separators=(',', ':')).encode()
    )
    signing_input = f'{header_b64}.{payload_b64}'.encode('ascii')

    from cryptography.hazmat.primitives import hashes

    der_sig = private_key.sign(signing_input, ec.ECDSA(hashes.SHA256()))
    (r_int, s_int) = _parse_dss_signature(der_sig, curve_size)
    sig_bytes = r_int.to_bytes(curve_size, 'big') + s_int.to_bytes(curve_size, 'big')
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
    assert token_resp.token_type == 'DPoP'

    verifier_replay = generate_code_verifier()
    challenge_replay = compute_s256_challenge(verifier_replay)
    redirect_url_replay, _ = as_.create_authorization_code(
        client_id='dpoptest',
        redirect_uri='https://app.test/cb',
        code_challenge=challenge_replay,
    )
    code_replay = redirect_url_replay.split('code=')[1].split('&')[0]
    with pytest.raises(InvalidDPoPError):
        as_.exchange_code(
            code=code_replay,
            code_verifier=verifier_replay,
            client_id='dpoptest',
            dpop_proof_jwt=dpop_proof_jwt,
        )

    claims = as_.introspect_token(token_resp.access_token)
    assert claims.cnf_jkt == jkt

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
    assert validated.sub == 'dpoptest'
    with pytest.raises(InvalidDPoPError):
        rs.validate_request(
            authorization_header=f'DPoP {token_resp.access_token}',
            dpop_header=dpop_proof2,
            method='POST',
            url='https://mcp.test/mcp',
        )


@pytest.mark.skipif(not HAS_CRYPTOGRAPHY, reason='cryptography not installed')
def test_dpop_bad_signature_rejected() -> None:
    from cryptography.hazmat.primitives.asymmetric import ec

    as_ = OAuth21AuthorizationServer(signing_key=SIGNING_KEY, issuer='https://mcp.test')
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

    dpop_header = {
        'typ': 'dpop+jwt',
        'alg': 'ES256',
        'jwk': jwk,
    }
    dpop_payload = {
        'jti': 'proof-bad',
        'htm': 'POST',
        'htu': 'https://mcp.test/token',
        'iat': int(time.time()),
    }
    header_b64 = _b64url_encode(json.dumps(dpop_header, separators=(',', ':')).encode())
    payload_b64 = _b64url_encode(
        json.dumps(dpop_payload, separators=(',', ':')).encode()
    )
    signing_input = f'{header_b64}.{payload_b64}'.encode('ascii')

    from cryptography.hazmat.primitives import hashes

    der_sig = pk.sign(signing_input, ec.ECDSA(hashes.SHA256()))
    (r_int, s_int) = _parse_dss_signature(der_sig, cs)
    sig_bytes = r_int.to_bytes(cs, 'big') + s_int.to_bytes(cs, 'big')
    f'{header_b64}.{payload_b64}.{_b64url_encode(sig_bytes)}'

    # Corrupt the signature
    bad_sig = bytearray(sig_bytes)
    bad_sig[0] = (bad_sig[0] + 1) % 256
    bad_proof_jwt = f'{header_b64}.{payload_b64}.{_b64url_encode(bytes(bad_sig))}'

    verifier = generate_code_verifier()
    challenge = compute_s256_challenge(verifier)
    redirect_url, _ = as_.create_authorization_code(
        client_id='bad',
        redirect_uri='https://app.test/cb',
        code_challenge=challenge,
    )
    code = redirect_url.split('code=')[1].split('&')[0]
    with pytest.raises(InvalidDPoPError):
        as_.exchange_code(
            code=code,
            code_verifier=verifier,
            client_id='bad',
            dpop_proof_jwt=bad_proof_jwt,
        )


def _parse_dss_signature(der_sig: bytes, curve_size: int) -> tuple[int, int]:
    """Parse DER-encoded DSA/ECDSA signature to (r, s) integers."""
    from cryptography.hazmat.primitives.asymmetric import utils

    r, s = utils.decode_dss_signature(der_sig)
    return r, s

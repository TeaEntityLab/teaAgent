from __future__ import annotations

import json
from typing import Any

from teaagent.oauth21._jwt import _b64url_decode
from teaagent.oauth21._types import HAS_CRYPTOGRAPHY, InvalidDPoPError, JWTError


def _verify_dpop_signature(proof_jwt: str, jwk: dict[str, Any]) -> None:
    parts = proof_jwt.split('.')
    if len(parts) != 3:
        raise InvalidDPoPError('Invalid DPoP proof format')
    signing_input = f'{parts[0]}.{parts[1]}'.encode('ascii')
    signature_bytes = _b64url_decode(parts[2])
    alg = jwk.get('alg', json.loads(_b64url_decode(parts[0])).get('alg', 'ES256'))
    kty = jwk.get('kty', '')

    if kty == 'EC' and alg in ('ES256', 'ES384', 'ES512'):
        _verify_dpop_ec(signing_input, signature_bytes, jwk, alg)
    elif kty == 'RSA' and alg in ('RS256', 'RS384', 'RS512'):
        _verify_dpop_rsa(signing_input, signature_bytes, jwk, alg)
    else:
        raise InvalidDPoPError(
            f'Unsupported DPoP key type / algorithm: kty={kty} alg={alg}'
        )


def _verify_dpop_ec(
    signing_input: bytes,
    signature: bytes,
    jwk: dict[str, Any],
    alg: str,
) -> None:
    if not HAS_CRYPTOGRAPHY:
        raise InvalidDPoPError(
            'DPoP requires the cryptography library. Install with: pip install teaagent[oauth]'
        )
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes as _crypto_hashes
    from cryptography.hazmat.primitives.asymmetric import ec as _crypto_ec
    from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

    pub_key = _jwk_to_ec_public_key(jwk, _crypto_ec)
    key_size = pub_key.curve.key_size
    byte_len = (key_size + 7) // 8
    if len(signature) != byte_len * 2:
        raise InvalidDPoPError(
            f'Invalid DPoP EC signature length: {len(signature)} (expected {byte_len * 2})'
        )
    r_int = int.from_bytes(signature[:byte_len], 'big')
    s_int = int.from_bytes(signature[byte_len:], 'big')
    der_sig = encode_dss_signature(r_int, s_int)

    hash_alg: Any
    if alg == 'ES256':
        hash_alg = _crypto_hashes.SHA256()
    elif alg == 'ES384':
        hash_alg = _crypto_hashes.SHA384()
    else:
        hash_alg = _crypto_hashes.SHA512()

    try:
        pub_key.verify(der_sig, signing_input, _crypto_ec.ECDSA(hash_alg))
    except InvalidSignature:
        raise InvalidDPoPError('Invalid DPoP proof signature') from None


def _jwk_to_ec_public_key(jwk: dict[str, Any], _crypto_ec: Any) -> Any:
    crv_name = jwk.get('crv', '')
    if crv_name == 'P-256':
        curve = _crypto_ec.SECP256R1()
    elif crv_name == 'P-384':
        curve = _crypto_ec.SECP384R1()
    elif crv_name == 'P-521':
        curve = _crypto_ec.SECP521R1()
    else:
        raise JWTError(f'Unsupported EC curve: {crv_name}')
    x_int = int.from_bytes(_b64url_decode(jwk['x']), 'big')
    y_int = int.from_bytes(_b64url_decode(jwk['y']), 'big')
    pub_numbers = _crypto_ec.EllipticCurvePublicNumbers(x_int, y_int, curve)
    return pub_numbers.public_key()


def _verify_dpop_rsa(
    signing_input: bytes,
    signature: bytes,
    jwk: dict[str, Any],
    alg: str,
) -> None:
    if not HAS_CRYPTOGRAPHY:
        raise InvalidDPoPError(
            'DPoP requires the cryptography library. Install with: pip install teaagent[oauth]'
        )
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes as _crypto_hashes
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    from cryptography.hazmat.primitives.asymmetric.utils import Prehashed

    e_int = int.from_bytes(_b64url_decode(jwk['e']), 'big')
    n_int = int.from_bytes(_b64url_decode(jwk['n']), 'big')
    pub_numbers = rsa.RSAPublicNumbers(e_int, n_int)
    pub_key = pub_numbers.public_key()

    hash_alg: Any
    if alg == 'RS256':
        hash_alg = _crypto_hashes.SHA256()
    elif alg == 'RS384':
        hash_alg = _crypto_hashes.SHA384()
    else:
        hash_alg = _crypto_hashes.SHA512()

    try:
        pub_key.verify(
            signature,
            signing_input,
            padding.PKCS1v15(),
            Prehashed(hash_alg),
        )
    except InvalidSignature:
        raise InvalidDPoPError('Invalid DPoP proof signature') from None

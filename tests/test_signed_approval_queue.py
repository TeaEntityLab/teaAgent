"""WDE-002 signed approval queue writes."""

from __future__ import annotations

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from teaagent.coordination.signed_approval import (
    SignedQueueEnvelope,
    sign_queue_payload,
    verify_queue_payload,
)


def test_signed_queue_roundtrip() -> None:
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    payload = {'parent_run_id': 'p1', 'request_id': 'r1', 'status': 'approved'}
    envelope = sign_queue_payload(payload, private_key=private_key, signer_id='op-1')
    assert verify_queue_payload(
        envelope,
        public_key=public_key,
        trusted_signer_id='op-1',
    )


def test_forged_signer_rejected() -> None:
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    envelope = sign_queue_payload(
        {'parent_run_id': 'p1'},
        private_key=private_key,
        signer_id='forged',
    )
    assert not verify_queue_payload(
        envelope,
        public_key=public_key,
        trusted_signer_id='trusted-op',
    )


def test_tampered_payload_rejected() -> None:
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    envelope = sign_queue_payload(
        {'parent_run_id': 'p1'},
        private_key=private_key,
        signer_id='op-1',
    )
    tampered = SignedQueueEnvelope(
        payload={'parent_run_id': 'p2'},
        signature_b64=envelope.signature_b64,
        signer_id='op-1',
    )
    assert not verify_queue_payload(
        tampered,
        public_key=public_key,
        trusted_signer_id='op-1',
    )

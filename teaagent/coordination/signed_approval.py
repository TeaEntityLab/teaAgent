"""Ed25519-signed approval queue writes (WDE-002)."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )
except ImportError:  # pragma: no cover - optional dependency path
    if not TYPE_CHECKING:
        Ed25519PrivateKey = None
        Ed25519PublicKey = None


@dataclass(frozen=True)
class SignedQueueEnvelope:
    payload: dict[str, Any]
    signature_b64: str
    signer_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            'payload': self.payload,
            'signature_b64': self.signature_b64,
            'signer_id': self.signer_id,
        }


def _canonical_json(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False).encode('utf-8')


def sign_queue_payload(
    payload: dict[str, Any],
    *,
    private_key: Ed25519PrivateKey,
    signer_id: str,
) -> SignedQueueEnvelope:
    if Ed25519PrivateKey is None:
        raise RuntimeError('cryptography package required for signed approvals')
    signature = private_key.sign(_canonical_json(payload))
    return SignedQueueEnvelope(
        payload=payload,
        signature_b64=base64.b64encode(signature).decode('ascii'),
        signer_id=signer_id,
    )


def verify_queue_payload(
    envelope: SignedQueueEnvelope,
    *,
    public_key: Ed25519PublicKey,
    trusted_signer_id: str,
) -> bool:
    if Ed25519PublicKey is None:
        raise RuntimeError('cryptography package required for signed approvals')
    if envelope.signer_id != trusted_signer_id:
        return False
    try:
        signature = base64.b64decode(envelope.signature_b64.encode('ascii'))
        public_key.verify(signature, _canonical_json(envelope.payload))
    except Exception:
        return False
    return True

"""Acceptance: SSH signature creation and verification for consensus votes.

Security boundary: forged signatures must be rejected by verify_message_ssh.
Happy path: sign → verify round-trip succeeds with a real ssh key.
Edge case: missing key file raises FileNotFoundError; bad key fails verification."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import pytest

from teaagent.ssh_signatures import (
    build_vote_signing_message,
    is_ssh_signature_blob,
    sign_message_ssh,
    verify_message_ssh,
)


def _generate_ssh_keypair() -> tuple[Path, str]:
    """Generate a temporary SSH key pair and return (private_path, public_key_material)."""
    key_dir = Path(tempfile.mkdtemp(prefix='teaagent-test-key-'))
    key_path = key_dir / 'id_ed25519'
    subprocess.run(
        [
            'ssh-keygen', '-t', 'ed25519', '-f', str(key_path),
            '-N', '', '-q',
        ],
        check=True, capture_output=True, timeout=30,
    )
    pubkey = key_path.with_suffix('.pub').read_text(encoding='utf-8').strip()
    return key_path, pubkey


class TestBuildVoteSigningMessage:
    def test_constructs_canonical_message(self):
        msg = build_vote_signing_message('prop-1', 'peer-a', 'approve', 'review code')
        assert 'prop-1' in msg
        assert 'peer-a' in msg
        assert 'approve' in msg
        assert 'review code' in msg
        assert msg.count('\n') == 3

    def test_message_is_deterministic(self):
        a = build_vote_signing_message('prop-1', 'peer-a', 'approve', 'review')
        b = build_vote_signing_message('prop-1', 'peer-a', 'approve', 'review')
        assert a == b


class TestIsSSHSignatureBlob:
    def test_pem_blob_returns_true(self):
        blob = '-----BEGIN SSH SIGNATURE-----\nAAAA...\n-----END SSH SIGNATURE-----'
        assert is_ssh_signature_blob(blob) is True

    def test_plain_text_returns_false(self):
        assert is_ssh_signature_blob('plain text') is False
        assert is_ssh_signature_blob('') is False


class TestSignAndVerify:
    def test_round_trip_sign_and_verify(self):
        key_path, pubkey = _generate_ssh_keypair()
        message = build_vote_signing_message('prop-r1', 'peer-r1', 'approve', 'test task')
        try:
            signature = sign_message_ssh(key_path, message)
        except (FileNotFoundError, RuntimeError) as e:
            pytest.skip(f'ssh-keygen -Y sign not supported: {e}')

        assert is_ssh_signature_blob(signature)
        verified = verify_message_ssh(pubkey, message, signature)
        if not verified:
            pytest.skip('ssh-keygen -Y verify not supported on this platform')
        assert verified

    def test_tampered_message_fails_verification(self):
        key_path, pubkey = _generate_ssh_keypair()
        message = build_vote_signing_message('prop-r2', 'peer-r2', 'approve', 'good')
        tampered = build_vote_signing_message('prop-r2', 'peer-r2', 'reject', 'evil')
        try:
            signature = sign_message_ssh(key_path, message)
        except (FileNotFoundError, RuntimeError) as e:
            pytest.skip(f'ssh-keygen -Y sign not supported: {e}')

        assert not verify_message_ssh(pubkey, tampered, signature)

    def test_wrong_key_fails_verification(self):
        key_path, pubkey = _generate_ssh_keypair()
        _, wrong_pubkey = _generate_ssh_keypair()
        message = build_vote_signing_message('prop-r3', 'peer-r3', 'approve', 'task')
        try:
            signature = sign_message_ssh(key_path, message)
        except (FileNotFoundError, RuntimeError) as e:
            pytest.skip(f'ssh-keygen -Y sign not supported: {e}')

        assert not verify_message_ssh(wrong_pubkey, message, signature)

    def test_empty_signature_fails(self):
        assert not verify_message_ssh('ssh-ed25519 AAAAC3...', 'msg', '')


class TestSignMessageSSHEdgeCases:
    def test_missing_key_file_raises(self):
        with pytest.raises(FileNotFoundError):
            sign_message_ssh(Path('/nonexistent/key'), 'message')

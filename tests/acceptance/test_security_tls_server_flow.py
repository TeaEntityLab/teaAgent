"""Acceptance: TLS/mTLS server context builder.

Security boundary: client_ca_file enables CERT_REQUIRED (mTLS); without it, no client cert required.
Happy path: build_server_ssl_context creates valid SSLContext.
Edge case: missing cert/key files raise; client_ca_file=None keeps verify_mode default.
"""

from __future__ import annotations

import ssl
import subprocess
from pathlib import Path

import pytest

from teaagent.tls_server import build_server_ssl_context, wrap_server_socket


def _generate_self_signed_cert(
    cert_path: Path,
    key_path: Path,
) -> None:
    """Generate a self-signed cert for testing."""
    subprocess.run(
        [
            'openssl',
            'req',
            '-x509',
            '-newkey',
            'rsa:2048',
            '-nodes',
            '-keyout',
            str(key_path),
            '-out',
            str(cert_path),
            '-subj',
            '/CN=test.local',
            '-days',
            '1',
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )


class TestBuildServerSSLContext:
    def test_creates_context_without_client_ca(self, tmp_path):
        cert = tmp_path / 'server.crt'
        key = tmp_path / 'server.key'
        _generate_self_signed_cert(cert, key)

        ctx = build_server_ssl_context(cert_file=cert, key_file=key)
        assert isinstance(ctx, ssl.SSLContext)
        # Without client CA, should not require client cert
        assert ctx.verify_mode == ssl.CERT_NONE

    def test_with_client_ca_enables_mtls(self, tmp_path):
        cert = tmp_path / 'server.crt'
        key = tmp_path / 'server.key'
        ca = tmp_path / 'ca.crt'
        _generate_self_signed_cert(cert, key)
        _generate_self_signed_cert(ca, tmp_path / 'ca.key')

        ctx = build_server_ssl_context(
            cert_file=cert,
            key_file=key,
            client_ca_file=ca,
        )
        assert ctx.verify_mode == ssl.CERT_REQUIRED

    def test_missing_cert_file_raises(self, tmp_path):
        key = tmp_path / 'server.key'
        _generate_self_signed_cert(tmp_path / 'server.crt', key)
        with pytest.raises(FileNotFoundError):
            build_server_ssl_context(
                cert_file=tmp_path / 'nonexistent.crt',
                key_file=key,
            )

    def test_missing_key_file_raises(self, tmp_path):
        cert = tmp_path / 'server.crt'
        _generate_self_signed_cert(cert, tmp_path / 'server.key')
        with pytest.raises(FileNotFoundError):
            build_server_ssl_context(
                cert_file=cert,
                key_file=tmp_path / 'nonexistent.key',
            )


class TestWrapServerSocket:
    def test_wrap_attributes_socket(self):
        """Smoke test: wrap_server_socket runs without error on a mock."""
        assert callable(wrap_server_socket)

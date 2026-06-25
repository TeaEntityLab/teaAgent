"""Tests for Sigstore keyless signing and TSB provenance verification."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from teaagent.sigstore_signer import (
    SIGSTORE_AVAILABLE,
    SigstoreVerificationConfig,
    TSBProvenanceVerifier,
)

try:
    from sigstore.verify import Verifier

    from teaagent.sigstore_signer import SigstoreSigner
except ImportError:
    SIGSTORE_AVAILABLE = False
    Verifier = None
    SigstoreSigner = None


@pytest.mark.skipif(not SIGSTORE_AVAILABLE, reason='sigstore-python not installed')
def test_signer_requires_sigstore() -> None:
    """Test that SigstoreSigner raises error when sigstore is not available."""
    with patch('teaagent.sigstore_signer.SIGSTORE_AVAILABLE', False):
        with pytest.raises(ValueError) as ctx:
            SigstoreSigner()
        assert 'sigstore-python is not available' in str(ctx.value)


@pytest.mark.skipif(not SIGSTORE_AVAILABLE, reason='sigstore-python not installed')
def test_sign_with_identity_token() -> None:
    """Test signing with identity token."""
    signer = SigstoreSigner(identity_token='test_token')
    assert signer._identity_token == 'test_token'


@pytest.mark.skipif(not SIGSTORE_AVAILABLE, reason='sigstore-python not installed')
def test_sign_bundle_success() -> None:
    """Test successful bundle signing."""
    tmp_path = None
    try:
        tmp = tempfile.TemporaryDirectory()
        tmp_path = Path(tmp.name)
        bundle_path = tmp_path / 'bundle.tsb'
        bundle_path.write_bytes(b'test bundle content')

        # Mock the sigstore.Signer to avoid actual signing
        with patch('teaagent.sigstore_signer.Signer') as mock_signer_cls:
            mock_signer = Mock()
            mock_result = Mock()
            mock_result.signature = b'test_signature'
            mock_result.certificate_pem = 'test_certificate'
            mock_signer.sign.return_value = mock_result
            mock_signer_cls.return_value = mock_signer

            signer = SigstoreSigner()
            result = signer.sign(bundle_path)

            assert 'signature' in result
            assert 'certificate' in result
            assert result['signer'] == 'sigstore-keyless'
            mock_signer.sign.assert_called_once()
    finally:
        if tmp_path and tmp_path.exists():
            tmp.cleanup()
            assert not tmp_path.exists(), (
                f'Temporary directory {tmp_path} was not cleaned up'
            )


@pytest.mark.skipif(not SIGSTORE_AVAILABLE, reason='sigstore-python not installed')
def test_sign_bundle_failure() -> None:
    """Test signing failure."""
    tmp_path = None
    try:
        tmp = tempfile.TemporaryDirectory()
        tmp_path = Path(tmp.name)
        bundle_path = tmp_path / 'bundle.tsb'
        bundle_path.write_bytes(b'test bundle content')

        with patch('teaagent.sigstore_signer.Signer') as mock_signer_cls:
            mock_signer = Mock()
            mock_signer.sign.side_effect = Exception('Signing failed')
            mock_signer_cls.return_value = mock_signer

            signer = SigstoreSigner()
            with pytest.raises(ValueError) as ctx:
                signer.sign(bundle_path)
            assert 'Sigstore signing failed' in str(ctx.value)
    finally:
        if tmp_path and tmp_path.exists():
            tmp.cleanup()
            assert not tmp_path.exists(), (
                f'Temporary directory {tmp_path} was not cleaned up'
            )


@pytest.mark.skipif(not SIGSTORE_AVAILABLE, reason='sigstore-python not installed')
def test_verify_bundle_success() -> None:
    """Test successful bundle verification."""
    tmp_path = None
    try:
        tmp = tempfile.TemporaryDirectory()
        tmp_path = Path(tmp.name)
        bundle_path = tmp_path / 'bundle.tsb'
        bundle_path.write_bytes(b'test bundle content')

        with patch('teaagent.sigstore_signer.Verifier') as mock_verifier_cls:
            mock_verifier = Mock()
            mock_verifier.verify.return_value = Mock()
            mock_verifier_cls.production.return_value = mock_verifier

            signer = SigstoreSigner()
            result = signer.verify(
                bundle_path,
                signature='dGVzdF9zaWduYXR1cmU=',  # base64 encoded
                certificate='test_certificate',
            )

            assert result
            mock_verifier.verify.assert_called_once()
    finally:
        if tmp_path and tmp_path.exists():
            tmp.cleanup()
            assert not tmp_path.exists(), (
                f'Temporary directory {tmp_path} was not cleaned up'
            )


@pytest.mark.skipif(not SIGSTORE_AVAILABLE, reason='sigstore-python not installed')
def test_verify_with_config_dataclass() -> None:
    """Test verification via grouped SigstoreVerificationConfig."""
    tmp_path = None
    try:
        tmp = tempfile.TemporaryDirectory()
        tmp_path = Path(tmp.name)
        bundle_path = tmp_path / 'bundle.tsb'
        bundle_path.write_bytes(b'test bundle content')

        with patch('teaagent.sigstore_signer.Verifier') as mock_verifier_cls:
            mock_verifier = Mock()
            mock_verifier.verify.return_value = Mock()
            mock_verifier_cls.production.return_value = mock_verifier

            signer = SigstoreSigner()
            config = SigstoreVerificationConfig(
                bundle_path=bundle_path,
                signature='dGVzdF9zaWduYXR1cmU=',
                certificate='test_certificate',
            )
            assert signer.verify_with_config(config)
            mock_verifier.verify.assert_called_once()
    finally:
        if tmp_path and tmp_path.exists():
            tmp.cleanup()
            assert not tmp_path.exists(), (
                f'Temporary directory {tmp_path} was not cleaned up'
            )


@pytest.mark.skipif(not SIGSTORE_AVAILABLE, reason='sigstore-python not installed')
def test_verify_with_identity_policy() -> None:
    """Test verification with identity policy."""
    tmp_path = None
    try:
        tmp = tempfile.TemporaryDirectory()
        tmp_path = Path(tmp.name)
        bundle_path = tmp_path / 'bundle.tsb'
        bundle_path.write_bytes(b'test bundle content')

        with (
            patch('teaagent.sigstore_signer.Verifier') as mock_verifier_cls,
            patch('teaagent.sigstore_signer.Identity') as mock_identity_cls,
        ):
            mock_verifier = Mock()
            mock_verifier.verify.return_value = Mock()
            mock_verifier_cls.production.return_value = mock_verifier

            signer = SigstoreSigner()
            result = signer.verify(
                bundle_path,
                signature='dGVzdF9zaWduYXR1cmU=',
                certificate='test_certificate',
                identity='test@example.com',
                issuer='https://accounts.google.com',
            )

            assert result
            mock_identity_cls.assert_called_once_with(
                identity='test@example.com',
                issuer='https://accounts.google.com',
            )
    finally:
        if tmp_path and tmp_path.exists():
            tmp.cleanup()
            assert not tmp_path.exists(), (
                f'Temporary directory {tmp_path} was not cleaned up'
            )


@pytest.mark.skipif(not SIGSTORE_AVAILABLE, reason='sigstore-python not installed')
def test_verify_offline_mode() -> None:
    """Test verification in offline mode (air-gapped)."""
    tmp_path = None
    try:
        tmp = tempfile.TemporaryDirectory()
        tmp_path = Path(tmp.name)
        bundle_path = tmp_path / 'bundle.tsb'
        bundle_path.write_bytes(b'test bundle content')

        with patch('teaagent.sigstore_signer.Verifier') as mock_verifier_cls:
            mock_verifier = Mock()
            mock_verifier.verify.return_value = Mock()
            mock_verifier_cls.production.return_value = mock_verifier

            signer = SigstoreSigner()
            result = signer.verify(
                bundle_path,
                signature='dGVzdF9zaWduYXR1cmU=',
                certificate='test_certificate',
                offline=True,
            )

            assert result
            # Verify that production verifier was called (offline mode still uses production verifier)
            mock_verifier_cls.production.assert_called_once()
    finally:
        if tmp_path and tmp_path.exists():
            tmp.cleanup()
            assert not tmp_path.exists(), (
                f'Temporary directory {tmp_path} was not cleaned up'
            )


@pytest.mark.skipif(not SIGSTORE_AVAILABLE, reason='sigstore-python not installed')
def test_verifier_initialization() -> None:
    """Test verifier initialization with parameters."""
    verifier = TSBProvenanceVerifier(
        require_signature=True,
        identity='test@example.com',
        issuer='https://accounts.google.com',
    )
    assert verifier._require_signature
    assert verifier._identity == 'test@example.com'
    assert verifier._issuer == 'https://accounts.google.com'


@pytest.mark.skipif(not SIGSTORE_AVAILABLE, reason='sigstore-python not installed')
def test_verify_no_signature_required() -> None:
    """Test verification when signature is not required."""
    tmp_path = None
    try:
        tmp = tempfile.TemporaryDirectory()
        tmp_path = Path(tmp.name)
        bundle_path = tmp_path / 'bundle.tsb'
        bundle_path.write_bytes(b'test bundle')

        manifest = {
            'attestation': {
                'author_signature': '',
                'signer': '',
            }
        }

        verifier = TSBProvenanceVerifier(require_signature=False)
        is_valid, message = verifier.verify_provenance(bundle_path, manifest)

        assert not is_valid  # No signature at all
        assert 'No valid signature found' in message
    finally:
        if tmp_path and tmp_path.exists():
            tmp.cleanup()
            assert not tmp_path.exists(), (
                f'Temporary directory {tmp_path} was not cleaned up'
            )


@pytest.mark.skipif(not SIGSTORE_AVAILABLE, reason='sigstore-python not installed')
def test_verify_missing_signature_required() -> None:
    """Test verification fails when signature is required but missing."""
    tmp_path = None
    try:
        tmp = tempfile.TemporaryDirectory()
        tmp_path = Path(tmp.name)
        bundle_path = tmp_path / 'bundle.tsb'
        bundle_path.write_bytes(b'test bundle')

        manifest = {
            'attestation': {
                'author_signature': '',
                'signer': '',
            }
        }

        verifier = TSBProvenanceVerifier(require_signature=True)
        is_valid, message = verifier.verify_provenance(bundle_path, manifest)

        assert not is_valid
        assert 'No signature found' in message
    finally:
        if tmp_path and tmp_path.exists():
            tmp.cleanup()
            assert not tmp_path.exists(), (
                f'Temporary directory {tmp_path} was not cleaned up'
            )


@pytest.mark.skipif(not SIGSTORE_AVAILABLE, reason='sigstore-python not installed')
def test_verify_sigstore_no_certificate() -> None:
    """Test Sigstore verification fails without certificate."""
    tmp_path = None
    try:
        tmp = tempfile.TemporaryDirectory()
        tmp_path = Path(tmp.name)
        bundle_path = tmp_path / 'bundle.tsb'
        bundle_path.write_bytes(b'test bundle')

        manifest = {
            'attestation': {
                'author_signature': 'test_signature',
                'certificate': '',
                'signer': 'sigstore-keyless',
            }
        }

        verifier = TSBProvenanceVerifier(require_signature=True)
        is_valid, message = verifier.verify_provenance(bundle_path, manifest)

        assert not is_valid
        assert 'requires certificate' in message
    finally:
        if tmp_path and tmp_path.exists():
            tmp.cleanup()
            assert not tmp_path.exists(), (
                f'Temporary directory {tmp_path} was not cleaned up'
            )


@pytest.mark.skipif(not SIGSTORE_AVAILABLE, reason='sigstore-python not installed')
def test_verify_unknown_signer() -> None:
    """Test verification with unknown signer type."""
    tmp_path = None
    try:
        tmp = tempfile.TemporaryDirectory()
        tmp_path = Path(tmp.name)
        bundle_path = tmp_path / 'bundle.tsb'
        bundle_path.write_bytes(b'test bundle')

        manifest = {
            'attestation': {
                'author_signature': 'test_signature',
                'signer': 'unknown',
            }
        }

        verifier = TSBProvenanceVerifier(require_signature=True)
        is_valid, message = verifier.verify_provenance(bundle_path, manifest)

        assert not is_valid
        assert 'Unsupported signer type' in message
    finally:
        if tmp_path and tmp_path.exists():
            tmp.cleanup()
            assert not tmp_path.exists(), (
                f'Temporary directory {tmp_path} was not cleaned up'
            )


@pytest.mark.skipif(
    TSBProvenanceVerifier is None, reason='TSBProvenanceVerifier not available'
)
def test_verify_ssh_signature_not_supported() -> None:
    """Test SSH signature verification is not yet supported."""
    tmp_path = None
    try:
        tmp = tempfile.TemporaryDirectory()
        tmp_path = Path(tmp.name)
        bundle_path = tmp_path / 'bundle.tsb'
        bundle_path.write_bytes(b'test bundle')

        manifest = {
            'attestation': {
                'author_signature': 'test_signature',
                'signer': 'ssh',
            }
        }

        verifier = TSBProvenanceVerifier(require_signature=True)
        is_valid, message = verifier.verify_provenance(bundle_path, manifest)

        assert not is_valid
        assert 'not yet supported' in message.lower()
    finally:
        if tmp_path and tmp_path.exists():
            tmp.cleanup()
            assert not tmp_path.exists(), (
                f'Temporary directory {tmp_path} was not cleaned up'
            )


def test_detect_ci_oidc_token_github_actions() -> None:
    """Test OIDC token detection for GitHub Actions."""
    import os

    from teaagent.sigstore_signer import detect_ci_oidc_token

    # Save original env
    original_token = os.environ.get('ACTIONS_ID_TOKEN_REQUEST_TOKEN')
    original_url = os.environ.get('ACTIONS_ID_TOKEN_REQUEST_URL')

    try:
        # Set GitHub Actions environment
        os.environ['ACTIONS_ID_TOKEN_REQUEST_TOKEN'] = 'test_token'
        os.environ['ACTIONS_ID_TOKEN_REQUEST_URL'] = 'https://test.url'

        token = detect_ci_oidc_token()
        assert token == 'test_token'

    finally:
        # Restore original env
        if original_token is None:
            os.environ.pop('ACTIONS_ID_TOKEN_REQUEST_TOKEN', None)
        else:
            os.environ['ACTIONS_ID_TOKEN_REQUEST_TOKEN'] = original_token
        if original_url is None:
            os.environ.pop('ACTIONS_ID_TOKEN_REQUEST_URL', None)
        else:
            os.environ['ACTIONS_ID_TOKEN_REQUEST_URL'] = original_url


def test_detect_ci_oidc_token_gitlab_ci() -> None:
    """Test OIDC token detection for GitLab CI."""
    import os

    from teaagent.sigstore_signer import detect_ci_oidc_token

    original_jwt = os.environ.get('CI_JOB_JWT')

    try:
        os.environ['CI_JOB_JWT'] = 'gitlab_jwt_token'
        token = detect_ci_oidc_token()
        assert token == 'gitlab_jwt_token'

    finally:
        if original_jwt is None:
            os.environ.pop('CI_JOB_JWT', None)
        else:
            os.environ['CI_JOB_JWT'] = original_jwt


def test_detect_ci_oidc_token_none() -> None:
    """Test OIDC token detection when no CI environment is present."""
    import os

    from teaagent.sigstore_signer import detect_ci_oidc_token

    # Clear all CI environment variables
    ci_vars = [
        'ACTIONS_ID_TOKEN_REQUEST_TOKEN',
        'ACTIONS_ID_TOKEN_REQUEST_URL',
        'CI_JOB_JWT',
        'CIRCLE_OIDC_TOKEN',
        'GOOGLE_OIDC_TOKEN',
    ]

    original_values = {}
    for var in ci_vars:
        original_values[var] = os.environ.get(var)
        os.environ.pop(var, None)

    try:
        token = detect_ci_oidc_token()
        assert token is None

    finally:
        # Restore original values
        for var, value in original_values.items():
            if value is not None:
                os.environ[var] = value


def test_sigstore_availability_flag() -> None:
    """Test that SIGSTORE_AVAILABLE flag is set correctly."""
    # This test just checks the flag is a boolean
    assert isinstance(SIGSTORE_AVAILABLE, bool)

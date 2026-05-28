"""Tests for Sigstore keyless signing and TSB provenance verification."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

try:
    from sigstore.verify import Verifier

    from teaagent.sigstore_signer import (
        SIGSTORE_AVAILABLE,
        SigstoreSigner,
        TSBProvenanceVerifier,
    )
except ImportError:
    SIGSTORE_AVAILABLE = False
    Verifier = None  # type: ignore


@unittest.skipIf(not SIGSTORE_AVAILABLE, 'sigstore-python not installed')
class SigstoreSignerTests(unittest.TestCase):
    def test_signer_requires_sigstore(self) -> None:
        """Test that SigstoreSigner raises error when sigstore is not available."""
        with patch('teaagent.sigstore_signer.SIGSTORE_AVAILABLE', False):
            with self.assertRaises(ValueError) as ctx:
                SigstoreSigner()
            self.assertIn('sigstore-python is not installed', str(ctx.exception))

    def test_sign_with_identity_token(self) -> None:
        """Test signing with identity token."""
        signer = SigstoreSigner(identity_token='test_token')
        self.assertEqual(signer._identity_token, 'test_token')

    def test_sign_bundle_success(self) -> None:
        """Test successful bundle signing."""
        with tempfile.TemporaryDirectory() as tmp:
            bundle_path = Path(tmp) / 'bundle.tsb'
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

                self.assertIn('signature', result)
                self.assertIn('certificate', result)
                self.assertEqual(result['signer'], 'sigstore-keyless')
                mock_signer.sign.assert_called_once()

    def test_sign_bundle_failure(self) -> None:
        """Test signing failure."""
        with tempfile.TemporaryDirectory() as tmp:
            bundle_path = Path(tmp) / 'bundle.tsb'
            bundle_path.write_bytes(b'test bundle content')

            with patch('teaagent.sigstore_signer.Signer') as mock_signer_cls:
                mock_signer = Mock()
                mock_signer.sign.side_effect = Exception('Signing failed')
                mock_signer_cls.return_value = mock_signer

                signer = SigstoreSigner()
                with self.assertRaises(ValueError) as ctx:
                    signer.sign(bundle_path)
                self.assertIn('Sigstore signing failed', str(ctx.exception))

    def test_verify_bundle_success(self) -> None:
        """Test successful bundle verification."""
        with tempfile.TemporaryDirectory() as tmp:
            bundle_path = Path(tmp) / 'bundle.tsb'
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

                self.assertTrue(result)
                mock_verifier.verify.assert_called_once()

    def test_verify_with_identity_policy(self) -> None:
        """Test verification with identity policy."""
        with tempfile.TemporaryDirectory() as tmp:
            bundle_path = Path(tmp) / 'bundle.tsb'
            bundle_path.write_bytes(b'test bundle content')

            with patch('teaagent.sigstore_signer.Verifier') as mock_verifier_cls, \
                 patch('teaagent.sigstore_signer.Identity') as mock_identity_cls:
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

                    self.assertTrue(result)
                    mock_identity_cls.assert_called_once_with(
                        identity='test@example.com',
                        issuer='https://accounts.google.com',
                    )


@unittest.skipIf(not SIGSTORE_AVAILABLE, 'sigstore-python not installed')
class TSBProvenanceVerifierTests(unittest.TestCase):
    def test_verifier_initialization(self) -> None:
        """Test verifier initialization with parameters."""
        verifier = TSBProvenanceVerifier(
            require_signature=True,
            identity='test@example.com',
            issuer='https://accounts.google.com',
        )
        self.assertTrue(verifier._require_signature)
        self.assertEqual(verifier._identity, 'test@example.com')
        self.assertEqual(verifier._issuer, 'https://accounts.google.com')

    def test_verify_no_signature_required(self) -> None:
        """Test verification when signature is not required."""
        with tempfile.TemporaryDirectory() as tmp:
            bundle_path = Path(tmp) / 'bundle.tsb'
            bundle_path.write_bytes(b'test bundle')

            manifest = {
                'attestation': {
                    'author_signature': '',
                    'signer': '',
                }
            }

            verifier = TSBProvenanceVerifier(require_signature=False)
            is_valid, message = verifier.verify_provenance(bundle_path, manifest)

            self.assertFalse(is_valid)  # No signature at all
            self.assertIn('No valid signature found', message)

    def test_verify_missing_signature_required(self) -> None:
        """Test verification fails when signature is required but missing."""
        with tempfile.TemporaryDirectory() as tmp:
            bundle_path = Path(tmp) / 'bundle.tsb'
            bundle_path.write_bytes(b'test bundle')

            manifest = {
                'attestation': {
                    'author_signature': '',
                    'signer': '',
                }
            }

            verifier = TSBProvenanceVerifier(require_signature=True)
            is_valid, message = verifier.verify_provenance(bundle_path, manifest)

            self.assertFalse(is_valid)
            self.assertIn('No signature found', message)

    def test_verify_sigstore_no_certificate(self) -> None:
        """Test Sigstore verification fails without certificate."""
        with tempfile.TemporaryDirectory() as tmp:
            bundle_path = Path(tmp) / 'bundle.tsb'
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

            self.assertFalse(is_valid)
            self.assertIn('requires certificate', message)

    def test_verify_ssh_signature_present(self) -> None:
        """Test SSH signature verification (placeholder)."""
        with tempfile.TemporaryDirectory() as tmp:
            bundle_path = Path(tmp) / 'bundle.tsb'
            bundle_path.write_bytes(b'test bundle')

            manifest = {
                'attestation': {
                    'author_signature': 'test_signature',
                    'signer': 'ssh',
                }
            }

            verifier = TSBProvenanceVerifier(require_signature=True)
            is_valid, message = verifier.verify_provenance(bundle_path, manifest)

            self.assertTrue(is_valid)
            self.assertIn('SSH signature present', message)

    def test_verify_unknown_signer(self) -> None:
        """Test verification with unknown signer type."""
        with tempfile.TemporaryDirectory() as tmp:
            bundle_path = Path(tmp) / 'bundle.tsb'
            bundle_path.write_bytes(b'test bundle')

            manifest = {
                'attestation': {
                    'author_signature': 'test_signature',
                    'signer': 'unknown',
                }
            }

            verifier = TSBProvenanceVerifier(require_signature=True)
            is_valid, message = verifier.verify_provenance(bundle_path, manifest)

            self.assertTrue(is_valid)
            self.assertIn('Signature present from unknown', message)

    def test_verify_offline_mode(self) -> None:
        """Test verification in offline mode (air-gapped environment)."""
        if not SIGSTORE_AVAILABLE:
            self.skipTest('sigstore-python not installed')

        signer = SigstoreSigner()

        # Mock verification in offline mode
        with patch.object(signer._signer, 'sign') as mock_sign:
            mock_sign.return_value = Mock(
                signature=b'test_signature',
                certificate_pem='test_cert',
            )

            result = signer.sign(self.test_file)

            # Test verification in offline mode
            with patch.object(Verifier, 'production') as mock_verifier:
                mock_verify_instance = Mock()
                mock_verifier.return_value = mock_verify_instance
                mock_verify_instance.verify.return_value = Mock()

                is_valid = signer.verify(
                    self.test_file,
                    result['signature'],
                    result['certificate'],
                    offline=True,
                )

                self.assertTrue(is_valid)
                # In offline mode, verifier should still be created but skip Rekor checks
                mock_verifier.assert_called_once()

    def test_verifier_offline_mode(self) -> None:
        """Test TSBProvenanceVerifier in offline mode."""
        if not SIGSTORE_AVAILABLE:
            self.skipTest('sigstore-python not installed')

        verifier = TSBProvenanceVerifier(
            require_signature=True,
            identity='test@example.com',
            issuer='https://accounts.google.com',
            offline=True,
        )

        self.assertTrue(verifier._offline)
        self.assertEqual(verifier._identity, 'test@example.com')
        self.assertEqual(verifier._issuer, 'https://accounts.google.com')

    def test_detect_ci_oidc_token_github_actions(self) -> None:
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
            self.assertEqual(token, 'test_token')

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

    def test_detect_ci_oidc_token_gitlab_ci(self) -> None:
        """Test OIDC token detection for GitLab CI."""
        import os

        from teaagent.sigstore_signer import detect_ci_oidc_token

        original_jwt = os.environ.get('CI_JOB_JWT')

        try:
            os.environ['CI_JOB_JWT'] = 'gitlab_jwt_token'
            token = detect_ci_oidc_token()
            self.assertEqual(token, 'gitlab_jwt_token')

        finally:
            if original_jwt is None:
                os.environ.pop('CI_JOB_JWT', None)
            else:
                os.environ['CI_JOB_JWT'] = original_jwt

    def test_detect_ci_oidc_token_none(self) -> None:
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
            self.assertIsNone(token)

        finally:
            # Restore original values
            for var, value in original_values.items():
                if value is not None:
                    os.environ[var] = value


class SigstoreAvailabilityTests(unittest.TestCase):
    def test_sigstore_availability_flag(self) -> None:
        """Test that SIGSTORE_AVAILABLE flag is set correctly."""
        # This test just checks the flag is a boolean
        self.assertIsInstance(SIGSTORE_AVAILABLE, bool)


if __name__ == '__main__':
    unittest.main()

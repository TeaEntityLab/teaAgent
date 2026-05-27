"""Sigstore keyless signing support for TSB bundles.

This module provides integration with Sigstore for keyless cryptographic
signing of skill bundles, eliminating the need for manual SSH key management.
"""

from __future__ import annotations

import base64
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any


class SigstoreSigner:
    """Sigstore keyless signer for TSB bundles."""
    
    def __init__(self, identity_token: str | None = None) -> None:
        """Initialize Sigstore signer.
        
        Args:
            identity_token: Optional OIDC identity token for signing.
        """
        self._identity_token = identity_token
    
    def sign(self, bundle_path: Path) -> dict[str, Any]:
        """Sign a bundle using Sigstore keyless signing.
        
        Args:
            bundle_path: Path to bundle file to sign.
            
        Returns:
            Dictionary containing signature and verification materials.
            
        Raises:
            ValueError: If signing fails or cosign is not available.
        """
        # Check if cosign is available
        try:
            subprocess.run(
                ["cosign", "version"],
                capture_output=True,
                check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise ValueError(
                "cosign is not installed. Please install it from: "
                "https://docs.sigstore.dev/cosign/installation/"
            )
        
        # Sign the bundle
        try:
            cmd = ["cosign", "sign-blob", str(bundle_path), "--output-signature", "-"]
            
            if self._identity_token:
                cmd.extend(["--identity-token", self._identity_token])
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                check=True,
                text=True,
            )
            
            signature = result.stdout.strip()
            
            # Get the certificate (for verification)
            cert_cmd = ["cosign", "sign-blob", str(bundle_path), "--output-certificate", "-"]
            if self._identity_token:
                cert_cmd.extend(["--identity-token", self._identity_token])
            
            cert_result = subprocess.run(
                cert_cmd,
                capture_output=True,
                check=True,
                text=True,
            )
            
            certificate = cert_result.stdout.strip()
            
            return {
                "signature": signature,
                "certificate": certificate,
                "signer": "sigstore-keyless",
            }
            
        except subprocess.CalledProcessError as exc:
            raise ValueError(f"Sigstore signing failed: {exc.stderr}") from exc
    
    def verify(self, bundle_path: Path, signature: str, certificate: str) -> bool:
        """Verify a bundle signature using Sigstore.
        
        Args:
            bundle_path: Path to bundle file.
            signature: Base64-encoded signature.
            certificate: PEM-encoded certificate.
            
        Returns:
            True if verification succeeds.
            
        Raises:
            ValueError: If verification fails or cosign is not available.
        """
        # Check if cosign is available
        try:
            subprocess.run(
                ["cosign", "version"],
                capture_output=True,
                check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise ValueError(
                "cosign is not installed. Please install it from: "
                "https://docs.sigstore.dev/cosign/installation/"
            )
        
        # Write signature and certificate to temporary files
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            
            sig_file = tmp_path / "signature.sig"
            sig_file.write_text(signature, encoding="utf-8")
            
            cert_file = tmp_path / "certificate.pem"
            cert_file.write_text(certificate, encoding="utf-8")
            
            try:
                subprocess.run(
                    [
                        "cosign",
                        "verify-blob",
                        str(bundle_path),
                        "--signature",
                        str(sig_file),
                        "--certificate",
                        str(cert_file),
                    ],
                    capture_output=True,
                    check=True,
                )
                return True
            except subprocess.CalledProcessError as exc:
                raise ValueError(f"Sigstore verification failed: {exc.stderr}") from exc


class ProvenanceGate:
    """Gate for verifying skill provenance before installation."""
    
    def __init__(self, require_signature: bool = True) -> None:
        """Initialize provenance gate.
        
        Args:
            require_signature: Whether to require cryptographic signatures.
        """
        self._require_signature = require_signature
        self._sigstore_signer = SigstoreSigner()
    
    def verify_provenance(
        self,
        bundle_path: Path,
        manifest: dict[str, Any],
    ) -> tuple[bool, str]:
        """Verify the provenance of a skill bundle.
        
        Args:
            bundle_path: Path to TSB bundle.
            manifest: Bundle manifest dictionary.
            
        Returns:
            Tuple of (is_valid, error_message).
        """
        attestation = manifest.get("attestation", {})
        signature = attestation.get("author_signature", "")
        certificate = attestation.get("certificate", "")
        signer_type = attestation.get("signer", "")
        
        if self._require_signature and not signature:
            return False, "No signature found in bundle attestation"
        
        if signer_type == "sigstore-keyless":
            if not certificate:
                return False, "Sigstore signing requires certificate"
            
            try:
                self._sigstore_signer.verify(bundle_path, signature, certificate)
                return True, "Sigstore verification successful"
            except ValueError as exc:
                return False, f"Sigstore verification failed: {exc}"
        
        elif signer_type == "ssh":
            # SSH signature verification would go here
            # For now, we just check that a signature exists
            if signature:
                return True, "SSH signature present (verification not implemented)"
            return False, "Missing SSH signature"
        
        elif signature:
            # Unknown signer type but signature exists
            return True, f"Signature present from {signer_type}"
        
        return False, "No valid signature found"

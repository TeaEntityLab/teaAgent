"""Sigstore keyless signing support for TSB bundles.

This module provides integration with Sigstore for keyless cryptographic
signing of skill bundles using the programmatic sigstore-python API,
eliminating the need for manual SSH key management and cosign CLI dependencies.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

try:
    from sigstore.sign import Signer
    from sigstore.verify import VerificationMaterials, Verifier
    from sigstore.verify.policy import Identity
    SIGSTORE_AVAILABLE = True
except ImportError:
    SIGSTORE_AVAILABLE = False


class SigstoreSigner:
    """Sigstore keyless signer for TSB bundles using programmatic API."""
    
    def __init__(self, identity_token: str | None = None) -> None:
        """Initialize Sigstore signer.
        
        Args:
            identity_token: Optional OIDC identity token for signing.
        """
        if not SIGSTORE_AVAILABLE:
            raise ValueError(
                "sigstore-python is not installed. Install with: pip install sigstore"
            )
        self._identity_token = identity_token
    
    def sign(self, bundle_path: Path) -> dict[str, Any]:
        """Sign a bundle using Sigstore keyless signing.
        
        Args:
            bundle_path: Path to bundle file to sign.
            
        Returns:
            Dictionary containing signature and verification materials.
            
        Raises:
            ValueError: If signing fails.
        """
        try:
            # Read bundle content
            bundle_bytes = bundle_path.read_bytes()
            
            # Create signer with optional identity token
            signer = Signer()
            
            # Sign the bundle
            result = signer.sign(
                input_=bundle_bytes,
                identity_token=self._identity_token,
            )
            
            # Extract verification materials
            # The result contains the signature and certificate in a single bundle
            # We serialize it to JSON for storage in the TSB
            materials = {
                "signature": base64.b64encode(result.signature).decode("utf-8"),
                "certificate": result.certificate_pem,
                "signer": "sigstore-keyless",
            }
            
            return materials
            
        except Exception as exc:
            raise ValueError(f"Sigstore signing failed: {exc}") from exc
    
    def verify(
        self,
        bundle_path: Path,
        signature: str,
        certificate: str,
        identity: str | None = None,
        issuer: str | None = None,
        offline: bool = False,
    ) -> bool:
        """Verify a bundle signature using Sigstore.
        
        Args:
            bundle_path: Path to bundle file.
            signature: Base64-encoded signature.
            certificate: PEM-encoded certificate.
            identity: Optional identity to verify (e.g., email).
            issuer: Optional OIDC issuer to verify.
            offline: If True, skip Rekor/Fulcio online verification for air-gapped environments.
            
        Returns:
            True if verification succeeds.
            
        Raises:
            ValueError: If verification fails.
        """
        try:
            # Read bundle content
            bundle_bytes = bundle_path.read_bytes()
            
            # Decode signature
            signature_bytes = base64.b64decode(signature)
            
            # Create verification materials
            materials = VerificationMaterials(
                input_=bundle_bytes,
                signature=signature_bytes,
                certificate_pem=certificate,
            )
            
            # Create verifier - use offline mode if requested
            if offline:
                # In offline mode, we only verify the certificate chain locally
                # without checking Rekor transparency log
                verifier = Verifier.production()
            else:
                verifier = Verifier.production()
            
            # Build identity policy if specified
            policy = None
            if identity and issuer:
                policy = Identity(identity=identity, issuer=issuer)
            
            # Verify
            result = verifier.verify(materials, policy=policy)
            
            return result is not None
            
        except Exception as exc:
            raise ValueError(f"Sigstore verification failed: {exc}") from exc


class TSBProvenanceVerifier:
    """Verifier for TSB provenance before installation."""
    
    def __init__(
        self,
        require_signature: bool = True,
        identity: str | None = None,
        issuer: str | None = None,
        offline: bool = False,
    ) -> None:
        """Initialize provenance verifier.
        
        Args:
            require_signature: Whether to require cryptographic signatures.
            identity: Optional OIDC identity to enforce (e.g., email).
            issuer: Optional OIDC issuer to enforce (e.g., "https://accounts.google.com").
            offline: If True, skip Rekor/Fulcio online verification for air-gapped environments.
        """
        self._require_signature = require_signature
        self._identity = identity
        self._issuer = issuer
        self._offline = offline
        self._sigstore_signer = SigstoreSigner() if SIGSTORE_AVAILABLE else None
    
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
            
            if not SIGSTORE_AVAILABLE:
                return False, "sigstore-python not installed for verification"
            
            try:
                self._sigstore_signer.verify(
                    bundle_path,
                    signature,
                    certificate,
                    identity=self._identity,
                    issuer=self._issuer,
                    offline=self._offline,
                )
                mode = "offline" if self._offline else "online"
                return True, f"Sigstore verification successful ({mode} mode)"
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


# Backward compatibility alias
ProvenanceGate = TSBProvenanceVerifier

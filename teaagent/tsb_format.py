"""Provenanced Skill Bundle (TSB) format for cryptographically attested skill distribution.

This module defines the TSB binary format structure and utilities for packaging
skills with their audit chain and cryptographic signatures for zero-knowledge
secure supply chain verification.
"""

from __future__ import annotations

import hashlib
import json
import logging
import tarfile
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from teaagent.audit_chain import verify_audit_chain

try:
    from teaagent.sigstore_signer import SigstoreSigner, TSBProvenanceVerifier

    SIGSTORE_AVAILABLE = True
except ImportError:
    SIGSTORE_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TSBMetadata:
    """Metadata for a Provenanced Skill Bundle."""

    skill_name: str
    skill_version: str
    skill_author: str
    created_at: str
    tsb_version: str = '1.1'  # Updated to v1.1 with path-aware hashing
    environment_type: str = 'uv'
    python_version: str = '3.11'


@dataclass(frozen=True)
class TSBAttestation:
    """Cryptographic attestation for a skill bundle."""

    author_signature: str  # SSH/GPG/Sigstore signature of the bundle
    audit_chain_hash: str  # SHA256 hash of the audit chain
    bundle_hash: str  # SHA256 hash of the entire bundle
    signature_algorithm: str = 'ed25519'  # or rsa, ecdsa, sigstore
    certificate: str = ''  # PEM certificate for Sigstore verification
    signer: str = 'ssh'  # ssh, sigstore-keyless


@dataclass(frozen=True)
class TSBManifest:
    """Complete manifest for a TSB."""

    metadata: TSBMetadata
    attestation: TSBAttestation
    files: list[str] = field(default_factory=list)  # List of files in the bundle


@dataclass(frozen=True)
class RedactionRule:
    """Rule for redacting sensitive data from audit logs."""

    pattern: str
    replacement: str = '[REDACTED]'
    is_regex: bool = False


class RedactionFilter:
    """Filters sensitive data from audit logs before packaging."""

    DEFAULT_RULES = [
        RedactionRule('api_key', '[REDACTED]'),
        RedactionRule('secret', '[REDACTED]'),
        RedactionRule('token', '[REDACTED]'),
        RedactionRule('password', '[REDACTED]'),
        RedactionRule('ssh_key', '[REDACTED]'),
        RedactionRule('private_key', '[REDACTED]'),
        RedactionRule('/home/', '[HOME]/'),
        RedactionRule('/Users/', '[HOME]/'),
        RedactionRule('/tmp/', '[TEMP]/'),
    ]

    def __init__(self, custom_rules: list[RedactionRule] | None = None) -> None:
        """Initialize redaction filter.

        Args:
            custom_rules: Additional redaction rules beyond defaults.
        """
        self.rules = self.DEFAULT_RULES + (custom_rules or [])

    def redact_string(self, text: str) -> str:
        """Apply redaction rules to a string.

        Args:
            text: Input text to redact.

        Returns:
            Redacted text.
        """
        result = text
        for rule in self.rules:
            if rule.is_regex:
                import re

                result = re.sub(
                    rule.pattern, rule.replacement, result, flags=re.IGNORECASE
                )
            else:
                result = result.replace(rule.pattern, rule.replacement)
        return result

    def redact_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """Recursively redact sensitive data from a dictionary.

        Args:
            data: Dictionary to redact.

        Returns:
            Redacted dictionary.
        """
        result: dict[str, Any] = {}
        for key, value in data.items():
            # Check if key matches sensitive patterns
            key_is_sensitive = any(
                rule.pattern.lower() in key.lower()
                for rule in self.rules
                if not rule.is_regex
            )

            if key_is_sensitive:
                # Completely redact values under sensitive keys
                result[key] = '[REDACTED]'
            elif isinstance(value, str):
                result[key] = self.redact_string(value)
            elif isinstance(value, dict):
                result[key] = self.redact_dict(value)
            elif isinstance(value, list):
                # Recursively redact list items, with special handling for sensitive data
                result[key] = [
                    self.redact_dict(item)
                    if isinstance(item, dict)
                    else self.redact_string(item)
                    if isinstance(item, str)
                    else item
                    for item in value
                ]
            else:
                result[key] = value
        return result

    def redact_audit_log(self, audit_log_path: Path) -> str:
        """Redact sensitive data from an audit log file.

        Args:
            audit_log_path: Path to audit log file.

        Returns:
            Redacted audit log content.
        """
        import json

        lines = audit_log_path.read_text(encoding='utf-8').strip().split('\n')
        redacted_lines = []

        for line in lines:
            try:
                event = json.loads(line)
                redacted_event = self.redact_dict(event)
                redacted_lines.append(json.dumps(redacted_event))
            except json.JSONDecodeError:
                # Keep non-JSON lines as-is but apply string redaction
                redacted_lines.append(self.redact_string(line))

        return '\n'.join(redacted_lines)


class TSBBuilder:
    """Builder for creating Provenanced Skill Bundles."""

    def __init__(
        self,
        skill_path: Path,
        audit_log_path: Path,
        author_key_path: Path | None = None,
        use_sigstore: bool = False,
        identity_token: str | None = None,
    ) -> None:
        """Initialize TSB builder.

        Args:
            skill_path: Path to skill directory.
            audit_log_path: Path to audit log file.
            author_key_path: Path to author's SSH/GPG key for signing.
            use_sigstore: Use Sigstore keyless signing instead of SSH key.
            identity_token: OIDC identity token for Sigstore signing.
        """
        self._skill_path = Path(skill_path).resolve()
        self._audit_log_path = Path(audit_log_path).resolve()
        self._author_key_path = Path(author_key_path) if author_key_path else None
        self._use_sigstore = use_sigstore
        self._identity_token = identity_token
        self._redaction_filter = RedactionFilter()

    def build_tsb(
        self,
        output_path: Path,
        metadata: TSBMetadata,
        skip_audit_verification: bool = False,
    ) -> TSBManifest:
        """Build a TSB file.

        Args:
            output_path: Path for output TSB file.
            metadata: TSB metadata.
            skip_audit_verification: Skip audit chain verification (for testing).

        Returns:
            TSB manifest.
        """
        # Create temporary directory for bundle
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)

            # Copy skill files
            skill_files = []
            for file_path in self._skill_path.rglob('*'):
                if file_path.is_file() and not file_path.name.startswith('.'):
                    rel_path = file_path.relative_to(self._skill_path)
                    dest_path = tmp_path / 'skill' / rel_path
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    dest_path.write_bytes(file_path.read_bytes())
                    skill_files.append(str(rel_path))

            # Redact and copy audit log
            redacted_audit = self._redaction_filter.redact_audit_log(
                self._audit_log_path
            )
            audit_path = tmp_path / 'audit.jsonl'
            audit_path.write_text(redacted_audit, encoding='utf-8')

            # Verify audit chain integrity
            if not skip_audit_verification:
                verification = verify_audit_chain(audit_path)
                if not verification.valid:
                    raise ValueError(
                        f'Audit chain verification failed: {verification.error}'
                    )

            # Calculate hashes
            audit_hash = hashlib.sha256(redacted_audit.encode()).hexdigest()

            # Create manifest
            manifest = TSBManifest(
                metadata=metadata,
                attestation=TSBAttestation(
                    author_signature='',  # Will be filled after signing
                    audit_chain_hash=audit_hash,
                    bundle_hash='',  # Will be filled after packaging
                ),
                files=skill_files,
            )

            # Calculate hash of skill files and audit only (excluding manifest)
            # Use sorted iteration for deterministic hash across platforms
            # Include relative paths in hash to prevent structural tampering (TSB v1.1)
            bundle_hash = hashlib.sha256()
            skill_files_sorted = sorted(
                (tmp_path / 'skill').rglob('*'), key=lambda p: str(p)
            )
            for file_path in skill_files_sorted:
                if file_path.is_file():
                    # Include relative path in hash to prevent file renaming attacks
                    rel_path = file_path.relative_to(tmp_path / 'skill')
                    bundle_hash.update(str(rel_path).encode('utf-8'))
                    bundle_hash.update(file_path.read_bytes())
            bundle_hash.update((tmp_path / 'audit.jsonl').read_bytes())
            bundle_hash_str = bundle_hash.hexdigest()

            # Create initial tarball with placeholder manifest (for signing)
            manifest_path = tmp_path / 'manifest.json'
            manifest_dict = self._manifest_to_dict(manifest)
            manifest_path.write_text(
                json.dumps(manifest_dict, indent=2), encoding='utf-8'
            )

            # Create temporary tarball for signing
            temp_tsb_path = tmp_path / 'temp.tsb'
            with tarfile.open(temp_tsb_path, 'w:gz') as tar:
                tar.add(tmp_path, arcname='')

            # Sign bundle if key provided or using Sigstore
            signature = ''
            certificate = ''
            signer_type = ''

            if self._use_sigstore and SIGSTORE_AVAILABLE:
                try:
                    sigstore_signer = SigstoreSigner(
                        identity_token=self._identity_token
                    )
                    sig_result = sigstore_signer.sign(temp_tsb_path)
                    signature = sig_result['signature']
                    certificate = sig_result['certificate']
                    signer_type = 'sigstore-keyless'
                except ValueError as exc:
                    raise ValueError(f'Sigstore signing failed: {exc}') from exc
            elif self._author_key_path and self._author_key_path.exists():
                signature = self._sign_bundle(temp_tsb_path, self._author_key_path)
                signer_type = 'ssh'

            # Update manifest with final hashes and signature
            manifest = TSBManifest(
                metadata=manifest.metadata,
                attestation=TSBAttestation(
                    author_signature=signature,
                    audit_chain_hash=audit_hash,
                    bundle_hash=bundle_hash_str,
                    signature_algorithm=manifest.attestation.signature_algorithm,
                    certificate=certificate,
                    signer=signer_type,
                ),
                files=manifest.files,
            )

            # Write final manifest
            manifest_dict = self._manifest_to_dict(manifest)
            manifest_path.write_text(
                json.dumps(manifest_dict, indent=2), encoding='utf-8'
            )

            # Create final tarball
            with tarfile.open(output_path, 'w:gz') as tar:
                tar.add(tmp_path, arcname='')

            return manifest

    def _sign_bundle(self, bundle_path: Path, key_path: Path) -> str:
        """Sign the bundle using SSH key.

        Args:
            bundle_path: Path to bundle file.
            key_path: Path to SSH private key.

        Returns:
            Base64-encoded signature.

        Raises:
            ValueError: If signing fails.
        """
        import base64
        import subprocess

        try:
            # Use ssh-keygen to sign
            result = subprocess.run(
                [
                    'ssh-keygen',
                    '-Y',
                    'sign',
                    '-f',
                    str(key_path),
                    '-n',
                    'teaagent-tsb',
                    str(bundle_path),
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            # Extract signature from output
            signature = result.stdout.strip()
            return base64.b64encode(signature.encode()).decode()
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            # Do NOT fall back to hash-based signature - this is security theater
            raise ValueError(
                f'Failed to sign bundle with ssh-keygen: {exc}. Please ensure ssh-keygen is installed and the key is valid.'
            ) from exc

    def _manifest_to_dict(self, manifest: TSBManifest) -> dict[str, Any]:
        """Convert manifest to dictionary."""
        return {
            'metadata': {
                'skill_name': manifest.metadata.skill_name,
                'skill_version': manifest.metadata.skill_version,
                'skill_author': manifest.metadata.skill_author,
                'created_at': manifest.metadata.created_at,
                'tsb_version': manifest.metadata.tsb_version,
                'environment_type': manifest.metadata.environment_type,
                'python_version': manifest.metadata.python_version,
            },
            'attestation': {
                'author_signature': manifest.attestation.author_signature,
                'audit_chain_hash': manifest.attestation.audit_chain_hash,
                'bundle_hash': manifest.attestation.bundle_hash,
                'signature_algorithm': manifest.attestation.signature_algorithm,
                'certificate': manifest.attestation.certificate,
                'signer': manifest.attestation.signer,
            },
            'files': manifest.files,
        }


class TSBVerifier:
    """Verifier for Provenanced Skill Bundles."""

    def __init__(self, tsb_path: Path, offline: bool = False) -> None:
        """Initialize TSB verifier.

        Args:
            tsb_path: Path to TSB file.
            offline: If True, skip Rekor/Fulcio online verification for air-gapped environments.
        """
        self._tsb_path = Path(tsb_path).resolve()
        self._offline = offline

    def verify(
        self,
        verify_signature: bool = True,
        skip_audit_verification: bool = False,
        allow_unsigned: bool = False,
        identity: str | None = None,
        issuer: str | None = None,
    ) -> tuple[bool, str]:
        """Verify TSB integrity and attestation.

        Args:
            verify_signature: Whether to verify cryptographic signature.
            skip_audit_verification: Skip audit chain verification (for testing).
            allow_unsigned: Allow unsigned bundles (unsafe for production).
            identity: Optional OIDC identity to enforce (e.g., email).
            issuer: Optional OIDC issuer to enforce (e.g., "https://accounts.google.com").

        Returns:
            Tuple of (is_valid, error_message).
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)

            # Extract tarball with path traversal protection
            try:
                with tarfile.open(self._tsb_path, 'r:gz') as tar:
                    # Use data_filter to prevent path traversal attacks (CVE-2007-4559, CVE-2025-4517)
                    # Python 3.12+ supports filter='data', fallback to members-only extraction for older versions
                    if hasattr(tarfile, 'data_filter'):
                        tar.extractall(tmp_path, filter='data')
                    else:
                        # Fallback: extract members individually with path validation
                        for member in tar.getmembers():
                            # Prevent absolute path and parent directory traversal
                            if member.name.startswith('/') or '..' in member.name.split(
                                '/'
                            ):
                                return (
                                    False,
                                    f'Path traversal attempt detected: {member.name}',
                                )
                            tar.extract(member, tmp_path)
            except (tarfile.TarError, OSError, ValueError) as exc:
                logger.warning('Failed to extract TSB: %s', exc)
                return False, f'Failed to extract TSB: {exc}'

            # Read manifest
            manifest_path = tmp_path / 'manifest.json'
            if not manifest_path.exists():
                return False, 'Manifest not found in TSB'

            try:
                manifest_data = json.loads(manifest_path.read_text(encoding='utf-8'))
            except json.JSONDecodeError as exc:
                return False, f'Invalid manifest JSON: {exc}'

            # Verify bundle hash (hash of skill files and audit only, excluding manifest)
            # Use sorted iteration for deterministic hash across platforms
            # Include relative paths in hash to prevent structural tampering (TSB v1.1)
            bundle_hash_obj = hashlib.sha256()
            skill_path = tmp_path / 'skill'
            if skill_path.exists():
                skill_files = sorted(skill_path.rglob('*'), key=lambda p: str(p))
                for file_path in skill_files:
                    if file_path.is_file():
                        # Include relative path in hash to prevent file renaming attacks
                        rel_path = str(file_path.relative_to(skill_path))
                        bundle_hash_obj.update(rel_path.encode('utf-8'))
                        bundle_hash_obj.update(file_path.read_bytes())
            audit_path = tmp_path / 'audit.jsonl'
            if audit_path.exists():
                bundle_hash_obj.update(audit_path.read_bytes())
            bundle_hash = bundle_hash_obj.hexdigest()

            if manifest_data['attestation']['bundle_hash'] != bundle_hash:
                return (
                    False,
                    f'Bundle hash mismatch: expected {manifest_data["attestation"]["bundle_hash"]}, got {bundle_hash}',
                )

            # Verify audit chain
            audit_path = tmp_path / 'audit.jsonl'
            if audit_path.exists() and not skip_audit_verification:
                verification = verify_audit_chain(audit_path)
                if not verification.valid:
                    return (
                        False,
                        f'Audit chain verification failed: {verification.error}',
                    )

                # Verify audit hash
                audit_hash = hashlib.sha256(audit_path.read_bytes()).hexdigest()
                if manifest_data['attestation']['audit_chain_hash'] != audit_hash:
                    return (
                        False,
                        f'Audit hash mismatch: expected {manifest_data["attestation"]["audit_chain_hash"]}, got {audit_hash}',
                    )

            # Verify signature if requested
            if verify_signature:
                # Require signature when verification is enabled, unless allow_unsigned is set
                if not manifest_data['attestation']['author_signature']:
                    if allow_unsigned:
                        # Allow unsigned bundles in development mode
                        return (
                            True,
                            'TSB verification successful (unsigned bundle allowed in development mode)',
                        )
                    else:
                        return (
                            False,
                            'Signature verification requested but bundle is unsigned. Use allow_unsigned=True for development (unsafe for production).',
                        )

                # Use TSBProvenanceVerifier for verification if available
                if SIGSTORE_AVAILABLE:
                    try:
                        verifier = TSBProvenanceVerifier(
                            require_signature=True,
                            identity=identity,  # Optional: enforce specific email
                            issuer=issuer,  # Optional: enforce specific OIDC issuer
                            offline=self._offline,  # Offline mode for air-gapped environments
                        )
                        is_valid, message = verifier.verify_provenance(
                            self._tsb_path, manifest_data
                        )
                        if not is_valid:
                            return False, f'Provenance verification failed: {message}'
                    except (ImportError, ValueError, TypeError, OSError) as exc:
                        logger.warning('Provenance verifier error: %s', exc)
                        return False, f'Provenance verifier error: {exc}'
                else:
                    # Fallback: sigstore not available, cannot verify signatures securely
                    # Fail closed for security - don't accept unverified signatures
                    return (
                        False,
                        'Signature verification requires sigstore-python. Install with: pip install sigstore',
                    )

            return True, 'TSB verification successful'

    def extract_skill(self, output_path: Path) -> None:
        """Extract skill files from TSB.

        Args:
            output_path: Path to extract skill to.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)

            # Extract tarball with path traversal protection (CVE-2007-4559, CVE-2025-4517)
            with tarfile.open(self._tsb_path, 'r:gz') as tar:
                # Use data_filter to prevent path traversal attacks
                # Python 3.12+ supports filter='data', fallback to members-only extraction for older versions
                if hasattr(tarfile, 'data_filter'):
                    tar.extractall(tmp_path, filter='data')
                else:
                    # Fallback: extract members individually with path validation
                    for member in tar.getmembers():
                        # Prevent absolute path and parent directory traversal
                        if member.name.startswith('/') or '..' in member.name.split(
                            '/'
                        ):
                            raise ValueError(
                                f'Path traversal attempt detected: {member.name}'
                            )
                        tar.extract(member, tmp_path)

            # Copy skill directory
            skill_src = tmp_path / 'skill'
            if skill_src.exists():
                import shutil

                shutil.copytree(skill_src, output_path)

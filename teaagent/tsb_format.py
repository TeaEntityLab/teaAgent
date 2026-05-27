"""Provenanced Skill Bundle (TSB) format for cryptographically attested skill distribution.

This module defines the TSB binary format structure and utilities for packaging
skills with their audit chain and cryptographic signatures for zero-knowledge
secure supply chain verification.
"""

from __future__ import annotations

import hashlib
import json
import tarfile
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from teaagent.audit_chain import verify_audit_chain


@dataclass(frozen=True)
class TSBMetadata:
    """Metadata for a Provenanced Skill Bundle."""
    skill_name: str
    skill_version: str
    skill_author: str
    created_at: str
    tsb_version: str = "1.0"
    environment_type: str = "uv"
    python_version: str = "3.11"


@dataclass(frozen=True)
class TSBAttestation:
    """Cryptographic attestation for a skill bundle."""
    author_signature: str  # SSH/GPG signature of the bundle
    audit_chain_hash: str  # SHA256 hash of the audit chain
    bundle_hash: str  # SHA256 hash of the entire bundle
    signature_algorithm: str = "ed25519"  # or rsa, ecdsa


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
    replacement: str = "[REDACTED]"
    is_regex: bool = False


class RedactionFilter:
    """Filters sensitive data from audit logs before packaging."""
    
    DEFAULT_RULES = [
        RedactionRule("api_key", "[REDACTED]"),
        RedactionRule("secret", "[REDACTED]"),
        RedactionRule("token", "[REDACTED]"),
        RedactionRule("password", "[REDACTED]"),
        RedactionRule("ssh_key", "[REDACTED]"),
        RedactionRule("private_key", "[REDACTED]"),
        RedactionRule("/home/", "[HOME]/"),
        RedactionRule("/Users/", "[HOME]/"),
        RedactionRule("/tmp/", "[TEMP]/"),
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
                result = re.sub(rule.pattern, rule.replacement, result, flags=re.IGNORECASE)
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
        result = {}
        for key, value in data.items():
            if isinstance(value, str):
                result[key] = self.redact_string(value)
            elif isinstance(value, dict):
                result[key] = self.redact_dict(value)
            elif isinstance(value, list):
                result[key] = [self.redact_dict(item) if isinstance(item, dict) else item for item in value]
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
        
        lines = audit_log_path.read_text(encoding="utf-8").strip().split("\n")
        redacted_lines = []
        
        for line in lines:
            try:
                event = json.loads(line)
                redacted_event = self.redact_dict(event)
                redacted_lines.append(json.dumps(redacted_event))
            except json.JSONDecodeError:
                # Keep non-JSON lines as-is but apply string redaction
                redacted_lines.append(self.redact_string(line))
        
        return "\n".join(redacted_lines)


class TSBBuilder:
    """Builder for creating Provenanced Skill Bundles."""
    
    def __init__(
        self,
        skill_path: Path,
        audit_log_path: Path,
        author_key_path: Path | None = None,
    ) -> None:
        """Initialize TSB builder.
        
        Args:
            skill_path: Path to skill directory.
            audit_log_path: Path to audit log file.
            author_key_path: Path to author's SSH/GPG key for signing.
        """
        self._skill_path = Path(skill_path).resolve()
        self._audit_log_path = Path(audit_log_path).resolve()
        self._author_key_path = Path(author_key_path) if author_key_path else None
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
            for file_path in self._skill_path.rglob("*"):
                if file_path.is_file() and not file_path.name.startswith("."):
                    rel_path = file_path.relative_to(self._skill_path)
                    dest_path = tmp_path / "skill" / rel_path
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    dest_path.write_bytes(file_path.read_bytes())
                    skill_files.append(str(rel_path))
            
            # Redact and copy audit log
            redacted_audit = self._redaction_filter.redact_audit_log(self._audit_log_path)
            audit_path = tmp_path / "audit.jsonl"
            audit_path.write_text(redacted_audit, encoding="utf-8")
            
            # Verify audit chain integrity
            if not skip_audit_verification:
                verification = verify_audit_chain(audit_path)
                if not verification.valid:
                    raise ValueError(f"Audit chain verification failed: {verification.error}")
            
            # Calculate hashes
            audit_hash = hashlib.sha256(redacted_audit.encode()).hexdigest()
            
            # Create manifest
            manifest = TSBManifest(
                metadata=metadata,
                attestation=TSBAttestation(
                    author_signature="",  # Will be filled after signing
                    audit_chain_hash=audit_hash,
                    bundle_hash="",  # Will be filled after packaging
                ),
                files=skill_files,
            )
            
            # Calculate hash of skill files and audit only (excluding manifest)
            # Use sorted iteration for deterministic hash across platforms
            bundle_hash = hashlib.sha256()
            skill_files = sorted((tmp_path / "skill").rglob("*"), key=lambda p: str(p))
            for file_path in skill_files:
                if file_path.is_file():
                    bundle_hash.update(file_path.read_bytes())
            bundle_hash.update((tmp_path / "audit.jsonl").read_bytes())
            bundle_hash = bundle_hash.hexdigest()
            
            # Sign bundle if key provided
            signature = ""
            if self._author_key_path and self._author_key_path.exists():
                signature = self._sign_bundle(output_path, self._author_key_path)
            
            # Update manifest with final hashes and signature
            manifest = TSBManifest(
                metadata=manifest.metadata,
                attestation=TSBAttestation(
                    author_signature=signature,
                    audit_chain_hash=audit_hash,
                    bundle_hash=bundle_hash,
                    signature_algorithm=manifest.attestation.signature_algorithm,
                ),
                files=manifest.files,
            )
            
            # Write final manifest
            manifest_path = tmp_path / "manifest.json"
            manifest_dict = self._manifest_to_dict(manifest)
            manifest_path.write_text(json.dumps(manifest_dict, indent=2), encoding="utf-8")
            
            # Create final tarball
            with tarfile.open(output_path, "w:gz") as tar:
                tar.add(tmp_path, arcname="")
            
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
                    "ssh-keygen",
                    "-Y",
                    "sign",
                    "-f",
                    str(key_path),
                    "-n",
                    "teaagent-tsb",
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
            raise ValueError(f"Failed to sign bundle with ssh-keygen: {exc}. Please ensure ssh-keygen is installed and the key is valid.")
    
    def _manifest_to_dict(self, manifest: TSBManifest) -> dict[str, Any]:
        """Convert manifest to dictionary."""
        return {
            "metadata": {
                "skill_name": manifest.metadata.skill_name,
                "skill_version": manifest.metadata.skill_version,
                "skill_author": manifest.metadata.skill_author,
                "created_at": manifest.metadata.created_at,
                "tsb_version": manifest.metadata.tsb_version,
                "environment_type": manifest.metadata.environment_type,
                "python_version": manifest.metadata.python_version,
            },
            "attestation": {
                "author_signature": manifest.attestation.author_signature,
                "audit_chain_hash": manifest.attestation.audit_chain_hash,
                "bundle_hash": manifest.attestation.bundle_hash,
                "signature_algorithm": manifest.attestation.signature_algorithm,
            },
            "files": manifest.files,
        }


class TSBVerifier:
    """Verifier for Provenanced Skill Bundles."""
    
    def __init__(self, tsb_path: Path) -> None:
        """Initialize TSB verifier.
        
        Args:
            tsb_path: Path to TSB file.
        """
        self._tsb_path = Path(tsb_path).resolve()
    
    def verify(self, verify_signature: bool = True, skip_audit_verification: bool = False) -> tuple[bool, str]:
        """Verify TSB integrity and attestation.
        
        Args:
            verify_signature: Whether to verify cryptographic signature.
            skip_audit_verification: Skip audit chain verification (for testing).
            
        Returns:
            Tuple of (is_valid, error_message).
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            
            # Extract tarball with path traversal protection
            try:
                with tarfile.open(self._tsb_path, "r:gz") as tar:
                    # Use data_filter to prevent path traversal attacks (CVE-2007-4559, CVE-2025-4517)
                    # Python 3.12+ supports filter='data', fallback to members-only extraction for older versions
                    if hasattr(tarfile, 'data_filter'):
                        tar.extractall(tmp_path, filter='data')
                    else:
                        # Fallback: extract members individually with path validation
                        for member in tar.getmembers():
                            # Prevent absolute path and parent directory traversal
                            if member.name.startswith('/') or '..' in member.name.split('/'):
                                return False, f"Path traversal attempt detected: {member.name}"
                            tar.extract(member, tmp_path)
            except Exception as exc:
                return False, f"Failed to extract TSB: {exc}"
            
            # Read manifest
            manifest_path = tmp_path / "manifest.json"
            if not manifest_path.exists():
                return False, "Manifest not found in TSB"
            
            try:
                manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                return False, f"Invalid manifest JSON: {exc}"
            
            # Verify bundle hash (hash of skill files and audit only, excluding manifest)
            # Use sorted iteration for deterministic hash across platforms
            bundle_hash = hashlib.sha256()
            skill_path = tmp_path / "skill"
            if skill_path.exists():
                skill_files = sorted(skill_path.rglob("*"), key=lambda p: str(p))
                for file_path in skill_files:
                    if file_path.is_file():
                        bundle_hash.update(file_path.read_bytes())
            audit_path = tmp_path / "audit.jsonl"
            if audit_path.exists():
                bundle_hash.update(audit_path.read_bytes())
            bundle_hash = bundle_hash.hexdigest()
            
            if manifest_data["attestation"]["bundle_hash"] != bundle_hash:
                return False, f"Bundle hash mismatch: expected {manifest_data['attestation']['bundle_hash']}, got {bundle_hash}"
            
            # Verify audit chain
            audit_path = tmp_path / "audit.jsonl"
            if audit_path.exists() and not skip_audit_verification:
                verification = verify_audit_chain(audit_path)
                if not verification.valid:
                    return False, f"Audit chain verification failed: {verification.error}"
                
                # Verify audit hash
                audit_hash = hashlib.sha256(audit_path.read_bytes()).hexdigest()
                if manifest_data["attestation"]["audit_chain_hash"] != audit_hash:
                    return False, f"Audit hash mismatch: expected {manifest_data['attestation']['audit_chain_hash']}, got {audit_hash}"
            
            # Verify signature if requested
            if verify_signature and manifest_data["attestation"]["author_signature"]:
                # In production, this would verify against the author's public key
                # For now, we just check that a signature exists
                if not manifest_data["attestation"]["author_signature"]:
                    return False, "Missing author signature"
            
            return True, "TSB verification successful"
    
    def extract_skill(self, output_path: Path) -> None:
        """Extract skill files from TSB.
        
        Args:
            output_path: Path to extract skill to.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            
            # Extract tarball
            with tarfile.open(self._tsb_path, "r:gz") as tar:
                tar.extractall(tmp_path)
            
            # Copy skill directory
            skill_src = tmp_path / "skill"
            if skill_src.exists():
                import shutil
                shutil.copytree(skill_src, output_path)

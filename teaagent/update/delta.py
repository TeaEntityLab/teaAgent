"""Delta update mechanism for efficient updates (TASK-H6-003-02).

experimental — unwired

This module provides delta generation, application, and verification for
efficient binary updates without downloading full packages.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class DeltaType(str, Enum):
    """Type of delta update."""

    BINARY = 'binary'  # Binary diff (bsdiff)
    FILE = 'file'  # File-level delta
    BLOCK = 'block'  # Block-level delta


@dataclass
class DeltaMetadata:
    """Metadata for a delta update."""

    from_version: str
    to_version: str
    delta_type: DeltaType
    size_bytes: int = 0
    checksum: str = ''
    created_at: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            'from_version': self.from_version,
            'to_version': self.to_version,
            'delta_type': self.delta_type.value,
            'size_bytes': self.size_bytes,
            'checksum': self.checksum,
            'created_at': self.created_at,
            'metadata': self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'DeltaMetadata':
        """Create from dictionary."""
        return cls(
            from_version=data['from_version'],
            to_version=data['to_version'],
            delta_type=DeltaType(data['delta_type']),
            size_bytes=data.get('size_bytes', 0),
            checksum=data.get('checksum', ''),
            created_at=data.get('created_at'),
            metadata=data.get('metadata', {}),
        )


@dataclass
class Delta:
    """A delta update between two versions."""

    metadata: DeltaMetadata
    delta_data: bytes = b''
    verification_hash: str = ''

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            'metadata': self.metadata.to_dict(),
            'delta_data': self.delta_data.hex()
            if isinstance(self.delta_data, bytes)
            else self.delta_data,
            'verification_hash': self.verification_hash,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'Delta':
        """Create from dictionary."""
        return cls(
            metadata=DeltaMetadata.from_dict(data['metadata']),
            delta_data=bytes.fromhex(data['delta_data'])
            if isinstance(data['delta_data'], str)
            else data['delta_data'],
            verification_hash=data.get('verification_hash', ''),
        )


class DeltaGenerator:
    """Generator for delta updates."""

    def __init__(self) -> None:
        """Initialize the delta generator."""
        pass

    def generate_file_delta(
        self,
        old_files: dict[str, bytes],
        new_files: dict[str, bytes],
    ) -> Delta:
        """Generate a file-level delta.

        Args:
            old_files: Dictionary of old file paths to contents.
            new_files: Dictionary of new file paths to contents.

        Returns:
            Delta object.
        """
        # Calculate delta (simple implementation: only changed files)
        changed_files = {}
        for path, new_content in new_files.items():
            if path not in old_files or old_files[path] != new_content:
                # Encode bytes as hex for JSON serialization
                changed_files[path] = new_content.hex()

        # Serialize delta
        delta_data = json.dumps(changed_files).encode('utf-8')

        # Calculate checksum
        checksum = hashlib.sha256(delta_data).hexdigest()

        # Create metadata
        from_version = '0.1.0'  # Would be passed in production
        to_version = '0.2.0'  # Would be passed in production
        metadata = DeltaMetadata(
            from_version=from_version,
            to_version=to_version,
            delta_type=DeltaType.FILE,
            size_bytes=len(delta_data),
            checksum=checksum,
        )

        return Delta(
            metadata=metadata,
            delta_data=delta_data,
            verification_hash=checksum,
        )

    def generate_binary_delta(
        self,
        old_binary: bytes,
        new_binary: bytes,
    ) -> Delta:
        """Generate a binary delta (placeholder for bsdiff).

        Args:
            old_binary: Old binary data.
            new_binary: New binary data.

        Returns:
            Delta object.
        """
        # Placeholder: simple diff (in production, use bsdiff)
        # For now, just return the full new binary as the delta
        delta_data = new_binary

        # Calculate checksum
        checksum = hashlib.sha256(delta_data).hexdigest()

        # Create metadata
        from_version = '0.1.0'
        to_version = '0.2.0'
        metadata = DeltaMetadata(
            from_version=from_version,
            to_version=to_version,
            delta_type=DeltaType.BINARY,
            size_bytes=len(delta_data),
            checksum=checksum,
        )

        return Delta(
            metadata=metadata,
            delta_data=delta_data,
            verification_hash=checksum,
        )

    def calculate_delta_size(
        self,
        old_files: dict[str, bytes],
        new_files: dict[str, bytes],
    ) -> int:
        """Calculate the size of a file delta.

        Args:
            old_files: Dictionary of old file paths to contents.
            new_files: Dictionary of new file paths to contents.

        Returns:
            Size in bytes.
        """
        changed_files = {}
        for path, new_content in new_files.items():
            if path not in old_files or old_files[path] != new_content:
                # Encode bytes as hex for JSON serialization
                changed_files[path] = new_content.hex()

        delta_data = json.dumps(changed_files).encode('utf-8')
        return len(delta_data)


class DeltaApplier:
    """Applier for delta updates."""

    def __init__(self) -> None:
        """Initialize the delta applier."""
        pass

    def apply_file_delta(
        self,
        current_files: dict[str, bytes],
        delta: Delta,
    ) -> dict[str, bytes]:
        """Apply a file-level delta.

        Args:
            current_files: Current file dictionary.
            delta: Delta to apply.

        Returns:
            Updated file dictionary.
        """
        if delta.metadata.delta_type != DeltaType.FILE:
            raise ValueError(f'Expected file delta, got {delta.metadata.delta_type}')

        # Deserialize delta data
        changed_files = json.loads(delta.delta_data.decode('utf-8'))

        # Apply changes (decode hex back to bytes)
        updated_files = current_files.copy()
        for path, content_hex in changed_files.items():
            updated_files[path] = bytes.fromhex(content_hex)

        return updated_files

    def apply_binary_delta(
        self,
        current_binary: bytes,
        delta: Delta,
    ) -> bytes:
        """Apply a binary delta (placeholder for bspatch).

        Args:
            current_binary: Current binary data.
            delta: Delta to apply.

        Returns:
            Updated binary data.
        """
        if delta.metadata.delta_type != DeltaType.BINARY:
            raise ValueError(f'Expected binary delta, got {delta.metadata.delta_type}')

        # Placeholder: just return the delta data (in production, use bspatch)
        return delta.delta_data

    def verify_delta_checksum(self, delta: Delta) -> bool:
        """Verify delta checksum.

        Args:
            delta: Delta to verify.

        Returns:
            True if checksum matches, False otherwise.
        """
        calculated_checksum = hashlib.sha256(delta.delta_data).hexdigest()
        return calculated_checksum == delta.metadata.checksum

    def verify_delta_integrity(
        self,
        delta: Delta,
        expected_hash: str,
    ) -> bool:
        """Verify delta integrity against expected hash.

        Args:
            delta: Delta to verify.
            expected_hash: Expected verification hash.

        Returns:
            True if hashes match, False otherwise.
        """
        return delta.verification_hash == expected_hash


class DeltaManager:
    """Manager for delta update operations."""

    def __init__(self) -> None:
        """Initialize the delta manager."""
        self.generator = DeltaGenerator()
        self.applier = DeltaApplier()

    def create_delta(
        self,
        old_version: str,
        new_version: str,
        old_files: dict[str, bytes],
        new_files: dict[str, bytes],
        delta_type: DeltaType = DeltaType.FILE,
    ) -> Delta:
        """Create a delta between versions.

        Args:
            old_version: Old version string.
            new_version: New version string.
            old_files: Old file dictionary.
            new_files: New file dictionary.
            delta_type: Type of delta to generate.

        Returns:
            Delta object.
        """
        if delta_type == DeltaType.FILE:
            delta = self.generator.generate_file_delta(old_files, new_files)
        elif delta_type == DeltaType.BINARY:
            # Combine all files into single binary for binary delta
            old_binary = self._combine_files(old_files)
            new_binary = self._combine_files(new_files)
            delta = self.generator.generate_binary_delta(old_binary, new_binary)
        else:
            raise ValueError(f'Unsupported delta type: {delta_type}')

        # Update metadata
        delta.metadata.from_version = old_version
        delta.metadata.to_version = new_version

        return delta

    def _combine_files(self, files: dict[str, bytes]) -> bytes:
        """Combine files into single binary.

        Args:
            files: Dictionary of file paths to contents.

        Returns:
            Combined binary data.
        """
        # Simple concatenation with file headers
        combined = b''
        for path, content in sorted(files.items()):
            header = f'FILE:{path}\n'.encode('utf-8')
            combined += header + content
        return combined

    def apply_delta(
        self,
        current_files: dict[str, bytes],
        delta: Delta,
    ) -> dict[str, bytes]:
        """Apply a delta to current files.

        Args:
            current_files: Current file dictionary.
            delta: Delta to apply.

        Returns:
            Updated file dictionary.
        """
        # Verify delta before applying
        if not self.applier.verify_delta_checksum(delta):
            raise ValueError('Delta checksum verification failed')

        # Apply delta
        if delta.metadata.delta_type == DeltaType.FILE:
            return self.applier.apply_file_delta(current_files, delta)
        elif delta.metadata.delta_type == DeltaType.BINARY:
            # Binary delta - not applicable to file dictionary
            raise ValueError('Binary delta cannot be applied to file dictionary')
        else:
            raise ValueError(f'Unsupported delta type: {delta.metadata.delta_type}')

    def calculate_savings(
        self,
        old_files: dict[str, bytes],
        new_files: dict[str, bytes],
        delta_type: DeltaType = DeltaType.FILE,
    ) -> dict[str, Any]:
        """Calculate space savings from using delta.

        Args:
            old_files: Old file dictionary.
            new_files: New file dictionary.
            delta_type: Type of delta.

        Returns:
            Dictionary with savings information.
        """
        old_size = sum(len(content) for content in old_files.values())
        new_size = sum(len(content) for content in new_files.values())
        delta_size = self.generator.calculate_delta_size(old_files, new_files)

        savings = old_size - delta_size
        savings_percentage = (savings / old_size * 100) if old_size > 0 else 0.0

        return {
            'old_size_bytes': old_size,
            'new_size_bytes': new_size,
            'delta_size_bytes': delta_size,
            'savings_bytes': savings,
            'savings_percentage': savings_percentage,
        }

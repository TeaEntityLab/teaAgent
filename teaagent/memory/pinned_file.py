"""Pinned file data model and storage for live context synchronization.

This module provides:
- PinnedFile dataclass for structuring pinned file information
- Storage operations for pinned files in .teaagent/memory/pinned.json
- File existence validation before pinning
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class PinnedFile:
    """A pinned file for live context synchronization.
    
    Attributes:
        file_path: Path to the pinned file (relative to workspace root)
        pinned_at: When the file was pinned (Unix timestamp)
        last_modified: When the file was last modified (Unix timestamp)
    """
    file_path: str
    pinned_at: float
    last_modified: float
    
    @classmethod
    def create(cls, file_path: str) -> "PinnedFile":
        """Create a new pinned file entry.
        
        Args:
            file_path: Path to the file to pin (relative to workspace root)
            
        Returns:
            A new PinnedFile instance
        """
        return cls(
            file_path=file_path,
            pinned_at=datetime.now().timestamp(),
            last_modified=datetime.now().timestamp(),
        )
    
    def update_last_modified(self) -> None:
        """Update the last modified timestamp to current time."""
        self.last_modified = datetime.now().timestamp()
    
    def to_dict(self) -> dict:
        """Convert pinned file to dictionary for JSON serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "PinnedFile":
        """Create pinned file from dictionary.
        
        Args:
            data: Dictionary containing pinned file data
            
        Returns:
            A PinnedFile instance
        """
        return cls(**data)


class PinnedFileStorage:
    """Storage for pinned files in .teaagent/memory/pinned.json."""
    
    def __init__(self, root: Path) -> None:
        """Initialize pinned file storage.
        
        Args:
            root: The workspace root directory
        """
        self.root = Path(root).resolve()
        self.tea_dir = self.root / ".teaagent"
        self.memory_dir = self.tea_dir / "memory"
        self.storage_file = self.memory_dir / "pinned.json"
        
        # Ensure directories exist
        self.memory_dir.mkdir(parents=True, exist_ok=True)
    
    def _read_pinned_files(self) -> list[dict]:
        """Read pinned files from storage.
        
        Returns:
            List of pinned file dictionaries. Returns empty list if file
            doesn't exist or is corrupted.
        """
        if not self.storage_file.exists():
            return []
        
        try:
            with open(self.storage_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, list):
                    return []
                return data
        except (OSError, json.JSONDecodeError) as exc:
            # Log warning but don't crash
            import sys
            print(f"[TeaAgent] Warning: Failed to read pinned files: {exc}", file=sys.stderr)
            return []
    
    def _write_pinned_files(self, pinned_files: list[dict]) -> None:
        """Write pinned files to storage.
        
        Args:
            pinned_files: List of pinned file dictionaries to write
        """
        try:
            with open(self.storage_file, "w", encoding="utf-8") as f:
                json.dump(pinned_files, f, indent=2)
        except OSError as exc:
            import sys
            print(f"[TeaAgent] Warning: Failed to write pinned files: {exc}", file=sys.stderr)
    
    def add(self, file_path: str) -> bool:
        """Add a file to the pinned list.
        
        Args:
            file_path: Path to the file to pin (relative to workspace root)
            
        Returns:
            True if file was added, False if file doesn't exist or already pinned
        """
        # Validate file exists
        full_path = self.root / file_path
        if not full_path.exists():
            return False
        
        # Check if already pinned
        pinned_files = self._read_pinned_files()
        for pf in pinned_files:
            if pf.get("file_path") == file_path:
                return False
        
        # Add new pinned file
        pinned_file = PinnedFile.create(file_path)
        pinned_files.append(pinned_file.to_dict())
        self._write_pinned_files(pinned_files)
        return True
    
    def remove(self, file_path: str) -> bool:
        """Remove a file from the pinned list.
        
        Args:
            file_path: Path to the file to unpin (relative to workspace root)
            
        Returns:
            True if file was removed, False if file was not pinned
        """
        pinned_files = self._read_pinned_files()
        original_count = len(pinned_files)
        pinned_files = [pf for pf in pinned_files if pf.get("file_path") != file_path]
        
        if len(pinned_files) < original_count:
            self._write_pinned_files(pinned_files)
            return True
        return False
    
    def list_all(self) -> list[PinnedFile]:
        """List all pinned files.
        
        Returns:
            List of all PinnedFile instances
        """
        pinned_files_data = self._read_pinned_files()
        return [PinnedFile.from_dict(data) for data in pinned_files_data]
    
    def clear_all(self) -> None:
        """Clear all pinned files from storage."""
        self._write_pinned_files([])
    
    def update_last_modified(self, file_path: str) -> bool:
        """Update the last modified timestamp for a pinned file.
        
        Args:
            file_path: Path to the file to update (relative to workspace root)
            
        Returns:
            True if file was found and updated, False otherwise
        """
        pinned_files = self._read_pinned_files()
        updated = False
        
        for pf in pinned_files:
            if pf.get("file_path") == file_path:
                pf["last_modified"] = datetime.now().timestamp()
                updated = True
                break
        
        if updated:
            self._write_pinned_files(pinned_files)
        
        return updated
    
    def is_pinned(self, file_path: str) -> bool:
        """Check if a file is pinned.
        
        Args:
            file_path: Path to check (relative to workspace root)
            
        Returns:
            True if file is pinned, False otherwise
        """
        pinned_files = self._read_pinned_files()
        for pf in pinned_files:
            if pf.get("file_path") == file_path:
                return True
        return False

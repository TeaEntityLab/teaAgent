"""In-memory virtual filesystem sandbox."""

from __future__ import annotations

from pathlib import Path


class VFSSandbox:
    """In-memory virtual file system overlay for zero-pollution parallel experiments.

    Intercepts file writes and stores them in memory until explicitly flushed.
    Reads fall through to the actual filesystem for files not in memory.
    """

    def __init__(self, root: str | Path):
        """Initialize VFS sandbox.

        Args:
            root: Repository root path.
        """
        self._root = Path(root).resolve()
        self._memory_files: dict[str, str] = {}
        self._deleted_files: set[str] = set()

    def write_file(self, path: str, content: str) -> None:
        """Write file to memory overlay.

        Args:
            path: Relative path from root.
            content: File content.
        """
        self._memory_files[path] = content
        self._deleted_files.discard(path)

    def read_file(self, path: str) -> str:
        """Read file from memory overlay or filesystem.

        Args:
            path: Relative path from root.

        Returns:
            File content.
        """
        if path in self._memory_files:
            return self._memory_files[path]
        if path in self._deleted_files:
            raise FileNotFoundError(f'File deleted in VFS: {path}')

        full_path = self._root / path
        if full_path.exists():
            return full_path.read_text(encoding='utf-8')
        raise FileNotFoundError(f'File not found: {path}')

    def delete_file(self, path: str) -> None:
        """Mark file as deleted in memory overlay.

        Args:
            path: Relative path from root.
        """
        self._memory_files.pop(path, None)
        self._deleted_files.add(path)

    def file_exists(self, path: str) -> bool:
        """Check if file exists in memory overlay or filesystem.

        Args:
            path: Relative path from root.

        Returns:
            True if file exists.
        """
        if path in self._memory_files:
            return True
        if path in self._deleted_files:
            return False
        return (self._root / path).exists()

    def list_files(self) -> list[str]:
        """List all files in memory overlay.

        Returns:
            List of file paths.
        """
        return list(self._memory_files.keys())

    def flush_to_disk(self) -> dict[str, bool]:
        """Flush all memory files to disk.

        Returns:
            Dict mapping file paths to flush success status.
        """
        results: dict[str, bool] = {}

        for path, content in self._memory_files.items():
            try:
                full_path = self._root / path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(content, encoding='utf-8')
                results[path] = True
            except OSError:
                results[path] = False

        # Delete files marked for deletion
        for path in self._deleted_files:
            try:
                full_path = self._root / path
                if full_path.exists():
                    full_path.unlink()
                results[path] = True
            except OSError:
                results[path] = False

        return results

    def clear(self) -> None:
        """Clear all memory files and deletions."""
        self._memory_files.clear()
        self._deleted_files.clear()

    def get_memory_size(self) -> int:
        """Get total size of memory files in bytes.

        Returns:
            Size in bytes.
        """
        return sum(len(content) for content in self._memory_files.values())

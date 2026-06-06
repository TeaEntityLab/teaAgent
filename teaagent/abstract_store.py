from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Generic, TypeVar

T = TypeVar('T')


class AbstractStore(ABC, Generic[T]):
    """Generic interface for storage backends.

    Enables database-backed deployments and makes storage pluggable.
    Concrete stores like RunStore, MemoryCatalog, and ApprovalPresetStore
    implement this interface.

    Type parameter ``T`` types the stored values (e.g. ``MemoryEntry``,
    ``list[dict[str, Any]]``).
    """

    @abstractmethod
    def save(self, key: str, value: T) -> None:
        """Store a value by key."""
        ...

    @abstractmethod
    def load(self, key: str) -> T | None:
        """Load a value by key. Returns None if not found."""
        ...

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete a value by key. Returns True if deleted, False if not found."""
        ...

    @abstractmethod
    def list_keys(self) -> list[str]:
        """List all keys in the store."""
        ...

    def exists(self, key: str) -> bool:
        """Check if a key exists in the store."""
        return self.load(key) is not None

    @abstractmethod
    def clear(self) -> None:
        """Remove all entries from the store."""
        ...


class JsonlStoreBackend(AbstractStore[T]):
    """Reference JSONL-file storage backend.

    One JSON object per line, append-friendly semantics.
    Each stored value is serialised as a single JSON object with an
    additional ``_key`` field so the backend can reconstitute the map.

    Intended as the default on-disk backend and as a reference for
    pluggable alternative backends (SQLite, PostgreSQL, etc.).
    """

    def __init__(
        self,
        path: str | Path,
        *,
        readonly: bool = False,
        key_field: str = 'key',
    ) -> None:
        self.path = Path(path).resolve()
        self.readonly = readonly
        self._key_field = key_field
        if not readonly:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def save(self, key: str, value: T) -> None:
        if self.readonly:
            raise RuntimeError('Cannot save in readonly mode')
        entries = self._read_all()
        entries[key] = value
        self._write_all(entries)

    def load(self, key: str) -> T | None:
        return self._read_all().get(key)

    def delete(self, key: str) -> bool:
        if self.readonly:
            raise RuntimeError('Cannot delete in readonly mode')
        entries = self._read_all()
        if key not in entries:
            return False
        del entries[key]
        self._write_all(entries)
        return True

    def list_keys(self) -> list[str]:
        return list(self._read_all().keys())

    def exists(self, key: str) -> bool:
        return key in self._read_all()

    def clear(self) -> None:
        if self.readonly:
            raise RuntimeError('Cannot clear in readonly mode')
        self._write_all({})

    def _read_all(self) -> dict[str, T]:
        if not self.path.exists():
            return {}
        result: dict[str, T] = {}
        for line in self.path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            key = data.get(self._key_field)
            if key is not None and isinstance(key, str):
                result[key] = data  # type: ignore[assignment]
        return result

    def _write_all(self, entries: dict[str, T]) -> None:
        lines: list[str] = [
            json.dumps(value, sort_keys=True)  # type: ignore[arg-type]
            for value in entries.values()
        ]
        self.path.write_text('\n'.join(lines) + '\n', encoding='utf-8')

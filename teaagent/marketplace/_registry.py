"""Local marketplace registry for skill publishing and discovery."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4


@dataclass(frozen=True)
class MarketplaceEntry:
    entry_id: str
    name: str
    description: str
    version: str
    author: str
    skill_path: str
    published_at: str
    updated_at: str
    tags: tuple[str, ...] = ()
    source: str = 'local'

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MarketplaceRegistry:
    """Local registry of published skill entries."""

    def __init__(self, root: str | Path = '.') -> None:
        self._root = Path(root).resolve()
        self._dir = self._root / '.teaagent' / 'marketplace'
        self._dir.mkdir(parents=True, exist_ok=True)

    def _manifest(self) -> Path:
        return self._dir / 'registry.json'

    def _read(self) -> list[MarketplaceEntry]:
        p = self._manifest()
        if not p.exists():
            return []
        data = json.loads(p.read_text(encoding='utf-8'))
        return [MarketplaceEntry(**e) for e in data] if isinstance(data, list) else []

    def _write(self, entries: list[MarketplaceEntry]) -> None:
        self._manifest().write_text(
            json.dumps([e.to_dict() for e in entries], indent=2),
            encoding='utf-8',
        )

    def publish(
        self,
        name: str,
        description: str,
        *,
        version: str = '0.1.0',
        author: str = '',
        skill_path: str = '',
        tags: Optional[list[str]] = None,
    ) -> MarketplaceEntry:
        now = datetime.now(timezone.utc).isoformat()
        entry = MarketplaceEntry(
            entry_id=str(uuid4()),
            name=name,
            description=description,
            version=version,
            author=author,
            skill_path=skill_path,
            published_at=now,
            updated_at=now,
            tags=tuple(tags or []),
        )
        entries = self._read()
        entries.insert(0, entry)
        self._write(entries)
        return entry

    def search(
        self,
        query: str = '',
        *,
        tag: Optional[str] = None,
        limit: int = 20,
    ) -> list[MarketplaceEntry]:
        entries = self._read()
        if query:
            q = query.lower()
            entries = [e for e in entries if q in e.name.lower() or q in e.description.lower()]
        if tag:
            entries = [e for e in entries if tag in e.tags]
        return entries[:limit]

    def list(self, *, limit: int = 50) -> list[MarketplaceEntry]:
        return self._read()[:limit]

    def remove(self, entry_id: str) -> bool:
        entries = [e for e in self._read() if e.entry_id != entry_id]
        before = len(entries)
        self._write(entries)
        return len(self._read()) < before

    def get(self, name: str) -> Optional[MarketplaceEntry]:
        for e in self._read():
            if e.name == name:
                return e
        return None

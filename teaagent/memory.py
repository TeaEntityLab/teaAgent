from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List
from uuid import uuid4

from teaagent.audit import utc_now


@dataclass(frozen=True)
class MemoryEntry:
    memory_id: str
    content: str
    tags: tuple[str, ...] = field(default_factory=tuple)
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "content": self.content,
            "tags": list(self.tags),
            "created_at": self.created_at,
        }


class MemoryCatalog:
    def __init__(self, root: str | Path = ".") -> None:
        self.root = Path(root).resolve()
        self.path = self.root / ".teaagent" / "memory.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def add(self, content: str, *, tags: tuple[str, ...] = ()) -> MemoryEntry:
        entry = MemoryEntry(memory_id=uuid4().hex, content=content.strip(), tags=normalize_tags(tags))
        if not entry.content:
            raise ValueError("memory content cannot be empty")
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry.to_dict(), sort_keys=True) + "\n")
        return entry

    def list(self, *, limit: int = 20) -> List[MemoryEntry]:
        entries = self._read_entries()
        return list(reversed(entries))[:limit]

    def search(self, query: str, *, limit: int = 10) -> List[MemoryEntry]:
        normalized = query.strip().lower()
        if not normalized:
            return []
        matches = [entry for entry in reversed(self._read_entries()) if memory_matches(entry, normalized)]
        return matches[:limit]

    def show(self, memory_id: str) -> MemoryEntry:
        safe_id = memory_id.strip()
        for entry in self._read_entries():
            if entry.memory_id == safe_id:
                return entry
        raise FileNotFoundError(f"memory '{memory_id}' not found")

    def _read_entries(self) -> List[MemoryEntry]:
        if not self.path.exists():
            return []
        entries: List[MemoryEntry] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            entries.append(
                MemoryEntry(
                    memory_id=payload["memory_id"],
                    content=payload["content"],
                    tags=tuple(payload.get("tags", [])),
                    created_at=payload.get("created_at", utc_now()),
                )
            )
        return entries


def normalize_tags(tags: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted({tag.strip().lower() for tag in tags if tag.strip()}))


def memory_matches(entry: MemoryEntry, query: str) -> bool:
    haystack = " ".join((entry.content.lower(), " ".join(entry.tags).lower()))
    return all(token in haystack for token in query.split())


def memory_entries_to_prompt(entries: list[MemoryEntry]) -> list[dict[str, Any]]:
    return [entry.to_dict() for entry in entries]

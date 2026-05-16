from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List
from uuid import uuid4

from teaagent.audit import utc_now
from teaagent.storage import append_jsonl_line


@dataclass(frozen=True)
class MemoryEntry:
    """A single tagged memory entry stored by the agent."""

    memory_id: str
    content: str
    tags: tuple[str, ...] = field(default_factory=tuple)
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            'memory_id': self.memory_id,
            'content': self.content,
            'tags': list(self.tags),
            'created_at': self.created_at,
        }


class MemoryCatalog:
    def __init__(self, root: str | Path = '.') -> None:
        self.root = Path(root).resolve()
        self.path = self.root / '.teaagent' / 'memory.jsonl'
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def add(self, content: str, *, tags: tuple[str, ...] = ()) -> MemoryEntry:
        entry = MemoryEntry(
            memory_id=uuid4().hex, content=content.strip(), tags=normalize_tags(tags)
        )
        if not entry.content:
            raise ValueError('memory content cannot be empty')
        append_jsonl_line(self.path, json.dumps(entry.to_dict(), sort_keys=True))
        return entry

    def list(self, *, limit: int = 20) -> List[MemoryEntry]:
        entries = self._read_entries()
        return list(reversed(entries))[:limit]

    def search(self, query: str, *, limit: int = 10) -> List[MemoryEntry]:
        normalized = query.strip().lower()
        if not normalized:
            return []
        tokens = tuple(token for token in normalized.split() if token)
        matches = [
            entry for entry in self._read_entries() if memory_matches(entry, normalized)
        ]
        ranked = sorted(
            matches,
            key=lambda entry: (
                memory_relevance_score(entry, tokens),
                entry.created_at,
            ),
            reverse=True,
        )
        return ranked[:limit]

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
        for line in self.path.read_text(encoding='utf-8').splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            entry = memory_entry_from_payload(payload)
            if entry is not None:
                entries.append(entry)
        return entries


def memory_entry_from_payload(payload: Any) -> MemoryEntry | None:
    if not isinstance(payload, dict):
        return None
    memory_id = payload.get('memory_id')
    content = payload.get('content')
    tags = payload.get('tags', [])
    created_at = payload.get('created_at', utc_now())
    if not isinstance(memory_id, str) or not memory_id:
        return None
    if not isinstance(content, str) or not content:
        return None
    if not isinstance(created_at, str) or not created_at:
        return None
    if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
        return None
    return MemoryEntry(
        memory_id=memory_id, content=content, tags=tuple(tags), created_at=created_at
    )


def normalize_tags(tags: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted({tag.strip().lower() for tag in tags if tag.strip()}))


def memory_matches(entry: MemoryEntry, query: str) -> bool:
    haystack = ' '.join((entry.content.lower(), ' '.join(entry.tags).lower()))
    return all(token in haystack for token in query.split())


def memory_relevance_score(entry: MemoryEntry, tokens: tuple[str, ...]) -> int:
    content = entry.content.lower()
    tags = tuple(tag.lower() for tag in entry.tags)
    score = 0
    for token in tokens:
        if token in content:
            score += 3
        if any(token in tag for tag in tags):
            score += 2
    if 'auto-curated' in tags:
        score += 4
    if 'run-summary' in tags:
        score += 2
    return score


def memory_entries_to_prompt(entries: list[MemoryEntry]) -> list[dict[str, Any]]:
    return [entry.to_dict() for entry in entries]

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List
from uuid import uuid4

from teaagent.audit import utc_now
from teaagent.storage import append_jsonl_line


def _create_memory_hierarchy(root: str | Path) -> 'MemoryHierarchy':
    """Factory function to create memory hierarchy."""
    return MemoryHierarchy(root)


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


# --- Three-Tier Memory Hierarchy (Claude Code compatible) ---


class MemoryHierarchy:
    """Three-tier memory system: Project / Personal / Auto-Memory.

    Matches Claude Code's memory hierarchy:
    - Project: `.teaagent/memory.jsonl` (team-shared, git-tracked)
    - Personal: `~/.config/teaagent/memory.jsonl` (user-specific, not git-tracked)
    - Auto-Memory: `.claude/MEMORY.md` (persistent, not git-tracked)
    """

    def __init__(self, root: str | Path = '.') -> None:
        self.root = Path(root).resolve()
        self._project_catalog: MemoryCatalog | None = None
        self._personal_catalog: MemoryCatalog | None = None

    @property
    def project(self) -> MemoryCatalog:
        """Project-level memory (git-tracked)."""
        if self._project_catalog is None:
            self._project_catalog = MemoryCatalog(self.root)
        return self._project_catalog

    @property
    def personal(self) -> MemoryCatalog:
        """Personal-level memory (user-wide, not git-tracked)."""
        if self._personal_catalog is None:
            personal_path = Path.home() / '.config' / 'teaagent'
            personal_path.mkdir(parents=True, exist_ok=True)
            self._personal_catalog = MemoryCatalog(personal_path)
        return self._personal_catalog

    def auto_memory_path(self) -> Path:
        """Path to auto-memory file (`.claude/MEMORY.md` compatible)."""
        return self.root / '.claude' / 'MEMORY.md'

    def load_auto_memory(self) -> str:
        """Load auto-memory content from `.claude/MEMORY.md`."""
        path = self.auto_memory_path()
        if path.exists():
            return path.read_text(encoding='utf-8')
        return ''

    def save_auto_memory(self, content: str) -> None:
        """Save content to `.claude/MEMORY.md`."""
        path = self.auto_memory_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')

    def append_auto_memory(self, entry: str) -> None:
        """Append a new entry to auto-memory (creates new section)."""
        existing = self.load_auto_memory()
        timestamp = utc_now()
        new_content = f'{existing}\n\n## {timestamp}\n\n{entry}'.strip()
        self.save_auto_memory(new_content)

    def search_all(
        self,
        query: str,
        *,
        limit: int = 10,
        include_project: bool = True,
        include_personal: bool = True,
        include_auto: bool = False,
    ) -> dict[str, list[MemoryEntry]]:
        """Search across all memory tiers.

        Returns a dict with keys: 'project', 'personal', 'auto_memory'
        """
        results: dict[str, list[MemoryEntry]] = {
            'project': [],
            'personal': [],
            'auto_memory': [],
        }

        if include_project:
            results['project'] = self.project.search(query, limit=limit)

        if include_personal:
            results['personal'] = self.personal.search(query, limit=limit)

        if include_auto:
            auto_content = self.load_auto_memory()
            if query.lower() in auto_content.lower():
                results['auto_memory'] = [
                    MemoryEntry(
                        memory_id='auto-memory-1',
                        content=auto_content[:500],
                        tags=('auto-memory',),
                    )
                ]

        return results

    def to_prompt_context(self, max_entries: int = 5) -> str:
        """Generate prompt context from all memory tiers."""
        parts: list[str] = []

        project_entries = self.project.list(limit=max_entries)
        if project_entries:
            parts.append('## Project Memory')
            for entry in project_entries:
                parts.append(f'- [{entry.created_at[:10]}] {entry.content[:200]}')

        personal_entries = self.personal.list(limit=max_entries)
        if personal_entries:
            parts.append('## Personal Memory')
            for entry in personal_entries:
                parts.append(f'- [{entry.created_at[:10]}] {entry.content[:200]}')

        auto_memory = self.load_auto_memory()
        if auto_memory:
            parts.append('## Auto-Memory')
            parts.append(auto_memory[:500])

        return '\n'.join(parts) if parts else ''

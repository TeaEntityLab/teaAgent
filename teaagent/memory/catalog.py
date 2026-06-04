"""Memory catalog for tagged memory entries."""

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
    branch_name: str | None = None  # Git branch name for memory isolation
    run_id: str | None = None  # Run ID for memory isolation

    def to_dict(self) -> dict[str, Any]:
        return {
            'memory_id': self.memory_id,
            'content': self.content,
            'tags': list(self.tags),
            'created_at': self.created_at,
            'branch_name': self.branch_name,
            'run_id': self.run_id,
        }


class MemoryCatalog:
    def __init__(self, root: str | Path = '.', *, readonly: bool = False) -> None:
        self.root = Path(root).resolve()
        self.path = self.root / '.teaagent' / 'memory.jsonl'
        self.quarantine_path = self.root / '.teaagent' / 'memory-quarantine.jsonl'
        self.readonly = readonly
        self._corrupt_count = 0  # Track corrupt entries for health reporting
        self._cache: List[MemoryEntry] | None = None  # In-memory cache
        self._cache_dirty = True  # Track if cache needs refresh
        if not readonly:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        elif not self.path.parent.exists():
            # Read-only mode but directory doesn't exist - this is expected for first use
            # No warning needed since we're not creating anything
            pass

    def add(
        self,
        content: str,
        *,
        tags: tuple[str, ...] = (),
        branch_name: str | None = None,
        run_id: str | None = None,
    ) -> MemoryEntry:
        if self.readonly:
            raise RuntimeError('Cannot add memory in readonly mode')
        entry = MemoryEntry(
            memory_id=uuid4().hex,
            content=content.strip(),
            tags=normalize_tags(tags),
            branch_name=branch_name,
            run_id=run_id,
        )
        if not entry.content:
            raise ValueError('memory content cannot be empty')
        append_jsonl_line(self.path, json.dumps(entry.to_dict(), sort_keys=True))
        self._cache_dirty = True  # Invalidate cache on write
        return entry

    def add_quarantined(
        self,
        content: str,
        *,
        tags: tuple[str, ...] = (),
        provenance: dict[str, Any],
        branch_name: str | None = None,
        run_id: str | None = None,
    ) -> MemoryEntry:
        if self.readonly:
            raise RuntimeError('Cannot add quarantined memory in readonly mode')
        entry = MemoryEntry(
            memory_id=uuid4().hex,
            content=content.strip(),
            tags=normalize_tags(tags),
            branch_name=branch_name,
            run_id=run_id,
        )
        if not entry.content:
            raise ValueError('memory content cannot be empty')
        row = {
            **entry.to_dict(),
            'quarantine': True,
            'provenance': provenance,
        }
        append_jsonl_line(self.quarantine_path, json.dumps(row, sort_keys=True))
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
        # Use cache if available and not dirty
        if self._cache is not None and not self._cache_dirty:
            return self._cache

        if not self.path.exists():
            self._cache = []
            self._cache_dirty = False
            return []
        entries: List[MemoryEntry] = []
        for line in self.path.read_text(encoding='utf-8').splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                self._corrupt_count += 1
                continue
            entry = memory_entry_from_payload(payload)
            if entry is not None:
                entries.append(entry)
        self._cache = entries
        self._cache_dirty = False
        return entries

    def health_report(self) -> dict[str, Any]:
        """Report health status including corruption count.

        Scans memory entries for JSON validity to detect corruption.

        Returns:
            Dict with 'corrupt_entries' count and 'healthy' boolean
        """
        total_lines = 0
        corrupt_entries = 0
        if self.path.exists():
            for line in self.path.read_text(encoding='utf-8').splitlines():
                if not line.strip():
                    continue
                total_lines += 1
                try:
                    json.loads(line)
                except json.JSONDecodeError:
                    corrupt_entries += 1

        return {
            'corrupt_entries': corrupt_entries,
            'total_entries': total_lines - corrupt_entries,
            'healthy': corrupt_entries == 0,
        }

    def delete_by_branch(self, branch_name: str) -> int:
        """Delete all memory entries associated with a specific branch.

        Args:
            branch_name: Git branch name to filter by.

        Returns:
            Number of entries deleted.
        """
        if self.readonly:
            raise RuntimeError('Cannot delete memory in readonly mode')
        if not self.path.exists():
            return 0

        entries = self._read_entries()
        filtered = [entry for entry in entries if entry.branch_name != branch_name]
        deleted_count = len(entries) - len(filtered)

        if deleted_count > 0:
            # Rewrite file with filtered entries
            self.path.write_text(
                '\n'.join(
                    json.dumps(entry.to_dict(), sort_keys=True) for entry in filtered
                ),
                encoding='utf-8',
            )
            self._cache_dirty = True  # Invalidate cache on delete

        return deleted_count

    def delete_by_run_id(self, run_id: str) -> int:
        """Delete all memory entries associated with a specific run ID.

        Args:
            run_id: Run ID to filter by.

        Returns:
            Number of entries deleted.
        """
        if self.readonly:
            raise RuntimeError('Cannot delete memory in readonly mode')
        if not self.path.exists():
            return 0

        entries = self._read_entries()
        filtered = [entry for entry in entries if entry.run_id != run_id]
        deleted_count = len(entries) - len(filtered)

        if deleted_count > 0:
            # Rewrite file with filtered entries
            self.path.write_text(
                '\n'.join(
                    json.dumps(entry.to_dict(), sort_keys=True) for entry in filtered
                ),
                encoding='utf-8',
            )
            self._cache_dirty = True  # Invalidate cache on delete

        return deleted_count

    def quarantine_by_branch(self, branch_name: str, reason: str) -> int:
        """Move all memory entries for a branch to quarantine.

        Args:
            branch_name: Git branch name to quarantine.
            reason: Reason for quarantine (stored in provenance).

        Returns:
            Number of entries quarantined.
        """
        if self.readonly:
            raise RuntimeError('Cannot quarantine memory in readonly mode')
        if not self.path.exists():
            return 0

        entries = self._read_entries()
        to_quarantine = [entry for entry in entries if entry.branch_name == branch_name]
        quarantined_count = len(to_quarantine)

        if quarantined_count > 0:
            # Remove from main catalog
            filtered = [entry for entry in entries if entry.branch_name != branch_name]
            self.path.write_text(
                '\n'.join(
                    json.dumps(entry.to_dict(), sort_keys=True) for entry in filtered
                ),
                encoding='utf-8',
            )
            self._cache_dirty = True  # Invalidate cache on quarantine

            # Add to quarantine
            for entry in to_quarantine:
                row = {
                    **entry.to_dict(),
                    'quarantine': True,
                    'provenance': {
                        'reason': reason,
                        'original_branch': branch_name,
                        'quarantined_at': utc_now(),
                    },
                }
                append_jsonl_line(self.quarantine_path, json.dumps(row, sort_keys=True))

        return quarantined_count


# --- Helper functions for memory matching and scoring ---


def normalize_tags(tags: tuple[str, ...]) -> tuple[str, ...]:
    """Normalize tags to lowercase and deduplicate."""
    return tuple(sorted(set(tag.lower().strip() for tag in tags if tag.strip())))


def memory_matches(entry: MemoryEntry, query: str) -> bool:
    """Check if a memory entry matches a query string."""
    normalized = query.strip().lower()
    if not normalized:
        return True
    content_lower = entry.content.lower()
    return normalized in content_lower


def memory_relevance_score(entry: MemoryEntry, query_tokens: tuple[str, ...]) -> int:
    """Score a memory entry's relevance to query tokens."""
    if not query_tokens:
        return 0
    content_lower = entry.content.lower()
    score = 0
    for token in query_tokens:
        if token in content_lower:
            score += 1
    # Boost score for entries with specific tags
    if 'failure' in entry.tags:
        score += 4
    if 'run-summary' in entry.tags:
        score += 2
    return score


def memory_entry_from_payload(payload: dict[str, Any]) -> MemoryEntry | None:
    """Reconstruct a MemoryEntry from a JSON payload."""
    try:
        return MemoryEntry(
            memory_id=payload['memory_id'],
            content=payload['content'],
            tags=tuple(payload.get('tags', [])),
            created_at=payload.get('created_at', ''),
            branch_name=payload.get('branch_name'),
            run_id=payload.get('run_id'),
        )
    except (KeyError, TypeError):
        return None


def memory_entries_to_prompt(entries: list[MemoryEntry]) -> list[dict[str, Any]]:
    return [entry.to_dict() for entry in entries]

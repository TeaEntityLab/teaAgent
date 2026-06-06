from __future__ import annotations

import json
import os
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, List, Literal, cast
from uuid import uuid4

from teaagent.abstract_store import AbstractStore
from teaagent.audit import utc_now
from teaagent.storage import append_jsonl_line


def _create_memory_hierarchy(root: str | Path) -> 'MemoryHierarchy':
    """Factory function to create memory hierarchy."""
    return MemoryHierarchy(root)


@dataclass
class MemoryMeta:
    """Typed metadata for memory entries.

    Carries scope, ownership, freshness, confidence, and review state.
    """

    scope: Literal['project', 'personal', 'auto']
    owner: str  # run_id or user
    source_run_id: str | None = None
    freshness_score: float = 1.0
    ttl_days: int | None = 30
    confidence: float = 0.0
    review_state: Literal[
        'pending', 'approved', 'rejected', 'quarantined', 'promoted'
    ] = 'pending'

    def __post_init__(self) -> None:
        if self.freshness_score < 0.0 or self.freshness_score > 1.0:
            raise ValueError(
                f'freshness_score must be 0.0-1.0, got {self.freshness_score}'
            )
        if self.confidence < 0.0 or self.confidence > 1.0:
            raise ValueError(f'confidence must be 0.0-1.0, got {self.confidence}')
        _valid_review = {
            'pending',
            'approved',
            'rejected',
            'quarantined',
            'promoted',
        }
        if self.review_state not in _valid_review:
            raise ValueError(
                f"Invalid review_state '{self.review_state}'. "
                f'Must be one of: {sorted(_valid_review)}'
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            'scope': self.scope,
            'owner': self.owner,
            'source_run_id': self.source_run_id,
            'freshness_score': self.freshness_score,
            'ttl_days': self.ttl_days,
            'confidence': self.confidence,
            'review_state': self.review_state,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryMeta:
        return cls(
            scope=data.get('scope', 'auto'),
            owner=data.get('owner', 'unknown'),
            source_run_id=data.get('source_run_id'),
            freshness_score=float(data.get('freshness_score', 1.0)),
            ttl_days=data.get('ttl_days', 30),
            confidence=float(data.get('confidence', 0.0)),
            review_state=data.get('review_state', 'pending'),
        )


def compute_freshness(created_at: str, ttl_days: int | None = 30) -> float:
    """Compute freshness score from 1.0 (new) decaying to 0.0 at TTL.

    Args:
        created_at: ISO-format datetime string.
        ttl_days: Days after which freshness reaches 0.0.
                  None means always fresh (returns 1.0).

    Returns:
        Freshness score clamped to [0.0, 1.0].
    """
    if ttl_days is None or ttl_days <= 0:
        return 1.0
    try:
        created = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        age_days = (now - created).total_seconds() / 86400.0
        if age_days <= 0:
            return 1.0
        if age_days >= ttl_days:
            return 0.0
        return round(1.0 - (age_days / ttl_days), 4)
    except (ValueError, TypeError):
        return 0.5  # Conservative fallback for unparseable timestamps


@dataclass(frozen=True)
class MemoryEntry:
    """A single tagged memory entry stored by the agent."""

    memory_id: str
    content: str
    tags: tuple[str, ...] = field(default_factory=tuple)
    created_at: str = field(default_factory=utc_now)
    branch_name: str | None = None  # Git branch name for memory isolation
    run_id: str | None = None  # Run ID for memory isolation
    meta: MemoryMeta | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            'memory_id': self.memory_id,
            'content': self.content,
            'tags': list(self.tags),
            'created_at': self.created_at,
            'branch_name': self.branch_name,
            'run_id': self.run_id,
        }
        if self.meta is not None:
            result['meta'] = self.meta.to_dict()
        return result


class MemoryCatalog(AbstractStore['MemoryEntry']):
    def __init__(self, root: str | Path = '.', *, readonly: bool = False) -> None:
        self.root = Path(root).resolve()
        self.path = self.root / '.teaagent' / 'memory.jsonl'
        self.quarantine_path = self.root / '.teaagent' / 'memory-quarantine.jsonl'
        self.readonly = readonly
        self._corrupt_count = 0  # Track corrupt entries for health reporting
        self._cached_entries: list[MemoryEntry] | None = None
        self._cached_signature: tuple[int, int] | None = None
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
        meta: MemoryMeta | None = None,
    ) -> MemoryEntry:
        if self.readonly:
            raise RuntimeError('Cannot add memory in readonly mode')
        entry = MemoryEntry(
            memory_id=uuid4().hex,
            content=content.strip(),
            tags=normalize_tags(tags),
            branch_name=branch_name,
            run_id=run_id,
            meta=meta,
        )
        if not entry.content:
            raise ValueError('memory content cannot be empty')
        append_jsonl_line(self.path, json.dumps(entry.to_dict(), sort_keys=True))
        return entry

    def add_quarantined(
        self,
        content: str,
        *,
        tags: tuple[str, ...] = (),
        provenance: dict[str, Any],
        branch_name: str | None = None,
        run_id: str | None = None,
        meta: MemoryMeta | None = None,
        audit_logger: Any | None = None,
    ) -> MemoryEntry:
        if self.readonly:
            raise RuntimeError('Cannot add quarantined memory in readonly mode')
        entry = MemoryEntry(
            memory_id=uuid4().hex,
            content=content.strip(),
            tags=normalize_tags(tags),
            branch_name=branch_name,
            run_id=run_id,
            meta=meta,
        )
        if not entry.content:
            raise ValueError('memory content cannot be empty')
        row = {
            **entry.to_dict(),
            'quarantine': True,
            'provenance': provenance,
        }
        append_jsonl_line(self.quarantine_path, json.dumps(row, sort_keys=True))
        if audit_logger is not None:
            effective_run_id = run_id or entry.run_id
            if effective_run_id:
                audit_logger.record(
                    event_type='memory_write_quarantined',
                    run_id=effective_run_id,
                    content_digest=(
                        provenance.get('content_digest', '')
                        if isinstance(provenance, dict)
                        else ''
                    ),
                    quarantine_reason=(
                        provenance.get('reason', 'unknown')
                        if isinstance(provenance, dict)
                        else 'unknown'
                    ),
                    memory_id=entry.memory_id,
                )
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

    def _lock_path(self) -> Path:
        return self.path.with_suffix('.lock')

    @contextmanager
    def _cross_process_lock(self) -> Iterator[None]:
        """Cross-process file lock via ``fcntl.flock``.

        Subagents run in separate processes so ``threading.Lock()`` is
        insufficient.  This lock serialises read-modify-write cycles across
        all processes that share the same ``memory.jsonl`` file.
        """
        lock_path = self._lock_path()
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open('w', encoding='utf-8') as handle:
            try:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            except (ImportError, OSError):
                # fcntl is Unix-specific; gracefully fall back to no locking on Windows or other platforms
                pass
            try:
                yield
            finally:
                try:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                except (ImportError, OSError):
                    # fcntl is Unix-specific; gracefully fall back to no unlocking on Windows or other platforms
                    pass

    def _read_entries(self) -> List[MemoryEntry]:
        if not self.path.exists():
            self._cached_entries = None
            self._cached_signature = None
            return []

        stat = self.path.stat()
        signature = (stat.st_mtime_ns, stat.st_size)
        if self._cached_entries is not None and self._cached_signature == signature:
            return list(self._cached_entries)

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

        self._cached_entries = list(entries)
        self._cached_signature = signature
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

    def _atomic_write_entries(self, entries: List[MemoryEntry]) -> None:
        temp = self.path.with_suffix(f'.jsonl.tmp.{uuid4().hex}')
        temp.write_text(
            '\n'.join(json.dumps(entry.to_dict(), sort_keys=True) for entry in entries),
            encoding='utf-8',
        )
        os.replace(temp, self.path)

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

        with self._cross_process_lock():
            entries = self._read_entries()
            filtered = [entry for entry in entries if entry.branch_name != branch_name]
            deleted_count = len(entries) - len(filtered)

            if deleted_count > 0:
                self._atomic_write_entries(filtered)

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

        with self._cross_process_lock():
            entries = self._read_entries()
            filtered = [entry for entry in entries if entry.run_id != run_id]
            deleted_count = len(entries) - len(filtered)

            if deleted_count > 0:
                self._atomic_write_entries(filtered)

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

        with self._cross_process_lock():
            entries = self._read_entries()
            to_quarantine = [
                entry for entry in entries if entry.branch_name == branch_name
            ]
            quarantined_count = len(to_quarantine)

            if quarantined_count > 0:
                filtered = [
                    entry for entry in entries if entry.branch_name != branch_name
                ]
                self._atomic_write_entries(filtered)

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
                    append_jsonl_line(
                        self.quarantine_path, json.dumps(row, sort_keys=True)
                    )

        return quarantined_count

    def list_quarantined(self, *, limit: int = 20) -> List[MemoryEntry]:
        """List quarantined memory entries.

        Args:
            limit: Maximum number of entries to return.

        Returns:
            List of quarantined memory entries.
        """
        if not self.quarantine_path.exists():
            return []

        entries: List[MemoryEntry] = []
        for line in self.quarantine_path.read_text(encoding='utf-8').splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if payload.get('quarantine', False):
                entry = memory_entry_from_payload(payload)
                if entry is not None:
                    entries.append(entry)

        return list(reversed(entries))[:limit]

    def promote_quarantined(
        self,
        memory_id: str,
        *,
        attestation: str,
        audit_logger: Any | None = None,
        run_id: str | None = None,
    ) -> MemoryEntry:
        """Promote a quarantined memory entry to the main catalog.

        Args:
            memory_id: ID of the quarantined memory entry to promote.
            attestation: Attestation string for the promotion (e.g., operator confirmation).
            audit_logger: Optional audit logger for emitting promotion events.
            run_id: Optional run ID for audit.

        Returns:
            The promoted memory entry.

        Raises:
            FileNotFoundError: If the memory_id is not found in quarantine.
            RuntimeError: If in readonly mode.
        """
        if self.readonly:
            raise RuntimeError('Cannot promote memory in readonly mode')

        # Find the quarantined entry
        quarantined_entries = []
        for line in self.quarantine_path.read_text(encoding='utf-8').splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if (
                payload.get('quarantine', False)
                and payload.get('memory_id') == memory_id
            ):
                quarantined_entries.append(payload)

        if not quarantined_entries:
            raise FileNotFoundError(f"quarantined memory '{memory_id}' not found")

        # Remove quarantine flag and add provenance attestation
        payload = quarantined_entries[0]
        payload['quarantine'] = False
        if 'provenance' not in payload:
            payload['provenance'] = {}
        payload['provenance']['promoted_at'] = utc_now()
        payload['provenance']['attestation'] = attestation

        # Remove from quarantine file
        remaining_lines = [
            line
            for line in self.quarantine_path.read_text(encoding='utf-8').splitlines()
            if line.strip() and json.loads(line).get('memory_id') != memory_id
        ]
        self.quarantine_path.write_text('\n'.join(remaining_lines), encoding='utf-8')

        # Add to main catalog
        entry = memory_entry_from_payload(payload)
        if entry is None:
            raise RuntimeError('Failed to create memory entry from payload')
        with self._cross_process_lock():
            append_jsonl_line(self.path, json.dumps(payload, sort_keys=True))

        if audit_logger is not None:
            effective_run_id = run_id or entry.run_id
            if effective_run_id:
                audit_logger.record(
                    event_type='memory_write_promoted',
                    run_id=effective_run_id,
                    memory_id=entry.memory_id,
                    attestation=attestation,
                )

        return entry

    def set_review_state(
        self, memory_id: str, state: str, attestation: str
    ) -> MemoryEntry:
        """Set review state on a memory entry, updating or creating its meta.

        Args:
            memory_id: ID of the memory entry.
            state: New review state (pending/approved/rejected/quarantined/promoted).
            attestation: Attestation string (e.g. operator/run identifier).

        Returns:
            The updated memory entry.

        Raises:
            RuntimeError: If in readonly mode.
            ValueError: If the state is invalid.
            FileNotFoundError: If the memory_id is not found.
        """
        if self.readonly:
            raise RuntimeError('Cannot set review state in readonly mode')
        _valid = {'pending', 'approved', 'rejected', 'quarantined', 'promoted'}
        if state not in _valid:
            raise ValueError(
                f"Invalid review state '{state}'. Must be one of: {sorted(_valid)}"
            )

        with self._cross_process_lock():
            entries = self._read_entries()
            for i, entry in enumerate(entries):
                if entry.memory_id == memory_id:
                    existing = entry.meta
                    new_meta = MemoryMeta(
                        scope=existing.scope if existing else 'auto',
                        owner=existing.owner if existing else attestation,
                        source_run_id=(existing.source_run_id if existing else None),
                        freshness_score=(existing.freshness_score if existing else 1.0),
                        ttl_days=existing.ttl_days if existing else 30,
                        confidence=existing.confidence if existing else 0.0,
                        review_state=cast(
                            Literal[
                                'pending',
                                'approved',
                                'rejected',
                                'quarantined',
                                'promoted',
                            ],
                            state,
                        ),
                    )
                    new_entry = MemoryEntry(
                        memory_id=entry.memory_id,
                        content=entry.content,
                        tags=entry.tags,
                        created_at=entry.created_at,
                        branch_name=entry.branch_name,
                        run_id=entry.run_id,
                        meta=new_meta,
                    )
                    entries[i] = new_entry
                    self._atomic_write_entries(entries)
                    return new_entry

        raise FileNotFoundError(f"memory '{memory_id}' not found")

    def maintain_dry_run(self) -> dict[str, Any]:
        """Perform a dry-run maintenance report without executing actions.

        Returns:
            Dict with maintenance recommendations and statistics.
        """
        report: dict[str, Any] = {
            'total_entries': 0,
            'quarantined_entries': 0,
            'stale_entries': 0,
            'duplicate_entries': 0,
            'recommendations': [],
        }

        # Count main catalog entries
        main_entries: list[MemoryEntry] = []
        if self.path.exists():
            main_entries = self._read_entries()
            report['total_entries'] = len(main_entries)

            # Check for duplicates (same content)
            content_map: dict[str, list[str]] = {}
            for entry in main_entries:
                content = entry.content
                if content in content_map:
                    content_map[content].append(entry.memory_id)
                else:
                    content_map[content] = [entry.memory_id]

            duplicate_count = sum(1 for ids in content_map.values() if len(ids) > 1)
            report['duplicate_entries'] = duplicate_count
            if duplicate_count > 0:
                report['recommendations'].append(
                    f'Found {duplicate_count} duplicate entries (same content)'
                )

        # Count quarantined entries
        quarantined = self.list_quarantined()
        report['quarantined_entries'] = len(quarantined)

        if report['quarantined_entries'] > 0:
            report['recommendations'].append(
                f'Review {report["quarantined_entries"]} quarantined entries for promotion'
            )

        # Check for stale entries (older than 30 days)
        from datetime import datetime, timedelta, timezone

        cutoff_date = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        stale_count = 0
        for entry in main_entries:
            if entry.created_at < cutoff_date:
                stale_count += 1

        report['stale_entries'] = stale_count
        if stale_count > 0:
            report['recommendations'].append(
                f'Consider reviewing {stale_count} entries older than 30 days'
            )

        return report

    def save(self, key: str, value: MemoryEntry) -> None:
        if self.readonly:
            raise RuntimeError('Cannot save in readonly mode')
        with self._cross_process_lock():
            entries = self._read_entries()
            found = False
            for i, entry in enumerate(entries):
                if entry.memory_id == key:
                    entries[i] = value
                    found = True
                    break
            if found:
                self._atomic_write_entries(entries)
            else:
                append_jsonl_line(
                    self.path, json.dumps(value.to_dict(), sort_keys=True)
                )

    def load(self, key: str) -> MemoryEntry | None:
        try:
            return self.show(key)
        except FileNotFoundError:
            return None

    def delete(self, key: str) -> bool:
        if self.readonly:
            raise RuntimeError('Cannot delete in readonly mode')
        with self._cross_process_lock():
            entries = self._read_entries()
            original = len(entries)
            entries = [e for e in entries if e.memory_id != key]
            if len(entries) == original:
                return False
            self._atomic_write_entries(entries)
            return True

    def list_keys(self) -> list[str]:
        return [e.memory_id for e in self._read_entries()]

    def exists(self, key: str) -> bool:
        try:
            self.show(key)
            return True
        except FileNotFoundError:
            return False

    def clear(self) -> None:
        if self.readonly:
            raise RuntimeError('Cannot clear in readonly mode')
        with self._cross_process_lock():
            if self.path.exists():
                self.path.write_text('', encoding='utf-8')


def memory_entry_from_payload(payload: Any) -> MemoryEntry | None:
    if not isinstance(payload, dict):
        return None
    memory_id = payload.get('memory_id')
    content = payload.get('content')
    tags = payload.get('tags', [])
    created_at = payload.get('created_at', utc_now())
    branch_name = payload.get('branch_name')
    run_id = payload.get('run_id')
    if not isinstance(memory_id, str) or not memory_id:
        return None
    if not isinstance(content, str) or not content:
        return None
    if not isinstance(created_at, str) or not created_at:
        return None
    if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
        return None
    if branch_name is not None and not isinstance(branch_name, str):
        return None
    if run_id is not None and not isinstance(run_id, str):
        return None
    meta: MemoryMeta | None = None
    meta_payload = payload.get('meta')
    if isinstance(meta_payload, dict):
        try:
            meta = MemoryMeta.from_dict(meta_payload)
        except (ValueError, TypeError):
            meta = None  # Degrade safely on malformed meta
    return MemoryEntry(
        memory_id=memory_id,
        content=content,
        tags=tuple(tags),
        created_at=created_at,
        branch_name=branch_name,
        run_id=run_id,
        meta=meta,
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

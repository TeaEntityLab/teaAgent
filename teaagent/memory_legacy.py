"""Legacy memory catalog module (re-exported from teaagent.memory.catalog for compatibility)."""

from __future__ import annotations

from teaagent.memory.catalog import (
    MemoryCatalog,
    MemoryEntry,
    MemoryHierarchy,
    _create_memory_hierarchy,
    memory_entries_to_prompt,
    memory_entry_from_payload,
    memory_matches,
    memory_relevance_score,
    normalize_tags,
)

__all__ = [
    'MemoryCatalog',
    'MemoryEntry',
    'MemoryHierarchy',
    '_create_memory_hierarchy',
    'memory_entries_to_prompt',
    'memory_entry_from_payload',
    'normalize_tags',
    'memory_matches',
    'memory_relevance_score',
]

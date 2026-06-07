"""Legacy memory catalog module (deprecated — use ``teaagent.memory``)."""

from __future__ import annotations

import warnings

warnings.warn(
    'teaagent.memory_legacy is deprecated; import from teaagent.memory instead',
    DeprecationWarning,
    stacklevel=2,
)

from teaagent.memory.catalog import (  # noqa: E402
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

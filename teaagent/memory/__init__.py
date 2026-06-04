"""Memory and context management for TeaAgent.

This module provides persistent memory features including:
- Failure experience cards for learning from past mistakes
- Pinned file tracking for live context synchronization
- Memory catalog for tagged memory entries
- Team memory for shared agent context
"""

from __future__ import annotations

from teaagent.memory.failure_card import FailureCard, FailureCardStorage
from teaagent.memory.file_watcher import FileWatcher
from teaagent.memory.pinned_file import PinnedFile, PinnedFileStorage
from teaagent.memory.team_memory import TeamMemory

# Import from the canonical memory catalog module
from .catalog import (
    MemoryCatalog,
    MemoryEntry,
    memory_entries_to_prompt,
    memory_entry_from_payload,
)

__all__ = [
    'FailureCard',
    'FailureCardStorage',
    'PinnedFile',
    'PinnedFileStorage',
    'FileWatcher',
    'TeamMemory',
    'MemoryCatalog',
    'MemoryEntry',
    'memory_entries_to_prompt',
    'memory_entry_from_payload',
]

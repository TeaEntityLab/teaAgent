from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from teaagent.context_pack import ContextPack
from teaagent.daily import (
    CONTEXT_PROFILES,
    TokenBudgetReport,
    build_token_budget_report,
)
from teaagent.memory import MemoryCatalog, MemoryEntry
from teaagent.run_store import RunStore

logger = logging.getLogger(__name__)

_LARGE_FILE_THRESHOLD_BYTES = 100_000
_MAX_ARTIFACTS_TO_REPORT = 5


@dataclass
class ContextPressureScore:
    """A scorecard that estimates how much pressure the current workspace
    puts on the LLM's context window.

    Derived from the token-budget report, memory catalogue, pinned files,
    recent runs, and large workspace files.
    """

    token_usage_ratio: float
    usage_level: str
    estimated_total_tokens: int
    max_context_tokens: int | None
    memory_count: int
    files_pinned: int
    recent_runs: int
    large_artifacts: list[str]
    contributors: dict[str, int]
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            'token_usage_ratio': self.token_usage_ratio,
            'usage_level': self.usage_level,
            'estimated_total_tokens': self.estimated_total_tokens,
            'max_context_tokens': self.max_context_tokens,
            'memory_count': self.memory_count,
            'files_pinned': self.files_pinned,
            'recent_runs': self.recent_runs,
            'large_artifacts': self.large_artifacts,
            'contributors': self.contributors,
            'recommendations': self.recommendations,
        }


def _detect_large_artifacts(workspace_root: Path) -> list[str]:
    """Walk the workspace and collect paths of large files, ignoring well-known
    directories that are rarely context-relevant."""
    ignore_dirs = {
        '.git',
        '__pycache__',
        'node_modules',
        'dist',
        'build',
        '.venv',
        'venv',
        '.tox',
        '.mypy_cache',
        '.pytest_cache',
        '.teasgent',
        '.teaagent',
    }
    large: list[str] = []
    try:
        for entry in workspace_root.rglob('*'):
            if not entry.is_file():
                continue
            parts = set(entry.parts)
            if ignore_dirs & parts:
                continue
            try:
                size = entry.stat().st_size
            except OSError:
                continue
            if size >= _LARGE_FILE_THRESHOLD_BYTES:
                large.append(str(entry.relative_to(workspace_root)))
    except (OSError, PermissionError):
        pass
    return sorted(large)[:_MAX_ARTIFACTS_TO_REPORT]


def compute_context_pressure(
    workspace_root: Path,
) -> ContextPressureScore:
    """Compute a context-pressure score for the given workspace root.

    Returns a ``ContextPressureScore`` that can be displayed in the TUI
    state panel or serialised to JSON.
    """
    root = workspace_root.resolve()

    memory = MemoryCatalog(root, readonly=True)
    memories: list[MemoryEntry] = memory.list(limit=20)

    profile = CONTEXT_PROFILES['balanced']
    context_pack = ContextPack(
        task='',
        candidate_files=[],
        memories=[],
        symbols=[],
        graph_rag={},
    )

    budget: TokenBudgetReport = build_token_budget_report(
        task='(context pressure check)',
        provider='gpt',
        model=None,
        context_pack=context_pack,
        memories=memories,
        tool_count=0,
        profile=profile,
    )

    memory_count = len(memories)

    files_pinned = 0
    try:
        from teaagent.memory.pinned_file import PinnedFileStorage

        pinned_storage = PinnedFileStorage(root)
        files_pinned = len(pinned_storage.list_all())
    except Exception:
        logger.exception('pinned files query failed')

    recent_runs = 0
    try:
        store = RunStore(root, readonly=True)
        recent_runs = len(store.list_runs(limit=50))
    except Exception:
        logger.exception('recent runs query failed')

    large_artifacts = _detect_large_artifacts(root)

    recommendations: list[str] = list(budget.recommendations)

    if memory_count > 50:
        recommendations.append(
            f'high memory count ({memory_count}); consider pruning or reviewing'
        )
    if files_pinned > 10:
        recommendations.append(f'{files_pinned} pinned files — review for relevance')
    if large_artifacts:
        recommendations.append(
            f'{len(large_artifacts)} large file(s) detected '
            f'(≥ {_LARGE_FILE_THRESHOLD_BYTES // 1000} KB); '
            'consider summarising or excluding from context'
        )
    if recent_runs > 20:
        recommendations.append(
            f'{recent_runs} recent runs exist; consider archiving older runs'
        )

    usage_ratio = budget.usage_ratio if budget.usage_ratio is not None else 0.0

    return ContextPressureScore(
        token_usage_ratio=usage_ratio,
        usage_level=budget.usage_level,
        estimated_total_tokens=budget.estimated_total_tokens,
        max_context_tokens=budget.max_context_tokens,
        memory_count=memory_count,
        files_pinned=files_pinned,
        recent_runs=recent_runs,
        large_artifacts=large_artifacts,
        contributors=budget.contributors,
        recommendations=recommendations,
    )

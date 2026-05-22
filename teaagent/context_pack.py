from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from teaagent.code_analysis._prompt import extract_candidate_paths
from teaagent.memory import MemoryCatalog

_CODE_SUFFIXES = {'.py', '.pyi', '.ts', '.tsx', '.js', '.jsx'}
_INDEX_MARKERS = (
    '.teaagent/graphqlite.db',
    '.teaagent/knowledge',
    '.teaagent/codegraph',
)


@dataclass(frozen=True)
class ContextPack:
    """Read-only evidence bundle for planning/preflight (Aider-style repo map)."""

    task: str
    candidate_files: list[dict[str, Any]]
    memories: list[dict[str, Any]]
    symbols: list[dict[str, Any]]
    graph_rag: dict[str, Any]
    read_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            'task': self.task,
            'candidate_files': self.candidate_files,
            'memories': self.memories,
            'symbols': self.symbols,
            'graph_rag': self.graph_rag,
            'read_only': self.read_only,
        }


def _resolve_candidate_file(root: Path, raw: str) -> dict[str, Any]:
    candidate = (
        (root / raw).resolve() if not Path(raw).is_absolute() else Path(raw).resolve()
    )
    try:
        candidate.relative_to(root)
        in_workspace = True
    except ValueError:
        in_workspace = False
    exists = candidate.is_file() if in_workspace else False
    return {
        'path': raw,
        'resolved': str(candidate) if in_workspace else raw,
        'exists': exists,
        'in_workspace': in_workspace,
        'reason': 'task_path_mention',
    }


def _symbol_hints(
    root: Path, candidate_files: list[dict[str, Any]], *, limit: int
) -> list[dict[str, Any]]:
    hints: list[dict[str, Any]] = []
    for entry in candidate_files:
        if not entry.get('exists'):
            continue
        path = Path(str(entry['resolved']))
        if path.suffix not in _CODE_SUFFIXES:
            continue
        try:
            line_count = sum(1 for _ in path.open(encoding='utf-8', errors='ignore'))
        except OSError:
            line_count = 0
        hints.append(
            {
                'path': entry['path'],
                'line_count': line_count,
                'lsp_symbols': 'deferred',
                'reason': 'file_stat_only',
            }
        )
        if len(hints) >= limit:
            break
    return hints


def _graph_rag_status(root: Path, task: str) -> dict[str, Any]:
    indexes = [marker for marker in _INDEX_MARKERS if (root / marker).exists()]
    return {
        'status': 'indexed' if indexes else 'not_indexed',
        'indexes': indexes,
        'query': task[:120],
        'hits': [],
        'reason': 'read_only_preflight_no_search',
    }


def build_context_pack(
    task: str,
    *,
    root: str | Path = '.',
    memory_limit: int = 5,
    file_limit: int = 12,
    symbol_limit: int = 8,
    include_agents_md: bool = True,
) -> ContextPack:
    root_path = Path(root).resolve()
    texts = [task]
    agents_path = root_path / 'AGENTS.md'
    if include_agents_md and agents_path.is_file():
        texts.append(agents_path.read_text(encoding='utf-8'))

    raw_paths = extract_candidate_paths(*texts)
    candidate_files = [
        _resolve_candidate_file(root_path, raw) for raw in raw_paths[:file_limit]
    ]
    memories = [
        entry.to_dict()
        for entry in MemoryCatalog(root_path).search(task, limit=memory_limit)
    ]
    symbols = _symbol_hints(root_path, candidate_files, limit=symbol_limit)
    graph_rag = _graph_rag_status(root_path, task)

    return ContextPack(
        task=task,
        candidate_files=candidate_files,
        memories=memories,
        symbols=symbols,
        graph_rag=graph_rag,
    )

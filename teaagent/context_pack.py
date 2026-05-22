from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from teaagent.code_analysis._config import CodeAnalysisConfig
from teaagent.code_analysis._manager import LSPServerManager
from teaagent.code_analysis._prompt import extract_candidate_paths
from teaagent.hybrid_search import indexed_db_path, search_if_indexed
from teaagent.memory import MemoryCatalog
from teaagent.rag import tokenize

_CODE_SUFFIXES = {'.py', '.pyi', '.ts', '.tsx', '.js', '.jsx'}
_INDEX_MARKERS = (
    '.teaagent/graphqlite.db',
    '.teaagent/knowledge',
    '.teaagent/codegraph',
    '.teaagent/hybrid_search.sqlite3',
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


def _resolve_code_analysis_config(
    root: Path, config: Optional[CodeAnalysisConfig]
) -> Optional[CodeAnalysisConfig]:
    if config is not None:
        return config if config.enabled else None
    try:
        from teaagent.config_loader import ConfigResolver

        rc = ConfigResolver(workspace_root=root).resolve()
        enabled = rc.get('code_analysis_enabled')
        if isinstance(enabled, bool) and enabled:
            return CodeAnalysisConfig.from_root(root, enabled=True)
    except Exception:
        return None
    return None


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


def _file_stat_symbol(entry: dict[str, Any]) -> dict[str, Any]:
    path = Path(str(entry['resolved']))
    try:
        line_count = sum(1 for _ in path.open(encoding='utf-8', errors='ignore'))
    except OSError:
        line_count = 0
    return {
        'path': entry['path'],
        'line_count': line_count,
        'symbols': [],
        'reason': 'file_stat_only',
    }


def _hydrate_lsp_symbols(
    *,
    candidate_files: list[dict[str, Any]],
    candidate_paths: list[str],
    config: CodeAnalysisConfig,
    limit: int,
) -> list[dict[str, Any]]:
    manager = LSPServerManager(config)
    hints: list[dict[str, Any]] = []
    try:
        for raw in candidate_paths:
            if len(hints) >= limit:
                break
            entry = next(
                (item for item in candidate_files if item['path'] == raw), None
            )
            if entry is None or not entry.get('exists'):
                continue
            if Path(str(entry['resolved'])).suffix not in _CODE_SUFFIXES:
                continue
            symbols = manager.document_symbols(raw)
            if not symbols:
                continue
            hints.append(
                {
                    'path': raw,
                    'symbols': [
                        {
                            'kind': symbol.kind,
                            'name': symbol.symbol,
                            'line': symbol.line,
                            'column': symbol.column,
                            'detail': symbol.detail,
                        }
                        for symbol in symbols[:20]
                    ],
                    'reason': 'lsp_document_symbols',
                }
            )
    finally:
        manager.shutdown_all()
    return hints


def _symbol_hints(
    root: Path,
    candidate_files: list[dict[str, Any]],
    candidate_paths: list[str],
    *,
    limit: int,
    hydrate_lsp: bool,
    code_analysis_config: Optional[CodeAnalysisConfig],
) -> list[dict[str, Any]]:
    if hydrate_lsp:
        config = _resolve_code_analysis_config(root, code_analysis_config)
        if config is not None:
            try:
                hydrated = _hydrate_lsp_symbols(
                    candidate_files=candidate_files,
                    candidate_paths=candidate_paths,
                    config=config,
                    limit=limit,
                )
                if hydrated:
                    return hydrated
            except Exception:
                pass

    hints: list[dict[str, Any]] = []
    for entry in candidate_files:
        if not entry.get('exists'):
            continue
        if Path(str(entry['resolved'])).suffix not in _CODE_SUFFIXES:
            continue
        hints.append(_file_stat_symbol(entry))
        if len(hints) >= limit:
            break
    return hints


def _graph_rag_evidence(
    root: Path,
    task: str,
    *,
    search_graph: bool,
    hit_limit: int,
) -> dict[str, Any]:
    indexes = [marker for marker in _INDEX_MARKERS if (root / marker).exists()]
    hybrid_db = indexed_db_path(root)
    if hybrid_db.is_file() and '.teaagent/hybrid_search.sqlite3' not in indexes:
        indexes.append('.teaagent/hybrid_search.sqlite3')

    if not indexes:
        return {
            'status': 'not_indexed',
            'indexes': [],
            'query': task[:120],
            'hits': [],
            'reason': 'no_index_present',
        }

    if not search_graph:
        return {
            'status': 'indexed',
            'indexes': indexes,
            'query': task[:120],
            'hits': [],
            'reason': 'search_disabled',
        }

    search_query = ' '.join(tokenize(task)[:12]) or task[:120]
    try:
        result = search_if_indexed(root, search_query, limit=hit_limit)
    except Exception as exc:
        return {
            'status': 'indexed',
            'indexes': indexes,
            'query': task[:120],
            'hits': [],
            'reason': f'search_failed:{exc.__class__.__name__}',
        }

    if result is None:
        return {
            'status': 'indexed',
            'indexes': indexes,
            'query': task[:120],
            'hits': [],
            'reason': 'no_hybrid_index',
        }

    hits = result.get('hits', [])
    return {
        'status': 'indexed',
        'indexes': indexes,
        'query': task[:120],
        'search_query': search_query,
        'hits': hits,
        'backend': result.get('backend', 'local'),
        'collection': result.get('collection', 'default'),
        'reason': 'hybrid_search_read' if hits else 'hybrid_search_empty',
    }


def build_context_pack(
    task: str,
    *,
    root: str | Path = '.',
    memory_limit: int = 5,
    file_limit: int = 12,
    symbol_limit: int = 8,
    graph_hit_limit: int = 5,
    include_agents_md: bool = True,
    hydrate_lsp: bool = False,
    search_graph: bool = True,
    code_analysis_config: Optional[CodeAnalysisConfig] = None,
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
    symbols = _symbol_hints(
        root_path,
        candidate_files,
        raw_paths,
        limit=symbol_limit,
        hydrate_lsp=hydrate_lsp,
        code_analysis_config=code_analysis_config,
    )
    graph_rag = _graph_rag_evidence(
        root_path, task, search_graph=search_graph, hit_limit=graph_hit_limit
    )

    return ContextPack(
        task=task,
        candidate_files=candidate_files,
        memories=memories,
        symbols=symbols,
        graph_rag=graph_rag,
    )

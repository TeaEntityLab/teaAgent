from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from teaagent.code_analysis._config import CodeAnalysisConfig
from teaagent.code_analysis._manager import LSPServerManager
from teaagent.code_analysis._prompt import extract_candidate_paths
from teaagent.code_ontology import CodeOntologyGraph
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


def _candidate_from_graph_hit(root: Path, hit: dict[str, Any]) -> dict[str, Any] | None:
    raw = str(hit.get('path') or hit.get('doc_id') or '').strip()
    if not raw:
        return None
    entry = _resolve_candidate_file(root, raw)
    if not entry['exists']:
        return None
    entry['reason'] = 'graph_rag_hit'
    entry['source'] = str(hit.get('source') or hit.get('backend') or 'graph_rag')
    if 'score' in hit:
        entry['score'] = hit.get('score')
    snippet = str(hit.get('snippet', '')).strip()
    if snippet:
        entry['snippet'] = snippet[:200]
    return entry


def _append_graph_hit_candidates(
    *,
    root: Path,
    candidate_files: list[dict[str, Any]],
    graph_rag: dict[str, Any],
    file_limit: int,
) -> list[dict[str, Any]]:
    seen = {str(entry.get('path')) for entry in candidate_files}
    enriched = list(candidate_files)
    for hit in graph_rag.get('hits', []):
        if not isinstance(hit, dict):
            continue
        entry = _candidate_from_graph_hit(root, hit)
        if entry is None or entry['path'] in seen:
            continue
        enriched.append(entry)
        seen.add(entry['path'])
        if len(enriched) >= file_limit:
            break
    return enriched


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


_GRAPHQLITE_DOCUMENT_QUERY = 'MATCH (n:Document) RETURN n.doc_id AS doc_id, n.text AS text, n.source AS source LIMIT 100'


def _knowledge_collection_name(root: Path) -> str:
    marker = root / '.teaagent' / 'knowledge'
    if marker.is_file():
        try:
            payload = json.loads(marker.read_text(encoding='utf-8'))
            if isinstance(payload, dict):
                name = payload.get('collection')
                if isinstance(name, str) and name.strip():
                    return name.strip()
        except (OSError, json.JSONDecodeError, TypeError):
            pass
    return 'knowledge'


def _tag_hits(hits: list[dict[str, Any]], source: str) -> list[dict[str, Any]]:
    tagged: list[dict[str, Any]] = []
    for hit in hits:
        entry = dict(hit)
        entry['source'] = source
        tagged.append(entry)
    return tagged


def _dedupe_hits(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for hit in hits:
        key = str(hit.get('path') or hit.get('doc_id') or hit.get('snippet', ''))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(hit)
    return deduped


def _graphqlite_hits(
    root: Path, search_query: str, *, limit: int
) -> list[dict[str, Any]]:
    db_path = root / '.teaagent' / 'graphqlite.db'
    if not db_path.is_file():
        return []
    tokens = [token.lower() for token in tokenize(search_query)]
    try:
        from teaagent.graphqlite_store import GraphQLiteConfig, GraphQLiteGraphStore

        store = GraphQLiteGraphStore(GraphQLiteConfig(database=str(db_path)))
        rows = store.query(_GRAPHQLITE_DOCUMENT_QUERY)
    except Exception:
        return []
    if not isinstance(rows, list):
        return []

    hits: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        text = str(row.get('text', ''))
        lower = text.lower()
        if tokens and not all(token in lower for token in tokens):
            continue
        doc_id = str(row.get('doc_id', ''))
        hits.append(
            {
                'doc_id': doc_id,
                'path': doc_id,
                'snippet': text[:200],
                'source': 'graphqlite',
            }
        )
        if len(hits) >= limit:
            break
    return hits


def _code_ontology_hits(root: Path, task: str, *, limit: int) -> list[dict[str, Any]]:
    """Extract code ontology dependency information for context."""
    try:
        from teaagent.graphqlite_store import GraphQLiteConfig, GraphQLiteGraphStore

        db_path = root / '.teaagent' / 'graphqlite.db'
        if not db_path.is_file():
            return []

        store = GraphQLiteGraphStore(GraphQLiteConfig(database=str(db_path)))
        ontology = CodeOntologyGraph(root, graph_store=store)

        # Extract entity names from task
        tokens = tokenize(task)
        entity_names = [t for t in tokens if len(t) > 2 and t.isidentifier()]

        hits: list[dict[str, Any]] = []
        for entity_name in entity_names[:5]:  # Limit to top 5 entities
            # Query dependencies
            deps = ontology.query_dependencies(entity_name, direction='both')
            for dep in deps[:3]:  # Limit to top 3 dependencies per entity
                if isinstance(dep, dict) and 'file_path' in dep:
                    hits.append(
                        {
                            'path': dep.get('file_path', ''),
                            'snippet': f'Dependency chain for {entity_name}: {dep.get("name", "")} ({dep.get("node_type", "")})',
                            'source': 'code_ontology',
                            'entity': entity_name,
                            'relation': 'dependency',
                        }
                    )
                    if len(hits) >= limit:
                        return hits

        return hits
    except Exception:
        return []


def _graph_rag_reason(
    sources: dict[str, dict[str, Any]], hits: list[dict[str, Any]]
) -> str:
    if hits:
        active = [name for name, payload in sources.items() if payload.get('hits')]
        if len(active) == 1 and active[0] == 'hybrid':
            return 'hybrid_search_read'
        if len(active) == 1 and active[0] == 'knowledge':
            return 'knowledge_search_read'
        if len(active) == 1 and active[0] == 'graphqlite':
            return 'graphqlite_read'
        return 'multi_source_read'
    if sources:
        return 'indexed_search_empty'
    return 'no_hybrid_index'


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
            'sources': {},
            'reason': 'no_index_present',
        }

    if not search_graph:
        return {
            'status': 'indexed',
            'indexes': indexes,
            'query': task[:120],
            'hits': [],
            'sources': {},
            'reason': 'search_disabled',
        }

    search_query = ' '.join(tokenize(task)[:12]) or task[:120]
    sources: dict[str, dict[str, Any]] = {}
    combined: list[dict[str, Any]] = []

    try:
        hybrid_result = search_if_indexed(root, search_query, limit=hit_limit)
        if hybrid_result is not None:
            hybrid_hits = _tag_hits(hybrid_result.get('hits', []), 'hybrid')
            sources['hybrid'] = {
                'hits': hybrid_hits,
                'backend': hybrid_result.get('backend', 'local'),
                'collection': hybrid_result.get('collection', 'default'),
                'reason': 'hybrid_search_read'
                if hybrid_hits
                else 'hybrid_search_empty',
            }
            combined.extend(hybrid_hits)

        knowledge_marker = root / '.teaagent' / 'knowledge'
        if knowledge_marker.exists() and hybrid_db.is_file():
            collection = _knowledge_collection_name(root)
            knowledge_result = search_if_indexed(
                root, search_query, limit=hit_limit, collection=collection
            )
            if knowledge_result is not None:
                knowledge_hits = _tag_hits(
                    knowledge_result.get('hits', []), 'knowledge'
                )
                sources['knowledge'] = {
                    'hits': knowledge_hits,
                    'backend': knowledge_result.get('backend', 'local'),
                    'collection': collection,
                    'reason': (
                        'knowledge_search_read'
                        if knowledge_hits
                        else 'knowledge_search_empty'
                    ),
                }
                combined.extend(knowledge_hits)

        graphqlite_hits = _graphqlite_hits(root, search_query, limit=hit_limit)
        if graphqlite_hits:
            sources['graphqlite'] = {
                'hits': graphqlite_hits,
                'backend': 'graphqlite',
                'reason': 'graphqlite_read',
            }
            combined.extend(graphqlite_hits)

        # Add code ontology dependency information
        ontology_hits = _code_ontology_hits(root, task, limit=hit_limit)
        if ontology_hits:
            sources['code_ontology'] = {
                'hits': ontology_hits,
                'backend': 'code_ontology',
                'reason': 'code_ontology_dependency_analysis',
            }
            combined.extend(ontology_hits)
    except Exception as exc:
        return {
            'status': 'indexed',
            'indexes': indexes,
            'query': task[:120],
            'search_query': search_query,
            'hits': [],
            'sources': sources,
            'reason': f'search_failed:{exc.__class__.__name__}',
        }

    hits = _dedupe_hits(combined)[:hit_limit]
    payload: dict[str, Any] = {
        'status': 'indexed',
        'indexes': indexes,
        'query': task[:120],
        'search_query': search_query,
        'hits': hits,
        'sources': sources,
        'reason': _graph_rag_reason(sources, hits),
    }
    if hybrid_result := sources.get('hybrid'):
        payload['backend'] = hybrid_result.get('backend', 'local')
        payload['collection'] = hybrid_result.get('collection', 'default')
    return payload


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
    readonly: bool = False,
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
        for entry in MemoryCatalog(root_path, readonly=readonly).search(
            task, limit=memory_limit
        )
    ]
    graph_rag = _graph_rag_evidence(
        root_path, task, search_graph=search_graph, hit_limit=graph_hit_limit
    )
    candidate_files = _append_graph_hit_candidates(
        root=root_path,
        candidate_files=candidate_files,
        graph_rag=graph_rag,
        file_limit=file_limit,
    )
    symbols = _symbol_hints(
        root_path,
        candidate_files,
        raw_paths,
        limit=symbol_limit,
        hydrate_lsp=hydrate_lsp,
        code_analysis_config=code_analysis_config,
    )

    return ContextPack(
        task=task,
        candidate_files=candidate_files,
        memories=memories,
        symbols=symbols,
        graph_rag=graph_rag,
    )

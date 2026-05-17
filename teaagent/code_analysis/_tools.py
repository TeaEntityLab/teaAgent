from __future__ import annotations

from teaagent.code_analysis._config import CodeAnalysisConfig
from teaagent.code_analysis._graph_rag import ingest_code_relations_to_graph
from teaagent.code_analysis._manager import LSPServerManager
from teaagent.code_analysis._treesitter import extract_tree_sitter_relations
from teaagent.graph_rag import KnowledgeGraph
from teaagent.tools import ToolAnnotations, ToolRegistry


def register_code_analysis_tools(
    registry: ToolRegistry, config: CodeAnalysisConfig
) -> None:
    if not config.enabled:
        return

    manager = LSPServerManager(config)

    registry.register(
        name='code_definition',
        description='Find the definition location for the symbol at a file position.',
        input_schema={
            'type': 'object',
            'properties': {
                'path': {'type': 'string'},
                'line': {'type': 'integer'},
                'column': {'type': 'integer'},
            },
            'required': ['path', 'line', 'column'],
        },
        output_schema={
            'type': 'object',
            'properties': {
                'references': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'symbol': {'type': 'string'},
                            'file_path': {'type': 'string'},
                            'line': {'type': 'integer'},
                            'column': {'type': 'integer'},
                            'kind': {'type': 'string'},
                            'detail': {'type': 'string'},
                        },
                        'required': [
                            'symbol',
                            'file_path',
                            'line',
                            'column',
                            'kind',
                            'detail',
                        ],
                    },
                }
            },
            'required': ['references'],
        },
        annotations=ToolAnnotations(read_only=True, destructive=False, idempotent=True),
        handler=lambda args: {
            'references': [
                {
                    'symbol': r.symbol,
                    'file_path': r.file_path,
                    'line': r.line,
                    'column': r.column,
                    'kind': r.kind,
                    'detail': r.detail,
                }
                for r in manager.goto_definition(
                    args['path'], args['line'], args['column']
                )
            ]
        },
    )

    registry.register(
        name='code_references',
        description='Find references to the symbol at a file position.',
        input_schema={
            'type': 'object',
            'properties': {
                'path': {'type': 'string'},
                'line': {'type': 'integer'},
                'column': {'type': 'integer'},
            },
            'required': ['path', 'line', 'column'],
        },
        output_schema={
            'type': 'object',
            'properties': {
                'references': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'symbol': {'type': 'string'},
                            'file_path': {'type': 'string'},
                            'line': {'type': 'integer'},
                            'column': {'type': 'integer'},
                            'kind': {'type': 'string'},
                            'detail': {'type': 'string'},
                        },
                        'required': [
                            'symbol',
                            'file_path',
                            'line',
                            'column',
                            'kind',
                            'detail',
                        ],
                    },
                },
            },
            'required': ['references'],
        },
        annotations=ToolAnnotations(read_only=True, destructive=False, idempotent=True),
        handler=lambda args: {
            'references': [
                {
                    'symbol': r.symbol,
                    'file_path': r.file_path,
                    'line': r.line,
                    'column': r.column,
                    'kind': r.kind,
                    'detail': r.detail,
                }
                for r in manager.find_references(
                    args['path'], args['line'], args['column']
                )
            ]
        },
    )

    registry.register(
        name='code_diagnostics',
        description='Get diagnostics (errors/warnings) for a file.',
        input_schema={
            'type': 'object',
            'properties': {'path': {'type': 'string'}},
            'required': ['path'],
        },
        output_schema={
            'type': 'object',
            'properties': {
                'diagnostics': {'type': 'array', 'items': {'type': 'object'}},
            },
            'required': ['diagnostics'],
        },
        annotations=ToolAnnotations(read_only=True, destructive=False, idempotent=True),
        handler=lambda args: {
            'diagnostics': manager.document_diagnostics(args['path'])
        },
    )

    registry.register(
        name='code_symbols',
        description='List symbols for a file (functions, classes, variables).',
        input_schema={
            'type': 'object',
            'properties': {'path': {'type': 'string'}},
            'required': ['path'],
        },
        output_schema={
            'type': 'object',
            'properties': {
                'symbols': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'symbol': {'type': 'string'},
                            'file_path': {'type': 'string'},
                            'line': {'type': 'integer'},
                            'column': {'type': 'integer'},
                            'kind': {'type': 'string'},
                            'detail': {'type': 'string'},
                        },
                        'required': [
                            'symbol',
                            'file_path',
                            'line',
                            'column',
                            'kind',
                            'detail',
                        ],
                    },
                },
            },
            'required': ['symbols'],
        },
        annotations=ToolAnnotations(read_only=True, destructive=False, idempotent=True),
        handler=lambda args: {
            'symbols': [
                {
                    'symbol': r.symbol,
                    'file_path': r.file_path,
                    'line': r.line,
                    'column': r.column,
                    'kind': r.kind,
                    'detail': r.detail,
                }
                for r in manager.document_symbols(args['path'])
            ]
        },
    )

    registry.register(
        name='code_tree_sitter_relations',
        description='Extract code relationships with tree-sitter-compatible parsing.',
        input_schema={
            'type': 'object',
            'properties': {'path': {'type': 'string'}},
            'required': ['path'],
        },
        output_schema={
            'type': 'object',
            'properties': {
                'relations': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'source': {'type': 'string'},
                            'relation': {'type': 'string'},
                            'target': {'type': 'string'},
                            'line': {'type': 'integer'},
                            'column': {'type': 'integer'},
                        },
                        'required': [
                            'source',
                            'relation',
                            'target',
                            'line',
                            'column',
                        ],
                    },
                }
            },
            'required': ['relations'],
        },
        annotations=ToolAnnotations(read_only=True, destructive=False, idempotent=True),
        handler=lambda args: {
            'relations': [
                {
                    'source': rel.source,
                    'relation': rel.relation,
                    'target': rel.target,
                    'line': rel.line,
                    'column': rel.column,
                }
                for rel in extract_tree_sitter_relations(args['path'])
            ]
        },
    )

    registry.register(
        name='code_relations_to_graph',
        description='Extract code relationships and ingest them into an in-memory GraphRAG graph.',
        input_schema={
            'type': 'object',
            'properties': {
                'path': {'type': 'string'},
                'doc_id': {'type': 'string'},
                'source': {'type': 'string'},
            },
            'required': ['path'],
        },
        output_schema={
            'type': 'object',
            'properties': {
                'relations': {'type': 'integer'},
                'edges': {'type': 'integer'},
                'documents': {'type': 'integer'},
            },
            'required': ['relations', 'edges', 'documents'],
        },
        annotations=ToolAnnotations(
            read_only=False, destructive=False, idempotent=False
        ),
        handler=lambda args: _ingest_graph(args),
    )


def _ingest_graph(args: dict[str, str]) -> dict[str, int]:
    graph = _GRAPH_BY_ROOT.get('__default__')
    if graph is None:
        graph = KnowledgeGraph()
        _GRAPH_BY_ROOT['__default__'] = graph
    relations = ingest_code_relations_to_graph(
        args['path'],
        graph,
        doc_id=args.get('doc_id'),
        source=args.get('source', 'code'),
    )
    return {
        'relations': len(relations),
        'edges': len(graph.all_edges()),
        'documents': len(graph.all_documents()),
    }


_GRAPH_BY_ROOT: dict[str, KnowledgeGraph] = {}

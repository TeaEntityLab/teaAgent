from __future__ import annotations

from teaagent.code_analysis._config import CodeAnalysisConfig
from teaagent.code_analysis._manager import LSPServerManager
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

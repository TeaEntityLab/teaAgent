from __future__ import annotations

from typing import Any, Optional

_OPENAPI_VERSION = '3.1.0'


def generate_openapi_schema(
    registry: Any,
    *,
    title: str = 'TeaAgent Tools API',
    version: str = '1.0.0',
    server_url: Optional[str] = None,
) -> dict[str, Any]:
    paths: dict[str, Any] = {}
    for tool in registry.mcp_metadata():
        name = tool['name']
        description = tool.get('description', '')
        input_schema = dict(tool.get('input_schema') or {})
        output_schema = dict(tool.get('output_schema') or {'type': 'object'})
        annotations = tool.get('annotations', {})

        operation: dict[str, Any] = {
            'summary': description,
            'operationId': name,
            'tags': ['tools'],
            'requestBody': {
                'required': True,
                'content': {
                    'application/json': {
                        'schema': input_schema,
                    }
                },
            },
            'responses': {
                '200': {
                    'description': 'Tool result',
                    'content': {
                        'application/json': {
                            'schema': output_schema,
                        }
                    },
                },
                '400': {'description': 'Invalid input'},
                '403': {'description': 'Tool call blocked by policy'},
            },
        }

        hints = []
        if annotations.get('readOnlyHint'):
            hints.append('read_only')
        if annotations.get('destructiveHint'):
            hints.append('destructive')
        if annotations.get('idempotentHint'):
            hints.append('idempotent')
        if hints:
            operation['x-mcp-annotations'] = hints

        paths[f'/tools/{name}'] = {'post': operation}

    schema: dict[str, Any] = {
        'openapi': _OPENAPI_VERSION,
        'info': {'title': title, 'version': version},
        'paths': paths,
    }
    if server_url:
        schema['servers'] = [{'url': server_url}]
    return schema

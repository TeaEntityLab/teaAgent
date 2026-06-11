from __future__ import annotations

import io
import json
import tempfile
from contextlib import redirect_stdout

from teaagent.openapi import generate_openapi_schema


def _fake_registry(tools: list[dict]) -> object:
    class FakeRegistry:
        def mcp_metadata(self):
            return tools

    return FakeRegistry()


def test_basic_structure() -> None:
    registry = _fake_registry([])
    schema = generate_openapi_schema(registry)
    assert schema['openapi'] == '3.1.0'
    assert 'info' in schema
    assert 'paths' in schema
    assert schema['info']['title'] == 'TeaAgent Tools API'
    assert schema['info']['version'] == '1.0.0'


def test_no_server_when_url_omitted() -> None:
    schema = generate_openapi_schema(_fake_registry([]))
    assert 'servers' not in schema


def test_server_url_embedded() -> None:
    schema = generate_openapi_schema(_fake_registry([]), server_url='https://api.test')
    assert schema['servers'][0]['url'] == 'https://api.test'


def test_tool_becomes_post_path() -> None:
    tools = [
        {
            'name': 'read_file',
            'description': 'Read a file',
            'input_schema': {
                'type': 'object',
                'properties': {'path': {'type': 'string'}},
                'required': ['path'],
            },
            'output_schema': {'type': 'object'},
            'annotations': {
                'readOnlyHint': True,
                'destructiveHint': False,
                'idempotentHint': True,
            },
        }
    ]
    schema = generate_openapi_schema(_fake_registry(tools))
    assert '/tools/read_file' in schema['paths']
    operation = schema['paths']['/tools/read_file']['post']
    assert operation['operationId'] == 'read_file'
    assert operation['summary'] == 'Read a file'
    assert 'requestBody' in operation
    body_schema = operation['requestBody']['content']['application/json']['schema']
    assert body_schema['properties']['path']['type'] == 'string'


def test_mcp_annotations_embedded_on_destructive() -> None:
    tools = [
        {
            'name': 'delete_file',
            'description': '',
            'input_schema': {},
            'output_schema': {},
            'annotations': {
                'readOnlyHint': False,
                'destructiveHint': True,
                'idempotentHint': False,
            },
        }
    ]
    schema = generate_openapi_schema(_fake_registry(tools))
    operation = schema['paths']['/tools/delete_file']['post']
    assert 'x-mcp-annotations' in operation
    assert 'destructive' in operation['x-mcp-annotations']


def test_read_only_tool_has_no_destructive_annotation() -> None:
    tools = [
        {
            'name': 'list_files',
            'description': '',
            'input_schema': {},
            'output_schema': {},
            'annotations': {
                'readOnlyHint': True,
                'destructiveHint': False,
                'idempotentHint': True,
            },
        }
    ]
    schema = generate_openapi_schema(_fake_registry(tools))
    operation = schema['paths']['/tools/list_files']['post']
    hints = operation.get('x-mcp-annotations', [])
    assert 'destructive' not in hints


def test_custom_title_and_version() -> None:
    schema = generate_openapi_schema(
        _fake_registry([]), title='My API', version='2.3.0'
    )
    assert schema['info']['title'] == 'My API'
    assert schema['info']['version'] == '2.3.0'


def test_multiple_tools_produce_multiple_paths() -> None:
    tools = [
        {
            'name': 'alpha',
            'description': '',
            'input_schema': {},
            'output_schema': {},
            'annotations': {},
        },
        {
            'name': 'beta',
            'description': '',
            'input_schema': {},
            'output_schema': {},
            'annotations': {},
        },
    ]
    schema = generate_openapi_schema(_fake_registry(tools))
    assert '/tools/alpha' in schema['paths']
    assert '/tools/beta' in schema['paths']


def test_responses_include_400_and_403() -> None:
    tools = [
        {
            'name': 'do_it',
            'description': '',
            'input_schema': {},
            'output_schema': {},
            'annotations': {},
        },
    ]
    schema = generate_openapi_schema(_fake_registry(tools))
    responses = schema['paths']['/tools/do_it']['post']['responses']
    assert '400' in responses
    assert '403' in responses


def test_workspace_openapi_outputs_valid_schema() -> None:
    from teaagent.cli import main

    with tempfile.TemporaryDirectory() as tmp:
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(['workspace', 'openapi', '--root', tmp])

    assert exit_code == 0
    schema = json.loads(output.getvalue())
    assert schema['openapi'] == '3.1.0'
    assert 'paths' in schema


def test_workspace_openapi_custom_title_and_version() -> None:
    from teaagent.cli import main

    with tempfile.TemporaryDirectory() as tmp:
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(
                [
                    'workspace',
                    'openapi',
                    '--root',
                    tmp,
                    '--title',
                    'My Custom API',
                    '--api-version',
                    '3.0.0',
                    '--server-url',
                    'https://tools.example.com',
                ]
            )

    assert exit_code == 0
    schema = json.loads(output.getvalue())
    assert schema['info']['title'] == 'My Custom API'
    assert schema['info']['version'] == '3.0.0'
    assert schema['servers'][0]['url'] == 'https://tools.example.com'

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout

from teaagent.openapi import generate_openapi_schema


def _fake_registry(tools: list[dict]) -> object:
    class FakeRegistry:
        def mcp_metadata(self):
            return tools

    return FakeRegistry()


class GenerateOpenAPISchemaTests(unittest.TestCase):
    def test_basic_structure(self) -> None:
        registry = _fake_registry([])
        schema = generate_openapi_schema(registry)
        self.assertEqual(schema['openapi'], '3.1.0')
        self.assertIn('info', schema)
        self.assertIn('paths', schema)
        self.assertEqual(schema['info']['title'], 'TeaAgent Tools API')
        self.assertEqual(schema['info']['version'], '1.0.0')

    def test_no_server_when_url_omitted(self) -> None:
        schema = generate_openapi_schema(_fake_registry([]))
        self.assertNotIn('servers', schema)

    def test_server_url_embedded(self) -> None:
        schema = generate_openapi_schema(
            _fake_registry([]), server_url='https://api.test'
        )
        self.assertEqual(schema['servers'][0]['url'], 'https://api.test')

    def test_tool_becomes_post_path(self) -> None:
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
        self.assertIn('/tools/read_file', schema['paths'])
        operation = schema['paths']['/tools/read_file']['post']
        self.assertEqual(operation['operationId'], 'read_file')
        self.assertEqual(operation['summary'], 'Read a file')
        self.assertIn('requestBody', operation)
        body_schema = operation['requestBody']['content']['application/json']['schema']
        self.assertEqual(body_schema['properties']['path']['type'], 'string')

    def test_mcp_annotations_embedded_on_destructive(self) -> None:
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
        self.assertIn('x-mcp-annotations', operation)
        self.assertIn('destructive', operation['x-mcp-annotations'])

    def test_read_only_tool_has_no_destructive_annotation(self) -> None:
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
        self.assertNotIn('destructive', hints)

    def test_custom_title_and_version(self) -> None:
        schema = generate_openapi_schema(
            _fake_registry([]), title='My API', version='2.3.0'
        )
        self.assertEqual(schema['info']['title'], 'My API')
        self.assertEqual(schema['info']['version'], '2.3.0')

    def test_multiple_tools_produce_multiple_paths(self) -> None:
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
        self.assertIn('/tools/alpha', schema['paths'])
        self.assertIn('/tools/beta', schema['paths'])

    def test_responses_include_400_and_403(self) -> None:
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
        self.assertIn('400', responses)
        self.assertIn('403', responses)


class WorkspaceOpenAPICLITests(unittest.TestCase):
    def test_workspace_openapi_outputs_valid_schema(self) -> None:
        from teaagent.cli import main

        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(['workspace', 'openapi', '--root', tmp])

        self.assertEqual(exit_code, 0)
        schema = json.loads(output.getvalue())
        self.assertEqual(schema['openapi'], '3.1.0')
        self.assertIn('paths', schema)

    def test_workspace_openapi_custom_title_and_version(self) -> None:
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

        self.assertEqual(exit_code, 0)
        schema = json.loads(output.getvalue())
        self.assertEqual(schema['info']['title'], 'My Custom API')
        self.assertEqual(schema['info']['version'], '3.0.0')
        self.assertEqual(schema['servers'][0]['url'], 'https://tools.example.com')


if __name__ == '__main__':
    unittest.main()

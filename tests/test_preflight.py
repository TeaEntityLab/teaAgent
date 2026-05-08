from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout

from teaagent import MemoryCatalog, PermissionMode, preflight
from teaagent.cli import main


class PreflightTests(unittest.TestCase):
    def test_preflight_marks_ambiguous_task_not_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = preflight('improve stuff', root=tmp, provider='gpt')

            payload = report.to_dict()
            self.assertFalse(payload['ready'])
            self.assertTrue(payload['clarification']['needs_clarification'])
            self.assertIsNone(payload['routing'])
            self.assertEqual(payload['memories'], [])
            self.assertGreater(payload['tool_count'], 0)

    def test_preflight_includes_routing_and_matching_memories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            MemoryCatalog(tmp).add(
                'review this patch in the test suite for regressions'
            )

            report = preflight(
                'review this patch for regressions in the test suite',
                root=tmp,
                provider='gpt',
                permission_mode=PermissionMode.WORKSPACE_WRITE,
                route=True,
            )
            payload = report.to_dict()

            self.assertTrue(payload['ready'])
            self.assertEqual(payload['routing']['category'], 'review')
            self.assertEqual(payload['model'], 'gpt-4o')
            self.assertEqual(payload['permission_mode'], 'workspace-write')
            self.assertEqual(len(payload['memories']), 1)

    def test_cli_agent_preflight_returns_needs_clarification_exit_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()

            with redirect_stdout(output):
                exit_code = main(
                    ['agent', 'preflight', 'gpt', 'improve stuff', '--root', tmp]
                )

            payload = json.loads(output.getvalue())
            self.assertEqual(exit_code, 2)
            self.assertFalse(payload['ready'])

    def test_cli_agent_preflight_with_route_model_reports_routing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()

            with redirect_stdout(output):
                exit_code = main(
                    [
                        'agent',
                        'preflight',
                        'gpt',
                        'review this patch for regressions in the test suite',
                        '--route-model',
                        '--root',
                        tmp,
                    ]
                )

            payload = json.loads(output.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertEqual(payload['routing']['category'], 'review')
            self.assertEqual(payload['model'], 'gpt-4o')


if __name__ == '__main__':
    unittest.main()

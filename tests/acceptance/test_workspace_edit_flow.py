from __future__ import annotations

import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from conftest import FakeAdapter

from teaagent.cli import main
from teaagent.workspace_tools._helpers import compute_line_hash


class WorkspaceEditFlowAcceptanceTests(unittest.TestCase):
    def test_hash_read_edit_git_test_and_diff_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / 'notes.txt'
            target.write_text('Hello\n', encoding='utf-8')
            subprocess.run(['git', 'init'], cwd=tmp, check=True, capture_output=True)

            line_hash = compute_line_hash(1, 'Hello\n')
            test_command = (
                f'{sys.executable} -c '
                '"from pathlib import Path; '
                "assert Path('notes.txt').read_text(encoding='utf-8') == "
                "'Hello from TeaAgent\\n'\""
            )
            adapter = FakeAdapter(
                [
                    '{"type":"tool","tool_name":"workspace_read_file_hashed","arguments":{"path":"notes.txt"},"call_id":"read-hashed"}',
                    json.dumps(
                        {
                            'type': 'tool',
                            'tool_name': 'workspace_edit_at_hash',
                            'arguments': {
                                'path': 'notes.txt',
                                'line': 1,
                                'hash': line_hash,
                                'old': 'Hello',
                                'new': 'Hello from TeaAgent',
                            },
                            'call_id': 'edit-line-1',
                        }
                    ),
                    '{"type":"tool","tool_name":"workspace_git_status","arguments":{},"call_id":"git-status"}',
                    json.dumps(
                        {
                            'type': 'tool',
                            'tool_name': 'workspace_run_shell_mutate',
                            'arguments': {
                                'command': test_command,
                                'timeout_seconds': 5,
                            },
                            'call_id': 'run-test',
                        }
                    ),
                    '{"type":"tool","tool_name":"workspace_run_shell_inspect","arguments":{"command":"git diff -- notes.txt","timeout_seconds":5},"call_id":"git-diff"}',
                    '{"type":"final","content":"Diff summary: notes.txt line 1 changed from Hello to Hello from TeaAgent; test command passed."}',
                ]
            )

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(
                    [
                        'agent',
                        'run',
                        'gpt',
                        'Safely edit notes.txt and verify the change',
                        '--root',
                        tmp,
                        '--allow-destructive',
                    ],
                    _adapter_factory=lambda _provider, model=None: adapter,
                )
            payload = json.loads(output.getvalue())

            self.assertEqual(exit_code, 0)
            self.assertEqual(
                target.read_text(encoding='utf-8'), 'Hello from TeaAgent\n'
            )
            self.assertEqual(payload['status'], 'completed')
            self.assertIn('Diff summary:', payload['final_answer'])
            self.assertEqual(payload['audit_summary']['destructive_tool_calls'], 2)
            self.assertEqual(
                payload['audit_summary']['tool_names'],
                [
                    'workspace_read_file_hashed',
                    'workspace_edit_at_hash',
                    'workspace_git_status',
                    'workspace_run_shell_mutate',
                    'workspace_run_shell_inspect',
                ],
            )
            self.assertEqual(adapter.outputs, [])


if __name__ == '__main__':
    unittest.main()

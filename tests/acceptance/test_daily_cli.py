from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from conftest import FakeAdapter

from teaagent.cli import main


class DailyCLIAcceptanceTests(unittest.TestCase):
    def test_daily_cli_read_only_run_preflight_and_audit_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'README.md').write_text('hello teaagent', encoding='utf-8')
            adapter = FakeAdapter(
                [
                    '{"type":"tool","tool_name":"workspace_read_file","arguments":{"path":"README.md"},"call_id":"read-1"}',
                    '{"type":"final","content":"repo summarized"}',
                ]
            )

            preflight_out = io.StringIO()
            with redirect_stdout(preflight_out):
                preflight_code = main(
                    [
                        'agent',
                        'preflight',
                        'gpt',
                        'Summarize README.md for onboarding',
                        '--root',
                        tmp,
                        '--permission-mode',
                        'read-only',
                    ]
                )
            preflight_payload = json.loads(preflight_out.getvalue())

            run_out = io.StringIO()
            with (
                patch('teaagent.cli.create_llm_adapter', return_value=adapter),
                redirect_stdout(run_out),
            ):
                run_code = main(
                    [
                        'agent',
                        'run',
                        'gpt',
                        'Summarize README.md for onboarding',
                        '--root',
                        tmp,
                        '--permission-mode',
                        'read-only',
                    ]
                )
            run_payload = json.loads(run_out.getvalue())

            show_out = io.StringIO()
            with redirect_stdout(show_out):
                show_code = main(
                    ['agent', 'show', run_payload['run_id'], '--root', tmp]
                )
            events = json.loads(show_out.getvalue())

            self.assertEqual(preflight_code, 0)
            self.assertTrue(preflight_payload['ready'])
            self.assertEqual(preflight_payload['permission_mode'], 'read-only')
            self.assertEqual(run_code, 0)
            self.assertEqual(run_payload['status'], 'completed')
            self.assertEqual(run_payload['final_answer'], 'repo summarized')
            self.assertEqual(run_payload['audit_summary']['status'], 'completed')
            self.assertEqual(
                run_payload['audit_summary']['tool_names'], ['workspace_read_file']
            )
            self.assertEqual(run_payload['audit_summary']['approval_required'], False)
            self.assertEqual(show_code, 0)
            self.assertIn('run_completed', [event['event_type'] for event in events])

    def test_daily_cli_prompt_approval_resume_is_auditable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first_adapter = FakeAdapter(
                [
                    '{"type":"tool","tool_name":"workspace_write_file","arguments":{"path":"TODO.md","content":"done"},"call_id":"write-1"}'
                ]
            )
            first_out = io.StringIO()
            with (
                patch('teaagent.cli.create_llm_adapter', return_value=first_adapter),
                redirect_stdout(first_out),
            ):
                first_code = main(
                    ['agent', 'run', 'gpt', 'Create TODO.md', '--root', tmp]
                )
            first_payload = json.loads(first_out.getvalue())

            resume_adapter = FakeAdapter(
                [
                    '{"type":"tool","tool_name":"workspace_write_file","arguments":{"path":"TODO.md","content":"done"},"call_id":"write-1"}',
                    '{"type":"final","content":"created todo"}',
                ]
            )
            resume_out = io.StringIO()
            with (
                patch('teaagent.cli.create_llm_adapter', return_value=resume_adapter),
                redirect_stdout(resume_out),
            ):
                resume_code = main(
                    ['agent', 'resume', 'gpt', first_payload['run_id'], '--root', tmp]
                )
            resume_payload = json.loads(resume_out.getvalue())

            self.assertEqual(first_code, 1)
            self.assertEqual(first_payload['status'], 'pending_approval')
            self.assertTrue(first_payload['audit_summary']['approval_required'])
            self.assertEqual(first_payload['approval']['call_id'], 'write-1')
            self.assertEqual(resume_code, 0)
            self.assertEqual(resume_payload['status'], 'completed')
            self.assertEqual(resume_payload['resumed_from'], first_payload['run_id'])
            self.assertEqual(resume_payload['auto_approved_call_id'], 'write-1')
            self.assertEqual(
                resume_payload['audit_summary']['destructive_tool_calls'], 1
            )
            self.assertEqual(
                (Path(tmp) / 'TODO.md').read_text(encoding='utf-8'), 'done'
            )


if __name__ == '__main__':
    unittest.main()

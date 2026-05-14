from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from conftest import FakeAdapter

from teaagent.tui import TeaAgentTUI


class DailyTUIAcceptanceTests(unittest.TestCase):
    def test_daily_tui_chat_memory_progress_and_audit_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'note.txt').write_text('hello', encoding='utf-8')
            output: list[str] = []
            adapter = FakeAdapter(
                [
                    '{"type":"tool","tool_name":"workspace_read_file","arguments":{"path":"note.txt"},"call_id":"read-1"}',
                    '{"type":"final","content":"note summarized"}',
                ]
            )
            tui = TeaAgentTUI(
                root=tmp,
                input_fn=lambda _prompt: 'exit',
                output_fn=output.append,
                adapter_factory=lambda _provider, _model: adapter,
            )

            self.assertTrue(tui.handle_command('chat on'))
            self.assertTrue(
                tui.handle_command(
                    'memory add summarize note.txt Prefer concise summaries'
                )
            )
            self.assertTrue(tui.handle_command('progress on'))
            self.assertTrue(tui.handle_command('ask summarize note.txt'))
            self.assertTrue(tui.handle_command('session show'))

            joined = '\n'.join(output)
            session_payload = json.loads(output[-1])

            self.assertIn('chat: on', joined)
            self.assertIn('progress: on', joined)
            self.assertIn('tool: workspace_read_file', joined)
            self.assertIn('note summarized', output)
            self.assertEqual(len(session_payload['messages']), 2)
            self.assertIn(
                'Prefer concise summaries', adapter.requests[0].messages[0].content
            )

    def test_daily_tui_prompt_approval_is_auditable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output: list[str] = []
            adapter = FakeAdapter(
                [
                    '{"type":"tool","tool_name":"workspace_write_file","arguments":{"path":"TODO.md","content":"done"},"call_id":"write-1"}',
                    '{"type":"final","content":"created todo"}',
                ]
            )
            tui = TeaAgentTUI(
                root=tmp,
                input_fn=lambda _prompt: 'yes',
                output_fn=output.append,
                adapter_factory=lambda _provider, _model: adapter,
            )

            self.assertTrue(tui.handle_command('ask create TODO.md'))
            approval_payload = json.loads(output[1])
            result_payload = json.loads(output[-1])

            self.assertEqual(approval_payload['status'], 'approval_required')
            self.assertEqual(result_payload['status'], 'completed')
            self.assertTrue(result_payload['audit_summary']['approval_required'])
            self.assertEqual(
                result_payload['audit_summary']['destructive_tool_calls'], 1
            )
            self.assertEqual(
                (Path(tmp) / 'TODO.md').read_text(encoding='utf-8'), 'done'
            )


if __name__ == '__main__':
    unittest.main()

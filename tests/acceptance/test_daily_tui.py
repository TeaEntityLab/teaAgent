from __future__ import annotations

import json
import tempfile
from pathlib import Path

from conftest import FakeAdapter

from teaagent.tui import TeaAgentTUI
from test_support import can_bind_loopback


def test_daily_tui_chat_memory_progress_and_audit_summary() -> None:
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

        assert tui.handle_command('chat on')
        assert tui.handle_command(
            'memory add summarize note.txt Prefer concise summaries'
        )
        assert tui.handle_command('progress on')
        assert tui.handle_command('ask summarize note.txt')
        assert tui.handle_command('session show')

        joined = '\n'.join(output)
        session_payload = json.loads(output[-1])

        assert 'chat: on' in joined
        assert 'progress: on' in joined
        assert 'tool: workspace_read_file' in joined
        assert 'note summarized' in output
        assert len(session_payload['messages']) == 2
        assert 'Prefer concise summaries' in adapter.requests[0].messages[0].content


def test_daily_tui_prompt_approval_is_auditable() -> None:
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

        assert tui.handle_command('ask create TODO.md')
        approval_payload = next(
            json.loads(line)
            for line in output
            if line.strip().startswith('{') and 'approval_required' in line
        )
        result_payload = json.loads(output[-1])

        assert approval_payload['status'] == 'approval_required'
        assert result_payload['status'] == 'completed'
        assert result_payload['audit_summary']['approval_required']
        assert result_payload['audit_summary']['destructive_tool_calls'] == 1
        assert (Path(tmp) / 'TODO.md').read_text(encoding='utf-8') == 'done'


def test_daily_tui_command_reports_brief() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / 'README.md').write_text('hello teaagent', encoding='utf-8')
        output: list[str] = []
        tui = TeaAgentTUI(
            root=tmp,
            input_fn=lambda _prompt: 'exit',
            output_fn=output.append,
        )

        assert tui.handle_command('permission read-only')
        assert tui.handle_command('daily summarize README.md')

        payload = json.loads(output[-1])
        if not can_bind_loopback():
            assert 'daily: ready=False' in '\n'.join(output)
            assert not payload['ready']
            return

        assert 'daily: ready=True' in '\n'.join(output)
        assert payload['ready']
        assert payload['permission_mode'] == 'read-only'
        assert 'token_budget' in payload
        assert 'harness_health' in payload

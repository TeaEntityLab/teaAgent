"""AC-NEW-19: Read-only planning mode flow.

As a user, I want a named planning lane that can inspect safely in read-only
mode while blocking destructive actions, so I can plan before editing.

Acceptance criteria:
- Read-only run can inspect files and complete with planning metadata.
- Read-only run blocks workspace writes.
- Read-only run blocks shell mutation.
"""

from __future__ import annotations

import io
import json
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from conftest import FakeAdapter

from teaagent.cli import main


def test_read_only_plan_mode_allows_inspection_and_returns_planning_metadata() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / 'README.md').write_text('hello teaagent', encoding='utf-8')
        adapter = FakeAdapter(
            [
                '{"type":"tool","tool_name":"workspace_read_file","arguments":{"path":"README.md"},"call_id":"read-1"}',
                '{"type":"final","content":"inspection complete"}',
            ]
        )
        output = io.StringIO()
        with (
            patch('teaagent.cli.create_llm_adapter', return_value=adapter),
            redirect_stdout(output),
        ):
            exit_code = main(
                [
                    'agent',
                    'run',
                    'gpt',
                    'Plan how to update README.md without making edits',
                    '--root',
                    tmp,
                    '--permission-mode',
                    'read-only',
                ]
            )
        payload = json.loads(output.getvalue())

        assert exit_code == 0
        assert payload['status'] == 'completed'
        assert payload['permission_mode'] == 'read-only'
        assert payload['run_mode'] == 'planning'
        assert payload['final_answer'] == 'inspection complete'
        assert payload['audit_summary']['tool_names'] == ['workspace_read_file']


def test_read_only_plan_mode_blocks_workspace_write() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        adapter = FakeAdapter(
            [
                '{"type":"tool","tool_name":"workspace_write_file","arguments":{"path":"TODO.md","content":"x"},"call_id":"write-1"}'
            ]
        )
        output = io.StringIO()
        with (
            patch('teaagent.cli.create_llm_adapter', return_value=adapter),
            redirect_stdout(output),
        ):
            exit_code = main(
                [
                    'agent',
                    'run',
                    'gpt',
                    'Plan a change but attempt a write',
                    '--root',
                    tmp,
                    '--permission-mode',
                    'read-only',
                ]
            )
        payload = json.loads(output.getvalue())

        assert exit_code == 1
        assert payload['status'] == 'failed:permission'
        assert payload['permission_mode'] == 'read-only'
        assert payload['run_mode'] == 'planning'
        assert payload['audit_summary']['approval_required'] is False


def test_read_only_plan_mode_blocks_shell_mutation() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        adapter = FakeAdapter(
            [
                '{"type":"tool","tool_name":"workspace_run_shell_mutate","arguments":{"command":"echo plan","timeout_seconds":3},"call_id":"mutate-1"}'
            ]
        )
        output = io.StringIO()
        with (
            patch('teaagent.cli.create_llm_adapter', return_value=adapter),
            redirect_stdout(output),
        ):
            exit_code = main(
                [
                    'agent',
                    'run',
                    'gpt',
                    'Plan a change but attempt shell mutation',
                    '--root',
                    tmp,
                    '--permission-mode',
                    'read-only',
                ]
            )
        payload = json.loads(output.getvalue())

        assert exit_code == 1
        assert payload['status'] == 'failed:permission'
        assert payload['permission_mode'] == 'read-only'
        assert payload['run_mode'] == 'planning'
        assert payload['audit_summary']['approval_required'] is False

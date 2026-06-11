"""Test module for daily CLI workflow integration.

This module tests the daily CLI workflow, which integrates preflight, run, and
show commands for a streamlined daily development experience. The workflow is
designed to be read-only by default and provides comprehensive audit summaries.

Key concepts tested:
- Daily Workflow: Preflight → Run → Show integration
- Read-Only Mode: Default permission mode is read-only for safety
- Preflight Validation: Preflight validates context pack and readiness
- Audit Summary: Run output includes comprehensive audit summary
- Token Budget: Preflight and daily show token budget status
- Resume Flow: Pending approval runs can be resumed with auto-approval

Acceptance Criteria:
- AC1: Daily preflight returns ready status and context pack
- AC2: Daily run completes with audit summary
- AC3: Agent show returns audit events
- AC4: Preflight context pack is read-only when permission-mode is read-only
- AC5: Daily brief reports token budget and harness health
- AC6: Daily brief includes recommendations
- AC7: Prompt approval resume is auditable with auto-approval
- AC8: Resume flow records resumed_from and auto_approved_call_id

Technical Details:
- agent preflight validates context pack and readiness before run
- agent run executes the task with specified permission mode
- agent show returns audit events for a run
- token_budget includes: usage_level, usage_cents, limit_cents
- harness_health checks system readiness
- recent_runs shows recent run history
- Resume auto-approves the pending approval from the original run
- Audit summary includes: status, tool_names, approval_required, destructive_tool_calls

References:
- Daily workflow design: /docs/architecture/daily_workflow.md
- Preflight spec: /docs/specs/preflight.md
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
from test_support import can_bind_loopback


def test_daily_cli_read_only_run_preflight_and_audit_summary() -> None:
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
            show_code = main(['agent', 'show', run_payload['run_id'], '--root', tmp])
        events = json.loads(show_out.getvalue())

        if not can_bind_loopback():
            assert preflight_code == 2
            assert not preflight_payload['ready']
        else:
            assert preflight_code == 0
            assert preflight_payload['ready']
        assert preflight_payload['permission_mode'] == 'read-only'
        assert run_code == 0
        assert run_payload['status'] == 'completed'
        assert run_payload['final_answer'] == 'repo summarized'
        assert run_payload['audit_summary']['status'] == 'completed'
        assert run_payload['audit_summary']['tool_names'] == ['workspace_read_file']
        assert run_payload['audit_summary']['approval_required'] is False
        assert show_code == 0
        assert 'run_completed' in [event['event_type'] for event in events]
        assert 'token_budget' in preflight_payload
        assert preflight_payload['context_pack']['read_only'] is True


def test_daily_cli_brief_is_read_only_and_reports_token_budget() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / 'README.md').write_text('hello teaagent', encoding='utf-8')

        daily_out = io.StringIO()
        with redirect_stdout(daily_out):
            daily_code = main(
                [
                    'agent',
                    'daily',
                    'gpt',
                    'Summarize README.md for onboarding',
                    '--root',
                    tmp,
                    '--permission-mode',
                    'read-only',
                ]
            )
        payload = json.loads(daily_out.getvalue())

        if not can_bind_loopback():
            assert daily_code == 2
            assert not payload['ready']
            return

        assert daily_code == 0
        assert payload['ready']
        assert payload['permission_mode'] == 'read-only'
        assert 'token_budget' in payload
        assert 'harness_health' in payload
        assert payload['recent_runs'] == []
        assert len(payload['recommendations']) >= 1
        assert not (root / 'TODO.md').exists()


def test_daily_cli_prompt_approval_resume_is_auditable() -> None:
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
            first_code = main(['agent', 'run', 'gpt', 'Create TODO.md', '--root', tmp])
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

        assert first_code == 1
        assert first_payload['status'] == 'pending_approval'
        assert first_payload['audit_summary']['approval_required']
        assert first_payload['approval']['call_id'] == 'write-1'
        assert resume_code == 0
        assert resume_payload['status'] == 'completed'
        assert resume_payload['resumed_from'] == first_payload['run_id']
        assert resume_payload['auto_approved_call_id'] == 'write-1'
        assert resume_payload['audit_summary']['destructive_tool_calls'] == 1
        assert (Path(tmp) / 'TODO.md').read_text(encoding='utf-8') == 'done'

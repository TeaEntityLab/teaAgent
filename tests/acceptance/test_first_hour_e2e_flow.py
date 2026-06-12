"""Test module for first-hour end-to-end user flow.

This module tests the complete first-hour user journey, covering the essential
workflow from initial setup through daily operations, planning, editing, testing,
and undo. This is a critical integration test that validates the entire TeaAgent
workflow as a user would experience it.

Key concepts tested:
- Initial Setup: Configuration creation with provider, API key, and permission mode
- Daily Command: Token budget and permission mode validation for daily operations
- Plan Command: Plan artifact generation with read-only safety
- Agent Run: Task execution with permission mode and tool call limits
- Test Evidence: Verification that changes pass local tests (pytest)
- Run Show: Audit trail inspection and run history retrieval
- Undo Operation: Restoration of workspace to pre-run state
- Git Integration: Baseline commits and change tracking

Acceptance Criteria:
- AC1: Setup command creates .teaagent/config.toml with provider and API key
- AC2: Daily command returns token_budget and respects permission_mode
- AC3: Plan command generates artifact under .teaagent/plans/ with read_only=True
- AC4: Agent run completes successfully with workspace-write permission mode
- AC5: Agent run makes actual edits to files (calc.py fix)
- AC6: Local tests (pytest) pass after agent edits
- AC7: Agent show command returns run history with correct run_id
- AC8: Undo command restores workspace to baseline state
- AC9: All commands respect permission_mode flags throughout the flow

Technical Details:
- Uses subprocess for git operations (init, add, commit)
- Uses FakeAdapter for mocking LLM responses in tests
- Tests both read-only and workspace-write permission modes
- Validates JSON output from CLI commands
- Checks file content before and after operations
- Requires loopback socket binding for plan command (skipped if unavailable)
- Uses can_bind_loopback() to detect socket binding restrictions

References:
- First-hour UX design: /docs/architecture/first_hour_ux.md
- CLI workflow spec: /docs/specs/cli_workflow.md
- Undo operation design: /docs/architecture/undo_operation.md
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from conftest import FakeAdapter

from teaagent.cli import main
from teaagent.plan import load_plan_contract
from test_support import can_bind_loopback

_GIT_ENV = {
    'GIT_AUTHOR_NAME': 'TeaAgent Acceptance',
    'GIT_AUTHOR_EMAIL': 'teaagent@acceptance.test',
    'GIT_COMMITTER_NAME': 'TeaAgent Acceptance',
    'GIT_COMMITTER_EMAIL': 'teaagent@acceptance.test',
}


def test_first_hour_setup_daily_plan_edit_undo(tmp_path: Path) -> None:
    calc = tmp_path / 'calc.py'
    test_file = tmp_path / 'test_calc.py'
    calc.write_text('def add(a, b):\n    return a - b\n', encoding='utf-8')
    test_file.write_text(
        'from calc import add\n\ndef test_add():\n    assert add(1, 2) == 3\n',
        encoding='utf-8',
    )
    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ['git', 'add', 'calc.py', 'test_calc.py'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'commit', '-m', 'baseline'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        env={**os.environ, **_GIT_ENV},
    )

    with redirect_stdout(io.StringIO()):
        setup_code = main(
            [
                'setup',
                '--root',
                str(tmp_path),
                '--provider',
                'gpt',
                '--api-key',
                'sk-first-hour',
                '--permission-mode',
                'read-only',
            ]
        )
    assert setup_code == 0
    assert (tmp_path / '.teaagent' / 'config.toml').is_file()

    daily_out = io.StringIO()
    with redirect_stdout(daily_out):
        daily_code = main(
            [
                'agent',
                'daily',
                'gpt',
                'plan calc fix for first hour',
                '--root',
                str(tmp_path),
                '--permission-mode',
                'read-only',
            ]
        )
    daily_payload = json.loads(daily_out.getvalue())
    assert daily_code in (0, 2)
    assert daily_payload['permission_mode'] == 'read-only'
    assert 'token_budget' in daily_payload

    plan_out = io.StringIO()
    with redirect_stdout(plan_out):
        plan_code = main(
            [
                'agent',
                'plan',
                'gpt',
                'Plan fix for calc.py without editing yet',
                '--root',
                str(tmp_path),
                '--permission-mode',
                'read-only',
            ]
        )
    plan_payload = json.loads(plan_out.getvalue())
    if not can_bind_loopback():
        assert plan_code == 2
        assert plan_payload['ready'] is False
        return

    assert plan_code == 0
    # With --permission-mode read-only, context_pack.read_only should be True
    assert plan_payload['context_pack']['read_only'] is True

    adapter = FakeAdapter(
        [
            json.dumps(
                {
                    'type': 'tool',
                    'tool_name': 'workspace_write_file',
                    'arguments': {
                        'path': 'calc.py',
                        'content': 'def add(a, b):\n    return a + b\n',
                    },
                    'call_id': 'fix-calc',
                }
            ),
            json.dumps(
                {
                    'type': 'tool',
                    'tool_name': 'workspace_run_shell_inspect',
                    'arguments': {'command': "rg 'return a \\+ b' calc.py"},
                    'call_id': 'verify-calc',
                }
            ),
            '{"type":"final","content":"calc fixed; rerun pytest locally to verify"}',
        ]
    )
    plan_artifact = Path(plan_payload['plan_artifact'])
    plan_contract = load_plan_contract(plan_artifact, root=tmp_path)

    # Compute digest for the write approval
    from teaagent.policy import compute_scoped_payload_digest

    write_args = {'path': 'calc.py', 'content': 'def add(a, b):\n    return a + b\n'}
    write_digest = compute_scoped_payload_digest('workspace_write_file', write_args)

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
                'Fix calc.py so pytest passes',
                '--root',
                str(tmp_path),
                '--permission-mode',
                'prompt',
                '--from-plan',
                str(plan_artifact),
                '--allow-external-plan',
                '--require-plan',
                '--git-sandbox-auto-stash',
                '--approve-scoped',
                f'workspace_write_file:{write_digest}',
                '--max-iterations',
                '8',
                '--max-tool-calls',
                '8',
            ]
        )
    run_payload = json.loads(run_out.getvalue())
    assert run_code == 0
    assert run_payload['status'] == 'completed'
    assert run_payload['plan_contract']['content_hash'] == plan_contract.content_hash
    assert run_payload['plan_contract']['task'] == plan_contract.task
    assert run_payload['run_evidence']['commands_run']
    assert run_payload['run_evidence']['approvals']
    assert 'a + b' in calc.read_text(encoding='utf-8')

    pytest_result = subprocess.run(
        [sys.executable, '-m', 'pytest', '-q', '-s'],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert pytest_result.returncode == 0

    show_out = io.StringIO()
    with redirect_stdout(show_out):
        show_code = main(
            [
                'agent',
                'show',
                run_payload['run_id'],
                '--root',
                str(tmp_path),
            ]
        )
    assert show_code == 0
    show_payload = json.loads(show_out.getvalue())
    assert isinstance(show_payload, list)
    assert any(event.get('run_id') == run_payload['run_id'] for event in show_payload)

    undo_out = io.StringIO()
    with redirect_stdout(undo_out):
        undo_code = main(
            ['agent', 'undo', run_payload['run_id'], '--root', str(tmp_path)]
        )
    undo_payload = json.loads(undo_out.getvalue())
    assert undo_code == 0
    assert undo_payload['status'] == 'restored'
    assert 'a - b' in calc.read_text(encoding='utf-8')

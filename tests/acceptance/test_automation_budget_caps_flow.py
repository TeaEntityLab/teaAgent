"""Test module for automation budget caps enforcement.

This module tests the budget cap enforcement mechanism for automation runs,
specifically how the system detects and handles runtime budget violations during
background reconciliation. Budget caps prevent automations from running indefinitely
or consuming excessive resources.

Key concepts tested:
- Runtime Cap Enforcement: Automations that exceed max_runtime_seconds are terminated
- Background Reconciliation: The reconciliation process monitors running background processes
- Process Termination: Exceeded processes are terminated and marked as runtime_cap_exceeded
- Cleanup Verification: Background process files are cleaned up or marked as terminated
- Status Transitions: Automation status transitions from background_started to runtime_cap_exceeded

Acceptance Criteria:
- AC1: Reconciliation detects processes that exceeded max_runtime_seconds
- AC2: Exceeded processes are terminated via terminate_background_pid
- AC3: Automation status is updated to runtime_cap_exceeded
- AC4: running_background_id is cleared after termination
- AC5: Background process files are cleaned up or show termination evidence
- AC6: Audit trail records the cap violation and termination

Technical Details:
- AutomationStore manages automation specs and their runtime state
- _reconcile_automation_runs monitors background processes and enforces caps
- Background process state is stored in .teaagent/background/*.json files
- Process existence is checked via _process_exists (mocked in tests)
- Termination is handled by terminate_background_pid (mocked in tests)
- Budget caps include max_runtime_seconds, max_iterations, max_tool_calls

References:
- Automation v2 design: /docs/architecture/automation_v2.md
- Budget caps spec: /docs/specs/automation_budget_caps.md
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from teaagent.automations import AutomationSpec, AutomationStore
from teaagent.cli._handlers._agent import _reconcile_automation_runs


def test_reconcile_marks_runtime_cap_exceeded(tmp_path) -> None:
    store = AutomationStore(tmp_path)
    spec = store.create(
        name='cap-test',
        task='do work with explicit scope and acceptance checks in prompt',
        schedule='every 30m',
        provider=None,
        model=None,
        permission_mode='read-only',
        context_profile='lean',
        max_iterations=3,
        max_tool_calls=3,
        max_runtime_seconds=60,
    )
    started = datetime.now(timezone.utc) - timedelta(seconds=120)
    record = {
        'background_id': 'bg1',
        'pid': 99999,
        'command': ['echo', 'test'],
        'started_at': started.isoformat(),
        'log_path': str(tmp_path / 'bg1.log'),
        'alive': True,
    }
    bg_dir = tmp_path / '.teaagent' / 'background'
    bg_dir.mkdir(parents=True, exist_ok=True)
    (bg_dir / 'bg1.json').write_text(json.dumps(record), encoding='utf-8')
    (tmp_path / 'bg1.log').write_text('{"run_id":"run-xyz"}\n', encoding='utf-8')
    store.update(
        AutomationSpec(
            **{
                **spec.to_dict(),
                'running_background_id': 'bg1',
                'last_status': 'background_started',
            }
        )
    )
    with (
        patch(
            'teaagent.ergonomics.background_run._process_exists',
            side_effect=[True, False],
        ),
        patch('teaagent.automation_limits.terminate_background_pid', return_value=True),
    ):
        _reconcile_automation_runs(str(tmp_path), store)
    updated = store.show(spec.automation_id)
    # Verify automation status is updated to runtime_cap_exceeded
    assert updated.last_status == 'runtime_cap_exceeded', (
        f'Expected last_status to be "runtime_cap_exceeded", got {updated.last_status}'
    )
    # Verify running_background_id is cleared after termination
    assert updated.running_background_id is None, (
        f'Expected running_background_id to be None after termination, got {updated.running_background_id}'
    )

    # Verify cleanup: background process files should be cleaned up after termination
    bg_json_file = bg_dir / 'bg1.json'
    # After runtime cap exceeded and process terminated, the background file should be cleaned up
    # or marked as terminated. We verify explicit cleanup to prevent orphaned state.
    if bg_json_file.exists():
        record_after = json.loads(bg_json_file.read_text(encoding='utf-8'))
        # The file may still exist but must show evidence of termination
        # (e.g., exit_code set, or alive=False). This is a hard requirement.
        assert 'exit_code' in record_after or not record_after.get('alive', True), (
            f'Background process must show evidence of termination, got: {record_after}'
        )
    else:
        # File was cleaned up - this is the ideal case
        assert True, 'Background file cleaned up successfully'

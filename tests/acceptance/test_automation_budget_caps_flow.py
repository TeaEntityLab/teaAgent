"""Automation v2 budget fields are enforced during background reconciliation."""

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
    assert updated.last_status == 'runtime_cap_exceeded'
    assert updated.running_background_id is None

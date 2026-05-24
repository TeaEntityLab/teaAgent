from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from teaagent.automation_limits import (
    background_runtime_seconds,
    cost_cap_exceeded,
    enforce_runtime_cap,
)
from teaagent.automations import AutomationSpec


def test_background_runtime_seconds_parses_iso_timestamp() -> None:
    started = datetime.now(timezone.utc) - timedelta(seconds=30)
    elapsed = background_runtime_seconds({'started_at': started.isoformat()})
    assert elapsed is not None
    assert 25 <= elapsed <= 35


def test_enforce_runtime_cap_terminates_when_over_limit() -> None:
    started = datetime.now(timezone.utc) - timedelta(seconds=120)
    background = {
        'alive': True,
        'pid': 4242,
        'started_at': started.isoformat(),
    }
    with patch(
        'teaagent.automation_limits.terminate_background_pid', return_value=True
    ) as kill:
        capped = enforce_runtime_cap(background, max_runtime_seconds=60)
    assert capped is True
    kill.assert_called_once_with(4242)


def test_cost_cap_exceeded_compares_run_estimate() -> None:
    spec = AutomationSpec(
        automation_id='a1',
        name='n',
        task='t',
        schedule='every 30m',
        max_cost_cents=10,
    )
    with patch(
        'teaagent.automation_limits.automation_run_cost_cents',
        return_value=25.0,
    ):
        assert cost_cap_exceeded('.', spec, run_id='run-1') is True

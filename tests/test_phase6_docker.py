from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from teaagent.docker_sandbox import DockerSandbox
from teaagent.resource_monitor import ResourceType, ResourceUsage, ResourceViolation


@dataclass
class _Completed:
    returncode: int
    stdout: str = ''
    stderr: str = ''


def test_preflight_failure_falls_back_and_emits_audit() -> None:
    logger = MagicMock()
    with patch(
        'teaagent.docker_sandbox.subprocess.run',
        return_value=_Completed(returncode=1, stderr='docker daemon unavailable'),
    ):
        sandbox = DockerSandbox(audit_logger=logger, run_id='run-1')
        result = sandbox.start()

    assert result.status == 'fallback'
    assert result.fallback == 'wasm'
    assert logger.record.call_count == 2
    assert logger.record.call_args_list[0][0][0] == 'docker_preflight_failed'
    assert logger.record.call_args_list[1][0][0] == 'sandbox_fallback_to_wasm'


def test_resource_violation_aborts_container() -> None:
    logger = MagicMock()
    calls = iter(
        [
            _Completed(returncode=0, stdout='container-1\n'),  # docker run
            _Completed(returncode=0, stdout='ok\n'),  # docker exec
            _Completed(returncode=0, stdout='killed\n'),  # docker kill
        ]
    )
    fake_usage = ResourceUsage(
        timestamp=datetime.now(timezone.utc),
        cpu_percent=300.0,
        memory_mb=2048.0,
        cpu_limit_cores=1.0,
        memory_limit_mb=512.0,
    )
    fake_violation = ResourceViolation(
        resource_type=ResourceType.CPU,
        current_value=300.0,
        limit=100.0,
        timestamp=datetime.now(timezone.utc),
        severity='critical',
    )

    with (
        patch(
            'teaagent.docker_sandbox.subprocess.run',
            side_effect=lambda *a, **k: next(calls),
        ),
        patch(
            'teaagent.docker_sandbox.DockerSandbox.preflight',
            return_value={'status': 'ok', 'runtime': 'docker'},
        ),
        patch(
            'teaagent.docker_sandbox.ResourceMonitor.get_current_usage',
            return_value=fake_usage,
        ),
        patch(
            'teaagent.docker_sandbox.ResourceMonitor.check_violations',
            return_value=[fake_violation],
        ),
    ):
        sandbox = DockerSandbox(audit_logger=logger, run_id='run-2')
        result = sandbox.execute_code("print('x')")

    assert result.status == 'aborted'
    assert 'resource violation' in result.message
    event_names = [c[0][0] for c in logger.record.call_args_list]
    assert 'resource_violation_detected' in event_names
    assert 'docker_sandbox_aborted' in event_names

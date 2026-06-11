from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from teaagent.managed_runtime import ManagedAgentRunner, ManagedRunResult


class _OkRuntime:
    def run_task(self, task: str, *, context: dict) -> str:
        return f'done:{task}'

    def health_check(self) -> bool:
        return True


class _FailRuntime:
    def run_task(self, task: str, *, context: dict) -> str:
        raise RuntimeError('runtime exploded')

    def health_check(self) -> bool:
        return False


class _ContextCapture:
    def __init__(self) -> None:
        self.received: list[dict] = []

    def run_task(self, task: str, *, context: dict) -> str:
        self.received.append(context)
        return 'ok'

    def health_check(self) -> bool:
        return True


def _logger() -> MagicMock:
    m = MagicMock()
    m.record = MagicMock()
    return m


def test_started_and_completed_events_emitted() -> None:
    log = _logger()
    runner = ManagedAgentRunner(_OkRuntime(), runtime_name='ok')
    runner.run('my task', audit_logger=log, run_id='run-1')
    event_types = [c[0][0] for c in log.record.call_args_list]
    assert 'managed_task_started' in event_types
    assert 'managed_task_completed' in event_types


def test_started_event_contains_task() -> None:
    log = _logger()
    ManagedAgentRunner(_OkRuntime()).run(
        'important task', audit_logger=log, run_id='r1'
    )
    started = [
        c for c in log.record.call_args_list if c[0][0] == 'managed_task_started'
    ]
    assert len(started) == 1
    assert started[0][1]['task'] == 'important task'


def test_completed_event_contains_output_length() -> None:
    log = _logger()
    ManagedAgentRunner(_OkRuntime()).run('task', audit_logger=log)
    completed = [
        c for c in log.record.call_args_list if c[0][0] == 'managed_task_completed'
    ]
    assert len(completed) == 1
    assert 'output_length' in completed[0][1]


def test_failed_event_emitted_on_exception() -> None:
    log = _logger()
    runner = ManagedAgentRunner(_FailRuntime(), runtime_name='fail')
    with pytest.raises(RuntimeError):
        runner.run('bad task', audit_logger=log, run_id='r2')
    event_types = [c[0][0] for c in log.record.call_args_list]
    assert 'managed_task_failed' in event_types
    assert 'managed_task_completed' not in event_types


def test_failed_event_contains_error() -> None:
    log = _logger()
    with pytest.raises(RuntimeError):
        ManagedAgentRunner(_FailRuntime()).run('x', audit_logger=log)
    failed = [c for c in log.record.call_args_list if c[0][0] == 'managed_task_failed']
    assert 'error' in failed[0][1]
    assert 'exploded' in failed[0][1]['error']


def test_no_audit_without_logger() -> None:
    log = _logger()
    result = ManagedAgentRunner(_OkRuntime()).run('task')
    log.record.assert_not_called()
    # Verify that the task still completed without audit
    assert result.output == 'done:task'


def test_run_id_propagated_to_events() -> None:
    log = _logger()
    ManagedAgentRunner(_OkRuntime()).run('task', audit_logger=log, run_id='xyz-123')
    for call in log.record.call_args_list:
        assert call[0][1] == 'xyz-123'


def test_runtime_name_in_audit_events() -> None:
    log = _logger()
    ManagedAgentRunner(_OkRuntime(), runtime_name='my-runtime').run(
        'task', audit_logger=log
    )
    for call in log.record.call_args_list:
        assert call[1]['runtime'] == 'my-runtime'


def test_result_still_returned_when_logger_present() -> None:
    log = _logger()
    result = ManagedAgentRunner(_OkRuntime()).run('hi', audit_logger=log)
    assert isinstance(result, ManagedRunResult)
    assert result.output == 'done:hi'


def test_exception_still_raised_when_logger_present() -> None:
    log = _logger()
    with pytest.raises(RuntimeError) as cm:
        ManagedAgentRunner(_FailRuntime()).run('x', audit_logger=log)
    # Verify that the error message is preserved
    assert 'exploded' in str(cm.value)
    # Verify that audit events were still recorded
    assert len(log.record.call_args_list) > 0


def test_tools_forwarded_in_context() -> None:
    cap = _ContextCapture()
    runner = ManagedAgentRunner(cap)
    tools = [{'name': 'file_read', 'description': 'Reads a file'}]
    runner.run('task', context={'tools': tools})
    assert cap.received[0]['tools'] == tools


def test_empty_context_passed_as_dict() -> None:
    cap = _ContextCapture()
    ManagedAgentRunner(cap).run('task')
    assert isinstance(cap.received[0], dict)


def test_context_merged_correctly() -> None:
    cap = _ContextCapture()
    ManagedAgentRunner(cap).run('task', context={'key': 'value', 'num': 42})
    assert cap.received[0]['key'] == 'value'
    assert cap.received[0]['num'] == 42

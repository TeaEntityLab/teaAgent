from __future__ import annotations

import unittest
from unittest.mock import MagicMock

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


class ManagedAgentRunnerAuditTests(unittest.TestCase):
    def test_started_and_completed_events_emitted(self) -> None:
        log = _logger()
        runner = ManagedAgentRunner(_OkRuntime(), runtime_name='ok')
        runner.run('my task', audit_logger=log, run_id='run-1')
        event_types = [c[0][0] for c in log.record.call_args_list]
        self.assertIn('managed_task_started', event_types)
        self.assertIn('managed_task_completed', event_types)

    def test_started_event_contains_task(self) -> None:
        log = _logger()
        ManagedAgentRunner(_OkRuntime()).run(
            'important task', audit_logger=log, run_id='r1'
        )
        started = [
            c for c in log.record.call_args_list if c[0][0] == 'managed_task_started'
        ]
        self.assertEqual(len(started), 1)
        self.assertEqual(started[0][1]['task'], 'important task')

    def test_completed_event_contains_output_length(self) -> None:
        log = _logger()
        ManagedAgentRunner(_OkRuntime()).run('task', audit_logger=log)
        completed = [
            c for c in log.record.call_args_list if c[0][0] == 'managed_task_completed'
        ]
        self.assertEqual(len(completed), 1)
        self.assertIn('output_length', completed[0][1])

    def test_failed_event_emitted_on_exception(self) -> None:
        log = _logger()
        runner = ManagedAgentRunner(_FailRuntime(), runtime_name='fail')
        with self.assertRaises(RuntimeError):
            runner.run('bad task', audit_logger=log, run_id='r2')
        event_types = [c[0][0] for c in log.record.call_args_list]
        self.assertIn('managed_task_failed', event_types)
        self.assertNotIn('managed_task_completed', event_types)

    def test_failed_event_contains_error(self) -> None:
        log = _logger()
        with self.assertRaises(RuntimeError):
            ManagedAgentRunner(_FailRuntime()).run('x', audit_logger=log)
        failed = [
            c for c in log.record.call_args_list if c[0][0] == 'managed_task_failed'
        ]
        self.assertIn('error', failed[0][1])
        self.assertIn('exploded', failed[0][1]['error'])

    def test_no_audit_without_logger(self) -> None:
        log = _logger()
        ManagedAgentRunner(_OkRuntime()).run('task')
        log.record.assert_not_called()

    def test_run_id_propagated_to_events(self) -> None:
        log = _logger()
        ManagedAgentRunner(_OkRuntime()).run('task', audit_logger=log, run_id='xyz-123')
        for call in log.record.call_args_list:
            self.assertEqual(call[0][1], 'xyz-123')

    def test_runtime_name_in_audit_events(self) -> None:
        log = _logger()
        ManagedAgentRunner(_OkRuntime(), runtime_name='my-runtime').run(
            'task', audit_logger=log
        )
        for call in log.record.call_args_list:
            self.assertEqual(call[1]['runtime'], 'my-runtime')

    def test_result_still_returned_when_logger_present(self) -> None:
        log = _logger()
        result = ManagedAgentRunner(_OkRuntime()).run('hi', audit_logger=log)
        self.assertIsInstance(result, ManagedRunResult)
        self.assertEqual(result.output, 'done:hi')

    def test_exception_still_raised_when_logger_present(self) -> None:
        log = _logger()
        with self.assertRaises(RuntimeError):
            ManagedAgentRunner(_FailRuntime()).run('x', audit_logger=log)


class ManagedRuntimeToolContextTests(unittest.TestCase):
    def test_tools_forwarded_in_context(self) -> None:
        cap = _ContextCapture()
        runner = ManagedAgentRunner(cap)
        tools = [{'name': 'file_read', 'description': 'Reads a file'}]
        runner.run('task', context={'tools': tools})
        self.assertEqual(cap.received[0]['tools'], tools)

    def test_empty_context_passed_as_dict(self) -> None:
        cap = _ContextCapture()
        ManagedAgentRunner(cap).run('task')
        self.assertIsInstance(cap.received[0], dict)

    def test_context_merged_correctly(self) -> None:
        cap = _ContextCapture()
        ManagedAgentRunner(cap).run('task', context={'key': 'value', 'num': 42})
        self.assertEqual(cap.received[0]['key'], 'value')
        self.assertEqual(cap.received[0]['num'], 42)


if __name__ == '__main__':
    unittest.main()

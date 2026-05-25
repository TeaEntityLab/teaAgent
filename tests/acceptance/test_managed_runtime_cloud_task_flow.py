"""Stub cloud managed runtime: health, run, failure audit, artifact metadata."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from teaagent.audit import AuditLogger
from teaagent.managed_runtime import ManagedAgentRunner


class _CloudTaskStub:
    def __init__(self) -> None:
        self.cancelled = False
        self.tasks: list[str] = []

    def run_task(self, task: str, *, context: dict[str, Any]) -> str:
        self.tasks.append(task)
        if self.cancelled:
            raise RuntimeError('task cancelled')
        return json.dumps(
            {
                'status': 'completed',
                'artifact': 'summary.txt',
                'log': f'tools={len(context.get("tools", []))}',
            }
        )

    def health_check(self) -> bool:
        return True

    def poll(self) -> dict[str, str]:
        return {'status': 'completed' if self.tasks else 'idle'}

    def cancel(self) -> dict[str, bool]:
        self.cancelled = True
        return {'cancelled': True}


class ManagedRuntimeCloudTaskFlowTests(unittest.TestCase):
    def test_cloud_stub_run_poll_cancel_and_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            audit_path = Path(tmp) / 'cloud-run.jsonl'
            audit = AuditLogger(audit_path)
            stub = _CloudTaskStub()
            runner = ManagedAgentRunner(stub, runtime_name='cloud-stub')
            self.assertTrue(runner.healthy())
            result = runner.run(
                'summarize workspace',
                context={'request_id': 'cloud-1', 'tools': [{'name': 'read'}]},
                audit_logger=audit,
                run_id='cloud-run-1',
            )
            self.assertEqual(stub.poll()['status'], 'completed')
            payload = json.loads(result.output)
            self.assertEqual(payload['status'], 'completed')
            self.assertEqual(payload['artifact'], 'summary.txt')
            self.assertTrue(stub.cancel()['cancelled'])

            events = [
                json.loads(line)
                for line in audit_path.read_text(encoding='utf-8').splitlines()
                if line.strip()
            ]
            self.assertEqual(
                [event['event_type'] for event in events],
                ['managed_task_started', 'managed_task_completed'],
            )

    def test_cloud_stub_failure_records_managed_task_failed(self) -> None:
        class _FailStub(_CloudTaskStub):
            def run_task(self, task: str, *, context: dict[str, Any]) -> str:
                raise RuntimeError('cloud backend unavailable')

        with tempfile.TemporaryDirectory() as tmp:
            audit_path = Path(tmp) / 'cloud-fail.jsonl'
            audit = AuditLogger(audit_path)
            runner = ManagedAgentRunner(_FailStub(), runtime_name='cloud-stub')
            with self.assertRaises(RuntimeError):
                runner.run(
                    'fail task',
                    context={},
                    audit_logger=audit,
                    run_id='cloud-fail-1',
                )
            events = [
                json.loads(line)
                for line in audit_path.read_text(encoding='utf-8').splitlines()
            ]
            self.assertEqual(events[-1]['event_type'], 'managed_task_failed')


if __name__ == '__main__':
    unittest.main()

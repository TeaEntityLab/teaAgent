"""Stub cloud managed runtime: health, run, failure audit, artifact metadata."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest

from teaagent.managed_runtime import ManagedAgentRunner, managed_runtime_capabilities
from teaagent.types import AuditLogger


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


def test_managed_runtime_capabilities_are_explicit_about_optional_sdks() -> None:
    capabilities = managed_runtime_capabilities()
    assert len(capabilities) >= 4
    for capability in capabilities:
        assert capability['status'] in {'available', 'missing_sdk'}
        assert 'pip install' in capability['install_hint']
        assert capability['experimental']


def test_cloud_stub_run_poll_cancel_and_audit() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        audit_path = Path(tmp) / 'cloud-run.jsonl'
        audit = AuditLogger(audit_path)
        stub = _CloudTaskStub()
        runner = ManagedAgentRunner(stub, runtime_name='cloud-stub')
        assert runner.healthy()
        result = runner.run(
            'summarize workspace',
            context={'request_id': 'cloud-1', 'tools': [{'name': 'read'}]},
            audit_logger=audit,
            run_id='cloud-run-1',
        )
        assert stub.poll()['status'] == 'completed'
        payload = json.loads(result.output)
        assert payload['status'] == 'completed'
        assert payload['artifact'] == 'summary.txt'
        assert stub.cancel()['cancelled']

        events = [
            json.loads(line)
            for line in audit_path.read_text(encoding='utf-8').splitlines()
            if line.strip()
        ]
        assert [event['event_type'] for event in events] == [
            'managed_task_started',
            'managed_task_completed',
        ]


def test_cloud_stub_failure_records_managed_task_failed() -> None:
    class _FailStub(_CloudTaskStub):
        def run_task(self, task: str, *, context: dict[str, Any]) -> str:
            raise RuntimeError('cloud backend unavailable')

    with tempfile.TemporaryDirectory() as tmp:
        audit_path = Path(tmp) / 'cloud-fail.jsonl'
        audit = AuditLogger(audit_path)
        runner = ManagedAgentRunner(_FailStub(), runtime_name='cloud-stub')
        with pytest.raises(RuntimeError):
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
        assert events[-1]['event_type'] == 'managed_task_failed'

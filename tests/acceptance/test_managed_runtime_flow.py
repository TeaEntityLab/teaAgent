from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from teaagent.audit import AuditLogger
from teaagent.managed_runtime import ManagedAgentRunner, managed_runtime_context
from teaagent.tools import ToolAnnotations, ToolRegistry


class _CapturingManagedRuntime:
    def __init__(self) -> None:
        self.received_task = ''
        self.received_context: dict = {}

    def run_task(self, task: str, *, context: dict) -> str:
        self.received_task = task
        self.received_context = context
        return f'managed:{len(context["tools"])}'

    def health_check(self) -> bool:
        return True


class ManagedRuntimeFlowAcceptanceTests(unittest.TestCase):
    def test_managed_runtime_receives_tool_context_and_persists_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            audit_path = Path(tmp) / 'managed-run.jsonl'
            audit = AuditLogger(audit_path)
            registry = ToolRegistry()
            registry.register(
                name='workspace_read_file',
                description='Read a workspace file',
                input_schema={'type': 'object'},
                output_schema={'type': 'object'},
                annotations=ToolAnnotations(read_only=True),
                handler=lambda _args: {'content': 'ok'},
            )
            runtime = _CapturingManagedRuntime()
            runner = ManagedAgentRunner(runtime, runtime_name='acceptance-runtime')

            context = managed_runtime_context(
                registry, workspace_root=tmp, extra={'request_id': 'req-1'}
            )
            result = runner.run(
                'summarize workspace',
                context=context,
                audit_logger=audit,
                run_id='managed-1',
            )
            events = [
                json.loads(line)
                for line in audit_path.read_text(encoding='utf-8').splitlines()
            ]

            self.assertEqual(result.output, 'managed:1')
            self.assertEqual(result.runtime, 'acceptance-runtime')
            self.assertEqual(result.metadata['run_id'], 'managed-1')
            self.assertEqual(result.metadata['tool_count'], 1)
            self.assertIn('tools', result.metadata['context_keys'])
            self.assertEqual(runtime.received_task, 'summarize workspace')
            self.assertEqual(runtime.received_context['request_id'], 'req-1')
            self.assertEqual(runtime.received_context['workspace_root'], tmp)
            self.assertEqual(
                runtime.received_context['tools'][0]['name'], 'workspace_read_file'
            )
            self.assertEqual(
                [event['event_type'] for event in events],
                ['managed_task_started', 'managed_task_completed'],
            )
            self.assertEqual(events[0]['payload']['tool_count'], 1)
            self.assertEqual(events[1]['payload']['output_length'], len('managed:1'))


if __name__ == '__main__':
    unittest.main()

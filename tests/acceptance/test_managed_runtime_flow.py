from __future__ import annotations

import json
import tempfile
from pathlib import Path

from teaagent.managed_runtime import ManagedAgentRunner, managed_runtime_context
from teaagent.types import AuditLogger, ToolAnnotations, ToolRegistry


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


def test_managed_runtime_receives_tool_context_and_persists_audit() -> None:
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

        assert result.output == 'managed:1'
        assert result.runtime == 'acceptance-runtime'
        assert result.metadata['run_id'] == 'managed-1'
        assert result.metadata['tool_count'] == 1
        assert 'tools' in result.metadata['context_keys']
        assert runtime.received_task == 'summarize workspace'
        assert runtime.received_context['request_id'] == 'req-1'
        assert runtime.received_context['workspace_root'] == tmp
        assert runtime.received_context['tools'][0]['name'] == 'workspace_read_file'
        assert [event['event_type'] for event in events] == [
            'managed_task_started',
            'managed_task_completed',
        ]
        assert events[0]['payload']['tool_count'] == 1
        assert events[1]['payload']['output_length'] == len('managed:1')

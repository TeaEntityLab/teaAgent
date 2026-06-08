from __future__ import annotations

import json
import logging

from teaagent.ergonomics.run_summary import summarize_run
from teaagent.policy import ApprovalPolicy
from teaagent.runner import AgentRunner, FinalAnswer, ToolRequest
from teaagent.types import (
    AuditLogger,
    PermissionMode,
    RunBudget,
    ToolAnnotations,
    ToolRegistry,
)


def test_summarize_run_counts_tools_and_files(tmp_path) -> None:
    root = tmp_path
    run_id = 'abc123'
    (root / '.teaagent' / 'undo').mkdir(parents=True)
    (root / '.teaagent' / 'undo' / f'{run_id}.jsonl').write_text(
        '\n'.join(
            [
                json.dumps(
                    {'path': 'a.txt', 'existed_before': True, 'content_b64': 'AA=='}
                ),
                json.dumps(
                    {'path': 'b.txt', 'existed_before': False, 'content_b64': None}
                ),
                json.dumps(
                    {'path': 'a.txt', 'existed_before': True, 'content_b64': 'AA=='}
                ),
            ]
        )
        + '\n',
        encoding='utf-8',
    )
    events = [
        {
            'event_type': 'tool_call_started',
            'payload': {'annotations': {'read_only': True}},
        },
        {
            'event_type': 'tool_call_started',
            'payload': {'annotations': {'read_only': False}},
        },
        {
            'event_type': 'tool_call_started',
            'payload': {'annotations': {'read_only': False}},
        },
    ]
    summary = summarize_run(
        root=root,
        run_id=run_id,
        events=events,
        cost_cents=42.0,
        input_tokens=10,
        output_tokens=5,
        budget_cap_cents=100,
    )
    assert summary['tool_calls_total'] == 3
    assert summary['tool_calls_read'] == 1
    assert summary['tool_calls_write'] == 2
    assert summary['files_changed_count'] == 2
    assert summary['files_changed'] == ['a.txt', 'b.txt']


def test_run_summary_emitted_on_completion(tmp_path, caplog) -> None:
    """AgentRunner emits summary log when show_summary=True."""
    registry = ToolRegistry()
    registry.register(
        name='workspace_read_file',
        description='read a file',
        input_schema={
            'type': 'object',
            'properties': {'path': {'type': 'string'}},
            'required': ['path'],
        },
        output_schema={
            'type': 'object',
            'properties': {'content': {'type': 'string'}},
        },
        annotations=ToolAnnotations(read_only=True),
        handler=lambda _: {'content': 'hello'},
    )
    registry.register(
        name='workspace_write_file',
        description='write a file',
        input_schema={
            'type': 'object',
            'properties': {
                'path': {'type': 'string'},
                'content': {'type': 'string'},
            },
            'required': ['path', 'content'],
        },
        output_schema={
            'type': 'object',
            'properties': {'written': {'type': 'boolean'}},
        },
        annotations=ToolAnnotations(destructive=True),
        handler=lambda _: {'written': True},
    )
    audit = AuditLogger()

    runner = AgentRunner(
        registry=registry,
        audit=audit,
        budget=RunBudget(max_estimated_cost_cents=100),
        approval_policy=ApprovalPolicy(permission_mode=PermissionMode.ALLOW),
        workspace_root=tmp_path,
        show_summary=True,
    )

    call_seq = iter(
        [
            ToolRequest(
                tool_name='workspace_read_file',
                arguments={'path': 'hello.txt'},
                call_id='call-1',
            ),
            ToolRequest(
                tool_name='workspace_write_file',
                arguments={'path': 'hello.txt', 'content': 'world'},
                call_id='call-2',
            ),
            FinalAnswer(content='done'),
        ]
    )

    with caplog.at_level(logging.INFO, logger='teaagent.runner._core'):
        result = runner.run(task='test', decide=lambda _: next(call_seq))

    assert result.status == 'completed'
    assert 'Run summary:' in caplog.text
    assert 'Tools called:' in caplog.text
    assert 'read, 1 write' in caplog.text
    assert 'Files changed:' in caplog.text
    assert 'Cost:' in caplog.text
    assert 'Audit log:' in caplog.text
    assert 'Undo:' in caplog.text


def test_run_summary_suppressed_when_show_summary_false(tmp_path, caplog) -> None:
    """AgentRunner does NOT emit summary when show_summary=False."""
    registry = ToolRegistry()
    registry.register(
        name='workspace_read_file',
        description='read a file',
        input_schema={
            'type': 'object',
            'properties': {'path': {'type': 'string'}},
            'required': ['path'],
        },
        output_schema={
            'type': 'object',
            'properties': {'content': {'type': 'string'}},
        },
        annotations=ToolAnnotations(read_only=True),
        handler=lambda _: {'content': 'hello'},
    )
    audit = AuditLogger()

    runner = AgentRunner(
        registry=registry,
        audit=audit,
        budget=RunBudget(max_estimated_cost_cents=100),
        workspace_root=tmp_path,
        show_summary=False,
    )

    call_seq = iter(
        [
            ToolRequest(
                tool_name='workspace_read_file',
                arguments={'path': 'hello.txt'},
                call_id='call-1',
            ),
            FinalAnswer(content='done'),
        ]
    )

    with caplog.at_level(logging.INFO, logger='teaagent.runner._core'):
        result = runner.run(task='test', decide=lambda _: next(call_seq))

    assert result.status == 'completed'
    assert 'Run summary:' not in caplog.text

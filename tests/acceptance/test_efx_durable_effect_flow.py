"""Acceptance: EFX-001/002/003 local durable-effect guards.

Providerless. These tests exercise the governed runner, approval, and
annotation seams. They do not call live GitHub, browser, or paid providers.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from teaagent.approval.manager import ApprovalManager
from teaagent.audit import AuditLogger
from teaagent.checkpoint import SQLiteCheckpointStore
from teaagent.errors import ToolPermissionError
from teaagent.github_integration import register_github_tools
from teaagent.mcp_tool_adapter import _infer_annotations
from teaagent.policy import (
    ApprovalPolicy,
    PermissionMode,
    compute_scoped_payload_digest,
)
from teaagent.prompt import parse_model_decision
from teaagent.runner import AgentRunner, FinalAnswer, ToolRequest
from teaagent.tools import ToolAnnotations, ToolRegistry


def test_prompt_mode_pauses_github_create_pr_without_calling_handler() -> None:
    registry = ToolRegistry()
    register_github_tools(registry)
    audit = AuditLogger()
    runner = AgentRunner(
        registry=registry,
        audit=audit,
        approval_policy=ApprovalPolicy(permission_mode=PermissionMode.PROMPT),
    )
    request = ToolRequest(
        tool_name='github_create_pr',
        arguments={'repo': 'o/r', 'title': 't', 'head': 'feature'},
        call_id='pr-1',
    )
    with (
        patch.dict('os.environ', {'GITHUB_TOKEN': 'fake-token'}, clear=False),
        patch(
            'teaagent.github_integration._gh_api',
            side_effect=AssertionError('github API must not run before approval'),
        ) as mocked,
    ):
        result = runner.run(task='open a pull request', decide=lambda _: request)
    assert result.status == 'pending_approval'
    assert result.metadata.get('approval', {}).get('call_id') == 'pr-1'
    assert mocked.call_count == 0
    assert any(
        event.event_type == 'tool_call_pending_approval' for event in audit.events
    )
    assert not any(event.event_type == 'tool_call_started' for event in audit.events)
    assert not any(event.event_type == 'tool_call_completed' for event in audit.events)


def test_mcp_read_only_hint_cannot_relax_local_policy() -> None:
    annotations = _infer_annotations(
        {
            'name': 'remote_echo',
            'annotations': {
                'readOnlyHint': True,
                'destructiveHint': False,
                'idempotentHint': True,
            },
        }
    )
    assert annotations.read_only is False
    assert annotations.destructive is True
    assert annotations.idempotent is False
    assert annotations.external_effect is True


def test_one_time_approval_is_payload_bound_and_consumed() -> None:
    first = parse_model_decision(
        '{"type":"tool","tool_name":"github_review_pr",'
        '"arguments":{"repo":"o/r","pr_number":1,"body":"a"}}'
    )
    second = parse_model_decision(
        '{"type":"tool","tool_name":"github_review_pr",'
        '"arguments":{"repo":"o/r","pr_number":1,"body":"b"}}'
    )
    assert isinstance(first, ToolRequest)
    assert isinstance(second, ToolRequest)
    assert first.call_id != second.call_id
    assert compute_scoped_payload_digest('github_review_pr', first.arguments) in (
        first.call_id
    )

    manager = ApprovalManager(permission_mode=PermissionMode.PROMPT)
    manager.approve_once(
        first.call_id,
        tool_name='github_review_pr',
        arguments=first.arguments,
    )
    with pytest.raises(ToolPermissionError):
        manager.assert_allowed(
            tool_name='github_review_pr',
            call_id=first.call_id,
            destructive=True,
            external_effect=True,
            arguments=second.arguments,
        )
    manager.assert_allowed(
        tool_name='github_review_pr',
        call_id=first.call_id,
        destructive=True,
        external_effect=True,
        arguments=first.arguments,
    )
    with pytest.raises(ToolPermissionError):
        manager.assert_allowed(
            tool_name='github_review_pr',
            call_id=first.call_id,
            destructive=True,
            external_effect=True,
            arguments=first.arguments,
        )


def test_unmatched_mutating_start_refuses_blind_reddispatch(tmp_path: Path) -> None:
    marker = tmp_path / 'marker.txt'
    registry = ToolRegistry()

    def handler(args: dict[str, object]) -> dict[str, object]:
        del args
        existing = marker.read_text(encoding='utf-8') if marker.exists() else ''
        marker.write_text(existing + 'x', encoding='utf-8')
        return {'written': True}

    registry.register(
        name='mutate_marker',
        description='Append to a workspace marker.',
        input_schema={'type': 'object', 'properties': {'path': {'type': 'string'}}},
        output_schema={
            'type': 'object',
            'properties': {'written': {'type': 'boolean'}},
        },
        handler=handler,
        annotations=ToolAnnotations(
            read_only=False,
            destructive=True,
            idempotent=False,
            external_effect=True,
        ),
    )
    store = SQLiteCheckpointStore(tmp_path / 'ckpt.sqlite')
    digest = compute_scoped_payload_digest('mutate_marker', {'path': 'marker.txt'})
    extra = {
        'pending_effect': {
            'call_id': 'call-crash',
            'tool_name': 'mutate_marker',
            'payload_digest': digest,
            'idempotent': False,
            'retry_safe': False,
            'outcome': 'OUTCOME_UNKNOWN',
        }
    }
    calls = iter(
        [
            ToolRequest(
                tool_name='mutate_marker',
                arguments={'path': 'marker.txt'},
                call_id='call-crash',
            ),
            FinalAnswer(content='done'),
        ]
    )
    runner = AgentRunner(
        registry=registry,
        audit=AuditLogger(),
        approval_policy=ApprovalPolicy(permission_mode=PermissionMode.ALLOW),
        checkpoint_store=store,
        workspace_root=tmp_path,
    )
    result = runner.run(
        task='mutate',
        run_id='efx-accept',
        decide=lambda _: next(calls),
        initial_context_extra=extra,
    )
    assert result.status == 'completed'
    assert not marker.exists()
    unknown = [
        obs
        for obs in (store.load('efx-accept') or {}).get('observations', [])
        if obs.get('error') == 'OUTCOME_UNKNOWN'
    ]
    assert unknown
    assert unknown[0].get('retry_safe') is False

"""WS5 integration and extension boundary tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from teaagent.errors import ToolPermissionError
from teaagent.integration import (
    AgentService,
    CallbackApprovalStrategy,
    PolicyApprovalStrategy,
    RunSetupRequest,
    normalize_run_event,
    prepare_agent_run,
    storage_bundle_for_workspace,
    validate_plugin_tools,
)
from teaagent.integration.event_stream import RunEventStream
from teaagent.policy import PermissionMode
from teaagent.runner._types import ApprovalRequest
from teaagent.tools import ToolAnnotations, ToolRegistry


def test_prepare_agent_run_builds_shared_objects(tmp_path: Path) -> None:
    prepared = prepare_agent_run(
        RunSetupRequest(root=tmp_path, permission_mode=PermissionMode.READ_ONLY)
    )
    assert prepared.root == tmp_path.resolve()
    assert prepared.registry.list_tools()
    assert prepared.audit is not None
    assert prepared.budget.max_iterations == 10
    assert prepared.approval_policy.permission_mode == PermissionMode.READ_ONLY
    assert prepared.approval_policy.workspace_root == str(tmp_path.resolve())
    assert prepared.approval_policy._approval_manager.workspace_root == str(
        tmp_path.resolve()
    )
    assert prepared.run_id.startswith('pending-')


def test_agent_service_prepare_matches_helper(tmp_path: Path) -> None:
    service = AgentService()
    request = RunSetupRequest(root=tmp_path, max_tool_calls=3)
    prepared = service.prepare(request)
    assert prepared.budget.max_tool_calls == 3


def test_normalize_run_event_is_stable_and_redacted() -> None:
    event = normalize_run_event(
        {
            'event_id': 'evt-1',
            'run_id': 'run-1',
            'event_type': 'tool_call_completed',
            'created_at': '2026-06-06T10:00:00+00:00',
            'payload': {
                'tool_name': 'grep',
                'api_key': 'sk-secret-value-1234567890',
            },
        }
    )
    assert event.classification == 'tool'
    assert event.payload.get('api_key') != 'sk-secret-value-1234567890'
    assert event.to_dict()['event_type'] == 'tool_call_completed'


def test_run_event_stream_replays_to_subscribers() -> None:
    seen: list[str] = []

    class _Collector:
        def on_event(self, event) -> None:
            seen.append(event.event_type)

    stream = RunEventStream()
    stream.subscribe(_Collector())
    stream.replay(
        [
            {'event_type': 'run_started', 'run_id': 'r1', 'payload': {}},
            {'event_type': 'run_completed', 'run_id': 'r1', 'payload': {}},
        ]
    )
    assert seen == ['run_started', 'run_completed']


def test_policy_approval_strategy_blocks_read_only_destructive(tmp_path: Path) -> None:
    prepared = prepare_agent_run(
        RunSetupRequest(root=tmp_path, permission_mode=PermissionMode.READ_ONLY)
    )
    strategy = PolicyApprovalStrategy(prepared.approval_policy)
    with pytest.raises(ToolPermissionError):
        strategy.assert_allowed(
            tool_name='workspace_write_file',
            call_id='call-1',
            destructive=True,
            arguments={'path': 'README.md'},
        )


def test_callback_approval_strategy_uses_handler() -> None:
    def _approve(request: ApprovalRequest) -> bool:
        assert request.tool_name == 'workspace_write_file'
        return True

    strategy = CallbackApprovalStrategy(_approve)
    strategy.assert_allowed(
        tool_name='workspace_write_file',
        call_id='call-1',
        destructive=True,
        arguments={'path': 'README.md'},
    )
    assert strategy.to_handler() is _approve


def test_storage_bundle_exposes_local_adapters(tmp_path: Path) -> None:
    bundle = storage_bundle_for_workspace(tmp_path)
    assert bundle.runs.list_runs(limit=1) == []
    assert bundle.approvals.list_grants() == []
    assert bundle.memory.search('nothing', limit=1) == []


def test_validate_plugin_tools_blocks_invalid_tool() -> None:
    registry = ToolRegistry()
    registry.register(
        name='bad_plugin_tool',
        description='invalid plugin tool',
        input_schema={'type': 'string'},
        output_schema={'type': 'object', 'properties': {'ok': {'type': 'boolean'}}},
        annotations=ToolAnnotations(read_only=True, destructive=True),
        handler=lambda args: {'ok': True},
    )
    report = validate_plugin_tools(registry, tool_names=['bad_plugin_tool'])
    assert report.blocked
    assert report.error_count >= 1


def test_load_plugins_rolls_back_governed_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from teaagent.plugins import load_plugins

    registry = ToolRegistry()

    class _FakeEntryPoint:
        name = 'bad-plugin'

        def load(self):
            def register(reg: ToolRegistry) -> None:
                reg.register(
                    name='bad_plugin_tool',
                    description='invalid plugin tool',
                    input_schema={'type': 'string'},
                    output_schema={
                        'type': 'object',
                        'properties': {'ok': {'type': 'boolean'}},
                    },
                    annotations=ToolAnnotations(read_only=True, destructive=True),
                    handler=lambda args: {'ok': True},
                )

            return register

    monkeypatch.setattr(
        'teaagent.plugins._entry_points',
        lambda group: [_FakeEntryPoint()],
    )
    monkeypatch.setattr('teaagent.plugins._audit_plugin_source', lambda ep: True)

    result = load_plugins(registry)
    assert result.failed == ['bad-plugin']
    assert 'bad_plugin_tool' not in registry.list_tools()

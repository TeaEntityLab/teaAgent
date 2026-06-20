"""ADR-0033 / S-P0-1: auto-mode approval authority and audit event.

Asserts that auto mode no longer escalates allowlisted destructive tools to
``DANGER_FULL_ACCESS`` and instead authorizes them via a payload-scoped
preapproval digest with a dedicated ``tool_call_approved`` audit event.
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from teaagent import (
    AgentRunner,
    ApprovalPolicy,
    AuditLogger,
    FinalAnswer,
    ToolAnnotations,
    ToolRegistry,
    ToolRequest,
)
from teaagent.auto_mode import AutoModeConfig
from teaagent.ergonomics.approval_store import ApprovalPresetStore
from teaagent.policy import compute_scoped_payload_digest
from teaagent.runner._auto_mode_manager import AutoModeManager
from teaagent.types import PermissionMode, ToolPermissionError

INPUT_SCHEMA = {
    'type': 'object',
    'properties': {'value': {'type': 'string'}},
    'required': ['value'],
}
OUTPUT_SCHEMA = {
    'type': 'object',
    'properties': {'value': {'type': 'string'}},
    'required': ['value'],
}

DESTRUCTIVE_TOOL = 'pilot_mutate'
OTHER_DESTRUCTIVE_TOOL = 'pilot_other_mutate'


def _build_registry(
    *, destructive: bool = True, name: str = DESTRUCTIVE_TOOL
) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        name=name,
        description='A destructive pilot tool for auto-mode authority tests.',
        input_schema=INPUT_SCHEMA,
        output_schema=OUTPUT_SCHEMA,
        annotations=ToolAnnotations(
            read_only=not destructive,
            destructive=destructive,
            idempotent=False,
        ),
        handler=lambda args: {'value': args['value']},
    )
    return registry


def _policy_with_store(tmp: str | Path, run_id: str) -> ApprovalPolicy:
    root = Path(tmp) / '.teaagent'
    store = ApprovalPresetStore(root=root)
    return ApprovalPolicy(
        permission_mode=PermissionMode.PROMPT,
        approval_store=store,
        approval_origin_run_id=run_id,
        workspace_root=str(tmp),
        enable_jit_prompt=False,
    )


# ── (a) no DANGER_FULL_ACCESS escalation + (c) audit event ───────────────


def test_auto_mode_does_not_escalate_to_danger_full_access() -> None:
    """Auto mode preserves the parent permission mode (no DANGER_FULL_ACCESS)."""
    with TemporaryDirectory() as tmp:
        run_id = 'run-auto-no-escalate'
        policy = _policy_with_store(tmp, run_id)
        audit = AuditLogger()
        runner = AgentRunner(
            registry=_build_registry(),
            audit=audit,
            approval_policy=policy,
            auto_mode_config=AutoModeConfig(
                enabled=True,
                allowed_tools=frozenset({DESTRUCTIVE_TOOL}),
                max_iterations=5,
                max_tool_calls=5,
            ),
        )
        arguments = {'value': 'delete-me'}

        def decide(context):
            if not context['observations']:
                return ToolRequest(
                    tool_name=DESTRUCTIVE_TOOL,
                    arguments=arguments,
                    call_id='call-1',
                )
            return FinalAnswer(content='done')

        result = runner.run(task='auto destructive', decide=decide, run_id=run_id)

        assert result.status == 'completed', result.error_message
        # The runner's policy must not have been escalated to danger-full-access.
        assert runner.approval_policy.permission_mode is PermissionMode.PROMPT
        assert runner.approval_policy.allow_all_destructive is False
        assert runner.approval_policy.full_access_acknowledged is False


def test_auto_mode_emits_tool_call_approved_audit_event() -> None:
    """A payload-scoped ``tool_call_approved`` event is emitted for auto-mode calls."""
    with TemporaryDirectory() as tmp:
        run_id = 'run-auto-audit'
        policy = _policy_with_store(tmp, run_id)
        audit = AuditLogger()
        runner = AgentRunner(
            registry=_build_registry(),
            audit=audit,
            approval_policy=policy,
            auto_mode_config=AutoModeConfig(
                enabled=True,
                allowed_tools=frozenset({DESTRUCTIVE_TOOL}),
                max_iterations=5,
                max_tool_calls=5,
            ),
        )
        arguments = {'value': 'delete-me'}
        expected_digest = compute_scoped_payload_digest(DESTRUCTIVE_TOOL, arguments)

        def decide(context):
            if not context['observations']:
                return ToolRequest(
                    tool_name=DESTRUCTIVE_TOOL,
                    arguments=arguments,
                    call_id='call-audit',
                )
            return FinalAnswer(content='done')

        result = runner.run(task='auto destructive', decide=decide, run_id=run_id)
        assert result.status == 'completed', result.error_message

        approved_events = [
            e
            for e in audit.events
            if e.event_type == 'tool_call_approved'
            and e.payload.get('tool_name') == DESTRUCTIVE_TOOL
        ]
        assert len(approved_events) == 1, (
            f'expected one tool_call_approved event, got {len(approved_events)}'
        )
        payload = approved_events[0].payload
        assert payload['authority_type'] == 'auto_mode'
        assert payload['scope'] == 'payload_digest'
        assert payload['auto_approved'] is True
        assert payload['argument_digest'] == expected_digest
        assert payload['call_id'] == 'call-audit'


def test_auto_mode_denied_in_pipeline_records_no_false_approval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If a later assert_allowed gate denies the call, auto mode must NOT have
    already written a ``tool_call_approved`` event.

    Regression for the audit-integrity bug where the auto-mode approval event
    was emitted *before* the nine-stage ``assert_allowed`` pipeline ran, so a
    denial elsewhere (path safety, plan contract, JIT) left a false approval in
    the audit trail with no matching denial.
    """
    with TemporaryDirectory() as tmp:
        run_id = 'run-auto-denied'
        policy = _policy_with_store(tmp, run_id)
        audit = AuditLogger()
        runner = AgentRunner(
            registry=_build_registry(),
            audit=audit,
            approval_policy=policy,
            auto_mode_config=AutoModeConfig(
                enabled=True,
                allowed_tools=frozenset({DESTRUCTIVE_TOOL}),
                max_iterations=5,
                max_tool_calls=5,
            ),
        )
        arguments = {'value': 'delete-me'}

        # Simulate a downstream pipeline gate (e.g. workspace-path safety)
        # rejecting the call even though auto mode selected a scoped policy.
        def deny(self: ApprovalPolicy, *args: object, **kwargs: object) -> None:
            raise ToolPermissionError('denied by a later pipeline gate')

        monkeypatch.setattr(ApprovalPolicy, 'assert_allowed', deny)

        def decide(context):
            if not context['observations']:
                return ToolRequest(
                    tool_name=DESTRUCTIVE_TOOL,
                    arguments=arguments,
                    call_id='call-denied',
                )
            return FinalAnswer(content='done')

        result = runner.run(task='auto destructive', decide=decide, run_id=run_id)

        # The call was denied, so the run must not report success.
        assert result.status != 'completed'
        # And crucially: no auto-mode approval event was written.
        approved_events = [
            e
            for e in audit.events
            if e.event_type == 'tool_call_approved'
            and e.payload.get('authority_type') == 'auto_mode'
        ]
        assert approved_events == [], (
            'auto-mode tool_call_approved must not be recorded when the call is '
            f'denied; got {len(approved_events)} false approval(s)'
        )


# ── (b) authority is payload-scoped ──────────────────────────────────────


def test_auto_mode_authority_is_payload_scoped() -> None:
    """A different payload is denied under the auto-mode-scoped policy."""
    with TemporaryDirectory() as tmp:
        run_id = 'run-auto-scope'
        parent = _policy_with_store(tmp, run_id)
        manager = AutoModeManager(
            auto_mode_config=AutoModeConfig(
                enabled=True,
                allowed_tools=frozenset({DESTRUCTIVE_TOOL}),
            )
        )
        approved_args = {'value': 'approved-payload'}
        denied_args = {'value': 'different-payload'}

        approval = manager.get_auto_approve_policy(
            parent_policy=parent,
            tool_name=DESTRUCTIVE_TOOL,
            arguments=approved_args,
            destructive=True,
        )
        assert approval is not None
        scoped_policy, digest = approval

        # The exact approved payload is authorized.
        scoped_policy.assert_allowed(
            tool_name=DESTRUCTIVE_TOOL,
            call_id='call-scope-ok',
            destructive=True,
            arguments=approved_args,
        )

        # A replay with a different payload is denied (no blanket authority).
        with pytest.raises(ToolPermissionError):
            scoped_policy.assert_allowed(
                tool_name=DESTRUCTIVE_TOOL,
                call_id='call-scope-bad',
                destructive=True,
                arguments=denied_args,
            )

        # The injected digest must match only the approved payload.
        assert digest == compute_scoped_payload_digest(DESTRUCTIVE_TOOL, approved_args)
        assert digest != compute_scoped_payload_digest(DESTRUCTIVE_TOOL, denied_args)


def test_auto_mode_disabled_returns_no_policy() -> None:
    """When auto mode is disabled, no auto-approve policy is produced."""
    with TemporaryDirectory() as tmp:
        parent = _policy_with_store(tmp, 'run-disabled')
        manager = AutoModeManager(auto_mode_config=None)
        assert (
            manager.get_auto_approve_policy(
                parent_policy=parent,
                tool_name=DESTRUCTIVE_TOOL,
                arguments={'value': 'x'},
                destructive=True,
            )
            is None
        )


def test_auto_mode_non_destructive_returns_no_policy() -> None:
    """Non-destructive calls are not handled by the auto-mode authority path."""
    with TemporaryDirectory() as tmp:
        parent = _policy_with_store(tmp, 'run-readonly')
        manager = AutoModeManager(
            auto_mode_config=AutoModeConfig(
                enabled=True,
                allowed_tools=frozenset({DESTRUCTIVE_TOOL}),
            )
        )
        assert (
            manager.get_auto_approve_policy(
                parent_policy=parent,
                tool_name=DESTRUCTIVE_TOOL,
                arguments={'value': 'x'},
                destructive=False,
            )
            is None
        )


# ── (d) non-allowlisted destructive calls still require JIT ──────────────


def test_non_allowlisted_destructive_call_requires_approval() -> None:
    """A destructive tool outside the auto-mode allowlist is not auto-approved."""
    with TemporaryDirectory() as tmp:
        run_id = 'run-auto-jit'
        policy = _policy_with_store(tmp, run_id)
        audit = AuditLogger()
        # Registry with a destructive tool that is NOT on the allowlist.
        registry = _build_registry(name=OTHER_DESTRUCTIVE_TOOL)
        runner = AgentRunner(
            registry=registry,
            audit=audit,
            approval_policy=policy,
            auto_mode_config=AutoModeConfig(
                enabled=True,
                allowed_tools=frozenset({DESTRUCTIVE_TOOL}),
                max_iterations=5,
                max_tool_calls=5,
            ),
        )

        def decide(context):
            return ToolRequest(
                tool_name=OTHER_DESTRUCTIVE_TOOL,
                arguments={'value': 'unauthorized'},
                call_id='call-jit',
            )

        result = runner.run(
            task='non-allowlisted destructive', decide=decide, run_id=run_id
        )
        # The guard blocks the non-allowlisted tool → pending approval, not run.
        assert result.status == 'pending_approval', result.status

        # No auto_mode approval event may be emitted for the blocked call.
        auto_events = [
            e
            for e in audit.events
            if e.event_type == 'tool_call_approved'
            and e.payload.get('authority_type') == 'auto_mode'
        ]
        assert auto_events == []

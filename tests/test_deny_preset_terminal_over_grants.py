# test-type: adversarial
"""Owner decision 2026-10-27: a matched deny preset is terminal over grants.

Session approvals (``approve_session``) and once grants (``approve_once``) must
never override a matched deny preset. Before the fix,
``ApprovalManager.assert_allowed`` (``teaagent/approval/manager.py``) returned on
``is_tool_session_approved`` and ``consume_once`` before it consulted
``check_preset``, so deny + session and deny + once were both ALLOWED.

Pinned behaviour:

- deny + session approval -> ``ToolPermissionError`` with ``POLICY_DENIED``.
- deny + once grant with the exact payload -> ``POLICY_DENIED``, and the once grant
  is NOT consumed by the denied attempt (it stays available for inspection).
- The governed runner path (``AgentRunner`` -> ``ApprovalPolicy.assert_allowed``)
  with a session or once grant on the runner's coordinator and a deny preset: the
  tool handler never runs and the audit records ``policy_denied``.
- Control: with no deny preset, session and once grants still allow the call.
- Falsifier: revoking the deny grant restores the session allow.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from teaagent.approval.manager import (
    ApprovalManager,
    JITApprovalState,
    PermissionMode,
)
from teaagent.cli import main
from teaagent.ergonomics._approval_state import ApprovalPresetStore
from teaagent.errors import DenialReasonCode, ToolPermissionError
from teaagent.policy import ApprovalPolicy, compute_scoped_payload_digest
from teaagent.runner import AgentRunner, FinalAnswer, ToolRequest
from teaagent.types import AuditLogger, ToolAnnotations, ToolRegistry

_TOOL = 'workspace_write_file'
_ARGS: dict[str, Any] = {'path': 'x.txt', 'content': 'hi'}
_CALL_ID = 'call-deny-terminal'
_REQUEST = ToolRequest(tool_name=_TOOL, arguments=_ARGS, call_id=_CALL_ID)


def _manager(root: Path) -> ApprovalManager:
    return ApprovalManager(
        permission_mode=PermissionMode.PROMPT,
        approval_store=ApprovalPresetStore(root),
        approval_origin_run_id='run-deny-terminal',
        workspace_root=str(root),
        enable_jit_prompt=False,
    )


def _assert_policy_denied(exc: pytest.ExceptionInfo[ToolPermissionError]) -> None:
    assert exc.value.reason_code is DenialReasonCode.POLICY_DENIED


def _recording_registry(calls: list[dict[str, Any]]) -> ToolRegistry:
    registry = ToolRegistry()

    def _write(arguments: dict[str, Any]) -> dict[str, Any]:
        calls.append(arguments)
        return {'success': True}

    registry.register(
        name=_TOOL,
        description='Write a file (destructive, recorded for tests)',
        input_schema={
            'type': 'object',
            'properties': {'path': {'type': 'string'}, 'content': {'type': 'string'}},
            'required': ['path', 'content'],
        },
        output_schema={
            'type': 'object',
            'properties': {'success': {'type': 'boolean'}},
        },
        handler=_write,
        annotations=ToolAnnotations(destructive=True),
    )
    return registry


def _run_with_grant(
    root: Path,
    *,
    session: bool = False,
    once: bool = False,
) -> tuple[list[dict[str, Any]], AuditLogger]:
    """Run one destructive call through the real runner with a grant seeded on it."""
    calls: list[dict[str, Any]] = []
    audit = AuditLogger()
    policy = ApprovalPolicy(
        permission_mode=PermissionMode.PROMPT,
        approval_store=ApprovalPresetStore(root),
        approval_origin_run_id='run-deny-terminal',
        workspace_root=str(root),
    )
    runner = AgentRunner(
        registry=_recording_registry(calls),
        audit=audit,
        approval_policy=policy,
    )
    jit = runner.approval_manager.jit_state
    if session:
        jit.approve_session(_TOOL)
    if once:
        jit.approve_once(
            _CALL_ID, payload_digest=compute_scoped_payload_digest(_TOOL, dict(_ARGS))
        )
    steps = iter([_REQUEST, FinalAnswer(content='done')])
    runner.run(task='write file', decide=lambda _: next(steps))
    return calls, audit


def _event_types(audit: AuditLogger) -> list[str]:
    return [event.event_type for event in audit.events]


def _policy_denied_recorded(audit: AuditLogger) -> bool:
    return any(
        event.event_type == 'tool_call_blocked'
        and event.payload.get('reason_code') == 'policy_denied'
        for event in audit.events
    )


# --- ApprovalManager (the ordering bug itself) -------------------------------


def test_deny_preset_blocks_session_approved_tool(tmp_path: Path) -> None:
    """deny + approve_session -> POLICY_DENIED (was ALLOWED before the fix)."""
    ApprovalPresetStore(tmp_path).deny(_TOOL, path_globs=['*'])
    manager = _manager(tmp_path)
    manager.approve_session(_TOOL)

    with pytest.raises(ToolPermissionError) as exc:
        manager.assert_allowed(
            tool_name=_TOOL,
            call_id='call-session',
            destructive=True,
            arguments=dict(_ARGS),
        )
    _assert_policy_denied(exc)


def test_deny_preset_blocks_once_grant_and_leaves_grant_unconsumed(
    tmp_path: Path,
) -> None:
    """deny + approve_once (exact payload) -> POLICY_DENIED, grant not consumed."""
    ApprovalPresetStore(tmp_path).deny(_TOOL, path_globs=['*'])
    manager = _manager(tmp_path)
    manager.approve_once(_CALL_ID, tool_name=_TOOL, arguments=dict(_ARGS))

    with pytest.raises(ToolPermissionError) as exc:
        manager.assert_allowed(
            tool_name=_TOOL,
            call_id=_CALL_ID,
            destructive=True,
            arguments=dict(_ARGS),
        )
    _assert_policy_denied(exc)

    # The denied attempt must not have consumed the once grant.
    digest = compute_scoped_payload_digest(_TOOL, dict(_ARGS))
    assert manager.get_jit_state().is_call_approved(_CALL_ID, digest)
    assert _CALL_ID in manager.get_jit_state().approved_call_ids


def test_no_deny_preset_session_and_once_still_allow(tmp_path: Path) -> None:
    """Control: without a deny preset, session and once grants still allow."""
    manager = _manager(tmp_path)
    manager.approve_session(_TOOL)
    manager.assert_allowed(
        tool_name=_TOOL,
        call_id='call-session',
        destructive=True,
        arguments=dict(_ARGS),
    )

    once_manager = _manager(tmp_path)
    once_manager.approve_once(_CALL_ID, tool_name=_TOOL, arguments=dict(_ARGS))
    once_manager.assert_allowed(
        tool_name=_TOOL,
        call_id=_CALL_ID,
        destructive=True,
        arguments=dict(_ARGS),
    )
    # The allowed once grant is consumed, as before.
    assert _CALL_ID not in once_manager.get_jit_state().approved_call_ids


# --- ApprovalPolicy / governed runner path -----------------------------------


def test_policy_path_blocks_session_approval_under_deny(tmp_path: Path) -> None:
    """ApprovalPolicy.assert_allowed with a session approval in jit_state -> blocked."""
    ApprovalPresetStore(tmp_path).deny(_TOOL, path_globs=['*'])
    policy = ApprovalPolicy(
        permission_mode=PermissionMode.PROMPT,
        approval_store=ApprovalPresetStore(tmp_path),
        approval_origin_run_id='run-deny-terminal',
        workspace_root=str(tmp_path),
        enable_jit_prompt=False,
    )
    jit = JITApprovalState()
    jit.approve_session(_TOOL)

    with pytest.raises(ToolPermissionError) as exc:
        policy.assert_allowed(
            tool_name=_TOOL,
            call_id='call-policy',
            destructive=True,
            arguments=dict(_ARGS),
            jit_state=jit,
        )
    _assert_policy_denied(exc)


def test_runner_session_approval_under_deny_is_not_executed(
    tmp_path: Path,
) -> None:
    """Governed runner path: deny preset + session approval -> handler never runs."""
    ApprovalPresetStore(tmp_path).deny(_TOOL, path_globs=['*'])

    calls, audit = _run_with_grant(tmp_path, session=True)

    assert calls == []
    event_types = _event_types(audit)
    assert 'tool_call_started' not in event_types
    assert 'tool_call_approved' not in event_types
    assert _policy_denied_recorded(audit)


def test_runner_once_grant_under_deny_is_not_executed(tmp_path: Path) -> None:
    """Governed runner path: deny preset + once grant -> handler never runs."""
    ApprovalPresetStore(tmp_path).deny(_TOOL, path_globs=['*'])

    calls, audit = _run_with_grant(tmp_path, once=True)

    assert calls == []
    event_types = _event_types(audit)
    assert 'tool_call_started' not in event_types
    assert 'tool_call_approved' not in event_types
    assert _policy_denied_recorded(audit)


def test_runner_grants_without_deny_still_execute(tmp_path: Path) -> None:
    """Control: no deny preset, session grant on the real runner runs the tool."""
    calls, audit = _run_with_grant(tmp_path, session=True)

    assert calls == [_ARGS]
    assert 'tool_call_started' in _event_types(audit)
    assert not _policy_denied_recorded(audit)


def test_revoking_deny_restores_session_allow(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Falsifier: revoking the deny grant lets the session approval allow the call."""
    rc = main(['approval', 'deny', _TOOL, '--root', str(tmp_path), '--path-glob', '*'])
    assert rc == 0
    grant_id = json.loads(capsys.readouterr().out)['grant_id']

    blocked_calls, _ = _run_with_grant(tmp_path, session=True)
    assert blocked_calls == []

    rc = main(['approval', 'revoke', grant_id, '--root', str(tmp_path)])
    assert rc == 0
    assert json.loads(capsys.readouterr().out)['status'] == 'revoked'

    calls, audit = _run_with_grant(tmp_path, session=True)
    assert calls == [_ARGS]
    assert 'tool_call_started' in _event_types(audit)
    assert not _policy_denied_recorded(audit)

# test-type: behavior
"""Regression test for dogfood finding G1: deny presets must block at runtime.

Repro (docs/work-log/dogfood-findings-2026-09-15.md, G1 row): ``teaagent approval
deny <tool> --path-glob <glob>`` registered a deny grant, and ``approval check``
reported ``decision: deny``, but the runtime path never blocked the call.

The tests below drive the governed path (AgentRunner -> ApprovalPolicy.assert_allowed
-> ApprovalManager preset check) with a recording tool, so "not executed" is observed
directly rather than inferred from the run status.

Behaviour pinned (current code):

- Deny preset in ``prompt`` mode with no approval handler: the call is not executed
  and the audit records a ``policy_denied`` reason. The raise lives at
  ``teaagent/approval/manager.py:987-991``; the deny is matched first by
  ``teaagent/ergonomics/_approval_state.py:616-617``.
- Deny preset in ``allow`` mode: the call is still blocked. The backend approves
  ``allow`` mode, but the preset check at ``teaagent/approval/manager.py:987`` runs
  before the ``if decision.approved: return`` short-circuit at ``:1003``, so an
  explicit deny wins over the owner-chosen ``allow`` widening.
- Without a deny preset the same flow executes the tool (control), so the blocking
  assertions cannot pass vacuously.

Not pinned here: in ``prompt`` mode with an ``approval_handler`` that approves, the
runner's ToolPermissionError path (``teaagent/runner/_governed_execution.py:314-335``)
still asks the handler, and an approving handler runs a deny-matched call. Whether
an interactive override should beat a deny preset is an open owner decision.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from teaagent.cli import main
from teaagent.ergonomics._approval_state import ApprovalPresetStore
from teaagent.policy import ApprovalPolicy
from teaagent.runner import AgentRunner, ApprovalRequest, FinalAnswer, ToolRequest
from teaagent.types import (
    AuditLogger,
    PermissionMode,
    ToolAnnotations,
    ToolRegistry,
)

_TOOL = 'workspace_write_file'
_ARGS: dict[str, Any] = {'path': 'x.txt', 'content': 'hi'}
_REQUEST = ToolRequest(tool_name=_TOOL, arguments=_ARGS, call_id='call-g1')
_BLOCKING_EVENTS = ('tool_call_blocked', 'tool_call_pending_approval')


def _recording_registry(calls: list[dict[str, Any]]) -> ToolRegistry:
    """Destructive write tool whose only side effect is appending to ``calls``."""
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


def _register_deny_via_cli(root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Register the deny grant exactly as the G1 repro does (CLI, not the store API)."""
    rc = main(['approval', 'deny', _TOOL, '--root', str(root), '--path-glob', '*'])
    assert rc == 0
    assert '"scope": "deny"' in capsys.readouterr().out


def _run_tool_call(
    root: Path,
    *,
    permission_mode: PermissionMode,
    approval_handler: Any = None,
) -> tuple[Any, list[dict[str, Any]], AuditLogger]:
    calls: list[dict[str, Any]] = []
    audit = AuditLogger()
    policy = ApprovalPolicy(
        permission_mode=permission_mode,
        approval_store=ApprovalPresetStore(root),
        approval_origin_run_id='run-g1',
        workspace_root=str(root),
        allow_all_destructive=permission_mode is PermissionMode.ALLOW,
    )
    runner = AgentRunner(
        registry=_recording_registry(calls),
        audit=audit,
        approval_policy=policy,
        approval_handler=approval_handler,
    )
    steps = iter([_REQUEST, FinalAnswer(content='done')])
    result = runner.run(task='write file', decide=lambda _: next(steps))
    return result, calls, audit


def _event_types(audit: AuditLogger) -> list[str]:
    return [event.event_type for event in audit.events]


def _reason_codes(audit: AuditLogger, event_types: tuple[str, ...]) -> list[Any]:
    return [
        event.payload.get('reason_code')
        for event in audit.events
        if event.event_type in event_types
    ]


def test_deny_grant_reported_by_check_precondition(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Precondition for the G1 repro: the CLI-registered grant reads back as deny."""
    _register_deny_via_cli(tmp_path, capsys)

    check = ApprovalPresetStore(tmp_path).check(
        _TOOL, permission_mode='prompt', arguments=dict(_ARGS)
    )
    assert check['decision'] == 'deny'


def test_deny_grant_blocks_tool_call_in_prompt_mode(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """(a) G1 regression: a matched deny grant stops the tool from running.

    No approval handler is attached, so nothing can approve the call. The tool
    handler must never be invoked, and the audit must carry the deny-specific
    ``policy_denied`` reason rather than a generic missing-approval reason.
    """
    _register_deny_via_cli(tmp_path, capsys)

    result, calls, audit = _run_tool_call(
        tmp_path, permission_mode=PermissionMode.PROMPT
    )

    assert calls == []
    assert result.status != 'completed'
    event_types = _event_types(audit)
    assert 'tool_call_started' not in event_types
    assert 'tool_call_approved' not in event_types
    assert any(et in _BLOCKING_EVENTS for et in event_types)
    assert 'policy_denied' in _reason_codes(audit, _BLOCKING_EVENTS)


def test_deny_grant_blocks_tool_call_in_allow_mode(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """(c) An explicit deny still wins under ``allow`` mode.

    ``allow`` lets the backend approve the call, but the preset check at
    ``teaagent/approval/manager.py:987`` runs before the approved short-circuit at
    ``:1003``. The call is blocked with ``tool_call_blocked`` and ``policy_denied``.
    """
    _register_deny_via_cli(tmp_path, capsys)

    result, calls, audit = _run_tool_call(
        tmp_path, permission_mode=PermissionMode.ALLOW
    )

    assert calls == []
    assert result.status != 'completed'
    assert 'tool_call_started' not in _event_types(audit)
    assert 'tool_call_blocked' in _event_types(audit)
    assert 'policy_denied' in _reason_codes(audit, ('tool_call_blocked',))


def test_without_deny_grant_prompt_mode_runs_tool_after_approval(
    tmp_path: Path,
) -> None:
    """(b) Control: with no deny grant and an approving handler, the tool runs.

    Proves the recording tool and governed path execute the call when nothing
    denies it, so the blocking assertions above are not vacuous.
    """

    def approve(_req: ApprovalRequest) -> bool:
        return True

    result, calls, audit = _run_tool_call(
        tmp_path, permission_mode=PermissionMode.PROMPT, approval_handler=approve
    )

    assert result.status == 'completed'
    assert calls == [_ARGS]
    assert 'tool_call_started' in _event_types(audit)
    assert 'policy_denied' not in _reason_codes(audit, _BLOCKING_EVENTS)


def test_without_deny_grant_allow_mode_runs_tool(tmp_path: Path) -> None:
    """(b) Control under ``allow`` mode: no deny grant means the tool runs."""
    result, calls, audit = _run_tool_call(
        tmp_path, permission_mode=PermissionMode.ALLOW
    )

    assert result.status == 'completed'
    assert calls == [_ARGS]
    assert 'tool_call_started' in _event_types(audit)
    assert 'tool_call_blocked' not in _event_types(audit)

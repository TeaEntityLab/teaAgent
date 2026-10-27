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

- Deny preset in ``prompt`` mode with an approving ``approval_handler``: the call is
  still blocked and the handler is never consulted. This is the owner decision
  "block in all modes" (docs/reviews/dogfood-g1-g22-2026-09-15-risk.md:22;
  docs/cli.md:923 "Matched deny grants hard-block in every mode"). The runner's
  ToolPermissionError path (``teaagent/runner/_governed_execution.py``) records a
  ``policy_denied`` block and re-raises for ``POLICY_DENIED`` instead of offering
  interactive approval. Removing the deny grant (``approval revoke``) is the only
  way to let such a call run again; the falsifier test pins that escape hatch.
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

import pytest

from teaagent.cli import main
from teaagent.ergonomics._approval_state import ApprovalPresetStore
from teaagent.policy import ApprovalPolicy
from teaagent.run_store import RunStore
from teaagent.runner import (
    AgentRunner,
    ApprovalRequest,
    FinalAnswer,
    RunResult,
    ToolRequest,
)
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


def _register_deny_via_cli(root: Path, capsys: pytest.CaptureFixture[str]) -> str:
    """Register the deny grant exactly as the G1 repro does (CLI, not the store API).

    Returns the new grant's ``grant_id`` so callers can revoke it.
    """
    rc = main(['approval', 'deny', _TOOL, '--root', str(root), '--path-glob', '*'])
    assert rc == 0
    out = capsys.readouterr().out
    assert '"scope": "deny"' in out
    grant_id = json.loads(out)['grant_id']
    assert isinstance(grant_id, str)
    return grant_id


def _run_tool_call(
    root: Path,
    *,
    permission_mode: PermissionMode,
    approval_handler: Any = None,
    audit: AuditLogger | None = None,
) -> tuple[Any, list[dict[str, Any]], AuditLogger]:
    calls: list[dict[str, Any]] = []
    audit = audit if audit is not None else AuditLogger()
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


def test_deny_grant_blocks_approving_handler_in_prompt_mode(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """(d) G-P1-4: a deny preset is terminal in ``prompt`` mode.

    The handler would approve, but a matched deny must never reach it. Before the
    fix, ``_governed_execution.py`` offered the ToolPermissionError to the handler
    for destructive tools, and the approving handler ran the denied tool.
    """
    _register_deny_via_cli(tmp_path, capsys)
    handler_calls: list[ApprovalRequest] = []

    def approve(req: ApprovalRequest) -> bool:
        handler_calls.append(req)
        return True

    result, calls, audit = _run_tool_call(
        tmp_path, permission_mode=PermissionMode.PROMPT, approval_handler=approve
    )

    assert handler_calls == []
    assert calls == []
    assert result.status != 'completed'
    event_types = _event_types(audit)
    assert 'tool_call_started' not in event_types
    assert 'tool_call_approved' not in event_types
    assert 'tool_call_blocked' in event_types
    assert 'policy_denied' in _reason_codes(audit, ('tool_call_blocked',))


def test_why_denied_renders_policy_denied_description(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """(e) ``approval why-denied`` renders ``policy_denied`` with a real description."""
    _register_deny_via_cli(tmp_path, capsys)
    run_id = 'run-g1-4-why-denied'
    store = RunStore(tmp_path)
    audit = store.audit_logger(run_id)

    def approve(_req: ApprovalRequest) -> bool:
        return True

    _run_tool_call(
        tmp_path,
        permission_mode=PermissionMode.PROMPT,
        approval_handler=approve,
        audit=audit,
    )
    store.logger_for_result(
        RunResult(
            run_id=run_id,
            final_answer=None,
            iterations=1,
            tool_calls=0,
            status='failed',
        ),
        audit,
    )

    out = io.StringIO()
    with redirect_stdout(out):
        code = main(['approval', 'why-denied', run_id, '--root', str(tmp_path)])

    assert code == 0
    rendered = out.getvalue()
    assert 'Reason:   policy_denied' in rendered
    assert 'Unknown denial reason' not in rendered
    assert 'approval preset' in rendered


def test_revoking_deny_grant_lets_approving_handler_run_tool(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """(f) Falsifier: ``approval revoke <deny_grant_id>`` is the escape hatch.

    With the deny present the approving handler is never consulted. After revoke,
    a new run with the same approving handler executes the tool, which shows the
    block came from the deny grant and nothing else.
    """
    grant_id = _register_deny_via_cli(tmp_path, capsys)
    handler_calls: list[ApprovalRequest] = []

    def approve(req: ApprovalRequest) -> bool:
        handler_calls.append(req)
        return True

    _, blocked_calls, _ = _run_tool_call(
        tmp_path, permission_mode=PermissionMode.PROMPT, approval_handler=approve
    )
    assert blocked_calls == []
    assert handler_calls == []

    rc = main(['approval', 'revoke', grant_id, '--root', str(tmp_path)])
    assert rc == 0
    assert json.loads(capsys.readouterr().out)['status'] == 'revoked'

    result, calls, audit = _run_tool_call(
        tmp_path, permission_mode=PermissionMode.PROMPT, approval_handler=approve
    )
    assert result.status == 'completed'
    assert calls == [_ARGS]
    assert len(handler_calls) == 1
    assert 'tool_call_started' in _event_types(audit)
    assert 'policy_denied' not in _reason_codes(audit, _BLOCKING_EVENTS)

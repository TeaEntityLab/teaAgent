"""EFX-003: one-time approvals bind payload digest and are consumed."""

from __future__ import annotations

import pytest

from teaagent.approval.manager import ApprovalManager, JITApprovalState
from teaagent.errors import ToolPermissionError
from teaagent.policy import PermissionMode, compute_scoped_payload_digest
from teaagent.prompt import parse_model_decision
from teaagent.runner import ToolRequest


def test_omitted_call_ids_include_payload_digest() -> None:
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
    digest_a = compute_scoped_payload_digest('github_review_pr', first.arguments)
    digest_b = compute_scoped_payload_digest('github_review_pr', second.arguments)
    assert digest_a in first.call_id
    assert digest_b in second.call_id
    assert first.call_id.startswith('model-github_review_pr-')


def test_digest_bound_grant_does_not_authorize_changed_arguments() -> None:
    state = JITApprovalState()
    args_a = {'repo': 'o/r', 'pr_number': 1, 'body': 'a'}
    args_b = {'repo': 'o/r', 'pr_number': 1, 'body': 'b'}
    digest_a = compute_scoped_payload_digest('github_review_pr', args_a)
    digest_b = compute_scoped_payload_digest('github_review_pr', args_b)
    state.approve_once('shared-id', payload_digest=digest_a)
    assert state.is_call_approved('shared-id', digest_a) is True
    assert state.is_call_approved('shared-id', digest_b) is False
    assert state.consume_once('shared-id', digest_b) is False
    assert state.consume_once('shared-id', digest_a) is True
    assert state.consume_once('shared-id', digest_a) is False


def test_assert_allowed_consumes_one_time_grant() -> None:
    mgr = ApprovalManager(permission_mode=PermissionMode.PROMPT)
    args = {'path': 'hello.txt', 'content': 'x'}
    mgr.approve_once('c1', tool_name='workspace_write_file', arguments=args)
    mgr.assert_allowed(
        tool_name='workspace_write_file',
        call_id='c1',
        destructive=True,
        arguments=args,
    )
    assert mgr.get_jit_state().is_call_approved('c1') is False
    with pytest.raises(ToolPermissionError):
        mgr.assert_allowed(
            tool_name='workspace_write_file',
            call_id='c1',
            destructive=True,
            arguments=args,
        )


def test_session_approval_is_not_consumed() -> None:
    mgr = ApprovalManager(permission_mode=PermissionMode.PROMPT)
    mgr.approve_session('workspace_write_file')
    args = {'path': 'hello.txt', 'content': 'x'}
    mgr.assert_allowed(
        tool_name='workspace_write_file',
        call_id='c1',
        destructive=True,
        arguments=args,
    )
    mgr.assert_allowed(
        tool_name='workspace_write_file',
        call_id='c2',
        destructive=True,
        arguments={'path': 'hello.txt', 'content': 'y'},
    )

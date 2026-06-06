"""WS3-006 approval-token exactness for destructive tools."""

from __future__ import annotations

from tempfile import TemporaryDirectory

import pytest

from teaagent.approval_manager import PermissionMode
from teaagent.ergonomics.approval_store import ApprovalPresetStore
from teaagent.errors import ToolPermissionError
from teaagent.policy import ApprovalPolicy


def _policy_with_store(tmp: str, run_id: str) -> ApprovalPolicy:
    root = f'{tmp}/.teaagent'
    store = ApprovalPresetStore(root=root)
    return ApprovalPolicy(
        permission_mode=PermissionMode.PROMPT,
        approval_store=store,
        approval_origin_run_id=run_id,
        workspace_root=tmp,
    )


def test_stale_scoped_token_cannot_be_reused() -> None:
    with TemporaryDirectory() as tmp:
        run_id = 'run-token-1'
        policy = _policy_with_store(tmp, run_id)
        store = policy.approval_store
        assert store is not None
        store.add_scoped_approval(
            run_id=run_id,
            call_id='call-a',
            tool_name='workspace_write_file',
            arguments={'path': 'a.txt', 'content': 'one'},
        )
        policy.assert_allowed(
            tool_name='workspace_write_file',
            call_id='call-a',
            destructive=True,
            arguments={'path': 'a.txt', 'content': 'one'},
        )
        with pytest.raises(ToolPermissionError):
            policy.assert_allowed(
                tool_name='workspace_write_file',
                call_id='call-a',
                destructive=True,
                arguments={'path': 'a.txt', 'content': 'one'},
            )


def test_mismatched_arguments_reject_scoped_token() -> None:
    with TemporaryDirectory() as tmp:
        run_id = 'run-token-2'
        policy = _policy_with_store(tmp, run_id)
        store = policy.approval_store
        assert store is not None
        store.add_scoped_approval(
            run_id=run_id,
            call_id='call-b',
            tool_name='workspace_write_file',
            arguments={'path': 'b.txt', 'content': 'approved'},
        )
        with pytest.raises(ToolPermissionError):
            policy.assert_allowed(
                tool_name='workspace_write_file',
                call_id='call-b',
                destructive=True,
                arguments={'path': 'b.txt', 'content': 'changed'},
            )


def test_wrong_call_id_cannot_reuse_scoped_approval() -> None:
    with TemporaryDirectory() as tmp:
        run_id = 'run-token-3'
        policy = _policy_with_store(tmp, run_id)
        store = policy.approval_store
        assert store is not None
        store.add_scoped_approval(
            run_id=run_id,
            call_id='call-c',
            tool_name='workspace_write_file',
            arguments={'path': 'c.txt', 'content': 'x'},
        )
        with pytest.raises(ToolPermissionError):
            policy.assert_allowed(
                tool_name='workspace_write_file',
                call_id='call-d',
                destructive=True,
                arguments={'path': 'c.txt', 'content': 'x'},
            )

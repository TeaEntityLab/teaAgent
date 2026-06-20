"""G-P2-2: ``preapproved_call_ids`` removal — payload_digest is the only path.

After the deprecation window, call-id-based preapproval
(``preapproved_call_ids``) is no longer honoured. The only scoped
preapproval mechanism is ``preapproved_payload_digests``.
"""

from __future__ import annotations

import contextlib
import warnings
from pathlib import Path

import pytest

from teaagent.ergonomics.approval_store import ApprovalPresetStore
from teaagent.policy import ApprovalPolicy, compute_scoped_payload_digest
from teaagent.types import PermissionMode, ToolPermissionError


def _policy_with_store(
    tmp: str,
    run_id: str,
    *,
    preapproved_call_ids: frozenset[str] = frozenset(),
    preapproved_payload_digests: frozenset[str] = frozenset(),
) -> ApprovalPolicy:
    root = f'{tmp}/.teaagent'
    store = ApprovalPresetStore(root=root)
    return ApprovalPolicy(
        permission_mode=PermissionMode.PROMPT,
        approval_store=store,
        approval_origin_run_id=run_id,
        workspace_root=tmp,
        preapproved_call_ids=preapproved_call_ids,
        preapproved_payload_digests=preapproved_payload_digests,
    )


def test_preapproved_call_ids_no_longer_grant_approval(tmp_path: Path) -> None:
    """A call_id present in preapproved_call_ids must NOT approve the call."""
    run_id = 'run-legacy-1'
    policy = _policy_with_store(
        str(tmp_path),
        run_id,
        preapproved_call_ids=frozenset({'call-legacy'}),
    )
    with pytest.raises(ToolPermissionError):
        policy.assert_allowed(
            tool_name='workspace_write_file',
            call_id='call-legacy',
            destructive=True,
            arguments={'path': 'a.txt', 'content': 'data'},
        )


def test_preapproved_call_ids_emit_no_deprecation_warning(
    tmp_path: Path,
) -> None:
    """G-P2-2: the deprecation warning for preapproved_call_ids is gone."""
    run_id = 'run-legacy-2'
    policy = _policy_with_store(
        str(tmp_path),
        run_id,
        preapproved_call_ids=frozenset({'call-legacy'}),
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        with contextlib.suppress(ToolPermissionError):
            policy.assert_allowed(
                tool_name='workspace_write_file',
                call_id='call-legacy',
                destructive=True,
                arguments={'path': 'a.txt', 'content': 'data'},
            )
    assert not [
        w
        for w in caught
        if issubclass(w.category, DeprecationWarning)
        and 'preapproved_call_ids' in str(w.message)
    ]


def test_payload_digest_still_grants_approval(tmp_path: Path) -> None:
    """payload_digest-based preapproval remains the supported path."""
    run_id = 'run-digest-1'
    tool_name = 'workspace_write_file'
    args = {'path': 'a.txt', 'content': 'data'}
    digest = compute_scoped_payload_digest(tool_name, args)
    policy = _policy_with_store(
        str(tmp_path),
        run_id,
        preapproved_payload_digests=frozenset({digest}),
    )
    # Should not raise — payload digest approves the call.
    policy.assert_allowed(
        tool_name=tool_name,
        call_id='call-any',
        destructive=True,
        arguments=args,
    )


def test_payload_digest_is_call_id_independent(tmp_path: Path) -> None:
    """payload_digest approves regardless of the call_id used."""
    run_id = 'run-digest-2'
    tool_name = 'workspace_write_file'
    args = {'path': 'b.txt', 'content': 'data'}
    digest = compute_scoped_payload_digest(tool_name, args)
    policy = _policy_with_store(
        str(tmp_path),
        run_id,
        preapproved_payload_digests=frozenset({digest}),
    )
    policy.assert_allowed(
        tool_name=tool_name,
        call_id='whatever-id',
        destructive=True,
        arguments=args,
    )


def test_wrong_payload_digest_denies(tmp_path: Path) -> None:
    """An unrelated digest does not approve a different payload."""
    run_id = 'run-digest-3'
    tool_name = 'workspace_write_file'
    args = {'path': 'c.txt', 'content': 'data'}
    other_digest = compute_scoped_payload_digest(
        tool_name, {'path': 'other.txt', 'content': 'data'}
    )
    policy = _policy_with_store(
        str(tmp_path),
        run_id,
        preapproved_payload_digests=frozenset({other_digest}),
    )
    with pytest.raises(ToolPermissionError):
        policy.assert_allowed(
            tool_name=tool_name,
            call_id='call-x',
            destructive=True,
            arguments=args,
        )

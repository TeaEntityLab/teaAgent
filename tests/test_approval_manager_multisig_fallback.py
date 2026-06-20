"""G-P1-3: ``multisig_fallback`` audit event when agent_id is missing.

When multi-sig quorum is enabled but the session has no ``agent_id`` set,
``MultiSigQuorumManager.check_quorum`` falls back to standard approval.
This module asserts that a structured ``multisig_fallback`` audit event
(with a reason) is emitted so misconfigured sessions are detectable after
the fact.
"""

from __future__ import annotations

import contextlib
import logging
from pathlib import Path

import pytest

from teaagent.approval_manager import (
    ApprovalManager,
    MultiSigQuorumConfig,
    PermissionMode,
    ToolPermissionError,
)


def _manager_without_agent_id() -> ApprovalManager:
    return ApprovalManager(
        permission_mode=PermissionMode.PROMPT,
        multi_sig_config=MultiSigQuorumConfig(enabled=True, required_approvals=2),
        agent_id='',  # misconfigured session
    )


def test_multisig_fallback_emits_audit_event(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """check_quorum emits a ``multisig_fallback`` log event with a reason."""
    manager = _manager_without_agent_id()
    with caplog.at_level(logging.WARNING, logger='teaagent.approval_manager'):
        result = manager._multisig_manager.check_quorum(
            'workspace_write_file', 'call-1', {'path': 'a.txt'}
        )

    assert result is False

    fallback_records = [
        r for r in caplog.records if r.__dict__.get('event') == 'multisig_fallback'
    ]
    assert fallback_records, 'expected a multisig_fallback audit event'
    record = fallback_records[0]
    assert record.__dict__.get('reason') == 'agent_id_not_set'
    assert record.__dict__.get('tool_name') == 'workspace_write_file'
    assert record.__dict__.get('call_id') == 'call-1'
    assert record.__dict__.get('required_approvals') == 2


def test_multisig_fallback_not_emitted_when_agent_id_set(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No fallback event when agent_id is configured."""
    manager = ApprovalManager(
        permission_mode=PermissionMode.PROMPT,
        multi_sig_config=MultiSigQuorumConfig(enabled=True, required_approvals=2),
        agent_id='agent-a',
    )
    # Avoid blocking on federated peer-signature collection.
    monkeypatch.setattr(
        manager._multisig_manager,
        '_collect_peer_signatures',
        lambda request: [],
    )
    with caplog.at_level(logging.WARNING, logger='teaagent.approval_manager'):
        manager._multisig_manager.check_quorum(
            'workspace_write_file', 'call-1', {'path': 'a.txt'}
        )

    assert not [
        r for r in caplog.records if r.__dict__.get('event') == 'multisig_fallback'
    ]


def test_multisig_fallback_not_emitted_when_disabled(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """No fallback event when multi-sig is disabled."""
    manager = ApprovalManager(
        permission_mode=PermissionMode.PROMPT,
        multi_sig_config=MultiSigQuorumConfig(enabled=False),
        agent_id='',
    )
    with caplog.at_level(logging.WARNING, logger='teaagent.approval_manager'):
        manager._multisig_manager.check_quorum(
            'workspace_write_file', 'call-1', {'path': 'a.txt'}
        )

    assert not [
        r for r in caplog.records if r.__dict__.get('event') == 'multisig_fallback'
    ]


def test_multisig_fallback_then_denied(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    """End-to-end: a misconfigured session is denied and audited."""
    from teaagent.policy import ApprovalPolicy

    policy = ApprovalPolicy(
        permission_mode=PermissionMode.PROMPT,
        multi_sig_config=MultiSigQuorumConfig(
            enabled=True,
            required_approvals=2,
            high_risk_patterns=['workspace_write'],
        ),
        agent_id='',
        workspace_root=str(tmp_path),
    )
    with (
        caplog.at_level(logging.WARNING, logger='teaagent.approval_manager'),
        contextlib.suppress(ToolPermissionError),
    ):
        policy.assert_allowed(
            tool_name='workspace_write_file',
            call_id='call-x',
            destructive=True,
            arguments={'path': 'config.json'},
        )

    assert [r for r in caplog.records if r.__dict__.get('event') == 'multisig_fallback']

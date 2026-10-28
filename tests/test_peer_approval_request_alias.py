# test-type: contract
"""A-P1-8 (owner decision Q4, 2026-10-27): the P2P multi-signature request class is
``PeerApprovalRequest``. ``ApprovalRequest`` stays as a deprecated alias for the same class.

Three classes were named ``ApprovalRequest`` before this change: the P2P request in
``teaagent.approval.manager``, the backend decision input in ``teaagent.approval.backend``,
and the runner type in ``teaagent.runner._types``. The rename removes the collision for
the multi-signature module.
"""

from __future__ import annotations

import dataclasses
import importlib
from typing import Any

import pytest

from teaagent.approval import backend as approval_backend
from teaagent.approval import manager


def test_peer_approval_request_is_exported_under_its_own_name() -> None:
    assert manager.PeerApprovalRequest.__name__ == 'PeerApprovalRequest'
    assert 'PeerApprovalRequest' in manager.__all__


def test_deprecated_alias_resolves_to_the_same_class() -> None:
    assert manager.ApprovalRequest is manager.PeerApprovalRequest


def test_alias_resolves_to_the_same_class_through_compat_module() -> None:
    compat_module = importlib.import_module('teaagent.approval_manager')
    alias: Any = compat_module.ApprovalRequest
    assert alias is manager.PeerApprovalRequest


def test_peer_request_is_distinct_from_backend_decision_request() -> None:
    assert manager.PeerApprovalRequest is not approval_backend.ApprovalRequest


def test_peer_request_is_a_frozen_dataclass_with_the_broadcast_fields() -> None:
    assert dataclasses.is_dataclass(manager.PeerApprovalRequest)
    request = manager.PeerApprovalRequest(
        request_id='req-1',
        tool_name='workspace_write_file',
        call_id='call-1',
        arguments={},
        request_hash='hash',
        timestamp=0.0,
        requester_agent_id='agent-a',
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        request.tool_name = 'other'  # type: ignore[misc]
    field_names = {f.name for f in dataclasses.fields(manager.PeerApprovalRequest)}
    assert {
        'request_id',
        'tool_name',
        'call_id',
        'arguments',
        'request_hash',
        'timestamp',
        'requester_agent_id',
    } <= field_names


def test_quorum_check_builds_a_peer_approval_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[object] = []

    def _capture(request: object) -> list[object]:
        captured.append(request)
        return []

    quorum = manager.MultiSigQuorumManager(
        config=manager.MultiSigQuorumConfig(enabled=True, required_approvals=2),
        agent_id='agent-a',
    )
    monkeypatch.setattr(quorum, '_collect_peer_signatures', _capture)

    quorum.check_quorum('workspace_write_file', 'call-1', {'path': 'a.txt'})

    assert len(captured) == 1
    assert type(captured[0]) is manager.PeerApprovalRequest

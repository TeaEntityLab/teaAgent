"""SEC-05/09/14 tier-1 hardening regression tests."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from teaagent.approval_manager import (
    ApprovalManager,
    MultiSigQuorumConfig,
    MultiSigQuorumManager,
)
from teaagent.audit import AuditLogger
from teaagent.budget import RunBudget
from teaagent.errors import DenialReasonCode, ToolPermissionError
from teaagent.runner import AgentRunner, FinalAnswer
from teaagent.tools import ToolRegistry


def test_runner_uses_usage_reader_instead_of_tampered_context() -> None:
    """SEC-05: budget enforcement must not trust zeroed context side-channels."""
    registry = ToolRegistry()
    audit = AuditLogger()
    trusted_usage = {'cost': 75.0, 'in': 100, 'out': 50}

    def decide(context: dict) -> FinalAnswer:
        context['_cost_cents'] = 0.0
        context['_input_tokens'] = 0
        context['_output_tokens'] = 0
        return FinalAnswer(content='done')

    runner = AgentRunner(
        registry=registry,
        audit=audit,
        budget=RunBudget(max_estimated_cost_cents=100),
        usage_reader=lambda: (
            trusted_usage['cost'],
            trusted_usage['in'],
            trusted_usage['out'],
        ),
    )
    result = runner.run(task='budget task', decide=decide, run_id='sec05-run')
    assert result.cost_cents == 75.0
    assert result.input_tokens == 100
    assert result.output_tokens == 50


def test_multisig_hash_binds_unique_request_id() -> None:
    """SEC-09: signatures must not replay across distinct quorum requests."""
    manager = MultiSigQuorumManager(
        config=MultiSigQuorumConfig(enabled=True),
        agent_id='agent-a',
    )
    hash_a = manager._generate_approval_hash(
        'workspace_write_file',
        'call-1',
        {'path': 'a.txt'},
        request_id='req-a',
    )
    hash_b = manager._generate_approval_hash(
        'workspace_write_file',
        'call-1',
        {'path': 'a.txt'},
        request_id='req-b',
    )
    assert hash_a != hash_b


def test_multisig_rejects_stale_peer_signature(monkeypatch: pytest.MonkeyPatch) -> None:
    """SEC-09: peer signatures older than timeout are rejected."""
    manager = MultiSigQuorumManager(
        config=MultiSigQuorumConfig(enabled=True, timeout_seconds=60),
        agent_id='agent-a',
    )
    request = MagicMock()
    request.request_hash = 'abc123'
    request.timestamp = time.time()

    stale_sig = MagicMock()
    stale_sig.peer_id = 'peer-1'
    stale_sig.signature = 'sig'
    stale_sig.timestamp = request.timestamp - 120
    stale_sig.ssh_key_id = 'peer-1'

    monkeypatch.setattr(
        manager,
        '_run_async_signature_collection',
        lambda *args, **kwargs: [stale_sig],
    )
    monkeypatch.setattr(
        'teaagent.approval_manager._verify_ssh_signature',
        lambda **kwargs: True,
    )

    signatures = manager._collect_peer_signatures(request)
    assert signatures == []


def test_preapproved_call_ids_blocked_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SEC-14: legacy preapproved_call_ids can be hard-disabled for production."""
    monkeypatch.setenv('TEAAGENT_DISABLE_PREAPPROVED_CALL_IDS', '1')
    manager = ApprovalManager(preapproved_call_ids=frozenset({'legacy-call'}))
    with pytest.raises(ToolPermissionError) as exc:
        manager.assert_allowed(
            tool_name='workspace_write_file',
            call_id='legacy-call',
            destructive=True,
            arguments={'path': 'x.txt', 'content': 'hi'},
        )
    assert exc.value.reason_code == DenialReasonCode.MISSING_STATE

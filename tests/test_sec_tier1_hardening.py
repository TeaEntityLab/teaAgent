"""SEC-05/09/14 tier-1 hardening regression tests."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from teaagent.approval._multisig_crypto import (
    generate_approval_hash,
    resolve_allow_dev_signatures,
)
from teaagent.approval_manager import (
    ApprovalManager,
    MultiSigQuorumConfig,
    MultiSigQuorumManager,
)
from teaagent.audit import AuditLogger
from teaagent.budget import RunBudget
from teaagent.errors import ConfigError, DenialReasonCode, ToolPermissionError
from teaagent.policy import ApprovalPolicy
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
    """SEC-14 / G-P2-2: call-id preapproval no longer grants approval.

    The legacy hard-disable env is now moot: ``preapproved_call_ids`` is ignored
    unconditionally, so the call falls through to the (unmet) JIT approval path.
    """
    monkeypatch.setenv('TEAAGENT_DISABLE_PREAPPROVED_CALL_IDS', '1')
    manager = ApprovalManager(preapproved_call_ids=frozenset({'legacy-call'}))
    with pytest.raises(ToolPermissionError) as exc:
        manager.assert_allowed(
            tool_name='workspace_write_file',
            call_id='legacy-call',
            destructive=True,
            arguments={'path': 'x.txt', 'content': 'hi'},
        )
    assert exc.value.reason_code == DenialReasonCode.JIT_NO_APPROVAL


# --- SEC-09: single-source approval hash eliminates the replay window ---


def test_policy_approval_hash_binds_request_id() -> None:
    """SEC-09: the ApprovalPolicy hash (previously a replayable 1-hour bucket)
    now binds the unique request_id, so a captured signature cannot be replayed.
    """
    policy = ApprovalPolicy(agent_id='agent-a')
    hash_a = policy._generate_approval_hash(
        'workspace_write_file', 'call-1', {'path': 'a.txt'}, request_id='req-a'
    )
    hash_b = policy._generate_approval_hash(
        'workspace_write_file', 'call-1', {'path': 'a.txt'}, request_id='req-b'
    )
    assert hash_a != hash_b


def test_approval_hash_is_single_source_of_truth() -> None:
    """SEC-09: policy, manager, and the canonical helper agree — no drift."""
    args = {'path': 'a.txt'}
    canonical = generate_approval_hash(
        'workspace_write_file', 'call-1', args, request_id='req-1'
    )
    policy = ApprovalPolicy(agent_id='agent-a')
    manager = MultiSigQuorumManager(
        config=MultiSigQuorumConfig(enabled=True), agent_id='agent-a'
    )
    assert (
        policy._generate_approval_hash(
            'workspace_write_file', 'call-1', args, request_id='req-1'
        )
        == canonical
    )
    assert (
        manager._generate_approval_hash(
            'workspace_write_file', 'call-1', args, request_id='req-1'
        )
        == canonical
    )


def test_approval_hash_has_no_wallclock_time_bucket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SEC-09: hash for a fixed request_id is stable across wall-clock time
    (the old 1-hour time bucket that created the replay window is gone).
    """
    monkeypatch.setattr('time.time', lambda: 0.0)
    first = generate_approval_hash(
        'workspace_write_file', 'call-1', {'path': 'a.txt'}, request_id='req-1'
    )
    monkeypatch.setattr('time.time', lambda: 10_000.0)
    second = generate_approval_hash(
        'workspace_write_file', 'call-1', {'path': 'a.txt'}, request_id='req-1'
    )
    assert first == second


# --- SEC-15: dev-hash signatures fail closed over a non-loopback relay ---


def test_dev_signatures_allowed_only_on_loopback_relay() -> None:
    """SEC-15: dev signatures are honored when the relay is loopback."""
    cfg = MultiSigQuorumConfig(
        enabled=True,
        allow_dev_signatures=True,
        local_relay_base_url='http://127.0.0.1:8791',
    )
    assert resolve_allow_dev_signatures(cfg, env_enabled=False) is True


def test_dev_signatures_rejected_on_non_loopback_relay() -> None:
    """SEC-15: dev signatures over a WAN relay raise instead of accepting forgeries."""
    cfg = MultiSigQuorumConfig(
        enabled=True,
        allow_dev_signatures=True,
        peer_relay_urls={'peer': 'https://peer.example:8791'},
    )
    with pytest.raises(ConfigError) as exc:
        resolve_allow_dev_signatures(cfg, env_enabled=False)
    assert 'loopback' in str(exc.value).lower()


def test_env_dev_signatures_rejected_on_non_loopback_relay() -> None:
    """SEC-15: the env flag is guarded the same way as the config flag."""
    cfg = MultiSigQuorumConfig(
        enabled=True, local_relay_base_url='https://collector.example:8791'
    )
    with pytest.raises(ConfigError):
        resolve_allow_dev_signatures(cfg, env_enabled=True)


def test_dev_signatures_not_requested_allows_real_ssh_over_wan() -> None:
    """SEC-15: without dev signatures, a WAN relay is fine (real SSH enforced)."""
    cfg = MultiSigQuorumConfig(
        enabled=True, peer_relay_urls={'peer': 'https://peer.example:8791'}
    )
    assert resolve_allow_dev_signatures(cfg, env_enabled=False) is False


def test_collect_peer_signatures_fails_closed_before_wan_broadcast() -> None:
    """SEC-15: the live quorum path raises before broadcasting to a WAN relay."""
    manager = MultiSigQuorumManager(
        config=MultiSigQuorumConfig(
            enabled=True,
            allow_dev_signatures=True,
            peer_relay_urls={'peer': 'https://peer.example:8791'},
        ),
        agent_id='agent-a',
    )
    with pytest.raises(ConfigError):
        manager._collect_peer_signatures(MagicMock())

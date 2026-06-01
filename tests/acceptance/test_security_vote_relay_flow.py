"""Acceptance: vote relay payload parsing, verification, and submission."""

from __future__ import annotations

import pytest

from teaagent.consensus import (
    ConsensusConfig,
    ConsensusEngine,
    PeerIdentity,
    PeerRegistry,
    RiskLevel,
)
from teaagent.vote_relay import (
    VoteRelayPayload,
    require_relay_bind_auth,
    verify_relay_vote,
)


def _make_engine_with_peer() -> tuple[ConsensusEngine, str]:
    registry = PeerRegistry()
    registry.register(
        PeerIdentity(
            name='peer-a',
            ssh_public_key='ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGx... test',
            is_active=True,
        )
    )
    config = ConsensusConfig()
    engine = ConsensusEngine(peer_registry=registry, config=config)
    state = engine.request_consensus(
        task_description='test task',
        risk_level=RiskLevel.MEDIUM,
        proposed_by='peer-a',
    )
    return engine, state.proposal.id


def _make_payload(proposal_id: str, **overrides) -> VoteRelayPayload:
    defaults: dict = {
        'proposal_id': proposal_id,
        'peer_name': 'peer-a',
        'decision': 'approve',
        'signature': 'plaintext-sig',
        'comment': None,
    }
    defaults.update(overrides)
    return VoteRelayPayload(**defaults)


class TestVoteRelayPayload:
    def test_from_dict_round_trip(self):
        data = {
            'proposal_id': 'prop-1',
            'peer_name': 'peer-a',
            'decision': 'approve',
            'signature': 'sig-data',
        }
        payload = VoteRelayPayload.from_dict(data)
        assert payload.proposal_id == 'prop-1'
        assert payload.peer_name == 'peer-a'
        assert payload.decision == 'approve'
        assert payload.signature == 'sig-data'
        assert payload.comment is None

    def test_from_dict_with_comment(self):
        data = {
            'proposal_id': 'p1',
            'peer_name': 'peer-b',
            'decision': 'reject',
            'signature': 'sig2',
            'comment': 'needs work',
        }
        payload = VoteRelayPayload.from_dict(data)
        assert payload.comment == 'needs work'


class TestVerifyRelayVote:
    def test_proposal_not_found(self):
        engine, proposal_id = _make_engine_with_peer()
        payload = _make_payload(proposal_id='prop-missing')
        ok, reason = verify_relay_vote(engine, payload, require_ssh=False)
        assert not ok
        assert 'proposal not found' in reason

    def test_peer_not_active(self):
        engine, proposal_id = _make_engine_with_peer()
        engine.peer_registry.deactivate('peer-a')
        payload = _make_payload(proposal_id)
        ok, reason = verify_relay_vote(engine, payload, require_ssh=False)
        assert not ok
        assert 'inactive' in reason

    def test_invalid_decision_value(self):
        engine, proposal_id = _make_engine_with_peer()
        payload = _make_payload(proposal_id, decision='INVALID')
        ok, reason = verify_relay_vote(engine, payload, require_ssh=False)
        assert not ok
        assert 'invalid decision' in reason.lower()

    def test_require_ssh_rejects_plaintext(self):
        engine, proposal_id = _make_engine_with_peer()
        payload = _make_payload(proposal_id)
        ok, reason = verify_relay_vote(engine, payload, require_ssh=True)
        assert not ok
        assert 'SSH signature' in reason

    def test_dev_signatures_disabled_rejects(self):
        engine, proposal_id = _make_engine_with_peer()
        payload = _make_payload(proposal_id)
        ok, reason = verify_relay_vote(
            engine,
            payload,
            require_ssh=False,
            allow_dev_signatures=False,
        )
        assert not ok
        assert 'dev signatures' in reason


class TestRequireRelayBindAuth:
    def test_loopback_allows_no_policy(self):
        require_relay_bind_auth('127.0.0.1', None)

    def test_non_loopback_requires_policy(self):
        with pytest.raises(ValueError, match='non-loopback'):
            require_relay_bind_auth('0.0.0.0', None)

    def test_non_loopback_with_policy_ok(self):
        from teaagent.surface_auth import SurfaceAuthPolicy

        policy = SurfaceAuthPolicy()
        require_relay_bind_auth('0.0.0.0', policy)

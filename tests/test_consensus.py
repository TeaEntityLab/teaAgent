"""Tests for consensus data structures."""

import hashlib
import time

import pytest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from teaagent.consensus import (
    ConsensusConfig,
    ConsensusEngine,
    ConsensusState,
    ConsensusStatus,
    PeerIdentity,
    PeerRegistry,
    Proposal,
    RiskLevel,
    Vote,
    VoteDecision,
    VotingMechanism,
    VotingThreshold,
)


class TestPeerIdentity:
    """Tests for PeerIdentity."""

    def test_peer_identity_creation(self) -> None:
        """Test creating a peer identity."""
        peer = PeerIdentity(
            name='peer1',
            ssh_public_key='ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ...',
        )
        assert peer.name == 'peer1'
        assert peer.ssh_public_key.startswith('ssh-rsa')
        assert peer.fingerprint is not None
        assert len(peer.fingerprint) == 16
        assert peer.is_active is True

    def test_fingerprint_generation(self) -> None:
        """Test fingerprint generation from SSH key."""
        peer1 = PeerIdentity(
            name='peer1',
            ssh_public_key='ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ...',
        )
        peer2 = PeerIdentity(
            name='peer2',
            ssh_public_key='ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ...',
        )
        # Same key should produce same fingerprint
        assert peer1.fingerprint == peer2.fingerprint

    def test_signature_verification(self) -> None:
        """Test signature verification."""
        peer = PeerIdentity(
            name='peer1',
            ssh_public_key='ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ...',
        )
        # This is a simplified test - in production, use real signatures
        message = 'test message'
        signature = hashlib.sha256((message + peer.ssh_public_key).encode()).hexdigest()
        assert peer.verify_signature(message, signature) is True

    def test_signature_verification_invalid(self) -> None:
        """Test signature verification with invalid signature."""
        peer = PeerIdentity(
            name='peer1',
            ssh_public_key='ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ...',
        )
        message = 'test message'
        signature = 'invalid_signature'
        assert peer.verify_signature(message, signature) is False


class TestVote:
    """Tests for Vote."""

    def test_vote_creation(self) -> None:
        """Test creating a vote."""
        vote = Vote(
            peer_name='peer1',
            decision=VoteDecision.APPROVE,
            signature='sig123',
        )
        assert vote.peer_name == 'peer1'
        assert vote.decision == VoteDecision.APPROVE
        assert vote.signature == 'sig123'
        assert vote.comment is None

    def test_vote_with_comment(self) -> None:
        """Test creating a vote with a comment."""
        vote = Vote(
            peer_name='peer1',
            decision=VoteDecision.REJECT,
            signature='sig123',
            comment='Risk too high',
        )
        assert vote.comment == 'Risk too high'

    def test_vote_serialization(self) -> None:
        """Test vote serialization to dict and back."""
        vote = Vote(
            peer_name='peer1',
            decision=VoteDecision.APPROVE,
            signature='sig123',
            comment='Looks good',
        )
        data = vote.to_dict()
        restored = Vote.from_dict(data)
        assert restored.peer_name == vote.peer_name
        assert restored.decision == vote.decision
        assert restored.signature == vote.signature
        assert restored.comment == vote.comment


class TestProposal:
    """Tests for Proposal."""

    def test_proposal_creation(self) -> None:
        """Test creating a proposal."""
        proposal = Proposal(
            id='prop-001',
            task_description='Deploy to production',
            risk_level=RiskLevel.CRITICAL,
            proposed_by='admin',
        )
        assert proposal.id == 'prop-001'
        assert proposal.task_description == 'Deploy to production'
        assert proposal.risk_level == RiskLevel.CRITICAL
        assert proposal.proposed_by == 'admin'

    def test_proposal_expiration(self) -> None:
        """Test proposal expiration."""
        # Expired proposal
        expired_proposal = Proposal(
            id='prop-001',
            task_description='Deploy to production',
            risk_level=RiskLevel.CRITICAL,
            proposed_by='admin',
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        assert expired_proposal.is_expired() is True

        # Non-expired proposal
        valid_proposal = Proposal(
            id='prop-002',
            task_description='Deploy to production',
            risk_level=RiskLevel.CRITICAL,
            proposed_by='admin',
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        assert valid_proposal.is_expired() is False

        # No expiration
        no_expiry_proposal = Proposal(
            id='prop-003',
            task_description='Deploy to production',
            risk_level=RiskLevel.CRITICAL,
            proposed_by='admin',
        )
        assert no_expiry_proposal.is_expired() is False

    def test_proposal_serialization(self) -> None:
        """Test proposal serialization to dict and back."""
        proposal = Proposal(
            id='prop-001',
            task_description='Deploy to production',
            risk_level=RiskLevel.HIGH,
            proposed_by='admin',
            metadata={'environment': 'production'},
        )
        data = proposal.to_dict()
        restored = Proposal.from_dict(data)
        assert restored.id == proposal.id
        assert restored.task_description == proposal.task_description
        assert restored.risk_level == proposal.risk_level
        assert restored.proposed_by == proposal.proposed_by
        assert restored.metadata == proposal.metadata


class TestConsensusState:
    """Tests for ConsensusState."""

    def test_consensus_state_creation(self) -> None:
        """Test creating a consensus state."""
        proposal = Proposal(
            id='prop-001',
            task_description='Deploy to production',
            risk_level=RiskLevel.HIGH,
            proposed_by='admin',
        )
        state = ConsensusState(proposal=proposal)
        assert state.proposal == proposal
        assert state.status == ConsensusStatus.PENDING
        assert len(state.votes) == 0

    def test_add_vote(self) -> None:
        """Test adding votes to consensus state."""
        proposal = Proposal(
            id='prop-001',
            task_description='Deploy to production',
            risk_level=RiskLevel.HIGH,
            proposed_by='admin',
        )
        state = ConsensusState(proposal=proposal)

        vote1 = Vote(peer_name='peer1', decision=VoteDecision.APPROVE, signature='sig1')
        vote2 = Vote(peer_name='peer2', decision=VoteDecision.APPROVE, signature='sig2')

        state.add_vote(vote1)
        state.add_vote(vote2)

        assert len(state.votes) == 2

    def test_get_vote(self) -> None:
        """Test retrieving a vote by peer name."""
        proposal = Proposal(
            id='prop-001',
            task_description='Deploy to production',
            risk_level=RiskLevel.HIGH,
            proposed_by='admin',
        )
        state = ConsensusState(proposal=proposal)

        vote = Vote(peer_name='peer1', decision=VoteDecision.APPROVE, signature='sig1')
        state.add_vote(vote)

        retrieved = state.get_vote('peer1')
        assert retrieved is not None
        assert retrieved.peer_name == 'peer1'

        not_found = state.get_vote('peer2')
        assert not_found is None

    def test_has_voted(self) -> None:
        """Test checking if a peer has voted."""
        proposal = Proposal(
            id='prop-001',
            task_description='Deploy to production',
            risk_level=RiskLevel.HIGH,
            proposed_by='admin',
        )
        state = ConsensusState(proposal=proposal)

        vote = Vote(peer_name='peer1', decision=VoteDecision.APPROVE, signature='sig1')
        state.add_vote(vote)

        assert state.has_voted('peer1') is True
        assert state.has_voted('peer2') is False

    def test_vote_counting(self) -> None:
        """Test counting votes by decision."""
        proposal = Proposal(
            id='prop-001',
            task_description='Deploy to production',
            risk_level=RiskLevel.HIGH,
            proposed_by='admin',
        )
        state = ConsensusState(proposal=proposal)

        state.add_vote(Vote(peer_name='peer1', decision=VoteDecision.APPROVE, signature='sig1'))
        state.add_vote(Vote(peer_name='peer2', decision=VoteDecision.APPROVE, signature='sig2'))
        state.add_vote(Vote(peer_name='peer3', decision=VoteDecision.REJECT, signature='sig3'))
        state.add_vote(Vote(peer_name='peer4', decision=VoteDecision.ABSTAIN, signature='sig4'))

        assert state.get_vote_count(VoteDecision.APPROVE) == 2
        assert state.get_vote_count(VoteDecision.REJECT) == 1
        assert state.get_vote_count(VoteDecision.ABSTAIN) == 1

    def test_quorum_calculation_simple_majority(self) -> None:
        """Test quorum calculation with simple majority."""
        proposal = Proposal(
            id='prop-001',
            task_description='Deploy to production',
            risk_level=RiskLevel.HIGH,
            proposed_by='admin',
        )
        state = ConsensusState(
            proposal=proposal,
            voting_threshold=VotingThreshold.SIMPLE_MAJORITY,
            required_peers={'peer1', 'peer2', 'peer3'},
        )
        # 3 peers, simple majority = 2
        assert state.get_quorum_size() == 2

    def test_quorum_calculation_supermajority(self) -> None:
        """Test quorum calculation with supermajority."""
        proposal = Proposal(
            id='prop-001',
            task_description='Deploy to production',
            risk_level=RiskLevel.HIGH,
            proposed_by='admin',
        )
        state = ConsensusState(
            proposal=proposal,
            voting_threshold=VotingThreshold.SUPERMAJORITY,
            required_peers={'peer1', 'peer2', 'peer3'},
        )
        # 3 peers, supermajority = 3 (2/3 rounded up)
        assert state.get_quorum_size() == 3

    def test_quorum_calculation_unanimous(self) -> None:
        """Test quorum calculation with unanimous."""
        proposal = Proposal(
            id='prop-001',
            task_description='Deploy to production',
            risk_level=RiskLevel.HIGH,
            proposed_by='admin',
        )
        state = ConsensusState(
            proposal=proposal,
            voting_threshold=VotingThreshold.UNANIMOUS,
            required_peers={'peer1', 'peer2', 'peer3'},
        )
        # 3 peers, unanimous = 3
        assert state.get_quorum_size() == 3

    def test_has_quorum(self) -> None:
        """Test checking if quorum is reached."""
        proposal = Proposal(
            id='prop-001',
            task_description='Deploy to production',
            risk_level=RiskLevel.HIGH,
            proposed_by='admin',
        )
        state = ConsensusState(
            proposal=proposal,
            voting_threshold=VotingThreshold.SIMPLE_MAJORITY,
            required_peers={'peer1', 'peer2', 'peer3'},
        )

        state.add_vote(Vote(peer_name='peer1', decision=VoteDecision.APPROVE, signature='sig1'))
        assert state.has_quorum() is False

        state.add_vote(Vote(peer_name='peer2', decision=VoteDecision.APPROVE, signature='sig2'))
        assert state.has_quorum() is True

    def test_is_approved_simple_majority(self) -> None:
        """Test approval with simple majority."""
        proposal = Proposal(
            id='prop-001',
            task_description='Deploy to production',
            risk_level=RiskLevel.HIGH,
            proposed_by='admin',
        )
        state = ConsensusState(
            proposal=proposal,
            voting_threshold=VotingThreshold.SIMPLE_MAJORITY,
            required_peers={'peer1', 'peer2', 'peer3'},
        )

        state.add_vote(Vote(peer_name='peer1', decision=VoteDecision.APPROVE, signature='sig1'))
        state.add_vote(Vote(peer_name='peer2', decision=VoteDecision.APPROVE, signature='sig2'))
        state.add_vote(Vote(peer_name='peer3', decision=VoteDecision.REJECT, signature='sig3'))

        assert state.is_approved() is True  # 2/3 approve > 50%

    def test_is_approved_rejected(self) -> None:
        """Test rejection when votes are against."""
        proposal = Proposal(
            id='prop-001',
            task_description='Deploy to production',
            risk_level=RiskLevel.HIGH,
            proposed_by='admin',
        )
        state = ConsensusState(
            proposal=proposal,
            voting_threshold=VotingThreshold.SIMPLE_MAJORITY,
            required_peers={'peer1', 'peer2', 'peer3'},
        )

        state.add_vote(Vote(peer_name='peer1', decision=VoteDecision.APPROVE, signature='sig1'))
        state.add_vote(Vote(peer_name='peer2', decision=VoteDecision.REJECT, signature='sig2'))
        state.add_vote(Vote(peer_name='peer3', decision=VoteDecision.REJECT, signature='sig3'))

        assert state.is_approved() is False  # 1/3 approve < 50%

    def test_is_approved_unanimous(self) -> None:
        """Test approval with unanimous requirement."""
        proposal = Proposal(
            id='prop-001',
            task_description='Deploy to production',
            risk_level=RiskLevel.HIGH,
            proposed_by='admin',
        )
        state = ConsensusState(
            proposal=proposal,
            voting_threshold=VotingThreshold.UNANIMOUS,
            required_peers={'peer1', 'peer2', 'peer3'},
        )

        state.add_vote(Vote(peer_name='peer1', decision=VoteDecision.APPROVE, signature='sig1'))
        state.add_vote(Vote(peer_name='peer2', decision=VoteDecision.APPROVE, signature='sig2'))
        state.add_vote(Vote(peer_name='peer3', decision=VoteDecision.REJECT, signature='sig3'))

        assert state.is_approved() is False  # Not unanimous

        state.votes = [
            Vote(peer_name='peer1', decision=VoteDecision.APPROVE, signature='sig1'),
            Vote(peer_name='peer2', decision=VoteDecision.APPROVE, signature='sig2'),
            Vote(peer_name='peer3', decision=VoteDecision.APPROVE, signature='sig3'),
        ]
        assert state.is_approved() is True  # Unanimous

    def test_consensus_state_serialization(self) -> None:
        """Test consensus state serialization to dict and back."""
        proposal = Proposal(
            id='prop-001',
            task_description='Deploy to production',
            risk_level=RiskLevel.HIGH,
            proposed_by='admin',
        )
        state = ConsensusState(
            proposal=proposal,
            status=ConsensusStatus.VOTING,
            required_peers={'peer1', 'peer2'},
        )
        state.add_vote(Vote(peer_name='peer1', decision=VoteDecision.APPROVE, signature='sig1'))

        data = state.to_dict()
        restored = ConsensusState.from_dict(data)
        assert restored.proposal.id == state.proposal.id
        assert restored.status == state.status
        assert len(restored.votes) == len(state.votes)
        assert restored.required_peers == state.required_peers


class TestConsensusConfig:
    """Tests for ConsensusConfig."""

    def test_config_creation(self) -> None:
        """Test creating consensus config."""
        config = ConsensusConfig()
        assert config.default_voting_threshold == VotingThreshold.SUPERMAJORITY
        assert config.consensus_timeout_seconds == 300
        assert config.require_all_peers is False

    def test_config_custom_values(self) -> None:
        """Test creating config with custom values."""
        config = ConsensusConfig(
            default_voting_threshold=VotingThreshold.UNANIMOUS,
            consensus_timeout_seconds=600,
            require_all_peers=True,
        )
        assert config.default_voting_threshold == VotingThreshold.UNANIMOUS
        assert config.consensus_timeout_seconds == 600
        assert config.require_all_peers is True

    def test_config_serialization(self) -> None:
        """Test config serialization to dict and back."""
        config = ConsensusConfig(
            default_voting_threshold=VotingThreshold.SIMPLE_MAJORITY,
            consensus_timeout_seconds=120,
            pre_approved_patterns=['security-scan', 'code-review'],
        )
        data = config.to_dict()
        restored = ConsensusConfig.from_dict(data)
        assert restored.default_voting_threshold == config.default_voting_threshold
        assert restored.consensus_timeout_seconds == config.consensus_timeout_seconds
        assert restored.pre_approved_patterns == config.pre_approved_patterns


class TestPeerRegistry:
    """Tests for PeerRegistry."""

    def test_registry_in_memory(self) -> None:
        """Test in-memory peer registry."""
        registry = PeerRegistry()
        peer = PeerIdentity(
            name='peer1',
            ssh_public_key='ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ...',
        )

        registry.register(peer)
        assert registry.get('peer1') == peer
        assert len(registry.list_all()) == 1

    def test_registry_duplicate_error(self) -> None:
        """Test that duplicate peer registration raises error."""
        registry = PeerRegistry()
        peer1 = PeerIdentity(
            name='peer1',
            ssh_public_key='ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ...',
        )
        peer2 = PeerIdentity(
            name='peer1',
            ssh_public_key='ssh-rsa BBBB3NzaC1yc2EAAAADAQABAAABAQ...',
        )

        registry.register(peer1)
        with pytest.raises(ValueError, match='already registered'):
            registry.register(peer2)

    def test_registry_unregister(self) -> None:
        """Test unregistering a peer."""
        registry = PeerRegistry()
        peer = PeerIdentity(
            name='peer1',
            ssh_public_key='ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ...',
        )

        registry.register(peer)
        assert registry.get('peer1') is not None

        unregistered = registry.unregister('peer1')
        assert unregistered == peer
        assert registry.get('peer1') is None

    def test_registry_list_active(self) -> None:
        """Test listing only active peers."""
        registry = PeerRegistry()
        peer1 = PeerIdentity(
            name='peer1',
            ssh_public_key='ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ...',
            is_active=True,
        )
        peer2 = PeerIdentity(
            name='peer2',
            ssh_public_key='ssh-rsa BBBB3NzaC1yc2EAAAADAQABAAABAQ...',
            is_active=False,
        )

        registry.register(peer1)
        registry.register(peer2)

        assert len(registry.list_all()) == 2
        assert len(registry.list_active()) == 1
        assert registry.list_active()[0].name == 'peer1'

    def test_registry_activate_deactivate(self) -> None:
        """Test activating and deactivating peers."""
        registry = PeerRegistry()
        peer = PeerIdentity(
            name='peer1',
            ssh_public_key='ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ...',
            is_active=True,
        )

        registry.register(peer)
        assert registry.get('peer1').is_active is True

        registry.deactivate('peer1')
        assert registry.get('peer1').is_active is False

        registry.activate('peer1')
        assert registry.get('peer1').is_active is True

    def test_registry_key_rotation(self) -> None:
        """Test rotating SSH keys."""
        registry = PeerRegistry()
        peer = PeerIdentity(
            name='peer1',
            ssh_public_key='ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ...',
        )

        registry.register(peer)
        old_fingerprint = registry.get('peer1').fingerprint

        registry.rotate_key('peer1', 'ssh-rsa BBBB3NzaC1yc2EAAAADAQABAAABAQ...')
        new_fingerprint = registry.get('peer1').fingerprint

        assert old_fingerprint != new_fingerprint

    def test_registry_verify_peer(self) -> None:
        """Test verifying peer signatures."""
        registry = PeerRegistry()
        peer = PeerIdentity(
            name='peer1',
            ssh_public_key='ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ...',
        )

        registry.register(peer)
        message = 'test message'
        signature = hashlib.sha256((message + peer.ssh_public_key).encode()).hexdigest()

        assert registry.verify_peer('peer1', message, signature) is True
        assert registry.verify_peer('peer1', message, 'invalid') is False
        assert registry.verify_peer('nonexistent', message, signature) is False

    def test_registry_verify_inactive_peer(self) -> None:
        """Test that inactive peers cannot verify signatures."""
        registry = PeerRegistry()
        peer = PeerIdentity(
            name='peer1',
            ssh_public_key='ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ...',
            is_active=False,
        )

        registry.register(peer)
        message = 'test message'
        signature = hashlib.sha256((message + peer.ssh_public_key).encode()).hexdigest()

        assert registry.verify_peer('peer1', message, signature) is False

    def test_registry_persistence(self) -> None:
        """Test registry persistence to file."""
        with TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / 'peers.json'

            # Create registry and add peer
            registry1 = PeerRegistry(storage_path=storage_path)
            peer = PeerIdentity(
                name='peer1',
                ssh_public_key='ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ...',
            )
            registry1.register(peer)

            # Create new registry instance (should load from file)
            registry2 = PeerRegistry(storage_path=storage_path)
            loaded_peer = registry2.get('peer1')

            assert loaded_peer is not None
            assert loaded_peer.name == peer.name
            assert loaded_peer.ssh_public_key == peer.ssh_public_key

    def test_registry_persistence_empty(self) -> None:
        """Test loading from non-existent file."""
        with TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / 'nonexistent.json'
            registry = PeerRegistry(storage_path=storage_path)
            assert len(registry.list_all()) == 0


class TestVotingMechanism:
    """Tests for VotingMechanism."""

    def test_initiate_voting(self) -> None:
        """Test initiating voting on a proposal."""
        config = ConsensusConfig()
        mechanism = VotingMechanism(config)

        proposal = Proposal(
            id='prop-001',
            task_description='Deploy to production',
            risk_level=RiskLevel.HIGH,
            proposed_by='admin',
        )

        state = mechanism.initiate_voting(
            proposal=proposal,
            required_peers={'peer1', 'peer2', 'peer3'},
        )

        assert state.proposal == proposal
        assert state.status == ConsensusStatus.VOTING
        assert state.required_peers == {'peer1', 'peer2', 'peer3'}
        assert state.started_at is not None

    def test_cast_vote(self) -> None:
        """Test casting a vote."""
        config = ConsensusConfig()
        mechanism = VotingMechanism(config)

        proposal = Proposal(
            id='prop-001',
            task_description='Deploy to production',
            risk_level=RiskLevel.HIGH,
            proposed_by='admin',
        )

        mechanism.initiate_voting(
            proposal=proposal,
            required_peers={'peer1', 'peer2'},
        )

        success = mechanism.cast_vote(
            proposal_id='prop-001',
            peer_name='peer1',
            decision=VoteDecision.APPROVE,
            signature='sig1',
        )

        assert success is True
        state = mechanism.get_state('prop-001')
        assert state.get_vote_count(VoteDecision.APPROVE) == 1

    def test_cast_vote_duplicate(self) -> None:
        """Test that duplicate votes are rejected."""
        config = ConsensusConfig()
        mechanism = VotingMechanism(config)

        proposal = Proposal(
            id='prop-001',
            task_description='Deploy to production',
            risk_level=RiskLevel.HIGH,
            proposed_by='admin',
        )

        mechanism.initiate_voting(
            proposal=proposal,
            required_peers={'peer1', 'peer2'},
        )

        mechanism.cast_vote(
            proposal_id='prop-001',
            peer_name='peer1',
            decision=VoteDecision.APPROVE,
            signature='sig1',
        )

        success = mechanism.cast_vote(
            proposal_id='prop-001',
            peer_name='peer1',
            decision=VoteDecision.REJECT,
            signature='sig2',
        )

        assert success is False

    def test_cast_vote_closed(self) -> None:
        """Test that votes cannot be cast on closed proposals."""
        config = ConsensusConfig()
        mechanism = VotingMechanism(config)

        proposal = Proposal(
            id='prop-001',
            task_description='Deploy to production',
            risk_level=RiskLevel.HIGH,
            proposed_by='admin',
        )

        state = mechanism.initiate_voting(
            proposal=proposal,
            required_peers={'peer1', 'peer2'},
        )
        state.status = ConsensusStatus.APPROVED

        success = mechanism.cast_vote(
            proposal_id='prop-001',
            peer_name='peer1',
            decision=VoteDecision.APPROVE,
            signature='sig1',
        )

        assert success is False

    def test_cancel_vote(self) -> None:
        """Test cancelling a vote."""
        config = ConsensusConfig()
        mechanism = VotingMechanism(config)

        proposal = Proposal(
            id='prop-001',
            task_description='Deploy to production',
            risk_level=RiskLevel.HIGH,
            proposed_by='admin',
        )

        mechanism.initiate_voting(
            proposal=proposal,
            required_peers={'peer1', 'peer2'},
        )

        mechanism.cast_vote(
            proposal_id='prop-001',
            peer_name='peer1',
            decision=VoteDecision.APPROVE,
            signature='sig1',
        )

        success = mechanism.cancel_vote('prop-001', 'peer1')
        assert success is True

        state = mechanism.get_state('prop-001')
        assert state.get_vote_count(VoteDecision.APPROVE) == 0

    def test_check_timeout(self) -> None:
        """Test timeout checking."""
        config = ConsensusConfig(consensus_timeout_seconds=1)
        mechanism = VotingMechanism(config)

        proposal = Proposal(
            id='prop-001',
            task_description='Deploy to production',
            risk_level=RiskLevel.HIGH,
            proposed_by='admin',
        )

        mechanism.initiate_voting(
            proposal=proposal,
            required_peers={'peer1', 'peer2'},
        )

        # Should not timeout immediately
        assert mechanism.check_timeout('prop-001') is False

        # Wait for timeout
        time.sleep(1.1)
        assert mechanism.check_timeout('prop-001') is True

        state = mechanism.get_state('prop-001')
        assert state.status == ConsensusStatus.TIMEOUT

    def test_close_voting_approved(self) -> None:
        """Test closing voting with approval."""
        config = ConsensusConfig()
        mechanism = VotingMechanism(config)

        proposal = Proposal(
            id='prop-001',
            task_description='Deploy to production',
            risk_level=RiskLevel.HIGH,
            proposed_by='admin',
        )

        mechanism.initiate_voting(
            proposal=proposal,
            required_peers={'peer1', 'peer2', 'peer3'},
            threshold=VotingThreshold.SIMPLE_MAJORITY,
        )

        mechanism.cast_vote('prop-001', 'peer1', VoteDecision.APPROVE, 'sig1')
        mechanism.cast_vote('prop-001', 'peer2', VoteDecision.APPROVE, 'sig2')
        mechanism.cast_vote('prop-001', 'peer3', VoteDecision.REJECT, 'sig3')

        state = mechanism.close_voting('prop-001')
        assert state.status == ConsensusStatus.APPROVED

    def test_close_voting_rejected(self) -> None:
        """Test closing voting with rejection."""
        config = ConsensusConfig()
        mechanism = VotingMechanism(config)

        proposal = Proposal(
            id='prop-001',
            task_description='Deploy to production',
            risk_level=RiskLevel.HIGH,
            proposed_by='admin',
        )

        mechanism.initiate_voting(
            proposal=proposal,
            required_peers={'peer1', 'peer2', 'peer3'},
            threshold=VotingThreshold.SIMPLE_MAJORITY,
        )

        mechanism.cast_vote('prop-001', 'peer1', VoteDecision.APPROVE, 'sig1')
        mechanism.cast_vote('prop-001', 'peer2', VoteDecision.REJECT, 'sig2')
        mechanism.cast_vote('prop-001', 'peer3', VoteDecision.REJECT, 'sig3')

        state = mechanism.close_voting('prop-001')
        assert state.status == ConsensusStatus.REJECTED

    def test_list_active_votings(self) -> None:
        """Test listing active votings."""
        config = ConsensusConfig()
        mechanism = VotingMechanism(config)

        proposal1 = Proposal(
            id='prop-001',
            task_description='Deploy to production',
            risk_level=RiskLevel.HIGH,
            proposed_by='admin',
        )
        proposal2 = Proposal(
            id='prop-002',
            task_description='Run security scan',
            risk_level=RiskLevel.LOW,
            proposed_by='admin',
        )

        mechanism.initiate_voting(proposal1, {'peer1', 'peer2'})
        mechanism.initiate_voting(proposal2, {'peer1', 'peer2'})

        # Close one
        mechanism.close_voting('prop-001')

        active = mechanism.list_active_votings()
        assert len(active) == 1
        assert active[0].proposal.id == 'prop-002'

    def test_cleanup_completed(self) -> None:
        """Test cleanup of completed voting states."""
        config = ConsensusConfig()
        mechanism = VotingMechanism(config)

        proposal = Proposal(
            id='prop-001',
            task_description='Deploy to production',
            risk_level=RiskLevel.HIGH,
            proposed_by='admin',
        )

        mechanism.initiate_voting(proposal, {'peer1', 'peer2'})
        mechanism.close_voting('prop-001')

        # Should not cleanup with a small threshold
        removed = mechanism.cleanup_completed(older_than_seconds=0.1)
        assert removed == 0

        # Cleanup after 1 second
        time.sleep(1.1)
        removed = mechanism.cleanup_completed(older_than_seconds=1)
        assert removed == 1

        assert mechanism.get_state('prop-001') is None


class TestConsensusEngine:
    """Tests for ConsensusEngine."""

    def test_request_consensus(self) -> None:
        """Test requesting consensus for a task."""
        registry = PeerRegistry()
        peer1 = PeerIdentity(name='peer1', ssh_public_key='ssh-rsa key1')
        peer2 = PeerIdentity(name='peer2', ssh_public_key='ssh-rsa key2')
        registry.register(peer1)
        registry.register(peer2)

        config = ConsensusConfig()
        engine = ConsensusEngine(peer_registry=registry, config=config)

        state = engine.request_consensus(
            task_description='Deploy to production',
            risk_level=RiskLevel.HIGH,
            proposed_by='admin',
        )

        assert state.proposal.task_description == 'Deploy to production'
        assert state.status == ConsensusStatus.VOTING
        assert state.required_peers == {'peer1', 'peer2'}

    def test_request_consensus_custom_peers(self) -> None:
        """Test requesting consensus with custom peer set."""
        registry = PeerRegistry()
        peer1 = PeerIdentity(name='peer1', ssh_public_key='ssh-rsa key1')
        peer2 = PeerIdentity(name='peer2', ssh_public_key='ssh-rsa key2')
        peer3 = PeerIdentity(name='peer3', ssh_public_key='ssh-rsa key3')
        registry.register(peer1)
        registry.register(peer2)
        registry.register(peer3)

        config = ConsensusConfig()
        engine = ConsensusEngine(peer_registry=registry, config=config)

        state = engine.request_consensus(
            task_description='Deploy to production',
            risk_level=RiskLevel.HIGH,
            proposed_by='admin',
            required_peers={'peer1', 'peer2'},
        )

        assert state.required_peers == {'peer1', 'peer2'}

    def test_request_consensus_no_peers(self) -> None:
        """Test that consensus request fails with no peers."""
        registry = PeerRegistry()
        config = ConsensusConfig()
        engine = ConsensusEngine(peer_registry=registry, config=config)

        with pytest.raises(ValueError, match='No active peers'):
            engine.request_consensus(
                task_description='Deploy to production',
                risk_level=RiskLevel.HIGH,
                proposed_by='admin',
            )

    def test_submit_vote(self) -> None:
        """Test submitting a vote."""
        registry = PeerRegistry()
        peer1 = PeerIdentity(name='peer1', ssh_public_key='ssh-rsa key1')
        registry.register(peer1)

        config = ConsensusConfig()
        engine = ConsensusEngine(peer_registry=registry, config=config)

        state = engine.request_consensus(
            task_description='Deploy to production',
            risk_level=RiskLevel.HIGH,
            proposed_by='admin',
        )

        signature = hashlib.sha256((state.proposal.task_description + peer1.ssh_public_key).encode()).hexdigest()
        success = engine.submit_vote(
            proposal_id=state.proposal.id,
            peer_name='peer1',
            decision=VoteDecision.APPROVE,
            signature=signature,
        )

        assert success is True
        updated_state = engine.get_consensus_status(state.proposal.id)
        assert updated_state.get_vote_count(VoteDecision.APPROVE) == 1

    def test_submit_vote_invalid_signature(self) -> None:
        """Test that invalid signatures are rejected."""
        registry = PeerRegistry()
        peer1 = PeerIdentity(name='peer1', ssh_public_key='ssh-rsa key1')
        registry.register(peer1)

        config = ConsensusConfig()
        engine = ConsensusEngine(peer_registry=registry, config=config)

        state = engine.request_consensus(
            task_description='Deploy to production',
            risk_level=RiskLevel.HIGH,
            proposed_by='admin',
        )

        success = engine.submit_vote(
            proposal_id=state.proposal.id,
            peer_name='peer1',
            decision=VoteDecision.APPROVE,
            signature='invalid_signature',
        )

        assert success is False

    def test_get_consensus_status(self) -> None:
        """Test getting consensus status."""
        registry = PeerRegistry()
        peer1 = PeerIdentity(name='peer1', ssh_public_key='ssh-rsa key1')
        registry.register(peer1)

        config = ConsensusConfig()
        engine = ConsensusEngine(peer_registry=registry, config=config)

        state = engine.request_consensus(
            task_description='Deploy to production',
            risk_level=RiskLevel.HIGH,
            proposed_by='admin',
        )

        retrieved = engine.get_consensus_status(state.proposal.id)
        assert retrieved is not None
        assert retrieved.proposal.id == state.proposal.id

    def test_get_consensus_status_expired(self) -> None:
        """Test that expired proposals are marked as timeout."""
        registry = PeerRegistry()
        peer1 = PeerIdentity(name='peer1', ssh_public_key='ssh-rsa key1')
        registry.register(peer1)

        config = ConsensusConfig()
        engine = ConsensusEngine(peer_registry=registry, config=config)

        state = engine.request_consensus(
            task_description='Deploy to production',
            risk_level=RiskLevel.HIGH,
            proposed_by='admin',
            expires_in_seconds=0.1,
        )

        time.sleep(0.2)
        retrieved = engine.get_consensus_status(state.proposal.id)
        assert retrieved.status == ConsensusStatus.TIMEOUT

    def test_generate_attestation(self) -> None:
        """Test generating attestation for approved proposal."""
        registry = PeerRegistry()
        peer1 = PeerIdentity(name='peer1', ssh_public_key='ssh-rsa key1')
        peer2 = PeerIdentity(name='peer2', ssh_public_key='ssh-rsa key2')
        registry.register(peer1)
        registry.register(peer2)

        config = ConsensusConfig()
        engine = ConsensusEngine(peer_registry=registry, config=config)

        state = engine.request_consensus(
            task_description='Deploy to production',
            risk_level=RiskLevel.HIGH,
            proposed_by='admin',
            threshold=VotingThreshold.SIMPLE_MAJORITY,
        )

        # Submit approving votes
        sig1 = hashlib.sha256((state.proposal.task_description + peer1.ssh_public_key).encode()).hexdigest()
        sig2 = hashlib.sha256((state.proposal.task_description + peer2.ssh_public_key).encode()).hexdigest()
        engine.submit_vote(state.proposal.id, 'peer1', VoteDecision.APPROVE, sig1)
        engine.submit_vote(state.proposal.id, 'peer2', VoteDecision.APPROVE, sig2)

        attestation = engine.generate_attestation(state.proposal.id)
        assert attestation is not None
        assert attestation['proposal_id'] == state.proposal.id
        assert 'peer1' in attestation['approved_by']
        assert 'peer2' in attestation['approved_by']

    def test_generate_attestation_not_approved(self) -> None:
        """Test that attestation fails for non-approved proposal."""
        registry = PeerRegistry()
        peer1 = PeerIdentity(name='peer1', ssh_public_key='ssh-rsa key1')
        registry.register(peer1)

        config = ConsensusConfig()
        engine = ConsensusEngine(peer_registry=registry, config=config)

        state = engine.request_consensus(
            task_description='Deploy to production',
            risk_level=RiskLevel.HIGH,
            proposed_by='admin',
        )

        attestation = engine.generate_attestation(state.proposal.id)
        assert attestation is None

    def test_cancel_consensus(self) -> None:
        """Test cancelling an active consensus."""
        registry = PeerRegistry()
        peer1 = PeerIdentity(name='peer1', ssh_public_key='ssh-rsa key1')
        registry.register(peer1)

        config = ConsensusConfig()
        engine = ConsensusEngine(peer_registry=registry, config=config)

        state = engine.request_consensus(
            task_description='Deploy to production',
            risk_level=RiskLevel.HIGH,
            proposed_by='admin',
        )

        success = engine.cancel_consensus(state.proposal.id, 'admin')
        assert success is True

        retrieved = engine.get_consensus_status(state.proposal.id)
        assert retrieved.status == ConsensusStatus.CANCELLED

    def test_resolve_conflict(self) -> None:
        """Test resolving a conflict in consensus."""
        registry = PeerRegistry()
        peer1 = PeerIdentity(name='peer1', ssh_public_key='ssh-rsa key1')
        registry.register(peer1)

        config = ConsensusConfig()
        engine = ConsensusEngine(peer_registry=registry, config=config)

        state = engine.request_consensus(
            task_description='Deploy to production',
            risk_level=RiskLevel.HIGH,
            proposed_by='admin',
        )

        success = engine.resolve_conflict(state.proposal.id, 'Manual override approved')
        assert success is True

        retrieved = engine.get_consensus_status(state.proposal.id)
        assert retrieved.proposal.metadata['conflict_resolution'] == 'Manual override approved'

    def test_list_active_consensus(self) -> None:
        """Test listing active consensus requests."""
        registry = PeerRegistry()
        peer1 = PeerIdentity(name='peer1', ssh_public_key='ssh-rsa key1')
        registry.register(peer1)

        config = ConsensusConfig()
        engine = ConsensusEngine(peer_registry=registry, config=config)

        state1 = engine.request_consensus(
            task_description='Deploy to production',
            risk_level=RiskLevel.HIGH,
            proposed_by='admin',
        )
        state2 = engine.request_consensus(
            task_description='Run security scan',
            risk_level=RiskLevel.LOW,
            proposed_by='admin',
        )

        # Close one
        engine.voting_mechanism.close_voting(state1.proposal.id)

        active = engine.list_active_consensus()
        assert len(active) == 1
        assert active[0].proposal.id == state2.proposal.id

    def test_engine_persistence(self) -> None:
        """Test consensus engine persistence."""
        with TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / 'consensus.json'

            registry = PeerRegistry()
            peer1 = PeerIdentity(name='peer1', ssh_public_key='ssh-rsa key1')
            registry.register(peer1)

            config = ConsensusConfig()
            engine1 = ConsensusEngine(peer_registry=registry, config=config, storage_path=storage_path)

            state = engine1.request_consensus(
                task_description='Deploy to production',
                risk_level=RiskLevel.HIGH,
                proposed_by='admin',
            )

            # Create new engine instance (should load from file)
            engine2 = ConsensusEngine(peer_registry=registry, config=config, storage_path=storage_path)
            loaded_state = engine2.get_consensus_status(state.proposal.id)

            assert loaded_state is not None
            assert loaded_state.proposal.id == state.proposal.id

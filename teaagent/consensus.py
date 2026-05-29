"""Consensus system for federated swarm coordination.

This module provides data structures and logic for peer-to-peer consensus
in multi-agent swarms, including peer identity management, voting mechanisms,
and consensus state tracking.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Risk classification for proposals and tool calls."""

    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    CRITICAL = 'critical'


class VoteDecision(Enum):
    """Possible vote decisions from peers."""

    APPROVE = 'approve'
    REJECT = 'reject'
    ABSTAIN = 'abstain'


class ConsensusStatus(Enum):
    """Status of a consensus process."""

    PENDING = 'pending'
    VOTING = 'voting'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    TIMEOUT = 'timeout'
    CANCELLED = 'cancelled'


class VotingThreshold(Enum):
    """Voting threshold configurations."""

    SIMPLE_MAJORITY = 'simple_majority'  # > 50%
    SUPERMAJORITY = 'supermajority'  # > 66.6%
    UNANIMOUS = 'unanimous'  # 100%
    CUSTOM = 'custom'  # Custom percentage


@dataclass(frozen=True)
class PeerIdentity:
    """Identity of a peer in the swarm."""

    name: str
    ssh_public_key: str
    fingerprint: str = field(init=False)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    is_active: bool = True

    def __post_init__(self) -> None:
        """Compute fingerprint from SSH public key."""
        # Generate fingerprint from SSH public key
        key_bytes = self.ssh_public_key.encode('utf-8')
        fingerprint = hashlib.sha256(key_bytes).hexdigest()[:16]
        object.__setattr__(self, 'fingerprint', fingerprint)

    def verify_signature(self, message: str, signature: str) -> bool:
        """Verify a signature from this peer.

        Args:
            message: The message that was signed
            signature: The signature to verify

        Returns:
            True if signature is valid, False otherwise
        """
        try:
            # Parse SSH public key
            # This is a simplified version - in production, use proper SSH key parsing
            # For now, we'll use a simple hash-based verification
            # In production, this should use proper SSH signature verification
            expected_sig = hashlib.sha256(
                (message + self.ssh_public_key).encode()
            ).hexdigest()
            return signature == expected_sig
        except (ValueError, TypeError) as exc:
            logger.debug('Signature verification failed: %s', exc)
            return False


@dataclass
class Vote:
    """A vote from a peer on a proposal."""

    peer_name: str
    decision: VoteDecision
    signature: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    comment: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert vote to dictionary for serialization."""
        return {
            'peer_name': self.peer_name,
            'decision': self.decision.value,
            'signature': self.signature,
            'timestamp': self.timestamp.isoformat(),
            'comment': self.comment,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> Vote:
        """Create vote from dictionary."""
        return cls(
            peer_name=data['peer_name'],
            decision=VoteDecision(data['decision']),
            signature=data['signature'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            comment=data.get('comment'),
        )


@dataclass
class Proposal:
    """A proposal requiring consensus."""

    id: str
    task_description: str
    risk_level: RiskLevel
    proposed_by: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convert proposal to dictionary for serialization."""
        return {
            'id': self.id,
            'task_description': self.task_description,
            'risk_level': self.risk_level.value,
            'proposed_by': self.proposed_by,
            'created_at': self.created_at.isoformat(),
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'metadata': self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> Proposal:
        """Create proposal from dictionary."""
        return cls(
            id=data['id'],
            task_description=data['task_description'],
            risk_level=RiskLevel(data['risk_level']),
            proposed_by=data['proposed_by'],
            created_at=datetime.fromisoformat(data['created_at']),
            expires_at=datetime.fromisoformat(data['expires_at'])
            if data.get('expires_at')
            else None,
            metadata=data.get('metadata', {}),
        )

    def is_expired(self) -> bool:
        """Check if proposal has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at


@dataclass
class ConsensusState:
    """State of a consensus process."""

    proposal: Proposal
    status: ConsensusStatus = ConsensusStatus.PENDING
    votes: List[Vote] = field(default_factory=list)
    voting_threshold: VotingThreshold = VotingThreshold.SUPERMAJORITY
    custom_threshold: Optional[float] = None  # For CUSTOM threshold
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    required_peers: Set[str] = field(default_factory=set)

    def add_vote(self, vote: Vote) -> None:
        """Add a vote to the consensus state."""
        self.votes.append(vote)

    def get_vote(self, peer_name: str) -> Optional[Vote]:
        """Get a vote from a specific peer."""
        for vote in self.votes:
            if vote.peer_name == peer_name:
                return vote
        return None

    def has_voted(self, peer_name: str) -> bool:
        """Check if a peer has voted."""
        return self.get_vote(peer_name) is not None

    def get_vote_count(self, decision: VoteDecision) -> int:
        """Count votes with a specific decision."""
        return sum(1 for vote in self.votes if vote.decision == decision)

    def get_total_votes(self) -> int:
        """Get total number of votes."""
        return len(self.votes)

    def get_quorum_size(self) -> int:
        """Calculate required quorum size based on threshold."""
        total_peers = len(self.required_peers) if self.required_peers else 1

        if self.voting_threshold == VotingThreshold.SIMPLE_MAJORITY:
            return (total_peers // 2) + 1
        elif self.voting_threshold == VotingThreshold.SUPERMAJORITY:
            return (total_peers * 2) // 3 + 1
        elif self.voting_threshold == VotingThreshold.UNANIMOUS:
            return total_peers
        elif self.voting_threshold == VotingThreshold.CUSTOM and self.custom_threshold:
            return int(total_peers * self.custom_threshold) + 1
        else:
            return (total_peers // 2) + 1

    def has_quorum(self) -> bool:
        """Check if quorum has been reached."""
        required = self.get_quorum_size()
        return self.get_total_votes() >= required

    def is_approved(self) -> bool:
        """Check if proposal is approved based on votes."""
        if not self.has_quorum():
            return False

        total_votes = self.get_total_votes()
        approve_votes = self.get_vote_count(VoteDecision.APPROVE)
        reject_votes = self.get_vote_count(VoteDecision.REJECT)

        # Calculate required approval ratio
        if self.voting_threshold == VotingThreshold.SIMPLE_MAJORITY:
            return approve_votes > (total_votes / 2)
        elif self.voting_threshold == VotingThreshold.SUPERMAJORITY:
            return approve_votes > (total_votes * 2 / 3)
        elif self.voting_threshold == VotingThreshold.UNANIMOUS:
            return reject_votes == 0 and approve_votes == total_votes
        elif self.voting_threshold == VotingThreshold.CUSTOM and self.custom_threshold:
            return (approve_votes / total_votes) >= self.custom_threshold
        else:
            return approve_votes > (total_votes / 2)

    def to_dict(self) -> Dict:
        """Convert consensus state to dictionary for serialization."""
        return {
            'proposal': self.proposal.to_dict(),
            'status': self.status.value,
            'votes': [vote.to_dict() for vote in self.votes],
            'voting_threshold': self.voting_threshold.value,
            'custom_threshold': self.custom_threshold,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat()
            if self.completed_at
            else None,
            'required_peers': list(self.required_peers),
        }

    @classmethod
    def from_dict(cls, data: Dict) -> ConsensusState:
        """Create consensus state from dictionary."""
        return cls(
            proposal=Proposal.from_dict(data['proposal']),
            status=ConsensusStatus(data['status']),
            votes=[Vote.from_dict(v) for v in data['votes']],
            voting_threshold=VotingThreshold(data['voting_threshold']),
            custom_threshold=data.get('custom_threshold'),
            started_at=datetime.fromisoformat(data['started_at'])
            if data.get('started_at')
            else None,
            completed_at=datetime.fromisoformat(data['completed_at'])
            if data.get('completed_at')
            else None,
            required_peers=set(data.get('required_peers', [])),
        )


@dataclass
class ConsensusConfig:
    """Configuration for consensus system."""

    default_voting_threshold: VotingThreshold = VotingThreshold.SUPERMAJORITY
    default_custom_threshold: Optional[float] = None
    consensus_timeout_seconds: int = 300  # 5 minutes
    require_all_peers: bool = False
    allow_abstain: bool = True
    enable_pre_approval: bool = False
    pre_approved_patterns: List[str] = field(default_factory=list)
    async_vote_collection: bool = False
    vote_poll_timeout_seconds: float = 2.0

    def to_dict(self) -> Dict:
        """Convert config to dictionary."""
        return {
            'default_voting_threshold': self.default_voting_threshold.value,
            'default_custom_threshold': self.default_custom_threshold,
            'consensus_timeout_seconds': self.consensus_timeout_seconds,
            'require_all_peers': self.require_all_peers,
            'allow_abstain': self.allow_abstain,
            'enable_pre_approval': self.enable_pre_approval,
            'pre_approved_patterns': self.pre_approved_patterns,
            'async_vote_collection': self.async_vote_collection,
            'vote_poll_timeout_seconds': self.vote_poll_timeout_seconds,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> ConsensusConfig:
        """Create config from dictionary."""
        return cls(
            default_voting_threshold=VotingThreshold(
                data.get('default_voting_threshold', 'supermajority')
            ),
            default_custom_threshold=data.get('default_custom_threshold'),
            consensus_timeout_seconds=data.get('consensus_timeout_seconds', 300),
            require_all_peers=data.get('require_all_peers', False),
            allow_abstain=data.get('allow_abstain', True),
            enable_pre_approval=data.get('enable_pre_approval', False),
            pre_approved_patterns=data.get('pre_approved_patterns', []),
            async_vote_collection=data.get('async_vote_collection', False),
            vote_poll_timeout_seconds=float(data.get('vote_poll_timeout_seconds', 2.0)),
        )


class PeerRegistry:
    """Registry for managing peer identities."""

    def __init__(self, storage_path: Optional[Path] = None) -> None:
        """Initialize peer registry.

        Args:
            storage_path: Path to persist peer registry. If None, uses in-memory storage.
        """
        self.storage_path = storage_path
        self._peers: Dict[str, PeerIdentity] = {}
        if storage_path:
            self._load()

    def register(self, peer: PeerIdentity) -> None:
        """Register a new peer.

        Args:
            peer: The peer identity to register

        Raises:
            ValueError: If a peer with the same name already exists
        """
        if peer.name in self._peers:
            raise ValueError(f"Peer '{peer.name}' already registered")
        self._peers[peer.name] = peer
        if self.storage_path:
            self._save()

    def unregister(self, peer_name: str) -> Optional[PeerIdentity]:
        """Unregister a peer.

        Args:
            peer_name: Name of the peer to unregister

        Returns:
            The unregistered peer, or None if not found
        """
        peer = self._peers.pop(peer_name, None)
        if peer and self.storage_path:
            self._save()
        return peer

    def get(self, peer_name: str) -> Optional[PeerIdentity]:
        """Get a peer by name.

        Args:
            peer_name: Name of the peer

        Returns:
            The peer identity, or None if not found
        """
        return self._peers.get(peer_name)

    def list_all(self) -> List[PeerIdentity]:
        """List all registered peers.

        Returns:
            List of all peer identities
        """
        return list(self._peers.values())

    def list_active(self) -> List[PeerIdentity]:
        """List only active peers.

        Returns:
            List of active peer identities
        """
        return [peer for peer in self._peers.values() if peer.is_active]

    def activate(self, peer_name: str) -> bool:
        """Activate a peer.

        Args:
            peer_name: Name of the peer to activate

        Returns:
            True if peer was activated, False if not found
        """
        peer = self._peers.get(peer_name)
        if peer:
            # Create new instance with is_active=True
            active_peer = PeerIdentity(
                name=peer.name,
                ssh_public_key=peer.ssh_public_key,
                created_at=peer.created_at,
                is_active=True,
            )
            self._peers[peer_name] = active_peer
            if self.storage_path:
                self._save()
            return True
        return False

    def deactivate(self, peer_name: str) -> bool:
        """Deactivate a peer.

        Args:
            peer_name: Name of the peer to deactivate

        Returns:
            True if peer was deactivated, False if not found
        """
        peer = self._peers.get(peer_name)
        if peer:
            # Create new instance with is_active=False
            inactive_peer = PeerIdentity(
                name=peer.name,
                ssh_public_key=peer.ssh_public_key,
                created_at=peer.created_at,
                is_active=False,
            )
            self._peers[peer_name] = inactive_peer
            if self.storage_path:
                self._save()
            return True
        return False

    def rotate_key(self, peer_name: str, new_ssh_key: str) -> bool:
        """Rotate SSH key for a peer.

        Args:
            peer_name: Name of the peer
            new_ssh_key: New SSH public key

        Returns:
            True if key was rotated, False if peer not found
        """
        peer = self._peers.get(peer_name)
        if peer:
            # Create new instance with new key
            updated_peer = PeerIdentity(
                name=peer.name,
                ssh_public_key=new_ssh_key,
                created_at=peer.created_at,
                is_active=peer.is_active,
            )
            self._peers[peer_name] = updated_peer
            if self.storage_path:
                self._save()
            return True
        return False

    def verify_peer(self, peer_name: str, message: str, signature: str) -> bool:
        """Verify a signature from a peer.

        Args:
            peer_name: Name of the peer
            message: The message that was signed
            signature: The signature to verify

        Returns:
            True if signature is valid from this peer, False otherwise
        """
        peer = self.get(peer_name)
        if not peer or not peer.is_active:
            return False
        return peer.verify_signature(message, signature)

    def _save(self) -> None:
        """Save peer registry to storage."""
        if not self.storage_path:
            return

        data = {
            'peers': [
                {
                    'name': peer.name,
                    'ssh_public_key': peer.ssh_public_key,
                    'created_at': peer.created_at.isoformat(),
                    'is_active': peer.is_active,
                }
                for peer in self._peers.values()
            ]
        }

        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage_path.write_text(json.dumps(data, indent=2), encoding='utf-8')

    def _load(self) -> None:
        """Load peer registry from storage."""
        if not self.storage_path or not self.storage_path.exists():
            return

        try:
            data = json.loads(self.storage_path.read_text(encoding='utf-8'))
            for peer_data in data.get('peers', []):
                peer = PeerIdentity(
                    name=peer_data['name'],
                    ssh_public_key=peer_data['ssh_public_key'],
                    created_at=datetime.fromisoformat(peer_data['created_at']),
                    is_active=peer_data.get('is_active', True),
                )
                self._peers[peer.name] = peer
        except (json.JSONDecodeError, OSError, KeyError, ValueError, TypeError) as exc:
            # If loading fails, start with empty registry
            logger.warning('Failed to load peer registry: %s', exc)
            self._peers = {}


class VotingMechanism:
    """Mechanism for managing voting on proposals."""

    def __init__(self, config: ConsensusConfig) -> None:
        """Initialize voting mechanism.

        Args:
            config: Consensus configuration
        """
        self.config = config
        self._active_votes: Dict[str, ConsensusState] = {}

    def initiate_voting(
        self,
        proposal: Proposal,
        required_peers: Set[str],
        threshold: Optional[VotingThreshold] = None,
        custom_threshold: Optional[float] = None,
    ) -> ConsensusState:
        """Initiate voting on a proposal.

        Args:
            proposal: The proposal to vote on
            required_peers: Set of peer names that must vote
            threshold: Voting threshold (uses config default if None)
            custom_threshold: Custom threshold percentage (for CUSTOM threshold)

        Returns:
            The consensus state for this voting process
        """
        state = ConsensusState(
            proposal=proposal,
            voting_threshold=threshold or self.config.default_voting_threshold,
            custom_threshold=custom_threshold or self.config.default_custom_threshold,
            required_peers=required_peers,
            started_at=datetime.now(timezone.utc),
        )
        state.status = ConsensusStatus.VOTING
        self._active_votes[proposal.id] = state
        return state

    def cast_vote(
        self,
        proposal_id: str,
        peer_name: str,
        decision: VoteDecision,
        signature: str,
        comment: Optional[str] = None,
    ) -> bool:
        """Cast a vote on a proposal.

        Args:
            proposal_id: ID of the proposal
            peer_name: Name of the peer voting
            decision: The vote decision
            signature: Signature of the vote
            comment: Optional comment on the vote

        Returns:
            True if vote was cast, False if voting is closed or peer already voted
        """
        state = self._active_votes.get(proposal_id)
        if not state:
            return False

        if state.status != ConsensusStatus.VOTING:
            return False

        if state.has_voted(peer_name):
            return False

        vote = Vote(
            peer_name=peer_name,
            decision=decision,
            signature=signature,
            comment=comment,
        )
        state.add_vote(vote)

        # Check if voting is complete
        self._check_voting_complete(state)

        return True

    def cancel_vote(self, proposal_id: str, peer_name: str) -> bool:
        """Cancel a vote from a peer.

        Args:
            proposal_id: ID of the proposal
            peer_name: Name of the peer cancelling their vote

        Returns:
            True if vote was cancelled, False if not found or voting closed
        """
        state = self._active_votes.get(proposal_id)
        if not state:
            return False

        if state.status != ConsensusStatus.VOTING:
            return False

        # Remove the vote
        state.votes = [v for v in state.votes if v.peer_name != peer_name]
        return True

    def get_state(self, proposal_id: str) -> Optional[ConsensusState]:
        """Get the current state of voting on a proposal.

        Args:
            proposal_id: ID of the proposal

        Returns:
            The consensus state, or None if not found
        """
        return self._active_votes.get(proposal_id)

    def check_timeout(self, proposal_id: str) -> bool:
        """Check if a proposal has timed out.

        Args:
            proposal_id: ID of the proposal

        Returns:
            True if proposal has timed out, False otherwise
        """
        state = self._active_votes.get(proposal_id)
        if not state or not state.started_at:
            return False

        elapsed = (datetime.now(timezone.utc) - state.started_at).total_seconds()
        if elapsed > self.config.consensus_timeout_seconds:
            state.status = ConsensusStatus.TIMEOUT
            state.completed_at = datetime.now(timezone.utc)
            return True

        return False

    def close_voting(self, proposal_id: str) -> Optional[ConsensusState]:
        """Close voting on a proposal and determine result.

        Args:
            proposal_id: ID of the proposal

        Returns:
            The final consensus state, or None if not found
        """
        state = self._active_votes.get(proposal_id)
        if not state:
            return None

        if state.status != ConsensusStatus.VOTING:
            return state

        state.completed_at = datetime.now(timezone.utc)

        if state.is_approved():
            state.status = ConsensusStatus.APPROVED
        else:
            state.status = ConsensusStatus.REJECTED

        return state

    def _check_voting_complete(self, state: ConsensusState) -> None:
        """Check if voting is complete and update status.

        Args:
            state: The consensus state to check
        """
        # Check if all required peers have voted
        if state.required_peers:
            all_voted = all(state.has_voted(peer) for peer in state.required_peers)
            if all_voted:
                self.close_voting(state.proposal.id)
                return

        # Check if we have enough votes to determine outcome
        if state.has_quorum():
            # If we have quorum and can determine outcome, close early
            if state.is_approved():
                self.close_voting(state.proposal.id)
            elif state.get_vote_count(VoteDecision.REJECT) >= state.get_quorum_size():
                # Enough rejections to definitely fail
                self.close_voting(state.proposal.id)

    def list_active_votings(self) -> List[ConsensusState]:
        """List all currently active votings.

        Returns:
            List of active consensus states
        """
        return [
            state
            for state in self._active_votes.values()
            if state.status == ConsensusStatus.VOTING
        ]

    def cleanup_completed(self, older_than_seconds: int = 3600) -> int:
        """Clean up completed voting states.

        Args:
            older_than_seconds: Remove states completed more than this many seconds ago

        Returns:
            Number of states removed
        """
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=older_than_seconds)
        to_remove = []

        for proposal_id, state in self._active_votes.items():
            if (
                state.status
                in (
                    ConsensusStatus.APPROVED,
                    ConsensusStatus.REJECTED,
                    ConsensusStatus.TIMEOUT,
                    ConsensusStatus.CANCELLED,
                )
                and state.completed_at
                and state.completed_at < cutoff
            ):
                to_remove.append(proposal_id)

        for proposal_id in to_remove:
            del self._active_votes[proposal_id]

        return len(to_remove)


def peer_vote_signature(peer: PeerIdentity, task_description: str) -> str:
    """Build the test/dev signature format used by ``PeerIdentity.verify_signature``."""
    return hashlib.sha256((task_description + peer.ssh_public_key).encode()).hexdigest()


def parse_vote_import_payload(raw: object) -> list[dict[str, object]]:
    """Normalize vote-import JSON (bare list or ``{\"votes\": [...]}`` wrapper)."""
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    if isinstance(raw, dict) and isinstance(raw.get('votes'), list):
        return [item for item in raw['votes'] if isinstance(item, dict)]
    raise ValueError('Expected a JSON array or object with a "votes" array')


def import_votes_batch(
    engine: ConsensusEngine,
    records: list[dict[str, object]],
    *,
    auto_sign: bool = True,
) -> dict[str, object]:
    """Import external peer votes from JSON records."""
    accepted = 0
    rejected = 0
    errors: list[str] = []
    for index, record in enumerate(records):
        proposal_id = record.get('proposal_id')
        peer_name = record.get('peer_name')
        decision_raw = record.get('decision')
        if not proposal_id or not peer_name or not decision_raw:
            errors.append(f'record[{index}]: proposal_id, peer_name, decision required')
            rejected += 1
            continue
        try:
            decision = VoteDecision(str(decision_raw))
        except ValueError:
            errors.append(f'record[{index}]: invalid decision {decision_raw!r}')
            rejected += 1
            continue
        state = engine.get_consensus_status(str(proposal_id))
        if state is None:
            errors.append(f'record[{index}]: proposal {proposal_id!r} not found')
            rejected += 1
            continue
        peer = engine.peer_registry.get(str(peer_name))
        if peer is None:
            errors.append(f'record[{index}]: peer {peer_name!r} not found')
            rejected += 1
            continue
        signature = record.get('signature')
        if not signature and auto_sign:
            signature = peer_vote_signature(peer, state.proposal.task_description)
        if not signature:
            errors.append(f'record[{index}]: missing signature')
            rejected += 1
            continue
        comment = record.get('comment')
        comment_str = str(comment) if comment is not None else None
        if engine.submit_vote(
            str(proposal_id),
            str(peer_name),
            decision,
            str(signature),
            comment=comment_str,
        ):
            accepted += 1
        else:
            errors.append(f'record[{index}]: submit_vote failed')
            rejected += 1
    return {'accepted': accepted, 'rejected': rejected, 'errors': errors}


def task_matches_pre_approval(task_description: str, config: ConsensusConfig) -> bool:
    """Return True when *task_description* matches configured pre-approval patterns."""
    if not config.enable_pre_approval:
        return False
    if not config.pre_approved_patterns:
        return True
    return any(
        fnmatch.fnmatch(task_description, pattern)
        for pattern in config.pre_approved_patterns
    )


class ConsensusEngine:
    """Core consensus engine coordinating voting and attestation."""

    def __init__(
        self,
        peer_registry: PeerRegistry,
        config: ConsensusConfig,
        storage_path: Optional[Path] = None,
    ) -> None:
        """Initialize consensus engine.

        Args:
            peer_registry: Registry of peer identities
            config: Consensus configuration
            storage_path: Path to persist consensus state
        """
        self.peer_registry = peer_registry
        self.config = config
        self.storage_path = storage_path
        self.voting_mechanism = VotingMechanism(config)
        self._load_state()

    def request_consensus(
        self,
        task_description: str,
        risk_level: RiskLevel,
        proposed_by: str,
        required_peers: Optional[Set[str]] = None,
        threshold: Optional[VotingThreshold] = None,
        custom_threshold: Optional[float] = None,
        expires_in_seconds: Optional[int] = None,
        metadata: Optional[Dict] = None,
    ) -> ConsensusState:
        """Request consensus for a task.

        Args:
            task_description: Description of the task requiring consensus
            risk_level: Risk level of the task
            proposed_by: Peer proposing the task
            required_peers: Peers required to vote (uses all active if None)
            threshold: Voting threshold (uses config default if None)
            custom_threshold: Custom threshold percentage
            expires_in_seconds: Time before proposal expires
            metadata: Additional metadata

        Returns:
            The consensus state for this request
        """
        # Generate proposal ID
        proposal_id = self._generate_proposal_id(task_description, proposed_by)

        # Determine required peers
        if required_peers is None:
            required_peers = {peer.name for peer in self.peer_registry.list_active()}

        if not required_peers:
            raise ValueError('No active peers available for consensus')

        # Calculate expiration
        expires_at = None
        if expires_in_seconds:
            expires_at = datetime.now(timezone.utc) + timedelta(
                seconds=expires_in_seconds
            )

        # Create proposal
        proposal = Proposal(
            id=proposal_id,
            task_description=task_description,
            risk_level=risk_level,
            proposed_by=proposed_by,
            expires_at=expires_at,
            metadata=metadata or {},
        )

        # Initiate voting
        state = self.voting_mechanism.initiate_voting(
            proposal=proposal,
            required_peers=required_peers,
            threshold=threshold,
            custom_threshold=custom_threshold,
        )

        self._save_state()
        return state

    def submit_vote(
        self,
        proposal_id: str,
        peer_name: str,
        decision: VoteDecision,
        signature: str,
        comment: Optional[str] = None,
    ) -> bool:
        """Submit a vote on a proposal.

        Args:
            proposal_id: ID of the proposal
            peer_name: Name of the peer voting
            decision: The vote decision
            signature: Signature of the vote
            comment: Optional comment

        Returns:
            True if vote was submitted successfully
        """
        # Verify peer signature
        state = self.voting_mechanism.get_state(proposal_id)
        if not state:
            return False

        # Verify the signature is from the claimed peer
        if not self.peer_registry.verify_peer(
            peer_name, state.proposal.task_description, signature
        ):
            return False

        # Cast the vote
        success = self.voting_mechanism.cast_vote(
            proposal_id=proposal_id,
            peer_name=peer_name,
            decision=decision,
            signature=signature,
            comment=comment,
        )

        if success:
            self._save_state()

        return success

    def get_consensus_status(self, proposal_id: str) -> Optional[ConsensusState]:
        """Get the current status of a consensus request.

        Args:
            proposal_id: ID of the proposal

        Returns:
            The consensus state, or None if not found
        """
        state = self.voting_mechanism.get_state(proposal_id)

        # Check for timeout
        if (
            state
            and state.status == ConsensusStatus.VOTING
            and self.voting_mechanism.check_timeout(proposal_id)
        ):
            self._save_state()

        # Check for expiration
        if state and state.proposal.is_expired():
            state.status = ConsensusStatus.TIMEOUT
            state.completed_at = datetime.now(timezone.utc)
            self._save_state()

        return state

    def cast_approving_votes_for_active_peers(self, proposal_id: str) -> int:
        """Cast approve votes from active peers (trusted local orchestration)."""
        state = self.get_consensus_status(proposal_id)
        if state is None:
            return 0
        cast = 0
        description = state.proposal.task_description
        for peer in self.peer_registry.list_active():
            if peer.name not in state.required_peers:
                continue
            signature = peer_vote_signature(peer, description)
            if self.submit_vote(
                proposal_id,
                peer.name,
                VoteDecision.APPROVE,
                signature,
            ):
                cast += 1
        return cast

    def poll_until_resolved(
        self,
        proposal_id: str,
        *,
        timeout_seconds: float,
        interval_seconds: float = 0.05,
    ) -> Optional[ConsensusState]:
        """Poll consensus status without blocking longer than ``timeout_seconds``."""
        import time

        deadline = time.monotonic() + max(timeout_seconds, 0.0)
        latest: Optional[ConsensusState] = None
        while True:
            latest = self.get_consensus_status(proposal_id)
            if latest is None:
                return None
            if latest.status in {
                ConsensusStatus.APPROVED,
                ConsensusStatus.REJECTED,
                ConsensusStatus.TIMEOUT,
                ConsensusStatus.CANCELLED,
            }:
                return latest
            if time.monotonic() >= deadline:
                return latest
            time.sleep(interval_seconds)

    def generate_attestation(self, proposal_id: str) -> Optional[Dict]:
        """Generate attestation for an approved proposal.

        Args:
            proposal_id: ID of the approved proposal

        Returns:
            Attestation data, or None if proposal not approved
        """
        state = self.get_consensus_status(proposal_id)
        if not state or state.status != ConsensusStatus.APPROVED:
            return None

        # Generate attestation
        attestation = {
            'proposal_id': proposal_id,
            'task_description': state.proposal.task_description,
            'risk_level': state.proposal.risk_level.value,
            'approved_by': [
                vote.peer_name
                for vote in state.votes
                if vote.decision == VoteDecision.APPROVE
            ],
            'rejected_by': [
                vote.peer_name
                for vote in state.votes
                if vote.decision == VoteDecision.REJECT
            ],
            'abstained_by': [
                vote.peer_name
                for vote in state.votes
                if vote.decision == VoteDecision.ABSTAIN
            ],
            'signatures': [vote.signature for vote in state.votes],
            'approved_at': state.completed_at.isoformat()
            if state.completed_at
            else None,
            'voting_threshold': state.voting_threshold.value,
        }

        return attestation

    def cancel_consensus(self, proposal_id: str, cancelled_by: str) -> bool:
        """Cancel an active consensus request.

        Args:
            proposal_id: ID of the proposal
            cancelled_by: Peer cancelling the consensus

        Returns:
            True if consensus was cancelled
        """
        state = self.voting_mechanism.get_state(proposal_id)
        if not state or state.status != ConsensusStatus.VOTING:
            return False

        state.status = ConsensusStatus.CANCELLED
        state.completed_at = datetime.now(timezone.utc)
        self._save_state()
        return True

    def resolve_conflict(self, proposal_id: str, resolution: str) -> bool:
        """Resolve a conflict in consensus.

        Args:
            proposal_id: ID of the proposal
            resolution: Resolution description

        Returns:
            True if conflict was resolved
        """
        state = self.voting_mechanism.get_state(proposal_id)
        if not state:
            return False

        # Add resolution to metadata
        state.proposal.metadata['conflict_resolution'] = resolution
        self._save_state()
        return True

    def list_active_consensus(self) -> List[ConsensusState]:
        """List all active consensus requests.

        Returns:
            List of active consensus states
        """
        return self.voting_mechanism.list_active_votings()

    def cleanup_old_consensus(self, older_than_seconds: int = 3600) -> int:
        """Clean up old consensus states.

        Args:
            older_than_seconds: Remove states older than this

        Returns:
            Number of states removed
        """
        removed = self.voting_mechanism.cleanup_completed(older_than_seconds)
        if removed > 0:
            self._save_state()
        return removed

    def _generate_proposal_id(self, task_description: str, proposed_by: str) -> str:
        """Generate a unique proposal ID.

        Args:
            task_description: Task description
            proposed_by: Peer proposing the task

        Returns:
            Unique proposal ID
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        hash_input = f'{task_description}:{proposed_by}:{timestamp}'
        hash_value = hashlib.sha256(hash_input.encode()).hexdigest()[:16]
        return f'prop-{hash_value}'

    def _save_state(self) -> None:
        """Save consensus state to storage."""
        if not self.storage_path:
            return

        data = {
            'consensus_states': [
                state.to_dict()
                for state in self.voting_mechanism._active_votes.values()
            ],
        }

        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage_path.write_text(json.dumps(data, indent=2), encoding='utf-8')

    def _load_state(self) -> None:
        """Load consensus state from storage."""
        if not self.storage_path or not self.storage_path.exists():
            return

        try:
            data = json.loads(self.storage_path.read_text(encoding='utf-8'))
            for state_data in data.get('consensus_states', []):
                state = ConsensusState.from_dict(state_data)
                self.voting_mechanism._active_votes[state.proposal.id] = state
        except (json.JSONDecodeError, OSError, KeyError, ValueError, TypeError) as exc:
            # If loading fails, start with empty state
            logger.warning('Failed to load consensus state: %s', exc)
            self.voting_mechanism._active_votes = {}

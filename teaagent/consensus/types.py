"""Data types for the consensus system.

This module provides data structures for peer-to-peer consensus
in multi-agent swarms, including identity, proposals, votes,
and consensus state tracking.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
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
        """Verify a dev hash or production SSH signature from this peer."""
        try:
            from teaagent.ssh_signatures import (
                is_ssh_signature_blob,
                verify_message_ssh,
            )

            if is_ssh_signature_blob(signature):
                return verify_message_ssh(self.ssh_public_key, message, signature)
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
    cancelled_by: Optional[str] = None  # Peer who cancelled the consensus

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
        """Check if proposal is approved based on votes.

        Threshold behavior (strict >, not >=):
        - SIMPLE_MAJORITY: approve > total_votes / 2 (50%)
        - SUPERMAJORITY:   approve > total_votes * 2 / 3 (66.6...%)
        - UNANIMOUS:       approve == total_votes (100%)
        - CUSTOM:          approve > total_votes * custom_threshold

        Note: SUPERMAJORITY requires strictly more than 2/3.
        For 3 peers, 2 approve + 1 reject = 66.6% which equals 2/3,
        so the proposal is rejected (2 > 2.0 is False).
        """
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
            'cancelled_by': self.cancelled_by,
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
            cancelled_by=data.get('cancelled_by'),
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

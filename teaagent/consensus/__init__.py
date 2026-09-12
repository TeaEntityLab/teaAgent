"""Consensus system for federated swarm coordination.

Re-exports all public symbols from the consensus package.
"""

from __future__ import annotations

from teaagent.consensus.engine import (
    ConsensusEngine,
    import_votes_batch,
    parse_vote_import_payload,
    peer_vote_signature,
    task_matches_pre_approval,
)
from teaagent.consensus.peer_registry import PeerRegistry
from teaagent.consensus.types import (
    ConsensusConfig,
    ConsensusState,
    ConsensusStatus,
    PeerIdentity,
    Proposal,
    RiskLevel,
    Vote,
    VoteDecision,
    VotingThreshold,
)
from teaagent.consensus.voting import VotingMechanism

__all__ = [
    'ConsensusConfig',
    'ConsensusEngine',
    'ConsensusState',
    'ConsensusStatus',
    'PeerIdentity',
    'PeerRegistry',
    'Proposal',
    'RiskLevel',
    'Vote',
    'VoteDecision',
    'VotingMechanism',
    'VotingThreshold',
    'import_votes_batch',
    'parse_vote_import_payload',
    'peer_vote_signature',
    'task_matches_pre_approval',
]

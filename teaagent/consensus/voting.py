"""Voting mechanism for the consensus system."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set

from teaagent.consensus.types import (
    ConsensusConfig,
    ConsensusState,
    ConsensusStatus,
    Proposal,
    Vote,
    VoteDecision,
    VotingThreshold,
)


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
        if state.required_peers:
            all_voted = all(state.has_voted(peer) for peer in state.required_peers)
            if all_voted:
                self.close_voting(state.proposal.id)
                return

        if state.has_quorum() and (
            state.is_approved()
            or state.get_vote_count(VoteDecision.REJECT) >= state.get_quorum_size()
        ):
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

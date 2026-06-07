"""Core consensus engine coordinating voting and attestation."""

from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import os
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Dict, List, Optional, Set

from teaagent.consensus.peer_registry import PeerRegistry
from teaagent.consensus.types import (
    ConsensusConfig,
    ConsensusState,
    ConsensusStatus,
    PeerIdentity,
    Proposal,
    RiskLevel,
    VoteDecision,
    VotingThreshold,
)
from teaagent.consensus.voting import VotingMechanism

logger = logging.getLogger(__name__)


def peer_vote_signature(
    peer: PeerIdentity,
    task_description: str,
    *,
    proposal_id: str | None = None,
    peer_name: str | None = None,
    decision: str | None = None,
) -> str:
    """Build the test/dev signature format used by PeerIdentity.verify_signature."""
    from teaagent.ssh_signatures import build_vote_signing_message

    if proposal_id and peer_name and decision:
        message = build_vote_signing_message(
            proposal_id, peer_name, decision, task_description
        )
    else:
        message = task_description
    return hashlib.sha256((message + peer.ssh_public_key).encode()).hexdigest()


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
    """Return True when task_description matches configured pre-approval patterns."""
    if not config.enable_pre_approval:
        return False
    if not config.pre_approved_patterns:
        return True
    import fnmatch

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
        self._lock = threading.RLock()
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
        proposal_id = self._generate_proposal_id(task_description, proposed_by)

        if required_peers is None:
            required_peers = {peer.name for peer in self.peer_registry.list_active()}

        if not required_peers:
            raise ValueError('No active peers available for consensus')

        expires_at = None
        if expires_in_seconds:
            expires_at = datetime.now(timezone.utc) + timedelta(
                seconds=expires_in_seconds
            )

        proposal = Proposal(
            id=proposal_id,
            task_description=task_description,
            risk_level=risk_level,
            proposed_by=proposed_by,
            expires_at=expires_at,
            metadata=metadata or {},
        )

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
        state = self.voting_mechanism.get_state(proposal_id)
        if not state:
            return False

        from teaagent.ssh_signatures import build_vote_signing_message

        canonical = build_vote_signing_message(
            proposal_id,
            peer_name,
            decision.value,
            state.proposal.task_description,
        )
        legacy = state.proposal.task_description
        verified = self.peer_registry.verify_peer(
            peer_name, canonical, signature
        ) or self.peer_registry.verify_peer(peer_name, legacy, signature)
        if not verified:
            return False

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

        if (
            state
            and state.status == ConsensusStatus.VOTING
            and self.voting_mechanism.check_timeout(proposal_id)
        ):
            self._save_state()

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
            signature = peer_vote_signature(
                peer,
                description,
                proposal_id=proposal_id,
                peer_name=peer.name,
                decision=VoteDecision.APPROVE.value,
            )
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
        """Poll consensus status without blocking longer than timeout_seconds."""
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
        state.cancelled_by = cancelled_by
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
        """Save consensus state to storage atomically under reentrant lock."""
        if not self.storage_path:
            return

        with self._lock:
            data = {
                'consensus_states': [
                    state.to_dict()
                    for state in self.voting_mechanism._active_votes.values()
                ],
            }

            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            with NamedTemporaryFile(
                'w',
                dir=str(self.storage_path.parent),
                delete=False,
                suffix='.tmp',
            ) as tmp:
                try:
                    json.dump(data, tmp, indent=2)
                    tmp.flush()
                    os.fsync(tmp.fileno())
                    os.replace(tmp.name, self.storage_path)
                except (OSError, IOError, json.JSONDecodeError):
                    with contextlib.suppress(OSError):
                        os.unlink(tmp.name)
                    raise

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
            logger.warning('Failed to load consensus state: %s', exc)
            self.voting_mechanism._active_votes = {}

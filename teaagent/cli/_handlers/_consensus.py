"""Consensus CLI handlers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from teaagent.consensus import (
    ConsensusConfig,
    ConsensusEngine,
    ConsensusStatus,
    PeerIdentity,
    PeerRegistry,
    RiskLevel,
    VoteDecision,
    VotingThreshold,
)


def consensus_peers_list_command(args: argparse.Namespace) -> int:
    """List all registered peers."""
    storage_path = Path(args.storage) if args.storage else None
    registry = PeerRegistry(storage_path=storage_path)

    peers = registry.list_all()

    if not peers:
        print('No peers registered.')
        return 0

    print(f'Registered peers ({len(peers)}):\n')

    for peer in peers:
        status = 'active' if peer.is_active else 'inactive'
        print(f'  Name: {peer.name}')
        print(f'  Status: {status}')
        print(f'  Fingerprint: {peer.fingerprint}')
        print(f'  Created: {peer.created_at.isoformat()}')
        print(f'  SSH Key: {peer.ssh_public_key[:50]}...')
        print()

    return 0


def consensus_peers_add_command(args: argparse.Namespace) -> int:
    """Add a new peer."""
    storage_path = Path(args.storage) if args.storage else None
    registry = PeerRegistry(storage_path=storage_path)

    # Read SSH public key from file if provided
    if args.ssh_key_file:
        ssh_key = Path(args.ssh_key_file).read_text(encoding='utf-8').strip()
    else:
        ssh_key = args.ssh_key

    peer = PeerIdentity(
        name=args.name,
        ssh_public_key=ssh_key,
        is_active=True,
    )

    try:
        registry.register(peer)
        print(f'Peer "{args.name}" registered successfully.')
        print(f'Fingerprint: {peer.fingerprint}')
        return 0
    except ValueError as exc:
        print(f'Error: {exc}')
        return 1


def consensus_peers_remove_command(args: argparse.Namespace) -> int:
    """Remove a peer."""
    storage_path = Path(args.storage) if args.storage else None
    registry = PeerRegistry(storage_path=storage_path)

    peer = registry.unregister(args.name)

    if peer:
        print(f'Peer "{args.name}" removed successfully.')
        return 0
    else:
        print(f'Peer "{args.name}" not found.')
        return 1


def consensus_peers_activate_command(args: argparse.Namespace) -> int:
    """Activate a peer."""
    storage_path = Path(args.storage) if args.storage else None
    registry = PeerRegistry(storage_path=storage_path)

    if registry.activate(args.name):
        print(f'Peer "{args.name}" activated.')
        return 0
    else:
        print(f'Peer "{args.name}" not found.')
        return 1


def consensus_peers_deactivate_command(args: argparse.Namespace) -> int:
    """Deactivate a peer."""
    storage_path = Path(args.storage) if args.storage else None
    registry = PeerRegistry(storage_path=storage_path)

    if registry.deactivate(args.name):
        print(f'Peer "{args.name}" deactivated.')
        return 0
    else:
        print(f'Peer "{args.name}" not found.')
        return 1


def consensus_status_command(args: argparse.Namespace) -> int:
    """Show consensus status."""
    storage_path = Path(args.storage) if args.storage else None
    peer_storage = Path(args.peer_storage) if args.peer_storage else None
    consensus_storage = Path(args.consensus_storage) if args.consensus_storage else None

    registry = PeerRegistry(storage_path=peer_storage)
    config = ConsensusConfig()
    engine = ConsensusEngine(peer_registry=registry, config=config, storage_path=consensus_storage)

    # Show peer status
    peers = registry.list_active()
    print(f'Active peers: {len(peers)}')
    for peer in peers:
        print(f'  - {peer.name} ({peer.fingerprint})')
    print()

    # Show active consensus requests
    active = engine.list_active_consensus()
    print(f'Active consensus requests: {len(active)}')
    for state in active:
        print(f'  - {state.proposal.id}: {state.proposal.task_description}')
        print(f'    Risk: {state.proposal.risk_level.value}')
        print(f'    Votes: {state.get_total_votes()}/{len(state.required_peers)}')
        print(f'    Status: {state.status.value}')
    print()

    return 0


def consensus_history_command(args: argparse.Namespace) -> int:
    """Show consensus voting history."""
    storage_path = Path(args.storage) if args.storage else None
    peer_storage = Path(args.peer_storage) if args.peer_storage else None
    consensus_storage = Path(args.consensus_storage) if args.consensus_storage else None

    registry = PeerRegistry(storage_path=peer_storage)
    config = ConsensusConfig()
    engine = ConsensusEngine(peer_registry=registry, config=config, storage_path=consensus_storage)

    # Get all consensus states (including completed)
    # This is a simplified version - in production, would query from storage
    print('Consensus history:')
    print('(Full history query not yet implemented)')
    print()

    return 0


def consensus_config_set_command(args: argparse.Namespace) -> int:
    """Set consensus configuration."""
    config = ConsensusConfig()

    if args.voting_threshold:
        config.default_voting_threshold = VotingThreshold(args.voting_threshold)
    if args.timeout:
        config.consensus_timeout_seconds = args.timeout
    if args.require_all:
        config.require_all_peers = True
    if args.allow_abstain is not None:
        config.allow_abstain = args.allow_abstain

    # In production, this would save to a config file
    print('Consensus configuration updated:')
    print(json.dumps(config.to_dict(), indent=2))
    print()
    print('(Note: Configuration persistence not yet implemented)')

    return 0


def consensus_request_command(args: argparse.Namespace) -> int:
    """Request consensus for a task."""
    storage_path = Path(args.storage) if args.storage else None
    peer_storage = Path(args.peer_storage) if args.peer_storage else None
    consensus_storage = Path(args.consensus_storage) if args.consensus_storage else None

    registry = PeerRegistry(storage_path=peer_storage)
    config = ConsensusConfig()
    engine = ConsensusEngine(peer_registry=registry, config=config, storage_path=consensus_storage)

    try:
        state = engine.request_consensus(
            task_description=args.task,
            risk_level=RiskLevel(args.risk_level),
            proposed_by=args.proposed_by,
            threshold=VotingThreshold(args.threshold) if args.threshold else None,
        )

        print(f'Consensus request initiated: {state.proposal.id}')
        print(f'Task: {state.proposal.task_description}')
        print(f'Risk: {state.proposal.risk_level.value}')
        print(f'Required peers: {len(state.required_peers)}')
        print(f'Voting threshold: {state.voting_threshold.value}')
        print()
        print('Waiting for votes...')
        print('(In production, this would wait for peer votes)')

        return 0
    except Exception as exc:
        print(f'Error: {exc}')
        return 1


def consensus_vote_command(args: argparse.Namespace) -> int:
    """Submit a vote on a proposal."""
    import hashlib

    storage_path = Path(args.storage) if args.storage else None
    peer_storage = Path(args.peer_storage) if args.peer_storage else None
    consensus_storage = Path(args.consensus_storage) if args.consensus_storage else None

    registry = PeerRegistry(storage_path=peer_storage)
    config = ConsensusConfig()
    engine = ConsensusEngine(peer_registry=registry, config=config, storage_path=consensus_storage)

    # Get the proposal to sign
    state = engine.get_consensus_status(args.proposal_id)
    if not state:
        print(f'Proposal "{args.proposal_id}" not found.')
        return 1

    # Generate signature (simplified - in production, use proper SSH signing)
    peer = registry.get(args.peer_name)
    if not peer:
        print(f'Peer "{args.peer_name}" not found.')
        return 1

    signature = hashlib.sha256((state.proposal.task_description + peer.ssh_public_key).encode()).hexdigest()

    success = engine.submit_vote(
        proposal_id=args.proposal_id,
        peer_name=args.peer_name,
        decision=VoteDecision(args.decision),
        signature=signature,
        comment=args.comment,
    )

    if success:
        print(f'Vote submitted successfully for proposal {args.proposal_id}')
        updated_state = engine.get_consensus_status(args.proposal_id)
        print(f'Current votes: {updated_state.get_total_votes()}/{len(updated_state.required_peers)}')
        return 0
    else:
        print('Failed to submit vote.')
        return 1

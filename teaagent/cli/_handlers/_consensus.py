"""Consensus CLI handlers."""

from __future__ import annotations

import argparse
import json
import ssl
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
    import_votes_batch,
    parse_vote_import_payload,
    peer_vote_signature,
)
from teaagent.consensus.types import (
    ConsensusState,
    consensus_config_path_from_storage,
    load_consensus_config,
    save_consensus_config,
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


_FINISHED_CONSENSUS_STATUSES = frozenset(
    {
        ConsensusStatus.APPROVED,
        ConsensusStatus.REJECTED,
        ConsensusStatus.TIMEOUT,
        ConsensusStatus.CANCELLED,
    }
)


def _consensus_config_path(args: argparse.Namespace) -> Path:
    config_path = getattr(args, 'config_path', None)
    if config_path:
        return Path(config_path)
    consensus_storage = (
        Path(args.consensus_storage)
        if getattr(args, 'consensus_storage', None)
        else None
    )
    return consensus_config_path_from_storage(consensus_storage)


def _load_persisted_consensus_config(args: argparse.Namespace) -> ConsensusConfig:
    return load_consensus_config(_consensus_config_path(args))


def _format_vote_tally(state: ConsensusState) -> str:
    return (
        f'approve={state.get_vote_count(VoteDecision.APPROVE)} '
        f'reject={state.get_vote_count(VoteDecision.REJECT)} '
        f'abstain={state.get_vote_count(VoteDecision.ABSTAIN)}'
    )


def consensus_status_command(args: argparse.Namespace) -> int:
    """Show consensus status."""
    engine = _consensus_engine_from_args(args)
    registry = engine.peer_registry

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
    engine = _consensus_engine_from_args(args)
    finished = [
        state
        for state in engine.list_all_consensus()
        if state.status in _FINISHED_CONSENSUS_STATUSES
    ]
    finished.sort(
        key=lambda state: state.completed_at or state.proposal.created_at,
        reverse=True,
    )

    print(f'Completed consensus proposals: {len(finished)}')
    for state in finished:
        completed = state.completed_at.isoformat() if state.completed_at else 'n/a'
        print(f'  - {state.proposal.id}: {state.proposal.task_description}')
        print(f'    Status: {state.status.value}')
        print(f'    Completed: {completed}')
        print(f'    Votes: {_format_vote_tally(state)}')
    print()
    return 0


def consensus_config_set_command(args: argparse.Namespace) -> int:
    """Set consensus configuration."""
    config_path = _consensus_config_path(args)
    config = load_consensus_config(config_path)

    if getattr(args, 'voting_threshold', None) is not None:
        config.default_voting_threshold = VotingThreshold(args.voting_threshold)
    if getattr(args, 'timeout', None) is not None:
        config.consensus_timeout_seconds = args.timeout
    if getattr(args, 'require_all', False):
        config.require_all_peers = True
    if getattr(args, 'allow_abstain', None) is not None:
        config.allow_abstain = args.allow_abstain

    save_consensus_config(config, config_path)
    print(json.dumps(config.to_dict(), indent=2))
    return 0


def consensus_request_command(args: argparse.Namespace) -> int:
    """Request consensus for a task."""
    engine = _consensus_engine_from_args(args)

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
        if getattr(args, 'auto_approve', False):
            cast = engine.cast_approving_votes_for_active_peers(state.proposal.id)
            print(f'Auto-approved {cast} peer vote(s)')

        if getattr(args, 'wait', False):
            timeout = float(getattr(args, 'timeout', 60))
            final = engine.poll_until_resolved(
                state.proposal.id, timeout_seconds=timeout
            )
            if final is None:
                print('Proposal not found after wait.')
                return 1
            print(f'Final status: {final.status.value}')
            print(
                json.dumps(
                    final.to_dict(), indent=2, default=lambda o: f'[{type(o).__name__}]'
                )
            )
            if final.status not in {ConsensusStatus.APPROVED, ConsensusStatus.REJECTED}:
                return 1
        else:
            print()
            print('Waiting for votes (use --wait or `teaagent consensus wait`).')

        return 0
    except Exception as exc:
        print(f'Error: {exc}')
        return 1


def _consensus_engine_from_args(args: argparse.Namespace) -> ConsensusEngine:
    peer_storage = Path(args.peer_storage) if args.peer_storage else None
    consensus_storage = Path(args.consensus_storage) if args.consensus_storage else None
    registry = PeerRegistry(storage_path=peer_storage)
    config = _load_persisted_consensus_config(args)
    return ConsensusEngine(
        peer_registry=registry, config=config, storage_path=consensus_storage
    )


def consensus_wait_command(args: argparse.Namespace) -> int:
    """Poll until a proposal reaches a terminal consensus status."""
    engine = _consensus_engine_from_args(args)
    final = engine.poll_until_resolved(
        args.proposal_id, timeout_seconds=float(args.timeout)
    )
    if final is None:
        print(f'Proposal "{args.proposal_id}" not found.')
        return 1
    print(f'Status: {final.status.value}')
    if final.cancelled_by:
        print(f'Cancelled by: {final.cancelled_by}')
    print(
        json.dumps(final.to_dict(), indent=2, default=lambda o: f'[{type(o).__name__}]')
    )
    if final.status in {
        ConsensusStatus.APPROVED,
        ConsensusStatus.REJECTED,
        ConsensusStatus.CANCELLED,
    }:
        return 0
    return 1


def consensus_cancel_command(args: argparse.Namespace) -> int:
    """Cancel an active consensus proposal and record who cancelled it."""
    engine = _consensus_engine_from_args(args)
    cancelled = engine.cancel_consensus(
        args.proposal_id, cancelled_by=args.cancelled_by
    )
    if not cancelled:
        print(
            f'Could not cancel proposal "{args.proposal_id}" '
            '(not found or not in voting state).'
        )
        return 1
    state = engine.get_consensus_status(args.proposal_id)
    if state is None:
        print(f'Proposal "{args.proposal_id}" cancelled.')
        return 0
    print(f'Status: {state.status.value}')
    if state.cancelled_by:
        print(f'Cancelled by: {state.cancelled_by}')
    print(
        json.dumps(state.to_dict(), indent=2, default=lambda o: f'[{type(o).__name__}]')
    )
    return 0


def consensus_votes_import_command(args: argparse.Namespace) -> int:
    """Import batched peer votes from a JSON file (external orchestrators)."""
    votes_path = Path(args.votes_file)
    if not votes_path.is_file():
        print(f'Error: votes file not found: {votes_path}')
        return 1
    try:
        raw = json.loads(votes_path.read_text(encoding='utf-8'))
        records = parse_vote_import_payload(raw)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f'Error: {exc}')
        return 1
    engine = _consensus_engine_from_args(args)
    summary = import_votes_batch(engine, records, auto_sign=not args.no_auto_sign)
    print(json.dumps(summary, indent=2))
    accepted = summary.get('accepted', 0)
    errors = summary.get('errors')
    ok = isinstance(accepted, int) and accepted > 0 and not errors
    return 0 if ok else 1


def consensus_vote_command(args: argparse.Namespace) -> int:
    """Submit a vote on a proposal."""
    engine = _consensus_engine_from_args(args)
    registry = engine.peer_registry

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

    signature = peer_vote_signature(peer, state.proposal.task_description)

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
        if updated_state:
            print(
                f'Current votes: {updated_state.get_total_votes()}/{len(updated_state.required_peers)}'
            )
        return 0
    else:
        print('Failed to submit vote.')
        return 1


def _relay_ssl_context(args: argparse.Namespace) -> ssl.SSLContext | None:
    if not getattr(args, 'tls_cert', None):
        return None
    from pathlib import Path

    from teaagent.tls_server import build_server_ssl_context

    if not args.tls_key:
        print('Error: --tls-key is required when --tls-cert is set')
        raise SystemExit(1)
    client_ca = (
        Path(args.tls_client_ca) if getattr(args, 'tls_client_ca', None) else None
    )
    return build_server_ssl_context(
        cert_file=Path(args.tls_cert),
        key_file=Path(args.tls_key),
        client_ca_file=client_ca,
    )


def consensus_relay_serve_command(args: argparse.Namespace) -> int:
    """Serve HTTP relay for SSH-signed production peer votes."""
    from pathlib import Path

    from teaagent.surface_auth import load_surface_auth_policy
    from teaagent.vote_relay import VoteRelayServer

    engine = _consensus_engine_from_args(args)
    token_file = (
        Path(args.api_token_file) if getattr(args, 'api_token_file', None) else None
    )
    policy = load_surface_auth_policy(
        api_token=getattr(args, 'api_token', None),
        api_token_file=token_file,
        relay_mode=True,
    )
    from teaagent.http_rate_limit import TokenRateLimiter

    rate_limiter = None
    rate_limit_calls = int(getattr(args, 'rate_limit_calls', 0))
    if rate_limit_calls > 0:
        rate_limiter = TokenRateLimiter(
            max_calls=rate_limit_calls,
            window_seconds=float(getattr(args, 'rate_limit_window', 60.0)),
        )
    try:
        allow_dev = bool(getattr(args, 'allow_dev_signatures', False))
        relay = VoteRelayServer(
            engine,
            host=args.host,
            port=args.port,
            require_ssh=not allow_dev,
            allow_dev_signatures=allow_dev,
            auth_policy=policy,
            ssl_context=_relay_ssl_context(args),
            rate_limiter=rate_limiter,
        )
    except ValueError as exc:
        print(f'Error: {exc}')
        return 1
    relay.serve_blocking()
    return 0


def consensus_relay_submit_command(args: argparse.Namespace) -> int:
    """Submit an SSH-signed vote to a remote relay."""
    from teaagent.consensus import VoteDecision
    from teaagent.vote_relay import VoteRelayClient

    client = VoteRelayClient(
        args.relay_url,
        api_token=getattr(args, 'api_token', None),
    )
    result = client.submit_vote(
        proposal_id=args.proposal_id,
        peer_name=args.peer_name,
        decision=VoteDecision(args.decision),
        task_description=args.task_description,
        private_key_path=args.private_key,
        comment=args.comment,
    )
    print(json.dumps(result, indent=2))
    return 0 if result.get('ok') else 1

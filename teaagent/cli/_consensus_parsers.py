"""Consensus CLI argument parsers."""

from __future__ import annotations

import argparse
from typing import Any, Callable, Optional


def _consensus_peers(
    subparsers: argparse._SubParsersAction,  # type: ignore[type-arg]
    list_handler: Optional[Callable] = None,
    add_handler: Optional[Callable] = None,
    remove_handler: Optional[Callable] = None,
    activate_handler: Optional[Callable] = None,
    deactivate_handler: Optional[Callable] = None,
) -> None:
    """Register consensus peers subcommands."""
    peers_parser = subparsers.add_parser('peers', help='Manage consensus peers')

    peers_subs = peers_parser.add_subparsers(
        dest='peers_command', help='Peer management commands'
    )

    # List peers
    list_cmd = peers_subs.add_parser('list', help='List all registered peers')
    list_cmd.add_argument('--storage', help='Path to peer registry storage')
    list_cmd.set_defaults(func=list_handler)

    # Add peer
    add_cmd = peers_subs.add_parser('add', help='Add a new peer')
    add_cmd.add_argument('name', help='Peer name')
    add_cmd.add_argument('--ssh-key', help='SSH public key')
    add_cmd.add_argument('--ssh-key-file', help='Path to SSH public key file')
    add_cmd.add_argument('--storage', help='Path to peer registry storage')
    add_cmd.set_defaults(func=add_handler)

    # Remove peer
    remove_cmd = peers_subs.add_parser('remove', help='Remove a peer')
    remove_cmd.add_argument('name', help='Peer name')
    remove_cmd.add_argument('--storage', help='Path to peer registry storage')
    remove_cmd.set_defaults(func=remove_handler)

    # Activate peer
    activate_cmd = peers_subs.add_parser('activate', help='Activate a peer')
    activate_cmd.add_argument('name', help='Peer name')
    activate_cmd.add_argument('--storage', help='Path to peer registry storage')
    activate_cmd.set_defaults(func=activate_handler)

    # Deactivate peer
    deactivate_cmd = peers_subs.add_parser('deactivate', help='Deactivate a peer')
    deactivate_cmd.add_argument('name', help='Peer name')
    deactivate_cmd.add_argument('--storage', help='Path to peer registry storage')
    deactivate_cmd.set_defaults(func=deactivate_handler)


def _consensus_config(
    subparsers: argparse._SubParsersAction,  # type: ignore[type-arg]
    set_handler: Optional[Callable] = None,
) -> None:
    """Register consensus config subcommands."""
    config_parser = subparsers.add_parser(
        'config', help='Manage consensus configuration'
    )

    config_subs = config_parser.add_subparsers(
        dest='config_command', help='Config management commands'
    )

    # Set config
    set_cmd = config_subs.add_parser('set', help='Set consensus configuration')
    set_cmd.add_argument(
        '--voting-threshold',
        choices=['simple_majority', 'supermajority', 'unanimous'],
        help='Voting threshold',
    )
    set_cmd.add_argument('--timeout', type=int, help='Consensus timeout in seconds')
    set_cmd.add_argument(
        '--require-all', action='store_true', help='Require all peers to vote'
    )
    set_cmd.add_argument('--allow-abstain', type=bool, help='Allow abstain votes')
    set_cmd.set_defaults(func=set_handler)


def register(
    subparsers: argparse._SubParsersAction,
    handlers: dict[str, Any],
) -> None:
    """Register consensus subcommands."""
    _consensus(
        subparsers,
        handlers.get('peers_list'),
        handlers.get('peers_add'),
        handlers.get('peers_remove'),
        handlers.get('peers_activate'),
        handlers.get('peers_deactivate'),
        handlers.get('config_set'),
        handlers.get('status'),
        handlers.get('history'),
        handlers.get('request'),
        handlers.get('vote'),
        handlers.get('wait'),
        handlers.get('votes_import'),
        handlers.get('relay_serve'),
        handlers.get('relay_submit'),
    )


def _consensus(
    subparsers: argparse._SubParsersAction,  # type: ignore[type-arg]
    peers_list_handler: Optional[Callable] = None,
    peers_add_handler: Optional[Callable] = None,
    peers_remove_handler: Optional[Callable] = None,
    peers_activate_handler: Optional[Callable] = None,
    peers_deactivate_handler: Optional[Callable] = None,
    config_set_handler: Optional[Callable] = None,
    status_handler: Optional[Callable] = None,
    history_handler: Optional[Callable] = None,
    request_handler: Optional[Callable] = None,
    vote_handler: Optional[Callable] = None,
    wait_handler: Optional[Callable] = None,
    votes_import_handler: Optional[Callable] = None,
    relay_serve_handler: Optional[Callable] = None,
    relay_submit_handler: Optional[Callable] = None,
) -> None:
    """Register consensus subcommands."""
    consensus_parser = subparsers.add_parser('consensus', help='Consensus management')

    consensus_subs = consensus_parser.add_subparsers(
        dest='consensus_command', help='Consensus commands'
    )

    # Peers subcommands
    _consensus_peers(
        consensus_subs,
        peers_list_handler,
        peers_add_handler,
        peers_remove_handler,
        peers_activate_handler,
        peers_deactivate_handler,
    )

    # Config subcommands
    _consensus_config(consensus_subs, config_set_handler)

    # Status command
    status_cmd = consensus_subs.add_parser('status', help='Show consensus status')
    status_cmd.add_argument('--storage', help='Path to consensus storage')
    status_cmd.add_argument('--peer-storage', help='Path to peer registry storage')
    status_cmd.add_argument(
        '--consensus-storage', help='Path to consensus state storage'
    )
    status_cmd.set_defaults(func=status_handler)

    # History command
    history_cmd = consensus_subs.add_parser(
        'history', help='Show consensus voting history'
    )
    history_cmd.add_argument('--storage', help='Path to consensus storage')
    history_cmd.add_argument('--peer-storage', help='Path to peer registry storage')
    history_cmd.add_argument(
        '--consensus-storage', help='Path to consensus state storage'
    )
    history_cmd.set_defaults(func=history_handler)

    # Request command
    request_cmd = consensus_subs.add_parser(
        'request', help='Request consensus for a task'
    )
    request_cmd.add_argument('task', help='Task description')
    request_cmd.add_argument(
        '--risk-level',
        choices=['low', 'medium', 'high', 'critical'],
        default='medium',
        help='Risk level',
    )
    request_cmd.add_argument(
        '--proposed-by', default='cli', help='Peer proposing the task'
    )
    request_cmd.add_argument(
        '--threshold',
        choices=['simple_majority', 'supermajority', 'unanimous'],
        help='Voting threshold',
    )
    request_cmd.add_argument('--storage', help='Path to consensus storage')
    request_cmd.add_argument('--peer-storage', help='Path to peer registry storage')
    request_cmd.add_argument(
        '--consensus-storage', help='Path to consensus state storage'
    )
    request_cmd.add_argument(
        '--wait',
        action='store_true',
        help='Poll until proposal reaches a terminal status',
    )
    request_cmd.add_argument(
        '--timeout',
        type=float,
        default=60.0,
        help='Seconds to wait when --wait is set',
    )
    request_cmd.add_argument(
        '--auto-approve',
        action='store_true',
        help='Cast approve votes from all active required peers (local dev)',
    )
    request_cmd.set_defaults(func=request_handler)

    wait_cmd = consensus_subs.add_parser(
        'wait', help='Poll until a proposal is approved, rejected, or timed out'
    )
    wait_cmd.add_argument('proposal_id', help='Proposal ID')
    wait_cmd.add_argument(
        '--timeout',
        type=float,
        default=60.0,
        help='Maximum seconds to poll',
    )
    wait_cmd.add_argument('--storage', help='Path to consensus storage')
    wait_cmd.add_argument('--peer-storage', help='Path to peer registry storage')
    wait_cmd.add_argument('--consensus-storage', help='Path to consensus state storage')
    wait_cmd.set_defaults(func=wait_handler)

    import_cmd = consensus_subs.add_parser(
        'votes-import', help='Import batched peer votes from JSON'
    )
    import_cmd.add_argument('votes_file', help='Path to votes JSON file')
    import_cmd.add_argument(
        '--no-auto-sign',
        action='store_true',
        help='Require explicit signature on each vote record',
    )
    import_cmd.add_argument('--storage', help='Path to consensus storage')
    import_cmd.add_argument('--peer-storage', help='Path to peer registry storage')
    import_cmd.add_argument(
        '--consensus-storage', help='Path to consensus state storage'
    )
    import_cmd.set_defaults(func=votes_import_handler)

    # Vote command
    vote_cmd = consensus_subs.add_parser('vote', help='Submit a vote on a proposal')
    vote_cmd.add_argument('proposal_id', help='Proposal ID')
    vote_cmd.add_argument('peer_name', help='Peer name')
    vote_cmd.add_argument(
        'decision', choices=['approve', 'reject', 'abstain'], help='Vote decision'
    )
    vote_cmd.add_argument('--comment', help='Vote comment')
    vote_cmd.add_argument('--storage', help='Path to consensus storage')
    vote_cmd.add_argument('--peer-storage', help='Path to peer registry storage')
    vote_cmd.add_argument('--consensus-storage', help='Path to consensus state storage')
    vote_cmd.set_defaults(func=vote_handler)

    relay_parser = consensus_subs.add_parser(
        'relay', help='SSH-signed vote relay for remote production peers'
    )
    relay_subs = relay_parser.add_subparsers(
        dest='relay_command', required=True, help='Relay commands'
    )
    relay_serve = relay_subs.add_parser('serve', help='Start vote relay HTTP server')
    relay_serve.add_argument('--host', default='127.0.0.1')
    relay_serve.add_argument('--port', type=int, default=8790)
    relay_serve.add_argument(
        '--allow-dev-signatures',
        action='store_true',
        help='Accept dev hash signatures (not for production)',
    )
    relay_serve.add_argument('--peer-storage', help='Path to peer registry storage')
    relay_serve.add_argument(
        '--consensus-storage', help='Path to consensus state storage'
    )
    relay_serve.set_defaults(func=relay_serve_handler)

    relay_submit = relay_subs.add_parser(
        'submit', help='Submit an SSH-signed vote to a remote relay'
    )
    relay_submit.add_argument('--relay-url', required=True, help='Relay base URL')
    relay_submit.add_argument('proposal_id', help='Proposal ID')
    relay_submit.add_argument('peer_name', help='Peer name')
    relay_submit.add_argument(
        'decision', choices=['approve', 'reject', 'abstain'], help='Vote decision'
    )
    relay_submit.add_argument(
        '--private-key',
        required=True,
        help='SSH private key path for signing',
    )
    relay_submit.add_argument(
        '--task-description',
        required=True,
        help='Task description from the proposal (for canonical signing)',
    )
    relay_submit.add_argument('--comment', help='Optional vote comment')
    relay_submit.set_defaults(func=relay_submit_handler)

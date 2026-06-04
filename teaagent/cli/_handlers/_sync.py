"""CLI handlers for federated multi-agent sync (TASK-011)."""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import ssl
from pathlib import Path

from teaagent.cli._output import print_json
from teaagent.federated_sync import FederatedGraphSync, SyncAck
from teaagent.graphqlite_store import GraphQLiteConfig, GraphQLiteGraphStore

logger = logging.getLogger(__name__)


def _graph_store_config(root: Path) -> GraphQLiteConfig:
    teaagent_dir = root / '.teaagent'
    teaagent_dir.mkdir(parents=True, exist_ok=True)
    return GraphQLiteConfig(database=str(teaagent_dir / 'graphqlite.db'))


def sync_export(args: argparse.Namespace) -> int:
    """Export federated sync message to file for P2P transfer.

    Args:
        args: CLI arguments with `root`, `agent_id`, and `output` attributes.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    root = Path(args.root).resolve()
    agent_id = args.agent_id
    output_path = Path(args.output)

    # Initialize graph store
    try:
        config = _graph_store_config(root)
        graph_store = GraphQLiteGraphStore(config)
    except (OSError, ValueError, ImportError, sqlite3.Error) as exc:
        logger.warning('Failed to initialize graph store: %s', exc)
        print_json(
            {
                'ok': False,
                'error': f'Failed to initialize graph store: {exc}',
            }
        )
        return 1

    # Initialize federated sync
    sync = FederatedGraphSync(root, agent_id, graph_store)

    # Create sync message with pending changes
    try:
        message = sync.create_sync_message()
    except (ValueError, OSError, TypeError) as exc:
        logger.warning('Failed to create sync message: %s', exc)
        print_json(
            {
                'ok': False,
                'error': f'Failed to create sync message: {exc}',
            }
        )
        return 1

    # Export to file
    try:
        sync.export_sync_message(message, output_path)
    except (OSError, ValueError) as exc:
        logger.warning('Failed to export sync message: %s', exc)
        print_json(
            {
                'ok': False,
                'error': f'Failed to export sync message: {exc}',
            }
        )
        return 1

    print_json(
        {
            'ok': True,
            'message_id': message.message_id,
            'sender_agent_id': message.sender_agent_id,
            'sequence_number': message.sequence_number,
            'graph_version': message.graph_version,
            'change_count': len(message.changes),
            'output_path': str(output_path),
        }
    )
    return 0


def sync_import(args: argparse.Namespace) -> int:
    """Import federated sync message from file and apply changes.

    Args:
        args: CLI arguments with `root`, `agent_id`, and `input` attributes.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    root = Path(args.root).resolve()
    agent_id = args.agent_id
    input_path = Path(args.input)

    if not input_path.exists():
        print_json(
            {
                'ok': False,
                'error': f'Input file not found: {input_path}',
            }
        )
        return 1

    # Initialize graph store
    try:
        config = _graph_store_config(root)
        graph_store = GraphQLiteGraphStore(config)
    except (OSError, ValueError, ImportError, sqlite3.Error) as exc:
        logger.warning('Failed to initialize graph store: %s', exc)
        print_json(
            {
                'ok': False,
                'error': f'Failed to initialize graph store: {exc}',
            }
        )
        return 1

    # Initialize federated sync
    sync = FederatedGraphSync(root, agent_id, graph_store)

    # Import sync message
    try:
        message = sync.import_sync_message(input_path)
    except (OSError, json.JSONDecodeError, ValueError, KeyError) as exc:
        logger.warning('Failed to import sync message: %s', exc)
        print_json(
            {
                'ok': False,
                'error': f'Failed to import sync message: {exc}',
            }
        )
        return 1

    if not message:
        print_json(
            {
                'ok': False,
                'error': 'Invalid sync message format',
            }
        )
        return 1

    # Process sync message
    try:
        ack: SyncAck = sync.process_sync_message(message)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        logger.warning('Failed to process sync message: %s', exc)
        print_json(
            {
                'ok': False,
                'error': f'Failed to process sync message: {exc}',
            }
        )
        return 1

    print_json(
        {
            'ok': True,
            'message_id': ack.message_id,
            'sender_agent_id': message.sender_agent_id,
            'receiver_agent_id': ack.receiver_agent_id,
            'accepted_changes': len(ack.accepted_changes),
            'rejected_changes': len(ack.rejected_changes),
            'conflicts': len(ack.conflicts),
            'accepted_change_ids': ack.accepted_changes,
            'rejected_change_ids': ack.rejected_changes,
            'conflict_details': ack.conflicts,
        }
    )
    return 0


def sync_status(args: argparse.Namespace) -> int:
    """Show current federated sync status.

    Args:
        args: CLI arguments with `root` and `agent_id` attributes.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    root = Path(args.root).resolve()
    agent_id = args.agent_id

    # Initialize federated sync (without graph store for status)
    sync = FederatedGraphSync(root, agent_id, graph_store=None)

    state = sync.get_sync_state()

    print_json(
        {
            'ok': True,
            'agent_id': state.agent_id,
            'graph_version': state.graph_version,
            'last_sync_time': state.last_sync_time,
            'sequence_number': state.sequence_number,
            'peer_count': len(state.peer_states),
            'peer_states': state.peer_states,
        }
    )
    return 0


def _signature_relay_ssl_context(
    args: argparse.Namespace,
) -> ssl.SSLContext | None:
    from teaagent.tls_server import build_server_ssl_context

    if not getattr(args, 'tls_cert', None):
        return None
    client_ca = (
        Path(args.tls_client_ca) if getattr(args, 'tls_client_ca', None) else None
    )
    return build_server_ssl_context(
        cert_file=Path(args.tls_cert),
        key_file=Path(args.tls_key),
        client_ca_file=client_ca,
    )


def sync_signature_relay_serve_command(args: argparse.Namespace) -> int:
    """Serve HTTP relay for WAN multi-sig approval signatures."""
    from pathlib import Path

    from teaagent.http_rate_limit import TokenRateLimiter
    from teaagent.signature_relay import SignatureRelayServer
    from teaagent.surface_auth import load_surface_auth_policy

    token_file = (
        Path(args.api_token_file) if getattr(args, 'api_token_file', None) else None
    )
    policy = load_surface_auth_policy(
        api_token=getattr(args, 'api_token', None),
        api_token_file=token_file,
        relay_mode=True,
    )
    rate_limiter = None
    rate_limit_calls = int(getattr(args, 'rate_limit_calls', 0))
    if rate_limit_calls > 0:
        rate_limiter = TokenRateLimiter(
            max_calls=rate_limit_calls,
            window_seconds=float(getattr(args, 'rate_limit_window', 60.0)),
        )
    try:
        relay = SignatureRelayServer(
            host=args.host,
            port=args.port,
            auth_policy=policy,
            ssl_context=_signature_relay_ssl_context(args),
            rate_limiter=rate_limiter,
        )
    except ValueError as exc:
        print_json({'ok': False, 'error': str(exc)})
        return 1
    relay.serve_blocking()
    return 0


def sync_signature_submit_command(args: argparse.Namespace) -> int:
    """POST an approval signature to a remote signature relay."""
    from teaagent.signature_relay import SignatureRelayClient

    client = SignatureRelayClient(api_token=getattr(args, 'api_token', None))
    submit_url = (getattr(args, 'submit_url', None) or '').strip()
    if not submit_url:
        relay_url = (getattr(args, 'relay_url', None) or '').strip()
        if not relay_url:
            print_json({'ok': False, 'error': 'provide --submit-url or --relay-url'})
            return 1
        submit_url = f'{relay_url.rstrip("/")}/api/v1/approval-signatures'
    result = client.post_signature(
        submit_url,
        {
            'request_id': args.request_id,
            'peer_id': args.peer_id,
            'signature': args.signature,
            'ssh_key_id': getattr(args, 'ssh_key_id', None),
        },
    )
    print_json(result)
    return 0 if result.get('ok') else 1

"""CLI handlers for federated multi-agent sync (TASK-011)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from teaagent.federated_sync import FederatedGraphSync, SyncAck
from teaagent.graphqlite_store import GraphQLiteConfig, GraphQLiteGraphStore


def print_json(data: dict) -> None:
    """Print JSON output."""
    print(json.dumps(data, indent=2))


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
        config = GraphQLiteConfig(path=root / '.teaagent' / 'graphqlite.db')
        graph_store = GraphQLiteGraphStore(config)
    except Exception as exc:
        print_json({
            'ok': False,
            'error': f'Failed to initialize graph store: {exc}',
        })
        return 1

    # Initialize federated sync
    sync = FederatedGraphSync(root, agent_id, graph_store)

    # Create sync message with pending changes
    try:
        message = sync.create_sync_message()
    except Exception as exc:
        print_json({
            'ok': False,
            'error': f'Failed to create sync message: {exc}',
        })
        return 1

    # Export to file
    try:
        sync.export_sync_message(message, output_path)
    except Exception as exc:
        print_json({
            'ok': False,
            'error': f'Failed to export sync message: {exc}',
        })
        return 1

    print_json({
        'ok': True,
        'message_id': message.message_id,
        'sender_agent_id': message.sender_agent_id,
        'sequence_number': message.sequence_number,
        'graph_version': message.graph_version,
        'change_count': len(message.changes),
        'output_path': str(output_path),
    })
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
        print_json({
            'ok': False,
            'error': f'Input file not found: {input_path}',
        })
        return 1

    # Initialize graph store
    try:
        config = GraphQLiteConfig(path=root / '.teaagent' / 'graphqlite.db')
        graph_store = GraphQLiteGraphStore(config)
    except Exception as exc:
        print_json({
            'ok': False,
            'error': f'Failed to initialize graph store: {exc}',
        })
        return 1

    # Initialize federated sync
    sync = FederatedGraphSync(root, agent_id, graph_store)

    # Import sync message
    try:
        message = sync.import_sync_message(input_path)
    except Exception as exc:
        print_json({
            'ok': False,
            'error': f'Failed to import sync message: {exc}',
        })
        return 1

    if not message:
        print_json({
            'ok': False,
            'error': 'Invalid sync message format',
        })
        return 1

    # Process sync message
    try:
        ack: SyncAck = sync.process_sync_message(message)
    except Exception as exc:
        print_json({
            'ok': False,
            'error': f'Failed to process sync message: {exc}',
        })
        return 1

    print_json({
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
    })
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

    print_json({
        'ok': True,
        'agent_id': state.agent_id,
        'graph_version': state.graph_version,
        'last_sync_time': state.last_sync_time,
        'sequence_number': state.sequence_number,
        'peer_count': len(state.peer_states),
        'peer_states': state.peer_states,
    })
    return 0

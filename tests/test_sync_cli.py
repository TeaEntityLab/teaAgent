"""Tests for federated sync CLI (TASK-011)."""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

from teaagent.cli._handlers._sync import sync_export, sync_import, sync_status
from teaagent.federated_sync import FederatedGraphSync


def test_sync_status_without_graph_store() -> None:
    """Test sync status without graph store."""
    with tempfile.TemporaryDirectory() as tmp:
        args = argparse.Namespace(
            root=tmp,
            agent_id='test-agent',
        )

        result = sync_status(args)

        assert result == 0


def test_sync_export_without_graph_store() -> None:
    """Test sync export creates the graph store path in a fresh workspace."""
    with tempfile.TemporaryDirectory() as tmp:
        output_path = Path(tmp) / 'sync.json'
        args = argparse.Namespace(
            root=tmp,
            agent_id='test-agent',
            output=str(output_path),
        )

        result = sync_export(args)

        assert result == 0
        assert output_path.is_file()


def test_sync_import_nonexistent_file() -> None:
    """Test sync import with nonexistent file."""
    with tempfile.TemporaryDirectory() as tmp:
        args = argparse.Namespace(
            root=tmp,
            agent_id='test-agent',
            input='/nonexistent/file.json',
        )

        result = sync_import(args)

        assert result == 1


def test_federated_sync_initialization() -> None:
    """Test FederatedGraphSync initialization."""
    with tempfile.TemporaryDirectory() as tmp:
        sync = FederatedGraphSync(tmp, 'test-agent', graph_store=None)

        state = sync.get_sync_state()
        assert state.agent_id == 'test-agent'
        assert state.graph_version == '0'
        assert state.sequence_number == 0


def test_federated_sync_record_node_change() -> None:
    """Test recording node changes."""
    with tempfile.TemporaryDirectory() as tmp:
        sync = FederatedGraphSync(tmp, 'test-agent', graph_store=None)

        change = sync.record_node_change(
            'node-1',
            'node_add',
            {'label': 'TestNode', 'data': 'test'},
        )

        assert change.node_id == 'node-1'
        assert change.change_type == 'node_add'
        assert change.source_agent_id == 'test-agent'


def test_federated_sync_record_edge_change() -> None:
    """Test recording edge changes."""
    with tempfile.TemporaryDirectory() as tmp:
        sync = FederatedGraphSync(tmp, 'test-agent', graph_store=None)

        change = sync.record_edge_change(
            'edge-1',
            'edge_add',
            {'from': 'node-1', 'to': 'node-2', 'edge_type': 'RELATED'},
        )

        assert change.edge_id == 'edge-1'
        assert change.change_type == 'edge_add'
        assert change.source_agent_id == 'test-agent'


def test_federated_sync_create_sync_message() -> None:
    """Test creating sync message."""
    with tempfile.TemporaryDirectory() as tmp:
        sync = FederatedGraphSync(tmp, 'test-agent', graph_store=None)

        sync.record_node_change('node-1', 'node_add', {'label': 'Test'})
        sync.record_edge_change(
            'edge-1', 'edge_add', {'from': 'node-1', 'to': 'node-2'}
        )

        message = sync.create_sync_message()

        assert message.sender_agent_id == 'test-agent'
        assert len(message.changes) == 2
        assert message.sequence_number == 1


def test_federated_sync_export_import_roundtrip() -> None:
    """Test export and import roundtrip."""
    with tempfile.TemporaryDirectory() as tmp:
        sync = FederatedGraphSync(tmp, 'test-agent', graph_store=None)

        sync.record_node_change('node-1', 'node_add', {'label': 'Test'})
        message = sync.create_sync_message()

        export_path = Path(tmp) / 'sync.json'
        sync.export_sync_message(message, export_path)

        assert export_path.exists()

        # Import back
        imported_message = sync.import_sync_message(export_path)

        assert imported_message is not None
        assert imported_message.message_id == message.message_id
        assert len(imported_message.changes) == len(message.changes)


def test_federated_sync_process_sync_message_without_store() -> None:
    """Test processing sync message without graph store."""
    with tempfile.TemporaryDirectory() as tmp:
        sync = FederatedGraphSync(tmp, 'test-agent', graph_store=None)

        sync.record_node_change('node-1', 'node_add', {'label': 'Test'})
        message = sync.create_sync_message()

        ack = sync.process_sync_message(message)

        assert len(ack.rejected_changes) == 1
        assert 'No graph store available' in ack.conflicts

"""Tests for federated graph sync protocol."""

from __future__ import annotations

import tempfile
from pathlib import Path

from teaagent.federated_sync import (
    FederatedGraphSync,
    GraphChange,
    SyncAck,
    SyncMessage,
    SyncState,
)


def test_graph_change_creation():
    change = GraphChange(
        change_id='change-1',
        timestamp=1234567890.0,
        node_id='node-1',
        change_type='node_add',
        data={'label': 'Class', 'name': 'MyClass'},
        source_agent_id='agent-1',
    )
    assert change.change_id == 'change-1'
    assert change.node_id == 'node-1'
    assert change.change_type == 'node_add'
    assert change.source_agent_id == 'agent-1'


def test_sync_message_creation():
    changes = [
        GraphChange(
            change_id='change-1',
            timestamp=1234567890.0,
            node_id='node-1',
            change_type='node_add',
            data={'label': 'Class'},
            source_agent_id='agent-1',
        )
    ]
    message = SyncMessage(
        message_id='msg-1',
        sender_agent_id='agent-1',
        timestamp=1234567890.0,
        changes=changes,
        sequence_number=1,
        graph_version='1',
    )
    assert message.message_id == 'msg-1'
    assert message.sender_agent_id == 'agent-1'
    assert len(message.changes) == 1
    assert message.sequence_number == 1


def test_sync_ack_creation():
    ack = SyncAck(
        message_id='msg-1',
        receiver_agent_id='agent-2',
        timestamp=1234567890.0,
        accepted_changes=['change-1'],
        rejected_changes=['change-2'],
        conflicts=['conflict-1'],
    )
    assert ack.message_id == 'msg-1'
    assert ack.receiver_agent_id == 'agent-2'
    assert len(ack.accepted_changes) == 1
    assert len(ack.rejected_changes) == 1


def test_sync_state_creation():
    state = SyncState(
        agent_id='agent-1',
        graph_version='1',
        last_sync_time=1234567890.0,
        sequence_number=5,
    )
    assert state.agent_id == 'agent-1'
    assert state.graph_version == '1'
    assert state.sequence_number == 5


def test_federated_sync_initialization():
    with tempfile.TemporaryDirectory() as tmpdir:
        sync = FederatedGraphSync(tmpdir, 'agent-1')
        state = sync.get_sync_state()

        assert state.agent_id == 'agent-1'
        assert state.graph_version == '0'
        assert state.sequence_number == 0


def test_federated_sync_load_state():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create initial sync state
        sync1 = FederatedGraphSync(tmpdir, 'agent-1')
        sync1._update_graph_version()

        # Load in new instance
        sync2 = FederatedGraphSync(tmpdir, 'agent-1')
        state = sync2.get_sync_state()

        assert state.graph_version == '1'


def test_record_node_change():
    with tempfile.TemporaryDirectory() as tmpdir:
        sync = FederatedGraphSync(tmpdir, 'agent-1')
        change = sync.record_node_change(
            node_id='node-1',
            change_type='node_add',
            data={'label': 'Class', 'name': 'MyClass'},
        )

        assert change.node_id == 'node-1'
        assert change.change_type == 'node_add'
        assert change.source_agent_id == 'agent-1'
        assert len(sync._pending_changes) == 1


def test_record_edge_change():
    with tempfile.TemporaryDirectory() as tmpdir:
        sync = FederatedGraphSync(tmpdir, 'agent-1')
        change = sync.record_edge_change(
            edge_id='edge-1',
            change_type='edge_add',
            data={'from': 'node-1', 'to': 'node-2', 'edge_type': 'CALLS'},
        )

        assert change.edge_id == 'edge-1'
        assert change.change_type == 'edge_add'
        assert len(sync._pending_changes) == 1


def test_create_sync_message():
    with tempfile.TemporaryDirectory() as tmpdir:
        sync = FederatedGraphSync(tmpdir, 'agent-1')
        sync.record_node_change('node-1', 'node_add', {'label': 'Class'})
        sync.record_node_change('node-2', 'node_add', {'label': 'Function'})

        message = sync.create_sync_message()

        assert message.sender_agent_id == 'agent-1'
        assert len(message.changes) == 2
        assert message.sequence_number == 1
        assert len(sync._pending_changes) == 0  # Changes should be cleared


def test_process_sync_message_without_store():
    with tempfile.TemporaryDirectory() as tmpdir:
        sync = FederatedGraphSync(tmpdir, 'agent-2')

        message = SyncMessage(
            message_id='msg-1',
            sender_agent_id='agent-1',
            timestamp=1234567890.0,
            changes=[],
            sequence_number=1,
            graph_version='1',
        )

        ack = sync.process_sync_message(message)

        assert ack.receiver_agent_id == 'agent-2'
        assert len(ack.rejected_changes) == 0  # No changes to reject
        assert 'No graph store available' in ack.conflicts


def test_export_import_sync_message():
    with tempfile.TemporaryDirectory() as tmpdir:
        sync = FederatedGraphSync(tmpdir, 'agent-1')
        sync.record_node_change('node-1', 'node_add', {'label': 'Class'})

        message = sync.create_sync_message()

        # Export
        export_path = Path(tmpdir) / 'sync_message.json'
        sync.export_sync_message(message, export_path)

        assert export_path.exists()

        # Import
        sync2 = FederatedGraphSync(tmpdir, 'agent-2')
        imported = sync2.import_sync_message(export_path)

        assert imported is not None
        assert imported.message_id == message.message_id
        assert imported.sender_agent_id == message.sender_agent_id
        assert len(imported.changes) == len(message.changes)


def test_sync_state_persistence():
    with tempfile.TemporaryDirectory() as tmpdir:
        sync1 = FederatedGraphSync(tmpdir, 'agent-1')
        sync1.record_node_change('node-1', 'node_add', {'label': 'Class'})
        sync1.create_sync_message()

        # Update peer state
        sync1._sync_state.peer_states['agent-2'] = {
            'last_seen_sequence': 1,
            'graph_version': '1',
            'last_seen_time': 1234567890.0,
        }
        sync1._save_sync_state()

        # Load in new instance
        sync2 = FederatedGraphSync(tmpdir, 'agent-1')
        state = sync2.get_sync_state()

        assert state.sequence_number == 1
        assert 'agent-2' in state.peer_states
        assert state.peer_states['agent-2']['last_seen_sequence'] == 1


def test_change_id_generation():
    with tempfile.TemporaryDirectory() as tmpdir:
        sync = FederatedGraphSync(tmpdir, 'agent-1')

        # Same data should generate same ID
        change1 = sync.record_node_change('node-1', 'node_add', {'label': 'Class'})
        sync._pending_changes.clear()
        change2 = sync.record_node_change('node-1', 'node_add', {'label': 'Class'})

        assert change1.change_id == change2.change_id

        # Different data should generate different ID
        change3 = sync.record_node_change('node-1', 'node_add', {'label': 'Function'})
        assert change1.change_id != change3.change_id


def test_graph_version_update():
    with tempfile.TemporaryDirectory() as tmpdir:
        sync = FederatedGraphSync(tmpdir, 'agent-1')

        assert sync.get_sync_state().graph_version == '0'

        sync._update_graph_version()
        assert sync.get_sync_state().graph_version == '1'

        sync._update_graph_version()
        assert sync.get_sync_state().graph_version == '2'

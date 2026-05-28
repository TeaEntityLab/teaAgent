"""Tests for federated sync CLI (TASK-011)."""

from __future__ import annotations

import argparse
import tempfile
import unittest
from pathlib import Path

from teaagent.cli._handlers._sync import sync_export, sync_import, sync_status
from teaagent.federated_sync import FederatedGraphSync


class SyncCLITests(unittest.TestCase):
    def test_sync_status_without_graph_store(self) -> None:
        """Test sync status without graph store."""
        with tempfile.TemporaryDirectory() as tmp:
            args = argparse.Namespace(
                root=tmp,
                agent_id='test-agent',
            )

            result = sync_status(args)

            self.assertEqual(result, 0)

    def test_sync_export_without_graph_store(self) -> None:
        """Test sync export without graph store."""
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / 'sync.json'
            args = argparse.Namespace(
                root=tmp,
                agent_id='test-agent',
                output=str(output_path),
            )

            result = sync_export(args)

            # Should fail without graph store
            self.assertEqual(result, 1)

    def test_sync_import_nonexistent_file(self) -> None:
        """Test sync import with nonexistent file."""
        with tempfile.TemporaryDirectory() as tmp:
            args = argparse.Namespace(
                root=tmp,
                agent_id='test-agent',
                input='/nonexistent/file.json',
            )

            result = sync_import(args)

            self.assertEqual(result, 1)

    def test_federated_sync_initialization(self) -> None:
        """Test FederatedGraphSync initialization."""
        with tempfile.TemporaryDirectory() as tmp:
            sync = FederatedGraphSync(tmp, 'test-agent', graph_store=None)

            state = sync.get_sync_state()
            self.assertEqual(state.agent_id, 'test-agent')
            self.assertEqual(state.graph_version, '0')
            self.assertEqual(state.sequence_number, 0)

    def test_federated_sync_record_node_change(self) -> None:
        """Test recording node changes."""
        with tempfile.TemporaryDirectory() as tmp:
            sync = FederatedGraphSync(tmp, 'test-agent', graph_store=None)

            change = sync.record_node_change(
                'node-1',
                'node_add',
                {'label': 'TestNode', 'data': 'test'},
            )

            self.assertEqual(change.node_id, 'node-1')
            self.assertEqual(change.change_type, 'node_add')
            self.assertEqual(change.source_agent_id, 'test-agent')

    def test_federated_sync_record_edge_change(self) -> None:
        """Test recording edge changes."""
        with tempfile.TemporaryDirectory() as tmp:
            sync = FederatedGraphSync(tmp, 'test-agent', graph_store=None)

            change = sync.record_edge_change(
                'edge-1',
                'edge_add',
                {'from': 'node-1', 'to': 'node-2', 'edge_type': 'RELATED'},
            )

            self.assertEqual(change.edge_id, 'edge-1')
            self.assertEqual(change.change_type, 'edge_add')
            self.assertEqual(change.source_agent_id, 'test-agent')

    def test_federated_sync_create_sync_message(self) -> None:
        """Test creating sync message."""
        with tempfile.TemporaryDirectory() as tmp:
            sync = FederatedGraphSync(tmp, 'test-agent', graph_store=None)

            sync.record_node_change('node-1', 'node_add', {'label': 'Test'})
            sync.record_edge_change(
                'edge-1', 'edge_add', {'from': 'node-1', 'to': 'node-2'}
            )

            message = sync.create_sync_message()

            self.assertEqual(message.sender_agent_id, 'test-agent')
            self.assertEqual(len(message.changes), 2)
            self.assertEqual(message.sequence_number, 1)

    def test_federated_sync_export_import_roundtrip(self) -> None:
        """Test export and import roundtrip."""
        with tempfile.TemporaryDirectory() as tmp:
            sync = FederatedGraphSync(tmp, 'test-agent', graph_store=None)

            sync.record_node_change('node-1', 'node_add', {'label': 'Test'})
            message = sync.create_sync_message()

            export_path = Path(tmp) / 'sync.json'
            sync.export_sync_message(message, export_path)

            self.assertTrue(export_path.exists())

            # Import back
            imported_message = sync.import_sync_message(export_path)

            self.assertIsNotNone(imported_message)
            self.assertEqual(imported_message.message_id, message.message_id)
            self.assertEqual(len(imported_message.changes), len(message.changes))

    def test_federated_sync_process_sync_message_without_store(self) -> None:
        """Test processing sync message without graph store."""
        with tempfile.TemporaryDirectory() as tmp:
            sync = FederatedGraphSync(tmp, 'test-agent', graph_store=None)

            sync.record_node_change('node-1', 'node_add', {'label': 'Test'})
            message = sync.create_sync_message()

            ack = sync.process_sync_message(message)

            self.assertEqual(len(ack.rejected_changes), 1)
            self.assertIn('No graph store available', ack.conflicts)


if __name__ == '__main__':
    unittest.main()

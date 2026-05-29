"""Tests for federated graph sync protocol."""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

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


def test_concurrent_record_node_changes():
    import threading

    with tempfile.TemporaryDirectory() as tmpdir:
        sync = FederatedGraphSync(tmpdir, 'agent-1')

        def record(i: int) -> None:
            sync.record_node_change(f'node-{i}', 'node_add', {'i': i})

        threads = [threading.Thread(target=record, args=(i,)) for i in range(10)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        message = sync.create_sync_message()
        assert len(message.changes) == 10


def test_import_sync_message_oserror_returns_none(tmp_path: Path):
    sync = FederatedGraphSync(str(tmp_path), 'agent-1')
    missing = tmp_path / 'does-not-exist.json'
    assert sync.import_sync_message(missing) is None


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


async def _collect_signatures_case(
    tmpdir: str,
    *,
    request_id: str = 'req-async-1',
    required_approvals: int = 1,
    submit_delay: float = 0.12,
) -> tuple[list, int]:
    """Collect signatures while a background task ticks the event loop."""
    sync = FederatedGraphSync(tmpdir, 'agent-1')
    ticks = 0

    async def ticker() -> None:
        nonlocal ticks
        for _ in range(8):
            await asyncio.sleep(0.05)
            ticks += 1

    async def delayed_submit() -> None:
        await asyncio.sleep(submit_delay)
        sync.submit_approval_signature(request_id, 'peer-1', 'sig-abc')

    ticker_task = asyncio.create_task(ticker())
    submit_task = asyncio.create_task(delayed_submit())
    signatures = await sync.collect_approval_signatures(
        request_id,
        timeout_seconds=2,
        required_approvals=required_approvals,
    )
    await ticker_task
    await submit_task
    return signatures, ticks


def test_collect_approval_signatures_async_non_blocking():
    """Event loop must stay responsive while polling (asyncio.sleep, not time.sleep)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        signatures, ticks = asyncio.run(_collect_signatures_case(tmpdir))
        assert ticks >= 2
        assert len(signatures) == 1
        assert signatures[0].peer_id == 'peer-1'
        assert signatures[0].signature == 'sig-abc'


def test_collect_approval_signatures_quorum_and_dedup():
    with tempfile.TemporaryDirectory() as tmpdir:
        sync = FederatedGraphSync(tmpdir, 'agent-1')
        request_id = 'req-quorum'
        sync.submit_approval_signature(request_id, 'peer-a', 'sig-a')
        sync.submit_approval_signature(request_id, 'peer-b', 'sig-b')
        signatures = asyncio.run(
            sync.collect_approval_signatures(
                request_id,
                timeout_seconds=1,
                required_approvals=2,
            )
        )
        peer_ids = {sig.peer_id for sig in signatures}
        assert peer_ids == {'peer-a', 'peer-b'}


def test_collect_approval_signatures_uses_async_sleep():
    with tempfile.TemporaryDirectory() as tmpdir:
        sync = FederatedGraphSync(tmpdir, 'agent-1')
        sleep_calls: list[float] = []
        real_sleep = asyncio.sleep

        async def tracked_sleep(delay: float) -> None:
            sleep_calls.append(delay)
            await real_sleep(0)

        async def run() -> None:
            with patch('asyncio.sleep', tracked_sleep):
                await sync.collect_approval_signatures(
                    'req-none',
                    timeout_seconds=0.25,
                    required_approvals=1,
                )

        asyncio.run(run())
        assert sleep_calls


def test_collect_approval_signatures_rejects_missing_auth_token():
    with tempfile.TemporaryDirectory() as tmpdir:
        sync = FederatedGraphSync(tmpdir, 'agent-1')
        request_id = 'req-auth'
        approvals_dir = Path(tmpdir) / '.teaagent' / 'pending_approvals'
        approvals_dir.mkdir(parents=True, exist_ok=True)
        sig_path = approvals_dir / f'{request_id}_signature_peer-x.json'
        sig_path.write_text(
            json.dumps(
                {
                    'request_id': request_id,
                    'peer_id': 'peer-x',
                    'signature': 'sig-x',
                    'timestamp': 1.0,
                }
            ),
            encoding='utf-8',
        )
        with patch.dict(os.environ, {'TEAAGENT_FEDERATED_SIGNATURE_TOKEN': 'secret'}):
            signatures = asyncio.run(
                sync.collect_approval_signatures(
                    request_id,
                    timeout_seconds=0.3,
                    required_approvals=1,
                )
            )
        assert signatures == []


def test_submit_approval_signature_includes_auth_token_when_configured():
    with tempfile.TemporaryDirectory() as tmpdir:
        sync = FederatedGraphSync(tmpdir, 'agent-1')
        request_id = 'req-submit-auth'
        with patch.dict(os.environ, {'TEAAGENT_FEDERATED_SIGNATURE_TOKEN': 'secret'}):
            assert sync.submit_approval_signature(request_id, 'peer-1', 'sig-1')
            sig_path = (
                Path(tmpdir)
                / '.teaagent'
                / 'pending_approvals'
                / f'{request_id}_signature_peer-1.json'
            )
            data = json.loads(sig_path.read_text(encoding='utf-8'))
            assert data['auth_token'] == 'secret'

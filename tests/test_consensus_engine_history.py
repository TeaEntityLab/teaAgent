"""Tests for consensus engine history listing."""

import tempfile
from pathlib import Path

from teaagent.consensus import (
    ConsensusConfig,
    ConsensusEngine,
    ConsensusStatus,
    PeerIdentity,
    PeerRegistry,
    RiskLevel,
)


def test_list_all_consensus_includes_active_and_completed() -> None:
    """list_all_consensus returns every persisted state, not just active votes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        peer_storage = Path(tmpdir) / 'peers.json'
        consensus_storage = Path(tmpdir) / 'consensus.json'
        registry = PeerRegistry(storage_path=peer_storage)
        registry.register(
            PeerIdentity(
                name='peer1',
                ssh_public_key='ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ...',
            )
        )
        registry.activate('peer1')

        engine = ConsensusEngine(
            peer_registry=registry,
            config=ConsensusConfig(),
            storage_path=consensus_storage,
        )
        state = engine.request_consensus(
            task_description='Ship feature',
            risk_level=RiskLevel.MEDIUM,
            proposed_by='peer1',
        )
        active_id = state.proposal.id
        assert engine.list_active_consensus()
        assert len(engine.list_all_consensus()) == 1

        assert engine.cancel_consensus(active_id, cancelled_by='peer1') is True
        assert engine.list_active_consensus() == []
        all_states = engine.list_all_consensus()
        assert len(all_states) == 1
        assert all_states[0].proposal.id == active_id
        assert all_states[0].status == ConsensusStatus.CANCELLED

        reloaded = ConsensusEngine(
            peer_registry=PeerRegistry(storage_path=peer_storage),
            config=ConsensusConfig(),
            storage_path=consensus_storage,
        )
        assert len(reloaded.list_all_consensus()) == 1

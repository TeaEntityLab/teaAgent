"""Tests for consensus CLI handlers."""

import argparse
import tempfile
from pathlib import Path

from teaagent.cli._handlers._consensus import (
    consensus_cancel_command,
    consensus_config_set_command,
    consensus_history_command,
    consensus_peers_activate_command,
    consensus_peers_add_command,
    consensus_peers_deactivate_command,
    consensus_peers_list_command,
    consensus_peers_remove_command,
    consensus_request_command,
    consensus_status_command,
    consensus_vote_command,
)


def test_consensus_peers_list_empty():
    """Test listing peers when none are registered."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_path = Path(tmpdir) / 'peers.json'
        args = argparse.Namespace(storage=str(storage_path))
        result = consensus_peers_list_command(args)
        assert result == 0


def test_consensus_peers_add():
    """Test adding a peer."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_path = Path(tmpdir) / 'peers.json'
        args = argparse.Namespace(
            name='peer1',
            ssh_key='ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ...',
            ssh_key_file=None,
            storage=str(storage_path),
        )
        result = consensus_peers_add_command(args)
        assert result == 0


def test_consensus_peers_list_after_add():
    """Test listing peers after adding one."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_path = Path(tmpdir) / 'peers.json'
        # Add a peer
        add_args = argparse.Namespace(
            name='peer1',
            ssh_key='ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ...',
            ssh_key_file=None,
            storage=str(storage_path),
        )
        consensus_peers_add_command(add_args)

        # List peers
        list_args = argparse.Namespace(storage=str(storage_path))
        result = consensus_peers_list_command(list_args)
        assert result == 0


def test_consensus_peers_remove():
    """Test removing a peer."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_path = Path(tmpdir) / 'peers.json'
        # Add a peer
        add_args = argparse.Namespace(
            name='peer1',
            ssh_key='ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ...',
            ssh_key_file=None,
            storage=str(storage_path),
        )
        consensus_peers_add_command(add_args)

        # Remove the peer
        remove_args = argparse.Namespace(name='peer1', storage=str(storage_path))
        result = consensus_peers_remove_command(remove_args)
        assert result == 0


def test_consensus_peers_activate():
    """Test activating a peer."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_path = Path(tmpdir) / 'peers.json'
        # Add a peer
        add_args = argparse.Namespace(
            name='peer1',
            ssh_key='ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ...',
            ssh_key_file=None,
            storage=str(storage_path),
        )
        consensus_peers_add_command(add_args)

        # Activate the peer
        activate_args = argparse.Namespace(name='peer1', storage=str(storage_path))
        result = consensus_peers_activate_command(activate_args)
        assert result == 0


def test_consensus_peers_deactivate():
    """Test deactivating a peer."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_path = Path(tmpdir) / 'peers.json'
        # Add a peer
        add_args = argparse.Namespace(
            name='peer1',
            ssh_key='ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ...',
            ssh_key_file=None,
            storage=str(storage_path),
        )
        consensus_peers_add_command(add_args)

        # Deactivate the peer
        deactivate_args = argparse.Namespace(name='peer1', storage=str(storage_path))
        result = consensus_peers_deactivate_command(deactivate_args)
        assert result == 0


def test_consensus_status():
    """Test showing consensus status."""
    with tempfile.TemporaryDirectory() as tmpdir:
        peer_storage = Path(tmpdir) / 'peers.json'
        consensus_storage = Path(tmpdir) / 'consensus.json'
        args = argparse.Namespace(
            storage=tmpdir,
            peer_storage=str(peer_storage),
            consensus_storage=str(consensus_storage),
        )
        result = consensus_status_command(args)
        assert result == 0


def test_consensus_history():
    """Test showing consensus history."""
    with tempfile.TemporaryDirectory() as tmpdir:
        peer_storage = Path(tmpdir) / 'peers.json'
        consensus_storage = Path(tmpdir) / 'consensus.json'
        args = argparse.Namespace(
            storage=tmpdir,
            peer_storage=str(peer_storage),
            consensus_storage=str(consensus_storage),
        )
        result = consensus_history_command(args)
        assert result == 0


def test_consensus_config_set():
    """Test setting consensus configuration."""
    args = argparse.Namespace(
        voting_threshold='supermajority',
        timeout=300,
        require_all=False,
        allow_abstain=True,
    )
    result = consensus_config_set_command(args)
    assert result == 0


def test_consensus_request():
    """Test requesting consensus for a task."""
    with tempfile.TemporaryDirectory() as tmpdir:
        peer_storage = Path(tmpdir) / 'peers.json'
        consensus_storage = Path(tmpdir) / 'consensus.json'
        # Add a peer first
        add_args = argparse.Namespace(
            name='peer1',
            ssh_key='ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ...',
            ssh_key_file=None,
            storage=str(peer_storage),
        )
        consensus_peers_add_command(add_args)

        # Request consensus
        request_args = argparse.Namespace(
            task='Deploy to production',
            risk_level='high',
            proposed_by='admin',
            threshold=None,
            storage=tmpdir,
            peer_storage=str(peer_storage),
            consensus_storage=str(consensus_storage),
        )
        result = consensus_request_command(request_args)
        assert result == 0


def test_consensus_vote():
    """Test submitting a vote."""
    with tempfile.TemporaryDirectory() as tmpdir:
        peer_storage = Path(tmpdir) / 'peers.json'
        consensus_storage = Path(tmpdir) / 'consensus.json'
        # Add a peer
        add_args = argparse.Namespace(
            name='peer1',
            ssh_key='ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ...',
            ssh_key_file=None,
            storage=str(peer_storage),
        )
        consensus_peers_add_command(add_args)

        # Request consensus
        request_args = argparse.Namespace(
            task='Deploy to production',
            risk_level='high',
            proposed_by='admin',
            threshold=None,
            storage=tmpdir,
            peer_storage=str(peer_storage),
            consensus_storage=str(consensus_storage),
        )
        consensus_request_command(request_args)

        # Get the proposal ID (would need to retrieve from engine in real usage)
        # For test, we'll use a placeholder
        vote_args = argparse.Namespace(
            proposal_id='prop-placeholder',
            peer_name='peer1',
            decision='approve',
            comment='Looks good',
            storage=tmpdir,
            peer_storage=str(peer_storage),
            consensus_storage=str(consensus_storage),
        )
        # This will fail because proposal_id doesn't exist, but that's expected
        result = consensus_vote_command(vote_args)
        # Should fail with "not found"
        assert result == 1


def test_consensus_cancel_command() -> None:
    """Cancel an active proposal and surface cancelled_by in the result."""
    with tempfile.TemporaryDirectory() as tmpdir:
        peer_storage = Path(tmpdir) / 'peers.json'
        consensus_storage = Path(tmpdir) / 'consensus.json'
        add_args = argparse.Namespace(
            name='peer1',
            ssh_key='ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ...',
            ssh_key_file=None,
            storage=str(peer_storage),
        )
        consensus_peers_add_command(add_args)
        consensus_peers_activate_command(
            argparse.Namespace(name='peer1', storage=str(peer_storage))
        )
        request_args = argparse.Namespace(
            task='Deploy to production',
            risk_level='high',
            proposed_by='admin',
            threshold=None,
            storage=tmpdir,
            peer_storage=str(peer_storage),
            consensus_storage=str(consensus_storage),
            wait=False,
            timeout=1.0,
            auto_approve=False,
        )
        assert consensus_request_command(request_args) == 0

        from teaagent.consensus import ConsensusConfig, ConsensusEngine, PeerRegistry

        engine = ConsensusEngine(
            peer_registry=PeerRegistry(storage_path=peer_storage),
            config=ConsensusConfig(),
            storage_path=consensus_storage,
        )
        active = engine.list_active_consensus()
        assert active
        proposal_id = active[0].proposal.id

        cancel_args = argparse.Namespace(
            proposal_id=proposal_id,
            cancelled_by='cli-operator',
            storage=tmpdir,
            peer_storage=str(peer_storage),
            consensus_storage=str(consensus_storage),
        )
        assert consensus_cancel_command(cancel_args) == 0
        reloaded = ConsensusEngine(
            peer_registry=PeerRegistry(storage_path=peer_storage),
            config=ConsensusConfig(),
            storage_path=consensus_storage,
        )
        final = reloaded.get_consensus_status(proposal_id)
        assert final is not None
        assert final.cancelled_by == 'cli-operator'

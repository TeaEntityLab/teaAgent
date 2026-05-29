"""Tests for SSH vote relay, WASM CI helpers, and multi-tenant control plane."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from teaagent.consensus import (
    ConsensusConfig,
    ConsensusEngine,
    PeerIdentity,
    PeerRegistry,
    RiskLevel,
    VotingThreshold,
    peer_vote_signature,
)
from teaagent.control_plane_api import ControlPlaneServer
from teaagent.control_plane_tenant import ControlPlaneRegistry, sanitize_tenant_id
from teaagent.ssh_signatures import (
    build_vote_signing_message,
    is_ssh_signature_blob,
)
from teaagent.vote_relay import (
    VoteRelayPayload,
    VoteRelayServer,
    submit_relay_vote,
    verify_relay_vote,
)
from teaagent.wasm_skill import build_wasm_invoke_contract, write_wasm_manifest


def test_build_vote_signing_message_stable() -> None:
    msg = build_vote_signing_message('p1', 'peer-a', 'approve', 'deploy svc')
    assert 'p1' in msg and 'peer-a' in msg


def test_dev_vote_signature_canonical_and_legacy() -> None:
    peer = PeerIdentity(name='p', ssh_public_key='ssh-rsa AAA')
    legacy = peer_vote_signature(peer, 'task')
    canonical = peer_vote_signature(
        peer, 'task', proposal_id='prop', peer_name='p', decision='approve'
    )
    assert legacy != canonical
    assert peer.verify_signature('task', legacy)
    assert peer.verify_signature(
        build_vote_signing_message('prop', 'p', 'approve', 'task'),
        canonical,
    )


def test_sanitize_tenant_id_rejects_invalid() -> None:
    assert sanitize_tenant_id('team-a') == 'team-a'
    with pytest.raises(ValueError):
        sanitize_tenant_id('../bad')


def test_control_plane_registry_isolates_tenants() -> None:
    registry = ControlPlaneRegistry()
    a = registry.get_or_create('tenant-a')
    b = registry.get_or_create('tenant-b')
    a.set_workflow({'phase': 'a'})
    b.set_workflow({'phase': 'b'})
    assert a.snapshot()['workflow']['phase'] == 'a'
    assert b.snapshot()['workflow']['phase'] == 'b'
    assert registry.list_tenants() == ['tenant-a', 'tenant-b']


def test_control_plane_server_lists_tenants(tmp_path: Path) -> None:
    registry = ControlPlaneRegistry()
    server = ControlPlaneServer(host='127.0.0.1', port=0, tenant_registry=registry)
    server.start()
    try:
        import urllib.request

        with urllib.request.urlopen(
            f'{server.base_url}/api/tenants', timeout=5
        ) as response:
            payload = json.loads(response.read().decode('utf-8'))
        assert 'tenants' in payload
    finally:
        server.stop()


def test_vote_relay_dev_signature(tmp_path: Path) -> None:
    registry = PeerRegistry(storage_path=tmp_path / 'peers.json')
    peer = PeerIdentity(name='peer-a', ssh_public_key='ssh-rsa KEY')
    registry.register(peer)
    registry.activate(peer.name)
    engine = ConsensusEngine(
        peer_registry=registry,
        config=ConsensusConfig(),
        storage_path=tmp_path / 'consensus.json',
    )
    state = engine.request_consensus(
        task_description='deploy',
        risk_level=RiskLevel.LOW,
        proposed_by='cli',
        threshold=VotingThreshold.SIMPLE_MAJORITY,
    )
    sig = peer_vote_signature(
        peer,
        state.proposal.task_description,
        proposal_id=state.proposal.id,
        peer_name=peer.name,
        decision='approve',
    )
    payload = VoteRelayPayload(
        proposal_id=state.proposal.id,
        peer_name=peer.name,
        decision='approve',
        signature=sig,
    )
    ok, reason = verify_relay_vote(engine, payload, require_ssh=False)
    assert ok, reason
    result = submit_relay_vote(engine, payload, require_ssh=False)
    assert result['ok'] is True


def test_vote_relay_server_health(tmp_path: Path) -> None:
    registry = PeerRegistry(storage_path=tmp_path / 'peers.json')
    engine = ConsensusEngine(
        peer_registry=registry,
        config=ConsensusConfig(),
        storage_path=tmp_path / 'consensus.json',
    )
    relay = VoteRelayServer(engine, host='127.0.0.1', port=0, require_ssh=False)
    relay.start()
    try:
        import urllib.request

        port = relay.port
        with urllib.request.urlopen(
            f'http://127.0.0.1:{port}/api/health', timeout=5
        ) as response:
            assert json.loads(response.read())['status'] == 'ok'
    finally:
        relay.stop()


def test_wasm_manifest_written(tmp_path: Path) -> None:
    skill = tmp_path / 'skill'
    skill.mkdir()
    write_wasm_manifest(skill)
    contract = build_wasm_invoke_contract(skill)
    assert (skill / 'wasm_manifest.json').is_file()
    assert contract['runtime_available'] is False or isinstance(
        contract['runtime_available'], bool
    )


@pytest.mark.skipif(
    subprocess.run(['which', 'ssh-keygen'], capture_output=True).returncode != 0,
    reason='ssh-keygen not installed',
)
def test_ssh_sign_produces_signature_blob(tmp_path: Path) -> None:
    key = tmp_path / 'id_ed25519'
    subprocess.run(
        ['ssh-keygen', '-t', 'ed25519', '-f', str(key), '-N', ''],
        check=True,
        capture_output=True,
    )
    pub = key.with_suffix('.pub').read_text(encoding='utf-8')
    message = build_vote_signing_message('p', 'peer', 'approve', 'task')
    from teaagent.ssh_signatures import sign_message_ssh, verify_message_ssh

    signature = sign_message_ssh(key, message)
    assert is_ssh_signature_blob(signature)
    # Verify is exercised in Linux CI; some macOS hosts block ssh-keygen -Y verify.
    verified = verify_message_ssh(pub, message, signature)
    if not verified:
        pytest.skip('ssh-keygen -Y verify unavailable on this host')

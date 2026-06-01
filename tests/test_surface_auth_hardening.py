"""Bearer token, mTLS bind rules, and per-tenant control plane authZ."""

from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest

from teaagent.consensus import ConsensusConfig, ConsensusEngine, PeerRegistry
from teaagent.control_plane_api import ControlPlaneServer
from teaagent.control_plane_tenant import ControlPlaneRegistry
from teaagent.surface_auth import (
    SurfaceAuthPolicy,
    authorize_request,
    extract_bearer_token,
    hash_token,
    load_surface_auth_policy,
)
from teaagent.vote_relay import VoteRelayServer, require_relay_bind_auth


def _skip_if_socket_bind_is_blocked() -> None:
    """Skip tests that require a loopback TCP listener when the environment forbids it.

    Some sandboxed execution environments disallow `socket.bind()` entirely, even on
    127.0.0.1 with an ephemeral port. These tests still provide value in normal
    developer/CI environments, so we skip only when binding is blocked.
    """

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(('127.0.0.1', 0))
    except PermissionError as exc:
        pytest.skip(f'sandbox forbids socket.bind() on loopback: {exc}')
    finally:
        sock.close()


def test_extract_bearer_token() -> None:
    assert extract_bearer_token({'Authorization': 'Bearer sekrit'}) == 'sekrit'
    assert extract_bearer_token({'X-TeaAgent-Relay-Token': 'relay'}) == 'relay'


def test_tenant_scoped_policy() -> None:
    policy = SurfaceAuthPolicy.from_single_token('team-a-secret')
    policy.entries[0] = policy.entries[0].__class__(
        token_hash=hash_token('team-a-secret'),
        tenants=frozenset({'team-a'}),
    )
    ok, _ = authorize_request(
        policy, {'Authorization': 'Bearer team-a-secret'}, tenant_id='team-a'
    )
    assert ok
    denied, reason = authorize_request(
        policy, {'Authorization': 'Bearer team-a-secret'}, tenant_id='team-b'
    )
    assert not denied
    assert 'not authorized' in reason


def test_token_file_admin_wildcard(tmp_path: Path) -> None:
    path = tmp_path / 'tokens.json'
    path.write_text(
        json.dumps({'tokens': [{'token': 'admin', 'tenants': ['*']}]}),
        encoding='utf-8',
    )
    policy = SurfaceAuthPolicy.from_token_file(path)
    assert policy.is_admin('admin')
    ok, _ = authorize_request(
        policy, {'Authorization': 'Bearer admin'}, require_admin=True
    )
    assert ok


def test_relay_requires_auth_on_wan_bind() -> None:
    with pytest.raises(ValueError, match='non-loopback'):
        require_relay_bind_auth('0.0.0.0', None)


def test_relay_rejects_missing_token(tmp_path: Path) -> None:
    _skip_if_socket_bind_is_blocked()
    engine = ConsensusEngine(
        peer_registry=PeerRegistry(storage_path=tmp_path / 'peers.json'),
        config=ConsensusConfig(),
        storage_path=tmp_path / 'consensus.json',
    )
    policy = SurfaceAuthPolicy.from_single_token('relay-secret')
    relay = VoteRelayServer(
        engine,
        host='127.0.0.1',
        port=0,
        require_ssh=False,
        auth_policy=policy,
    )
    relay.start()
    try:
        import urllib.error
        import urllib.request

        port = relay.port
        body = json.dumps(
            {
                'proposal_id': 'x',
                'peer_name': 'p',
                'decision': 'approve',
                'signature': 'sig',
            }
        ).encode()
        req = urllib.request.Request(
            f'http://127.0.0.1:{port}/api/v1/votes',
            data=body,
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(req, timeout=5)
        assert exc.value.code == 401
    finally:
        relay.stop()


def test_control_plane_tenant_authz(tmp_path: Path) -> None:
    _skip_if_socket_bind_is_blocked()
    token_path = tmp_path / 'tokens.json'
    token_path.write_text(
        json.dumps(
            {
                'tokens': [
                    {'token': 'scoped', 'tenants': ['team-a']},
                    {'token': 'admin', 'tenants': ['*']},
                ]
            }
        ),
        encoding='utf-8',
    )
    policy = load_surface_auth_policy(api_token_file=token_path)
    registry = ControlPlaneRegistry(default_tenant='default')
    server = ControlPlaneServer(
        host='127.0.0.1',
        port=0,
        tenant_registry=registry,
        auth_policy=policy,
    )
    server.start()
    try:
        import urllib.error
        import urllib.request

        url = f'{server.base_url}/api/tenants'
        admin_req = urllib.request.Request(
            url, headers={'Authorization': 'Bearer admin'}
        )
        with urllib.request.urlopen(admin_req, timeout=5) as resp:
            assert resp.status == 200

        scoped_req = urllib.request.Request(
            url, headers={'Authorization': 'Bearer scoped'}
        )
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(scoped_req, timeout=5)
        assert exc.value.code == 401
    finally:
        server.stop()

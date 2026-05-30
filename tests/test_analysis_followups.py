"""Tests for analysis-report follow-ups (rate limit, SSH policy, OAuth map, paths)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from teaagent.gateway_oauth import OAuthTenantMap
from teaagent.http_rate_limit import TokenRateLimiter
from teaagent.approval_manager import _SSH_VERIFICATION_IMPLEMENTED


def test_token_rate_limiter_blocks_burst() -> None:
    limiter = TokenRateLimiter(max_calls=2, window_seconds=60.0)
    assert limiter.allow('tok')[0]
    assert limiter.allow('tok')[0]
    ok, reason = limiter.allow('tok')
    assert not ok
    assert 'rate limit' in reason


def test_oauth_tenant_map_from_file(tmp_path: Path) -> None:
    path = tmp_path / 'map.json'
    path.write_text(
        json.dumps({'subject_tenants': {'alice@corp.com': 'team-a'}}),
        encoding='utf-8',
    )
    mapping = OAuthTenantMap.from_file(path)
    assert mapping.tenant_for_subject('alice@corp.com') == 'team-a'
    snippet = mapping.to_nginx_map_snippet()
    assert 'alice@corp.com' in snippet
    assert 'team-a' in snippet


def test_control_plane_tenant_path_route(tmp_path: Path) -> None:
    token_path = tmp_path / 'tokens.json'
    token_path.write_text(
        json.dumps({'tokens': [{'token': 'scoped', 'tenants': ['team-a']}]}),
        encoding='utf-8',
    )
    from teaagent.control_plane_api import ControlPlaneServer
    from teaagent.control_plane_tenant import ControlPlaneRegistry
    from teaagent.surface_auth import load_surface_auth_policy

    policy = load_surface_auth_policy(api_token_file=token_path)
    server = ControlPlaneServer(
        host='127.0.0.1',
        port=0,
        tenant_registry=ControlPlaneRegistry(),
        auth_policy=policy,
        max_sse_events=1,
    )
    server.start()
    try:
        import urllib.request

        req = urllib.request.Request(
            f'{server.base_url}/api/tenants/team-a/workflow/stream',
            headers={'Authorization': 'Bearer scoped'},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = resp.read(500).decode('utf-8', errors='replace')
        assert resp.status == 200
        assert 'workflow' in body or 'event:' in body
    finally:
        server.stop()


def test_relay_rate_limit_returns_429(tmp_path: Path) -> None:
    from teaagent.consensus import ConsensusConfig, ConsensusEngine, PeerRegistry
    from teaagent.surface_auth import SurfaceAuthPolicy
    from teaagent.vote_relay import VoteRelayServer

    engine = ConsensusEngine(
        peer_registry=PeerRegistry(storage_path=tmp_path / 'peers.json'),
        config=ConsensusConfig(),
        storage_path=tmp_path / 'consensus.json',
    )
    policy = SurfaceAuthPolicy.from_single_token('limit-token')
    limiter = TokenRateLimiter(max_calls=2, window_seconds=60.0)
    relay = VoteRelayServer(
        engine,
        host='127.0.0.1',
        port=0,
        require_ssh=False,
        auth_policy=policy,
        rate_limiter=limiter,
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
                'signature': 's',
            }
        ).encode()
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer limit-token',
        }
        url = f'http://127.0.0.1:{port}/api/v1/votes'
        req = urllib.request.Request(url, data=body, headers=headers, method='POST')
        for _ in range(2):
            with pytest.raises(urllib.error.HTTPError) as first:
                urllib.request.urlopen(req, timeout=5)
            assert first.value.code == 400
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(req, timeout=5)
        assert exc.value.code == 429
    finally:
        relay.stop()


def test_policy_ssh_flag_enabled() -> None:
    assert _SSH_VERIFICATION_IMPLEMENTED is True

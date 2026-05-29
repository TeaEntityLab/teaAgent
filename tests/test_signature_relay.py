"""Tests for HTTP signature relay (P4.3b WAN multi-sig)."""

from __future__ import annotations

import asyncio
import json
import tempfile
import time
import urllib.request
from dataclasses import asdict

from teaagent.federated_sync import (
    ApprovalRequestMessage,
    FederatedGraphSync,
)
from teaagent.signature_relay import (
    ApprovalRequestPayload,
    ApprovalSignaturePayload,
    SignatureRelayClient,
    SignatureRelayServer,
)
from teaagent.surface_auth import SurfaceAuthPolicy


def _http_json(
    url: str,
    *,
    method: str = 'GET',
    body: dict | None = None,
    token: str | None = None,
) -> dict:
    data = None if body is None else json.dumps(body).encode('utf-8')
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.loads(response.read().decode('utf-8'))


def test_signature_relay_store_roundtrip():
    policy = SurfaceAuthPolicy.from_single_token('relay-secret')
    relay = SignatureRelayServer(
        host='127.0.0.1',
        port=0,
        auth_policy=policy,
    )
    relay.start()
    try:
        base = relay.base_url
        token = 'relay-secret'
        req = ApprovalRequestPayload(
            request_id='req-1',
            tool_name='workspace_write_file',
            call_id='call-1',
            arguments={'path': 'a.txt'},
            request_hash='abc',
            timestamp=time.time(),
            requester_agent_id='agent-a',
            required_approvals=2,
            timeout_seconds=60,
            signature_submit_url=f'{base}/api/v1/approval-signatures',
        )
        posted = _http_json(
            f'{base}/api/v1/approval-requests',
            method='POST',
            body=asdict(req),
            token=token,
        )
        assert posted['ok'] is True

        sig = ApprovalSignaturePayload(
            request_id='req-1',
            peer_id='peer-b',
            signature='ssh-sig-blob',
            timestamp=time.time(),
        )
        submitted = _http_json(
            f'{base}/api/v1/approval-signatures',
            method='POST',
            body=asdict(sig),
            token=token,
        )
        assert submitted['ok'] is True

        listed = _http_json(
            f'{base}/api/v1/approval-signatures?request_id=req-1',
            token=token,
        )
        assert listed['ok'] is True
        assert len(listed['signatures']) == 1
        assert listed['signatures'][0]['peer_id'] == 'peer-b'
    finally:
        relay.stop()


def test_signature_relay_requires_auth_on_wan_bind():
    import pytest

    with pytest.raises(ValueError, match='non-loopback'):
        SignatureRelayServer(host='0.0.0.0', port=8791, auth_policy=None)


def test_federated_http_broadcast_and_collect():
    policy = SurfaceAuthPolicy.from_single_token('test-token')
    collector = SignatureRelayServer(host='127.0.0.1', port=0, auth_policy=policy)
    peer = SignatureRelayServer(host='127.0.0.1', port=0, auth_policy=policy)
    collector.start()
    peer.start()
    try:
        token = 'test-token'
        client = SignatureRelayClient(api_token=token)
        collect_url = collector.base_url

        with tempfile.TemporaryDirectory() as tmpdir:
            sync = FederatedGraphSync(tmpdir, 'agent-requester')
            message = ApprovalRequestMessage(
                request_id='req-http',
                tool_name='workspace_write_file',
                call_id='c1',
                arguments={},
                request_hash='hash',
                timestamp=time.time(),
                requester_agent_id='agent-requester',
                required_approvals=1,
                timeout_seconds=5,
                signature_submit_url=(f'{collect_url}/api/v1/approval-signatures'),
            )
            results = sync.broadcast_approval_request(
                message,
                ['peer-1'],
                peer_relay_urls={'peer-1': peer.base_url},
                relay_api_token=token,
            )
            assert results['peer-1'] is True

            client.post_signature(
                f'{collect_url}/api/v1/approval-signatures',
                {
                    'request_id': 'req-http',
                    'peer_id': 'peer-1',
                    'signature': 'sig-from-peer',
                    'timestamp': time.time(),
                },
            )

            signatures = asyncio.run(
                sync.collect_approval_signatures(
                    'req-http',
                    timeout_seconds=2,
                    required_approvals=1,
                    relay_base_url=collect_url,
                    relay_api_token=token,
                )
            )
            assert len(signatures) == 1
            assert signatures[0].peer_id == 'peer-1'
            assert signatures[0].signature == 'sig-from-peer'
    finally:
        collector.stop()
        peer.stop()


def test_signature_relay_rate_limit():
    from teaagent.http_rate_limit import TokenRateLimiter

    policy = SurfaceAuthPolicy.from_single_token('tok')
    relay = SignatureRelayServer(
        host='127.0.0.1',
        port=0,
        auth_policy=policy,
        rate_limiter=TokenRateLimiter(max_calls=1, window_seconds=60.0),
    )
    relay.start()
    try:
        base = relay.base_url
        body = {
            'request_id': 'r1',
            'peer_id': 'p1',
            'signature': 's1',
            'timestamp': time.time(),
        }
        first = _http_json(
            f'{base}/api/v1/approval-signatures',
            method='POST',
            body=body,
            token='tok',
        )
        assert first['ok'] is True
        import urllib.error

        req = urllib.request.Request(
            f'{base}/api/v1/approval-signatures',
            data=json.dumps(body).encode('utf-8'),
            headers={
                'Content-Type': 'application/json',
                'Authorization': 'Bearer tok',
            },
            method='POST',
        )
        try:
            urllib.request.urlopen(req, timeout=5)
            raised = False
        except urllib.error.HTTPError as exc:
            raised = exc.code == 429
        assert raised
    finally:
        relay.stop()

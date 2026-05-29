from __future__ import annotations

import http.client
import json
import threading
import time
import urllib.request

from teaagent.control_plane_api import (
    ControlPlaneServer,
    ControlPlaneState,
    format_sse_event,
)
from teaagent.jit_approval_server import (
    ApprovalRequestRecord,
    ApprovalStatus,
    JITApprovalServer,
)
from teaagent.tool_permissions import (
    PermissionRequest,
    ToolPermission,
    ToolPermissionManager,
    ToolSafetyLevel,
)


def _pending_record(
    jit: JITApprovalServer, request_id: str = 'test-req'
) -> ApprovalRequestRecord:
    request = PermissionRequest(
        tool_name='workspace_write_file',
        agent_name='agent-a',
        reason='write config',
    )
    record = ApprovalRequestRecord(
        request_id=request_id,
        request=request,
        status=ApprovalStatus.PENDING,
        created_at=time.time(),
        timeout_seconds=60,
    )
    jit._requests[request_id] = record
    return record


def test_format_sse_event() -> None:
    frame = format_sse_event('workflow_update', {'state': 'running'})
    assert 'event: workflow_update' in frame
    assert 'data: {"state":"running"}' in frame


def test_control_plane_serve_blocking_binds_port() -> None:
    state = ControlPlaneState()
    server = ControlPlaneServer(host='127.0.0.1', port=0, state=state)
    thread = threading.Thread(target=lambda: server.serve_blocking(announce=False))
    thread.start()
    try:
        time.sleep(0.1)
        with urllib.request.urlopen(f'{server.base_url}/') as resp:
            assert resp.status == 200
    finally:
        server.stop()
        thread.join(timeout=3)


def test_control_plane_serves_dashboard_and_sse() -> None:
    state = ControlPlaneState()
    state.set_workflow({'state': 'in_progress', 'current_step': 2})
    state.set_focus({'frames': [{'topic': 'auth', 'state': 'kept'}]})
    state.publish_jit_diff(
        'req-1',
        'agent-a',
        'old prompt',
        'new prompt',
        '--- old\n+++ new\n',
    )

    manager = ToolPermissionManager()
    jit = JITApprovalServer(manager, timeout_seconds=60)
    record = _pending_record(jit)

    server = ControlPlaneServer(
        state=state,
        jit_server=jit,
        max_sse_events=1,
        sse_interval_seconds=0.01,
    )
    server.start()
    try:
        with urllib.request.urlopen(f'{server.base_url}/') as resp:
            html = resp.read().decode('utf-8')
        assert 'TeaAgent Control Plane' in html

        conn = http.client.HTTPConnection(server.host, server.port, timeout=5)
        conn.request('GET', '/api/workflow/stream')
        workflow_resp = conn.getresponse()
        workflow_chunk = workflow_resp.read(4096).decode('utf-8')
        assert 'event: workflow_update' in workflow_chunk
        assert 'in_progress' in workflow_chunk
        conn.close()

        approve_body = json.dumps({'request_id': record.request_id}).encode('utf-8')
        approve_req = urllib.request.Request(
            f'{server.base_url}/api/jit/approve',
            data=approve_body,
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        with urllib.request.urlopen(approve_req) as resp:
            payload = json.loads(resp.read().decode('utf-8'))
        assert payload['status'] == ApprovalStatus.APPROVED.value
        updated = jit.get_request_status(record.request_id)
        assert updated is not None
        assert updated.status == ApprovalStatus.APPROVED
    finally:
        server.stop()


def test_jit_approve_invalid_json_returns_400() -> None:
    state = ControlPlaneState()
    manager = ToolPermissionManager(approval_callback=lambda req: True)
    jit = JITApprovalServer(manager, timeout_seconds=60)
    server = ControlPlaneServer(state=state, jit_server=jit)
    server.start()
    try:
        conn = http.client.HTTPConnection(server.host, server.port, timeout=5)
        conn.request(
            'POST',
            '/api/jit/approve',
            body=b'{not-json',
            headers={'Content-Type': 'application/json'},
        )
        resp = conn.getresponse()
        assert resp.status == 400
        payload = json.loads(resp.read().decode('utf-8'))
        assert 'invalid JSON' in payload['error']
        conn.close()
    finally:
        server.stop()


def test_jit_approve_with_approval_callback_grants_tool_access() -> None:
    """Mirror CLI wiring: dashboard approve must grant JIT tool access."""
    manager = ToolPermissionManager(approval_callback=lambda req: True)
    manager.register_tool_permission(
        ToolPermission(
            name='workspace_write_file',
            safety_level=ToolSafetyLevel.DESTRUCTIVE,
            requires_approval=True,
        )
    )
    manager.grant_agent_tool_access(
        'agent-a', ('workspace_write_file',), allow_destructive=True
    )
    jit = JITApprovalServer(manager, timeout_seconds=60)
    record = _pending_record(jit)

    denied_before, _ = manager.check_tool_access('agent-a', 'workspace_write_file')
    assert denied_before is False

    state = ControlPlaneState()
    server = ControlPlaneServer(state=state, jit_server=jit)
    server.start()
    try:
        approve_body = json.dumps({'request_id': record.request_id}).encode('utf-8')
        approve_req = urllib.request.Request(
            f'{server.base_url}/api/jit/approve',
            data=approve_body,
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        with urllib.request.urlopen(approve_req) as resp:
            assert json.loads(resp.read().decode('utf-8'))['status'] == 'approved'
    finally:
        server.stop()

    allowed_after, _ = manager.check_tool_access('agent-a', 'workspace_write_file')
    assert allowed_after is True

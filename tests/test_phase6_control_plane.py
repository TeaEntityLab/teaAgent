from __future__ import annotations

import http.client
import json
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
from teaagent.tool_permissions import PermissionRequest, ToolPermissionManager


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

from __future__ import annotations

import asyncio
from unittest.mock import patch

from teaagent.jit_approval_server import ApprovalStatus, JITApprovalServer
from teaagent.tool_permissions import ToolPermissionManager


class _FakeWriter:
    def __init__(self) -> None:
        self.buffer = b''

    def write(self, data: bytes) -> None:
        self.buffer += data

    async def drain(self) -> None:
        return None


def test_jit_wait_times_out_with_short_deadline() -> None:
    manager = ToolPermissionManager()
    server = JITApprovalServer(manager, timeout_seconds=1)

    with (
        patch('teaagent.jit_approval_server.time.sleep', return_value=None),
        patch(
            'teaagent.jit_approval_server.time.time',
            side_effect=[1000.0, 1000.1, 1001.2, 1001.3],
        ),
    ):
        record = server.request_approval(
            'agent-a', 'workspace_write_file', 'needs write'
        )

    assert record.status == ApprovalStatus.TIMEOUT


def test_send_sse_event_format() -> None:
    writer = _FakeWriter()
    manager = ToolPermissionManager()
    server = JITApprovalServer(manager)

    asyncio.run(
        server._send_sse_event(writer, 'approval_request', {'request_id': 'r1'})
    )
    text = writer.buffer.decode('utf-8')
    assert 'event: approval_request' in text
    assert 'data: {"request_id": "r1"}' in text

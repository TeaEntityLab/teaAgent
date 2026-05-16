from __future__ import annotations

import io
import json

from teaagent.code_analysis._client import StdioLSPClient
from teaagent.code_analysis._types import LSPServerConfig


class _FakeProc:
    def __init__(self, responses: list[dict]):
        self.stdin = io.BytesIO()
        self.stdout = io.BytesIO(_encode_messages(responses))
        self.stderr = io.BytesIO()
        self._terminated = False

    def poll(self):
        return None if not self._terminated else 0

    def terminate(self):
        self._terminated = True


class _WritableBytesIO(io.BytesIO):
    def flush(self):
        return None


def _encode_messages(messages: list[dict]) -> bytes:
    parts: list[bytes] = []
    for msg in messages:
        body = json.dumps(msg).encode('utf-8')
        parts.append(f'Content-Length: {len(body)}\r\n\r\n'.encode('ascii') + body)
    return b''.join(parts)


def test_initialize_and_definition_roundtrip():
    proc = _FakeProc(
        [
            {'jsonrpc': '2.0', 'id': 1, 'result': {'capabilities': {}}},
            {
                'jsonrpc': '2.0',
                'id': 2,
                'result': [
                    {
                        'uri': 'file:///tmp/demo.py',
                        'range': {'start': {'line': 4, 'character': 2}},
                    }
                ],
            },
            {'jsonrpc': '2.0', 'id': 3, 'result': None},
        ]
    )
    proc.stdin = _WritableBytesIO()

    client = StdioLSPClient(
        LSPServerConfig(language='python', command=['fake-lsp']),
        popen_factory=lambda *args, **kwargs: proc,
    )

    client.initialize('file:///tmp')
    refs = client.goto_definition('/tmp/demo.py', 5, 3)
    client.shutdown()

    assert len(refs) == 1
    assert refs[0].file_path == '/tmp/demo.py'
    assert refs[0].line == 5
    assert refs[0].column == 3

    written = proc.stdin.getvalue().decode('utf-8', errors='ignore')
    assert '"method": "initialize"' in written
    assert '"method": "textDocument/definition"' in written
    assert '"method": "shutdown"' in written


def test_diagnostics_shape():
    proc = _FakeProc(
        [
            {'jsonrpc': '2.0', 'id': 1, 'result': {'capabilities': {}}},
            {
                'jsonrpc': '2.0',
                'id': 2,
                'result': {'items': [{'message': 'x', 'severity': 1}]},
            },
        ]
    )
    proc.stdin = _WritableBytesIO()
    client = StdioLSPClient(
        LSPServerConfig(language='python', command=['fake-lsp']),
        popen_factory=lambda *args, **kwargs: proc,
    )
    client.initialize('file:///tmp')
    out = client.document_diagnostics('/tmp/demo.py')
    assert out == [{'message': 'x', 'severity': 1}]

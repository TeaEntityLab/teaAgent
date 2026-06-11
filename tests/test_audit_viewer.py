from __future__ import annotations

import json
import tempfile
import threading
from pathlib import Path
from urllib.request import urlopen

import pytest

from teaagent.audit_viewer import make_audit_server
from teaagent.run_store import RunStore
from teaagent.types import AuditLogger
from test_support import skip_if_socket_bind_is_blocked


def _make_store_with_run(tmp: str) -> RunStore:
    store = RunStore(tmp)
    path = Path(tmp) / '.teaagent' / 'runs' / 'test-run-1.jsonl'
    logger = AuditLogger(path=path)
    logger.record('run_started', 'test-run-1', task='hello world task')
    logger.record(
        'run_completed', 'test-run-1', answer='done', metadata={}, cost_cents=0.0
    )
    return store


@pytest.fixture
def audit_server():
    """Fixture to set up and tear down audit server for HTTP tests."""
    skip_if_socket_bind_is_blocked()
    tmp = tempfile.mkdtemp()
    store = _make_store_with_run(tmp)
    server = make_audit_server(store, host='127.0.0.1', port=0)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    yield server, port, tmp

    server.shutdown()
    # Verify cleanup
    import os
    import shutil

    assert os.path.exists(tmp), (
        f'Temporary directory {tmp} should still exist before cleanup'
    )
    shutil.rmtree(tmp)
    assert not os.path.exists(tmp), f'Temporary directory {tmp} was not cleaned up'


def _get(port, path: str) -> tuple[int, str]:
    url = f'http://127.0.0.1:{port}{path}'
    with urlopen(url) as resp:
        return resp.status, resp.read().decode('utf-8')


def test_root_returns_html(audit_server) -> None:
    server, port, tmp = audit_server
    status, body = _get(port, '/')
    assert status == 200
    assert '<html' in body.lower()
    assert 'TeaAgent Audit Viewer' in body


def test_root_lists_run(audit_server) -> None:
    server, port, tmp = audit_server
    status, body = _get(port, '/')
    assert status == 200
    assert 'test-run-1' in body


def test_run_page_shows_events(audit_server) -> None:
    server, port, tmp = audit_server
    status, body = _get(port, '/run/test-run-1')
    assert status == 200
    assert 'run_started' in body
    assert 'run_completed' in body


def test_api_runs_returns_json_list(audit_server) -> None:
    server, port, tmp = audit_server
    status, body = _get(port, '/api/runs')
    assert status == 200
    data = json.loads(body)
    assert isinstance(data, list)
    assert any(r['run_id'] == 'test-run-1' for r in data)


def test_api_runs_run_id_returns_json_events(audit_server) -> None:
    server, port, tmp = audit_server
    status, body = _get(port, '/api/runs/test-run-1')
    assert status == 200
    events = json.loads(body)
    assert isinstance(events, list)
    event_types = [e['event_type'] for e in events]
    assert 'run_started' in event_types


def test_unknown_path_returns_404(audit_server) -> None:
    server, port, tmp = audit_server
    from urllib.error import HTTPError

    with pytest.raises(HTTPError) as ctx:
        urlopen(f'http://127.0.0.1:{port}/no-such-path')
    assert ctx.value.code == 404


def test_unknown_run_id_returns_404(audit_server) -> None:
    server, port, tmp = audit_server
    from urllib.error import HTTPError

    with pytest.raises(HTTPError) as ctx:
        urlopen(f'http://127.0.0.1:{port}/run/no-such-run')
    assert ctx.value.code == 404


def test_run_page_html_escaped() -> None:
    from teaagent.audit_viewer import _render_run_page

    body = _render_run_page(
        'run-1', [{'event_type': '<script>', 'created_at': '', 'payload': {}}]
    )
    assert '<script>' not in body
    assert '&lt;script&gt;' in body


def test_runs_page_html_escaped() -> None:
    from teaagent.audit_viewer import _render_runs_page

    body = _render_runs_page(
        [{'run_id': 'r1', 'task': '<b>bad</b>', 'status': 'ok', 'created_at': ''}]
    )
    assert '<b>bad</b>' not in body


def test_audit_serve_requires_root_and_runs_server() -> None:
    from teaagent.cli import main

    with tempfile.TemporaryDirectory() as tmp:
        # Patch serve_audit_viewer to return immediately
        from unittest.mock import patch

        with patch('teaagent.audit_viewer.serve_audit_viewer') as mock_serve:
            mock_serve.return_value = None
            exit_code = main(['audit', 'serve', '--root', tmp, '--port', '9099'])
    assert exit_code == 0
    mock_serve.assert_called_once()

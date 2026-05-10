from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import urlopen

from teaagent.audit import AuditLogger
from teaagent.audit_viewer import make_audit_server
from teaagent.run_store import RunStore


def _make_store_with_run(tmp: str) -> RunStore:
    store = RunStore(tmp)
    path = Path(tmp) / '.teaagent' / 'runs' / 'test-run-1.jsonl'
    logger = AuditLogger(path=path)
    logger.record('run_started', 'test-run-1', task='hello world task')
    logger.record(
        'run_completed', 'test-run-1', answer='done', metadata={}, cost_cents=0.0
    )
    return store


class AuditViewerHTTPTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp()
        self._store = _make_store_with_run(self._tmp)
        self._server = make_audit_server(self._store, host='127.0.0.1', port=0)
        self._port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def tearDown(self) -> None:
        self._server.shutdown()

    def _get(self, path: str) -> tuple[int, str]:
        url = f'http://127.0.0.1:{self._port}{path}'
        with urlopen(url) as resp:
            return resp.status, resp.read().decode('utf-8')

    def test_root_returns_html(self) -> None:
        status, body = self._get('/')
        self.assertEqual(status, 200)
        self.assertIn('<html', body.lower())
        self.assertIn('TeaAgent Audit Viewer', body)

    def test_root_lists_run(self) -> None:
        status, body = self._get('/')
        self.assertEqual(status, 200)
        self.assertIn('test-run-1', body)

    def test_run_page_shows_events(self) -> None:
        status, body = self._get('/run/test-run-1')
        self.assertEqual(status, 200)
        self.assertIn('run_started', body)
        self.assertIn('run_completed', body)

    def test_api_runs_returns_json_list(self) -> None:
        status, body = self._get('/api/runs')
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertIsInstance(data, list)
        self.assertTrue(any(r['run_id'] == 'test-run-1' for r in data))

    def test_api_runs_run_id_returns_json_events(self) -> None:
        status, body = self._get('/api/runs/test-run-1')
        self.assertEqual(status, 200)
        events = json.loads(body)
        self.assertIsInstance(events, list)
        event_types = [e['event_type'] for e in events]
        self.assertIn('run_started', event_types)

    def test_unknown_path_returns_404(self) -> None:
        from urllib.error import HTTPError

        with self.assertRaises(HTTPError) as ctx:
            urlopen(f'http://127.0.0.1:{self._port}/no-such-path')
        self.assertEqual(ctx.exception.code, 404)

    def test_unknown_run_id_returns_404(self) -> None:
        from urllib.error import HTTPError

        with self.assertRaises(HTTPError) as ctx:
            urlopen(f'http://127.0.0.1:{self._port}/run/no-such-run')
        self.assertEqual(ctx.exception.code, 404)


class AuditViewerHTMLTests(unittest.TestCase):
    def test_run_page_html_escaped(self) -> None:
        from teaagent.audit_viewer import _render_run_page

        body = _render_run_page(
            'run-1', [{'event_type': '<script>', 'created_at': '', 'payload': {}}]
        )
        self.assertNotIn('<script>', body)
        self.assertIn('&lt;script&gt;', body)

    def test_runs_page_html_escaped(self) -> None:
        from teaagent.audit_viewer import _render_runs_page

        body = _render_runs_page(
            [{'run_id': 'r1', 'task': '<b>bad</b>', 'status': 'ok', 'created_at': ''}]
        )
        self.assertNotIn('<b>bad</b>', body)


class AuditServeCliTests(unittest.TestCase):
    def test_audit_serve_requires_root_and_runs_server(self) -> None:
        from teaagent.cli import main

        with tempfile.TemporaryDirectory() as tmp:
            # Patch serve_audit_viewer to return immediately
            from unittest.mock import patch

            with patch('teaagent.audit_viewer.serve_audit_viewer') as mock_serve:
                mock_serve.return_value = None
                exit_code = main(['audit', 'serve', '--root', tmp, '--port', '9099'])
        self.assertEqual(exit_code, 0)
        mock_serve.assert_called_once()


if __name__ == '__main__':
    unittest.main()

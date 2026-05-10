from __future__ import annotations

import html
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import urlparse

_CSS = """
body{font-family:system-ui,sans-serif;margin:2rem;background:#fafafa;color:#222}
h1{color:#1a1a2e}
a{color:#0066cc}
table{border-collapse:collapse;width:100%;background:#fff;box-shadow:0 1px 4px rgba(0,0,0,.08)}
th{background:#1a1a2e;color:#fff;padding:.6rem 1rem;text-align:left}
td{padding:.5rem 1rem;border-bottom:1px solid #e2e2e2}
tr:hover td{background:#f0f4ff}
.status-completed{color:#2e7d32;font-weight:600}
.status-failed{color:#c62828;font-weight:600}
.status-running{color:#1565c0}
.status-pending{color:#6a1e8a}
pre{background:#f4f4f4;padding:1rem;border-radius:4px;overflow-x:auto;font-size:.85em}
.back{margin-bottom:1rem;display:block}
"""

_HTML_HEADER = """<!DOCTYPE html><html><head>
<meta charset="utf-8">
<title>{title}</title>
<style>{css}</style>
</head><body>"""

_HTML_FOOTER = '</body></html>'


def _status_class(status: str) -> str:
    s = status.split(':')[0]
    return f'status-{s}'


def _render_runs_page(summaries: list[Any]) -> str:
    rows = ''
    for s in summaries:
        status = s.get('status', 'unknown')
        task = html.escape(str(s.get('task', ''))[:80])
        run_id = html.escape(str(s.get('run_id', '')))
        created = html.escape(str(s.get('created_at', ''))[:19])
        css = _status_class(status)
        rows += (
            f'<tr><td><a href="/run/{run_id}">{run_id[:16]}…</a></td>'
            f'<td>{task}</td>'
            f'<td class="{css}">{html.escape(status)}</td>'
            f'<td>{created}</td></tr>\n'
        )
    return (
        _HTML_HEADER.format(title='TeaAgent Audit Viewer', css=_CSS)
        + '<h1>TeaAgent Audit Viewer</h1>'
        + '<table><thead><tr><th>Run ID</th><th>Task</th><th>Status</th><th>Created</th></tr></thead>'
        + f'<tbody>{rows}</tbody></table>'
        + _HTML_FOOTER
    )


def _render_run_page(run_id: str, events: list[dict[str, Any]]) -> str:
    rows = ''
    for event in events:
        etype = html.escape(str(event.get('event_type', '')))
        created = html.escape(str(event.get('created_at', ''))[:19])
        payload = event.get('payload') or {}
        payload_str = html.escape(json.dumps(payload, ensure_ascii=False, indent=2))
        rows += (
            f'<tr><td>{created}</td><td><strong>{etype}</strong></td>'
            f'<td><pre>{payload_str}</pre></td></tr>\n'
        )
    return (
        _HTML_HEADER.format(title=f'Run {run_id[:16]}…', css=_CSS)
        + '<a class="back" href="/">← All runs</a>'
        + f'<h1>Run <code>{html.escape(run_id)}</code></h1>'
        + '<table><thead><tr><th>Time</th><th>Event</th><th>Payload</th></tr></thead>'
        + f'<tbody>{rows}</tbody></table>'
        + _HTML_FOOTER
    )


class _AuditHandler(BaseHTTPRequestHandler):
    run_store: Any = None

    def log_message(self, fmt: str, *args: Any) -> None:  # silence default logging
        pass

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip('/')

        if path == '' or path == '/':
            self._serve_runs_html()
        elif path.startswith('/run/'):
            run_id = path[len('/run/') :]
            self._serve_run_html(run_id)
        elif path == '/api/runs':
            self._serve_json_runs()
        elif path.startswith('/api/runs/'):
            run_id = path[len('/api/runs/') :]
            self._serve_json_run(run_id)
        else:
            self._not_found()

    def _serve_runs_html(self) -> None:
        summaries = [s.to_dict() for s in self.run_store.list_runs(limit=200)]
        body = _render_runs_page(summaries).encode('utf-8')
        self._respond(200, 'text/html; charset=utf-8', body)

    def _serve_run_html(self, run_id: str) -> None:
        try:
            events = self.run_store.show_run(run_id)
        except FileNotFoundError:
            self._not_found()
            return
        body = _render_run_page(run_id, events).encode('utf-8')
        self._respond(200, 'text/html; charset=utf-8', body)

    def _serve_json_runs(self) -> None:
        summaries = [s.to_dict() for s in self.run_store.list_runs(limit=200)]
        body = json.dumps(summaries, ensure_ascii=False).encode('utf-8')
        self._respond(200, 'application/json', body)

    def _serve_json_run(self, run_id: str) -> None:
        try:
            events = self.run_store.show_run(run_id)
        except FileNotFoundError:
            self._respond(404, 'application/json', b'{"error":"not found"}')
            return
        body = json.dumps(events, ensure_ascii=False).encode('utf-8')
        self._respond(200, 'application/json', body)

    def _not_found(self) -> None:
        self._respond(404, 'text/plain', b'Not found')

    def _respond(self, code: int, content_type: str, body: bytes) -> None:
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def make_audit_server(
    run_store: Any, *, host: str = '127.0.0.1', port: int = 8080
) -> HTTPServer:
    handler = type('_Handler', (_AuditHandler,), {'run_store': run_store})
    return HTTPServer((host, port), handler)


def serve_audit_viewer(
    run_store: Any,
    *,
    host: str = '127.0.0.1',
    port: int = 8080,
    print_fn: Any = print,
) -> None:
    server = make_audit_server(run_store, host=host, port=port)
    print_fn(f'TeaAgent audit viewer running at http://{host}:{port}')
    print_fn('Press Ctrl+C to stop.')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

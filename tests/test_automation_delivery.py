from __future__ import annotations

import json
import urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread

import pytest

from teaagent.automation_delivery import (
    deliver_automation_tick,
    resolve_automation_webhook_secret,
    resolve_automation_webhook_url,
    sign_webhook_body,
)
from teaagent.automation_ticket import validate_automation_spec
from teaagent.automations import AutomationStore


class _CaptureHandler(BaseHTTPRequestHandler):
    captured: list[dict[str, object]] = []
    signatures: list[str | None] = []

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get('Content-Length', '0'))
        body = self.rfile.read(length)
        _CaptureHandler.captured.append(json.loads(body.decode('utf-8')))
        _CaptureHandler.signatures.append(self.headers.get('X-TeaAgent-Signature-256'))
        self.send_response(204)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        return


def _start_server() -> tuple[HTTPServer, str]:
    server = HTTPServer(('127.0.0.1', 0), _CaptureHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    return server, f'http://{host}:{port}/hook'


def test_resolve_automation_webhook_url_from_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv('TEAAGENT_AUTOMATION_WEBHOOK_URL', 'https://env.example/hook')
    assert resolve_automation_webhook_url(tmp_path) == 'https://env.example/hook'


def test_resolve_automation_webhook_url_from_config(tmp_path: Path) -> None:
    config = tmp_path / '.teaagent' / 'config.toml'
    config.parent.mkdir(parents=True)
    config.write_text(
        'automation_webhook_url = "https://example.com/hook"\n', encoding='utf-8'
    )
    assert resolve_automation_webhook_url(tmp_path) == 'https://example.com/hook'


def test_deliver_skips_non_webhook_delivery(tmp_path: Path) -> None:
    spec = AutomationStore(tmp_path).draft(
        name='bg',
        task='Summarize repo changes with explicit output path notes.txt',
        schedule='every 30m',
        provider=None,
        model=None,
        permission_mode='read-only',
        context_profile='lean',
        max_iterations=3,
        max_tool_calls=3,
        delivery='background_log',
    )
    assert deliver_automation_tick(tmp_path, spec, status='ok') is False


def test_resolve_webhook_secret_from_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv('TEAAGENT_AUTOMATION_WEBHOOK_SECRET', 'from-env')
    assert resolve_automation_webhook_secret(tmp_path) == 'from-env'


def test_dry_run_errors_when_webhook_delivery_without_url(tmp_path: Path) -> None:
    spec = AutomationStore(tmp_path).draft(
        name='hook-job',
        task='Summarize repo changes with explicit output path notes.txt',
        schedule='every 30m',
        provider=None,
        model=None,
        permission_mode='read-only',
        context_profile='lean',
        max_iterations=3,
        max_tool_calls=3,
        delivery='webhook',
    )
    report = validate_automation_spec(spec, root=tmp_path)
    assert any('automation_webhook_url' in err for err in report.errors)


def test_sign_webhook_body_matches_audit_sink_convention() -> None:
    body = b'{"event":"automation_tick"}'
    assert sign_webhook_body('secret', body) == sign_webhook_body('secret', body)
    assert sign_webhook_body('secret', body).startswith('sha256=')


def test_deliver_automation_tick_posts_json(tmp_path: Path) -> None:
    _CaptureHandler.captured.clear()
    _CaptureHandler.signatures.clear()
    server, url = _start_server()
    try:
        config = tmp_path / '.teaagent' / 'config.toml'
        config.parent.mkdir(parents=True)
        config.write_text(
            f'automation_webhook_url = "{url}"\n'
            'automation_webhook_secret = "test-secret"\n',
            encoding='utf-8',
        )
        assert resolve_automation_webhook_secret(tmp_path) == 'test-secret'
        spec = AutomationStore(tmp_path).draft(
            name='hook-job',
            task='Summarize repo changes with explicit output path notes.txt',
            schedule='every 30m',
            provider=None,
            model=None,
            permission_mode='read-only',
            context_profile='lean',
            max_iterations=3,
            max_tool_calls=3,
            delivery='webhook',
        )
        delivered = deliver_automation_tick(
            tmp_path, spec, status='collector_ok', collector={'summary': 'ok'}
        )
        assert delivered is True
        assert _CaptureHandler.captured[-1]['status'] == 'collector_ok'
        assert _CaptureHandler.captured[-1]['event'] == 'automation_tick'
        sig = _CaptureHandler.signatures[-1]
        assert sig is not None
        assert sig.startswith('sha256=')
        assert len(sig) > len('sha256=')
    finally:
        server.shutdown()


def test_deliver_webhook_returns_false_without_url(tmp_path: Path) -> None:
    spec = AutomationStore(tmp_path).draft(
        name='hook-job',
        task='Summarize repo changes with explicit output path notes.txt',
        schedule='every 30m',
        provider=None,
        model=None,
        permission_mode='read-only',
        context_profile='lean',
        max_iterations=3,
        max_tool_calls=3,
        delivery='webhook',
    )
    assert deliver_automation_tick(tmp_path, spec, status='ok') is False


def test_deliver_webhook_raises_on_network_error(tmp_path: Path) -> None:
    config = tmp_path / '.teaagent' / 'config.toml'
    config.parent.mkdir(parents=True)
    config.write_text(
        'automation_webhook_url = "http://127.0.0.1:1/"\n', encoding='utf-8'
    )
    spec = AutomationStore(tmp_path).draft(
        name='hook-job',
        task='Summarize repo changes with explicit output path notes.txt',
        schedule='every 30m',
        provider=None,
        model=None,
        permission_mode='read-only',
        context_profile='lean',
        max_iterations=3,
        max_tool_calls=3,
        delivery='webhook',
    )
    with pytest.raises(urllib.error.URLError):
        deliver_automation_tick(tmp_path, spec, status='failed', raise_on_error=True)


def test_deliver_webhook_swallows_network_error_by_default(tmp_path: Path) -> None:
    config = tmp_path / '.teaagent' / 'config.toml'
    config.parent.mkdir(parents=True)
    config.write_text(
        'automation_webhook_url = "http://127.0.0.1:1/"\n', encoding='utf-8'
    )
    spec = AutomationStore(tmp_path).draft(
        name='hook-job',
        task='Summarize repo changes with explicit output path notes.txt',
        schedule='every 30m',
        provider=None,
        model=None,
        permission_mode='read-only',
        context_profile='lean',
        max_iterations=3,
        max_tool_calls=3,
        delivery='webhook',
    )
    assert deliver_automation_tick(tmp_path, spec, status='failed') is True

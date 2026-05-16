"""Tests for Slack/Discord native notifications."""

from __future__ import annotations

import json
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from typing import Any

from teaagent.notify import NotifyConfig, fire_notification


class _MockWorker:
    worker_id = 'test-123'
    pid = 42
    started_at = '2026-01-01T00:00:00Z'
    command = ['teaagent', 'agent', 'run', 'gpt', 'hello']


class _CaptureHandler(BaseHTTPRequestHandler):
    received: list[dict[str, Any]] = []

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length) if length else b''
        _CaptureHandler.received.append(json.loads(body))
        self.send_response(200)
        self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:
        pass  # suppress logging


def _start_mock_server() -> tuple[HTTPServer, str]:
    server = HTTPServer(('127.0.0.1', 0), _CaptureHandler)
    port = server.server_address[1]
    url = f'http://127.0.0.1:{port}/'
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, url


class TestSlackDiscordNotifications(unittest.TestCase):
    def setUp(self) -> None:
        _CaptureHandler.received = []

    def test_slack_webhook_sends_formatted_payload(self) -> None:
        server, url = _start_mock_server()
        try:
            config = NotifyConfig(slack_webhook_url=url, timeout_seconds=2)
            fire_notification(config, _MockWorker(), event='completed')
            self.assertEqual(len(_CaptureHandler.received), 1)
            payload = _CaptureHandler.received[0]
            self.assertIn('text', payload)
            self.assertIn('teaagent', payload['text'])
            self.assertIn('blocks', payload)
        finally:
            server.shutdown()

    def test_discord_webhook_sends_embed_payload(self) -> None:
        server, url = _start_mock_server()
        try:
            config = NotifyConfig(discord_webhook_url=url, timeout_seconds=2)
            fire_notification(config, _MockWorker(), event='stopped')
            self.assertEqual(len(_CaptureHandler.received), 1)
            payload = _CaptureHandler.received[0]
            self.assertIn('embeds', payload)
            self.assertEqual(len(payload['embeds']), 1)
            self.assertIn('teaagent', payload['embeds'][0]['title'])
        finally:
            server.shutdown()

    def test_all_notification_targets_fire(self) -> None:
        server, url = _start_mock_server()
        try:
            config = NotifyConfig(
                webhook_url=url,
                slack_webhook_url=url,
                discord_webhook_url=url,
                timeout_seconds=2,
            )
            fire_notification(config, _MockWorker(), event='completed')
            # All three targets should have fired
            self.assertEqual(len(_CaptureHandler.received), 3)
        finally:
            server.shutdown()


if __name__ == '__main__':
    unittest.main()

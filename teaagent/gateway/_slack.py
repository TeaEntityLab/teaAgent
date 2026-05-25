"""Slack adapter for the messaging gateway."""

from __future__ import annotations

import threading
from typing import Any, Optional

from teaagent.gateway._base import GatewayMessage


class SlackAdapter:
    """Slack bot adapter using RTM or Socket Mode.

    Requires ``slack-sdk`` (optional dependency).
    """

    def __init__(
        self,
        bot_token: str,
        app_token: str,
        *,
        server: Any = None,
    ) -> None:
        self._bot_token = bot_token
        self._app_token = app_token
        self._server = server
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._client: Any = None
        self._platform = 'slack'

    @property
    def platform_name(self) -> str:
        return self._platform

    def _check_deps(self) -> None:
        try:
            import slack_sdk  # noqa: F401
        except ImportError:
            raise ImportError(
                'Slack adapter requires slack-sdk. '
                'Install with: pip install slack-sdk'
            ) from None

    def start(self) -> None:
        self._check_deps()
        from slack_sdk.rtm import RTMClient

        self._client = RTMClient(token=self._bot_token)
        self._client.on(event='message')(self._handle)
        self._running = True
        self._thread = threading.Thread(target=self._client.start, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._client is not None:
            self._client.stop()

    def _handle(self, **payload: Any) -> None:
        if not self._running:
            return
        data = payload.get('data', {})
        text = data.get('text', '')
        if not text or data.get('bot_id'):
            return
        msg = GatewayMessage(
            platform=self._platform,
            channel_id=data.get('channel', ''),
            user_id=data.get('user', ''),
            text=text,
            message_id=data.get('ts', ''),
            username=data.get('user', ''),
        )
        if self._server is not None:
            response = self._server.dispatch(msg)
            if response:
                self.send_message(msg.channel_id, response)

    def send_message(self, channel_id: str, text: str) -> bool:
        self._check_deps()
        from slack_sdk.web import WebClient
        try:
            WebClient(token=self._bot_token).chat_postMessage(channel=channel_id, text=text)
            return True
        except Exception:
            return False

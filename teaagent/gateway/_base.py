"""Base adapter protocol and server for the messaging gateway."""

from __future__ import annotations

import threading
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol, runtime_checkable


@dataclass(frozen=True)
class GatewayMessage:
    """Normalized message from any messaging platform."""

    platform: str
    channel_id: str
    user_id: str
    text: str
    message_id: str = ''
    username: str = ''
    thread_ts: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            'platform': self.platform,
            'channel_id': self.channel_id,
            'user_id': self.user_id,
            'text': self.text,
            'message_id': self.message_id,
            'username': self.username,
            'thread_ts': self.thread_ts,
            'metadata': self.metadata,
        }


@runtime_checkable
class GatewayAdapter(Protocol):
    """Protocol each platform adapter must implement."""

    def start(self) -> None:
        """Start the adapter (connect, begin polling)."""

    def stop(self) -> None:
        """Gracefully stop the adapter."""

    def send_message(self, channel_id: str, text: str) -> bool:
        """Send a message to *channel_id*. Returns True on success."""

    @property
    def platform_name(self) -> str:
        """Return the platform identifier (e.g. 'telegram', 'slack')."""


class GatewayServer:
    """Orchestrates multiple platform adapters and dispatches to the agent loop."""

    def __init__(
        self,
        *,
        agent_handler: Optional[Any] = None,
    ) -> None:
        self._adapters: dict[str, GatewayAdapter] = {}
        self._handler = agent_handler
        self._running = False
        self._lock = threading.Lock()

    def register_adapter(self, adapter: GatewayAdapter) -> None:
        self._adapters[adapter.platform_name] = adapter

    def get_adapter(self, name: str) -> Optional[GatewayAdapter]:
        return self._adapters.get(name)

    def list_platforms(self) -> list[str]:
        return list(self._adapters)

    def start_all(self) -> None:
        self._running = True
        for _name, adapter in self._adapters.items():
            with suppress(Exception):
                adapter.start()

    def stop_all(self) -> None:
        self._running = False
        for adapter in self._adapters.values():
            with suppress(Exception):
                adapter.stop()

    def dispatch(self, msg: GatewayMessage) -> Optional[str]:
        """Dispatch *msg* to the agent handler and return the response text."""
        if self._handler is None:
            return None
        return self._handler(msg)

    @property
    def running(self) -> bool:
        return self._running

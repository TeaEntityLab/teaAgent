"""Discord bot adapter for the messaging gateway."""

from __future__ import annotations

import asyncio
import threading
from typing import Any, Optional

from teaagent.gateway._base import GatewayMessage


class DiscordAdapter:
    """Discord bot adapter using gateway intents.

    Requires ``discord.py`` (optional dependency).
    """

    def __init__(
        self,
        token: str,
        *,
        server: Any = None,
    ) -> None:
        self._token = token
        self._server = server
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._client: Any = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._platform = 'discord'

    @property
    def platform_name(self) -> str:
        return self._platform

    def _check_deps(self) -> None:
        try:
            import discord  # noqa: F401
        except ImportError:
            raise ImportError(
                'Discord adapter requires discord.py. '
                'Install with: pip install discord.py'
            ) from None

    def start(self) -> None:
        self._check_deps()
        import discord

        intents = discord.Intents.default()
        intents.message_content = True
        self._client = discord.Client(intents=intents)

        @self._client.event
        async def on_message(message: Any) -> None:
            if not self._running:
                return
            if message.author.bot:
                return
            msg = GatewayMessage(
                platform=self._platform,
                channel_id=str(message.channel.id),
                user_id=str(message.author.id),
                text=message.content,
                message_id=str(message.id),
                username=str(message.author),
            )
            if self._server is not None:
                response = self._server.dispatch(msg)
                if response:
                    await message.channel.send(response)

        self._running = True
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._run_client,
            daemon=True,
        )
        self._thread.start()

    def _run_client(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._client.run(self._token)

    def stop(self) -> None:
        self._running = False
        if self._client is not None and self._loop is not None:
            asyncio.run_coroutine_threadsafe(
                self._client.close(),
                self._loop,
            )

    def send_message(self, channel_id: str, text: str) -> bool:
        self._check_deps()
        if self._loop is None or not self._running:
            return False

        async def _send() -> bool:
            try:
                channel = self._client.get_channel(int(channel_id))
                if channel is None:
                    try:
                        channel = await self._client.fetch_channel(int(channel_id))
                    except Exception:
                        return False
                await channel.send(text)
                return True
            except Exception:
                return False

        future = asyncio.run_coroutine_threadsafe(_send(), self._loop)
        try:
            return future.result(timeout=30)
        except Exception:
            return False

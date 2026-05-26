"""Telegram bot adapter for the messaging gateway."""

from __future__ import annotations

import threading
from typing import Any, Optional

from teaagent.gateway._base import GatewayMessage


class TelegramAdapter:
    """Telegram bot adapter using long-polling.

    Requires ``python-telegram-bot`` (optional dependency).
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
        self._app: Any = None
        self._platform = 'telegram'

    @property
    def platform_name(self) -> str:
        return self._platform

    def _check_deps(self) -> None:
        try:
            import telegram  # noqa: F401
        except ImportError:
            raise ImportError(
                'Telegram adapter requires python-telegram-bot. '
                'Install with: pip install python-telegram-bot'
            ) from None

    def start(self) -> None:
        self._check_deps()
        from telegram.ext import Application, MessageHandler, filters

        self._app = Application.builder().token(self._token).build()
        self._app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle)
        )
        self._running = True
        self._thread = threading.Thread(target=self._app.run_polling, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._app is not None:
            self._app.stop()

    async def _handle(self, update: Any, context: Any) -> None:
        if not self._running or not update.message or not update.message.text:
            return
        msg = GatewayMessage(
            platform=self._platform,
            channel_id=str(update.effective_chat.id),
            user_id=str(update.effective_user.id),
            text=update.message.text,
            message_id=str(update.message.message_id),
            username=update.effective_user.username or '',
        )
        if self._server is not None:
            response = self._server.dispatch(msg)
            if response:
                await update.message.reply_text(response)

    def send_message(self, channel_id: str, text: str) -> bool:
        self._check_deps()
        import telegram

        try:
            bot = telegram.Bot(token=self._token)
            bot.send_message(chat_id=channel_id, text=text)
            return True
        except Exception:
            return False

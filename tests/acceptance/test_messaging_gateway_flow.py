"""Acceptance test for messaging gateway platform.

Verifies: GatewayServer, GatewayMessage, adapter registration, dispatch.
"""

from __future__ import annotations

from teaagent.gateway import GatewayAdapter, GatewayMessage, GatewayServer


class _TestAdapter:
    """In-memory test adapter for gateway testing."""

    def __init__(self) -> None:
        self.started = False
        self.stopped = False
        self.sent: list[tuple[str, str]] = []

    @property
    def platform_name(self) -> str:
        return 'test'

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True

    def send_message(self, channel_id: str, text: str) -> bool:
        self.sent.append((channel_id, text))
        return True


def test_gateway_server_register_and_list() -> None:
    server = GatewayServer()
    adapter = _TestAdapter()
    server.register_adapter(adapter)
    platforms = server.list_platforms()
    assert 'test' in platforms


def test_gateway_server_start_stop() -> None:
    server = GatewayServer()
    adapter = _TestAdapter()
    server.register_adapter(adapter)
    server.start_all()
    assert adapter.started
    server.stop_all()
    assert adapter.stopped


def test_gateway_dispatch_message() -> None:
    captured: list[str] = []

    def handler(msg: GatewayMessage) -> str:
        captured.append(msg.text)
        return f'reply: {msg.text}'

    server = GatewayServer(agent_handler=handler)
    msg = GatewayMessage(
        platform='test', channel_id='ch1', user_id='u1', text='hello gateway',
    )
    response = server.dispatch(msg)
    assert response == 'reply: hello gateway'
    assert captured == ['hello gateway']


def test_gateway_adapter_protocol() -> None:
    adapter = _TestAdapter()
    assert isinstance(adapter, GatewayAdapter)


def test_gateway_telegram_adapter_import() -> None:
    from teaagent.gateway import TelegramAdapter
    adapter = TelegramAdapter(token='test:token')
    assert adapter.platform_name == 'telegram'


def test_gateway_slack_adapter_import() -> None:
    from teaagent.gateway import SlackAdapter
    adapter = SlackAdapter(bot_token='xoxb-test', app_token='xapp-test')
    assert adapter.platform_name == 'slack'


def test_gateway_discord_adapter_import() -> None:
    from teaagent.gateway import DiscordAdapter
    adapter = DiscordAdapter(token='test.token')
    assert adapter.platform_name == 'discord'


def test_gateway_discord_adapter_protocol() -> None:
    from teaagent.gateway import DiscordAdapter
    adapter = DiscordAdapter(token='test.token')
    assert isinstance(adapter, GatewayAdapter)

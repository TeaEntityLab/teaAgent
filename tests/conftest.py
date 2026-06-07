from __future__ import annotations

import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Optional

import pytest

from teaagent.audit import AuditLogger
from teaagent.llm import LLMResponse
from teaagent.run_store import RunStore
from teaagent.tools import ToolRegistry
from test_support import can_bind_loopback, skip_if_socket_bind_is_blocked


@pytest.fixture
def tmp_run_store(tmp_path: Path) -> RunStore:
    """A RunStore backed by a temporary directory that is cleaned up after the test."""
    return RunStore(tmp_path)


@pytest.fixture
def mock_audit_logger(tmp_path: Path) -> AuditLogger:
    """An AuditLogger writing to a temporary directory."""
    store = RunStore(tmp_path)
    return store.audit_logger()


@pytest.fixture
def mock_tool_registry() -> ToolRegistry:
    """A ToolRegistry pre-loaded with a read_file tool."""
    registry = ToolRegistry()

    def _read_file(path: str) -> dict[str, object]:
        with open(path) as f:
            return {'content': f.read()}

    registry.register(
        name='read_file',
        description='Read a file from disk',
        input_schema={
            'type': 'object',
            'properties': {'path': {'type': 'string'}},
            'required': ['path'],
        },
        output_schema={
            'type': 'object',
            'properties': {'content': {'type': 'string'}},
        },
        handler=_read_file,
        annotations={'read_only': True, 'idempotent': True},
    )
    return registry


class FakeAdapter:
    provider = 'fake'

    def __init__(
        self, outputs: list[str], *, before_each: Optional[Callable[[], None]] = None
    ) -> None:
        self.outputs = list(outputs)
        self.requests: list[object] = []
        self.before_each = before_each

    def complete(self, request: object) -> LLMResponse:
        if self.before_each is not None:
            self.before_each()
        self.requests.append(request)
        content = self.outputs.pop(0)
        # LLMResponse doesn't take cost_cents as a parameter - it's a computed property
        return LLMResponse(provider='fake', model='fake-model', content=content)


def fake_adapter(
    outputs: list[str], *, before_each: Optional[Callable[[], None]] = None
) -> FakeAdapter:
    return FakeAdapter(outputs, before_each=before_each)


def temp_workspace(*files: tuple[str, str]) -> tempfile.TemporaryDirectory[str]:
    td = tempfile.TemporaryDirectory()
    root = Path(td.name)
    for relpath, content in files:
        filepath = root / relpath
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(content, encoding='utf-8')
    return td


__all__ = [
    'FakeAdapter',
    'fake_adapter',
    'skip_if_socket_bind_is_blocked',
    'temp_workspace',
]


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Skip network-binding tests when the environment forbids loopback listeners.

    Some sandboxed runners disallow `socket.bind()` entirely. Those tests are still
    valuable in normal dev/CI environments, but should not fail the suite when
    loopback binding is prohibited.
    """

    if can_bind_loopback():
        return

    skip = pytest.mark.skip(reason='sandbox forbids socket.bind() on loopback')
    network_globs = (
        'tests/test_a2a_http.py',
        'tests/test_mcp_http.py',
        'tests/test_analysis_followups.py',
        'tests/acceptance/test_automation_webhook_',
        'tests/acceptance/test_desktop_client_server_',
        'tests/acceptance/test_mcp_',
        'tests/acceptance/test_remote_mcp_',
        'tests/acceptance/test_repo_map_quality_large_repo_flow.py',
        'tests/acceptance/test_vscode_mcp_',
        'tests/acceptance/test_webhook_',
        'tests/e2e/test_end_to_end.py',
        'tests/integration/test_a2a_traceparent.py',
        'tests/integration/test_mcp_tool_adapter.py',
        'tests/integration/test_ultrawork_notify.py',
        'tests/integration/test_webhook_sink.py',
    )

    for item in items:
        nodeid = item.nodeid
        if any(g in nodeid for g in network_globs):
            item.add_marker(skip)

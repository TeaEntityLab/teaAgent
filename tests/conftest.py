from __future__ import annotations

import importlib.util
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Optional, Sequence

import pytest

from teaagent.chat_agent import ChatAgentConfig
from teaagent.llm import LLMResponse
from teaagent.policy import ApprovalPolicy
from teaagent.run_store import RunStore
from teaagent.types import AuditLogger, PermissionMode, ToolRegistry
from test_support import can_bind_loopback, skip_if_socket_bind_is_blocked

_REQUIRED_TEST_DEPENDENCIES = {
    'hypothesis': (
        'tests/test_cli_fuzz_parsers.py',
        'tests/test_property_invariants.py',
    ),
    'redis': (
        'tests/test_hybrid_approval_queue.py',
        'tests/test_hybrid_approval_queue_redis_failures.py',
    ),
}


def _selected_tests_include(
    selectors: Sequence[str], required_paths: Sequence[str]
) -> bool:
    if not selectors:
        return True
    for selector in selectors:
        if selector.startswith('-'):
            continue
        selected_path = selector.split('::', 1)[0]
        if selected_path in {'', '.', 'tests'}:
            return True
        normalized = selected_path.rstrip('/')
        for required_path in required_paths:
            if required_path == normalized or required_path.startswith(
                f'{normalized}/'
            ):
                return True
    return False


def _missing_test_dependencies(selectors: Sequence[str] = ()) -> list[str]:
    return [
        module
        for module, required_paths in _REQUIRED_TEST_DEPENDENCIES.items()
        if _selected_tests_include(selectors, required_paths)
        and importlib.util.find_spec(module) is None
    ]


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


@pytest.fixture(autouse=True)
def _reset_module_caches() -> None:
    """Reset global caches between tests (TST-012).

    Collects garbage to free thread objects and reduce memory pressure
    under ``--cov``, which can otherwise cause pydantic segfaults and
    ``RuntimeError: can't start new thread`` on CI (Python 3.10).
    """
    import gc

    from teaagent.config_loader import clear_config_cache

    clear_config_cache()
    _clear_lazy_export_cache()
    _clear_tui_completion_cache()
    _clear_code_analysis_cache()
    gc.collect()
    yield
    clear_config_cache()
    _clear_lazy_export_cache()
    _clear_tui_completion_cache()
    _clear_code_analysis_cache()
    gc.collect()


def _clear_lazy_export_cache() -> None:
    """Clear the teaagent lazy-import cache so tests start fresh."""
    import contextlib

    with contextlib.suppress(ImportError, AttributeError, KeyError):
        from teaagent._lazy_exports import _CACHE

        _CACHE.clear()


def _clear_tui_completion_cache() -> None:
    """Clear the TUI ontology completion cache."""
    import contextlib

    with contextlib.suppress(ImportError, AttributeError):
        from teaagent.tui._completion import _ontology_cache

        _ontology_cache.clear()


def _clear_code_analysis_cache() -> None:
    """Clear the code-analysis graph cache."""
    import contextlib

    with contextlib.suppress(ImportError, AttributeError):
        from teaagent.code_analysis._tools import clear_graph_cache

        clear_graph_cache()


@pytest.fixture
def mock_llm_adapter() -> FakeAdapter:
    """A FakeAdapter that returns empty responses for testing agent loops."""
    return FakeAdapter([])


@pytest.fixture
def fake_adapter_with_tool_response() -> FakeAdapter:
    """A FakeAdapter pre-configured with a common tool response pattern."""
    return FakeAdapter(
        [
            '{"type":"tool","tool_name":"workspace_read_file","arguments":{"path":"test.txt"},"call_id":"read-1"}',
            '{"type":"final","content":"done"}',
        ]
    )


@pytest.fixture
def fake_adapter_with_final_response() -> FakeAdapter:
    """A FakeAdapter pre-configured with a simple final response."""
    return FakeAdapter(['{"type":"final","content":"done"}'])


@pytest.fixture
def fake_adapter_with_invalid_then_final() -> FakeAdapter:
    """A FakeAdapter that returns invalid JSON then a valid final response (for retry testing)."""
    return FakeAdapter(['not-json', '{"type":"final","content":"done"}'])


@pytest.fixture
def fake_adapter_with_subagent_response() -> FakeAdapter:
    """A FakeAdapter pre-configured with subagent tool response pattern."""
    return FakeAdapter(
        [
            '{"type":"tool","tool_name":"subagent","arguments":{"task":"child task"},"call_id":"sub-1"}',
            '{"type":"final","content":"child done"}',
            '{"type":"final","content":"parent done"}',
        ]
    )


@pytest.fixture
def chat_agent_config(tmp_path: Path) -> ChatAgentConfig:
    """A ChatAgentConfig for testing with default settings."""
    return ChatAgentConfig.from_root(tmp_path)


@pytest.fixture
def chat_agent_config_with_limits(tmp_path: Path) -> ChatAgentConfig:
    """A ChatAgentConfig with iteration and tool call limits for testing."""
    return ChatAgentConfig.from_root(tmp_path, max_iterations=3, max_tool_calls=2)


@pytest.fixture
def chat_agent_config_with_subagent(tmp_path: Path) -> ChatAgentConfig:
    """A ChatAgentConfig with subagent enabled for testing."""
    return ChatAgentConfig.from_root(tmp_path, enable_subagent=True)


@pytest.fixture
def approval_policy_read_only() -> ApprovalPolicy:
    """An ApprovalPolicy configured for read-only mode."""
    return ApprovalPolicy(permission_mode=PermissionMode.READ_ONLY)


@pytest.fixture
def approval_policy_workspace_write() -> ApprovalPolicy:
    """An ApprovalPolicy configured for workspace-write mode."""
    return ApprovalPolicy(permission_mode=PermissionMode.WORKSPACE_WRITE)


@pytest.fixture
def approval_policy_allow() -> ApprovalPolicy:
    """An ApprovalPolicy configured for allow mode."""
    return ApprovalPolicy(permission_mode=PermissionMode.ALLOW)


@pytest.fixture
def approval_policy_danger_full_access() -> ApprovalPolicy:
    """An ApprovalPolicy configured for danger-full-access mode."""
    return ApprovalPolicy(permission_mode=PermissionMode.DANGER_FULL_ACCESS)


@pytest.fixture
def empty_tool_registry() -> ToolRegistry:
    """An empty ToolRegistry for testing."""
    return ToolRegistry()


def make_minimal_registry() -> ToolRegistry:
    """Create a minimal ToolRegistry for testing."""
    return ToolRegistry()


def make_noop_registry() -> ToolRegistry:
    """Create a ToolRegistry with a noop tool for testing."""
    registry = ToolRegistry()

    def _noop(**kwargs: object) -> dict[str, object]:
        return {'result': 'noop'}

    registry.register(
        name='noop',
        description='A no-op tool for testing',
        input_schema={'type': 'object', 'properties': {}, 'additionalProperties': True},
        output_schema={'type': 'object', 'properties': {'result': {'type': 'string'}}},
        handler=_noop,
        annotations={'idempotent': True},
    )
    return registry


def make_destructive_write_registry() -> ToolRegistry:
    """Create a ToolRegistry with a destructive write tool for testing."""
    from teaagent.types import ToolAnnotations

    registry = ToolRegistry()

    def _write_file(path: str, content: str) -> dict[str, object]:
        with open(path, 'w') as f:
            f.write(content)
        return {'success': True}

    registry.register(
        name='workspace_write_file',
        description='Write a file to disk (destructive)',
        input_schema={
            'type': 'object',
            'properties': {'path': {'type': 'string'}, 'content': {'type': 'string'}},
            'required': ['path', 'content'],
        },
        output_schema={
            'type': 'object',
            'properties': {'success': {'type': 'boolean'}},
        },
        handler=_write_file,
        annotations=ToolAnnotations(destructive=True),
    )
    return registry


def make_plugin_registrar(name: str):
    """Return a plugin callable that registers one tool named *name*."""
    from teaagent.types import ToolAnnotations

    def register(registry: ToolRegistry) -> None:
        registry.register(
            name=name,
            description=f'Plugin tool {name}',
            input_schema={'type': 'object', 'properties': {}},
            output_schema={'type': 'object', 'properties': {}},
            annotations=ToolAnnotations(read_only=True),
            handler=lambda _: {},
        )

    return register


@pytest.fixture
def git_repo_with_config(tmp_path: Path) -> Path:
    """A git repository initialized with test user config for testing git operations."""
    subprocess.run(['git', 'init'], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ['git', 'config', 'user.email', 'test@example.com'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'config', 'user.name', 'Test User'],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    return tmp_path


@pytest.fixture
def git_repo_with_commit(git_repo_with_config: Path) -> Path:
    """A git repository with an initial commit for testing."""
    (git_repo_with_config / 'test.txt').write_text('content')
    subprocess.run(
        ['git', 'add', 'test.txt'],
        cwd=git_repo_with_config,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ['git', 'commit', '-m', 'initial'],
        cwd=git_repo_with_config,
        check=True,
        capture_output=True,
    )
    return git_repo_with_config


@pytest.fixture
def test_file_in_workspace(tmp_path: Path) -> Path:
    """A test file created in the temporary workspace."""
    test_file = tmp_path / 'test.txt'
    test_file.write_text('test content', encoding='utf-8')
    return test_file


@pytest.fixture
def hello_file_in_workspace(tmp_path: Path) -> Path:
    """A hello.txt file created in the temporary workspace (common pattern in tests)."""
    hello_file = tmp_path / 'hello.txt'
    hello_file.write_text('hello', encoding='utf-8')
    return hello_file


def temp_workspace(*files: tuple[str, str]) -> tempfile.TemporaryDirectory[str]:
    td = tempfile.TemporaryDirectory()
    root = Path(td.name)
    for relpath, content in files:
        filepath = root / relpath
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(content, encoding='utf-8')
    return td


def pytest_sessionstart(session: pytest.Session) -> None:
    """Pre-warm common modules to reduce segfault risk under ``--cov``.

    Coverage instrumentation of type-annotation evaluation (used by
    ``pydantic-core``, ``typing.get_type_hints``, and ``dataclasses``)
    can trigger segfaults on Python 3.10.  Pre-importing modules here
    warms schema caches before the bulk of coverage tracking begins.
    """
    missing = _missing_test_dependencies(session.config.args)
    if missing:
        pytest.exit(
            'Missing test dependencies: '
            + ', '.join(missing)
            + '. Install the repository test environment with: '
            + 'pip install -e ".[dev]"',
            returncode=4,
        )

    # Pre-import high-traffic teaagent modules so their type-evaluation
    # happens once, not under coverage pressure.
    _preimport_modules = [
        'teaagent.run_store',
        'teaagent.audit',
        'teaagent.runner',
        'teaagent.budget',
        'teaagent.policy',
        'teaagent.types',
        'teaagent.tool_registry',
    ]
    import contextlib
    import importlib

    for mod in _preimport_modules:
        with contextlib.suppress(Exception):
            importlib.import_module(mod)


__all__ = [
    'FakeAdapter',
    '_missing_test_dependencies',
    'fake_adapter',
    'skip_if_socket_bind_is_blocked',
    'temp_workspace',
    'fake_adapter_with_tool_response',
    'fake_adapter_with_final_response',
    'fake_adapter_with_invalid_then_final',
    'fake_adapter_with_subagent_response',
]


_NIGHTLY_NODE_FRAGMENTS = (
    'tests/integration/',
    'test_audit_benchmark.py',
    'test_cli_fuzz_parsers.py',
    'test_mutation_smoke_registry.py',
    'test_governance_adversarial_runtime.py',
    'test_property_invariants.py',
    'integration/test_benchmark.py',
)


def _apply_suite_tier_markers(items: list[pytest.Item]) -> None:
    for item in items:
        nodeid = item.nodeid
        if 'tests/acceptance/' in nodeid:
            item.add_marker(pytest.mark.acceptance)
        if item.get_closest_marker('slow') or any(
            fragment in nodeid for fragment in _NIGHTLY_NODE_FRAGMENTS
        ):
            item.add_marker(pytest.mark.nightly)


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Apply suite tier markers and skip network tests in bind-blocked sandboxes."""

    _apply_suite_tier_markers(items)

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

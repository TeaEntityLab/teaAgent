from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from teaagent.managed_runtime import (
    GoogleADKRuntime,
    ManagedAgentRunner,
    ManagedRunResult,
    ManagedRuntimeAdapter,
    VertexAgentRuntime,
    _adk_events_to_text,
    _format_vertex_output,
    _vertex_agent_resource_name,
    _vertex_query_engine,
    managed_runtime_capabilities,
)


class FakeRuntime:
    def __init__(self, response: str = 'done') -> None:
        self._response = response

    def run_task(self, task: str, *, context: dict) -> str:
        return self._response

    def health_check(self) -> bool:
        return True


class UnhealthyRuntime:
    def run_task(self, task: str, *, context: dict) -> str:
        raise RuntimeError('runtime down')

    def health_check(self) -> bool:
        return False


def test_fake_satisfies_protocol() -> None:
    assert isinstance(FakeRuntime(), ManagedRuntimeAdapter)


def test_unhealthy_satisfies_protocol() -> None:
    assert isinstance(UnhealthyRuntime(), ManagedRuntimeAdapter)


def test_run_returns_managed_run_result() -> None:
    runner = ManagedAgentRunner(FakeRuntime('result text'), runtime_name='fake')
    result = runner.run('do something')
    assert isinstance(result, ManagedRunResult)
    assert result.output == 'result text'
    assert result.runtime == 'fake'


def test_run_passes_context() -> None:
    received: list[dict] = []

    class ContextCapture:
        def run_task(self, task: str, *, context: dict) -> str:
            received.append(context)
            return 'ok'

        def health_check(self) -> bool:
            return True

    runner = ManagedAgentRunner(ContextCapture())
    runner.run('task', context={'key': 'value'})
    assert received[0]['key'] == 'value'


def test_run_empty_context_defaults_to_dict() -> None:
    received: list[dict] = []

    class ContextCapture:
        def run_task(self, task: str, *, context: dict) -> str:
            received.append(context)
            return 'ok'

        def health_check(self) -> bool:
            return True

    runner = ManagedAgentRunner(ContextCapture())
    runner.run('task')
    assert isinstance(received[0], dict)


def test_runtime_name_defaults_to_class_name() -> None:
    runner = ManagedAgentRunner(FakeRuntime())
    assert runner._runtime_name == 'FakeRuntime'


def test_healthy_returns_true() -> None:
    runner = ManagedAgentRunner(FakeRuntime())
    assert runner.healthy()


def test_healthy_returns_false_for_unhealthy() -> None:
    runner = ManagedAgentRunner(UnhealthyRuntime())
    assert not runner.healthy()


def test_anthropic_raises_import_error_without_sdk() -> None:
    from teaagent.managed_runtime import AnthropicManagedRuntime

    try:
        import anthropic  # noqa: F401

        pytest.skip('anthropic is installed; stub path not reachable')
    except ImportError:
        with pytest.raises(ImportError) as ctx:
            AnthropicManagedRuntime(agent_id='x')
        assert 'anthropic' in str(ctx.value).lower()


def test_openai_raises_import_error_without_sdk() -> None:
    from teaagent.managed_runtime import OpenAIManagedRuntime

    try:
        import openai  # noqa: F401

        pytest.skip('openai is installed; stub path not reachable')
    except ImportError:
        with pytest.raises(ImportError) as ctx:
            OpenAIManagedRuntime(assistant_id='x')
        assert 'openai' in str(ctx.value).lower()


def test_google_adk_raises_import_error_without_sdk() -> None:
    from teaagent.managed_runtime import GoogleADKRuntime

    try:
        import google.adk  # noqa: F401

        pytest.skip('google-adk is installed; stub path not reachable')
    except ImportError:
        with pytest.raises(ImportError) as ctx:
            GoogleADKRuntime(agent_name='x')
        assert 'adk' in str(ctx.value).lower()


def test_vertex_raises_import_error_without_sdk() -> None:
    from teaagent.managed_runtime import VertexAgentRuntime

    try:
        import google.cloud.aiplatform  # noqa: F401

        pytest.skip('google-cloud-aiplatform is installed')
    except ImportError:
        with pytest.raises(ImportError) as ctx:
            VertexAgentRuntime(agent_id='x')
        assert 'vertex' in str(ctx.value).lower()


def test_managed_runtime_capabilities_report_optional_sdk_status() -> None:
    capabilities = managed_runtime_capabilities()
    names = {item['name'] for item in capabilities}
    assert 'anthropic' in names
    assert 'openai' in names
    assert 'google-adk' in names
    assert 'vertex-agent-engine' in names
    for item in capabilities:
        assert item['status'] in {'available', 'missing_sdk'}
        assert item['experimental']
        assert item['install_hint']


def test_format_vertex_output_nested_dict() -> None:
    assert _format_vertex_output({'output': {'text': 'hello'}}) == 'hello'


def test_adk_events_to_text_collects_final_response() -> None:
    event = SimpleNamespace(
        is_final_response=lambda: True,
        content=SimpleNamespace(
            parts=[SimpleNamespace(text='answer one')],
        ),
    )
    assert _adk_events_to_text([event]) == 'answer one'


def test_vertex_agent_resource_name_short_id() -> None:
    name = _vertex_agent_resource_name(
        '456',
        project_id='proj',
        location='us-central1',
    )
    assert name == 'projects/proj/locations/us-central1/reasoningEngines/456'


def test_vertex_query_prefers_message_kwarg() -> None:
    engine = MagicMock()
    engine.query.return_value = {'output': 'vertex-ok'}
    result = _vertex_query_engine(engine, 'ping', context={'user_id': 'u1'})
    engine.query.assert_called_once_with(message='ping', user_id='u1')
    assert _format_vertex_output(result) == 'vertex-ok'


@pytest.fixture
def google_adk_setup():
    try:
        import google.adk  # noqa: F401
    except ImportError:
        pytest.skip('google-adk not installed')
    yield


def test_run_task_uses_runner(google_adk_setup) -> None:
    fake_agent = object()
    final_event = SimpleNamespace(
        is_final_response=lambda: True,
        content=SimpleNamespace(parts=[SimpleNamespace(text='adk-result')]),
    )
    mock_runner = MagicMock()
    mock_runner.run.return_value = [final_event]

    with patch('google.adk.runners.Runner', return_value=mock_runner):
        runtime = GoogleADKRuntime(
            agent_name='demo_app',
            agent=fake_agent,
        )
        output = runtime.run_task('hello', context={})

    assert output == 'adk-result'
    mock_runner.run.assert_called_once()
    call_kwargs = mock_runner.run.call_args.kwargs
    assert call_kwargs['user_id'] == 'teaagent'
    assert call_kwargs['new_message'].parts[0].text == 'hello'


@pytest.fixture
def vertex_mock_setup():
    import sys
    from unittest.mock import MagicMock, patch

    # Patch _sdk_import_available to return True to avoid importlib.util.find_spec checking mocked modules
    sdk_patcher = patch(
        'teaagent.managed_runtime._sdk_import_available', return_value=True
    )
    sdk_patcher.start()

    # Mock sys.modules for google.cloud.aiplatform and vertexai to avoid MemoryError from loading large libraries
    orig_aiplatform = sys.modules.get('google.cloud.aiplatform')
    orig_vertexai = sys.modules.get('vertexai')
    orig_agent_engines = sys.modules.get('vertexai.agent_engines')

    sys.modules['google.cloud.aiplatform'] = MagicMock()
    sys.modules['vertexai'] = MagicMock()
    sys.modules['vertexai.agent_engines'] = MagicMock()

    yield

    sdk_patcher.stop()
    for name, orig in [
        ('google.cloud.aiplatform', orig_aiplatform),
        ('vertexai', orig_vertexai),
        ('vertexai.agent_engines', orig_agent_engines),
    ]:
        if orig is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = orig


def test_run_task_fetches_engine_and_queries(vertex_mock_setup) -> None:
    import sys

    engine = MagicMock()
    engine.query.return_value = 'remote-response'
    engine.resource_name = 'projects/p/locations/us-central1/reasoningEngines/1'

    # Configure the mocked modules in sys.modules
    sys.modules['vertexai'].agent_engines.get.return_value = engine

    runtime = VertexAgentRuntime(
        agent_id='1',
        project_id='p',
        location='us-central1',
    )
    output = runtime.run_task('task', context={})

    assert output == 'remote-response'
    assert runtime.health_check()

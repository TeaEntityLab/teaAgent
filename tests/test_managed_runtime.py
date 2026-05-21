from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

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


class ManagedRuntimeAdapterProtocolTests(unittest.TestCase):
    def test_fake_satisfies_protocol(self) -> None:
        self.assertIsInstance(FakeRuntime(), ManagedRuntimeAdapter)

    def test_unhealthy_satisfies_protocol(self) -> None:
        self.assertIsInstance(UnhealthyRuntime(), ManagedRuntimeAdapter)


class ManagedAgentRunnerTests(unittest.TestCase):
    def test_run_returns_managed_run_result(self) -> None:
        runner = ManagedAgentRunner(FakeRuntime('result text'), runtime_name='fake')
        result = runner.run('do something')
        self.assertIsInstance(result, ManagedRunResult)
        self.assertEqual(result.output, 'result text')
        self.assertEqual(result.runtime, 'fake')

    def test_run_passes_context(self) -> None:
        received: list[dict] = []

        class ContextCapture:
            def run_task(self, task: str, *, context: dict) -> str:
                received.append(context)
                return 'ok'

            def health_check(self) -> bool:
                return True

        runner = ManagedAgentRunner(ContextCapture())
        runner.run('task', context={'key': 'value'})
        self.assertEqual(received[0]['key'], 'value')

    def test_run_empty_context_defaults_to_dict(self) -> None:
        received: list[dict] = []

        class ContextCapture:
            def run_task(self, task: str, *, context: dict) -> str:
                received.append(context)
                return 'ok'

            def health_check(self) -> bool:
                return True

        runner = ManagedAgentRunner(ContextCapture())
        runner.run('task')
        self.assertIsInstance(received[0], dict)

    def test_runtime_name_defaults_to_class_name(self) -> None:
        runner = ManagedAgentRunner(FakeRuntime())
        self.assertEqual(runner._runtime_name, 'FakeRuntime')

    def test_healthy_returns_true(self) -> None:
        runner = ManagedAgentRunner(FakeRuntime())
        self.assertTrue(runner.healthy())

    def test_healthy_returns_false_for_unhealthy(self) -> None:
        runner = ManagedAgentRunner(UnhealthyRuntime())
        self.assertFalse(runner.healthy())


class RuntimeStubImportTests(unittest.TestCase):
    def test_anthropic_raises_import_error_without_sdk(self) -> None:
        from teaagent.managed_runtime import AnthropicManagedRuntime

        try:
            import anthropic  # noqa: F401

            self.skipTest('anthropic is installed; stub path not reachable')
        except ImportError:
            with self.assertRaises(ImportError) as ctx:
                AnthropicManagedRuntime(agent_id='x')
            self.assertIn('anthropic', str(ctx.exception).lower())

    def test_openai_raises_import_error_without_sdk(self) -> None:
        from teaagent.managed_runtime import OpenAIManagedRuntime

        try:
            import openai  # noqa: F401

            self.skipTest('openai is installed; stub path not reachable')
        except ImportError:
            with self.assertRaises(ImportError) as ctx:
                OpenAIManagedRuntime(assistant_id='x')
            self.assertIn('openai', str(ctx.exception).lower())

    def test_google_adk_raises_import_error_without_sdk(self) -> None:
        from teaagent.managed_runtime import GoogleADKRuntime

        try:
            import google.adk  # noqa: F401

            self.skipTest('google-adk is installed; stub path not reachable')
        except ImportError:
            with self.assertRaises(ImportError) as ctx:
                GoogleADKRuntime(agent_name='x')
            self.assertIn('adk', str(ctx.exception).lower())

    def test_vertex_raises_import_error_without_sdk(self) -> None:
        from teaagent.managed_runtime import VertexAgentRuntime

        try:
            import google.cloud.aiplatform  # noqa: F401

            self.skipTest('google-cloud-aiplatform is installed')
        except ImportError:
            with self.assertRaises(ImportError) as ctx:
                VertexAgentRuntime(agent_id='x')
            self.assertIn('vertex', str(ctx.exception).lower())


class ManagedRuntimeHelperTests(unittest.TestCase):
    def test_format_vertex_output_nested_dict(self) -> None:
        self.assertEqual(
            _format_vertex_output({'output': {'text': 'hello'}}),
            'hello',
        )

    def test_adk_events_to_text_collects_final_response(self) -> None:
        event = SimpleNamespace(
            is_final_response=lambda: True,
            content=SimpleNamespace(
                parts=[SimpleNamespace(text='answer one')],
            ),
        )
        self.assertEqual(_adk_events_to_text([event]), 'answer one')

    def test_vertex_agent_resource_name_short_id(self) -> None:
        name = _vertex_agent_resource_name(
            '456',
            project_id='proj',
            location='us-central1',
        )
        self.assertEqual(
            name,
            'projects/proj/locations/us-central1/reasoningEngines/456',
        )

    def test_vertex_query_prefers_message_kwarg(self) -> None:
        engine = MagicMock()
        engine.query.return_value = {'output': 'vertex-ok'}
        result = _vertex_query_engine(engine, 'ping', context={'user_id': 'u1'})
        engine.query.assert_called_once_with(message='ping', user_id='u1')
        self.assertEqual(_format_vertex_output(result), 'vertex-ok')


class GoogleADKRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        try:
            import google.adk  # noqa: F401
        except ImportError:
            self.skipTest('google-adk not installed')

    def test_run_task_uses_runner(self) -> None:
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

        self.assertEqual(output, 'adk-result')
        mock_runner.run.assert_called_once()
        call_kwargs = mock_runner.run.call_args.kwargs
        self.assertEqual(call_kwargs['user_id'], 'teaagent')
        self.assertEqual(call_kwargs['new_message'].parts[0].text, 'hello')


class VertexAgentRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        try:
            import google.cloud.aiplatform  # noqa: F401
        except ImportError:
            self.skipTest('google-cloud-aiplatform not installed')

    def test_run_task_fetches_engine_and_queries(self) -> None:
        engine = MagicMock()
        engine.query.return_value = 'remote-response'
        engine.resource_name = 'projects/p/locations/us-central1/reasoningEngines/1'

        with (
            patch('vertexai.init'),
            patch('vertexai.agent_engines.get', return_value=engine),
        ):
            runtime = VertexAgentRuntime(
                agent_id='1',
                project_id='p',
                location='us-central1',
            )
            output = runtime.run_task('task', context={})

        self.assertEqual(output, 'remote-response')
        self.assertTrue(runtime.healthy())


if __name__ == '__main__':
    unittest.main()

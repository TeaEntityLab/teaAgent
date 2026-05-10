from __future__ import annotations

import unittest

from teaagent.managed_runtime import (
    ManagedAgentRunner,
    ManagedRunResult,
    ManagedRuntimeAdapter,
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


if __name__ == '__main__':
    unittest.main()

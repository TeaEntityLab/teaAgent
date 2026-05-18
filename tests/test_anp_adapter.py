from __future__ import annotations

import unittest

from teaagent.anp_adapter import (
    ANPAdapterError,
    ANPBidirectionalRouter,
    ANPInboundAdapter,
    ANPOutboundClient,
)


class ANPInboundAdapterTests(unittest.TestCase):
    def test_handle_task_success(self) -> None:
        adapter = ANPInboundAdapter(lambda task, context: f'ok:{task}:{context["x"]}')
        result = adapter.handle_task({'task': 'build', 'context': {'x': '1'}})
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['output'], 'ok:build:1')

    def test_handle_task_requires_task(self) -> None:
        adapter = ANPInboundAdapter(lambda task, context: 'unused')
        with self.assertRaises(ANPAdapterError):
            adapter.handle_task({'context': {}})

    def test_handle_task_maps_execution_error(self) -> None:
        def _fail(task: str, context: dict[str, object]) -> str:
            raise RuntimeError('local failure')

        adapter = ANPInboundAdapter(_fail)
        result = adapter.try_handle_task({'task': 'test'})
        self.assertEqual(result['status'], 'error')
        self.assertIn('local failure', result['error'])


class ANPOutboundClientTests(unittest.TestCase):
    def test_delegate_uses_transport(self) -> None:
        calls: list[tuple[str, str, dict[str, object]]] = []

        def _transport(endpoint: str, task: str, context: dict[str, object]) -> dict:
            calls.append((endpoint, task, context))
            return {'output': 'remote done', 'agent_name': 'remote-a'}

        client = ANPOutboundClient(transport=_transport)
        result = client.delegate(
            endpoint='http://agent.example',
            task='ship',
            context={'env': 'ci'},
        )
        self.assertEqual(result.output, 'remote done')
        self.assertEqual(result.agent_name, 'remote-a')
        self.assertEqual(calls[0][1], 'ship')


class ANPBidirectionalRouterTests(unittest.TestCase):
    def test_auto_prefers_local(self) -> None:
        router = ANPBidirectionalRouter(
            local_runner=lambda task, context: 'local ok',
            outbound_client=ANPOutboundClient(
                transport=lambda endpoint, task, context: {'output': 'remote'}
            ),
        )
        result = router.route(task='run', route='auto', remote_endpoint='http://remote')
        self.assertEqual(result.source, 'local')
        self.assertEqual(result.output, 'local ok')

    def test_auto_falls_back_to_remote_when_local_fails(self) -> None:
        router = ANPBidirectionalRouter(
            local_runner=lambda task, context: (_ for _ in ()).throw(
                RuntimeError('boom')
            ),
            outbound_client=ANPOutboundClient(
                transport=lambda endpoint, task, context: {
                    'output': 'remote recovered',
                    'agent_name': 'remote-b',
                }
            ),
        )
        result = router.route(
            task='run',
            route='auto',
            remote_endpoint='http://remote',
            context={'k': 'v'},
        )
        self.assertEqual(result.source, 'remote')
        self.assertTrue(result.fallback_used)
        self.assertEqual(result.output, 'remote recovered')

    def test_remote_route_requires_endpoint(self) -> None:
        router = ANPBidirectionalRouter(
            local_runner=lambda task, context: 'local ok',
            outbound_client=ANPOutboundClient(
                transport=lambda endpoint, task, context: {'output': 'remote'}
            ),
        )
        with self.assertRaises(ANPAdapterError):
            router.route(task='run', route='remote')


if __name__ == '__main__':
    unittest.main()

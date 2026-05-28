from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout

from teaagent import classify_task, route_model
from teaagent.cli import main
from teaagent.model_routing import analyze_complexity, estimate_tokens


class ModelRoutingTests(unittest.TestCase):
    def test_classify_task_uses_deterministic_categories(self) -> None:
        self.assertEqual(classify_task('review this patch for regressions'), 'review')
        self.assertEqual(classify_task('run tests and fix failures'), 'test')
        self.assertEqual(classify_task('update docs cli markdown'), 'docs')

    def test_route_model_chooses_provider_specific_model(self) -> None:
        route = route_model('review this patch', provider='gpt')

        self.assertEqual(route.category, 'review')
        self.assertEqual(route.provider, 'gpt')
        # With complexity-based routing, review tasks (medium complexity) use gpt-4o-mini
        self.assertEqual(route.model, 'gpt-4o-mini')
        self.assertEqual(route.complexity, 'medium')

    def test_route_model_respects_explicit_model_override(self) -> None:
        route = route_model('review this patch', provider='gpt', model='custom-model')

        self.assertEqual(route.model, 'custom-model')
        self.assertEqual(route.reason, 'explicit model override')

    def test_analyze_complexity_high(self) -> None:
        self.assertEqual(analyze_complexity('redesign the system architecture'), 'high')
        self.assertEqual(analyze_complexity('implement distributed caching'), 'high')
        self.assertEqual(
            analyze_complexity('add authentication and encryption'), 'high'
        )

    def test_analyze_complexity_medium(self) -> None:
        self.assertEqual(analyze_complexity('add a new feature'), 'medium')
        self.assertEqual(analyze_complexity('fix the bug in the handler'), 'medium')
        self.assertEqual(analyze_complexity('update the configuration'), 'medium')

    def test_analyze_complexity_low(self) -> None:
        self.assertEqual(analyze_complexity('update the documentation'), 'low')
        self.assertEqual(analyze_complexity('add unit tests'), 'low')
        self.assertEqual(analyze_complexity('add comment to code'), 'low')

    def test_estimate_tokens(self) -> None:
        # Low complexity
        tokens = estimate_tokens('fix typo', 'low')
        self.assertGreater(tokens, 2000)  # Base buffer

        # Medium complexity
        tokens = estimate_tokens('add feature', 'medium')
        self.assertGreater(tokens, 2000)

        # High complexity
        tokens = estimate_tokens('redesign architecture', 'high')
        self.assertGreater(tokens, 2000)

    def test_route_model_includes_complexity(self) -> None:
        route = route_model('redesign the system architecture', provider='claude')

        self.assertEqual(route.complexity, 'high')
        self.assertGreater(route.estimated_tokens, 0)

    def test_route_model_uses_complexity_based_routing(self) -> None:
        # High complexity should use premium model
        route = route_model('redesign architecture', provider='gpt')
        self.assertEqual(route.model, 'gpt-4o')
        self.assertEqual(route.complexity, 'high')

        # Low complexity should use cheaper model
        route = route_model('update documentation', provider='gpt')
        self.assertEqual(route.model, 'gpt-4o-mini')
        self.assertEqual(route.complexity, 'low')

    def test_cli_model_route_outputs_json(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                ['model', 'route', 'review this patch', '--provider', 'gpt']
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload['category'], 'review')
        # With complexity-based routing, review tasks (medium complexity) use gpt-4o-mini
        self.assertEqual(payload['model'], 'gpt-4o-mini')
        self.assertIn('complexity', payload)


if __name__ == '__main__':
    unittest.main()

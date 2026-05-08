from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout

from teaagent import classify_task, route_model
from teaagent.cli import main


class ModelRoutingTests(unittest.TestCase):
    def test_classify_task_uses_deterministic_categories(self) -> None:
        self.assertEqual(classify_task('review this patch for regressions'), 'review')
        self.assertEqual(classify_task('run tests and fix failures'), 'test')
        self.assertEqual(classify_task('update docs cli markdown'), 'docs')

    def test_route_model_chooses_provider_specific_model(self) -> None:
        route = route_model('review this patch', provider='gpt')

        self.assertEqual(route.category, 'review')
        self.assertEqual(route.provider, 'gpt')
        self.assertEqual(route.model, 'gpt-4o')

    def test_route_model_respects_explicit_model_override(self) -> None:
        route = route_model('review this patch', provider='gpt', model='custom-model')

        self.assertEqual(route.model, 'custom-model')
        self.assertEqual(route.reason, 'explicit model override')

    def test_cli_model_route_outputs_json(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                ['model', 'route', 'review this patch', '--provider', 'gpt']
            )

        payload = json.loads(output.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload['category'], 'review')
        self.assertEqual(payload['model'], 'gpt-4o')


if __name__ == '__main__':
    unittest.main()

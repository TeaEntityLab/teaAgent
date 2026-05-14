from __future__ import annotations

import io
import json
import os
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from conftest import FakeAdapter

from teaagent.cli import main


class ModelSmokeGatingFlowAcceptanceTests(unittest.TestCase):
    def test_smoke_skips_without_required_env_and_does_not_call_provider(self) -> None:
        def fail_factory(provider: str, model: str | None = None) -> object:
            raise AssertionError(f'provider should not be called: {provider}')

        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = main(
                [
                    'model',
                    'smoke',
                    'gpt',
                    '--live-env-var',
                    'TEAAGENT_ACCEPT_HOSTED_SMOKE',
                ],
                _adapter_factory=fail_factory,
            )
        payload = json.loads(output.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertTrue(payload['skipped'])
        self.assertEqual(payload['provider'], 'gpt')
        self.assertIn('TEAAGENT_ACCEPT_HOSTED_SMOKE', payload['reason'])

    def test_smoke_runs_when_required_env_is_set(self) -> None:
        adapter = FakeAdapter(['ok'])
        output = io.StringIO()
        with (
            patch.dict(os.environ, {'TEAAGENT_ACCEPT_HOSTED_SMOKE': '1'}),
            redirect_stdout(output),
        ):
            exit_code = main(
                [
                    'model',
                    'smoke',
                    'gpt',
                    '--live-env-var',
                    'TEAAGENT_ACCEPT_HOSTED_SMOKE',
                ],
                _adapter_factory=lambda _provider, model=None: adapter,
            )
        payload = json.loads(output.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload['provider'], 'fake')
        self.assertEqual(payload['model'], 'fake-model')
        self.assertEqual(payload['content'], 'ok')
        self.assertNotIn('skipped', payload)


if __name__ == '__main__':
    unittest.main()

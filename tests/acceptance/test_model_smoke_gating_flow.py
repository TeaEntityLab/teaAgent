from __future__ import annotations

import io
import json
import os
from contextlib import redirect_stdout
from unittest.mock import patch

from conftest import FakeAdapter

from teaagent.cli import main


def test_smoke_skips_without_required_env_and_does_not_call_provider() -> None:
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

    assert exit_code == 0
    assert payload['skipped']
    assert payload['provider'] == 'gpt'
    assert 'TEAAGENT_ACCEPT_HOSTED_SMOKE' in payload['reason']


def test_smoke_runs_when_required_env_is_set() -> None:
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

    assert exit_code == 0
    assert payload['provider'] == 'fake'
    assert payload['model'] == 'fake-model'
    assert payload['content'] == 'ok'
    assert 'skipped' not in payload

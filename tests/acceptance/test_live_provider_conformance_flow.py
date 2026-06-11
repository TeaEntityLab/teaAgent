from __future__ import annotations

import io
import json
import os
from contextlib import redirect_stdout
from unittest.mock import patch

from conftest import FakeAdapter

from teaagent.cli import main
from teaagent.llm_conformance import run_model_conformance


def test_live_conformance_skips_without_required_env_and_does_not_call_provider() -> (
    None
):
    def fail_factory(provider: str, *, model: str | None = None) -> object:
        raise AssertionError(f'provider should not be called: {provider}')

    report = run_model_conformance(
        ['gpt'],
        adapter_factory=fail_factory,
        configuration_checker=lambda _provider: (True, 'configured'),
        live_env_var='TEAAGENT_ACCEPT_LIVE_CONFORMANCE',
    )
    payload = report.as_dict()

    assert payload['ok']
    assert payload['skipped'] == 1
    assert payload['live_env_var'] == 'TEAAGENT_ACCEPT_LIVE_CONFORMANCE'
    assert not payload['live_enabled']
    assert 'gated' in payload['results'][0]['error']


def test_live_conformance_runs_when_required_env_is_set() -> None:
    with patch.dict(os.environ, {'TEAAGENT_ACCEPT_LIVE_CONFORMANCE': '1'}):
        report = run_model_conformance(
            ['gpt'],
            adapter_factory=lambda _provider, model=None: FakeAdapter(['ok']),
            configuration_checker=lambda _provider: (True, 'configured'),
            live_env_var='TEAAGENT_ACCEPT_LIVE_CONFORMANCE',
        )

    payload = report.as_dict()
    assert payload['ok']
    assert payload['passed'] == 1
    assert payload['live_enabled']
    assert payload['results'][0]['status'] == 'passed'


def test_cli_conformance_exposes_env_gate() -> None:
    output = io.StringIO()
    with redirect_stdout(output):
        exit_code = main(
            [
                'model',
                'conformance',
                '--provider',
                'gpt',
                '--live-env-var',
                'TEAAGENT_ACCEPT_LIVE_CONFORMANCE',
            ]
        )
    payload = json.loads(output.getvalue())

    assert exit_code == 0
    assert payload['ok']
    assert payload['skipped'] == 1
    assert not payload['live_enabled']

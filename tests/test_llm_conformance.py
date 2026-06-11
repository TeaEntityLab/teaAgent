from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from unittest.mock import patch

from conftest import FakeAdapter

from teaagent.cli import main
from teaagent.llm_conformance import run_model_conformance


class FailingAdapter:
    def complete(self, request: object) -> object:
        raise RuntimeError('boom')


def test_run_model_conformance_reports_pass_skip_and_fail() -> None:
    adapters = {'gpt': FakeAdapter(['ok']), 'claude': FailingAdapter()}

    def check(provider: str) -> tuple[bool, str]:
        if provider == 'gemini':
            return False, 'GEMINI_API_KEY is not set'
        return True, 'configured'

    def factory(provider: str, *, model: str | None = None) -> object:
        return adapters[provider]

    report = run_model_conformance(
        ['gpt', 'gemini', 'claude'],
        adapter_factory=factory,
        configuration_checker=check,
    )

    assert not report.ok
    assert report.passed == 1
    assert report.skipped == 1
    assert report.failed == 1
    payload = report.as_dict()
    assert payload['results'][0]['status'] == 'passed'
    assert payload['results'][1]['status'] == 'skipped'
    assert payload['results'][2]['status'] == 'failed'


def test_run_model_conformance_fails_unexpected_content() -> None:
    def factory(provider: str, *, model: str | None = None) -> object:
        return FakeAdapter(['not ok'])

    report = run_model_conformance(
        ['gpt'],
        adapter_factory=factory,
        configuration_checker=lambda provider: (True, 'configured'),
    )

    assert not report.ok
    assert report.failed == 1
    assert 'expected' in (report.results[0].error or '')


def test_cli_model_conformance_outputs_report() -> None:
    output = io.StringIO()

    with (
        patch('teaagent.cli.run_model_conformance') as run_model_conformance,
        redirect_stdout(output),
    ):
        run_model_conformance.return_value.ok = True
        run_model_conformance.return_value.as_dict.return_value = {
            'ok': True,
            'passed': 1,
            'failed': 0,
            'skipped': 0,
            'results': [{'provider': 'gpt', 'status': 'passed'}],
        }
        exit_code = main(['model', 'conformance', '--provider', 'gpt'])

    payload = json.loads(output.getvalue())
    assert exit_code == 0
    assert payload['ok']
    run_model_conformance.assert_called_once_with(
        ['gpt'],
        prompt='Reply with exactly: ok',
        expected_content='ok',
        max_tokens=32,
        model=None,
    )

from __future__ import annotations

# test-type: behavior
import io
import json
import socket
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from teaagent import MemoryCatalog, PermissionMode
from teaagent.cli import main
from teaagent.preflight import check_provider_connectivity, preflight
from test_support import can_bind_loopback


def test_preflight_marks_ambiguous_task_not_ready() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        report = preflight('improve stuff', root=tmp, provider='gpt')

        payload = report.to_dict()
        assert not payload['ready']
        assert payload['clarification']['needs_clarification']
        assert payload['routing'] is None
        assert payload['memories'] == []
        assert payload['tool_count'] > 0


def test_preflight_includes_routing_and_matching_memories(
    offline_provider_connectivity: None,
) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        MemoryCatalog(tmp).add('review this patch in the test suite for regressions')

        report = preflight(
            'review this patch for regressions in the test suite',
            root=tmp,
            provider='gpt',
            permission_mode=PermissionMode.WORKSPACE_WRITE,
            route=True,
        )
        payload = report.to_dict()

        if not can_bind_loopback():
            assert not payload['ready']
            return

        assert payload['ready']
        assert payload['routing']['category'] == 'review'
        # With complexity-based routing, "review this patch for regressions" routes to gpt-4o-mini (medium complexity)
        assert payload['model'] == 'gpt-4o-mini'
        assert payload['permission_mode'] == 'workspace-write'
        assert len(payload['memories']) == 1


def test_cli_agent_preflight_returns_needs_clarification_exit_code() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                ['agent', 'preflight', 'gpt', 'improve stuff', '--root', tmp]
            )

        payload = json.loads(output.getvalue())
        assert exit_code == 2
        assert not payload['ready']


def test_cli_agent_preflight_with_route_model_reports_routing(
    offline_provider_connectivity: None,
) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        output = io.StringIO()

        with redirect_stdout(output):
            exit_code = main(
                [
                    'agent',
                    'preflight',
                    'gpt',
                    'review this patch for regressions in the test suite',
                    '--route-model',
                    '--root',
                    tmp,
                ]
            )

        payload = json.loads(output.getvalue())
        if not can_bind_loopback():
            assert exit_code == 2
            assert not payload['ready']
            return

        assert exit_code == 0
        assert payload['routing']['category'] == 'review'
        # With complexity-based routing, "review this patch for regressions" routes to gpt-4o-mini (medium complexity)
        assert payload['model'] == 'gpt-4o-mini'


def test_preflight_detects_run_store_corruption() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        # Create a corrupt run file to trigger health detection
        runs_dir = Path(tmp) / '.teaagent' / 'runs'
        runs_dir.mkdir(parents=True, exist_ok=True)
        (runs_dir / 'corrupt.jsonl').write_text('garbage data\n', encoding='utf-8')

        report = preflight('test task', root=tmp, provider='gpt')
        payload = report.to_dict()

        # Preflight should report corruption in health failures
        assert not payload['health']['healthy']
        failures = payload['health'].get('failures', [])
        failure_text = '\n'.join(failures)
        assert 'corrupt' in failure_text.lower()


def test_check_provider_connectivity_dns_failure_and_no_network_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fail_resolution(*args: object, **kwargs: object) -> None:
        raise socket.gaierror(-2, 'Name or service not known')

    monkeypatch.setattr('teaagent.preflight.socket.getaddrinfo', _fail_resolution)
    ok, msg = check_provider_connectivity('gpt')
    assert ok is False
    assert 'could not be resolved' in msg

    def _must_not_resolve(*args: object, **kwargs: object) -> None:
        raise AssertionError('getaddrinfo must not run for a no-network provider')

    monkeypatch.setattr('teaagent.preflight.socket.getaddrinfo', _must_not_resolve)
    ok, _ = check_provider_connectivity('fake')
    assert ok is True

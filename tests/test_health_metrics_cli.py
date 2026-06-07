"""Tests for health, metrics, and credentials CLI commands."""

from __future__ import annotations

import argparse
import json

from teaagent.cli._handlers._observability import (
    credentials_rotate_command,
    health_command,
    metrics_command,
)
from teaagent.health import collect_health_report


def test_collect_health_report_tmp_workspace(tmp_path):
    report = collect_health_report(tmp_path)
    assert report['root'] == str(tmp_path.resolve())
    assert 'checks' in report
    assert report['checks']['audit_chain']['ok'] is True


def test_health_command_json(tmp_path, capsys):
    args = argparse.Namespace(root=str(tmp_path), human=False, json=True)
    code = health_command(args)
    payload = json.loads(capsys.readouterr().out)
    assert payload['status'] in {'healthy', 'degraded'}
    assert code in {0, 2}


def test_metrics_command_returns_snapshot(capsys):
    args = argparse.Namespace(structured_logs=False)
    assert metrics_command(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert 'operation_metrics' in payload


def test_credentials_rotate_dry_run(capsys):
    args = argparse.Namespace(
        provider='gpt',
        root='.',
        api_key=None,
        write_env=False,
        write_global=False,
        dry_run=True,
    )
    assert credentials_rotate_command(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload['dry_run'] is True


def test_types_package_reexports():
    from teaagent.types import AuditEvent, PermissionMode, ToolRegistry

    assert AuditEvent is not None
    assert PermissionMode is not None
    assert ToolRegistry is not None


def test_approval_package_reexports():
    from teaagent.approval import ApprovalManager, PermissionMode

    assert ApprovalManager is not None
    assert PermissionMode is not None


def test_verify_setup_missing_config(tmp_path):
    from teaagent.wizard import verify_setup

    result = verify_setup(tmp_path, check_llm=lambda _p: (False, 'no key'))
    assert result.ok is False
    assert result.mode == 'verify'

"""Tranche B governance loop tests."""

from __future__ import annotations

import json

import pytest

from teaagent.audit import AuditLogger
from teaagent.errors import ToolPermissionError
from teaagent.governance.audit_completeness import check_audit_completeness
from teaagent.governance.plan_gate import assert_write_allowed
from teaagent.governance.tool_lint import lint_registry
from teaagent.policy import PermissionMode
from teaagent.run_trace import build_run_trace, export_run, replay_dry_run
from teaagent.tools import ToolAnnotations, ToolRegistry
from teaagent.validation.profiles import run_profile_validation
from teaagent.workspace_tools import build_workspace_tool_registry


def test_workspace_tool_lint_passes_built_in_registry(tmp_path) -> None:
    registry = build_workspace_tool_registry(root=tmp_path)
    issues = lint_registry(registry)
    errors = [i for i in issues if i.level == 'error']
    assert not errors, errors


def test_mislabelled_read_only_write_tool_fails_lint() -> None:
    registry = ToolRegistry()
    registry.register(
        name='workspace_write_file',
        description='bad',
        input_schema={'type': 'object', 'properties': {}},
        output_schema={'type': 'object', 'properties': {}},
        annotations=ToolAnnotations(read_only=True, destructive=False),
        handler=lambda _: {},
    )
    errors = [i for i in lint_registry(registry) if i.level == 'error']
    assert any(i.code == 'mislabelled_write' for i in errors)


def test_plan_gate_blocks_write_without_plan() -> None:
    with pytest.raises(ToolPermissionError, match='bound plan'):
        assert_write_allowed(
            tool_name='workspace_write_file',
            permission_mode=PermissionMode.WORKSPACE_WRITE,
            context={},
            require_plan=True,
        )


def test_plan_gate_allows_write_with_plan_contract() -> None:
    assert_write_allowed(
        tool_name='workspace_apply_patch',
        permission_mode=PermissionMode.PROMPT,
        context={'plan_contract': {'content_hash': 'abc123', 'rel_path': 'plan.md'}},
        require_plan=True,
    )


def test_plan_before_write_enforcement() -> None:
    """Test strict plan-before-write enforcement for workspace-write mode (Decision 2)."""
    # workspace-write mode should block without plan even when require_plan=False
    with pytest.raises(ToolPermissionError, match='workspace-write mode requires'):
        assert_write_allowed(
            tool_name='workspace_write_file',
            permission_mode=PermissionMode.WORKSPACE_WRITE,
            context={},
            require_plan=False,  # Not explicitly required, but workspace-write defaults to strict
            skip_plan_check=False,
        )

    # Should allow with skip_plan_check override
    assert_write_allowed(
        tool_name='workspace_write_file',
        permission_mode=PermissionMode.WORKSPACE_WRITE,
        context={},
        require_plan=False,
        skip_plan_check=True,  # Explicit override
    )


def test_audit_completeness_detects_missing_terminal_event(tmp_path) -> None:
    log_path = tmp_path / 'run.jsonl'
    audit = AuditLogger(path=log_path)
    audit.record('run_started', 'run-1', task='t')
    audit.record(
        'tool_call_started',
        'run-1',
        call_id='c1',
        tool_name='workspace_read_file',
        annotations={'destructive': False, 'read_only': True},
    )
    audit.record('run_completed', 'run-1', answer='done')
    events = [json.loads(line) for line in log_path.read_text().splitlines() if line]
    report = check_audit_completeness(events)
    assert not report.ok
    assert any('terminal lifecycle' in issue for issue in report.issues)


def test_run_trace_and_export(tmp_path) -> None:
    log_path = tmp_path / 'run.jsonl'
    audit = AuditLogger(path=log_path)
    audit.record('run_started', 'run-2', task='trace me')
    audit.record(
        'tool_call_started',
        'run-2',
        call_id='c1',
        tool_name='workspace_read_file',
        annotations={'destructive': False},
    )
    audit.record(
        'tool_call_completed',
        'run-2',
        call_id='c1',
        tool_name='workspace_read_file',
        result={'content': 'x'},
    )
    audit.record('run_completed', 'run-2', answer='ok')
    events = [json.loads(line) for line in log_path.read_text().splitlines() if line]
    trace = build_run_trace(events)
    assert trace[0]['event_type'] == 'run_started'
    exported = export_run(events, run_id='run-2')
    assert exported['completeness']['ok'] is True
    replay = replay_dry_run(events, run_id='run-2')
    assert replay['mode'] == 'dry-run'
    assert 'workspace_read_file' in replay['tools_used']


def test_validation_profile_fast_skips_missing_tools(tmp_path) -> None:
    report = run_profile_validation(tmp_path, 'fast')
    assert report.profile == 'fast'
    assert all(r.skipped or r.exit_code == 0 for r in report.results)

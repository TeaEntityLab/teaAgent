"""Harness self-test entry points for release gates."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from teaagent.errors import ToolPermissionError
from teaagent.governance.audit_completeness import check_audit_completeness
from teaagent.governance.tool_lint import lint_registry
from teaagent.policy import ApprovalPolicy, PermissionMode
from teaagent.workspace_tools import build_workspace_tool_registry


def run_security_selftest(root: str | Path = '.') -> dict[str, Any]:
    """Run governance security checks without invoking pytest."""
    workspace = Path(root).resolve()
    registry = build_workspace_tool_registry(workspace)
    lint_issues = lint_registry(registry)
    lint_errors = [issue for issue in lint_issues if issue.level == 'error']

    # Check for read_only tools with write-like keywords in descriptions
    read_only_write_keyword_warnings = [
        issue for issue in lint_issues
        if issue.level == 'warning' and issue.code == 'read_only_with_write_keywords'
    ]

    permission_ok = True
    permission_detail = 'read-only blocks destructive write'
    try:
        ApprovalPolicy(permission_mode=PermissionMode.READ_ONLY).assert_allowed(
            tool_name='workspace_write_file',
            call_id='selftest',
            destructive=True,
        )
        permission_ok = False
        permission_detail = 'read-only mode did not block destructive write'
    except ToolPermissionError:
        pass

    sample_events = [
        {
            'event_id': '1',
            'run_id': 'selftest',
            'event_type': 'run_started',
            'payload': {'task': 'selftest'},
        },
        {
            'event_id': '2',
            'run_id': 'selftest',
            'event_type': 'run_completed',
            'payload': {'answer': 'ok'},
        },
    ]
    audit_report = check_audit_completeness(sample_events)

    ok = not lint_errors and permission_ok and audit_report.ok
    return {
        'ok': ok,
        'tool_lint': {
            'ok': not lint_errors,
            'error_count': len(lint_errors),
            'warning_count': sum(1 for i in lint_issues if i.level == 'warning'),
        },
        'read_only_write_keyword_check': {
            'ok': len(read_only_write_keyword_warnings) == 0,
            'warnings': len(read_only_write_keyword_warnings),
            'details': [f"{issue.tool_name}: {issue.message}" for issue in read_only_write_keyword_warnings],
        },
        'permission_smoke': {'ok': permission_ok, 'detail': permission_detail},
        'audit_completeness_smoke': {
            'ok': audit_report.ok,
            'issues': audit_report.issues,
        },
    }

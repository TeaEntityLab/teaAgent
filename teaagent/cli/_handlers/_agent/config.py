from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Literal, Optional, cast

from teaagent.approval import parse_permission_mode
from teaagent.cli._formatting import format_error_block
from teaagent.cli._output import print_json
from teaagent.cli.execution import AgentExecutionFactory
from teaagent.run_store import RunStore
from teaagent.runner import RunResult
from teaagent.types import PermissionMode


def _derive_policy_source(routing_reason: str) -> str:
    """Derive the policy source from a routing reason string."""
    lower = routing_reason.lower()
    if 'explicit' in lower:
        return 'explicit_override'
    if 'complexity' in lower:
        return 'complexity'
    return 'category'


def _parse_approve_scoped(scoped_approvals: list[str]) -> frozenset[str]:
    """Parse --approve-scoped arguments into a frozenset of digests.

    Each argument is expected in the format TOOL:SHA256, where SHA256 is
    a 64-character lowercase hex string.

    Args:
        scoped_approvals: List of 'TOOL:SHA256' strings from --approve-scoped.

    Returns:
        frozenset of digest strings.

    Raises:
        SystemExit: If format is invalid.
    """
    digests = []
    for arg in scoped_approvals:
        if ':' not in arg:
            sys.exit(f'--approve-scoped expects TOOL:SHA256 format, got: {arg}')
        parts = arg.split(':', 1)
        if len(parts) != 2:
            sys.exit(f'--approve-scoped expects TOOL:SHA256 format, got: {arg}')
        _tool_name, digest = parts
        if len(digest) != 64 or not all(c in '0123456789abcdef' for c in digest):
            sys.exit(f'--approve-scoped expects TOOL:SHA256 (64 hex chars), got: {arg}')
        digests.append(digest)
    return frozenset(digests)


def _resolve_selected_skills(args: argparse.Namespace) -> Optional[frozenset[str]]:
    """Resolve selected skills from args, returning frozenset or None.

    Returns:
        - Empty frozenset if no_auto_skills is set
        - Frozenset of skill names if provided
        - None otherwise (to trigger auto-selection)
    """
    if getattr(args, 'no_auto_skills', False):
        return frozenset()
    names = [
        str(item).strip()
        for item in (getattr(args, 'skill', None) or [])
        if str(item).strip()
    ]
    if names:
        return frozenset(names)
    return None


def _resolve_auto_compact(args: argparse.Namespace) -> bool:
    if getattr(args, 'auto_compact', None) is not None:
        return bool(args.auto_compact)
    from teaagent.ergonomics.workspace_defaults import load_workspace_defaults

    defaults = load_workspace_defaults(getattr(args, 'root', '.'))
    return bool(defaults.get('auto_compact_on_resume', True))


def warn_if_approve_call_id_used(args: argparse.Namespace) -> bool:
    """Emit a clear deprecation notice when --approve-call-id is used.

    Call-id preapproval was removed (G-P2-2): a call id is predictable, so it is
    weaker authority than a cryptographic payload digest. The flag is retained
    only to surface this guidance instead of silently denying the call. Returns
    whether the flag was present.
    """
    call_ids = getattr(args, 'approve_call_id', None)
    if not call_ids:
        return False
    print(
        format_error_block(
            'Deprecation',
            '--approve-call-id no longer grants approval and is ignored. '
            'Call-id preapproval was removed for security (call ids are '
            'predictable). Use --approve-scoped TOOL:SHA256 (payload-digest '
            'preapproval) instead.',
            category='DEPRECATED',
        ),
        file=sys.stderr,
    )
    return True


def _save_git_sandbox_consent(root: str | Path, value: str) -> None:
    root_path = Path(root).resolve()
    tea_dir = root_path / '.teaagent'
    tea_dir.mkdir(parents=True, exist_ok=True)
    json_path = tea_dir / 'config.json'
    config = {}
    if json_path.is_file():
        try:
            config = json.loads(json_path.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, ValueError, OSError) as exc:
            print(f'Warning: Failed to read configuration: {exc}', file=sys.stderr)
            config = {}
    else:
        config = {}
    config['git_sandbox_consent'] = value
    try:
        json_path.write_text(
            json.dumps(config, sort_keys=True, indent=2), encoding='utf-8'
        )
    except Exception as exc:
        print(f'Warning: Failed to save configuration: {exc}', file=sys.stderr)


def _resolve_validation_profile(args: argparse.Namespace) -> Optional[str]:
    if getattr(args, 'no_validate', False):
        return None
    if getattr(args, 'validate', False):
        return getattr(args, 'validation_profile', None) or 'standard'
    return None


def _require_plan_gate(
    args: argparse.Namespace, plan_contract: Optional[Any]
) -> Optional[int]:
    # Strict plan-before-write enforcement for workspace-write mode (user-approved)
    mode = parse_permission_mode(args.permission_mode)
    if mode == PermissionMode.READ_ONLY:
        return None

    # Check if strict plan enforcement is enabled (default for workspace-write)
    require_plan = getattr(args, 'require_plan', False)
    skip_plan_check = getattr(args, 'skip_plan_check', False)

    # If user explicitly skips plan check, allow it (with warning logged elsewhere)
    if skip_plan_check:
        return None

    # For workspace-write mode, enforce plan requirement by default
    if mode == PermissionMode.WORKSPACE_WRITE and not require_plan:
        # Auto-enable require_plan for workspace-write mode unless explicitly skipped
        require_plan = True

    if not require_plan:
        return None

    if plan_contract is not None:
        return None
    # U-P1-2: route the plan-gate denial through format_error_block on stderr
    # (with a hint), not raw JSON on stdout. See
    # tests/test_cli_run_error_formatting.py::test_plan_gate_error_uses_format_error_block.
    print(
        format_error_block(
            'Error',
            'Plan-before-write enforcement requires a bound plan. Run `teaagent plan` then '
            '`teaagent run --from-plan .teaagent/plans/<file>.md --require-plan`. '
            'Use --skip-plan-check to override (not recommended).',
            category='PLAN_GATE',
        ),
        file=sys.stderr,
    )
    return 2


def _run_post_validation(
    args: argparse.Namespace,
    *,
    result: RunResult,
    store: RunStore,
    profile: str,
) -> int:
    from teaagent.validation.profiles import run_profile_validation

    report = run_profile_validation(
        str(args.root),
        cast(Literal['fast', 'standard', 'strict'], profile),
    )
    path = store.run_path(result.run_id)
    if path.is_file():
        audit = AgentExecutionFactory.create_audit_logger_from_path(path)
        audit.record('validation_started', result.run_id, profile=profile)
        audit.record(
            'validation_finished',
            result.run_id,
            passed=report.passed,
            report=report.to_dict(),
        )
    payload = {'validation': report.to_dict(), 'run_id': result.run_id}
    print_json(payload)
    return 0 if report.passed else 1

"""Plan-before-write enforcement for governed coding runs."""

from __future__ import annotations

from typing import Any

from teaagent.errors import ToolPermissionError
from teaagent.policy import PermissionMode

WRITE_TOOLS = frozenset(
    {
        'workspace_write_file',
        'workspace_apply_patch',
        'workspace_edit_at_hash',
    }
)

_PLAN_MODES = frozenset(
    {
        PermissionMode.WORKSPACE_WRITE,
        PermissionMode.PROMPT,
        PermissionMode.ALLOW,
        PermissionMode.DANGER_FULL_ACCESS,
    }
)


def _has_plan_contract(context: dict[str, Any]) -> bool:
    plan = context.get('plan_contract')
    if not isinstance(plan, dict):
        return False
    content_hash = plan.get('content_hash')
    return isinstance(content_hash, str) and bool(content_hash.strip())


def assert_write_allowed(
    *,
    tool_name: str,
    permission_mode: PermissionMode,
    context: dict[str, Any],
    require_plan: bool,
    skip_plan_check: bool = False,
) -> None:
    """Block workspace writes when plan binding is required but missing.

    Strict enforcement by default for workspace-write mode (Decision 2).
    Use --skip-plan-check to override for power users who understand the risks.
    """
    if tool_name not in WRITE_TOOLS:
        return
    if permission_mode not in _PLAN_MODES:
        return
    if skip_plan_check:
        # Explicit override - user acknowledged risk
        return
    if not require_plan and permission_mode != PermissionMode.WORKSPACE_WRITE:
        # require_plan=False is respected for non-workspace-write modes
        return
    # For workspace-write mode, enforce plan-by-default (strict)
    if permission_mode == PermissionMode.WORKSPACE_WRITE and not require_plan:
        raise ToolPermissionError(
            'workspace-write mode requires a bound plan by default for safety. '
            'Run `teaagent plan` then `teaagent run --from-plan <path> --require-plan`, '
            'or use --skip-plan-check to override (not recommended).'
        )
    if require_plan and not _has_plan_contract(context):
        raise ToolPermissionError(
            'Write tools require a bound plan. Run `teaagent plan` then '
            '`teaagent run --from-plan <path> --require-plan`, or drop --require-plan.'
        )

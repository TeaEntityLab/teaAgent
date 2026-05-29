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
) -> None:
    """Block workspace writes when plan binding is required but missing."""
    if tool_name not in WRITE_TOOLS:
        return
    if permission_mode not in _PLAN_MODES:
        return
    if not require_plan:
        return
    if _has_plan_contract(context):
        return
    raise ToolPermissionError(
        'Write tools require a bound plan. Run `teaagent plan` then '
        '`teaagent run --from-plan <path> --require-plan`, or drop --require-plan.'
    )

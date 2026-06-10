"""H4 governance shadow wiring (WDA-002 / WDA-003).

Connects the policy engine and RBAC modules to production entry paths in
shadow mode by default. RBAC may be switched to enforce via
``TEAAGENT_H4_RBAC_MODE=enforce``.
"""

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from teaagent.policy_engine import PolicyEffect, PolicyEngine, PolicyStore, PolicyType


class H4GovernanceMode(str, Enum):
    SHADOW = 'shadow'
    ENFORCE = 'enforce'


def _mode_from_env(var_name: str, *, default: H4GovernanceMode) -> H4GovernanceMode:
    raw = os.environ.get(var_name, default.value).strip().lower()
    if raw in {m.value for m in H4GovernanceMode}:
        return H4GovernanceMode(raw)
    return default


def policy_governance_mode() -> H4GovernanceMode:
    return _mode_from_env('TEAAGENT_H4_POLICY_MODE', default=H4GovernanceMode.SHADOW)


def rbac_governance_mode() -> H4GovernanceMode:
    return _mode_from_env('TEAAGENT_H4_RBAC_MODE', default=H4GovernanceMode.SHADOW)


def _policy_engine_for_root(root: str | Path) -> PolicyEngine:
    return PolicyEngine(PolicyStore(Path(root).resolve()))


def record_h4_shadow_event(
    audit: Any,
    run_id: str,
    *,
    surface: str,
    mode: H4GovernanceMode,
    allowed: bool,
    reason: str,
    context: dict[str, Any],
    enforced: bool,
    details: Optional[list[dict[str, Any]]] = None,
) -> None:
    audit.record(
        'h4_governance_shadow',
        run_id,
        surface=surface,
        mode=mode.value,
        allowed=allowed,
        enforced=enforced,
        reason=reason,
        context=context,
        details=details or [],
    )


def evaluate_approval_policy_shadow(
    *,
    workspace_root: str | Path | None,
    audit: Any,
    run_id: str,
    tool_name: str,
    arguments: dict[str, Any],
    destructive: bool,
    call_id: str,
) -> bool:
    """Evaluate approval policies and record a shadow receipt. Never blocks."""
    if workspace_root is None:
        return True

    mode = policy_governance_mode()
    context = {
        'action': 'approve_tool',
        'tool_name': tool_name,
        'call_id': call_id,
        'destructive': destructive,
        'arguments': arguments,
    }
    engine = _policy_engine_for_root(workspace_root)
    effect, details = engine.evaluate_with_explanation(
        context,
        policy_type=PolicyType.APPROVAL,
    )
    allowed = effect == PolicyEffect.ALLOW
    denying = next(
        (d for d in details if d.get('applies') and d.get('effect') == 'deny'),
        None,
    )
    reason = (
        f'Policy {denying["policy_id"]} would deny'
        if denying
        else 'Policy evaluation would allow'
    )
    record_h4_shadow_event(
        audit,
        run_id,
        surface='approval',
        mode=mode,
        allowed=allowed,
        reason=reason,
        context=context,
        enforced=False,
        details=details,
    )
    return True


def check_subagent_launch_rbac(
    *,
    workspace_root: str | Path,
    audit: Any | None,
    parent_run_id: str,
    assignee: str,
    def_name: str,
    depth: int,
) -> tuple[bool, str]:
    """RBAC gate for subagent launch. Shadow by default; enforce when configured."""
    from teaagent.rbac import Permission, RBACSystem

    mode = rbac_governance_mode()
    context = {
        'action': 'launch_subagent',
        'subagent': def_name,
        'depth': depth,
        'parent_run_id': parent_run_id,
    }
    rbac = RBACSystem(workspace_root)
    allowed, reason = rbac.check_action_permission(
        assignee,
        'start_workflow',
        context,
    )
    if audit is not None:
        record_h4_shadow_event(
            audit,
            parent_run_id,
            surface='subagent_launch',
            mode=mode,
            allowed=allowed,
            reason=reason,
            context={
                **context,
                'assignee': assignee,
                'permission': Permission.START_WORKFLOW.value,
            },
            enforced=mode == H4GovernanceMode.ENFORCE and not allowed,
            details=[],
        )
    if mode == H4GovernanceMode.ENFORCE and not allowed:
        return False, reason
    return True, reason

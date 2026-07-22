"""H4 rollback dry-run evidence (ADR-0031 criterion 5).

Runs the scratch-workspace rollback checks required before H4 promotion: forcing
policy/RBAC modes back to ``shadow`` must let denied actions proceed while still
recording receipts with ``mode=shadow`` and ``enforced=false``. The dry-run does
not change workspace configuration or flip defaults; it uses process-local env
vars and restores them before returning.
"""

from __future__ import annotations

import os
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Optional

from teaagent.governance.h4_integration import (
    check_subagent_launch_rbac,
    evaluate_approval_policy_shadow,
)
from teaagent.governance.policy_engine import (
    PolicyCondition,
    PolicyEffect,
    PolicyPrecedence,
    PolicyStore,
    PolicyType,
)
from teaagent.governance.rbac import Permission, RBACSystem


class _RecordingAudit:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    def record(self, event_type: str, run_id: str, **payload: Any) -> None:
        self.calls.append((event_type, run_id, payload))


@dataclass(frozen=True)
class H4RollbackSurfaceResult:
    """Rollback dry-run result for one H4 surface."""

    surface: str
    proceeded: bool
    mode: str
    allowed: bool
    enforced: bool
    reason: str

    @property
    def ok(self) -> bool:
        return self.proceeded and self.mode == 'shadow' and not self.enforced

    def to_dict(self) -> dict[str, Any]:
        return {
            'surface': self.surface,
            'ok': self.ok,
            'proceeded': self.proceeded,
            'mode': self.mode,
            'allowed': self.allowed,
            'enforced': self.enforced,
            'reason': self.reason,
        }


@dataclass(frozen=True)
class H4RollbackDryRunReport:
    """ADR-0031 criterion-5 rollback dry-run evidence."""

    policy: H4RollbackSurfaceResult
    rbac: H4RollbackSurfaceResult

    @property
    def ok(self) -> bool:
        return self.policy.ok and self.rbac.ok

    def to_dict(self) -> dict[str, Any]:
        return {
            'criterion': 'ADR-0031 criterion 5 — rollback to shadow mode',
            'ok': self.ok,
            'policy': self.policy.to_dict(),
            'rbac': self.rbac.to_dict(),
            'note': (
                'Evidence only: uses a scratch workspace and process-local env vars; '
                'does not change stored configuration, defaults, or H4 promotion status.'
            ),
        }


@contextmanager
def _temporary_env(name: str, value: str) -> Iterator[None]:
    old: Optional[str] = os.environ.get(name)
    os.environ[name] = value
    try:
        yield
    finally:
        if old is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = old


def _save_deny_all_approval_policy(root: Path) -> None:
    from teaagent.governance.policy_engine import Policy

    PolicyStore(root).save(
        Policy(
            policy_id='h4-rollback-deny-write',
            policy_type=PolicyType.APPROVAL,
            effect=PolicyEffect.DENY,
            conditions=[PolicyCondition('tool_name', 'equals', 'write_file')],
            precedence=PolicyPrecedence.HIGH,
            description='rollback dry-run deny write_file',
        )
    )


def _extract_payload(
    audit: _RecordingAudit, *, expected_surface: str
) -> dict[str, Any]:
    assert audit.calls, 'expected h4_governance_shadow receipt'
    event_type, _run_id, payload = audit.calls[-1]
    assert event_type == 'h4_governance_shadow'
    assert payload['surface'] == expected_surface
    return payload


def _run_policy_shadow_rollback(root: Path) -> H4RollbackSurfaceResult:
    _save_deny_all_approval_policy(root)
    audit = _RecordingAudit()
    with _temporary_env('TEAAGENT_H4_POLICY_MODE', 'shadow'):
        proceeded = evaluate_approval_policy_shadow(
            workspace_root=root,
            audit=audit,
            run_id='h4-rollback-policy',
            tool_name='write_file',
            arguments={'path': 'denied.txt'},
            destructive=True,
            call_id='rollback-call',
        )
    payload = _extract_payload(audit, expected_surface='approval')
    return H4RollbackSurfaceResult(
        surface='approval',
        proceeded=proceeded,
        mode=str(payload['mode']),
        allowed=bool(payload['allowed']),
        enforced=bool(payload['enforced']),
        reason=str(payload['reason']),
    )


def _run_rbac_shadow_rollback(root: Path) -> H4RollbackSurfaceResult:
    rbac = RBACSystem(root)
    viewer = rbac.create_role('viewer', [Permission.READ_FILE])
    rbac.assign_role(viewer.role_id, 'operator')
    audit = _RecordingAudit()
    with _temporary_env('TEAAGENT_H4_RBAC_MODE', 'shadow'):
        proceeded, reason = check_subagent_launch_rbac(
            workspace_root=root,
            audit=audit,
            parent_run_id='h4-rollback-rbac',
            assignee='operator',
            def_name='researcher',
            depth=1,
        )
    payload = _extract_payload(audit, expected_surface='subagent_launch')
    return H4RollbackSurfaceResult(
        surface='subagent_launch',
        proceeded=proceeded,
        mode=str(payload['mode']),
        allowed=bool(payload['allowed']),
        enforced=bool(payload['enforced']),
        reason=reason,
    )


def run_h4_rollback_dry_run() -> H4RollbackDryRunReport:
    """Run the scratch rollback proof for policy and RBAC H4 surfaces."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        return H4RollbackDryRunReport(
            policy=_run_policy_shadow_rollback(root),
            rbac=_run_rbac_shadow_rollback(root),
        )

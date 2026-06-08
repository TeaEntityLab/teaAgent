"""Plan-before-write enforcement for governed coding runs.

Includes intent-drift pre-write check (CPP-P0-008): validates that
write targets stay within the plan contract's approved file targets
before the tool call is dispatched.

Also includes ReviewGate (SCL-P1-006): a review gate packet that must be
presented before high-impact actions like skill install and memory promote.
"""

from __future__ import annotations

import json
import uuid as uuid_mod
from dataclasses import dataclass, field
from pathlib import Path, PurePath
from typing import Any, Literal
from uuid import uuid4

from teaagent.audit import secure_audit_dir, secure_audit_file, utc_now
from teaagent.errors import ToolPermissionError
from teaagent.policy import PermissionMode
from teaagent.storage import atomic_write_text

WRITE_TOOLS = frozenset(
    {
        'workspace_write_file',
        'workspace_apply_patch',
        'workspace_edit_at_hash',
    }
)

_PATH_ARGUMENT_KEYS = ('path', 'file_path', 'target_path', 'file')

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


def _extract_write_path(arguments: dict[str, Any] | None) -> str | None:
    """Extract the file path from a tool call's arguments."""
    if not arguments or not isinstance(arguments, dict):
        return None
    for key in _PATH_ARGUMENT_KEYS:
        raw = arguments.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return None


def assert_write_scope(  # noqa: C901
    *,
    tool_name: str,
    arguments: dict[str, Any] | None,
    plan_contract: Any,
) -> str | None:
    """Check that a write tool target is within the plan's approved file scope.

    Returns None if the write is within scope or no plan contract is bound.
    Returns a drift warning message if the target is outside the approved scope.

    This is the intent-drift pre-write check (CPP-P0-008): new files or
    broad edits outside the accepted scope require an explicit gate packet
    or plan update before proceeding.
    """
    if tool_name not in WRITE_TOOLS:
        return None
    if plan_contract is None:
        return None
    # plan_contract may be a PlanContract object or a dict from context
    if isinstance(plan_contract, dict):
        file_targets = plan_contract.get('file_targets', [])
    elif hasattr(plan_contract, 'file_targets'):
        file_targets = list(plan_contract.file_targets)
    else:
        return None

    if not file_targets:
        # No specific targets means all paths are allowed
        return None

    file_path = _extract_write_path(arguments)
    if file_path is None:
        return None

    # Normalize to POSIX and reject traversal
    norm_path = PurePath(file_path).as_posix()
    parts = norm_path.split('/')
    if '..' in parts:
        return (
            f"Path traversal detected in write target '{file_path}'. "
            f'Write target must be within the plan scope.'
        )

    for target in file_targets:
        norm_target = PurePath(target).as_posix()
        if norm_path == norm_target:
            return None
        if norm_path.startswith(norm_target + '/'):
            return None

    rel_path = ''
    if hasattr(plan_contract, 'rel_path'):
        rel_path = str(plan_contract.rel_path)
    elif isinstance(plan_contract, dict):
        rel_path = plan_contract.get('rel_path', '')

    return (
        f"Intent drift: tool '{tool_name}' targeting '{file_path}' is outside "
        f'the approved plan scope. Plan file targets: {sorted(file_targets)}. '
        f'Plan: {rel_path}. Update the plan or use an explicit gate packet.'
    )


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


# ---------------------------------------------------------------------------
# Review Gate (SCL-P1-006)
# ---------------------------------------------------------------------------


@dataclass
class ReviewGate:
    """Review gate packet for high-impact actions (skill install, memory promote).

    Gate packets are persisted to ``.teaagent/gates/`` and must be approved
    (``decision: 'approved'``) before the target action proceeds.
    """

    gate_id: str
    target_type: Literal['skill_install', 'memory_promote']
    target_name: str
    risk_reason: str
    diff_summary: str = ''
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    cost_summary: dict[str, float] = field(default_factory=dict)
    review_findings: list[dict[str, Any]] = field(default_factory=list)
    rollback_path: str = ''
    decision: str = 'pending'
    approver: str = ''
    created_at: str = ''

    def to_dict(self) -> dict[str, Any]:
        return {
            'gate_id': self.gate_id,
            'target_type': self.target_type,
            'target_name': self.target_name,
            'risk_reason': self.risk_reason,
            'diff_summary': self.diff_summary,
            'tool_calls': list(self.tool_calls),
            'cost_summary': dict(self.cost_summary),
            'review_findings': list(self.review_findings),
            'rollback_path': self.rollback_path,
            'decision': self.decision,
            'approver': self.approver,
            'created_at': self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReviewGate:
        return cls(
            gate_id=data.get('gate_id', ''),
            target_type=data.get('target_type', 'skill_install'),
            target_name=data.get('target_name', ''),
            risk_reason=data.get('risk_reason', ''),
            diff_summary=data.get('diff_summary', ''),
            tool_calls=list(data.get('tool_calls', []) or []),
            cost_summary=dict(data.get('cost_summary', {}) or {}),
            review_findings=list(data.get('review_findings', []) or []),
            rollback_path=data.get('rollback_path', ''),
            decision=data.get('decision', 'pending'),
            approver=data.get('approver', ''),
            created_at=data.get('created_at', ''),
        )


def require_review_gate(
    target_type: Literal['skill_install', 'memory_promote'],
    target_name: str,
    risk_reason: str,
    workspace_root: str | Path = '.',
) -> ReviewGate:
    """Build a review gate packet and persist it to ``.teaagent/gates/``.

    Returns the created gate with ``decision='pending'`` so the caller can
    display it and decide whether to proceed.
    """
    gate = ReviewGate(
        gate_id=str(uuid4()),
        target_type=target_type,
        target_name=target_name,
        risk_reason=risk_reason,
        decision='pending',
        created_at=utc_now(),
    )
    _save_gate(workspace_root, gate)
    return gate


def _validate_gate_id(gate_id: str) -> str:
    """Validate *gate_id* is a well-formed UUID and return it."""
    if not isinstance(gate_id, str) or not gate_id.strip():
        raise ValueError(f'gate_id must be a non-empty UUID string, got {gate_id!r}')
    try:
        uuid_mod.UUID(gate_id.strip())
    except (ValueError, AttributeError) as exc:
        raise ValueError(f'gate_id must be a valid UUID, got {gate_id!r}') from exc
    return gate_id.strip()


def load_gate(
    gate_id: str,
    workspace_root: str | Path = '.',
) -> ReviewGate:
    """Load a review gate by ID from ``.teaagent/gates/``."""
    safe_id = _validate_gate_id(gate_id)
    root = Path(workspace_root).resolve()
    gate_dir = (root / '.teaagent' / 'gates').resolve()
    candidate = (gate_dir / f'{safe_id}.json').resolve()
    if not candidate.is_file():
        raise FileNotFoundError(f'gate not found: {gate_id}')
    data = json.loads(candidate.read_text(encoding='utf-8'))
    return ReviewGate.from_dict(data)


def approve_gate(
    gate_id: str,
    approver: str,
    workspace_root: str | Path = '.',
) -> ReviewGate:
    """Mark a pending gate as approved by *approver*.

    Returns the updated gate.  Raises ``ValueError`` if the gate does not
    exist or is not in ``'pending'`` state.
    """
    gate = load_gate(gate_id, workspace_root=workspace_root)
    if gate.decision != 'pending':
        raise ValueError(f'gate {gate_id} is not pending (current: {gate.decision})')
    if not approver.strip():
        raise ValueError('approver must be a non-empty string')
    gate = ReviewGate(
        gate_id=gate.gate_id,
        target_type=gate.target_type,
        target_name=gate.target_name,
        risk_reason=gate.risk_reason,
        diff_summary=gate.diff_summary,
        tool_calls=list(gate.tool_calls),
        cost_summary=dict(gate.cost_summary),
        review_findings=list(gate.review_findings),
        rollback_path=gate.rollback_path,
        decision='approved',
        approver=approver.strip(),
        created_at=gate.created_at,
    )
    _save_gate(workspace_root, gate)
    return gate


def _gates_dir(workspace_root: str | Path) -> Path:
    root = Path(workspace_root).resolve()
    d = root / '.teaagent' / 'gates'
    d.mkdir(parents=True, exist_ok=True)
    secure_audit_dir(d)
    return d


def _save_gate(workspace_root: str | Path, gate: ReviewGate) -> None:
    path = _gates_dir(workspace_root) / f'{gate.gate_id}.json'
    content = json.dumps(gate.to_dict(), indent=2)
    atomic_write_text(path, content)
    secure_audit_file(path)

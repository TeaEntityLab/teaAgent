"""Operator cockpit state model for TUI and CLI surfaces.

This module provides CockpitState, a unified state model for the operator
cockpit that displays blocked approvals, harness health, budget status, and
recoverable state across all surfaces.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class HealthStatus(str, Enum):
    """Health status for harness and components."""

    HEALTHY = 'healthy'
    DEGRADED = 'degraded'
    UNHEALTHY = 'unhealthy'
    UNKNOWN = 'unknown'


class BudgetStatus(str, Enum):
    """Budget status for cost tracking."""

    OK = 'ok'
    WARNING = 'warning'
    EXCEEDED = 'exceeded'
    UNKNOWN = 'unknown'


@dataclass
class ApprovalState:
    """State of pending/blocked approvals."""

    pending_count: int = 0
    blocked_count: int = 0
    auto_approved_count: int = 0
    denied_count: int = 0


@dataclass
class HarnessHealth:
    """Health status of the harness and its components."""

    overall: HealthStatus = HealthStatus.UNKNOWN
    components: dict[str, HealthStatus] = field(default_factory=dict)
    last_check_time: Optional[float] = None
    errors: list[str] = field(default_factory=list)


@dataclass
class BudgetState:
    """Budget state for cost tracking.

    ``cost_state`` labels whether the displayed cost is actual, estimated,
    unavailable (no cost data), or unlimited (no cap). The UI must never
    imply actual cost when only an estimate or no value is available.
    """

    status: BudgetStatus = BudgetStatus.UNKNOWN
    spent_cents: float = 0.0
    limit_cents: Optional[float] = None
    remaining_cents: Optional[float] = None
    session_cost_cents: float = 0.0
    cost_state: str = 'unavailable'  # actual | estimated | unavailable | unlimited


@dataclass
class RecoverableState:
    """State of recoverable operations (undo, resume, etc.)."""

    has_undo_journal: bool = False
    has_checkpoint: bool = False
    has_suspended_session: bool = False
    last_run_id: Optional[str] = None
    last_run_recoverable: bool = False


@dataclass
class CockpitState:
    """Unified operator cockpit state.

    This model aggregates state from multiple sources:
    - Approval system (pending/blocked approvals)
    - Harness health (component status)
    - Budget tracking (cost limits and usage)
    - Recoverable state (undo, checkpoints, suspended sessions)
    """

    approvals: ApprovalState = field(default_factory=ApprovalState)
    harness_health: HarnessHealth = field(default_factory=HarnessHealth)
    budget: BudgetState = field(default_factory=BudgetState)
    recoverable: RecoverableState = field(default_factory=RecoverableState)
    context_health: Optional[dict[str, Any]] = None

    # P0-D-003: Active workspace root and approval scope for surface visibility.
    workspace_root: str = ''
    approval_scope: str = (
        ''  # e.g. 'prompt', 'workspace-write (scoped: src/**)', 'allow'
    )

    last_updated: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'approvals': {
                'pending_count': self.approvals.pending_count,
                'blocked_count': self.approvals.blocked_count,
                'auto_approved_count': self.approvals.auto_approved_count,
                'denied_count': self.approvals.denied_count,
            },
            'harness_health': {
                'overall': self.harness_health.overall.value,
                'components': {
                    k: v.value for k, v in self.harness_health.components.items()
                },
                'last_check_time': self.harness_health.last_check_time,
                'errors': self.harness_health.errors,
            },
            'budget': {
                'status': self.budget.status.value,
                'spent_cents': self.budget.spent_cents,
                'limit_cents': self.budget.limit_cents,
                'remaining_cents': self.budget.remaining_cents,
                'session_cost_cents': self.budget.session_cost_cents,
                'cost_state': self.budget.cost_state,
            },
            'recoverable': {
                'has_undo_journal': self.recoverable.has_undo_journal,
                'has_checkpoint': self.recoverable.has_checkpoint,
                'has_suspended_session': self.recoverable.has_suspended_session,
                'last_run_id': self.recoverable.last_run_id,
                'last_run_recoverable': self.recoverable.last_run_recoverable,
            },
            'context_health': self.context_health,
            'workspace_root': self.workspace_root,
            'approval_scope': self.approval_scope,
            'last_updated': self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'CockpitState':
        """Create from dictionary."""
        approvals_data = data.get('approvals', {})
        health_data = data.get('harness_health', {})
        budget_data = data.get('budget', {})
        recoverable_data = data.get('recoverable', {})

        return cls(
            approvals=ApprovalState(
                pending_count=approvals_data.get('pending_count', 0),
                blocked_count=approvals_data.get('blocked_count', 0),
                auto_approved_count=approvals_data.get('auto_approved_count', 0),
                denied_count=approvals_data.get('denied_count', 0),
            ),
            harness_health=HarnessHealth(
                overall=HealthStatus(health_data.get('overall', 'unknown')),
                components={
                    k: HealthStatus(v)
                    for k, v in health_data.get('components', {}).items()
                },
                last_check_time=health_data.get('last_check_time'),
                errors=health_data.get('errors', []),
            ),
            budget=BudgetState(
                status=BudgetStatus(budget_data.get('status', 'unknown')),
                spent_cents=budget_data.get('spent_cents', 0.0),
                limit_cents=budget_data.get('limit_cents'),
                remaining_cents=budget_data.get('remaining_cents'),
                session_cost_cents=budget_data.get('session_cost_cents', 0.0),
                cost_state=budget_data.get('cost_state', 'unavailable'),
            ),
            recoverable=RecoverableState(
                has_undo_journal=recoverable_data.get('has_undo_journal', False),
                has_checkpoint=recoverable_data.get('has_checkpoint', False),
                has_suspended_session=recoverable_data.get(
                    'has_suspended_session', False
                ),
                last_run_id=recoverable_data.get('last_run_id'),
                last_run_recoverable=recoverable_data.get(
                    'last_run_recoverable', False
                ),
            ),
            context_health=data.get('context_health'),
            workspace_root=data.get('workspace_root', ''),
            approval_scope=data.get('approval_scope', ''),
            last_updated=data.get('last_updated'),
        )

    def update_timestamp(self) -> None:
        """Update the last_updated timestamp to current time."""
        import time

        self.last_updated = time.time()


# ── Stale Workspace Assessment ──────────────────────────────────────────────


@dataclass
class StaleWorkspaceReport:
    """Read-only assessment of workspace staleness indicators.

    This report is computed without modifying any files.  It surfaces
    git dirty state, branch divergence, pending memory approvals, and
    unreviewed skill candidates so the operator can decide whether the
    workspace needs attention before a session.
    """

    dirty_git: bool = False
    branch: str = ''
    diverged_from_main: bool = False
    commits_behind: int = 0
    commits_ahead: int = 0
    pending_approvals: int = 0
    candidate_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            'dirty_git': self.dirty_git,
            'branch': self.branch,
            'diverged_from_main': self.diverged_from_main,
            'commits_behind': self.commits_behind,
            'commits_ahead': self.commits_ahead,
            'pending_approvals': self.pending_approvals,
            'candidate_count': self.candidate_count,
        }


def _run_git(args: list[str], cwd: Path | str) -> subprocess.CompletedProcess | None:
    """Run a git command, returning None on any failure (no git, non-zero exit)."""
    try:
        result = subprocess.run(
            ['git', *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return None
        return result
    except (FileNotFoundError, subprocess.SubprocessError):
        return None


def _count_quarantine_lines(root: Path) -> int:
    """Count lines in the memory quarantine JSONL file."""
    quarantine_path = root / '.teaagent' / 'memory-quarantine.jsonl'
    if not quarantine_path.is_file():
        return 0
    try:
        text = quarantine_path.read_text(encoding='utf-8')
        return len([line for line in text.splitlines() if line.strip()])
    except OSError:
        return 0


def _count_unreviewed_candidates(root: Path) -> int:
    """Count skill candidates whose status is *not* installed."""
    candidates_dir = root / '.teaagent' / 'skill-candidates'
    if not candidates_dir.is_dir():
        return 0
    count = 0
    for meta_path in sorted(candidates_dir.glob('*/candidate.json')):
        try:
            import json

            payload = json.loads(meta_path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            continue
        status = (payload or {}).get('status', '')
        if status != 'installed':
            count += 1
    return count


# ── Control Cockpit State ────────────────────────────────────────────────────


@dataclass
class ControlCockpitState:
    """Aggregated control cockpit state for TUI surface.

    Summarises spec/goal state, model routing, memory, review,
    skill diagnostics, approval state, and cost tracking into a
    single render-able struct.
    """

    spec: dict | None = None
    goal: dict | None = None
    model_route: dict | None = None
    memory: dict = field(
        default_factory=lambda: {'total_entries': 0, 'last_entry_summary': ''}
    )
    review: dict | None = None
    skill: dict = field(
        default_factory=lambda: {
            'loaded_count': 0,
            'shadowed_count': 0,
            'candidate_count': 0,
            'governance_status': {},
        }
    )
    approval: dict = field(
        default_factory=lambda: {
            'pending_count': 0,
            'blocked_count': 0,
            'mode': 'prompt',
        }
    )
    cost: dict = field(
        default_factory=lambda: {
            'spent_cents': 0.0,
            'limit_cents': None,
            'state': 'unavailable',
        }
    )
    last_updated: Optional[float] = None


def build_control_cockpit(
    root: Path | str,
    *,
    permission_mode: str = 'prompt',
    cost_cents: float = 0.0,
    cost_limit_cents: Optional[int] = None,
    cost_state: str = 'unavailable',
) -> ControlCockpitState:
    """Build a ControlCockpitState from workspace data sources.

    Parameters
    ----------
    root:
        Workspace root directory.
    permission_mode:
        Current permission mode (used for approval state).
    cost_cents:
        Spent cost in cents for the current session.
    cost_limit_cents:
        Cost limit in cents (or ``None`` for unlimited).
    cost_state:
        Cost state label: ``actual``, ``estimated``, ``unavailable``, or ``unlimited``.
    """
    import time

    root_path = Path(root).resolve()

    cockpit = ControlCockpitState(last_updated=time.time())

    # ── spec / goal ──
    try:
        from teaagent.goal_record import GoalStore

        store = GoalStore(root_path)
        goals = store.list()
        if goals:
            latest = goals[0]
            cockpit.goal = {
                'goal_id': latest.goal_id,
                'objective': latest.objective,
                'status': latest.status,
                'task_ids': latest.task_ids,
                'run_ids': latest.run_ids,
                'cost_cents': latest.cost_cents,
                'blockers': latest.blockers,
                'next_gate': latest.next_gate,
            }
            cockpit.spec = {
                'spec_id': latest.spec_id or '',
                'spec_hash': latest.spec_hash or '',
                'spec_exemption': latest.spec_exemption.to_dict()
                if latest.spec_exemption
                else None,
            }
    except Exception:
        pass

    # ── model route ──
    cockpit.model_route = None

    # ── memory ──
    try:
        from teaagent.memory import MemoryCatalog

        catalog = MemoryCatalog(root_path, readonly=True)
        entries = catalog.list(limit=5)
        cockpit.memory = {
            'total_entries': len(entries),
            'last_entry_summary': entries[0].content[:80] if entries else '',
        }
    except Exception:
        cockpit.memory = {'total_entries': 0, 'last_entry_summary': ''}

    # ── review ──
    try:
        if cockpit.goal:
            review_ids = cockpit.goal.get('review_ids', [])
            cockpit.review = {
                'review_ids_count': len(review_ids)
                if isinstance(review_ids, list)
                else 0,
                'latest_review_status': 'unknown',
            }
    except Exception:
        cockpit.review = None

    # ── skill diagnostics ──
    try:
        from teaagent.skill_loader import get_skill_diagnostics

        diag = get_skill_diagnostics(root_path)
        cockpit.skill = {
            'loaded_count': len(diag.get('loaded_skills', [])),
            'shadowed_count': len(diag.get('shadowed_skills', [])),
            'candidate_count': diag.get('candidate_count', 0),
            'governance_status': diag.get('governance_status', {}),
        }
    except Exception:
        cockpit.skill = {
            'loaded_count': 0,
            'shadowed_count': 0,
            'candidate_count': 0,
            'governance_status': {},
        }

    # ── approval ──
    pending = _count_quarantine_lines(root_path)
    cockpit.approval = {
        'pending_count': pending,
        'blocked_count': 0,
        'mode': permission_mode,
    }

    # ── cost ──
    cockpit.cost = {
        'spent_cents': cost_cents,
        'limit_cents': cost_limit_cents,
        'state': cost_state,
    }

    # ── context health (CTX-001) ──
    try:
        from teaagent.context_health import compute_context_health

        ch = compute_context_health(workspace_root=str(root_path))
        cockpit.skill.setdefault('context_health', ch.to_dict())
    except Exception:
        pass

    # ── extension activation explain (EXT-001) ──
    try:
        from teaagent.extension_explain import explain_extension_activation

        ext = explain_extension_activation(workspace_root=str(root_path))
        cockpit.skill.setdefault('extension_activation', ext.to_dict())
    except Exception:
        pass

    return cockpit


def assess_stale_workspace(root: str | Path) -> StaleWorkspaceReport:
    """Inspect the workspace for staleness signals without modifying files.

    Checks performed (all read-only):
      - Git dirty state via ``git status --porcelain``
      - Current branch via ``git rev-parse --abbrev-ref HEAD``
      - Branch divergence via ``git rev-list --left-right --count origin/main...HEAD``
      - Pending approvals via memory quarantine line count
      - Unreviewed skill candidates via ``.teaagent/skill-candidates/``

    Gracefully handles missing git, non-git directories, and missing metadata
    paths by returning defaults without raising.
    """
    root_path = Path(root).resolve()
    report = StaleWorkspaceReport()

    # -- git dirty state --
    porcelain = _run_git(['status', '--porcelain'], cwd=root_path)
    if porcelain is not None:
        report.dirty_git = bool(porcelain.stdout.strip())

    # -- branch name --
    branch_result = _run_git(['rev-parse', '--abbrev-ref', 'HEAD'], cwd=root_path)
    if branch_result is not None:
        report.branch = branch_result.stdout.strip()

    # -- divergence from origin/main --
    div = _run_git(
        ['rev-list', '--left-right', '--count', 'origin/main...HEAD'],
        cwd=root_path,
    )
    if div is not None:
        parts = div.stdout.strip().split()
        if len(parts) == 2:
            try:
                report.commits_behind = int(parts[0])
                report.commits_ahead = int(parts[1])
                report.diverged_from_main = (
                    report.commits_behind > 0 or report.commits_ahead > 0
                )
            except (ValueError, TypeError):
                pass

    # -- pending approvals (quarantine entries) --
    report.pending_approvals = _count_quarantine_lines(root_path)

    # -- unreviewed skill candidates --
    report.candidate_count = _count_unreviewed_candidates(root_path)

    return report

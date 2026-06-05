"""Goal record persistence — durable goal lifecycle across multiple runs.

A GoalRecord ties together spec, task list, runs, memory, review, and blockers
into a single persisted object. It is stored as a JSON file under
``.teaagent/goals/`` and follows the same patterns as ``PlanStorage`` and
``RunStore`` (secure directories, atomic writes).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from teaagent.audit import AuditLogger, secure_audit_dir, secure_audit_file, utc_now
from teaagent.spec_exemption import SpecExemptionReceipt
from teaagent.storage import atomic_write_text

logger = logging.getLogger(__name__)

# Valid goal statuses in the state machine.
VALID_STATUSES = frozenset(
    {'proposed', 'active', 'completed', 'failed', 'blocked', 'abandoned'}
)


@dataclass
class GoalRecord:
    """Persisted goal record tying together spec, tasks, runs, and review state.

    The state machine is:
      proposed → active → completed / failed / blocked / abandoned
    """

    goal_id: str  # UUID
    objective: str
    status: str = 'proposed'  # proposed | active | completed | failed | blocked | abandoned
    spec_id: str = ''
    spec_hash: str = ''
    task_ids: list[str] = field(default_factory=list)
    run_ids: list[str] = field(default_factory=list)
    cost_cents: float = 0.0
    memory_ids: list[str] = field(default_factory=list)
    review_ids: list[str] = field(default_factory=list)
    human_gate_ids: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    next_gate: str = ''
    spec_exemption: Optional[SpecExemptionReceipt] = None
    created_at: str = ''
    updated_at: str = ''

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict for JSON persistence."""
        return {
            'goal_id': self.goal_id,
            'objective': self.objective,
            'status': self.status,
            'spec_id': self.spec_id,
            'spec_hash': self.spec_hash,
            'task_ids': list(self.task_ids),
            'run_ids': list(self.run_ids),
            'cost_cents': self.cost_cents,
            'memory_ids': list(self.memory_ids),
            'review_ids': list(self.review_ids),
            'human_gate_ids': list(self.human_gate_ids),
            'blockers': list(self.blockers),
            'next_gate': self.next_gate,
            'spec_exemption': (self.spec_exemption.to_dict() if self.spec_exemption else None),
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GoalRecord:
        """Deserialize from a plain dict."""
        spec_exemption = None
        raw_exemption = data.get('spec_exemption')
        if isinstance(raw_exemption, dict):
            spec_exemption = SpecExemptionReceipt.from_dict(raw_exemption)
        return cls(
            goal_id=data.get('goal_id', ''),
            objective=data.get('objective', ''),
            status=data.get('status', 'proposed'),
            spec_id=data.get('spec_id', ''),
            spec_hash=data.get('spec_hash', ''),
            task_ids=list(data.get('task_ids', []) or []),
            run_ids=list(data.get('run_ids', []) or []),
            cost_cents=float(data.get('cost_cents', 0.0)),
            memory_ids=list(data.get('memory_ids', []) or []),
            review_ids=list(data.get('review_ids', []) or []),
            human_gate_ids=list(data.get('human_gate_ids', []) or []),
            blockers=list(data.get('blockers', []) or []),
            next_gate=data.get('next_gate', ''),
            spec_exemption=spec_exemption,
            created_at=data.get('created_at', ''),
            updated_at=data.get('updated_at', ''),
        )


class GoalStore:
    """Persistent storage for GoalRecords under ``.teaagent/goals/``.

    Each goal is stored as a single JSON file named ``{goal_id}.json``.
    The directory and files follow TeaAgent security conventions (700 / 600).

    Usage::

        store = GoalStore('.')
        goal = GoalRecord(
            goal_id='g-001', objective='Refactor auth',
            status='proposed',
        )
        store.save(goal)
        loaded = store.load('g-001')
        all_goals = store.list()
    """

    def __init__(self, root: str | Path = '.') -> None:
        self._root = Path(root).resolve() / '.teaagent' / 'goals'
        self._root.mkdir(parents=True, exist_ok=True)
        secure_audit_dir(self._root)

    def _goal_path(self, goal_id: str) -> Path:
        return self._root / f'{goal_id}.json'

    def save(self, goal: GoalRecord) -> None:
        """Persist a GoalRecord atomically.

        If ``created_at`` / ``updated_at`` are empty they are filled with the
        current UTC time.
        """
        now = utc_now()
        if not goal.created_at:
            goal.created_at = now
        goal.updated_at = now

        if goal.status not in VALID_STATUSES:
            raise ValueError(
                f"Invalid goal status '{goal.status}'. Must be one of: "
                f"{', '.join(sorted(VALID_STATUSES))}"
            )

        path = self._goal_path(goal.goal_id)
        data = goal.to_dict()
        atomic_write_text(path, json.dumps(data, indent=2))
        secure_audit_file(path)
        logger.info(f'Saved goal {goal.goal_id} (status={goal.status}) to {path}')

    def load(self, goal_id: str) -> GoalRecord:
        """Load a single GoalRecord by id.

        Raises:
            FileNotFoundError: If the goal does not exist.
        """
        path = self._goal_path(goal_id)
        if not path.is_file():
            raise FileNotFoundError(f'Goal {goal_id} not found at {path}')
        data = json.loads(path.read_text(encoding='utf-8'))
        goal = GoalRecord.from_dict(data)
        logger.info(f'Loaded goal {goal_id} (status={goal.status}) from {path}')
        return goal

    def list(self) -> list[GoalRecord]:
        """List all goals ordered by updated_at descending."""
        goals: list[GoalRecord] = []
        for path in sorted(
            self._root.glob('*.json'),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        ):
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
                goals.append(GoalRecord.from_dict(data))
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning(f'Skipping corrupt goal file {path}: {exc}')
        return goals

    def delete(self, goal_id: str) -> None:
        """Delete a goal from storage.

        Raises:
            FileNotFoundError: If the goal does not exist.
        """
        path = self._goal_path(goal_id)
        if not path.is_file():
            raise FileNotFoundError(f'Goal {goal_id} not found at {path}')
        path.unlink()
        logger.info(f'Deleted goal {goal_id} from {path}')

    def goal_audit_logger(self, goal_id: str) -> AuditLogger:
        """Create an AuditLogger for this goal's lifecycle events.

        Writes to ``.teaagent/goals/{goal_id}_audit.jsonl``.
        """
        path = self._root / f'{goal_id}_audit.jsonl'
        return AuditLogger(path=path)

    def set_status(
        self,
        goal_id: str,
        new_status: str,
        *,
        waivers: list[Any] | None = None,  # type: ignore[valid-type]
    ) -> GoalRecord:
        """Transition a goal to *new_status* with review gate enforcement.

        When transitioning TO ``'completed'``, this method enforces the
        SCL-P1-005 review gate: high-risk goals require a synthesis review
        (``review_ids``) or a documented waiver.

        Parameters
        ----------
        goal_id:
            The goal to transition.
        new_status:
            Target status (must be in ``VALID_STATUSES``).
        waivers:
            Optional list of ``WaiverRecord`` objects to check.

        Returns:
            The updated ``GoalRecord`` (already persisted).

        Raises:
            FileNotFoundError:
                If the goal does not exist.
            ValueError:
                If ``new_status`` is invalid, or if the goal is a
                high-risk goal without a review or waiver when
                transitioning to ``'completed'``.
        """
        goal = self.load(goal_id)

        if new_status == 'completed':
            from teaagent.governance.review_gate import (
                requires_review_before_close,
            )

            blocked, reason = requires_review_before_close(
                goal, waivers=waivers
            )
            if blocked:
                raise ValueError(
                    f"Cannot close high-risk goal '{goal_id}': {reason}"
                )

        goal.status = new_status
        self.save(goal)
        return goal

    def record_goal_event(
        self, goal_id: str, event_type: str, **payload: Any
    ) -> None:
        """Record a goal lifecycle event (goal_set, goal_updated, etc.).

        This appends a single audit event to the goal's audit log and
        automatically updates the ``updated_at`` timestamp on the GoalRecord.
        """
        audit = self.goal_audit_logger(goal_id)
        audit.record(event_type, goal_id, **payload)
        try:
            goal = self.load(goal_id)
            goal.updated_at = utc_now()
            self.save(goal)
        except FileNotFoundError:
            pass  # Goal not yet saved — caller should save it first

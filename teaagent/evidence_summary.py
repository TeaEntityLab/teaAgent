"""Run evidence summary for success, failure, cancellation, and pending approval.

Extracts a lightweight ``RunEvidenceSummary`` from a run's audit trail:
changed files, commands run, tests executed, approvals, costs, and
rollback availability.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from teaagent.run_store import RunStore


@dataclass
class RunEvidenceSummary:
    """Aggregated evidence summary constructed from run audit events.

    Fields:
        run_id: Run identifier.
        status: One of ``success``, ``failure``, ``cancelled``, ``pending_approval``, or ``unknown``.
        changed_files: Files modified during the run (from ``workspace_write_file`` events).
        commands_run: Shell mutation commands with tool name and arguments.
        tests_executed: Count of tool calls whose name contains ``test`` or ``pytest``.
        approvals: Approval events with timestamp, scope, and decision.
        total_cost_cents: Estimated or actual accumulated cost in cents.
        cost_state: One of ``actual``, ``estimated``, ``unavailable``, ``unlimited``.
        budget_cap_cents: Budget cap in cents, or ``None`` for unlimited.
        rollback_available: Whether a git sandbox or undo journal exists for this run.
        started_at: ISO 8601 timestamp of ``run_started``.
        finished_at: ISO 8601 timestamp of the terminal event (or ``None`` if still running).
    """

    run_id: str
    status: str = 'unknown'
    changed_files: list[str] = field(default_factory=list)
    commands_run: list[dict[str, Any]] = field(default_factory=list)
    tests_executed: int = 0
    approvals: list[dict[str, Any]] = field(default_factory=list)
    total_cost_cents: int = 0
    cost_state: str = 'unavailable'
    budget_cap_cents: int | None = None
    rollback_available: bool = False
    started_at: str = ''
    finished_at: str | None = None
    evidence_categories: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the summary to a JSON-safe dictionary."""
        return {
            'run_id': self.run_id,
            'status': self.status,
            'changed_files': self.changed_files,
            'commands_run': self.commands_run,
            'tests_executed': self.tests_executed,
            'approvals': self.approvals,
            'total_cost_cents': self.total_cost_cents,
            'cost_state': self.cost_state,
            'budget_cap_cents': self.budget_cap_cents,
            'rollback_available': self.rollback_available,
            'started_at': self.started_at,
            'finished_at': self.finished_at,
            'evidence_categories': self.evidence_categories,
        }


_TEST_TOOL_PATTERNS = ('test', 'pytest')


def _tool_matches_test(tool_name: str) -> bool:
    """Return True when *tool_name* names a test-related tool."""
    lowered = tool_name.lower()
    return any(pattern in lowered for pattern in _TEST_TOOL_PATTERNS)


def _extract_timestamp(event: dict[str, Any]) -> str:
    """Pick the best timestamp from an audit event.

    Prefers ``timestamp``, falls back to ``created_at``, then the empty string.
    """
    return str(event.get('timestamp', event.get('created_at', '')))


def _safe_payload(event: dict[str, Any]) -> dict[str, Any]:
    """Return the event payload as a dict, guarding against non-dict values."""
    payload = event.get('payload')
    if isinstance(payload, dict):
        return payload
    return {}


def _tool_arguments(payload: dict[str, Any]) -> dict[str, Any]:
    """Return tool arguments from either the ``arguments`` or ``input`` sub-keys."""
    args = payload.get('arguments', payload.get('input'))
    if isinstance(args, dict):
        return args
    return {}


def _process_event_lifecycle(
    event_type: str,
    payload: dict[str, Any],
    ts: str,
    *,
    started_at: str,
    finished_at: str | None,
    status: str,
    total_cost_cents: int,
) -> tuple[str, str | None, str, int]:
    """Update lifecycle state from a single audit event."""
    if event_type == 'run_started':
        return ts, finished_at, 'running', total_cost_cents
    if event_type == 'run_completed':
        cost = payload.get('cost_cents', 0)
        if isinstance(cost, (int, float)):
            total_cost_cents += int(cost)
        return started_at, ts, 'success', total_cost_cents
    if event_type == 'run_failed':
        cost = payload.get('cost_cents', 0)
        if isinstance(cost, (int, float)):
            total_cost_cents += int(cost)
        return started_at, ts, 'failure', total_cost_cents
    if event_type == 'run_paused':
        return started_at, ts, 'pending_approval', total_cost_cents
    if event_type == 'run_cancelled':
        return started_at, ts, 'cancelled', total_cost_cents
    return started_at, finished_at, status, total_cost_cents


def _process_event_file_shell(
    event_type: str,
    payload: dict[str, Any],
    ts: str,
    *,
    changed_files: list[str],
    commands_run: list[dict[str, Any]],
    tests_executed: int,
) -> None:
    """Update file-change and shell-mutation accumulators from a tool event."""
    if event_type not in ('tool_call_started', 'tool_call_completed'):
        return
    tool_name = str(payload.get('tool_name', ''))

    if tool_name == 'workspace_write_file':
        args = _tool_arguments(payload)
        path = args.get('path', args.get('file_path', ''))
        if path and isinstance(path, str) and path not in changed_files:
            changed_files.append(path)

    if tool_name == 'workspace_run_shell_mutate':
        args = _tool_arguments(payload)
        command = args.get('command', args.get('cmd', ''))
        if command and isinstance(command, str):
            commands_run.append(
                {'tool_name': tool_name, 'command': command, 'timestamp': ts}
            )


def _process_event_approvals(
    event_type: str,
    payload: dict[str, Any],
    ts: str,
    approvals: list[dict[str, Any]],
) -> None:
    """Update approvals list from a single event (deduplicate by call_id)."""
    if event_type == 'tool_call_pending_approval':
        call_id = str(payload.get('call_id', ''))
        existing = next((a for a in approvals if a['call_id'] == call_id), None)
        if existing is None:
            approvals.append(
                {
                    'call_id': call_id,
                    'tool_name': str(payload.get('tool_name', '')),
                    'decision': 'pending',
                    'timestamp': ts,
                    'scope': str(payload.get('scope', '')),
                }
            )
    elif event_type == 'approval_granted':
        _update_approval_decision(approvals, payload, ts, 'granted')
    elif event_type == 'approval_denied':
        _update_approval_decision(approvals, payload, ts, 'denied')


def _update_approval_decision(
    approvals: list[dict[str, Any]],
    payload: dict[str, Any],
    ts: str,
    decision: str,
) -> None:
    """Find or create an approval entry and set its decision."""
    call_id = str(payload.get('call_id', ''))
    existing = next((a for a in approvals if a['call_id'] == call_id), None)
    if existing is not None:
        existing['decision'] = decision
        existing['timestamp'] = ts
    else:
        approvals.append(
            {
                'call_id': call_id,
                'tool_name': str(payload.get('tool_name', '')),
                'decision': decision,
                'timestamp': ts,
                'scope': str(payload.get('scope', '')),
            }
        )


def _process_event_cost(
    event_type: str,
    payload: dict[str, Any],
    total_cost_cents: int,
) -> int:
    """Accumulate estimated cost from a tool_call event."""
    if event_type != 'tool_call':
        return total_cost_cents
    cost = payload.get('estimated_cost_cents', 0)
    if isinstance(cost, (int, float)):
        return total_cost_cents + int(cost)
    return total_cost_cents


def _process_event_evidence(
    event_type: str,
    payload: dict[str, Any],
    evidence_categories: dict[str, int],
) -> None:
    """Update evidence category counters from a single event."""
    if event_type == 'test_run':
        test_status = str(payload.get('status', ''))
        if test_status == 'passed':
            evidence_categories['verified'] += 1
        elif test_status == 'failed':
            evidence_categories['known_failure'] += 1
        elif test_status == 'skipped':
            evidence_categories['not_tested'] += 1
    elif event_type in ('run_failed', 'tool_error', 'command_failed'):
        evidence_categories['known_failure'] += 1
    elif event_type in ('tool_call_started', 'tool_call_completed'):
        tool_name = str(payload.get('tool_name', ''))
        if tool_name == 'workspace_write_file':
            evidence_categories['claimed'] += 1


def summarize_run_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Extract summary fields from a run's audit event list.

    Returns a dict with the intermediate keys consumed by
    ``build_evidence_summary``:
      - ``status``
      - ``changed_files``
      - ``commands_run``
      - ``tests_executed``
      - ``approvals``
      - ``total_cost_cents``
      - ``started_at``
      - ``finished_at``
    """
    changed_files: list[str] = []
    commands_run: list[dict[str, Any]] = []
    tests_executed: int = 0
    approvals: list[dict[str, Any]] = []
    total_cost_cents: int = 0
    started_at: str = ''
    finished_at: str | None = None
    status: str = 'unknown'
    evidence_categories: dict[str, int] = {
        'verified': 0,
        'claimed': 0,
        'not_tested': 0,
        'known_failure': 0,
    }

    for event in events:
        event_type = str(event.get('event_type', ''))
        payload = _safe_payload(event)
        ts = _extract_timestamp(event)

        started_at, finished_at, status, total_cost_cents = _process_event_lifecycle(
            event_type,
            payload,
            ts,
            started_at=started_at,
            finished_at=finished_at,
            status=status,
            total_cost_cents=total_cost_cents,
        )

        _process_event_file_shell(
            event_type,
            payload,
            ts,
            changed_files=changed_files,
            commands_run=commands_run,
            tests_executed=tests_executed,
        )

        if event_type in (
            'tool_call_started',
            'tool_call_completed',
        ) and _tool_matches_test(str(payload.get('tool_name', ''))):
            tests_executed += 1

        _process_event_approvals(event_type, payload, ts, approvals)

        total_cost_cents = _process_event_cost(event_type, payload, total_cost_cents)

        _process_event_evidence(event_type, payload, evidence_categories)

    if status == 'running':
        finished_at = None

    return {
        'status': status,
        'changed_files': changed_files,
        'commands_run': commands_run,
        'tests_executed': tests_executed,
        'approvals': approvals,
        'total_cost_cents': total_cost_cents,
        'started_at': started_at,
        'finished_at': finished_at,
        'evidence_categories': evidence_categories,
    }


def build_evidence_summary(
    run_store: RunStore,
    run_id: str,
    root: str | Path,
    *,
    budget_cap_cents: int | None = None,
) -> RunEvidenceSummary:
    """Build a ``RunEvidenceSummary`` from a run's stored audit events.

    Reads events via *run_store*, extracts structured fields, and checks
    rollback availability by looking for an undo journal or active git
    sandbox under *root*.

    *budget_cap_cents* sets the budget cap for cost_state derivation;
    pass ``None`` when the cap is unlimited.
    """
    try:
        events = run_store.show_run(run_id)
    except FileNotFoundError:
        return RunEvidenceSummary(run_id=run_id, status='unknown')

    summary = summarize_run_events(events)

    from teaagent.cost_state import derive_cost_state

    provider_reported = any(
        isinstance(event.get('payload'), dict)
        and event['payload'].get('actual_cost_cents') is not None
        for event in events
        if event.get('event_type')
        in {'run_completed', 'iteration_completed', 'llm_usage'}
    )
    cost_state = derive_cost_state(
        cost_cents=float(summary.get('total_cost_cents', 0)),
        budget_cap_cents=budget_cap_cents,
        provider_reported=provider_reported,
    )

    # ── rollback availability ─────────────────────────────────────────
    root_path = Path(root).resolve()
    rollback_available = False

    try:
        undo_path = run_store.undo_path(run_id)
        rollback_available = undo_path.is_file()
    except RuntimeError:
        pass

    if not rollback_available:
        try:
            from teaagent.sandbox import GitBranchSandbox

            git_sandbox = GitBranchSandbox(str(root_path), run_id=run_id)
            rollback_available = git_sandbox.is_available()
        except Exception:
            rollback_available = False

    return RunEvidenceSummary(
        run_id=run_id,
        status=summary['status'],
        changed_files=summary['changed_files'],
        commands_run=summary['commands_run'],
        tests_executed=summary['tests_executed'],
        approvals=summary['approvals'],
        total_cost_cents=summary['total_cost_cents'],
        cost_state=cost_state,
        budget_cap_cents=budget_cap_cents,
        rollback_available=rollback_available,
        started_at=summary['started_at'],
        finished_at=summary['finished_at'],
        evidence_categories=summary['evidence_categories'],
    )

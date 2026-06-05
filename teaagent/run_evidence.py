"""Run evidence bundle extraction from audit trails.

This module provides functions to extract structured evidence from a run's
audit trail, including commands_run, tests, approvals, and known_gaps.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from teaagent.asset_provenance import ProvenanceRecord
from teaagent.proof_of_use import ProofOfUseBundle, build_proof_of_use
from teaagent.run_store import RunStore


@dataclass
class CommandEvidence:
    """Evidence of a command executed during a run."""

    command: str
    tool_name: str
    exit_code: Optional[int] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    timestamp: Optional[float] = None


@dataclass
class TestEvidence:
    """Evidence of a test run during a run."""

    test_name: str
    test_file: str
    status: str  # 'passed', 'failed', 'skipped'
    duration_ms: Optional[float] = None
    error_message: Optional[str] = None
    timestamp: Optional[float] = None


@dataclass
class ApprovalEvidence:
    """Evidence of an approval during a run.

    ``authority_type`` records the mechanism that granted the approval:
    jit_prompt, preset_grant, scoped_approval, multi_sig, preapproved,
    or permission_mode. ``approved_by`` captures the specific authority
    identity (e.g. user, agent_id, automated rule name).
    """

    call_id: str
    tool_name: str
    approved: bool
    auto_approved: bool = False
    denied: bool = False
    timestamp: Optional[float] = None
    authority_type: str = ''  # jit_prompt | preset_grant | scoped_approval | multi_sig | preapproved | permission_mode
    approved_by: str = ''  # human identity, agent_id, rule name
    scope_path: str = ''  # file path or glob scope this approval applies to


@dataclass
class ModelRouteEvidence:
    """Evidence of a model routing decision during a run.

    Records the full routing decision: what was requested, what was
    resolved, the role assigned, the reason for the decision, the policy
    source, and cost estimates.
    """

    requested_provider: str
    requested_model: str
    resolved_provider: str
    resolved_model: str
    role: str
    routing_reason: str
    policy_source: str
    estimated_cost_cents: float = 0.0
    actual_cost_cents: float = 0.0
    fallback_used: bool = False
    timestamp: Optional[float] = None


@dataclass
class KnownGap:
    """A known gap or limitation identified during a run."""

    category: str
    description: str
    severity: str  # 'low', 'medium', 'high'
    auto_derived: bool = True
    timestamp: Optional[float] = None


@dataclass
class SkillActivationRecord:
    """DSK-P1-002: Record of a skill activation during a run.

    Captures which skill was activated, why, from where, and an optional
    link to the output artifact produced by the skill.
    """

    skill_name: str
    activation_cause: str  # 'explicit', 'auto', 'context', 'session'
    source_path: str
    activated_at: str  # ISO 8601 timestamp
    output_artifact_link: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'skill_name': self.skill_name,
            'activation_cause': self.activation_cause,
            'source_path': self.source_path,
            'activated_at': self.activated_at,
            'output_artifact_link': self.output_artifact_link,
        }


@dataclass
class RunEvidenceBundle:
    """Complete evidence bundle for a run."""

    run_id: str
    commands_run: list[CommandEvidence] = field(default_factory=list)
    tests: list[TestEvidence] = field(default_factory=list)
    approvals: list[ApprovalEvidence] = field(default_factory=list)
    routes: list[ModelRouteEvidence] = field(default_factory=list)
    known_gaps: list[KnownGap] = field(default_factory=list)
    workspace_root: str = ''
    goal_id: str = ''
    proof_of_use: Optional[ProofOfUseBundle] = None
    provenance: list[ProvenanceRecord] = field(default_factory=list)
    skill_activations: list[SkillActivationRecord] = field(default_factory=list)
    undo_available: bool = False
    undo_mechanism: Optional[str] = None  # 'journal' | 'checkpoint' | None
    undo_outcome: Optional[str] = None  # 'reverted' | 'partial' | 'failed' | None

    # ── cost tracking (P0-B) ──
    cost_cents: float = 0.0
    cost_state: str = 'unavailable'
    budget_cap_cents: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'run_id': self.run_id,
            'commands_run': [
                {
                    'command': cmd.command,
                    'tool_name': cmd.tool_name,
                    'exit_code': cmd.exit_code,
                    'stdout': cmd.stdout,
                    'stderr': cmd.stderr,
                    'timestamp': cmd.timestamp,
                }
                for cmd in self.commands_run
            ],
            'tests': [
                {
                    'test_name': test.test_name,
                    'test_file': test.test_file,
                    'status': test.status,
                    'duration_ms': test.duration_ms,
                    'error_message': test.error_message,
                    'timestamp': test.timestamp,
                }
                for test in self.tests
            ],
            'approvals': [
                {
                    'call_id': app.call_id,
                    'tool_name': app.tool_name,
                    'approved': app.approved,
                    'auto_approved': app.auto_approved,
                    'denied': app.denied,
                    'timestamp': app.timestamp,
                    'authority_type': app.authority_type,
                    'approved_by': app.approved_by,
                    'scope_path': app.scope_path,
                }
                for app in self.approvals
            ],
            'routes': [
                {
                    'requested_provider': route.requested_provider,
                    'requested_model': route.requested_model,
                    'resolved_provider': route.resolved_provider,
                    'resolved_model': route.resolved_model,
                    'role': route.role,
                    'routing_reason': route.routing_reason,
                    'policy_source': route.policy_source,
                    'estimated_cost_cents': route.estimated_cost_cents,
                    'actual_cost_cents': route.actual_cost_cents,
                    'fallback_used': route.fallback_used,
                    'timestamp': route.timestamp,
                }
                for route in self.routes
            ],
            'known_gaps': [
                {
                    'category': gap.category,
                    'description': gap.description,
                    'severity': gap.severity,
                    'auto_derived': gap.auto_derived,
                    'timestamp': gap.timestamp,
                }
                for gap in self.known_gaps
            ],
            'provenance': [record.to_dict() for record in self.provenance],
            'skill_activations': [
                activation.to_dict() for activation in self.skill_activations
            ],
            'workspace_root': self.workspace_root,
            'goal_id': self.goal_id,
            'proof_of_use': self.proof_of_use.to_dict() if self.proof_of_use is not None else None,
            'undo_available': self.undo_available,
            'undo_mechanism': self.undo_mechanism,
            'undo_outcome': self.undo_outcome,
            'cost_cents': self.cost_cents,
            'cost_state': self.cost_state,
            'budget_cap_cents': self.budget_cap_cents,
        }


def _extract_scope_path(payload: dict[str, Any]) -> str:
    """Extract the path scope from an approval event payload."""
    arguments = payload.get('arguments') or {}
    if not isinstance(arguments, dict):
        return payload.get('path', '') or payload.get('scope', '')
    for key in ('path', 'file_path', 'target_path', 'file'):
        val = arguments.get(key)
        if isinstance(val, str) and val.strip():
            return val
    return payload.get('path', '') or payload.get('scope', '')


def extract_commands_run(events: list[dict[str, Any]]) -> list[CommandEvidence]:
    """Extract command execution evidence from audit events."""
    commands: list[CommandEvidence] = []
    for event in events:
        event_type = event.get('event_type')
        payload = event.get('payload') or {}
        if not isinstance(payload, dict):
            continue

        if event_type == 'tool_use':
            tool_name = payload.get('tool_name', '')
            # Check if it's a shell/exec command
            if tool_name in ('exec', 'shell', 'execute_shell_command'):
                command = payload.get('input', {}).get('command', '')
                if command:
                    commands.append(
                        CommandEvidence(
                            command=command,
                            tool_name=tool_name,
                            timestamp=event.get('created_at'),
                        )
                    )
    return commands


def extract_tests(events: list[dict[str, Any]]) -> list[TestEvidence]:
    """Extract test execution evidence from audit events."""
    tests: list[TestEvidence] = []
    for event in events:
        event_type = event.get('event_type')
        payload = event.get('payload') or {}
        if not isinstance(payload, dict):
            continue

        if event_type == 'test_run':
            tests.append(
                TestEvidence(
                    test_name=payload.get('test_name', ''),
                    test_file=payload.get('test_file', ''),
                    status=payload.get('status', 'unknown'),
                    duration_ms=payload.get('duration_ms'),
                    error_message=payload.get('error_message'),
                    timestamp=event.get('created_at'),
                )
            )
    return tests


def extract_approvals(events: list[dict[str, Any]]) -> list[ApprovalEvidence]:
    """Extract approval evidence from audit events."""
    approvals: list[ApprovalEvidence] = []
    for event in events:
        event_type = event.get('event_type')
        payload = event.get('payload') or {}
        if not isinstance(payload, dict):
            continue

        scope_path = _extract_scope_path(payload)

        if event_type == 'approval_requested':
            approvals.append(
                ApprovalEvidence(
                    call_id=payload.get('call_id', ''),
                    tool_name=payload.get('tool_name', ''),
                    approved=False,
                    auto_approved=payload.get('auto_approved', False),
                    timestamp=event.get('created_at'),
                    authority_type=payload.get('authority_type', ''),
                    scope_path=scope_path,
                )
            )
        elif event_type == 'approval_granted':
            call_id = payload.get('call_id', '')
            existing = next((a for a in approvals if a.call_id == call_id), None)
            if existing:
                existing.approved = True
                existing.auto_approved = payload.get('auto_approved', False)
                existing.authority_type = payload.get('authority_type', '')
                existing.approved_by = payload.get('approved_by', '')
                if scope_path:
                    existing.scope_path = scope_path
            else:
                approvals.append(
                    ApprovalEvidence(
                        call_id=call_id,
                        tool_name=payload.get('tool_name', ''),
                        approved=True,
                        auto_approved=payload.get('auto_approved', False),
                        timestamp=event.get('created_at'),
                        authority_type=payload.get('authority_type', ''),
                        approved_by=payload.get('approved_by', ''),
                        scope_path=scope_path,
                    )
                )
        elif event_type == 'approval_denied':
            call_id = payload.get('call_id', '')
            existing = next((a for a in approvals if a.call_id == call_id), None)
            if existing:
                existing.denied = True
            else:
                approvals.append(
                    ApprovalEvidence(
                        call_id=call_id,
                        tool_name=payload.get('tool_name', ''),
                        approved=False,
                        denied=True,
                        timestamp=event.get('created_at'),
                        authority_type=payload.get('authority_type', ''),
                        scope_path=scope_path,
                    )
                )
    return approvals


def extract_routes(events: list[dict[str, Any]]) -> list[ModelRouteEvidence]:
    """Extract model routing evidence from audit events."""
    routes: list[ModelRouteEvidence] = []
    for event in events:
        event_type = event.get('event_type')
        payload = event.get('payload') or {}
        if not isinstance(payload, dict):
            continue

        if event_type == 'model_route':
            routes.append(
                ModelRouteEvidence(
                    requested_provider=payload.get('requested_provider', ''),
                    requested_model=payload.get('requested_model', ''),
                    resolved_provider=payload.get('resolved_provider', ''),
                    resolved_model=payload.get('resolved_model', ''),
                    role=payload.get('role', ''),
                    routing_reason=payload.get('routing_reason', ''),
                    policy_source=payload.get('policy_source', ''),
                    estimated_cost_cents=float(
                        payload.get('estimated_cost_cents', 0)
                    ),
                    actual_cost_cents=float(
                        payload.get('actual_cost_cents', 0)
                    ),
                    fallback_used=bool(payload.get('fallback_used', False)),
                    timestamp=event.get('created_at'),
                )
            )
    return routes


def extract_provenance(events: list[dict[str, Any]]) -> list[ProvenanceRecord]:
    """Extract asset provenance records from audit events.

    Reads ``provenance_collected`` audit events and reconstructs
    ``ProvenanceRecord`` instances from the snapshot payload.
    """
    records: list[ProvenanceRecord] = []
    for event in events:
        event_type = event.get('event_type')
        payload = event.get('payload') or {}
        if not isinstance(payload, dict):
            continue

        if event_type == 'provenance_collected':
            snapshot = payload.get('snapshot') or {}
            if not isinstance(snapshot, dict):
                continue
            for record in snapshot.get('records', []):
                if not isinstance(record, dict):
                    continue
                records.append(
                    ProvenanceRecord(
                        asset_type=record.get('asset_type', 'skill'),
                        name=record.get('name', ''),
                        source_path=record.get('source_path', ''),
                        governance_status=record.get('governance_status', 'unknown'),
                        activation_status=record.get('activation_status', 'unknown'),
                        revocation_status=record.get(
                            'revocation_status', 'unknown'
                        ),
                        shadowed_paths=list(record.get('shadowed_paths', [])),
                        loaded_at=record.get('loaded_at', 0.0),
                    )
                )
    return records


def _derive_activation_cause(reason: str, event_type: str, payload: dict[str, Any]) -> str:
    """Derive the skill activation cause from the transition reason or event payload.

    Returns one of ``'explicit'``, ``'auto'``, ``'context'``, or ``'session'``.
    """
    reason_lower = reason.lower()
    if event_type == 'skill_activated':
        cause = payload.get('cause', '')
        if cause in {'explicit', 'auto', 'context', 'session'}:
            return cause
    if 'explicit' in reason_lower or 'selected' in reason_lower:
        return 'explicit'
    if 'eager' in reason_lower or 'auto' in reason_lower:
        return 'auto'
    if 'context' in reason_lower or 'session' in reason_lower:
        return 'context'
    if 'config' in reason_lower:
        return 'session'
    return 'auto'


def _to_iso_timestamp(event: dict[str, Any]) -> str:
    """Convert an event's ``created_at`` to an ISO 8601 string."""
    ts = event.get('created_at')
    if ts is None:
        return datetime.now(timezone.utc).isoformat()
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return datetime.now(timezone.utc).isoformat()


def _find_output_artifact_link(
    skill_name: str,
    events: list[dict[str, Any]],
) -> Optional[str]:
    """Find an output artifact link for a skill by scanning ``tool_call_completed`` events.

    Returns the ``artifact_path`` from the first matching tool-call result,
    or ``None`` if no artifact is found.
    """
    for ev in events:
        if ev.get('event_type') != 'tool_call_completed':
            continue
        payload = ev.get('payload') or {}
        if not isinstance(payload, dict):
            continue
        tool_name = str(payload.get('tool_name', ''))
        result = payload.get('result')
        if skill_name not in tool_name:
            continue
        if isinstance(result, dict):
            artifact_path = result.get('artifact_path', '')
            if artifact_path:
                return artifact_path
    return None


def extract_skill_activations(
    events: list[dict[str, Any]],
) -> list[SkillActivationRecord]:
    """Extract skill activation records from audit events.

    Reads ``skill_lifecycle_transition`` events whose ``to_state`` is
    ``'activated'`` and ``skill_activated`` events, then builds one
    ``SkillActivationRecord`` per unique skill (first activation wins).
    """
    records: list[SkillActivationRecord] = []
    seen_skills: set[str] = set()

    for ev in events:
        event_type = ev.get('event_type')
        payload = ev.get('payload') or {}
        if not isinstance(payload, dict):
            continue

        # -- skill_lifecycle_transition with to_state='activated' -----------
        if event_type == 'skill_lifecycle_transition':
            to_state = payload.get('to_state', '')
            if to_state != 'activated':
                continue
            skill_name = str(payload.get('skill_name', ''))
            if not skill_name or skill_name in seen_skills:
                continue
            reason = str(payload.get('reason', ''))
            source_path = str(payload.get('source_path', ''))
            cause = _derive_activation_cause(reason, event_type, payload)
            activated_at = _to_iso_timestamp(ev)
            artifact_link = _find_output_artifact_link(skill_name, events)
            records.append(
                SkillActivationRecord(
                    skill_name=skill_name,
                    activation_cause=cause,
                    source_path=source_path,
                    activated_at=activated_at,
                    output_artifact_link=artifact_link,
                )
            )
            seen_skills.add(skill_name)

        # -- skill_activated (future event type) -----------------------------
        elif event_type == 'skill_activated':
            skill_name = str(payload.get('skill_name', ''))
            if not skill_name or skill_name in seen_skills:
                continue
            source_path = str(payload.get('source_path', ''))
            cause = _derive_activation_cause('', event_type, payload)
            activated_at = _to_iso_timestamp(ev)
            artifact_link = _find_output_artifact_link(skill_name, events)
            records.append(
                SkillActivationRecord(
                    skill_name=skill_name,
                    activation_cause=cause,
                    source_path=source_path,
                    activated_at=activated_at,
                    output_artifact_link=artifact_link,
                )
            )
            seen_skills.add(skill_name)

    return records


def auto_derive_known_gaps(
    events: list[dict[str, Any]], commands: list[CommandEvidence]
) -> list[KnownGap]:
    """Auto-derive known gaps from audit events and command evidence."""
    gaps: list[KnownGap] = []

    # Check for failed commands
    for cmd in commands:
        if cmd.exit_code and cmd.exit_code != 0:
            gaps.append(
                KnownGap(
                    category='command_failure',
                    description=f'Command failed with exit code {cmd.exit_code}: {cmd.command[:100]}',
                    severity='medium',
                    auto_derived=True,
                    timestamp=cmd.timestamp,
                )
            )

    # Check for run failures
    for event in events:
        event_type = event.get('event_type')
        payload = event.get('payload') or {}
        if not isinstance(payload, dict):
            continue

        if event_type == 'run_failed':
            gaps.append(
                KnownGap(
                    category='run_failure',
                    description=payload.get('message', 'Run failed'),
                    severity='high',
                    auto_derived=True,
                    timestamp=event.get('created_at'),
                )
            )

    # Check for tool errors
    for event in events:
        event_type = event.get('event_type')
        payload = event.get('payload') or {}
        if not isinstance(payload, dict):
            continue

        if event_type == 'tool_error':
            gaps.append(
                KnownGap(
                    category='tool_error',
                    description=payload.get('error', 'Tool error'),
                    severity='medium',
                    auto_derived=True,
                    timestamp=event.get('created_at'),
                )
            )

    return gaps


def _extract_undo_evidence(
    events: list[dict[str, Any]],
) -> tuple[Optional[str], Optional[str]]:
    """Return (undo_mechanism, undo_outcome) from audit events.

    Reads ``undo_applied`` events to determine which mechanism was used
    and what the outcome was. Returns (None, None) if no undo event found.
    """
    for event in events:
        if event.get('event_type') != 'undo_applied':
            continue
        payload = event.get('payload') or {}
        if not isinstance(payload, dict):
            continue
        undo_journal_path = payload.get('undo_journal_path')
        if undo_journal_path is not None:
            mechanism = 'journal'
        else:
            mechanism = 'checkpoint'
        status = payload.get('status')
        if status == 'restored':
            outcome = 'reverted'
        elif status == 'partial':
            outcome = 'partial'
        else:
            outcome = 'failed'
        return mechanism, outcome
    return None, None


def build_run_evidence_bundle(
    root: str | Path,
    run_id: str,
    *,
    goal_id: str = '',
) -> RunEvidenceBundle:
    """Build a complete evidence bundle for a run.

    Args:
        root: Workspace root directory.
        run_id: Run identifier.
        goal_id: Optional goal identifier to link this run to a GoalRecord.
    """
    try:
        events = RunStore(root).show_run(run_id)
    except FileNotFoundError:
        return RunEvidenceBundle(run_id=run_id, goal_id=goal_id)

    commands = extract_commands_run(events)
    tests = extract_tests(events)
    approvals = extract_approvals(events)
    routes = extract_routes(events)
    known_gaps = auto_derive_known_gaps(events, commands)

    undo_mechanism, undo_outcome = _extract_undo_evidence(events)
    store = RunStore(root)
    undo_available = store.undo_path(run_id).is_file()

    # Build proof-of-use from the same events.  We don't have access to the
    # final answer content at this point (RunStore only stores events), so
    # we pass an empty string.  Full proof-of-use with final-answer hash is
    # attached during _handle_final_answer.
    proof_of_use = build_proof_of_use(events, "")
    provenance = extract_provenance(events)
    skill_activations = extract_skill_activations(events)

    return RunEvidenceBundle(
        run_id=run_id,
        commands_run=commands,
        tests=tests,
        approvals=approvals,
        routes=routes,
        known_gaps=known_gaps,
        workspace_root=str(root),
        goal_id=goal_id,
        proof_of_use=proof_of_use if proof_of_use.proofs else None,
        provenance=provenance,
        skill_activations=skill_activations,
        undo_available=undo_available,
        undo_mechanism=undo_mechanism,
        undo_outcome=undo_outcome,
    )


def evidence_completeness_checklist() -> dict[str, list[str]]:
    """Return the expected evidence fields per run status.

    Each status maps to a list of field names and audit events that
    must be present for a run to be considered ``evidence-complete``.
    The returned keys match the attribute names on
    :class:`RunEvidenceBundle` (e.g. ``commands_run``, ``tests``)
    and additional event-type names (e.g. ``run_started``,
    ``run_completed``).

    Callers should check that the returned names exist as non-trivial
    values in the evidence bundle (non-empty lists, non-zero counts,
    non-``None`` optional fields).
    """
    return {
        'success': [
            'run_id',
            'commands_run',
            'tests',
            'approvals',
            'routes',
            'known_gaps',
            'workspace_root',
            'undo_available',
            'cost_cents',
            'cost_state',
            'budget_cap_cents',
            'event:run_started',
            'event:run_completed',
        ],
        'failure': [
            'run_id',
            'commands_run',
            'tests',
            'approvals',
            'routes',
            'known_gaps',
            'workspace_root',
            'cost_cents',
            'cost_state',
            'budget_cap_cents',
            # audit events that must be present
            'event:run_started',
            'event:run_failed',
        ],
        'cancelled': [
            'run_id',
            'commands_run',
            'tests',
            'cost_cents',
            'cost_state',
            'budget_cap_cents',
            # audit events that must be present
            'event:run_started',
            'event:run_cancelled',
        ],
        'pending_approval': [
            'run_id',
            'commands_run',
            'tests',
            'approvals',
            'cost_cents',
            'cost_state',
            'budget_cap_cents',
            # audit events that must be present
            'event:run_started',
            'event:run_paused',
        ],
        'unknown': [
            'run_id',
        ],
    }


def check_evidence_completeness(
    bundle: RunEvidenceBundle,
    events: list[dict[str, Any]],
    status: str,
) -> list[str]:
    """Check a run evidence bundle for completeness against the expected fields per status.

    Returns a list of missing evidence items (empty list means complete).
    Each missing item is a human-readable string describing what is absent.
    """
    checklist = evidence_completeness_checklist()
    expected = checklist.get(status, checklist['unknown'])
    bundle_dict = bundle.to_dict()
    missing: list[str] = []

    event_types = {e.get('event_type', '') for e in events}

    for item in expected:
        if item.startswith('event:'):
            event_name = item[len('event:'):]
            if event_name not in event_types:
                missing.append(f'missing audit event: {event_name}')
            continue

        value = bundle_dict.get(item)
        if value is None:
            missing.append(f'missing field: {item}')
        elif isinstance(value, list) and len(value) == 0:
            missing.append(f'empty list field: {item}')
        elif isinstance(value, str) and value == '':
            missing.append(f'empty string field: {item}')

    return missing

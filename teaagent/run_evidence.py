"""Run evidence bundle extraction from audit trails.

This module provides functions to extract structured evidence from a run's
audit trail, including commands_run, tests, approvals, and known_gaps.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Optional

from teaagent.asset_provenance import ProvenanceRecord
from teaagent.proof_of_use import ProofOfUseBundle, build_proof_of_use
from teaagent.run_store import RunStore
from teaagent.types import JsonMapping

if TYPE_CHECKING:
    from teaagent.runner._events import RunEvent


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

    __test__: ClassVar[bool] = False

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

    def to_dict(self) -> JsonMapping:
        """Convert to dictionary for serialization."""
        return {
            'skill_name': self.skill_name,
            'activation_cause': self.activation_cause,
            'source_path': self.source_path,
            'activated_at': self.activated_at,
            'output_artifact_link': self.output_artifact_link,
        }


@dataclass
class GitSandboxEvidence:
    """Git sandbox lifecycle state captured from audit events."""

    branch_name: str = ''
    original_branch: str = ''
    stash_id: str | None = None
    auto_stash: bool = False
    started: bool = False
    resolution: str | None = None
    resolved: bool = False
    success: bool = False
    error: str | None = None

    def to_dict(self) -> JsonMapping:
        return {
            'branch_name': self.branch_name,
            'original_branch': self.original_branch,
            'stash_id': self.stash_id,
            'auto_stash': self.auto_stash,
            'started': self.started,
            'resolution': self.resolution,
            'resolved': self.resolved,
            'success': self.success,
            'error': self.error,
        }


@dataclass
class HookActivityRecord:
    """A PreToolUse/PostToolUse hook side-effect captured from audit events.

    ADR 0032 M5 hook-observability: surfaces hook veto/mutation activity emitted
    by the tool-dispatch ``HookRegistry`` (``teaagent/tools.py``) into the
    evidence bundle so it appears in receipts. ``activity`` is the audit event
    kind without the ``tool_hook_`` prefix: ``pre_mutation``,
    ``pre_mutation_blocked``, ``vetoed``, ``post_mutation``, ``post_failed``.
    """

    activity: str
    tool_name: str
    call_id: str = ''
    error: str = ''
    added_keys: list[str] = field(default_factory=list)
    removed_keys: list[str] = field(default_factory=list)
    modified_keys: list[str] = field(default_factory=list)
    timestamp: Optional[str] = None

    def to_dict(self) -> JsonMapping:
        return {
            'activity': self.activity,
            'tool_name': self.tool_name,
            'call_id': self.call_id,
            'error': self.error,
            'added_keys': self.added_keys,
            'removed_keys': self.removed_keys,
            'modified_keys': self.modified_keys,
            'timestamp': self.timestamp,
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

    # ── context health (CTX-001) ──
    context_health: Optional[JsonMapping] = None

    # ── cost tracking (P0-B) ──
    cost_cents: float = 0.0
    cost_state: str = 'unavailable'
    budget_cap_cents: int | None = None

    git_sandbox: GitSandboxEvidence | None = None

    # ── hook observability (ADR 0032 M5) ──
    hook_activity: list[HookActivityRecord] = field(default_factory=list)

    def to_dict(self) -> JsonMapping:
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
            'proof_of_use': self.proof_of_use.to_dict()
            if self.proof_of_use is not None
            else None,
            'undo_available': self.undo_available,
            'undo_mechanism': self.undo_mechanism,
            'undo_outcome': self.undo_outcome,
            'context_health': self.context_health,
            'cost_cents': self.cost_cents,
            'cost_state': self.cost_state,
            'budget_cap_cents': self.budget_cap_cents,
            'git_sandbox': self.git_sandbox.to_dict()
            if self.git_sandbox is not None
            else None,
            'hook_activity': [record.to_dict() for record in self.hook_activity],
        }


_HOOK_AUDIT_TYPES: frozenset[str] = frozenset(
    {
        'tool_hook_pre_mutation',
        'tool_hook_pre_mutation_blocked',
        'tool_hook_vetoed',
        'tool_hook_post_mutation',
        'tool_hook_post_failed',
    }
)


def extract_hook_activity(events: list[JsonMapping]) -> list[HookActivityRecord]:
    """Extract PreToolUse/PostToolUse hook side-effects from audit events.

    Reads the five ``tool_hook_*`` events emitted by the tool-dispatch
    ``HookRegistry`` so hook veto/mutation activity is represented in the
    evidence bundle (ADR 0032 M5; review F1).
    """
    records: list[HookActivityRecord] = []
    for event in events:
        event_type = event.get('event_type')
        if event_type not in _HOOK_AUDIT_TYPES:
            continue
        payload = event.get('payload') or {}
        if not isinstance(payload, dict):
            continue
        records.append(
            HookActivityRecord(
                activity=str(event_type)[len('tool_hook_') :],
                tool_name=str(payload.get('tool_name', '')),
                call_id=str(payload.get('call_id', '')),
                error=str(payload.get('error', '')),
                added_keys=list(payload.get('added_keys') or []),
                removed_keys=list(payload.get('removed_keys') or []),
                modified_keys=list(payload.get('modified_keys') or []),
                timestamp=event.get('created_at'),
            )
        )
    return records


def extract_git_sandbox(events: list[JsonMapping]) -> GitSandboxEvidence | None:
    """Extract git sandbox lifecycle evidence from audit events."""
    evidence = GitSandboxEvidence()
    saw_event = False
    for event in events:
        event_type = event.get('event_type')
        payload = event.get('payload') or {}
        if not isinstance(payload, dict):
            continue
        if event_type == 'git_sandbox_started':
            saw_event = True
            evidence.started = bool(payload.get('success', False))
            evidence.auto_stash = bool(payload.get('auto_stash', False))
            evidence.branch_name = str(payload.get('branch_name', '') or '')
            evidence.original_branch = str(payload.get('original_branch', '') or '')
            stash_id = payload.get('stash_id')
            evidence.stash_id = str(stash_id) if stash_id else None
            error = payload.get('error')
            evidence.error = str(error) if error else None
        elif event_type == 'git_sandbox_resolved':
            saw_event = True
            evidence.resolved = True
            evidence.resolution = str(payload.get('resolution', '') or '') or None
            evidence.success = bool(payload.get('success', False))
            error = payload.get('error')
            evidence.error = str(error) if error else None
            if not evidence.branch_name:
                evidence.branch_name = str(payload.get('branch_name', '') or '')
            if not evidence.original_branch:
                evidence.original_branch = str(payload.get('original_branch', '') or '')
            if evidence.stash_id is None:
                stash_id = payload.get('stash_id')
                evidence.stash_id = str(stash_id) if stash_id else None
    return evidence if saw_event else None


def _extract_scope_path(payload: JsonMapping) -> str:
    """Extract the path scope from an approval event payload."""
    arguments = payload.get('arguments') or {}
    if not isinstance(arguments, dict):
        return payload.get('path', '') or payload.get('scope', '')
    for key in ('path', 'file_path', 'target_path', 'file'):
        val = arguments.get(key)
        if isinstance(val, str) and val.strip():
            return val
    return payload.get('path', '') or payload.get('scope', '')


def extract_commands_run(events: list[JsonMapping]) -> list[CommandEvidence]:
    """Extract command execution evidence from audit events."""
    commands: list[CommandEvidence] = []
    by_call_id: dict[str, CommandEvidence] = {}

    def _command_from_payload(payload: JsonMapping) -> str:
        arguments = payload.get('arguments') or payload.get('input') or {}
        if isinstance(arguments, dict):
            command = arguments.get('command', arguments.get('cmd', ''))
            if isinstance(command, str) and command.strip():
                return command.strip()
        result = payload.get('result')
        if isinstance(result, dict):
            command = result.get('command', '')
            if isinstance(command, str) and command.strip():
                return command.strip()
        return ''

    def _result_int(value: Any) -> int | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return int(value)
        return None

    def _append_or_update(
        *,
        call_id: str,
        tool_name: str,
        command: str,
        timestamp: Any,
    ) -> CommandEvidence:
        existing = by_call_id.get(call_id) if call_id else None
        if existing is not None:
            if command and not existing.command:
                existing.command = command
            if existing.timestamp is None:
                existing.timestamp = timestamp
            return existing
        entry = CommandEvidence(
            command=command,
            tool_name=tool_name,
            timestamp=timestamp,
        )
        commands.append(entry)
        if call_id:
            by_call_id[call_id] = entry
        return entry

    for event in events:
        event_type = event.get('event_type')
        payload = event.get('payload') or {}
        if not isinstance(payload, dict):
            continue

        if event_type not in {
            'tool_use',
            'tool_call_started',
            'tool_call_completed',
        }:
            continue

        tool_name = str(payload.get('tool_name', ''))
        if tool_name not in {
            'exec',
            'shell',
            'execute_shell_command',
            'workspace_run_shell_mutate',
            'workspace_run_shell_inspect',
            'workspace_run_shell',
        }:
            continue

        call_id = str(payload.get('call_id', '') or '')
        command = _command_from_payload(payload)

        if event_type in {'tool_use', 'tool_call_started'}:
            _append_or_update(
                call_id=call_id,
                tool_name=tool_name,
                command=command,
                timestamp=event.get('created_at'),
            )
            continue

        result = payload.get('result')
        if not isinstance(result, dict):
            continue
        entry = _append_or_update(
            call_id=call_id,
            tool_name=tool_name,
            command=command,
            timestamp=event.get('created_at'),
        )
        if 'exit_code' in result:
            entry.exit_code = _result_int(result.get('exit_code'))
        if isinstance(result.get('stdout'), str):
            entry.stdout = result.get('stdout')
        if isinstance(result.get('stderr'), str):
            entry.stderr = result.get('stderr')
    return commands


def extract_tests(events: list[JsonMapping]) -> list[TestEvidence]:
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


def extract_approvals(events: list[JsonMapping]) -> list[ApprovalEvidence]:
    """Extract approval evidence from audit events."""
    approvals: list[ApprovalEvidence] = []

    def approval_for(call_id: str) -> ApprovalEvidence | None:
        return next((a for a in approvals if a.call_id == call_id), None)

    def append_or_update(
        *,
        payload: JsonMapping,
        timestamp: Any,
        approved: bool = False,
        denied: bool = False,
    ) -> None:
        call_id = str(payload.get('call_id', '') or '')
        existing = approval_for(call_id)
        scope_path = _extract_scope_path(payload)
        if existing is None:
            approvals.append(
                ApprovalEvidence(
                    call_id=call_id,
                    tool_name=payload.get('tool_name', ''),
                    approved=approved,
                    auto_approved=payload.get('auto_approved', False),
                    denied=denied,
                    timestamp=timestamp,
                    authority_type=payload.get('authority_type', ''),
                    approved_by=payload.get('approved_by', ''),
                    scope_path=scope_path,
                )
            )
            return
        existing.approved = existing.approved or approved
        existing.denied = existing.denied or denied
        existing.auto_approved = payload.get('auto_approved', existing.auto_approved)
        existing.authority_type = payload.get('authority_type', existing.authority_type)
        existing.approved_by = payload.get('approved_by', existing.approved_by)
        if scope_path:
            existing.scope_path = scope_path

    for event in events:
        event_type = event.get('event_type')
        payload = event.get('payload') or {}
        if not isinstance(payload, dict):
            continue

        if event_type in {'approval_requested', 'tool_call_pending_approval'}:
            append_or_update(payload=payload, timestamp=event.get('created_at'))
        elif event_type in {'approval_granted', 'tool_call_approved'}:
            append_or_update(
                payload=payload,
                timestamp=event.get('created_at'),
                approved=True,
            )
        elif event_type in {'approval_denied', 'tool_call_denied'}:
            append_or_update(
                payload=payload,
                timestamp=event.get('created_at'),
                denied=True,
            )
    return approvals


def extract_routes(events: list[JsonMapping]) -> list[ModelRouteEvidence]:
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
                    estimated_cost_cents=float(payload.get('estimated_cost_cents', 0)),
                    actual_cost_cents=float(payload.get('actual_cost_cents', 0)),
                    fallback_used=bool(payload.get('fallback_used', False)),
                    timestamp=event.get('created_at'),
                )
            )
    return routes


def extract_provenance(events: list[JsonMapping]) -> list[ProvenanceRecord]:
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
                        revocation_status=record.get('revocation_status', 'unknown'),
                        shadowed_paths=list(record.get('shadowed_paths', [])),
                        loaded_at=record.get('loaded_at', 0.0),
                    )
                )
    return records


def _derive_activation_cause(reason: str, event_type: str, payload: JsonMapping) -> str:
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


def _to_iso_timestamp(event: JsonMapping) -> str:
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
    events: list[JsonMapping],
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
    events: list[JsonMapping],
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
    events: list[JsonMapping], commands: list[CommandEvidence]
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
    events: list[JsonMapping],
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

    # M6 FOLD-T002 cutover: production evidence is now derived from the TYPED
    # event stream, not raw audit dicts. Every evidence-bearing audit event is
    # typed in RunEventType (M2 + M3 + M5), so read_run_events_from_audit is
    # lossless here; events whose type is not in the taxonomy are not read by any
    # extractor anyway. The legacy raw-dict assembly is no longer the production
    # path — it survives only as the shared _assemble_evidence_bundle helper that
    # the fold also uses, so the two cannot diverge.
    from teaagent.runner._events import read_run_events_from_audit

    typed = read_run_events_from_audit(events)
    return build_evidence_from_events(typed, root=root, run_id=run_id, goal_id=goal_id)


def build_evidence_from_events(
    events: list['RunEvent'],
    *,
    root: str | Path,
    run_id: str,
    goal_id: str = '',
) -> RunEvidenceBundle:
    """Fold a typed ``RunEvent`` stream into a :class:`RunEvidenceBundle`.

    ADR 0032 M6 (FOLD-T001/T002): this is the production fold used by
    :func:`build_run_evidence_bundle`. Persisted audit entries are first mapped
    into the typed stream by ``read_run_events_from_audit``; every evidence-
    bearing audit event is covered by ``RunEventType`` (M2 + M3 + M5), so the
    conversion is lossless for evidence. The internal raw-dict assembler is an
    implementation helper after typed conversion, not an alternate production
    path or fallback flag.

    Args:
        events: Typed run events (from the M2-T001 reader over persisted audit).
        root: Workspace root directory.
        run_id: Run identifier.
        goal_id: Optional goal identifier to link this run to a GoalRecord.
    """
    from teaagent.runner._events import run_event_to_audit_event_type

    event_dicts: list[JsonMapping] = [
        {
            'event_type': run_event_to_audit_event_type(e.type),
            'run_id': e.run_id,
            'payload': dict(e.payload),
            'created_at': e.created_at,
        }
        for e in events
    ]
    return _assemble_evidence_bundle(
        event_dicts, root=root, run_id=run_id, goal_id=goal_id
    )


def _assemble_evidence_bundle(
    events: list[JsonMapping],
    *,
    root: str | Path,
    run_id: str,
    goal_id: str = '',
) -> RunEvidenceBundle:
    """Assemble a :class:`RunEvidenceBundle` from raw audit-event dicts.

    Internal to the typed-stream production fold. It reconstructs the existing
    extractor input shape after taxonomy validation, keeping extractor logic
    shared without preserving a second raw-event production path. Pure over the
    supplied ``events`` plus on-disk artifacts (undo journal, context health)
    keyed by ``root``/``run_id``.
    """
    commands = extract_commands_run(events)
    tests = extract_tests(events)
    approvals = extract_approvals(events)
    routes = extract_routes(events)
    known_gaps = auto_derive_known_gaps(events, commands)
    git_sandbox = extract_git_sandbox(events)

    hook_activity = extract_hook_activity(events)
    undo_mechanism, undo_outcome = _extract_undo_evidence(events)
    store = RunStore(root)
    undo_available = store.undo_path(run_id).is_file()

    # Build proof-of-use from the same events.  We don't have access to the
    # final answer content at this point (RunStore only stores events), so
    # we pass an empty string.  Full proof-of-use with final-answer hash is
    # attached during _handle_final_answer.
    proof_of_use = build_proof_of_use(events, '')
    provenance = extract_provenance(events)
    skill_activations = extract_skill_activations(events)

    # ── context health (CTX-001) ──
    try:
        from teaagent.context_health import compute_context_health

        ch = compute_context_health(workspace_root=str(root))
        ctx_health_dict: JsonMapping | None = ch.to_dict() if ch else None
    except Exception:
        ctx_health_dict = None

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
        context_health=ctx_health_dict,
        git_sandbox=git_sandbox,
        hook_activity=hook_activity,
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
    events: list[JsonMapping],
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
            event_name = item[len('event:') :]
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

"""Run evidence bundle extraction from audit trails.

This module provides functions to extract structured evidence from a run's
audit trail, including commands_run, tests, approvals, and known_gaps.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

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
    """Evidence of an approval during a run."""

    call_id: str
    tool_name: str
    approved: bool
    auto_approved: bool = False
    denied: bool = False
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
class RunEvidenceBundle:
    """Complete evidence bundle for a run."""

    run_id: str
    commands_run: list[CommandEvidence] = field(default_factory=list)
    tests: list[TestEvidence] = field(default_factory=list)
    approvals: list[ApprovalEvidence] = field(default_factory=list)
    known_gaps: list[KnownGap] = field(default_factory=list)

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
                }
                for app in self.approvals
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
        }


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

        if event_type == 'approval_requested':
            approvals.append(
                ApprovalEvidence(
                    call_id=payload.get('call_id', ''),
                    tool_name=payload.get('tool_name', ''),
                    approved=False,
                    auto_approved=payload.get('auto_approved', False),
                    timestamp=event.get('created_at'),
                )
            )
        elif event_type == 'approval_granted':
            # Update existing approval or add new
            call_id = payload.get('call_id', '')
            existing = next((a for a in approvals if a.call_id == call_id), None)
            if existing:
                existing.approved = True
                existing.auto_approved = payload.get('auto_approved', False)
            else:
                approvals.append(
                    ApprovalEvidence(
                        call_id=call_id,
                        tool_name=payload.get('tool_name', ''),
                        approved=True,
                        auto_approved=payload.get('auto_approved', False),
                        timestamp=event.get('created_at'),
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
                    )
                )
    return approvals


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


def build_run_evidence_bundle(root: str | Path, run_id: str) -> RunEvidenceBundle:
    """Build a complete evidence bundle for a run."""
    try:
        events = RunStore(root).show_run(run_id)
    except FileNotFoundError:
        return RunEvidenceBundle(run_id=run_id)

    commands = extract_commands_run(events)
    tests = extract_tests(events)
    approvals = extract_approvals(events)
    known_gaps = auto_derive_known_gaps(events, commands)

    return RunEvidenceBundle(
        run_id=run_id,
        commands_run=commands,
        tests=tests,
        approvals=approvals,
        known_gaps=known_gaps,
    )

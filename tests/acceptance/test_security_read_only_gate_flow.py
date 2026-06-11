"""Test module for read-only runtime gate security enforcement.

This module tests the read-only runtime gate, which is a critical security control
that prevents destructive operations when the agent is running in read-only mode.
The gate blocks write tools and mutating operations to protect against unintended
modifications, ensuring that read-only mode provides strong safety guarantees.

Key concepts tested:
- Runtime Block Reason: The gate provides clear reasons when blocking tools
- Tool Classification: Tools are classified as destructive or safe based on metadata
- Read-Only Declaration: Tools must declare read_only=True to pass in read-only mode
- Handler Analysis: The gate can analyze handler source code for mutation patterns
- Audit Trail: Blocked tool attempts are recorded in the audit log
- Audit Chain Integrity: Audit chain remains valid after recording blocked operations

Acceptance Criteria:
- AC1: Write tools (workspace_write_file, workspace_apply_patch, etc.) are blocked in read-only mode
- AC2: Shell mutation tools (workspace_run_shell_mutate) are blocked in read-only mode
- AC3: Tools with destructive=True are blocked unless read_only=True is declared
- AC4: Tools without read_only declaration are blocked in read-only mode
- AC5: Safe tools with read_only=True pass the gate
- AC6: Handler source analysis detects mutating operations (e.g., +=, =)
- AC7: Blocked tool attempts are recorded in audit with tool_name, reason, and permission_mode
- AC8: Audit chain integrity is maintained after recording blocked operations

Technical Details:
- read_only_runtime_block_reason checks tool metadata (read_only, destructive flags)
- read_only_handler_block_reason analyzes handler source code for mutation patterns
- Bedrock-specific tool names are recognized (workspace_write_file, workspace_apply_patch, etc.)
- AuditLogger records tool_call_blocked events with full context
- verify_audit_chain ensures audit log integrity and event sequencing
- The gate operates at runtime, before tool execution

References:
- Security design: /docs/architecture/security/read_only_gate.md
- Tool metadata spec: /docs/specs/tool_metadata.md
- Audit chain design: /docs/architecture/audit_chain.md
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from teaagent.read_only_gate import (
    read_only_handler_block_reason,
    read_only_runtime_block_reason,
)
from teaagent.types import AuditLogger, verify_audit_chain


def _mutating_handler(x: int) -> int:
    x += 1
    return x


def _safe_handler(x: int) -> int:
    """A read-only handler."""
    return x * 2


# Bedrock write tool names
def test_workspace_write_file_blocked():
    reason = read_only_runtime_block_reason(
        tool_name='workspace_write_file',
        description='Write a file',
        read_only=None,
        destructive=True,
    )
    # Security-critical: write tools must be blocked in read-only mode
    assert reason is not None, (
        'Expected workspace_write_file to be blocked in read-only mode'
    )
    assert 'blocked' in reason.lower(), (
        f'Expected block reason to mention "blocked", got: {reason}'
    )


def test_workspace_apply_patch_blocked():
    reason = read_only_runtime_block_reason(
        tool_name='workspace_apply_patch',
        description='Apply patch',
        read_only=None,
        destructive=True,
    )
    # Security-critical: patch tools must be blocked in read-only mode
    assert reason is not None, (
        'Expected workspace_apply_patch to be blocked in read-only mode'
    )


def test_workspace_edit_at_hash_blocked():
    reason = read_only_runtime_block_reason(
        tool_name='workspace_edit_at_hash',
        description='Edit file',
        read_only=None,
        destructive=True,
    )
    # Security-critical: edit tools must be blocked in read-only mode
    assert reason is not None, (
        'Expected workspace_edit_at_hash to be blocked in read-only mode'
    )


# Shell mutate names
def test_workspace_run_shell_mutate_blocked():
    reason = read_only_runtime_block_reason(
        tool_name='workspace_run_shell_mutate',
        description='Run shell',
        read_only=None,
        destructive=True,
    )
    # Security-critical: shell mutate tools must be blocked in read-only mode
    assert reason is not None, (
        'Expected workspace_run_shell_mutate to be blocked in read-only mode'
    )


def test_workspace_run_shell_blocked():
    reason = read_only_runtime_block_reason(
        tool_name='workspace_run_shell',
        description='Run shell',
        read_only=None,
        destructive=True,
    )
    # Security-critical: shell tools must be blocked in read-only mode
    assert reason is not None, (
        'Expected workspace_run_shell to be blocked in read-only mode'
    )


# Read-only flag required
def test_destructive_tool_blocked():
    reason = read_only_runtime_block_reason(
        tool_name='custom_tool',
        description='A custom tool',
        read_only=None,
        destructive=True,
    )
    # Security-critical: destructive tools without read_only=True must be blocked
    assert reason is not None, (
        'Expected destructive tool without read_only=True to be blocked'
    )


def test_read_only_true_passes_with_safe_descriptor():
    reason = read_only_runtime_block_reason(
        tool_name='safe_tool',
        description='Read data from source',
        read_only=True,
        destructive=False,
    )
    # Safe tools with read_only=True should pass the gate
    assert reason is None, 'Expected safe tool with read_only=True to pass the gate'


def test_missing_read_only_declaration_blocked():
    reason = read_only_runtime_block_reason(
        tool_name='unknown_tool',
        description='Query something',
        read_only=None,
        destructive=False,
    )
    # Security-critical: tools without read_only declaration must be blocked
    assert reason is not None, (
        'Expected tool without read_only declaration to be blocked'
    )
    assert 'read_only=true' in reason or 'Read-only' in reason, (
        f'Expected block reason to mention read_only declaration, got: {reason}'
    )


# Read-only handler block reason
def test_none_handler_returns_none():
    # Edge case: None handler should return None (no block reason)
    assert read_only_handler_block_reason('tool', None) is None, (
        'Expected None handler to return None block reason'
    )


def test_mutating_handler_source_detected():
    reason = read_only_handler_block_reason(
        'mutating_tool',
        _mutating_handler,
    )
    # Security-critical: mutating handlers should be detected and blocked
    assert reason is not None, 'Expected mutating handler to be detected and blocked'


def test_safe_handler_passes():
    reason = read_only_handler_block_reason(
        'safe_tool',
        _safe_handler,
    )
    # Safe handlers should pass the gate
    assert reason is None, 'Expected safe handler to pass the gate'


# Audit trail integrity
def test_audit_records_blocked_tool_attempt():
    """Audit logger should record when a tool is blocked by read-only gate."""
    audit = AuditLogger()
    tool_name = 'workspace_write_file'
    reason = read_only_runtime_block_reason(
        tool_name=tool_name,
        description='Write a file',
        read_only=None,
        destructive=True,
    )

    # Simulate recording the blocked attempt
    audit.record(
        'tool_call_blocked',
        'test-run',
        tool_name=tool_name,
        reason=reason,
        permission_mode='read-only',
    )

    # Verify audit event was recorded
    blocked_events = [e for e in audit.events if e.event_type == 'tool_call_blocked']
    assert len(blocked_events) == 1, (
        f'Expected exactly 1 blocked tool event, got {len(blocked_events)}'
    )
    assert blocked_events[0].payload['tool_name'] == tool_name, (
        f'Expected tool_name to be {tool_name!r}, got {blocked_events[0].payload["tool_name"]!r}'
    )
    assert blocked_events[0].payload['reason'] == reason, (
        f'Expected reason to match, got {blocked_events[0].payload["reason"]!r}'
    )
    assert blocked_events[0].payload['permission_mode'] == 'read-only', (
        f'Expected permission_mode to be "read-only", got {blocked_events[0].payload["permission_mode"]!r}'
    )


def test_audit_chain_integrity_after_block():
    """Audit chain should remain valid after recording blocked operations."""
    with tempfile.TemporaryDirectory() as tmp:
        log_path = Path(tmp) / 'audit.jsonl'
        audit = AuditLogger(path=log_path)

        # Record a blocked tool attempt
        audit.record(
            'tool_call_blocked',
            'test-run',
            tool_name='workspace_write_file',
            reason='blocked by read-only mode',
            permission_mode='read-only',
        )

        # Verify audit chain integrity
        result = verify_audit_chain(log_path)
        assert result.valid, f'Audit chain invalid: {result.error}'
        assert result.event_count == 1, (
            f'Expected 1 event in audit chain, got {result.event_count}'
        )

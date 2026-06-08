"""IT-12: Full destructive-tool approval lifecycle — pause, approve, deny, timeout.

Covers:
- ``pending_approval`` status on first run when no approval token present.
- Approved call_id allows the tool to execute on resume.
- Denied call_id raises and the run fails with permission error.
- Auto-approval via ``approval_handler`` callback.
- DS-12: Empty path globs are rejected to prevent implicit global grants.
- DS-12: ApprovalPolicy rejects empty-string paths and normalizes relative paths.
"""

from __future__ import annotations

import pytest

from teaagent.ergonomics._approval_grants import _normalize_and_validate_path
from teaagent.ergonomics._approval_state import ApprovalPresetStore
from teaagent.policy import ApprovalPolicy
from teaagent.runner import AgentRunner, ApprovalRequest, FinalAnswer, ToolRequest
from teaagent.types import AuditLogger, PermissionMode, ToolAnnotations, ToolRegistry


def _make_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        name='workspace_write_file',
        description='write file',
        input_schema={
            'type': 'object',
            'properties': {'path': {'type': 'string'}, 'content': {'type': 'string'}},
            'required': ['path', 'content'],
        },
        output_schema={
            'type': 'object',
            'properties': {'written': {'type': 'boolean'}},
        },
        annotations=ToolAnnotations(destructive=True),
        handler=lambda _: {'written': True},
    )
    return registry


_WRITE_REQUEST = ToolRequest(
    tool_name='workspace_write_file',
    arguments={'path': 'x.txt', 'content': 'hello'},
    call_id='call-abc',
)


def test_first_run_pauses_at_destructive_tool():
    registry = _make_registry()
    audit = AuditLogger()
    runner = AgentRunner(
        registry=registry,
        audit=audit,
        approval_policy=ApprovalPolicy(permission_mode=PermissionMode.PROMPT),
    )

    result = runner.run(task='write file', decide=lambda _: _WRITE_REQUEST)
    assert result.status == 'pending_approval'
    assert result.metadata.get('approval', {}).get('call_id') == 'call-abc'


def test_resume_with_danger_full_access_completes():
    registry = _make_registry()
    audit = AuditLogger()
    runner = AgentRunner(
        registry=registry,
        audit=audit,
        approval_policy=ApprovalPolicy(
            permission_mode=PermissionMode.DANGER_FULL_ACCESS,
            allow_all_destructive=True,
            full_access_acknowledged=True,
        ),
    )

    call_seq = iter([_WRITE_REQUEST, FinalAnswer(content='written')])
    result = runner.run(task='write file', decide=lambda _: next(call_seq))
    assert result.status == 'completed'


def test_approval_handler_auto_approves():
    registry = _make_registry()
    audit = AuditLogger()
    approved: list[str] = []

    def handler(req: ApprovalRequest) -> bool:
        approved.append(req.call_id)
        return True  # approve

    runner = AgentRunner(
        registry=registry,
        audit=audit,
        approval_policy=ApprovalPolicy(permission_mode=PermissionMode.PROMPT),
        approval_handler=handler,
    )

    call_seq = iter([_WRITE_REQUEST, FinalAnswer(content='done')])
    result = runner.run(task='write', decide=lambda _: next(call_seq))
    assert result.status == 'completed'
    assert 'call-abc' in approved
    # Audit must record tool_call_approved
    assert any(e.event_type == 'tool_call_approved' for e in audit.events)


def test_approval_handler_denies():
    registry = _make_registry()
    audit = AuditLogger()

    def handler(req: ApprovalRequest) -> bool:
        return False  # deny

    runner = AgentRunner(
        registry=registry,
        audit=audit,
        approval_policy=ApprovalPolicy(permission_mode=PermissionMode.PROMPT),
        approval_handler=handler,
    )

    result = runner.run(task='write', decide=lambda _: _WRITE_REQUEST)
    # After approval gate fix, denied approvals return pending_approval instead of failed
    assert result.status == 'pending_approval', (
        f'expected pending_approval, got {result.status!r}'
    )
    assert any(e.event_type == 'tool_call_denied' for e in audit.events)


def test_blocked_in_read_only_mode():
    registry = _make_registry()
    audit = AuditLogger()
    runner = AgentRunner(
        registry=registry,
        audit=audit,
        approval_policy=ApprovalPolicy(permission_mode=PermissionMode.READ_ONLY),
    )

    result = runner.run(task='write', decide=lambda _: _WRITE_REQUEST)
    # After approval gate fix, read-only mode returns pending_approval instead of failed
    assert result.status == 'pending_approval'
    assert any(e.event_type == 'tool_call_blocked' for e in audit.events)


def test_empty_path_globs_rejected_ds12(tmp_path):
    """DS-12: Empty path globs are rejected to prevent implicit global grants."""
    store = ApprovalPresetStore(tmp_path)

    # Empty list should raise ValueError
    with pytest.raises(ValueError, match='must contain at least one non-empty pattern'):
        store.grant('workspace_write_file', path_globs=[])

    # Whitespace-only list should raise ValueError
    with pytest.raises(ValueError, match='must contain at least one non-empty pattern'):
        store.grant('workspace_write_file', path_globs=['  ', '\t'])

    # None is allowed for session-scope (temporary grants)
    grant = store.grant('workspace_write_file', path_globs=None, scope='session')
    assert grant.path_globs == ()

    # deny() without any explicit scope is rejected to avoid global denials
    with pytest.raises(ValueError, match='must be provided explicitly'):
        store.deny('workspace_write_file', path_globs=None)

    # Valid patterns should work
    grant = store.grant('workspace_write_file', path_globs=['src/**'])
    assert grant.path_globs == ('src/**',)


def test_approval_policy_rejects_empty_path(tmp_path):
    """DS-12: ApprovalPolicy-level path grant rejects empty and whitespace-only paths.

    Regression guard: empty-string or whitespace path_globs must never create an
    implicit global workspace grant that the user believes is path-scoped.
    """
    store = ApprovalPresetStore(tmp_path)

    # Empty string path in path_globs must be rejected for all non-session scopes
    for scope in ('always', 'once'):
        with pytest.raises(ValueError, match='non-empty pattern'):
            store.grant('workspace_write_file', path_globs=[''], scope=scope)

    # Whitespace-only entries must also be rejected (they strip to nothing)
    with pytest.raises(ValueError, match='non-empty pattern'):
        store.grant('workspace_write_file', path_globs=[' ', '\t', ''], scope='always')

    # None path_globs must be rejected for non-session scopes
    with pytest.raises(ValueError, match='must be provided explicitly'):
        store.grant('workspace_write_file', path_globs=None, scope='always')

    # session-scope with None is allowed (no path restriction for temporary grants)
    session_grant = store.grant(
        'workspace_write_file', path_globs=None, scope='session'
    )
    assert session_grant.path_globs == ()

    # A grant with a valid non-empty path works for session scope
    valid_grant = store.grant('workspace_write_file', path_globs=['src/**'])
    assert valid_grant.path_globs == ('src/**',)

    # For persistent scopes (always/once), both path_globs and command_prefixes must be explicit
    always_grant = store.grant(
        'workspace_write_file',
        path_globs=['src/**'],
        command_prefixes=['git'],
        scope='always',
    )
    assert always_grant.path_globs == ('src/**',)
    assert always_grant.command_prefixes == ('git',)


def test_approval_policy_normalizes_relative_paths(tmp_path):
    """DS-12: Relative paths in tool arguments are normalized before approval matching.

    Ensures ./foo resolves to 'foo' within workspace (not a traversal bypass),
    ../escape is rejected, and absolute paths outside workspace are rejected.
    """
    workspace = tmp_path
    (workspace / 'src').mkdir()
    (workspace / 'src' / 'main.py').touch()
    nested = workspace / 'a' / 'b'
    nested.mkdir(parents=True)

    # Relative ./src/main.py normalizes to src/main.py (within workspace)
    result = _normalize_and_validate_path('./src/main.py', workspace)
    assert result == 'src/main.py', f'expected src/main.py, got {result!r}'

    # Nested relative path normalizes correctly
    result = _normalize_and_validate_path('./a/b', workspace)
    assert result == 'a/b', f'expected a/b, got {result!r}'

    # Parent traversal is rejected — cannot escape workspace root
    result = _normalize_and_validate_path('../escape', workspace)
    assert result is None, '../escape must be rejected (path traversal)'

    result = _normalize_and_validate_path('../../etc/passwd', workspace)
    assert result is None, '../../etc/passwd must be rejected'

    # Embedded traversal is also rejected
    result = _normalize_and_validate_path('src/../../../etc/passwd', workspace)
    assert result is None, 'embedded traversal must be rejected'

    # Absolute path outside workspace is rejected
    result = _normalize_and_validate_path('/tmp/evil', workspace)
    assert result is None, 'absolute path outside workspace must be rejected'

    # Plain filename without traversal is accepted
    result = _normalize_and_validate_path('src/main.py', workspace)
    assert result == 'src/main.py'

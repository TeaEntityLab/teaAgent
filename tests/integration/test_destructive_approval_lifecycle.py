"""IT-12: Full destructive-tool approval lifecycle — pause, approve, deny, timeout.

Covers:
- ``pending_approval`` status on first run when no approval token present.
- Approved call_id allows the tool to execute on resume.
- Denied call_id raises and the run fails with permission error.
- Auto-approval via ``approval_handler`` callback.
"""

from __future__ import annotations

from teaagent.audit import AuditLogger
from teaagent.policy import ApprovalPolicy, PermissionMode
from teaagent.runner import AgentRunner, ApprovalRequest, FinalAnswer, ToolRequest
from teaagent.tools import ToolAnnotations, ToolRegistry


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


def test_resume_with_approved_call_id_completes():
    registry = _make_registry()
    audit = AuditLogger()
    runner = AgentRunner(
        registry=registry,
        audit=audit,
        approval_policy=ApprovalPolicy(
            permission_mode=PermissionMode.PROMPT,
            approved_call_ids=frozenset({'call-abc'}),
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
    assert result.status.startswith('failed'), f'expected failed, got {result.status!r}'
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
    assert result.status.startswith('failed')
    assert any(e.event_type == 'tool_call_blocked' for e in audit.events)

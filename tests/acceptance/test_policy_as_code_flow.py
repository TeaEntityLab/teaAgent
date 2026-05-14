"""AC-NEW-14: Policy-as-Code deny rule enforcement flow.

As a security lead, I want a ``policy.yaml`` deny-rule that blocks specific
tool calls regardless of permission mode, so that hard safety boundaries are
declarative and auditable.

Acceptance criteria:
- A ``policy.yaml`` in the workspace root is loaded automatically.
- Matching deny rules block the tool call and the run fails with a clear message.
- Non-matching tool calls are not affected.
- The rule fires regardless of the active ``PermissionMode``.
- Rules can match on both tool_pattern and argument_pattern simultaneously.
"""

from __future__ import annotations

from teaagent.audit import AuditLogger
from teaagent.file_policy import DenyRule, FilePolicy, load_file_policy
from teaagent.policy import ApprovalPolicy, PermissionMode
from teaagent.runner import AgentRunner, FinalAnswer, ToolRequest
from teaagent.tools import ToolAnnotations, ToolRegistry


def _make_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        name='workspace_run_shell_mutate',
        description='shell',
        input_schema={
            'type': 'object',
            'properties': {'command': {'type': 'string'}},
            'required': ['command'],
        },
        output_schema={'type': 'object', 'properties': {}},
        annotations=ToolAnnotations(destructive=True),
        handler=lambda _: {'exit_code': 0},
    )
    registry.register(
        name='workspace_read_file',
        description='read',
        input_schema={
            'type': 'object',
            'properties': {'path': {'type': 'string'}},
            'required': ['path'],
        },
        output_schema={'type': 'object', 'properties': {'content': {'type': 'string'}}},
        annotations=ToolAnnotations(read_only=True),
        handler=lambda _: {'content': 'hello'},
    )
    return registry


def test_policy_yaml_loaded_from_workspace(tmp_path):
    (tmp_path / 'policy.yaml').write_text(
        'version: 1\nrules:\n  - id: block-rm\n    tool_pattern: "workspace_run_shell_*"\n    action: deny\n    message: "rm blocked by policy"\n',
        encoding='utf-8',
    )
    policy = load_file_policy(tmp_path)
    assert len(policy.rules) == 1
    assert policy.rules[0].id == 'block-rm'


def test_deny_rule_blocks_matching_tool_in_runner(tmp_path):
    policy = FilePolicy(
        rules=[
            DenyRule(
                id='block-shell',
                tool_pattern='workspace_run_shell_*',
                message='shell blocked',
            )
        ]
    )
    audit = AuditLogger()
    runner = AgentRunner(
        registry=_make_registry(),
        audit=audit,
        approval_policy=ApprovalPolicy(permission_mode=PermissionMode.ALLOW),
        file_policy=policy,
    )

    result = runner.run(
        task='run shell',
        decide=lambda _: ToolRequest(
            tool_name='workspace_run_shell_mutate',
            arguments={'command': 'ls'},
            call_id='c1',
        ),
    )
    assert result.status.startswith('failed')
    # run_failed must be in audit
    failed_events = [e for e in audit.events if e.event_type == 'run_failed']
    assert failed_events


def test_deny_rule_does_not_block_non_matching_tool():
    policy = FilePolicy(
        rules=[
            DenyRule(
                id='block-shell',
                tool_pattern='workspace_run_shell_*',
                message='shell blocked',
            )
        ]
    )
    audit = AuditLogger()
    runner = AgentRunner(
        registry=_make_registry(),
        audit=audit,
        approval_policy=ApprovalPolicy(permission_mode=PermissionMode.ALLOW),
        file_policy=policy,
    )

    call_seq = iter(
        [
            ToolRequest(
                tool_name='workspace_read_file',
                arguments={'path': 'README.md'},
                call_id='c2',
            ),
            FinalAnswer(content='read done'),
        ]
    )
    result = runner.run(task='read file', decide=lambda _: next(call_seq))
    assert result.status == 'completed'


def test_deny_rule_fires_in_danger_full_access_mode():
    """Even danger-full-access mode must be blocked by file policy."""
    policy = FilePolicy(
        rules=[
            DenyRule(
                id='hard-block',
                tool_pattern='workspace_run_shell_mutate',
                argument_pattern={'command': 'rm*'},
                message='rm always blocked',
            )
        ]
    )
    audit = AuditLogger()
    runner = AgentRunner(
        registry=_make_registry(),
        audit=audit,
        approval_policy=ApprovalPolicy(
            permission_mode=PermissionMode.DANGER_FULL_ACCESS
        ),
        file_policy=policy,
    )

    result = runner.run(
        task='delete',
        decide=lambda _: ToolRequest(
            tool_name='workspace_run_shell_mutate',
            arguments={'command': 'rm -rf /'},
            call_id='c3',
        ),
    )
    assert result.status.startswith('failed')

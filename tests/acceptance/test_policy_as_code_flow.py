"""Test module for policy-as-code deny rule enforcement.

This module tests the policy-as-code system, which enables declarative security
policies that block specific tool calls regardless of permission mode. This provides
hard safety boundaries that are auditable and version-controlled, complementing the
runtime permission mode system with additional declarative constraints.

Key concepts tested:
- Policy File Loading: policy.yaml in workspace root is loaded automatically
- Deny Rule Matching: Rules match on tool_pattern and argument_pattern
- Rule Enforcement: Matching rules block tool calls with clear error messages
- Permission Mode Independence: Rules fire regardless of active PermissionMode
- Pattern Matching: Rules can match both tool names and argument values
- Danger Mode Override: Even DANGER_FULL_ACCESS mode is blocked by policy

Acceptance Criteria:
- AC1: policy.yaml in workspace root is loaded automatically
- AC2: Matching deny rules block the tool call and the run fails with a clear message
- AC3: Non-matching tool calls are not affected by deny rules
- AC4: The rule fires regardless of the active PermissionMode
- AC5: Rules can match on both tool_pattern and argument_pattern simultaneously
- AC6: Even DANGER_FULL_ACCESS mode is blocked by deny rules (hard safety boundary)

Technical Details:
- FilePolicy loads deny rules from policy.yaml
- DenyRule specifies tool_pattern, argument_pattern, and message
- AgentRunner enforces file_policy before tool execution
- Rules are evaluated before permission mode checks
- Pattern matching uses glob-style patterns for tool names
- Argument pattern matching supports simple string matching
- Policy violations result in pending_approval status with error message

References:
- Policy-as-code design: /docs/architecture/policy_as_code.md
- Security boundaries: /docs/security/hard_boundaries.md
- Policy file format: /docs/specs/policy_yaml_format.md
"""

from __future__ import annotations

from teaagent.file_policy import DenyRule, FilePolicy, load_file_policy
from teaagent.policy import ApprovalPolicy
from teaagent.runner import AgentRunner, FinalAnswer, ToolRequest
from teaagent.types import AuditLogger, PermissionMode, ToolAnnotations, ToolRegistry


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
    user_rule_ids = [r.id for r in policy.rules if r.id == 'block-rm']
    # Verify user-defined rule was loaded
    assert len(user_rule_ids) == 1, (
        f'Expected exactly 1 user rule with id "block-rm", got {len(user_rule_ids)}'
    )
    all_ids = [r.id for r in policy.rules]
    # Verify block-rm rule is in the loaded policy
    assert 'block-rm' in all_ids, (
        f'Expected "block-rm" to be in loaded policy rules, got {all_ids}'
    )


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
    # Verify matching tool is blocked by policy
    assert result.status == 'pending_approval', (
        f'Expected status "pending_approval" when tool is blocked by policy, got {result.status!r}'
    )
    # Verify error message contains policy rule message
    assert 'shell blocked' in result.error_message, (
        f'Expected error message to contain "shell blocked", got {result.error_message!r}'
    )
    # Verify metadata is empty approval dict
    assert result.metadata == {'approval': {}}, (
        f'Expected empty approval metadata, got {result.metadata}'
    )
    # Verify audit events stopped at iteration_started (tool was blocked)
    assert [e.event_type for e in audit.events] == [
        'run_started',
        'iteration_started',
    ], (
        f'Expected audit events to stop at iteration_started, got {[e.event_type for e in audit.events]}'
    )


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
    # Verify non-matching tool is not blocked by policy
    assert result.status == 'completed', (
        f'Expected status "completed" for non-matching tool, got {result.status!r}'
    )


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
    # Verify policy blocks tool even in DANGER_FULL_ACCESS mode (hard safety boundary)
    assert result.status == 'pending_approval', (
        f'Expected status "pending_approval" even in DANGER_FULL_ACCESS mode, got {result.status!r}'
    )
    # Verify error message contains policy rule message
    assert 'rm always blocked' in result.error_message, (
        f'Expected error message to contain "rm always blocked", got {result.error_message!r}'
    )
    # Verify metadata is empty approval dict
    assert result.metadata == {'approval': {}}, (
        f'Expected empty approval metadata, got {result.metadata}'
    )
    # Verify audit events stopped at iteration_started (tool was blocked)
    assert [e.event_type for e in audit.events] == [
        'run_started',
        'iteration_started',
    ], (
        f'Expected audit events to stop at iteration_started, got {[e.event_type for e in audit.events]}'
    )

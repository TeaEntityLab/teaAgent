"""IT-7: FilePolicy deny rules block tool calls before ApprovalPolicy.

Covers: rule matching, argument_pattern glob, tool_pattern glob, rule ordering
(first match wins), empty policy (allow all), loading from .teaagent/policy.yaml
and workspace root policy.yaml.
"""

from __future__ import annotations

import pytest

from teaagent.errors import ToolPermissionError
from teaagent.file_policy import DenyRule, FilePolicy, load_file_policy

# ── unit: DenyRule matching ────────────────────────────────────────────────


def test_deny_rule_matches_exact_tool():
    rule = DenyRule(id='r1', tool_pattern='workspace_run_shell_mutate')
    assert rule.matches('workspace_run_shell_mutate', {})
    assert not rule.matches('workspace_run_shell_inspect', {})


def test_deny_rule_matches_glob_tool():
    rule = DenyRule(id='r2', tool_pattern='workspace_run_shell_*')
    assert rule.matches('workspace_run_shell_mutate', {})
    assert rule.matches('workspace_run_shell_inspect', {})
    assert not rule.matches('workspace_read_file', {})


def test_deny_rule_matches_argument_pattern():
    rule = DenyRule(
        id='r3',
        tool_pattern='workspace_run_shell_mutate',
        argument_pattern={'command': 'rm -rf*'},
    )
    assert rule.matches('workspace_run_shell_mutate', {'command': 'rm -rf /'})
    assert not rule.matches('workspace_run_shell_mutate', {'command': 'ls .'})


def test_deny_rule_argument_key_missing_does_not_match():
    rule = DenyRule(
        id='r4',
        tool_pattern='*',
        argument_pattern={'path': 'prod_*'},
    )
    assert not rule.matches('workspace_write_file', {'data': 'hello'})


# ── unit: FilePolicy.assert_allowed ────────────────────────────────────────


def test_file_policy_empty_allows_all():
    policy = FilePolicy()
    # Must not raise
    policy.assert_allowed(
        tool_name='workspace_run_shell_mutate', arguments={'command': 'rm -rf /'}
    )


def test_file_policy_blocks_matching_rule():
    policy = FilePolicy(
        rules=[
            DenyRule(
                id='block-rm', tool_pattern='workspace_run_shell_*', message='blocked'
            )
        ]
    )
    with pytest.raises(ToolPermissionError, match='blocked'):
        policy.assert_allowed(tool_name='workspace_run_shell_mutate', arguments={})


def test_file_policy_first_match_wins():
    rules = [
        DenyRule(
            id='block-1', tool_pattern='workspace_run_shell_*', message='first rule'
        ),
        DenyRule(
            id='block-2', tool_pattern='workspace_run_shell_*', message='second rule'
        ),
    ]
    policy = FilePolicy(rules=rules)
    with pytest.raises(ToolPermissionError, match='first rule'):
        policy.assert_allowed(tool_name='workspace_run_shell_mutate', arguments={})


# ── integration: load_file_policy ──────────────────────────────────────────


def test_load_file_policy_no_file(tmp_path):
    policy = load_file_policy(tmp_path)
    assert policy.rules == []
    assert policy.source_path is None


def test_load_file_policy_from_workspace_root(tmp_path):
    (tmp_path / 'policy.yaml').write_text(
        'version: 1\nrules:\n  - id: block-all\n    tool_pattern: "*"\n    action: deny\n    message: "all blocked"\n',
        encoding='utf-8',
    )
    policy = load_file_policy(tmp_path)
    assert len(policy.rules) == 1
    assert policy.rules[0].id == 'block-all'


def test_load_file_policy_from_teaagent_dir(tmp_path):
    dot_dir = tmp_path / '.teaagent'
    dot_dir.mkdir()
    (dot_dir / 'policy.yaml').write_text(
        'version: 1\nrules:\n  - id: inner\n    tool_pattern: "workspace_write_file"\n    action: deny\n',
        encoding='utf-8',
    )
    policy = load_file_policy(tmp_path)
    assert len(policy.rules) == 1
    assert policy.rules[0].id == 'inner'


def test_load_file_policy_json_format(tmp_path):
    import json

    data = {
        'version': 1,
        'rules': [
            {
                'id': 'json-rule',
                'tool_pattern': 'workspace_*',
                'action': 'deny',
                'message': 'json',
            }
        ],
    }
    (tmp_path / 'policy.json').write_text(json.dumps(data), encoding='utf-8')
    policy = load_file_policy(tmp_path)
    assert policy.rules[0].id == 'json-rule'


def test_file_policy_integrated_with_agent_runner(tmp_path):
    """FilePolicy.assert_allowed fires in AgentRunner before tool dispatch."""
    from teaagent.audit import AuditLogger
    from teaagent.runner import AgentRunner, FinalAnswer, ToolRequest
    from teaagent.tools import ToolAnnotations, ToolRegistry

    registry = ToolRegistry()
    registry.register(
        name='workspace_run_shell_mutate',
        description='shell mutate',
        input_schema={
            'type': 'object',
            'properties': {'command': {'type': 'string'}},
            'required': ['command'],
        },
        output_schema={'type': 'object', 'properties': {}},
        annotations=ToolAnnotations(destructive=True),
        handler=lambda _: {},
    )

    call_seq = iter(
        [
            ToolRequest(
                tool_name='workspace_run_shell_mutate',
                arguments={'command': 'rm -rf /'},
            ),
            FinalAnswer(content='done'),
        ]
    )

    policy = FilePolicy(
        rules=[
            DenyRule(
                id='block-rm',
                tool_pattern='workspace_run_shell_*',
                argument_pattern={'command': 'rm -rf*'},
                message='rm -rf is blocked',
            )
        ]
    )

    audit = AuditLogger()
    from teaagent.policy import ApprovalPolicy, PermissionMode

    runner = AgentRunner(
        registry=registry,
        audit=audit,
        approval_policy=ApprovalPolicy(
            permission_mode=PermissionMode.ALLOW,
        ),
        file_policy=policy,
    )

    result = runner.run(task='delete everything', decide=lambda _: next(call_seq))
    # The tool call should have been blocked by file_policy
    assert result.status.startswith('failed')
    blocked = [
        e for e in audit.events if e.event_type in ('tool_call_blocked', 'run_failed')
    ]
    assert blocked

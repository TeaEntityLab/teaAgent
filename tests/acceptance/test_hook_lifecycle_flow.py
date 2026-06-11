"""Test module for hook lifecycle and event interception.

This module tests the 8-event hook system that intercepts the agent tool lifecycle,
enabling custom logic at key points in agent execution. Hooks provide extensibility
for security policies, logging, result transformation, and other cross-cutting concerns.

Key concepts tested:
- PreToolUse Hooks: Can veto tool calls or modify arguments before execution
- PostToolUse Hooks: Can modify tool results after execution
- Hook Chaining: Multiple hooks run in registration order
- Permission Hooks: Enforce allow/deny patterns for tool access
- SessionStart Hooks: Fire at session initialization with context
- PreCompact Hooks: Can modify context before compaction
- Hook Registry: Manages hook registration and execution
- Hook Enablement: Hooks can be globally enabled/disabled

Acceptance Criteria:
- AC1: PreToolUse hook can veto a tool call by raising HookError
- AC2: PreToolUse hook can modify arguments before tool execution
- AC3: Multiple PreToolUse hooks run in registration order and pass-through when no veto
- AC4: PreToolUse hook error stops the chain (later hooks don't run)
- AC5: PostToolUse hook can modify the result of a tool call
- AC6: PostToolUse hook with no modification returns original result
- AC7: permission_check_hook with DENY mode blocks all destructive tools
- AC8: permission_check_hook with ALLOW mode passes through
- AC9: permission_check_hook with ASK mode respects deny_patterns
- AC10: permission_check_hook with ALLOW mode respects allow_patterns
- AC11: SessionStart hooks fire with correct session_id and context
- AC12: HookRegistry respects the enabled flag (disabled hooks don't run)
- AC13: PreCompact hooks can modify compaction context
- AC14: All 8 hook events exist in HookEvent enum

Technical Details:
- HookRegistry manages hook registration and execution
- HookError is raised to veto tool calls in PreToolUse hooks
- Hooks run in registration order (first registered runs first)
- permission_check_hook creates hooks for permission enforcement
- HookPermissionMode defines DENY, ALLOW, and ASK modes
- HookEvent enum defines 8 hook types: SessionStart, UserPromptSubmit, PreToolUse,
  PostToolUse, PreCompact, Stop, SubagentStop, SessionEnd
- HookRegistry.config.enabled controls global hook enablement

References:
- Hook system design: /docs/architecture/hook_system.md
- Hook lifecycle: /docs/specs/hook_lifecycle.md
- Security hooks: /docs/security/security_hooks.md
"""

from __future__ import annotations

import contextlib

import pytest

from teaagent.hooks import (
    HookError,
    HookPermissionMode,
    HookRegistry,
    permission_check_hook,
)


def test_pre_hook_veto_blocks_tool():
    registry = HookRegistry()

    def blocker(tool_name, arguments):
        raise HookError('blocked by policy')

    registry.register_pre_hook(blocker)
    try:
        registry.run_pre_hooks('workspace_write_file', {'path': 'x'})
    except HookError as e:
        assert 'blocked by policy' in str(e)
    else:
        raise AssertionError('expected HookError was not raised')


def test_pre_hook_can_modify_arguments():
    registry = HookRegistry()

    def inject_default(tool_name, arguments):
        if 'max_bytes' not in arguments:
            return dict(arguments, max_bytes=500)
        return None

    registry.register_pre_hook(inject_default)
    result = registry.run_pre_hooks('workspace_read_file', {'path': 'f.txt'})
    assert result is not None
    assert result.get('max_bytes') == 500


def test_multiple_pre_hooks_run_in_order():
    registry = HookRegistry()
    order = []

    def hook_a(tool_name, arguments):
        order.append('a')
        return None

    def hook_b(tool_name, arguments):
        order.append('b')
        return None

    registry.register_pre_hook(hook_a)
    registry.register_pre_hook(hook_b)
    registry.run_pre_hooks('workspace_read_file', {'path': 'x'})
    assert order == ['a', 'b']


def test_pre_hook_error_stops_chain():
    registry = HookRegistry()
    hit = []

    def first(tool_name, arguments):
        hit.append('first')
        raise HookError('stop')

    def second(tool_name, arguments):
        hit.append('second')
        return None

    registry.register_pre_hook(first)
    registry.register_pre_hook(second)
    with contextlib.suppress(HookError):
        registry.run_pre_hooks('workspace_write_file', {'path': 'x'})
    assert hit == ['first']


def test_post_hook_modifies_result():
    registry = HookRegistry()

    def add_metadata(tool_name, arguments, result):
        return dict(result, hook_processed=True)

    registry.register_post_hook(add_metadata)
    result = registry.run_post_hooks(
        'workspace_read_file',
        {'path': 'f.txt'},
        {'content': 'hello'},
    )
    assert result is not None
    assert result['hook_processed'] is True


def test_post_hook_no_modification_returns_original():
    registry = HookRegistry()

    def observer(tool_name, arguments, result):
        return None

    registry.register_post_hook(observer)
    result = registry.run_post_hooks(
        'workspace_read_file', {'path': 'x'}, {'content': 'y'}
    )
    assert result == {'content': 'y'}


def test_permission_check_deny_blocks_destructive():
    hook_fn = permission_check_hook(
        mode=HookPermissionMode.DENY,
        destructive_tools=frozenset(
            ['workspace_write_file', 'workspace_run_shell_mutate']
        ),
    )
    try:
        hook_fn('workspace_write_file', {'path': 'x'})
    except HookError as e:
        assert 'denied' in str(e).lower() or 'blocked' in str(e).lower()
    else:
        raise AssertionError('expected HookError for DENY mode')


def test_permission_check_allow_passes_destructive():
    hook_fn = permission_check_hook(
        mode=HookPermissionMode.ALLOW,
        destructive_tools=frozenset(['workspace_write_file']),
    )
    result = hook_fn('workspace_write_file', {'path': 'x'})
    assert result is None


def test_permission_check_deny_pattern():
    hook_fn = permission_check_hook(
        mode=HookPermissionMode.ASK,
        deny_patterns=['.git/*'],
        destructive_tools=frozenset(['workspace_write_file']),
    )
    with pytest.raises(HookError, match='matches denied pattern'):
        hook_fn('workspace_read_file', {'path': '.git/config'})


def test_permission_check_allow_pattern():
    hook_fn = permission_check_hook(
        mode=HookPermissionMode.ALLOW,
        allow_patterns=['src/*'],
        destructive_tools=frozenset(['workspace_write_file']),
    )
    result = hook_fn('workspace_write_file', {'path': 'src/main.py'})
    assert result is None


def test_session_start_hook_fires():
    registry = HookRegistry()
    fired = []

    def on_start(session_id, context):
        fired.append((session_id, context.get('key')))

    registry.register_session_start_hook(on_start)
    registry.run_session_start_hooks('sess-42', {'key': 'value'})
    assert fired == [('sess-42', 'value')]


def test_hook_registry_disabled_skips_pre_hooks():
    registry = HookRegistry()

    def blocker(tool_name, arguments):
        raise HookError('should not fire')

    registry.register_pre_hook(blocker)
    registry.config.enabled = False
    result = registry.run_pre_hooks('workspace_write_file', {'path': 'x'})
    assert result is None


def test_hook_registry_disabled_skips_post_hooks():
    registry = HookRegistry()

    def modifier(tool_name, arguments, result):
        return dict(result, touched=True)

    registry.register_post_hook(modifier)
    registry.config.enabled = False
    result = registry.run_post_hooks('workspace_read_file', {'path': 'x'}, {'val': 1})
    assert result is None


def test_pre_compact_hook_modifies_context():
    registry = HookRegistry()

    def compact_inject(context):
        return dict(context, compacted_by='hook')

    registry.register_pre_compact_hook(compact_inject)
    result = registry.run_pre_compact_hooks({'observations': []})
    assert result is not None
    assert result['compacted_by'] == 'hook'


def test_all_eight_hook_events_exist():
    from teaagent.hooks import HookEvent

    events = {e.value for e in HookEvent}
    assert 'SessionStart' in events
    assert 'UserPromptSubmit' in events
    assert 'PreToolUse' in events
    assert 'PostToolUse' in events
    assert 'PreCompact' in events
    assert 'Stop' in events
    assert 'SubagentStop' in events
    assert 'SessionEnd' in events
    assert len(HookEvent) == 8

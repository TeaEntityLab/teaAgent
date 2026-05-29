"""AC-NEW: Hook lifecycle acceptance test (elevated from integration).

Verifies that the 8-event hook system correctly intercepts the agent
tool lifecycle: PreToolUse can veto destructive operations, PostToolUse
can chain results, permission hooks enforce allow/deny patterns, and
multi-hook chaining preserves order.

Acceptance criteria:
- PreToolUse hook can veto a tool call by raising HookError.
- PostToolUse hook can modify the result of a tool call.
- Multiple PreToolUse hooks run in registration order and pass-through
  when no veto.
- permission_check_hook with DENY mode blocks all destructive tools.
- permission_check_hook with ALLOW mode passes through.
- SessionStart hooks fire with correct session_id and context.
- PreCompact hooks can modify compaction context.
- HookRegistry respects the enabled flag.
"""

from __future__ import annotations

import contextlib

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
    try:
        hook_fn('workspace_write_file', {'path': '.git/config'})
    except HookError:
        pass
    else:
        raise AssertionError('expected HookError for deny_pattern match')


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

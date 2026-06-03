"""Working example: 8-event hook lifecycle.

Demonstrates all eight hook events:
  SessionStart, UserPromptSubmit, PreToolUse, PostToolUse,
  PreCompact, Stop, SubagentStop, SessionEnd

Run without API keys:

    python3 docs/guides/examples/hooks_demo.py
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from teaagent.audit import AuditLogger
from teaagent.budget import RunBudget
from teaagent.hooks import (
    HookConfig,
    HookError,
    HookRegistry,
    format_check_hook,
    post_lint_check_hook,
)
from teaagent.policy import ApprovalPolicy, PermissionMode
from teaagent.runner import AgentRunner, FinalAnswer, ToolRequest
from teaagent.workspace_tools import build_workspace_tool_registry


# ── hook implementations ──────────────────────────────────────────────────────


def session_start_hook(session_id: str, context: dict[str, Any]) -> None:
    print(f'  [SessionStart]       session={session_id[:8]}')


def user_prompt_submit_hook(session_id: str, context: dict[str, Any]) -> None:
    task = context.get('task', '')
    print(f'  [UserPromptSubmit]   task={task!r:.40}')


def pre_tool_hook(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any] | None:
    print(f'  [PreToolUse]         tool={tool_name} args={list(arguments.keys())}')
    # Demonstrate modification: tag every write with metadata
    if 'content' in arguments:
        arguments = {
            **arguments,
            'content': arguments['content'] + '\n# written by agent',
        }
    return arguments  # return None to keep original unchanged


def post_tool_hook(
    tool_name: str, arguments: dict[str, Any], result: dict[str, Any]
) -> dict[str, Any] | None:
    print(f'  [PostToolUse]        tool={tool_name} result_keys={list(result.keys())}')
    return None  # no modification to result


def pre_compact_hook(context: dict[str, Any]) -> dict[str, Any] | None:
    print(f'  [PreCompact]         context_keys={list(context.keys())}')
    return None


def stop_hook(session_id: str, context: dict[str, Any]) -> None:
    print(f'  [Stop]               session={session_id[:8]}')


def subagent_stop_hook(session_id: str, context: dict[str, Any]) -> None:
    print(f'  [SubagentStop]       session={session_id[:8]}')


def session_end_hook(session_id: str, context: dict[str, Any]) -> None:
    print(f'  [SessionEnd]         session={session_id[:8]}')


# ── veto hook example ─────────────────────────────────────────────────────────


def no_delete_hook(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any] | None:
    """Veto any tool call that looks like a file deletion."""
    if 'delete' in tool_name.lower() or arguments.get('path', '').endswith('.py'):
        raise HookError(f'Deletion of Python files is not allowed: {tool_name}')
    return None


# ── demo ──────────────────────────────────────────────────────────────────────


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        workspace = Path(tmp)
        (workspace / 'hello.txt').write_text('Hello TeaAgent\n')

        # Wire all 8 hooks
        hook_reg = HookRegistry()
        hook_reg.register_session_start_hook(session_start_hook)
        hook_reg.register_user_prompt_submit_hook(user_prompt_submit_hook)
        hook_reg.register_pre_hook(pre_tool_hook)
        hook_reg.register_pre_hook(no_delete_hook)  # veto hook
        hook_reg.register_post_hook(post_tool_hook)
        hook_reg.register_pre_compact_hook(pre_compact_hook)
        hook_reg.register_stop_hook(stop_hook)
        hook_reg.register_subagent_stop_hook(subagent_stop_hook)
        hook_reg.register_session_end_hook(session_end_hook)

        # Add built-in quality-gate hooks
        hook_reg.register_post_hook(
            post_lint_check_hook(
                root=workspace,
                tools=frozenset({'workspace_write_file'}),
            )
        )

        registry = build_workspace_tool_registry(workspace)
        audit = AuditLogger(path=workspace / '.teaagent' / 'audit.jsonl')
        policy = ApprovalPolicy(permission_mode=PermissionMode.WORKSPACE_WRITE)

        step = [0]

        def decide(context):
            step[0] += 1
            if step[0] == 1:
                return ToolRequest(
                    tool_name='workspace_read_file',
                    arguments={'path': 'hello.txt'},
                )
            if step[0] == 2:
                return ToolRequest(
                    tool_name='workspace_write_file',
                    arguments={'path': 'output.txt', 'content': 'result\n'},
                )
            return FinalAnswer(content='done')

        print('Running agent with all 8 hooks registered:')
        runner = AgentRunner(
            registry=registry,
            audit=audit,
            budget=RunBudget(max_iterations=5, max_tool_calls=5),
            approval_policy=policy,
            hook_registry=hook_reg,
        )
        result = runner.run(task='read hello.txt then write output.txt', decide=decide)
        print(f'\nResult: {result.status}, {result.tool_calls} tool calls')


if __name__ == '__main__':
    main()

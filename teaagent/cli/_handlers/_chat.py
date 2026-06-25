"""Interactive chat REPL handler for teaagent.

This module provides the chat command which delegates to the TUI (``run_tui``).
The legacy ``run_chat_repl`` REPL was retired (U-P2-1); its sole live piece,
``suspend_to_background``, now lives in ``cli._handlers._agent.resume``.
"""

from __future__ import annotations

import argparse
import logging

from teaagent.approval import parse_permission_mode

logger = logging.getLogger(__name__)


def chat_command(args: argparse.Namespace) -> int:
    """Run the interactive chat REPL (delegates to the TUI via ``run_tui``)."""
    from teaagent.tui import run_tui

    provider: str | None = getattr(args, 'provider', None) or None
    model: str | None = getattr(args, 'model', None) or None
    allow_destructive = getattr(args, 'allow_destructive', False)
    permission_mode_str: str = getattr(args, 'permission_mode', 'prompt') or 'prompt'
    max_iterations = getattr(args, 'max_iterations', 10)
    max_tool_calls = getattr(args, 'max_tool_calls', 10)
    max_estimated_cost_cents = getattr(args, 'max_estimated_cost_cents', 500)
    enable_subagent = getattr(args, 'subagent', False)
    max_subagent_depth = getattr(args, 'max_subagent_depth', 1)
    heartbeat_seconds = getattr(args, 'heartbeat', 0.0)
    stream = getattr(args, 'stream', False)
    enable_git_tools = getattr(args, 'enable_git_tools', False)
    skill_search_dirs = getattr(args, 'skill_search_dirs', None)
    memory_limit_arg = getattr(args, 'memory_limit', None)
    memory_limit = memory_limit_arg if memory_limit_arg is not None else 5
    # TASK-DD2-001: the chat parser registers `task` as a positional optional
    # (add_agent_run_arguments include_task_positional=True in _agent_parsers.py).
    # Previously this value was never read here, so `teaagent chat "my task"`
    # silently dropped the task and opened an empty REPL instead.
    initial_task: str | None = getattr(args, 'task', None) or None

    try:
        return run_tui(
            database=':memory:',
            provider=provider,
            model=model,
            root=args.root if hasattr(args, 'root') else '.',
            allow_destructive=allow_destructive,
            permission_mode=parse_permission_mode(permission_mode_str),
            chat=True,
            input_fn=None,
            run_setup=False,
            setup_write_env=False,
            stream=stream,
            subagent=enable_subagent,
            max_iterations=max_iterations,
            max_tool_calls=max_tool_calls,
            max_subagent_depth=max_subagent_depth,
            heartbeat_seconds=heartbeat_seconds,
            enable_git_tools=enable_git_tools,
            skill_search_dirs=skill_search_dirs,
            memory_limit=memory_limit,
            max_estimated_cost_cents=max_estimated_cost_cents,
            initial_task=initial_task,
        )
    except KeyboardInterrupt:
        return 130
    except Exception:
        logger.error('Unhandled exception in chat REPL', exc_info=True)
        return 1

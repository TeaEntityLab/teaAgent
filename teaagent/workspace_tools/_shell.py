from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path
from typing import Any

from teaagent.workspace_tools._config import WorkspaceToolConfig
from teaagent.workspace_tools._helpers import (
    assert_shell_command_size_allowed,
    bounded_positive_int_arg,
    truncate_output,
)


def run_shell(config: WorkspaceToolConfig, args: dict[str, Any]) -> dict[str, Any]:
    command = args['command']
    assert_shell_command_size_allowed(config, command)
    timeout = bounded_positive_int_arg(
        args,
        'timeout_seconds',
        default=config.command_timeout_seconds,
        maximum=config.max_shell_timeout_seconds,
    )
    # Create a safe environment with sanitized pager settings
    env = {
        **os.environ,
        'PAGER': 'cat',
        'GIT_PAGER': 'cat',
    }
    result = subprocess.run(
        command,
        cwd=str(config.root),
        shell=True,
        text=True,
        capture_output=True,
        timeout=timeout,
        env=env,
    )
    return {
        'stdout': truncate_output(result.stdout, config.max_shell_output_bytes),
        'stderr': truncate_output(result.stderr, config.max_shell_output_bytes),
        'exit_code': result.returncode,
    }


def run_shell_argv(
    config: WorkspaceToolConfig, argv: list[str], *, timeout_seconds: int
) -> dict[str, Any]:
    # Create a safe environment with sanitized pager settings
    env = {
        **os.environ,
        'PAGER': 'cat',
        'GIT_PAGER': 'cat',
    }
    result = subprocess.run(
        argv,
        cwd=str(config.root),
        shell=False,
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        env=env,
    )
    return {
        'stdout': truncate_output(result.stdout, config.max_shell_output_bytes),
        'stderr': truncate_output(result.stderr, config.max_shell_output_bytes),
        'exit_code': result.returncode,
    }


def run_shell_inspect(
    config: WorkspaceToolConfig, args: dict[str, Any]
) -> dict[str, Any]:
    command = args['command']
    assert_shell_command_size_allowed(config, command)
    policy = classify_shell_command_policy(command)
    if policy != 'inspect':
        raise ValueError(
            'command is not inspect-safe; retry with workspace_run_shell_mutate'
        )
    timeout = bounded_positive_int_arg(
        args,
        'timeout_seconds',
        default=config.command_timeout_seconds,
        maximum=config.max_shell_timeout_seconds,
    )
    return run_shell_argv(config, shlex.split(command), timeout_seconds=timeout)


def classify_shell_command_policy(
    command: str, workspace_root: Path | None = None
) -> str:
    try:
        parts = shlex.split(command.strip())
    except ValueError:
        return 'mutate'
    if not parts:
        return 'mutate'
    if _has_unquoted_shell_operator(command):
        return 'mutate'
    if any(shell_arg_escapes_workspace(arg, workspace_root) for arg in parts[1:]):
        return 'mutate'
    if _is_allowed_inspect_argv(parts):
        return 'inspect'
    return 'mutate'


_INSPECT_EXECUTABLES = frozenset(
    {'pwd', 'ls', 'rg', 'grep', 'cat', 'head', 'tail', 'wc'}
)
_INSPECT_GIT_SUBCOMMANDS = frozenset(
    {'status', 'diff', 'log', 'show', 'branch', 'grep'}
)
_DANGEROUS_FIND_FLAGS = frozenset(
    {'-delete', '-exec', '-execdir', '-ok', '-okdir', '-fprint', '-fprint0', '-fprintf'}
)
_DANGEROUS_RG_FLAGS = frozenset({'--pre', '--pre-open', '--open-files-in-viewer', '-O'})
_DANGEROUS_GIT_FLAGS = frozenset({'--output', '-o'})


def _is_allowed_inspect_argv(parts: list[str]) -> bool:
    executable = parts[0]
    if executable in _INSPECT_EXECUTABLES:
        # Check for dangerous flags in allowed executables
        if executable == 'rg':
            return not any(
                arg in _DANGEROUS_RG_FLAGS
                or any(arg.startswith(dangerous) for dangerous in _DANGEROUS_RG_FLAGS)
                for arg in parts[1:]
            )
        return True
    if executable == 'find':
        return not any(arg in _DANGEROUS_FIND_FLAGS for arg in parts[1:])
    if executable == 'git' and len(parts) > 1:
        if any(arg.startswith('-c') or arg.startswith('--config') for arg in parts[1:]):
            return False
        # Check for dangerous git flags (both exact match and prefix match)
        if any(
            arg in _DANGEROUS_GIT_FLAGS
            or any(arg.startswith(dangerous) for dangerous in _DANGEROUS_GIT_FLAGS)
            for arg in parts[1:]
        ):
            return False
        return parts[1] in _INSPECT_GIT_SUBCOMMANDS
    return False


def _has_unquoted_shell_operator(command: str) -> bool:
    in_single = False
    in_double = False
    i = 0
    n = len(command)
    while i < n:
        ch = command[i]
        if in_single:
            if ch == "'" and (i == 0 or command[i - 1] != '\\'):
                in_single = False
        elif in_double:
            if ch == '"' and (i == 0 or command[i - 1] != '\\'):
                in_double = False
        else:
            if ch == "'":
                in_single = True
            elif ch == '"':
                in_double = True
            elif (
                ch in ('>', '<', '|', '&', ';', '`')
                or ch == '$'
                and i + 1 < n
                and command[i + 1] == '('
            ):
                return True
        i += 1
    return False


def shell_arg_escapes_workspace(arg: str, workspace_root: Path | None = None) -> bool:
    # Check the basic pattern-based escapes first
    if (
        arg.startswith(('/', '~'))
        or arg == '..'
        or arg.startswith('../')
        or '/../' in arg
    ):
        return True

    # Only perform symlink resolution if workspace_root is provided
    # This prevents false positives on legitimate relative paths
    if workspace_root is not None:
        try:
            # Resolve the argument to its canonical form to detect symlinks
            resolved_path = Path(arg).expanduser().resolve()
            # Check if the resolved path is absolute (escapes relative workspace)
            if resolved_path.is_absolute():
                return True
            # Check if the resolved path still contains parent directory references after resolution
            if '..' in resolved_path.parts:
                return True
            # Check if resolved path is within workspace root
            try:
                resolved_path.relative_to(workspace_root.resolve())
            except ValueError:
                # Path is not within workspace root
                return True
        except (OSError, ValueError):
            # If path resolution fails, treat it as potentially unsafe
            return True

    return False

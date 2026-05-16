"""Pre/post action hooks for tool execution quality gates."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


class HookError(Exception):
    """Raised by a pre-hook to veto a tool call."""


class PreHookFn(Protocol):
    def __call__(self, tool_name: str, arguments: dict[str, Any]) -> None: ...


class PostHookFn(Protocol):
    def __call__(
        self, tool_name: str, arguments: dict[str, Any], result: dict[str, Any]
    ) -> None: ...


@dataclass
class HookConfig:
    """Configuration for hook execution."""

    pre_hooks: list[PreHookFn] = field(default_factory=list)
    post_hooks: list[PostHookFn] = field(default_factory=list)
    enabled: bool = True


@dataclass
class HookRegistry:
    """Manages pre/post action hooks for tool execution."""

    config: HookConfig = field(default_factory=HookConfig)

    def register_pre_hook(self, fn: PreHookFn) -> None:
        self.config.pre_hooks.append(fn)

    def register_post_hook(self, fn: PostHookFn) -> None:
        self.config.post_hooks.append(fn)

    def run_pre_hooks(self, tool_name: str, arguments: dict[str, Any]) -> None:
        if not self.config.enabled:
            return
        for hook in self.config.pre_hooks:
            hook(tool_name, arguments)

    def run_post_hooks(
        self, tool_name: str, arguments: dict[str, Any], result: dict[str, Any]
    ) -> None:
        if not self.config.enabled:
            return
        for hook in self.config.post_hooks:
            hook(tool_name, arguments, result)


# --- Built-in hooks ---


def lint_check_hook(
    root: Path,
    *,
    tools: frozenset[str] = frozenset(
        {
            'workspace_write_file',
            'workspace_apply_patch',
            'workspace_edit_at_hash',
            'git_commit',
        }
    ),
) -> PostHookFn:
    """Run a linter after destructive file tools.

    This is a POST hook despite the name -- it runs after the tool modifies files.
    Use ``post_lint_check_hook`` instead for clarity.
    """
    return post_lint_check_hook(root, tools=tools)


def post_lint_check_hook(
    root: Path,
    *,
    tools: frozenset[str] = frozenset(
        {
            'workspace_write_file',
            'workspace_apply_patch',
            'workspace_edit_at_hash',
            'git_commit',
        }
    ),
) -> PostHookFn:
    """Run linter after file-modifying tools. Raises ``HookError`` on failure."""

    def _hook(
        tool_name: str, arguments: dict[str, Any], result: dict[str, Any]
    ) -> None:
        if tool_name not in tools:
            return
        try:
            subprocess.run(
                ['ruff', 'check', str(root)],
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )
        except subprocess.CalledProcessError as exc:
            raise HookError(f'Lint check failed: {exc.stderr.strip()[:500]}') from exc
        except FileNotFoundError:
            pass  # ruff not installed, skip

    return _hook


def run_tests_hook(
    root: Path,
    *,
    tools: frozenset[str] = frozenset(
        {
            'workspace_write_file',
            'workspace_apply_patch',
            'workspace_edit_at_hash',
            'git_commit',
        }
    ),
    command: list[str] | None = None,
) -> PostHookFn:
    """Run tests after file-modifying tools. Raises ``HookError`` on failure."""
    cmd = command or ['uv', 'run', 'pytest', 'tests/', '-x', '-q']

    def _hook(
        tool_name: str, arguments: dict[str, Any], result: dict[str, Any]
    ) -> None:
        if tool_name not in tools:
            return
        try:
            subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=120,
                cwd=root,
            )
        except subprocess.CalledProcessError as exc:
            raise HookError(f'Test run failed: {exc.stderr.strip()[:500]}') from exc
        except FileNotFoundError:
            pass

    return _hook


def format_check_hook(
    root: Path,
    *,
    tools: frozenset[str] = frozenset(
        {
            'workspace_write_file',
            'workspace_apply_patch',
            'workspace_edit_at_hash',
            'git_commit',
        }
    ),
) -> PostHookFn:
    """Run formatter after file-modifying tools."""
    cmd = ['ruff', 'format', str(root)]

    def _hook(
        tool_name: str, arguments: dict[str, Any], result: dict[str, Any]
    ) -> None:
        if tool_name not in tools:
            return
        try:
            subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )
        except subprocess.CalledProcessError as exc:
            raise HookError(f'Format check failed: {exc.stderr.strip()[:500]}') from exc
        except FileNotFoundError:
            pass

    return _hook


def shell_command_hook(
    command: str,
    *,
    tools: frozenset[str] = frozenset(),
    on_tools: frozenset[str] = frozenset(),
) -> PostHookFn:
    """Run an arbitrary shell command after specified tools."""
    target_tools = tools or on_tools

    def _hook(
        tool_name: str, arguments: dict[str, Any], result: dict[str, Any]
    ) -> None:
        if target_tools and tool_name not in target_tools:
            return
        try:
            subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )
        except subprocess.CalledProcessError as exc:
            raise HookError(
                f'Shell hook failed ({command}): {exc.stderr.strip()[:500]}'
            ) from exc

    return _hook

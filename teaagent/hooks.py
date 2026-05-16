"""Pre/post action hooks for tool execution quality gates.

This module implements an 8-event hook lifecycle compatible with Claude Code:
- SessionStart: Before session begins
- UserPromptSubmit: After user message submitted
- PreToolUse: Before tool execution (can veto)
- PostToolUse: After tool execution
- PreCompact: Before context compaction
- Stop: Before session stops
- SubagentStop: After subagent completes
- SessionEnd: After session ends
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Protocol


class HookEvent(Enum):
    """Hook lifecycle events (Claude Code compatible)."""

    SESSION_START = 'SessionStart'
    USER_PROMPT_SUBMIT = 'UserPromptSubmit'
    PRE_TOOL_USE = 'PreToolUse'
    POST_TOOL_USE = 'PostToolUse'
    PRE_COMPACT = 'PreCompact'
    STOP = 'Stop'
    SUBAGENT_STOP = 'SubagentStop'
    SESSION_END = 'SessionEnd'


class HookError(Exception):
    """Raised by a pre-hook to veto a tool call."""


class PreToolUseHookFn(Protocol):
    """Pre-tool hook that can modify arguments or veto execution."""

    def __call__(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Return modified arguments, None to allow, or raise HookError to block."""


class PostToolUseHookFn(Protocol):
    """Post-tool hook that can modify result."""

    def __call__(
        self, tool_name: str, arguments: dict[str, Any], result: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Return modified result or None to keep original."""


class SessionHookFn(Protocol):
    """Session lifecycle hook."""

    def __call__(self, session_id: str, context: dict[str, Any]) -> None: ...


class PreCompactHookFn(Protocol):
    """Pre-compaction hook."""

    def __call__(self, context: dict[str, Any]) -> dict[str, Any] | None:
        """Return modified compaction context or None."""


@dataclass
class HookConfig:
    """Configuration for hook execution."""

    pre_hooks: list[PreToolUseHookFn] = field(default_factory=list)
    post_hooks: list[PostToolUseHookFn] = field(default_factory=list)
    session_start_hooks: list[SessionHookFn] = field(default_factory=list)
    session_end_hooks: list[SessionHookFn] = field(default_factory=list)
    user_prompt_submit_hooks: list[SessionHookFn] = field(default_factory=list)
    pre_compact_hooks: list[PreCompactHookFn] = field(default_factory=list)
    stop_hooks: list[SessionHookFn] = field(default_factory=list)
    subagent_stop_hooks: list[SessionHookFn] = field(default_factory=list)
    enabled: bool = True


@dataclass
class HookRegistry:
    """Manages 8-event hooks for tool execution (Claude Code compatible)."""

    config: HookConfig = field(default_factory=HookConfig)

    def register_pre_hook(self, fn: PreToolUseHookFn) -> None:
        self.config.pre_hooks.append(fn)

    def register_post_hook(self, fn: PostToolUseHookFn) -> None:
        self.config.post_hooks.append(fn)

    def register_session_start_hook(self, fn: SessionHookFn) -> None:
        self.config.session_start_hooks.append(fn)

    def register_session_end_hook(self, fn: SessionHookFn) -> None:
        self.config.session_end_hooks.append(fn)

    def register_user_prompt_submit_hook(self, fn: SessionHookFn) -> None:
        self.config.user_prompt_submit_hooks.append(fn)

    def register_pre_compact_hook(self, fn: PreCompactHookFn) -> None:
        self.config.pre_compact_hooks.append(fn)

    def register_stop_hook(self, fn: SessionHookFn) -> None:
        self.config.stop_hooks.append(fn)

    def register_subagent_stop_hook(self, fn: SessionHookFn) -> None:
        self.config.subagent_stop_hooks.append(fn)

    def run_pre_hooks(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Run PreToolUse hooks. Returns modified args or None. Raises HookError to block."""
        if not self.config.enabled:
            return None
        modified_args = arguments
        for hook in self.config.pre_hooks:
            result = hook(tool_name, modified_args)
            if result is not None:
                modified_args = result
        return modified_args

    def run_post_hooks(
        self, tool_name: str, arguments: dict[str, Any], result: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Run PostToolUse hooks. Returns modified result or None."""
        if not self.config.enabled:
            return None
        modified_result = result
        for hook in self.config.post_hooks:
            hook_result = hook(tool_name, arguments, modified_result)
            if hook_result is not None:
                modified_result = hook_result
        return modified_result

    def run_session_start_hooks(self, session_id: str, context: dict[str, Any]) -> None:
        if self.config.enabled:
            for hook in self.config.session_start_hooks:
                hook(session_id, context)

    def run_session_end_hooks(self, session_id: str, context: dict[str, Any]) -> None:
        if self.config.enabled:
            for hook in self.config.session_end_hooks:
                hook(session_id, context)

    def run_user_prompt_submit_hooks(
        self, session_id: str, context: dict[str, Any]
    ) -> None:
        if self.config.enabled:
            for hook in self.config.user_prompt_submit_hooks:
                hook(session_id, context)

    def run_pre_compact_hooks(self, context: dict[str, Any]) -> dict[str, Any] | None:
        if not self.config.enabled:
            return None
        modified_context = context
        for hook in self.config.pre_compact_hooks:
            result = hook(modified_context)
            if result is not None:
                modified_context = result
        return modified_context

    def run_stop_hooks(self, session_id: str, context: dict[str, Any]) -> None:
        if self.config.enabled:
            for hook in self.config.stop_hooks:
                hook(session_id, context)

    def run_subagent_stop_hooks(self, session_id: str, context: dict[str, Any]) -> None:
        if self.config.enabled:
            for hook in self.config.subagent_stop_hooks:
                hook(session_id, context)


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
) -> PostToolUseHookFn:
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
) -> PostToolUseHookFn:
    """Run linter after file-modifying tools. Raises ``HookError`` on failure."""

    def _hook(
        tool_name: str, arguments: dict[str, Any], result: dict[str, Any]
    ) -> dict[str, Any] | None:
        if tool_name not in tools:
            return None
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
        return None

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
) -> PostToolUseHookFn:
    """Run tests after file-modifying tools. Raises ``HookError`` on failure."""
    cmd = command or ['uv', 'run', 'pytest', 'tests/', '-x', '-q']

    def _hook(
        tool_name: str, arguments: dict[str, Any], result: dict[str, Any]
    ) -> dict[str, Any] | None:
        if tool_name not in tools:
            return None
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
        return None

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
) -> PostToolUseHookFn:
    """Run formatter after file-modifying tools."""
    cmd = ['ruff', 'format', str(root)]

    def _hook(
        tool_name: str, arguments: dict[str, Any], result: dict[str, Any]
    ) -> dict[str, Any] | None:
        if tool_name not in tools:
            return None
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
        return None

    return _hook


def shell_command_hook(
    command: str,
    *,
    tools: frozenset[str] = frozenset(),
    on_tools: frozenset[str] = frozenset(),
) -> PostToolUseHookFn:
    """Run an arbitrary shell command after specified tools."""
    target_tools = tools or on_tools

    def _hook(
        tool_name: str, arguments: dict[str, Any], result: dict[str, Any]
    ) -> dict[str, Any] | None:
        if target_tools and tool_name not in target_tools:
            return None
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
        return None

    return _hook


# --- Permission System Hooks (Claude Code compatible) ---


class PermissionMode(Enum):
    """Permission modes similar to Claude Code."""

    AUTO = 'auto'
    ASK = 'ask'
    ALLOW = 'allow'
    DENY = 'deny'


def permission_check_hook(
    mode: PermissionMode = PermissionMode.AUTO,
    *,
    allow_patterns: frozenset[str] = frozenset(),
    deny_patterns: frozenset[str] = frozenset(),
    destructive_tools: frozenset[str] = frozenset(
        {
            'workspace_write_file',
            'workspace_apply_patch',
            'workspace_edit_at_hash',
            'git_commit',
            'git_push',
            'shell',
        }
    ),
) -> PreToolUseHookFn:
    """Permission check hook that enforces Allow/Ask/Deny patterns."""

    def _hook(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any] | None:
        if mode == PermissionMode.ALLOW:
            return None
        if mode == PermissionMode.DENY:
            raise HookError(f"Tool '{tool_name}' is blocked by permission policy")

        if tool_name in destructive_tools:
            raise HookError(
                f"Tool '{tool_name}' requires explicit approval. "
                f'Current mode: {mode.value}. '
                f"Use 'teaagent config set permissions.auto_approve_destructive true' to enable."
            )

        if deny_patterns:
            path = arguments.get('path', '')
            for pattern in deny_patterns:
                if _match_glob(path, pattern):
                    raise HookError(f"Path '{path}' matches denied pattern '{pattern}'")

        if allow_patterns:
            path = arguments.get('path', '')
            for pattern in allow_patterns:
                if _match_glob(path, pattern):
                    return None
            if tool_name in destructive_tools:
                raise HookError(
                    f"Path '{path}' not in allowed patterns. "
                    f'Use --allow-patterns to whitelist paths.'
                )

        return None

    return _hook


def _match_glob(path: str, pattern: str) -> bool:
    """Simple glob matching for permission patterns."""
    import fnmatch

    if not pattern:
        return False
    return fnmatch.fnmatch(path, pattern)


# --- Context File Loading Hooks (CLAUDE.md/AGENTS.md support) ---


def context_file_loader_hook(
    root: Path,
) -> SessionHookFn:
    """Load CLAUDE.md/AGENTS.md files into session context."""

    def _hook(session_id: str, context: dict[str, Any]) -> None:
        from teaagent.prompt import load_project_instructions

        instructions = load_project_instructions(root)
        if instructions:
            context['project_instructions'] = instructions

    return _hook


# --- MCP Integration Hooks ---


def mcp_tool_filter_hook(
    allowed_tools: frozenset[str] = frozenset(),
    blocked_tools: frozenset[str] = frozenset(),
) -> PreToolUseHookFn:
    """Filter MCP tool calls based on allow/block lists."""

    def _hook(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any] | None:
        if blocked_tools and tool_name in blocked_tools:
            raise HookError(f"MCP tool '{tool_name}' is blocked")

        if allowed_tools and tool_name not in allowed_tools:
            raise HookError(
                f"MCP tool '{tool_name}' not in allowed list. "
                f'Allowed: {sorted(allowed_tools)}'
            )

        return None

    return _hook


def mcp_sampling_hook(
    max_tokens: int = 4096,
    temperature: float = 0.7,
) -> PreToolUseHookFn:
    """Apply sampling configuration to MCP tool calls."""

    def _hook(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any] | None:
        if tool_name.startswith('mcp_'):
            arguments.setdefault('_sampling', {})
            arguments['_sampling'].setdefault('max_tokens', max_tokens)
            arguments['_sampling'].setdefault('temperature', temperature)
        return None

    return _hook

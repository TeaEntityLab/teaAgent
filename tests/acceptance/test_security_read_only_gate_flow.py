"""Acceptance: read-only runtime gate blocks write tools."""

from __future__ import annotations

from teaagent.read_only_gate import (
    read_only_handler_block_reason,
    read_only_runtime_block_reason,
)


def _mutating_handler(x: int) -> int:
    x += 1
    return x


def _safe_handler(x: int) -> int:
    """A read-only handler."""
    return x * 2


class TestBedrockWriteToolNames:
    def test_workspace_write_file_blocked(self):
        reason = read_only_runtime_block_reason(
            tool_name='workspace_write_file',
            description='Write a file',
            read_only=None,
            destructive=True,
        )
        assert reason is not None
        assert 'blocked' in reason.lower()

    def test_workspace_apply_patch_blocked(self):
        reason = read_only_runtime_block_reason(
            tool_name='workspace_apply_patch',
            description='Apply patch',
            read_only=None,
            destructive=True,
        )
        assert reason is not None

    def test_workspace_edit_at_hash_blocked(self):
        reason = read_only_runtime_block_reason(
            tool_name='workspace_edit_at_hash',
            description='Edit file',
            read_only=None,
            destructive=True,
        )
        assert reason is not None


class TestShellMutateNames:
    def test_workspace_run_shell_mutate_blocked(self):
        reason = read_only_runtime_block_reason(
            tool_name='workspace_run_shell_mutate',
            description='Run shell',
            read_only=None,
            destructive=True,
        )
        assert reason is not None

    def test_workspace_run_shell_blocked(self):
        reason = read_only_runtime_block_reason(
            tool_name='workspace_run_shell',
            description='Run shell',
            read_only=None,
            destructive=True,
        )
        assert reason is not None


class TestReadOnlyFlagRequired:
    def test_destructive_tool_blocked(self):
        reason = read_only_runtime_block_reason(
            tool_name='custom_tool',
            description='A custom tool',
            read_only=None,
            destructive=True,
        )
        assert reason is not None

    def test_read_only_true_passes_with_safe_descriptor(self):
        reason = read_only_runtime_block_reason(
            tool_name='safe_tool',
            description='Read data from source',
            read_only=True,
            destructive=False,
        )
        assert reason is None

    def test_missing_read_only_declaration_blocked(self):
        reason = read_only_runtime_block_reason(
            tool_name='unknown_tool',
            description='Query something',
            read_only=None,
            destructive=False,
        )
        assert reason is not None
        assert 'read_only=true' in reason or 'Read-only' in reason


class TestReadOnlyHandlerBlockReason:
    def test_none_handler_returns_none(self):
        assert read_only_handler_block_reason('tool', None) is None

    def test_mutating_handler_source_detected(self):
        reason = read_only_handler_block_reason(
            'mutating_tool',
            _mutating_handler,
        )
        assert reason is not None

    def test_safe_handler_passes(self):
        reason = read_only_handler_block_reason(
            'safe_tool',
            _safe_handler,
        )
        assert reason is None

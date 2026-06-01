from __future__ import annotations

from teaagent.approval_manager import format_denial_message
from teaagent.errors import DenialReasonCode, ToolPermissionError


class TestPermissionExplain:
    def test_format_denial_read_only_mode(self) -> None:
        error = ToolPermissionError(
            "Tool 'workspace_delete_file' is destructive (delete action)",
            reason_code=DenialReasonCode.READ_ONLY_MODE,
        )
        message = format_denial_message(
            error,
            tool_name='workspace_delete_file',
            call_id='call-abc',
            permission_mode='read-only',
        )

        assert 'workspace_delete_file' in message
        assert 'read-only' in message
        assert 'Change mode' in message
        assert 'Learn more' in message

    def test_format_denial_jit_no_approval(self) -> None:
        error = ToolPermissionError(
            "Tool call 'call-xyz' for 'workspace_run_shell_mutate' requires explicit approval.",
            reason_code=DenialReasonCode.JIT_NO_APPROVAL,
        )
        message = format_denial_message(
            error,
            tool_name='workspace_run_shell_mutate',
            call_id='call-xyz',
            permission_mode='prompt',
        )

        assert 'workspace_run_shell_mutate' in message
        assert 'prompt' in message
        assert 'approve --call-id call-xyz' in message
        assert 'approve --tool workspace_run_shell_mutate --session' in message
        assert 'Learn more' in message

    def test_format_denial_workspace_write_mode(self) -> None:
        error = ToolPermissionError(
            "Tool 'workspace_run_shell_mutate' requires prompt/allow/danger-full-access permission mode.",
            reason_code=DenialReasonCode.WORKSPACE_WRITE_MODE,
        )
        message = format_denial_message(
            error,
            tool_name='workspace_run_shell_mutate',
            call_id='call-def',
            permission_mode='workspace-write',
        )

        assert 'workspace_write' in message or 'workspace-write' in message
        assert 'Change mode' in message

    def test_format_denial_includes_all_options_sections(self) -> None:
        error = ToolPermissionError(
            "Tool 'dangerous_tool' requires approval.",
            reason_code=DenialReasonCode.MISSING_STATE,
        )
        message = format_denial_message(
            error,
            tool_name='dangerous_tool',
            call_id='call-ghi',
            permission_mode='prompt',
        )

        assert '✗ Blocked:' in message
        assert 'Rule:' in message
        assert 'Why:' in message
        assert 'Options:' in message
        assert 'Learn more' in message
        assert 'Approval status' in message

    def test_format_denial_error_without_reason_code(self) -> None:
        error = ToolPermissionError('Blocked by file policy')
        message = format_denial_message(
            error,
            tool_name='some_tool',
            call_id='call-jkl',
            permission_mode='read-only',
        )

        assert 'Blocked by file policy' in message
        assert 'read-only' in message
        assert '✗ Blocked:' in message
        assert 'Options:' in message

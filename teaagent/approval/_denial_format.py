"""Operator-facing denial message formatting for blocked tool calls.

Pure function with no state. Moved unchanged from ``teaagent.approval.manager``
(A-P1-6 split, ADR-0044). ``teaagent.approval.manager`` re-exports the name.
"""

from __future__ import annotations

from teaagent.errors import DenialReasonCode, ToolPermissionError


def format_denial_message(
    error: ToolPermissionError,
    *,
    tool_name: str,
    call_id: str,
    permission_mode: str | None = None,
) -> str:
    """Produce a structured, actionable denial message for a blocked tool call.

    Generates remediation options based on the denial reason code so the
    user can immediately take corrective action.
    """
    reason_code = getattr(error, 'reason_code', None)
    mode = permission_mode or 'unknown'

    lines: list[str] = []
    lines.append(f'✗ Blocked: {tool_name}')
    lines.append(f'  Rule:    Permission mode = {mode}')
    lines.append(f'  Why:     {error}')
    lines.append('  Options:')

    idx = 1
    if reason_code in (
        DenialReasonCode.JIT_NO_APPROVAL,
        DenialReasonCode.MISSING_STATE,
    ):
        lines.append(
            f'    {idx}. Approve once:    teaagent approve --call-id {call_id}'
        )
        idx += 1
        lines.append(
            f'    {idx}. Approve session: teaagent approve --tool {tool_name} --session'
        )
        idx += 1

    if reason_code in (
        DenialReasonCode.READ_ONLY_MODE,
        DenialReasonCode.WORKSPACE_WRITE_MODE,
    ):
        lines.append(
            f'    {idx}. Change mode:     teaagent config set permission_mode prompt'
        )
        idx += 1

    lines.append(f'    {idx}. Learn more:      teaagent docs permissions')
    idx += 1
    lines.append(f'    {idx}. Approval status: teaagent approval check --root .')

    return '\n'.join(lines)

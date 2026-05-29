"""Read-only runtime tool gate (no imports from policy or governance package init)."""

from __future__ import annotations

_WRITE_TOOL_NAMES = frozenset(
    {
        'workspace_write_file',
        'workspace_apply_patch',
        'workspace_edit_at_hash',
    }
)
_SHELL_MUTATE_NAMES = frozenset(
    {
        'workspace_run_shell_mutate',
        'workspace_run_shell',
    }
)


def read_only_runtime_block_reason(
    *,
    tool_name: str,
    description: str,
    read_only: bool | None,
    destructive: bool,
) -> str | None:
    """Return a block message for read-only runs, or None if the tool may proceed."""
    if tool_name in _WRITE_TOOL_NAMES:
        return f"Tool '{tool_name}' is blocked by read-only permission mode."
    if tool_name in _SHELL_MUTATE_NAMES:
        return f"Tool '{tool_name}' is blocked by read-only permission mode."
    if destructive:
        return f"Tool '{tool_name}' is blocked by read-only permission mode."
    if read_only is not True:
        return (
            f"Tool '{tool_name}' must declare read_only=true to run in read-only mode."
        )
    from teaagent.governance.tool_lint import check_write_keywords_in_text

    keywords = check_write_keywords_in_text(description)
    if keywords:
        joined = ', '.join(keywords)
        return (
            f"Tool '{tool_name}' description suggests write operations ({joined}) "
            'and is blocked in read-only mode.'
        )
    return None

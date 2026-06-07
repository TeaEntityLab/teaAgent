"""Read-only runtime tool gate (no imports from policy or governance package init)."""

from __future__ import annotations

import functools
import inspect
from collections.abc import Callable
from typing import Any

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


def read_only_handler_block_reason(
    tool_name: str,
    handler: Callable[..., Any] | None,
) -> str | None:
    """Block read-only tools whose handler source suggests mutation."""
    if handler is None:
        return None
    # Unwrap functools.partial to get the underlying function for source inspection
    if isinstance(handler, functools.partial):
        handler = handler.func
    try:
        source = inspect.getsource(handler)
    except (OSError, TypeError):
        return (
            f"Tool '{tool_name}' handler source is unavailable; "
            'read-only runs cannot verify it is non-mutating.'
        )
    from teaagent.governance.tool_lint import fuzz_check_handler_code

    write_ops = fuzz_check_handler_code(source, is_read_only=True)
    if not write_ops:
        return None
    preview = ', '.join(write_ops[:5])
    suffix = '...' if len(write_ops) > 5 else ''
    return (
        f"Tool '{tool_name}' handler appears to perform write operations "
        f'({preview}{suffix}) and is blocked in read-only mode.'
    )


def read_only_runtime_block_reason(
    *,
    tool_name: str,
    description: str,
    read_only: bool | None,
    destructive: bool,
    handler: Callable[..., Any] | None = None,
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
    return read_only_handler_block_reason(tool_name, handler)

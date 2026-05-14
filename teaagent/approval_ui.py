"""Interactive approval handler with unified diff preview.

``DiffApprovalHandler`` implements the :data:`~teaagent.runner.ApprovalHandler`
protocol.  When a destructive tool call requires approval it:

1. Generates a unified diff for workspace write tools (``workspace_write_file``,
   ``workspace_apply_patch``, ``workspace_edit_at_hash``).
2. For other tools it displays a formatted argument summary.
3. Presents the diff or summary to the user and prompts ``[y/n/e]``.
4. Returns ``True`` (approve) or ``False`` (deny).

``e`` (explain) prints full tool metadata before re-prompting.

Usage::

    from teaagent.approval_ui import DiffApprovalHandler
    from teaagent.chat_agent import ChatAgentConfig

    handler = DiffApprovalHandler(workspace_root='/path/to/project')
    config = ChatAgentConfig.from_root(
        '/path/to/project',
        permission_mode=PermissionMode.PROMPT,
        approval_handler=handler,
    )
"""

from __future__ import annotations

import difflib
from collections.abc import Callable
from pathlib import Path
from typing import Any, Optional

from teaagent.runner import ApprovalRequest

_WRITE_FILE_TOOLS = frozenset(
    {
        'workspace_write_file',
        'workspace_apply_patch',
        'workspace_edit_at_hash',
    }
)

_PROMPT = '[y]es / [n]o / [e]xplain? '
_MAX_DIFF_LINES = 80


class DiffApprovalHandler:
    """Interactive HITL approval handler that shows a unified diff.

    Parameters
    ----------
    workspace_root:
        Project root used to resolve relative file paths.
    input_fn:
        Callable for reading user input (default: ``input``).
        Receives the prompt string and returns the user's response.
    output_fn:
        Callable for writing output lines (default: ``print``).
    max_prompts:
        Maximum number of times to re-prompt before auto-denying (default 5).
    """

    def __init__(
        self,
        workspace_root: str | Path,
        *,
        input_fn: Callable[[str], str] = input,
        output_fn: Callable[[str], None] = print,
        max_prompts: int = 5,
    ) -> None:
        self._root = Path(workspace_root).resolve()
        self._input = input_fn
        self._output = output_fn
        self._max_prompts = max_prompts

    # ------------------------------------------------------------------
    # ApprovalHandler protocol
    # ------------------------------------------------------------------

    def __call__(self, request: ApprovalRequest) -> bool:
        self._output('')
        self._output(f'  Tool: {request.tool_name}  (call_id: {request.call_id})')
        self._output(f'  Reason: {request.reason}')

        self._show_preview(request)

        for _attempt in range(self._max_prompts):
            try:
                response = self._input(_PROMPT).strip().lower()
            except (EOFError, KeyboardInterrupt):
                self._output('  Denied (no input).')
                return False

            if response in {'y', 'yes'}:
                return True
            if response in {'n', 'no'}:
                return False
            if response in {'e', 'explain'}:
                self._explain(request)
            else:
                self._output(f'  Unrecognised response {response!r}. Enter y, n, or e.')

        self._output('  Maximum prompts exceeded — denying automatically.')
        return False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _show_preview(self, request: ApprovalRequest) -> None:
        tool = request.tool_name
        args = request.arguments

        if tool == 'workspace_write_file':
            self._show_write_diff(args)
        elif tool == 'workspace_apply_patch':
            self._show_patch(args)
        elif tool == 'workspace_edit_at_hash':
            self._show_edit_diff(args)
        else:
            self._show_arg_summary(args)

    def _resolve_safe(self, rel_path: str) -> Optional[Path]:
        try:
            p = (self._root / rel_path).resolve()
            p.relative_to(self._root)
            return p
        except (ValueError, OSError):
            return None

    def _show_write_diff(self, args: dict[str, Any]) -> None:
        rel = args.get('path', '')
        new_content = args.get('content', '')
        if not isinstance(rel, str) or not rel:
            self._output('  (no path argument — showing tool summary)')
            return

        abs_path = self._resolve_safe(rel)
        if abs_path is None:
            self._output(f'  (path {rel!r} is outside workspace — diff suppressed)')
            return

        if abs_path.is_file():
            try:
                old_lines = abs_path.read_text(
                    encoding='utf-8', errors='replace'
                ).splitlines(True)
            except OSError:
                old_lines = []
            label = f'a/{rel}'
        else:
            old_lines = []
            label = '/dev/null'

        new_lines = (new_content or '').splitlines(True)
        diff = list(
            difflib.unified_diff(
                old_lines,
                new_lines,
                fromfile=label,
                tofile=f'b/{rel}',
                lineterm='',
            )
        )
        self._emit_diff(diff, rel)

    def _show_patch(self, args: dict[str, Any]) -> None:
        rel = args.get('path', '')
        patch = args.get('patch', '')
        if patch:
            self._output(f'  Patch for {rel}:')
            for line in str(patch).splitlines()[:_MAX_DIFF_LINES]:
                self._output(f'  {line}')
        else:
            self._output(f'  Apply patch to {rel}')

    def _show_edit_diff(self, args: dict[str, Any]) -> None:
        rel = args.get('path', '')
        old = args.get('old', '')
        new = args.get('new', '')
        old_lines = str(old).splitlines(True)
        new_lines = str(new).splitlines(True)
        diff = list(
            difflib.unified_diff(
                old_lines,
                new_lines,
                fromfile=f'a/{rel}',
                tofile=f'b/{rel}',
                lineterm='',
            )
        )
        self._emit_diff(diff, rel)

    def _show_arg_summary(self, args: dict[str, Any]) -> None:
        self._output('  Arguments:')
        for key, value in args.items():
            val_str = str(value)[:120]
            self._output(f'    {key}: {val_str}')

    def _emit_diff(self, diff: list[str], rel: str) -> None:
        if not diff:
            self._output(f'  (no diff for {rel})')
            return
        self._output(f'  Diff for {rel}:')
        for line in diff[:_MAX_DIFF_LINES]:
            self._output(f'  {line}')
        if len(diff) > _MAX_DIFF_LINES:
            self._output(f'  ... ({len(diff) - _MAX_DIFF_LINES} more lines)')

    def _explain(self, request: ApprovalRequest) -> None:
        self._output('')
        self._output(f'  Tool: {request.tool_name}')
        self._output(f'  call_id: {request.call_id}')
        self._output(f'  annotations: {request.annotations}')
        self._output('  Arguments:')
        for key, value in request.arguments.items():
            self._output(f'    {key}: {str(value)[:200]}')
        self._output('')

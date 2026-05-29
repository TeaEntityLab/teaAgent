"""Static lint for ToolRegistry contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from teaagent.tools import ToolDefinition, ToolRegistry

IssueLevel = Literal['error', 'warning']

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


@dataclass(frozen=True)
class ToolLintIssue:
    tool_name: str
    level: IssueLevel
    code: str
    message: str


def _lint_tool(tool: ToolDefinition) -> list[ToolLintIssue]:
    issues: list[ToolLintIssue] = []
    name = tool.name
    ann = tool.annotations
    schema = tool.input_schema
    out_schema = tool.output_schema

    if not schema or schema.get('type') != 'object':
        issues.append(
            ToolLintIssue(
                name,
                'error',
                'missing_input_schema',
                'input_schema must be a JSON object schema',
            )
        )
    if not out_schema or out_schema.get('type') != 'object':
        issues.append(
            ToolLintIssue(
                name,
                'error',
                'missing_output_schema',
                'output_schema must be a JSON object schema',
            )
        )
    if not tool.description.strip():
        issues.append(
            ToolLintIssue(
                name, 'error', 'missing_description', 'description is required'
            )
        )
    if ann.read_only and ann.destructive:
        issues.append(
            ToolLintIssue(
                name,
                'error',
                'contradictory_annotations',
                'read_only and destructive cannot both be true',
            )
        )
    if ann.read_only and name in _WRITE_TOOL_NAMES:
        issues.append(
            ToolLintIssue(
                name,
                'error',
                'mislabelled_write',
                'filesystem write tool must not be read_only',
            )
        )
    if ann.read_only and name in _SHELL_MUTATE_NAMES:
        issues.append(
            ToolLintIssue(
                name,
                'error',
                'mislabelled_shell',
                'shell mutate tool must not be read_only',
            )
        )
    if not ann.destructive and name in _WRITE_TOOL_NAMES | _SHELL_MUTATE_NAMES:
        issues.append(
            ToolLintIssue(
                name,
                'warning',
                'missing_destructive',
                'write/shell tools should declare destructive=true',
            )
        )
    if ann.destructive and ann.read_only:
        issues.append(
            ToolLintIssue(
                name,
                'error',
                'destructive_read_only',
                'destructive tools cannot be read_only',
            )
        )
    return issues


def lint_registry(registry: ToolRegistry) -> list[ToolLintIssue]:
    """Return lint issues for every tool in *registry*."""
    issues: list[ToolLintIssue] = []
    for name in sorted(registry.list_tools()):
        issues.extend(_lint_tool(registry.get(name)))
    return issues

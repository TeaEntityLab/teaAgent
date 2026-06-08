"""Static lint for ToolRegistry contracts."""

from __future__ import annotations

import ast
import functools
import inspect
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

# Keywords that suggest write operations in docstrings or code
_WRITE_KEYWORDS = frozenset(
    {
        'write',
        'save',
        'create',
        'delete',
        'remove',
        'modify',
        'update',
        'edit',
        'append',
        'overwrite',
        'truncate',
        'mkdir',
        'touch',
        'chmod',
        'chown',
    }
)


@dataclass(frozen=True)
class ToolLintIssue:
    tool_name: str
    level: IssueLevel
    code: str
    message: str


def check_write_keywords_in_text(text: str) -> list[str]:
    """Extract write-like keywords found in text."""
    found = []
    text_lower = text.lower()
    for keyword in _WRITE_KEYWORDS:
        if keyword in text_lower:
            found.append(keyword)
    return found


def _check_write_keywords_in_text(text: str) -> list[str]:
    return check_write_keywords_in_text(text)


_SUBPROCESS_METHODS = frozenset({'run', 'call', 'Popen', 'check_output', 'check_call'})
_OS_METHODS = frozenset(
    {
        'system',
        'popen',
        'remove',
        'unlink',
        'rename',
        'replace',
        'mkdir',
        'makedirs',
        'rmdir',
    }
)
_SHUTIL_METHODS = frozenset({'rmtree', 'move', 'copy', 'copy2', 'copyfile'})
_WRITE_METHODS = frozenset(
    {
        'write',
        'save',
        'create',
        'delete',
        'remove',
        'update',
        'edit',
        'append',
        'overwrite',
    }
)
_DANGEROUS_FUNCS = frozenset(
    {'open', 'mkdir', 'remove', 'rmdir', 'unlink', 'eval', 'exec', 'compile'}
)
_DYNAMIC_EVAL = frozenset({'eval', 'exec', 'compile'})


def _check_ast_attribute_call(mod_id: str, attr: str, node: ast.Call) -> list[str]:
    write_operations: list[str] = []
    if mod_id == 'subprocess' and attr in _SUBPROCESS_METHODS:
        write_operations.append(f'subprocess.{attr}()')
        if node.args and isinstance(node.args[0], (ast.Constant, ast.JoinedStr)):
            write_operations.append(f'subprocess.{attr}(string_cmd)')
    elif mod_id == 'os' and attr in _OS_METHODS:
        write_operations.append(f'os.{attr}()')
        if (
            attr == 'system'
            and node.args
            and isinstance(node.args[0], (ast.Constant, ast.JoinedStr))
        ):
            write_operations.append('os.system(string_cmd)')
    elif mod_id == 'shutil' and attr in _SHUTIL_METHODS:
        write_operations.append(f'shutil.{attr}()')
    elif attr in _WRITE_METHODS:
        write_operations.append(f'{attr}()')
    return write_operations


def _check_ast_call_node(node: ast.Call) -> list[str]:
    write_operations: list[str] = []
    if isinstance(node.func, ast.Attribute):
        if isinstance(node.func.value, ast.Name):
            write_operations.extend(
                _check_ast_attribute_call(node.func.value.id, node.func.attr, node)
            )
    elif isinstance(node.func, ast.Name) and node.func.id in _DANGEROUS_FUNCS:
        write_operations.append(f'{node.func.id}()')
        if (
            node.func.id in _DYNAMIC_EVAL
            and node.args
            and not isinstance(node.args[0], ast.Constant)
        ):
            write_operations.append(f'{node.func.id}(dynamic)')
    return write_operations


def fuzz_check_handler_code(handler_code: str, is_read_only: bool) -> list[str]:
    if not is_read_only:
        return []

    write_operations = []
    try:
        tree = ast.parse(handler_code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                write_operations.extend(_check_ast_call_node(node))
            elif isinstance(node, ast.AugAssign):
                write_operations.append('augmented_assignment')
    except (SyntaxError, ValueError):
        pass
    return write_operations


def _lint_tool(tool: ToolDefinition) -> list[ToolLintIssue]:  # noqa: C901
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

    # Static analysis: check for write-like keywords in description
    if ann.read_only:
        write_keywords = _check_write_keywords_in_text(tool.description)
        if write_keywords:
            issues.append(
                ToolLintIssue(
                    name,
                    'warning',
                    'read_only_with_write_keywords',
                    f'read_only tool description contains write-like keywords: {", ".join(write_keywords)}',
                )
            )
        try:
            handler = tool.handler
            if isinstance(handler, functools.partial):
                handler = handler.func
            handler_source = inspect.getsource(handler)
        except (OSError, TypeError):
            issues.append(
                ToolLintIssue(
                    name,
                    'warning',
                    'handler_source_unavailable',
                    'read_only tool handler source could not be inspected',
                )
            )
        else:
            write_ops = fuzz_check_handler_code(handler_source, is_read_only=True)
            if write_ops:
                preview = ', '.join(write_ops[:5])
                issues.append(
                    ToolLintIssue(
                        name,
                        'error',
                        'read_only_handler_mutation',
                        f'read_only handler appears to mutate ({preview})',
                    )
                )

    # Validate capability manifest if present
    if tool.capability_manifest:
        manifest_tier = tool.capability_manifest.get('security_tier')
        if manifest_tier not in {'Low', 'Medium', 'High', 'Critical'}:
            issues.append(
                ToolLintIssue(
                    name,
                    'error',
                    'invalid_security_tier',
                    f'capability manifest security_tier must be one of: Low, Medium, High, Critical (got: {manifest_tier})',
                )
            )

        # Check if manifest tier conflicts with calculated tier
        calculated_tier = tool.get_security_tier()
        if manifest_tier and manifest_tier != calculated_tier:
            issues.append(
                ToolLintIssue(
                    name,
                    'warning',
                    'security_tier_mismatch',
                    f'capability manifest security_tier ({manifest_tier}) differs from calculated tier ({calculated_tier}) based on annotations',
                )
            )

    # Stateful tools with side effects should declare governance annotations
    if ann.stateful and not ann.destructive and not ann.idempotent:
        issues.append(
            ToolLintIssue(
                name,
                'warning',
                'stateful_without_governance',
                f'Stateful tool with side effects: should declare explicit destructive=True or add capability-governance annotation. Tool: {name}',
            )
        )

    return issues


def lint_registry(registry: ToolRegistry) -> list[ToolLintIssue]:
    """Return lint issues for every tool in *registry*."""
    issues: list[ToolLintIssue] = []
    for name in sorted(registry.list_tools()):
        issues.extend(_lint_tool(registry.get(name)))
    return issues

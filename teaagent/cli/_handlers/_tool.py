"""CLI handlers for tool governance commands."""

from __future__ import annotations

import argparse
import json
from typing import Any

from teaagent.governance.tool_lint import lint_registry
from teaagent.tools import ToolRegistry
from teaagent.workspace_tools import build_workspace_tool_registry


def _print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def _registry_for_args(args: argparse.Namespace) -> ToolRegistry:
    if getattr(args, 'all', False):
        return build_workspace_tool_registry(args.root)
    return build_workspace_tool_registry(args.root)


def tool_list_command(args: argparse.Namespace) -> int:
    registry = _registry_for_args(args)
    tools = []
    for name in sorted(registry.list_tools()):
        tool = registry.get(name)
        tools.append(
            {
                'name': name,
                'description': tool.description,
                'annotations': {
                    'read_only': tool.annotations.read_only,
                    'destructive': tool.annotations.destructive,
                    'idempotent': tool.annotations.idempotent,
                },
            }
        )
    _print_json({'count': len(tools), 'tools': tools})
    return 0


def tool_inspect_command(args: argparse.Namespace) -> int:
    registry = _registry_for_args(args)
    try:
        tool = registry.get(args.name)
    except KeyError:
        _print_json({'ok': False, 'error': f"tool '{args.name}' not found"})
        return 1
    _print_json(
        {
            'name': tool.name,
            'description': tool.description,
            'input_schema': tool.input_schema,
            'output_schema': tool.output_schema,
            'annotations': {
                'read_only': tool.annotations.read_only,
                'destructive': tool.annotations.destructive,
                'idempotent': tool.annotations.idempotent,
            },
        }
    )
    return 0


def tool_lint_command(args: argparse.Namespace) -> int:
    registry = _registry_for_args(args)
    issues = lint_registry(registry)
    errors = [i for i in issues if i.level == 'error']
    warnings = [i for i in issues if i.level == 'warning']
    payload = {
        'ok': not errors,
        'error_count': len(errors),
        'warning_count': len(warnings),
        'issues': [
            {
                'tool_name': i.tool_name,
                'level': i.level,
                'code': i.code,
                'message': i.message,
            }
            for i in issues
        ],
    }
    _print_json(payload)
    if errors and getattr(args, 'strict', False):
        return 1
    return 1 if errors else 0

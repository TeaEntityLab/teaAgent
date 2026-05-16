"""Regression contract: file/workspace policy must always enforce boundaries.

This is an indestructible contract — if this test fails, path-escalation or
shell-injection attacks could bypass workspace isolation.
"""

from __future__ import annotations

from pathlib import Path

from teaagent.tools import ToolAnnotations, ToolRegistry
from teaagent.workspace_tools import build_workspace_tool_registry


def test_workspace_path_escape_blocked(tmp_path: Path) -> None:
    registry = build_workspace_tool_registry(root=tmp_path)
    raised = False
    try:
        registry.execute('workspace_read_file', {'path': '../outside.txt'})
    except Exception:
        raised = True
    assert raised, 'Path escape must be blocked'


def test_workspace_symlink_escape_blocked(tmp_path: Path) -> None:
    link = tmp_path / 'link'
    link.symlink_to('/etc/passwd')
    registry = build_workspace_tool_registry(root=tmp_path)
    raised = False
    try:
        registry.execute('workspace_read_file', {'path': str(link)})
    except Exception:
        raised = True
    assert raised, 'Symlink escape must be blocked'


def test_tool_execution_validates_input_schema(tmp_path: Path) -> None:
    registry = ToolRegistry()
    registry.register(
        name='strict_tool',
        description='requires a name argument',
        input_schema={
            'type': 'object',
            'properties': {'name': {'type': 'string'}},
            'required': ['name'],
        },
        output_schema={'type': 'object', 'properties': {}},
        annotations=ToolAnnotations(read_only=True),
        handler=lambda args: {},
    )
    raised = False
    try:
        registry.execute('strict_tool', {})
    except Exception:
        raised = True
    assert raised, 'Missing required field must fail validation'

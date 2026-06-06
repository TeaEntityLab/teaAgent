"""WS3-003 schema and path-containment coverage."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from teaagent.approval_manager import ApprovalManager, PermissionMode
from teaagent.errors import ToolExecutionError, ToolPermissionError, ToolValidationError
from teaagent.policy import ApprovalPolicy
from teaagent.tools import ToolAnnotations, ToolRegistry
from teaagent.workspace_tools import build_workspace_tool_registry


def test_generated_tool_validates_nested_schema() -> None:
    registry = ToolRegistry()
    registry.register(
        name='generated_nested',
        description='dynamic tool with nested args',
        input_schema={
            'type': 'object',
            'properties': {
                'item': {
                    'type': 'object',
                    'properties': {'name': {'type': 'string'}},
                    'required': ['name'],
                }
            },
            'required': ['item'],
        },
        output_schema={'type': 'object', 'properties': {'ok': {'type': 'boolean'}}},
        annotations=ToolAnnotations(read_only=True),
        handler=lambda args: {'ok': True},
    )
    registry.execute('generated_nested', {'item': {'name': 'ok'}})
    with pytest.raises(ToolValidationError):
        registry.execute('generated_nested', {'item': {'name': 1}})


def test_destructive_generated_tool_requires_approval() -> None:
    policy = ApprovalPolicy(
        permission_mode=PermissionMode.PROMPT,
        workspace_root='.',
    )
    with pytest.raises(ToolPermissionError):
        policy.assert_allowed(
            tool_name='generated_delete',
            call_id='call-1',
            destructive=True,
            arguments={'path': 'README.md'},
        )


def test_workspace_symlink_escape_blocked() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        link = root / 'escape-link'
        link.symlink_to('/etc/passwd')
        registry = build_workspace_tool_registry(root=root)
        with pytest.raises(ToolExecutionError, match='symlinks are not allowed'):
            registry.execute('workspace_read_file', {'path': 'escape-link'})


def test_approval_manager_blocks_path_outside_workspace() -> None:
    with TemporaryDirectory() as tmp:
        manager = ApprovalManager(
            permission_mode=PermissionMode.PROMPT,
            workspace_root=str(tmp),
        )
        with pytest.raises(ToolPermissionError, match='outside'):
            manager.assert_allowed(
                tool_name='workspace_write_file',
                call_id='call-outside',
                destructive=True,
                arguments={'path': '../outside.txt'},
            )


def test_approval_manager_blocks_symlink_target_outside_workspace() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        outside = root.parent / 'outside-target.txt'
        outside.write_text('secret', encoding='utf-8')
        link = root / 'link-out'
        link.symlink_to(outside)
        manager = ApprovalManager(
            permission_mode=PermissionMode.PROMPT,
            workspace_root=str(root),
        )
        with pytest.raises(ToolPermissionError, match='outside'):
            manager.assert_allowed(
                tool_name='workspace_write_file',
                call_id='call-link',
                destructive=True,
                arguments={'path': 'link-out'},
            )

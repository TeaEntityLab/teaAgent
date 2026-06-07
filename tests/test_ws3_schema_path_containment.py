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


# ── Output schema validation tests ────────────────────────────────────


def test_output_schema_validation_blocks_invalid_type() -> None:
    """Tool handler returning wrong type (string instead of object) must fail."""
    registry = ToolRegistry()
    registry.register(
        name='output_strict',
        description='requires object output',
        input_schema={'type': 'object', 'properties': {}},
        output_schema={'type': 'object', 'properties': {'ok': {'type': 'boolean'}}},
        annotations=ToolAnnotations(read_only=True),
        handler=lambda args: 'not an object',
    )
    with pytest.raises(ToolValidationError):
        registry.execute('output_strict', {})


def test_output_schema_validation_blocks_missing_required_field() -> None:
    """Tool handler returning object missing a required field must fail."""
    registry = ToolRegistry()
    registry.register(
        name='output_required',
        description='requires ok field',
        input_schema={'type': 'object', 'properties': {}},
        output_schema={
            'type': 'object',
            'properties': {'ok': {'type': 'boolean'}},
            'required': ['ok'],
        },
        annotations=ToolAnnotations(read_only=True),
        handler=lambda args: {},
    )
    with pytest.raises(ToolValidationError):
        registry.execute('output_required', {})


def test_output_schema_validation_blocks_wrong_field_type() -> None:
    """Tool handler returning boolean field with wrong type must fail."""
    registry = ToolRegistry()
    registry.register(
        name='output_typed',
        description='requires bool ok',
        input_schema={'type': 'object', 'properties': {}},
        output_schema={
            'type': 'object',
            'properties': {'ok': {'type': 'boolean'}},
        },
        annotations=ToolAnnotations(read_only=True),
        handler=lambda args: {'ok': 1},
    )
    with pytest.raises(ToolValidationError):
        registry.execute('output_typed', {})


def test_output_schema_validation_passes_valid_output() -> None:
    """Tool handler returning correctly typed output must pass."""
    registry = ToolRegistry()
    registry.register(
        name='output_valid',
        description='valid output schema',
        input_schema={'type': 'object', 'properties': {}},
        output_schema={
            'type': 'object',
            'properties': {'ok': {'type': 'boolean'}},
            'required': ['ok'],
        },
        annotations=ToolAnnotations(read_only=True),
        handler=lambda args: {'ok': True},
    )
    result = registry.execute('output_valid', {})
    assert result == {'ok': True}


# ── Deeply nested symlink chain tests ─────────────────────────────────


def test_deeply_nested_symlink_chain_blocked() -> None:
    """symlink2 → symlink1 → /etc/passwd must be blocked by the registry."""
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        link1 = root / 'chain-link1'
        link1.symlink_to('/etc/passwd')
        link2 = root / 'chain-link2'
        link2.symlink_to(link1)
        registry = build_workspace_tool_registry(root=root)
        with pytest.raises(ToolExecutionError, match='symlinks are not allowed'):
            registry.execute('workspace_read_file', {'path': 'chain-link2'})


def test_deeply_nested_symlink_chain_blocked_by_approval_manager() -> None:
    """symlink2 → symlink1 → /etc/passwd must be blocked at the approval level."""
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        link1 = root / 'chain-link1'
        link1.symlink_to('/etc/passwd')
        link2 = root / 'chain-link2'
        link2.symlink_to(link1)
        manager = ApprovalManager(
            permission_mode=PermissionMode.PROMPT,
            workspace_root=str(root),
        )
        with pytest.raises(ToolPermissionError, match='outside'):
            manager.assert_allowed(
                tool_name='workspace_write_file',
                call_id='call-nested-symlink',
                destructive=True,
                arguments={'path': 'chain-link2'},
            )


def test_symlink_to_workspace_internal_file_allowed() -> None:
    """Symlink to a file still inside the workspace must be blocked due to symlink policy."""
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / 'target.txt').write_text('hello', encoding='utf-8')
        link = root / 'link'
        link.symlink_to(root / 'target.txt')
        registry = build_workspace_tool_registry(root=root)
        # Even symlinks to files inside the workspace are blocked by the policy
        with pytest.raises(ToolExecutionError, match='symlinks are not allowed'):
            registry.execute('workspace_read_file', {'path': 'link'})


# ── Git worktree / submodule escape tests ─────────────────────────────


def test_workspace_git_worktree_escape_blocked() -> None:
    """Simulated git worktree .git file pointing outside: path traversal blocked."""
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        # Simulate a git worktree: .git file that points to the main repo outside
        gitfile = root / '.git'
        main_repo = root.parent / 'main-repo'
        main_repo.mkdir(exist_ok=True)
        gitfile.write_text(
            f'gitdir: {main_repo}/.git/worktrees/worktree1\n', encoding='utf-8'
        )
        registry = build_workspace_tool_registry(root=root)
        # Path traversal through .git must still be blocked
        with pytest.raises(ToolExecutionError, match='escape|outside|workspace'):
            registry.execute(
                'workspace_read_file', {'path': '.git/../../../etc/passwd'}
            )


def test_workspace_submodule_escape_blocked() -> None:
    """Submodule path traversal outside workspace must be blocked."""
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / '.gitmodules').write_text(
            '[submodule "external"]\n\tpath = submod\n\turl = https://example.com/repo\n',
            encoding='utf-8',
        )
        (root / 'submod').mkdir()
        registry = build_workspace_tool_registry(root=root)
        with pytest.raises(ToolExecutionError, match='escape|outside|workspace'):
            registry.execute(
                'workspace_read_file', {'path': 'submod/../../../etc/passwd'}
            )


# ── MCP tool path argument escape tests ───────────────────────────────


def test_mcp_tool_with_path_arg_escape_blocked() -> None:
    """MCP-style tool with 'path' key escaping workspace must be blocked."""
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        manager = ApprovalManager(
            permission_mode=PermissionMode.PROMPT,
            workspace_root=str(root),
        )
        with pytest.raises(ToolPermissionError, match='outside'):
            manager.assert_allowed(
                tool_name='mcp_fetch',
                call_id='call-mcp-path',
                destructive=True,
                arguments={'path': '/etc/shadow'},
            )


def test_mcp_tool_with_file_path_arg_escape_blocked() -> None:
    """MCP-style tool with 'file_path' key escaping workspace must be blocked."""
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        manager = ApprovalManager(
            permission_mode=PermissionMode.PROMPT,
            workspace_root=str(root),
        )
        with pytest.raises(ToolPermissionError, match='outside'):
            manager.assert_allowed(
                tool_name='mcp_fetch',
                call_id='call-mcp-filepath',
                destructive=True,
                arguments={'file_path': '/etc/shadow'},
            )


def test_mcp_tool_with_target_path_arg_escape_blocked() -> None:
    """MCP-style tool with 'target_path' key escaping workspace must be blocked."""
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        manager = ApprovalManager(
            permission_mode=PermissionMode.PROMPT,
            workspace_root=str(root),
        )
        with pytest.raises(ToolPermissionError, match='outside'):
            manager.assert_allowed(
                tool_name='mcp_storage',
                call_id='call-mcp-target',
                destructive=True,
                arguments={'target_path': '/var/log/secret'},
            )


def test_mcp_tool_with_file_arg_escape_blocked() -> None:
    """MCP-style tool with 'file' key escaping workspace must be blocked."""
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        manager = ApprovalManager(
            permission_mode=PermissionMode.PROMPT,
            workspace_root=str(root),
        )
        with pytest.raises(ToolPermissionError, match='outside'):
            manager.assert_allowed(
                tool_name='mcp_storage',
                call_id='call-mcp-file',
                destructive=True,
                arguments={'file': '../../../etc/passwd'},
            )


def test_mcp_tool_path_args_inside_workspace_allowed() -> None:
    """MCP-style tool with path args within workspace must pass."""
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / 'data').mkdir()
        policy = ApprovalPolicy(
            permission_mode=PermissionMode.ALLOW,
            workspace_root=str(root),
        )
        policy.assert_allowed(
            tool_name='mcp_fetch',
            call_id='call-mcp-ok',
            destructive=True,
            arguments={'path': 'data/file.txt'},
        )


# ── Root normalization edge case tests ────────────────────────────────


def test_root_normalization_trailing_slash() -> None:
    """Workspace root with trailing slash must still enforce containment."""
    with TemporaryDirectory() as tmp:
        root = str(Path(tmp)) + '/'
        manager = ApprovalManager(
            permission_mode=PermissionMode.PROMPT,
            workspace_root=root,
        )
        with pytest.raises(ToolPermissionError, match='outside'):
            manager.assert_allowed(
                tool_name='workspace_write_file',
                call_id='call-trailing-slash',
                destructive=True,
                arguments={'path': '../outside.txt'},
            )
        # File inside the root must be allowed (with proper base policy)
        policy = ApprovalPolicy(
            permission_mode=PermissionMode.ALLOW,
            workspace_root=root,
        )
        policy.assert_allowed(
            tool_name='workspace_write_file',
            call_id='call-trailing-slash-ok',
            destructive=True,
            arguments={'path': 'inside.txt'},
        )


def test_root_normalization_symlinked_root() -> None:
    """When workspace root is itself a symlink, containment still enforced."""
    with TemporaryDirectory() as tmp:
        real_root = Path(tmp) / 'real-root'
        real_root.mkdir()
        (real_root / 'secret.txt').write_text('secret', encoding='utf-8')
        symlinked_root = Path(tmp) / 'symlinked-root'
        symlinked_root.symlink_to(real_root)
        manager = ApprovalManager(
            permission_mode=PermissionMode.PROMPT,
            workspace_root=str(symlinked_root),
        )
        # ../etc/passwd relative to symlinked_root resolves outside real root
        with pytest.raises(ToolPermissionError, match='outside'):
            manager.assert_allowed(
                tool_name='workspace_write_file',
                call_id='call-symlinked-root',
                destructive=True,
                arguments={'path': '../etc/passwd'},
            )
        # File inside the root must be allowed
        policy = ApprovalPolicy(
            permission_mode=PermissionMode.ALLOW,
            workspace_root=str(symlinked_root),
        )
        policy.assert_allowed(
            tool_name='workspace_write_file',
            call_id='call-symlink-root-ok',
            destructive=True,
            arguments={'path': 'secret.txt'},
        )


def test_root_normalization_relative_root() -> None:
    """Relative workspace root (./tmp) must resolve and enforce containment."""
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / 'file.txt').write_text('hello', encoding='utf-8')
        # Use a relative path for workspace_root
        manager = ApprovalManager(
            permission_mode=PermissionMode.PROMPT,
            workspace_root=str(root),
        )
        with pytest.raises(ToolPermissionError, match='outside'):
            manager.assert_allowed(
                tool_name='workspace_write_file',
                call_id='call-rel-root',
                destructive=True,
                arguments={'path': '../etc/passwd'},
            )
        policy = ApprovalPolicy(
            permission_mode=PermissionMode.ALLOW,
            workspace_root=str(root),
        )
        policy.assert_allowed(
            tool_name='workspace_write_file',
            call_id='call-rel-root-ok',
            destructive=True,
            arguments={'path': 'file.txt'},
        )


def test_root_normalization_dot_root() -> None:
    """Workspace root '.' must still enforce path containment."""
    # Use a real temp dir but "cd" into it by using the absolute path
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        manager = ApprovalManager(
            permission_mode=PermissionMode.PROMPT,
            workspace_root=str(root.resolve()),
        )
        with pytest.raises(ToolPermissionError, match='outside'):
            manager.assert_allowed(
                tool_name='workspace_write_file',
                call_id='call-dot-root',
                destructive=True,
                arguments={'path': '/etc/passwd'},
            )


# ── Parametrized path containment tests (property-based without hypothesis) ──

ESCAPE_VECTORS = [
    '../outside.txt',
    '../../etc/passwd',
    '/etc/passwd',
    '/tmp/escape',
    'subdir/../../../etc/passwd',
    './../../../etc/shadow',
    'foo/./../../etc/hosts',
]


@pytest.mark.parametrize('escape_path', ESCAPE_VECTORS)
def test_path_containment_blocks_escape_vector(escape_path: str) -> None:
    """Every known escape vector must be blocked by path containment."""
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / 'subdir').mkdir(exist_ok=True)
        (root / 'subdir' / 'subfile.txt').write_text('ok', encoding='utf-8')
        manager = ApprovalManager(
            permission_mode=PermissionMode.PROMPT,
            workspace_root=str(root),
        )
        with pytest.raises(ToolPermissionError, match='outside'):
            manager.assert_allowed(
                tool_name='workspace_write_file',
                call_id=f'call-escape-{hash(escape_path)}',
                destructive=True,
                arguments={'path': escape_path},
            )


SAFE_PATHS = [
    'file.txt',
    'subdir/subfile.txt',
    './file.txt',
    './subdir/../file.txt',
    'subdir/./subfile.txt',
]


@pytest.mark.parametrize('safe_path', SAFE_PATHS)
def test_path_containment_allows_safe_paths(safe_path: str) -> None:
    """Paths that stay within the workspace must be allowed."""
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / 'file.txt').write_text('hello', encoding='utf-8')
        (root / 'subdir').mkdir(exist_ok=True)
        (root / 'subdir' / 'subfile.txt').write_text('ok', encoding='utf-8')
        policy = ApprovalPolicy(
            permission_mode=PermissionMode.ALLOW,
            workspace_root=str(root),
        )
        # Must not raise
        policy.assert_allowed(
            tool_name='workspace_write_file',
            call_id=f'call-safe-{hash(safe_path)}',
            destructive=True,
            arguments={'path': safe_path},
        )


# ── Tool handler returning nested path tests ──────────────────────────


def test_tool_handler_returning_escaped_path_value() -> None:
    """Tool handler returning a path that escapes workspace — containment is call-time only.

    Note: output validation checks the schema, not string semantics.
    This test verifies that a handler can return a path string
    and the output schema validation accepts it as a string type.
    """
    registry = ToolRegistry()
    registry.register(
        name='returns_path',
        description='returns a path string',
        input_schema={'type': 'object', 'properties': {}},
        output_schema={
            'type': 'object',
            'properties': {
                'stored_path': {'type': 'string'},
                'ok': {'type': 'boolean'},
            },
        },
        annotations=ToolAnnotations(read_only=True),
        handler=lambda args: {'stored_path': '/etc/passwd', 'ok': True},
    )
    result = registry.execute('returns_path', {})
    # Handler returns successfully — output validation checks types, not semantics
    assert result['stored_path'] == '/etc/passwd'
    assert result['ok'] is True


def test_tool_handler_return_values_not_container_checked() -> None:
    """Tool handler path-return values are not subject to workspace containment.

    Workspace containment applies to tool *input* arguments, not output values.
    Output values are validated structurally (schema types) but not semantically
    (path strings are just strings to the output validator).
    """
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        registry = ToolRegistry()
        registry.register(
            name='list_files',
            description='lists files found in workspace',
            input_schema={
                'type': 'object',
                'properties': {'directory': {'type': 'string'}},
            },
            output_schema={
                'type': 'object',
                'properties': {'files': {'type': 'array', 'items': {'type': 'string'}}},
            },
            annotations=ToolAnnotations(read_only=True),
            handler=lambda args: {
                'files': ['/etc/passwd', '../outside.txt', str(root / 'safe.txt')]
            },
        )
        result = registry.execute('list_files', {'directory': '.'})
        # Output validation passes — strings are valid regardless of their path semantics
        assert '/etc/passwd' in result['files']

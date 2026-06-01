from __future__ import annotations

import logging
import re
import subprocess
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from teaagent.errors import ToolValidationError
from teaagent.external_backends import (
    FallbackKnowledgeBackend,
    get_code_parse_backend,
    get_knowledge_backend,
)
from teaagent.hybrid_search import get_hybrid_backend
from teaagent.tools import ToolAnnotations, ToolRegistry
from teaagent.workspace_tools._config import (
    WorkspaceToolConfig,
    _load_gitignore_matcher,
)
from teaagent.workspace_tools._helpers import (
    assert_write_size_allowed,
    compute_line_hash,
    format_hash_line,
    non_negative_int_arg,
    object_schema,
    positive_int_arg,
    relative_path,
    resolve_workspace_path,
)
from teaagent.workspace_tools._shell import (
    run_shell_inspect,
)

logger = logging.getLogger(__name__)


def build_workspace_tool_registry(
    root: str | Path = '.',
    config_provider: Any = None,
) -> ToolRegistry:
    """Build tool registry with dependency injection support.

    Args:
        root: Workspace root directory
        config_provider: Optional configuration provider for dependency injection

    Returns:
        Tool registry with registered tools
    """
    from teaagent.workspace_tools.config_provider import StaticConfigProvider
    from teaagent.workspace_tools.factory import ToolFactory

    config = WorkspaceToolConfig.from_root(root)

    if config_provider is None:
        config_provider = StaticConfigProvider(config)

    factory = ToolFactory(config)
    registry = ToolRegistry()
    register_workspace_tools(registry, factory)
    return registry


def register_workspace_tools(registry: ToolRegistry, factory: Any) -> None:
    """Register workspace tools using factory for dependency injection.

    Args:
        registry: Tool registry to register tools in
        factory: ToolFactory for creating tool handlers
    """
    registry.register(
        name='workspace_read_file',
        description='Read a UTF-8 text file inside the workspace root.',
        input_schema=object_schema(
            {'path': 'string', 'max_bytes': 'integer'},
            required=['path'],
        ),
        output_schema=object_schema(
            {
                'path': 'string',
                'content': 'string',
                'truncated': 'boolean',
                'mtime': 'number',
            },
            required=['path', 'content', 'truncated'],
        ),
        annotations=ToolAnnotations(read_only=True, idempotent=True),
        handler=factory.create_read_file_handler(),
    )
    registry.register(
        name='workspace_write_file',
        description='Write a UTF-8 text file inside the workspace root. If expected_mtime is provided and the file exists, the write is rejected if the file was modified since that mtime (concurrent modification guard).',
        input_schema=object_schema(
            {
                'path': 'string',
                'content': 'string',
                'create_dirs': 'boolean',
                'expected_mtime': 'number',
            },
            required=['path', 'content'],
        ),
        output_schema=object_schema(
            {
                'path': 'string',
                'bytes_written': 'integer',
                'mtime': 'number',
            },
            required=['path', 'bytes_written'],
        ),
        annotations=ToolAnnotations(destructive=True, idempotent=True),
        handler=factory.create_write_file_handler(),
    )
    registry.register(
        name='workspace_read_file_hashed',
        description='Read a UTF-8 text file with stable LINE#HASH anchors for safer patching.',
        input_schema=object_schema(
            {'path': 'string', 'max_bytes': 'integer'},
            required=['path'],
        ),
        output_schema=object_schema(
            {
                'path': 'string',
                'content': 'string',
                'truncated': 'boolean',
                'mtime': 'number',
            },
            required=['path', 'content', 'truncated'],
        ),
        annotations=ToolAnnotations(read_only=True, idempotent=True),
        handler=lambda args: read_file_hashed(factory._config, args),
    )
    registry.register(
        name='workspace_edit_at_hash',
        description='Edit one line only if its LINE#HASH anchor and old text still match.',
        input_schema=object_schema(
            {
                'path': 'string',
                'line': 'integer',
                'hash': 'string',
                'old': 'string',
                'new': 'string',
            },
            required=['path', 'line', 'hash', 'old', 'new'],
        ),
        output_schema=object_schema(
            {'path': 'string', 'line': 'integer', 'hash': 'string'},
            required=['path', 'line', 'hash'],
        ),
        annotations=ToolAnnotations(destructive=True, idempotent=False),
        handler=factory.create_edit_at_hash_handler(),
    )
    registry.register(
        name='workspace_apply_patch',
        description='Replace one exact text span in a UTF-8 file inside the workspace root.',
        input_schema=object_schema(
            {'path': 'string', 'old': 'string', 'new': 'string'},
            required=['path', 'old', 'new'],
        ),
        output_schema=object_schema(
            {'path': 'string', 'replacements': 'integer'},
            required=['path', 'replacements'],
        ),
        annotations=ToolAnnotations(destructive=True, idempotent=False),
        handler=lambda args: apply_patch(factory._config, args),
    )
    registry.register(
        name='workspace_list_files',
        description='List files matching a glob pattern inside the workspace root.',
        input_schema=object_schema(
            {'pattern': 'string', 'limit': 'integer', 'offset': 'integer'},
            required=['pattern'],
        ),
        output_schema=object_schema(
            {
                'files': {'type': 'array', 'items': {'type': 'string'}},
                'truncated': 'boolean',
                'offset': 'integer',
            },
            required=['files', 'truncated'],
        ),
        annotations=ToolAnnotations(read_only=True, idempotent=True),
        handler=lambda args: list_files(factory._config, args),
    )
    registry.register(
        name='workspace_search_text',
        description='Search text files with a regular expression inside the workspace root.',
        input_schema=object_schema(
            {
                'pattern': 'string',
                'include': 'string',
                'limit': 'integer',
                'offset': 'integer',
            },
            required=['pattern'],
        ),
        output_schema=object_schema(
            {
                'matches': {'type': 'array', 'items': {'type': 'object'}},
                'truncated': 'boolean',
                'offset': 'integer',
            },
            required=['matches', 'truncated'],
        ),
        annotations=ToolAnnotations(read_only=True, idempotent=True),
        handler=lambda args: search_text(factory._config, args),
    )
    registry.register(
        name='workspace_hybrid_index',
        description='Build or refresh a fallback hybrid index (FTS5 + basic vectors + RRF) for workspace files.',
        input_schema=object_schema(
            {
                'include': 'string',
                'collection': 'string',
                'backend': 'string',
                'clear': 'boolean',
            },
            required=[],
        ),
        output_schema=object_schema(
            {
                'backend': 'string',
                'collection': 'string',
                'indexed': 'integer',
                'skipped': 'integer',
                'include': 'string',
                'database': 'string',
            },
            required=[
                'backend',
                'collection',
                'indexed',
                'skipped',
                'include',
                'database',
            ],
        ),
        annotations=ToolAnnotations(destructive=True, idempotent=False),
        handler=lambda args: hybrid_index(factory._config, args),
    )
    registry.register(
        name='workspace_hybrid_search',
        description='Run hybrid retrieval against an indexed collection with backend selection for local or external adapters.',
        input_schema=object_schema(
            {
                'query': 'string',
                'limit': 'integer',
                'collection': 'string',
                'backend': 'string',
            },
            required=['query'],
        ),
        output_schema=object_schema(
            {
                'backend': 'string',
                'collection': 'string',
                'query': 'string',
                'hits': {'type': 'array', 'items': {'type': 'object'}},
            },
            required=['backend', 'collection', 'query', 'hits'],
        ),
        annotations=ToolAnnotations(read_only=True, idempotent=True),
        handler=lambda args: hybrid_search(factory._config, args),
    )
    registry.register(
        name='workspace_knowledge_index',
        description='Index knowledge with pluggable backend. Use backend=auto for primary-then-fallback behavior.',
        input_schema=object_schema(
            {
                'backend': 'string',
                'include': 'string',
                'collection': 'string',
                'clear': 'boolean',
                'primary_backend': 'string',
                'fallback_backend': 'string',
            },
            required=[],
        ),
        output_schema=object_schema(
            {'backend': 'string', 'result': {'type': 'object'}},
            required=['backend', 'result'],
        ),
        annotations=ToolAnnotations(destructive=True, idempotent=False),
        handler=lambda args: knowledge_index(factory._config, args),
    )
    registry.register(
        name='workspace_knowledge_search',
        description='Search knowledge with pluggable backend. Use backend=auto for primary-then-fallback behavior.',
        input_schema=object_schema(
            {
                'backend': 'string',
                'query': 'string',
                'limit': 'integer',
                'collection': 'string',
                'primary_backend': 'string',
                'fallback_backend': 'string',
            },
            required=['query'],
        ),
        output_schema=object_schema(
            {'backend': 'string', 'result': {'type': 'object'}},
            required=['backend', 'result'],
        ),
        annotations=ToolAnnotations(read_only=True, idempotent=True),
        handler=lambda args: knowledge_search(factory._config, args),
    )
    registry.register(
        name='workspace_code_parse',
        description='Run code parsing/navigation actions via pluggable code_parse backends (cx/codegraph/etc).',
        input_schema=object_schema(
            {
                'backend': 'string',
                'action': 'string',
                'path': 'string',
                'name': 'string',
                'kind': 'string',
                'file': 'string',
                'from': 'string',
            },
            required=['action'],
        ),
        output_schema=object_schema(
            {'backend': 'string', 'action': 'string', 'result': {'type': 'object'}},
            required=['backend', 'action', 'result'],
        ),
        annotations=ToolAnnotations(read_only=True, idempotent=True),
        handler=lambda args: code_parse(factory._config, args),
    )
    registry.register(
        name='workspace_git_status',
        description='Run git status --short inside the workspace root.',
        input_schema=object_schema({}, required=[]),
        output_schema=object_schema(
            {'status': 'string', 'exit_code': 'integer'},
            required=['status', 'exit_code'],
        ),
        annotations=ToolAnnotations(read_only=True, idempotent=True),
        handler=lambda _args: git_status(factory._config),
    )
    registry.register(
        name='workspace_run_shell_inspect',
        description='Run a bounded read-oriented shell command inside the workspace root.',
        input_schema=object_schema(
            {'command': 'string', 'timeout_seconds': 'integer'},
            required=['command'],
        ),
        output_schema=object_schema(
            {'stdout': 'string', 'stderr': 'string', 'exit_code': 'integer'},
            required=['stdout', 'stderr', 'exit_code'],
        ),
        annotations=ToolAnnotations(read_only=True, idempotent=False),
        handler=lambda args: run_shell_inspect(factory._config, args),
    )
    registry.register(
        name='workspace_run_shell_mutate',
        description='Run an approval-gated shell command inside the workspace root.',
        input_schema=object_schema(
            {'command': 'string', 'timeout_seconds': 'integer'},
            required=['command'],
        ),
        output_schema=object_schema(
            {'stdout': 'string', 'stderr': 'string', 'exit_code': 'integer'},
            required=['stdout', 'stderr', 'exit_code'],
        ),
        annotations=ToolAnnotations(destructive=True, idempotent=False),
        handler=factory.create_run_shell_handler(),
    )
    registry.register(
        name='workspace_run_shell',
        description='Compatibility alias for workspace_run_shell_mutate. Requires approval in agent runs.',
        input_schema=object_schema(
            {'command': 'string', 'timeout_seconds': 'integer'},
            required=['command'],
        ),
        output_schema=object_schema(
            {'stdout': 'string', 'stderr': 'string', 'exit_code': 'integer'},
            required=['stdout', 'stderr', 'exit_code'],
        ),
        annotations=ToolAnnotations(destructive=True, idempotent=False),
        handler=factory.create_run_shell_handler(),
    )

    _register_browser_tools_if_available(registry)


def _register_browser_tools_if_available(registry: ToolRegistry) -> None:
    """Register browser automation tools when Playwright is installed."""
    try:
        from teaagent.browser_tools import HAS_PLAYWRIGHT, register_browser_tools

        if HAS_PLAYWRIGHT:
            register_browser_tools(registry)
    except ImportError:
        # Browser tools module not available; skip registration gracefully
        logger.debug('Browser tools not available; Playwright not installed')


def read_file(config: WorkspaceToolConfig, args: dict[str, Any]) -> dict[str, Any]:
    path = resolve_workspace_path(config, args['path'])

    # Check for symlinks to prevent symlink attacks
    if path.is_symlink():
        raise ValueError('symlinks are not allowed')

    # Validate path is within workspace root to prevent path traversal
    if not path.resolve().is_relative_to(config.root.resolve()):
        raise ValueError('Path outside workspace')

    max_bytes = non_negative_int_arg(args, 'max_bytes', default=config.max_read_bytes)
    data = path.read_bytes()
    truncated = len(data) > max_bytes
    stat = path.stat()
    return {
        'path': relative_path(config, path),
        'content': data[:max_bytes].decode('utf-8', errors='replace'),
        'truncated': truncated,
        'mtime': stat.st_mtime,
    }


def read_file_hashed(
    config: WorkspaceToolConfig, args: dict[str, Any]
) -> dict[str, Any]:
    raw = read_file(config, args)
    lines = raw['content'].splitlines(keepends=True)
    raw['content'] = ''.join(
        format_hash_line(index, line) for index, line in enumerate(lines, start=1)
    )
    return raw


def write_file(config: WorkspaceToolConfig, args: dict[str, Any]) -> dict[str, Any]:
    import os
    import tempfile

    path = resolve_workspace_path(config, args['path'])

    # Check for symlinks to prevent symlink attacks
    if path.is_symlink():
        raise ValueError('symlinks are not allowed')

    if args.get('create_dirs', False):
        path.parent.mkdir(parents=True, exist_ok=True)
    content = args['content']
    assert_write_size_allowed(config, content)
    expected_mtime = args.get('expected_mtime')

    # Validate expected_mtime if provided
    if expected_mtime is not None:
        try:
            expected_mtime = float(expected_mtime)
        except (ValueError, TypeError):
            raise ValueError('expected_mtime must be a valid number') from None

    # Write to temporary file first for atomic operation
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # Verify mtime before atomic rename (TOCTOU-safe)
        if expected_mtime is not None and path.exists():
            actual_mtime = path.stat().st_mtime
            if abs(actual_mtime - expected_mtime) > 0.001:
                os.unlink(tmp_path)
                raise ValueError(
                    f'file {relative_path(config, path)} was modified since last read '
                    f'(expected_mtime={expected_mtime}, actual_mtime={actual_mtime:.6f}). '
                    f'Re-read the file before writing.'
                )

        # Atomic rename
        os.replace(tmp_path, path)
    except Exception:
        # Clean up temp file on error
        if os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError as exc:
                logger.warning(f'Temp file cleanup failed: {tmp_path}: {exc}')
        raise

    stat = path.stat()
    return {
        'path': relative_path(config, path),
        'bytes_written': len(content.encode('utf-8')),
        'mtime': stat.st_mtime,
    }


def apply_patch(config: WorkspaceToolConfig, args: dict[str, Any]) -> dict[str, Any]:
    path = resolve_workspace_path(config, args['path'])
    text = path.read_text(encoding='utf-8')
    old = args['old']
    if old not in text:
        raise ValueError('old text not found')
    if text.count(old) > 1:
        raise ValueError(
            'old text is not unique; provide more surrounding context '
            'or use workspace_edit_at_hash for a line-anchored edit'
        )
    updated = text.replace(old, args['new'], 1)
    assert_write_size_allowed(config, updated)
    path.write_text(updated, encoding='utf-8')
    return {'path': relative_path(config, path), 'replacements': 1}


def edit_at_hash(config: WorkspaceToolConfig, args: dict[str, Any]) -> dict[str, Any]:
    path = resolve_workspace_path(config, args['path'])
    lines = path.read_text(encoding='utf-8').splitlines(keepends=True)

    # Check for empty file
    if not lines:
        raise ValueError('Cannot edit empty file')

    # Validate line number type and range
    try:
        line_number = int(args['line'])
    except (ValueError, TypeError):
        raise ValueError('line must be an integer') from None

    if line_number < 1:
        raise ValueError('line must be >= 1')

    if line_number > len(lines):
        raise ValueError(
            f'line {line_number} is outside file range (max: {len(lines)})'
        )

    current = lines[line_number - 1]
    expected_hash = compute_line_hash(line_number, current)
    if expected_hash != args['hash']:
        raise ValueError('line hash mismatch')
    current_text = current.rstrip('\n').rstrip('\r')
    if current_text != args['old']:
        raise ValueError('old text mismatch')
    newline = '\n' if current.endswith('\n') else ''
    lines[line_number - 1] = args['new'] + newline
    updated = ''.join(lines)
    assert_write_size_allowed(config, updated)
    path.write_text(updated, encoding='utf-8')
    new_hash = compute_line_hash(line_number, lines[line_number - 1])
    return {'path': relative_path(config, path), 'line': line_number, 'hash': new_hash}


def list_files(config: WorkspaceToolConfig, args: dict[str, Any]) -> dict[str, Any]:
    pattern = args['pattern']
    limit = positive_int_arg(args, 'limit', default=200)
    offset = non_negative_int_arg(args, 'offset', default=0)
    skipped = 0
    is_ignored = _load_gitignore_matcher(config.root)
    files = []
    for path in sorted(config.root.rglob('*')):
        if not path.is_file():
            continue
        if path.is_symlink():
            continue
        rel = relative_path(config, path)
        if '.git' in path.parts or is_ignored(rel):
            continue
        if not fnmatch(rel, pattern):
            continue
        if skipped < offset:
            skipped += 1
            continue
        files.append(rel)
        if len(files) >= limit:
            return {
                'files': files,
                'truncated': True,
                'offset': offset + skipped + len(files),
            }
    return {'files': files, 'truncated': False, 'offset': offset + skipped + len(files)}


def search_text(config: WorkspaceToolConfig, args: dict[str, Any]) -> dict[str, Any]:
    pattern = args.get('pattern', '')
    if not pattern:
        raise ValueError('pattern is required and cannot be empty')
    try:
        regex = re.compile(pattern)
    except re.error as e:
        raise ValueError(f'Invalid regex pattern: {e}') from e
    include = args.get('include', '*')
    limit = positive_int_arg(args, 'limit', default=200)
    offset = non_negative_int_arg(args, 'offset', default=0)
    skipped = 0
    is_ignored = _load_gitignore_matcher(config.root)
    matches = []
    for path in sorted(config.root.rglob('*')):
        if not path.is_file():
            continue
        if path.is_symlink():
            continue
        rel = relative_path(config, path)
        if '.git' in path.parts or is_ignored(rel):
            continue
        if not fnmatch(rel, include):
            continue
        try:
            lines = path.read_text(encoding='utf-8').splitlines()
        except UnicodeDecodeError:
            continue
        for line_number, line in enumerate(lines, start=1):
            if regex.search(line):
                if skipped < offset:
                    skipped += 1
                    continue
                matches.append(
                    {
                        'path': rel,
                        'line': line_number,
                        'text': line,
                    }
                )
                if len(matches) >= limit:
                    return {
                        'matches': matches,
                        'truncated': True,
                        'offset': offset + skipped + len(matches),
                    }
    return {
        'matches': matches,
        'truncated': False,
        'offset': offset + skipped + len(matches),
    }


def hybrid_index(config: WorkspaceToolConfig, args: dict[str, Any]) -> dict[str, Any]:
    backend_name = str(args.get('backend', 'local'))
    backend = get_hybrid_backend(backend_name)
    payload = dict(args)
    result = backend.index(root=config.root, args=payload)
    if 'backend' not in result:
        result['backend'] = backend_name
    return result


def hybrid_search(config: WorkspaceToolConfig, args: dict[str, Any]) -> dict[str, Any]:
    backend_name = str(args.get('backend', 'local'))
    limit = positive_int_arg(args, 'limit', default=5)
    backend = get_hybrid_backend(backend_name)
    payload = dict(args)
    payload['limit'] = limit
    result = backend.search(root=config.root, args=payload)
    if 'backend' not in result:
        result['backend'] = backend_name
    return result


def knowledge_index(
    config: WorkspaceToolConfig, args: dict[str, Any]
) -> dict[str, Any]:
    backend_name = str(args.get('backend', 'local'))
    payload = dict(args)
    backend = _resolve_knowledge_backend(backend_name, payload)
    result = backend.index(root=config.root, args=payload)
    return {'backend': backend_name, 'result': result}


def knowledge_search(
    config: WorkspaceToolConfig, args: dict[str, Any]
) -> dict[str, Any]:
    backend_name = str(args.get('backend', 'local'))
    payload = dict(args)
    payload['limit'] = positive_int_arg(args, 'limit', default=5)
    backend = _resolve_knowledge_backend(backend_name, payload)
    result = backend.search(root=config.root, args=payload)
    return {'backend': backend_name, 'result': result}


def code_parse(config: WorkspaceToolConfig, args: dict[str, Any]) -> dict[str, Any]:
    backend_name = str(args.get('backend', 'cx_cli'))
    action = str(args['action'])
    _ACTION_REQUIRED_FIELDS: dict[str, list[str]] = {
        'overview': ['path'],
        'definition': ['name'],
        'references': ['name'],
        'symbols': [],
        'health': [],
    }
    required = _ACTION_REQUIRED_FIELDS.get(action, [])
    missing = [f for f in required if not args.get(f)]
    if missing:
        raise ToolValidationError(
            f"code_parse action '{action}' is missing required field(s): {', '.join(missing)}",
            hint=f"Provide the following fields for action '{action}': {', '.join(missing)}",
        )
    backend = get_code_parse_backend(backend_name)
    payload = dict(args)
    if action == 'health':
        result = backend.health(root=config.root)
    elif action == 'overview':
        result = backend.overview(root=config.root, args=payload)
    elif action == 'symbols':
        result = backend.symbols(root=config.root, args=payload)
    elif action == 'definition':
        result = backend.definition(root=config.root, args=payload)
    elif action == 'references':
        result = backend.references(root=config.root, args=payload)
    else:
        raise ValueError(
            'action must be one of: health, overview, symbols, definition, references'
        )
    return {'backend': backend_name, 'action': action, 'result': result}


def _resolve_knowledge_backend(backend_name: str, payload: dict[str, Any]) -> Any:
    if backend_name != 'auto':
        return get_knowledge_backend(backend_name)
    primary = str(payload.pop('primary_backend', 'qmd_mcp'))
    fallback = str(payload.pop('fallback_backend', 'local'))
    return FallbackKnowledgeBackend(primary=primary, fallback=fallback)


def git_status(config: WorkspaceToolConfig) -> dict[str, Any]:
    result = subprocess.run(
        ['git', 'status', '--short'],
        cwd=str(config.root),
        text=True,
        capture_output=True,
        timeout=config.command_timeout_seconds,
    )
    return {'status': result.stdout + result.stderr, 'exit_code': result.returncode}

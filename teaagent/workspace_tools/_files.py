from __future__ import annotations

import re
import subprocess
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

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
    run_shell,
    run_shell_inspect,
)


def build_workspace_tool_registry(root: str | Path = '.') -> ToolRegistry:
    registry = ToolRegistry()
    register_workspace_tools(registry, WorkspaceToolConfig.from_root(root))
    return registry


def register_workspace_tools(
    registry: ToolRegistry, config: WorkspaceToolConfig
) -> None:
    registry.register(
        name='workspace_read_file',
        description='Read a UTF-8 text file inside the workspace root.',
        input_schema=object_schema(
            {'path': 'string', 'max_bytes': 'integer'},
            required=['path'],
        ),
        output_schema=object_schema(
            {'path': 'string', 'content': 'string', 'truncated': 'boolean'},
            required=['path', 'content', 'truncated'],
        ),
        annotations=ToolAnnotations(read_only=True, idempotent=True),
        handler=lambda args: read_file(config, args),
    )
    registry.register(
        name='workspace_write_file',
        description='Write a UTF-8 text file inside the workspace root.',
        input_schema=object_schema(
            {'path': 'string', 'content': 'string', 'create_dirs': 'boolean'},
            required=['path', 'content'],
        ),
        output_schema=object_schema(
            {'path': 'string', 'bytes_written': 'integer'},
            required=['path', 'bytes_written'],
        ),
        annotations=ToolAnnotations(destructive=True, idempotent=True),
        handler=lambda args: write_file(config, args),
    )
    registry.register(
        name='workspace_read_file_hashed',
        description='Read a UTF-8 text file with stable LINE#HASH anchors for safer edits.',
        input_schema=object_schema(
            {'path': 'string', 'max_bytes': 'integer'},
            required=['path'],
        ),
        output_schema=object_schema(
            {'path': 'string', 'content': 'string', 'truncated': 'boolean'},
            required=['path', 'content', 'truncated'],
        ),
        annotations=ToolAnnotations(read_only=True, idempotent=True),
        handler=lambda args: read_file_hashed(config, args),
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
        handler=lambda args: edit_at_hash(config, args),
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
        handler=lambda args: apply_patch(config, args),
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
        handler=lambda args: list_files(config, args),
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
        handler=lambda args: search_text(config, args),
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
        handler=lambda args: hybrid_index(config, args),
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
        handler=lambda args: hybrid_search(config, args),
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
        handler=lambda args: knowledge_index(config, args),
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
        handler=lambda args: knowledge_search(config, args),
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
        handler=lambda args: code_parse(config, args),
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
        handler=lambda _args: git_status(config),
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
        handler=lambda args: run_shell_inspect(config, args),
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
        handler=lambda args: run_shell(config, args),
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
        handler=lambda args: run_shell(config, args),
    )


def read_file(config: WorkspaceToolConfig, args: dict[str, Any]) -> dict[str, Any]:
    path = resolve_workspace_path(config, args['path'])
    max_bytes = non_negative_int_arg(args, 'max_bytes', default=config.max_read_bytes)
    data = path.read_bytes()
    truncated = len(data) > max_bytes
    return {
        'path': relative_path(config, path),
        'content': data[:max_bytes].decode('utf-8', errors='replace'),
        'truncated': truncated,
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
    path = resolve_workspace_path(config, args['path'])
    if args.get('create_dirs', False):
        path.parent.mkdir(parents=True, exist_ok=True)
    content = args['content']
    assert_write_size_allowed(config, content)
    path.write_text(content, encoding='utf-8')
    return {
        'path': relative_path(config, path),
        'bytes_written': len(content.encode('utf-8')),
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
    line_number = args['line']
    if line_number < 1 or line_number > len(lines):
        raise ValueError('line is outside file range')
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
    regex = re.compile(args['pattern'])
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

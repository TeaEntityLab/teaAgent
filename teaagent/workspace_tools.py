from __future__ import annotations

import re
import shlex
import subprocess
import zlib
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Callable, Union

from teaagent.tools import ToolAnnotations, ToolRegistry


@dataclass(frozen=True)
class WorkspaceToolConfig:
    root: Path
    command_timeout_seconds: int = 30
    max_read_bytes: int = 200_000
    max_write_bytes: int = 200_000
    max_shell_command_bytes: int = 4_096
    max_shell_output_bytes: int = 200_000
    max_shell_timeout_seconds: int = 30

    @classmethod
    def from_root(cls, root: str | Path) -> 'WorkspaceToolConfig':
        return cls(root=Path(root).resolve())


_GITIGNORE_BASENAMES = frozenset({'.gitignore', '.agignore'})


def _load_gitignore_matcher(root: Path) -> Callable[[str], bool]:
    patterns: list[tuple[str, bool]] = []
    for name in _GITIGNORE_BASENAMES:
        ignore_file = root / name
        if not ignore_file.is_file():
            continue
        try:
            lines = ignore_file.read_text(encoding='utf-8').splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        for raw in lines:
            line = raw.strip()
            if not line or line.startswith('#'):
                continue
            negate = line.startswith('!')
            pattern = line[1:].strip() if negate else line
            if not pattern:
                continue
            dir_only = pattern.endswith('/')
            if dir_only:
                pattern = pattern[:-1]
            if pattern.startswith('/'):
                pattern = pattern[1:]
            patterns.append((pattern, negate))
    if not patterns:
        return _always_allow_matcher
    return _build_gitignore_matcher(patterns)


def _always_allow_matcher(_rel: str) -> bool:
    return False


def _build_gitignore_matcher(
    patterns: list[tuple[str, bool]],
) -> Callable[[str], bool]:
    def matcher(rel_path: str) -> bool:
        ignored = False
        for pattern, negate in patterns:
            if _gitignore_match(rel_path, pattern):
                ignored = not negate
        return ignored

    return matcher


def _gitignore_match(rel_path: str, pattern: str) -> bool:
    if '/' not in pattern and '**' not in pattern:
        return fnmatch(Path(rel_path).name, pattern)
    return fnmatch(rel_path, pattern)


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


def object_schema(
    properties: dict[str, Union[str, dict[str, Any]]], *, required: list[str]
) -> dict[str, Any]:
    return {
        'type': 'object',
        'properties': {
            name: type_name if isinstance(type_name, dict) else {'type': type_name}
            for name, type_name in properties.items()
        },
        'required': required,
    }


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


def git_status(config: WorkspaceToolConfig) -> dict[str, Any]:
    result = subprocess.run(
        ['git', 'status', '--short'],
        cwd=str(config.root),
        text=True,
        capture_output=True,
        timeout=config.command_timeout_seconds,
    )
    return {'status': result.stdout + result.stderr, 'exit_code': result.returncode}


def run_shell(config: WorkspaceToolConfig, args: dict[str, Any]) -> dict[str, Any]:
    command = args['command']
    assert_shell_command_size_allowed(config, command)
    timeout = bounded_positive_int_arg(
        args,
        'timeout_seconds',
        default=config.command_timeout_seconds,
        maximum=config.max_shell_timeout_seconds,
    )
    result = subprocess.run(
        command,
        cwd=str(config.root),
        shell=True,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    return {
        'stdout': truncate_output(result.stdout, config.max_shell_output_bytes),
        'stderr': truncate_output(result.stderr, config.max_shell_output_bytes),
        'exit_code': result.returncode,
    }


def run_shell_argv(
    config: WorkspaceToolConfig, argv: list[str], *, timeout_seconds: int
) -> dict[str, Any]:
    result = subprocess.run(
        argv,
        cwd=str(config.root),
        shell=False,
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
    )
    return {
        'stdout': truncate_output(result.stdout, config.max_shell_output_bytes),
        'stderr': truncate_output(result.stderr, config.max_shell_output_bytes),
        'exit_code': result.returncode,
    }


def run_shell_inspect(
    config: WorkspaceToolConfig, args: dict[str, Any]
) -> dict[str, Any]:
    command = args['command']
    assert_shell_command_size_allowed(config, command)
    policy = classify_shell_command_policy(command)
    if policy != 'inspect':
        raise ValueError(
            'command is not inspect-safe; retry with workspace_run_shell_mutate'
        )
    timeout = bounded_positive_int_arg(
        args,
        'timeout_seconds',
        default=config.command_timeout_seconds,
        maximum=config.max_shell_timeout_seconds,
    )
    return run_shell_argv(config, shlex.split(command), timeout_seconds=timeout)


def positive_int_arg(args: dict[str, Any], name: str, *, default: int) -> int:
    value = args.get(name, default)
    if value < 1:
        raise ValueError(f'{name} must be >= 1')
    return value


def bounded_positive_int_arg(
    args: dict[str, Any], name: str, *, default: int, maximum: int
) -> int:
    value = positive_int_arg(args, name, default=default)
    if value > maximum:
        raise ValueError(f'{name} must be <= {maximum}')
    return value


def non_negative_int_arg(args: dict[str, Any], name: str, *, default: int) -> int:
    value = args.get(name, default)
    if value < 0:
        raise ValueError(f'{name} must be >= 0')
    return value


def classify_shell_command_policy(command: str) -> str:
    try:
        parts = shlex.split(command.strip())
    except ValueError:
        return 'mutate'
    if not parts:
        return 'mutate'
    if _has_unquoted_shell_operator(command):
        return 'mutate'
    if any(shell_arg_escapes_workspace(arg) for arg in parts[1:]):
        return 'mutate'
    if _is_allowed_inspect_argv(parts):
        return 'inspect'
    return 'mutate'


_INSPECT_EXECUTABLES = frozenset(
    {'pwd', 'ls', 'rg', 'grep', 'cat', 'head', 'tail', 'wc'}
)
_INSPECT_GIT_SUBCOMMANDS = frozenset(
    {'status', 'diff', 'log', 'show', 'branch', 'grep'}
)
_DANGEROUS_FIND_FLAGS = frozenset(
    {'-delete', '-exec', '-execdir', '-ok', '-okdir', '-fprint', '-fprint0', '-fprintf'}
)


def _is_allowed_inspect_argv(parts: list[str]) -> bool:
    executable = parts[0]
    if executable in _INSPECT_EXECUTABLES:
        return True
    if executable == 'find':
        return not any(arg in _DANGEROUS_FIND_FLAGS for arg in parts[1:])
    if executable == 'git' and len(parts) > 1:
        if any(arg.startswith('-c') or arg.startswith('--config') for arg in parts[1:]):
            return False
        return parts[1] in _INSPECT_GIT_SUBCOMMANDS
    return False


def _has_unquoted_shell_operator(command: str) -> bool:
    in_single = False
    in_double = False
    i = 0
    n = len(command)
    while i < n:
        ch = command[i]
        if in_single:
            if ch == "'" and (i == 0 or command[i - 1] != '\\'):
                in_single = False
        elif in_double:
            if ch == '"' and (i == 0 or command[i - 1] != '\\'):
                in_double = False
        else:
            if ch == "'":
                in_single = True
            elif ch == '"':
                in_double = True
            elif (
                ch in ('>', '<', '|', '&', ';', '`')
                or ch == '$'
                and i + 1 < n
                and command[i + 1] == '('
            ):
                return True
        i += 1
    return False


def shell_arg_escapes_workspace(arg: str) -> bool:
    return (
        arg.startswith(('/', '~'))
        or arg == '..'
        or arg.startswith('../')
        or '/../' in arg
    )


def truncate_output(value: str, max_bytes: int) -> str:
    data = value.encode('utf-8')
    if len(data) <= max_bytes:
        return value
    marker = b'\n[truncated]'
    keep = max(0, max_bytes - len(marker))
    return (data[:keep] + marker).decode('utf-8', errors='replace')


def assert_write_size_allowed(config: WorkspaceToolConfig, content: str) -> None:
    byte_count = len(content.encode('utf-8'))
    if byte_count > config.max_write_bytes:
        raise ValueError(
            f'write would exceed max_write_bytes ({byte_count} > {config.max_write_bytes})'
        )


def assert_shell_command_size_allowed(
    config: WorkspaceToolConfig, command: str
) -> None:
    byte_count = len(command.encode('utf-8'))
    if byte_count > config.max_shell_command_bytes:
        raise ValueError(
            'shell command exceeds max_shell_command_bytes '
            f'({byte_count} > {config.max_shell_command_bytes})'
        )


def resolve_workspace_path(config: WorkspaceToolConfig, path: str) -> Path:
    resolved = (config.root / path).resolve()
    try:
        resolved.relative_to(config.root)
    except ValueError as exc:
        raise ValueError('path escapes workspace root') from exc
    return resolved


def relative_path(config: WorkspaceToolConfig, path: Path) -> str:
    return str(path.resolve().relative_to(config.root))


def compute_line_hash(line_number: int, content: str) -> str:
    normalized = f'{line_number}:{content.replace(chr(13), "").rstrip()}'.encode(
        'utf-8'
    )
    return f'{zlib.crc32(normalized) & 0xFF:02X}'


def format_hash_line(line_number: int, content: str) -> str:
    stripped_newline = content.rstrip('\n').rstrip('\r')
    newline = '\n' if content.endswith('\n') else ''
    return f'{line_number}#{compute_line_hash(line_number, content)}|{stripped_newline}{newline}'

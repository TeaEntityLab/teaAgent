from __future__ import annotations

import zlib
from pathlib import Path
from typing import Any, Union

from teaagent.workspace_tools._config import WorkspaceToolConfig


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

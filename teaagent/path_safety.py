"""Shared filesystem-containment checks for untrusted relative paths."""

from __future__ import annotations

from pathlib import Path


def resolve_contained_path(
    root: str | Path,
    value: str | Path,
    *,
    must_exist: bool = False,
    require_file: bool = False,
    require_directory: bool = False,
) -> Path:
    """Resolve *value* below *root* without traversing symbolic links."""
    if require_file and require_directory:
        raise ValueError('path cannot require both a file and a directory')

    root_path = Path(root).resolve()
    raw_path = Path(value)
    candidate = raw_path if raw_path.is_absolute() else root_path / raw_path
    try:
        lexical_relative = candidate.relative_to(root_path)
    except ValueError as exc:
        raise ValueError('path escapes root') from exc

    cursor = root_path
    for part in lexical_relative.parts:
        if part in ('', '.'):
            continue
        if part == '..':
            cursor = cursor.parent
            try:
                cursor.relative_to(root_path)
            except ValueError as exc:
                raise ValueError('path escapes root') from exc
            continue
        cursor /= part
        if cursor.is_symlink():
            raise ValueError('symlinks are not allowed')

    resolved = candidate.resolve()
    try:
        resolved.relative_to(root_path)
    except ValueError as exc:
        raise ValueError('path escapes root') from exc

    if must_exist and not resolved.exists():
        raise FileNotFoundError(f'path does not exist: {value}')
    if require_file and not resolved.is_file():
        raise FileNotFoundError(f'file does not exist: {value}')
    if require_directory and not resolved.is_dir():
        raise FileNotFoundError(f'directory does not exist: {value}')
    return resolved

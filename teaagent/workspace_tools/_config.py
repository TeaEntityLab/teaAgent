from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Callable

_GITIGNORE_BASENAMES = frozenset({'.gitignore', '.agignore'})


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

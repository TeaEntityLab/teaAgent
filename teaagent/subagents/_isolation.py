from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from teaagent.subagents._types import DEFAULT_SUBAGENT_ISOLATION

SUPPORTED_SUBAGENT_ISOLATIONS = frozenset({'shared', 'worktree'})


@dataclass(frozen=True)
class IsolationContext:
    parent_root: Path
    child_root: Path
    isolation: str
    worktree_path: Optional[Path] = None

    def cleanup(self) -> None:
        if self.worktree_path is None:
            return
        subprocess.run(
            ['git', 'worktree', 'remove', '--force', str(self.worktree_path)],
            cwd=self.parent_root,
            check=False,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ['git', 'worktree', 'prune'],
            cwd=self.parent_root,
            check=False,
            capture_output=True,
            text=True,
        )


def normalize_subagent_isolation(value: Any) -> str | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return DEFAULT_SUBAGENT_ISOLATION
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if normalized == 'container':
        return None
    if normalized in SUPPORTED_SUBAGENT_ISOLATIONS:
        return normalized
    return None


def prepare_subagent_isolation(
    parent_root: Path,
    *,
    isolation: str,
    session_key: str,
) -> tuple[IsolationContext | None, str]:
    root = parent_root.resolve()
    if isolation == DEFAULT_SUBAGENT_ISOLATION:
        return (
            IsolationContext(parent_root=root, child_root=root, isolation=isolation),
            '',
        )

    if isolation != 'worktree':
        return None, f'unsupported subagent isolation: {isolation}'

    if not (root / '.git').exists():
        return (
            None,
            'worktree isolation requires a git repository; use isolation=shared or run git init',
        )

    worktrees_dir = root / '.teaagent' / 'subagent-worktrees'
    worktrees_dir.mkdir(parents=True, exist_ok=True)
    worktree_path = worktrees_dir / session_key
    if worktree_path.exists():
        return None, f'worktree path already exists: {worktree_path}'

    result = subprocess.run(
        ['git', 'worktree', 'add', '--detach', str(worktree_path), 'HEAD'],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or '').strip()
        return None, f'git worktree add failed: {detail or "unknown error"}'

    return (
        IsolationContext(
            parent_root=root,
            child_root=worktree_path.resolve(),
            isolation=isolation,
            worktree_path=worktree_path.resolve(),
        ),
        '',
    )


def new_isolation_session_key(*, parent_run_id: str, def_name: str) -> str:
    suffix = uuid4().hex[:8]
    parent = parent_run_id.strip() or 'parent'
    return f'{parent[:12]}-{def_name}-{suffix}'

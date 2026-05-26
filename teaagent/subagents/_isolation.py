from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from teaagent.subagents._types import DEFAULT_SUBAGENT_ISOLATION
from teaagent.workspace_tools._config import _load_gitignore_matcher

SUPPORTED_SUBAGENT_ISOLATIONS = frozenset({'shared', 'worktree', 'container'})


@dataclass(frozen=True)
class IsolationContext:
    parent_root: Path
    child_root: Path
    isolation: str
    worktree_path: Optional[Path] = None
    container_path: Optional[Path] = None

    def cleanup(self) -> None:
        if self.worktree_path is not None:
            env = _git_subprocess_env()
            subprocess.run(
                ['git', 'worktree', 'remove', '--force', str(self.worktree_path)],
                cwd=self.parent_root,
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )
            subprocess.run(
                ['git', 'worktree', 'prune'],
                cwd=self.parent_root,
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )
        if self.container_path is not None:
            shutil.rmtree(self.container_path, ignore_errors=True)


def _git_subprocess_env() -> dict[str, str]:
    """Drop inherited git dir pointers so temp-repo worktrees are isolated."""
    env = os.environ.copy()
    for key in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE'):
        env.pop(key, None)
    return env


def normalize_subagent_isolation(value: Any) -> str | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return DEFAULT_SUBAGENT_ISOLATION
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if normalized in SUPPORTED_SUBAGENT_ISOLATIONS:
        return normalized
    return None


def _copy_workspace_snapshot(parent_root: Path, child_root: Path) -> None:
    root = parent_root.resolve()
    dest = child_root.resolve()
    is_ignored = _load_gitignore_matcher(root)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / '.teaagent').mkdir(parents=True, exist_ok=True)
    for src in sorted(root.rglob('*')):
        if not src.is_file() or src.is_symlink():
            continue
        rel = src.relative_to(root).as_posix()
        if rel.startswith('.teaagent/') or rel == '.teaagent':
            continue
        if is_ignored(rel):
            continue
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)


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

    if isolation == 'worktree':
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
            env=_git_subprocess_env(),
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

    if isolation == 'container':
        containers_dir = root / '.teaagent' / 'subagent-containers'
        containers_dir.mkdir(parents=True, exist_ok=True)
        container_path = containers_dir / session_key
        if container_path.exists():
            return None, f'container path already exists: {container_path}'
        try:
            _copy_workspace_snapshot(root, container_path)
        except OSError as exc:
            shutil.rmtree(container_path, ignore_errors=True)
            return None, f'container workspace snapshot failed: {exc}'
        return (
            IsolationContext(
                parent_root=root,
                child_root=container_path.resolve(),
                isolation=isolation,
                container_path=container_path.resolve(),
            ),
            '',
        )

    return None, f'unsupported subagent isolation: {isolation}'


def new_isolation_session_key(*, parent_run_id: str, def_name: str) -> str:
    suffix = uuid4().hex[:8]
    parent = parent_run_id.strip() or 'parent'
    return f'{parent[:12]}-{def_name}-{suffix}'

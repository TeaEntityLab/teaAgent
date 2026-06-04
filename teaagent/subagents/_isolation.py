from __future__ import annotations

import logging
import os
import shutil
import subprocess
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from teaagent.subagents._types import DEFAULT_SUBAGENT_ISOLATION
from teaagent.workspace_tools._config import _load_gitignore_matcher

logger = logging.getLogger(__name__)

SUPPORTED_SUBAGENT_ISOLATIONS = frozenset(
    {'shared', 'worktree', 'directory-snapshot', 'docker', 'auto'}
)
DEPRECATED_ISOLATION_ALIASES = {'container': 'directory-snapshot'}


@dataclass(frozen=True)
class IsolationContext:
    parent_root: Path
    child_root: Path
    isolation: str
    worktree_path: Optional[Path] = None
    container_path: Optional[Path] = None
    container_id: Optional[str] = None
    cpu_quota: Optional[float] = None
    memory_limit: Optional[str] = None

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
            # container_path is used for directory-snapshot compatibility
            logger.debug(f'Cleaning up directory snapshot: {self.container_path}')
            shutil.rmtree(self.container_path, ignore_errors=True)
        if self.container_id is not None:
            # Cleanup Docker container
            logger.debug(f'Cleaning up Docker container: {self.container_id}')
            subprocess.run(
                ['docker', 'rm', '-f', self.container_id],
                check=False,
                capture_output=True,
                text=True,
            )


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

    # Handle deprecated isolation mode names (normalized without warning here)
    if normalized in DEPRECATED_ISOLATION_ALIASES:
        return DEPRECATED_ISOLATION_ALIASES[normalized]

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
    cpu_quota: Optional[float] = None,
    memory_limit: Optional[str] = None,
) -> tuple[IsolationContext | None, str]:
    root = parent_root.resolve()

    # Check for deprecated isolation mode and trigger warning
    if isolation in DEPRECATED_ISOLATION_ALIASES:
        new_name = DEPRECATED_ISOLATION_ALIASES[isolation]
        warnings.warn(
            f"Subagent isolation mode '{isolation}' is deprecated and will be "
            f"removed in a future version. Use '{new_name}' instead. "
            f"Note: '{new_name}' does not provide OS-level container isolation - "
            f'it only creates a directory snapshot.',
            DeprecationWarning,
            stacklevel=2,
        )
        logger.warning(
            f"Subagent isolation mode '{isolation}' is deprecated. "
            f"Using '{new_name}' instead. "
            f'Note: This mode does not provide OS-level container isolation.'
        )
        isolation = new_name

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

    if isolation == 'directory-snapshot':
        snapshots_dir = root / '.teaagent' / 'subagent-snapshots'
        snapshots_dir.mkdir(parents=True, exist_ok=True)
        snapshot_path = snapshots_dir / session_key
        if snapshot_path.exists():
            return None, f'directory-snapshot path already exists: {snapshot_path}'
        try:
            _copy_workspace_snapshot(root, snapshot_path)
        except OSError as exc:
            shutil.rmtree(snapshot_path, ignore_errors=True)
            return None, f'directory-snapshot workspace copy failed: {exc}'
        return (
            IsolationContext(
                parent_root=root,
                child_root=snapshot_path.resolve(),
                isolation=isolation,
                container_path=snapshot_path.resolve(),  # Keep field name for compatibility
            ),
            '',
        )

    if isolation == 'docker':
        # Check if Docker is available
        docker_check = subprocess.run(
            ['docker', '--version'],
            check=False,
            capture_output=True,
            text=True,
        )
        if docker_check.returncode != 0:
            return None, 'docker isolation requires Docker to be installed and running'

        # Copy workspace to a temporary directory first
        temp_dir = root / '.teaagent' / 'subagent-docker-temp' / session_key
        temp_dir.mkdir(parents=True, exist_ok=True)
        try:
            _copy_workspace_snapshot(root, temp_dir)
        except OSError as exc:
            shutil.rmtree(temp_dir, ignore_errors=True)
            return None, f'docker workspace copy failed: {exc}'

        # Build Docker run command with resource limits
        docker_cmd = [
            'docker',
            'run',
            '-d',
            '--name',
            f'teaagent-subagent-{session_key}',
            '-v',
            f'{temp_dir}:/workspace:ro',
            '-w',
            '/workspace',
            '--user',
            '65534:65534',
            '--network',
            'none',
            '--cap-drop',
            'ALL',
            '--read-only',
            '--security-opt',
            'no-new-privileges',
        ]

        # Add CPU quota if specified
        if cpu_quota is not None:
            docker_cmd.extend(['--cpus', str(cpu_quota)])

        # Add memory limit if specified
        if memory_limit is not None:
            docker_cmd.extend(['--memory', memory_limit])

        docker_cmd.extend(['python:3.11-slim', 'sleep', 'infinity'])

        # Create and start a Docker container
        docker_run = subprocess.run(
            docker_cmd,
            check=False,
            capture_output=True,
            text=True,
        )

        if docker_run.returncode != 0:
            shutil.rmtree(temp_dir, ignore_errors=True)
            return None, f'docker container creation failed: {docker_run.stderr}'

        container_id = docker_run.stdout.strip()
        logger.info(f'Created Docker container: {container_id}')
        if cpu_quota:
            logger.info(f'CPU quota: {cpu_quota} cores')
        if memory_limit:
            logger.info(f'Memory limit: {memory_limit}')

        return (
            IsolationContext(
                parent_root=root,
                child_root=Path('/workspace'),
                isolation=isolation,
                container_path=temp_dir,
                container_id=container_id,
                cpu_quota=cpu_quota,
                memory_limit=memory_limit,
            ),
            '',
        )

    return None, f'unsupported subagent isolation: {isolation}'


def new_isolation_session_key(*, parent_run_id: str, def_name: str) -> str:
    # Sanitize def_name to prevent path traversal attacks (RSK-09)
    # Allow only alphanumeric characters, dashes, and underscores
    safe_def_name = ''.join(c for c in def_name if c.isalnum() or c in '-_')
    if not safe_def_name:
        safe_def_name = 'unnamed'
    suffix = uuid4().hex[:8]
    parent = parent_run_id.strip() or 'parent'
    # Also sanitize parent_run_id to be safe
    safe_parent = ''.join(c for c in parent if c.isalnum() or c in '-_')
    if not safe_parent:
        safe_parent = 'parent'
    return f'{safe_parent[:12]}-{safe_def_name}-{suffix}'

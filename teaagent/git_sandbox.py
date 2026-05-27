"""Git-native checkpoint branching for safe agent rollbacks.

This module provides GitBranchSandbox, which wraps git operations to create
temporary branches for agent runs, enabling safe rollbacks via native git
commands instead of manual file copying.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class GitSandboxResult:
    """Result of git sandbox operations."""

    success: bool
    branch_name: Optional[str] = None
    original_branch: Optional[str] = None
    error: Optional[str] = None


class GitBranchSandbox:
    """Git-based sandbox for safe agent rollbacks.

    Creates a temporary branch for agent runs, allowing rollback via
    native git operations. Falls back gracefully if not in a git repository.
    """

    def __init__(self, root: str | Path, run_id: str) -> None:
        self._root = Path(root).resolve()
        self._run_id = run_id
        self._branch_name = f'teaagent-run-{run_id}'
        self._original_branch: Optional[str] = None
        self._is_git_repo = self._check_git_repo()

    def _check_git_repo(self) -> bool:
        """Check if root is inside a git repository."""
        try:
            result = subprocess.run(
                ['git', 'rev-parse', '--is-inside-work-tree'],
                cwd=self._root,
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip() == 'true'
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def is_available(self) -> bool:
        """Check if git sandbox is available in this workspace."""
        return self._is_git_repo

    def start(self) -> GitSandboxResult:
        """Start the sandbox by creating a temporary branch."""
        if not self._is_git_repo:
            return GitSandboxResult(
                success=False,
                error='Not a git repository',
            )

        try:
            # Get current branch
            result = subprocess.run(
                ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                cwd=self._root,
                capture_output=True,
                text=True,
                check=True,
            )
            self._original_branch = result.stdout.strip()

            # Create and checkout temporary branch
            subprocess.run(
                ['git', 'checkout', '-b', self._branch_name],
                cwd=self._root,
                capture_output=True,
                text=True,
                check=True,
            )

            return GitSandboxResult(
                success=True,
                branch_name=self._branch_name,
                original_branch=self._original_branch,
            )
        except subprocess.CalledProcessError as exc:
            return GitSandboxResult(
                success=False,
                error=str(exc),
            )

    def commit(self, message: str) -> GitSandboxResult:
        """Commit current changes to the sandbox branch."""
        if not self._is_git_repo:
            return GitSandboxResult(
                success=False,
                error='Not a git repository',
            )

        try:
            subprocess.run(
                ['git', 'add', '-A'],
                cwd=self._root,
                capture_output=True,
                text=True,
                check=True,
            )
            subprocess.run(
                ['git', 'commit', '-m', message],
                cwd=self._root,
                capture_output=True,
                text=True,
                check=True,
            )
            return GitSandboxResult(success=True)
        except subprocess.CalledProcessError as exc:
            return GitSandboxResult(
                success=False,
                error=str(exc),
            )

    def rollback(self) -> GitSandboxResult:
        """Rollback to original branch and delete sandbox branch."""
        if not self._is_git_repo or not self._original_branch:
            return GitSandboxResult(
                success=False,
                error='Git sandbox not properly initialized',
            )

        try:
            # Switch back to original branch
            subprocess.run(
                ['git', 'checkout', self._original_branch],
                cwd=self._root,
                capture_output=True,
                text=True,
                check=True,
            )

            # Hard reset to discard any changes from sandbox branch
            subprocess.run(
                ['git', 'reset', '--hard', 'HEAD'],
                cwd=self._root,
                capture_output=True,
                text=True,
                check=True,
            )

            # Delete sandbox branch
            subprocess.run(
                ['git', 'branch', '-D', self._branch_name],
                cwd=self._root,
                capture_output=True,
                text=True,
                check=True,
            )

            return GitSandboxResult(success=True)
        except subprocess.CalledProcessError as exc:
            return GitSandboxResult(
                success=False,
                error=str(exc),
            )

    def merge(self) -> GitSandboxResult:
        """Merge sandbox branch back to original branch."""
        if not self._is_git_repo or not self._original_branch:
            return GitSandboxResult(
                success=False,
                error='Git sandbox not properly initialized',
            )

        try:
            # Switch back to original branch
            subprocess.run(
                ['git', 'checkout', self._original_branch],
                cwd=self._root,
                capture_output=True,
                text=True,
                check=True,
            )

            # Merge sandbox branch
            subprocess.run(
                ['git', 'merge', self._branch_name],
                cwd=self._root,
                capture_output=True,
                text=True,
                check=True,
            )

            # Delete sandbox branch
            subprocess.run(
                ['git', 'branch', '-D', self._branch_name],
                cwd=self._root,
                capture_output=True,
                text=True,
                check=True,
            )

            return GitSandboxResult(success=True)
        except subprocess.CalledProcessError as exc:
            return GitSandboxResult(
                success=False,
                error=str(exc),
            )

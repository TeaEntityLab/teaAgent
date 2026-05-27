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
    stash_id: Optional[str] = None


def is_git_repository(root: str | Path) -> bool:
    """Check if root is inside a git repository."""
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--is-inside-work-tree'],
            cwd=Path(root).resolve(),
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip() == 'true'
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def is_worktree_clean(root: str | Path) -> bool:
    """Check if git worktree is clean (no uncommitted changes)."""
    try:
        result = subprocess.run(
            ['git', 'status', '--porcelain'],
            cwd=Path(root).resolve(),
            capture_output=True,
            text=True,
            check=True,
        )
        return not result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def stash_save(root: str | Path, label: str) -> Optional[str]:
    """Save current changes to git stash and return stash ID.

    Uses `git stash push -u` to include untracked files.
    """
    try:
        result = subprocess.run(
            ['git', 'stash', 'push', '-u', '-m', label],
            cwd=Path(root).resolve(),
            capture_output=True,
            text=True,
            check=True,
        )
        # Extract stash reference from output
        if 'Saved working directory' in result.stdout:
            # Return stash@{0} format
            return 'stash@{0}'
        return None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def stash_pop(root: str | Path) -> bool:
    """Pop the most recent git stash."""
    try:
        subprocess.run(
            ['git', 'stash', 'pop'],
            cwd=Path(root).resolve(),
            capture_output=True,
            text=True,
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


class GitBranchSandbox:
    """Git-based sandbox for safe agent rollbacks.

    Creates a temporary branch for agent runs, allowing rollback via
    native git operations. Falls back gracefully if not in a git repository.
    """

    def __init__(self, root: str | Path, run_id: str) -> None:
        self._root = Path(root).resolve()
        self._run_id = run_id
        self._branch_name = f'teaagent-sandbox-{run_id}'
        self._original_branch: Optional[str] = None
        self._is_git_repo = is_git_repository(self._root)
        self._stash_id: Optional[str] = None

    def is_available(self) -> bool:
        """Check if git sandbox is available in this workspace."""
        return self._is_git_repo

    def is_clean(self) -> bool:
        """Check if worktree is clean."""
        return is_worktree_clean(self._root)

    def start(self, *, auto_stash: bool = False) -> GitSandboxResult:
        """Start the sandbox by creating a temporary branch.

        Args:
            auto_stash: If True, automatically stash dirty worktree before branching.

        Returns:
            GitSandboxResult with success status and branch information.
        """
        if not self._is_git_repo:
            return GitSandboxResult(
                success=False,
                error='Not a git repository',
            )

        # Preflight: Check if worktree is clean
        if not self.is_clean():
            if auto_stash:
                stash_label = f'TeaAgent dirty stash before run {self._run_id}'
                self._stash_id = stash_save(self._root, stash_label)
                if self._stash_id is None:
                    return GitSandboxResult(
                        success=False,
                        error='Failed to stash dirty worktree',
                    )
            else:
                return GitSandboxResult(
                    success=False,
                    error='Worktree is dirty. Commit or stash changes first, or use --auto-stash',
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
                stash_id=self._stash_id,
            )
        except subprocess.CalledProcessError as exc:
            return GitSandboxResult(
                success=False,
                error=str(exc),
            )

    def commit_transaction(self, tool_name: str, call_id: str) -> GitSandboxResult:
        """Commit current changes as a transaction with tool metadata.

        Args:
            tool_name: Name of the tool that made the changes.
            call_id: Call ID for the tool execution.

        Returns:
            GitSandboxResult with success status.
        """
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
            message = f'[TeaAgent Transaction] {tool_name} - {call_id}'
            subprocess.run(
                ['git', 'commit', '-m', message, '--no-verify'],
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
            # Clean sandbox branch before checkout to avoid conflicts
            subprocess.run(
                ['git', 'reset', '--hard', 'HEAD'],
                cwd=self._root,
                capture_output=True,
                text=True,
                check=True,
            )
            subprocess.run(
                ['git', 'clean', '-fd'],
                cwd=self._root,
                capture_output=True,
                text=True,
                check=True,
            )

            # Switch back to original branch
            subprocess.run(
                ['git', 'checkout', self._original_branch],
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

            # Pop stash if we auto-stashed
            if self._stash_id:
                stash_pop(self._root)

            return GitSandboxResult(success=True)
        except subprocess.CalledProcessError as exc:
            return GitSandboxResult(
                success=False,
                error=str(exc),
            )

    def merge(self, *, squash: bool = False) -> GitSandboxResult:
        """Merge sandbox branch back to original branch.

        Args:
            squash: If True, squash all commits into a single commit.

        Returns:
            GitSandboxResult with success status.
        """
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

            if squash:
                # Squash merge
                subprocess.run(
                    ['git', 'merge', '--squash', self._branch_name],
                    cwd=self._root,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                subprocess.run(
                    ['git', 'commit', '-m', f'chore: applied TeaAgent modifications for run {self._run_id}'],
                    cwd=self._root,
                    capture_output=True,
                    text=True,
                    check=True,
                )
            else:
                # Normal merge
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

            # Pop stash if we auto-stashed
            if self._stash_id:
                stash_pop(self._root)

            return GitSandboxResult(success=True)
        except subprocess.CalledProcessError as exc:
            # Preserve sandbox branch on merge failure
            return GitSandboxResult(
                success=False,
                error=f'Merge failed: {exc}. Sandbox branch preserved for manual resolution.',
            )

    def discard(self) -> GitSandboxResult:
        """Discard sandbox branch changes without merging."""
        return self.rollback()

    def keep(self) -> GitSandboxResult:
        """Keep sandbox branch for manual review."""
        # Just pop stash if we auto-stashed, leave branch active
        if self._stash_id:
            stash_pop(self._root)
        return GitSandboxResult(
            success=True,
            branch_name=self._branch_name,
            original_branch=self._original_branch,
        )


class GitTransactionSink:
    """Audit sink that commits git transactions after successful tool calls."""

    def __init__(self, sandbox: GitBranchSandbox) -> None:
        self._sandbox = sandbox
        self._pending: dict[str, dict[str, str]] = {}

    def __call__(self, event: object) -> None:
        from teaagent.audit import AuditEvent

        if not isinstance(event, AuditEvent):
            return

        payload = event.payload if isinstance(event.payload, dict) else {}

        if event.event_type == 'tool_call_started':
            self._on_tool_started(payload)
        elif event.event_type == 'tool_call_completed':
            self._on_tool_completed(payload)
        elif event.event_type in {'tool_call_failed', 'tool_call_blocked', 'tool_call_denied'}:
            self._on_tool_failed(payload)

    def _on_tool_started(self, payload: dict[str, object]) -> None:
        """Track tool call start for potential commit."""
        tool_name = payload.get('tool_name', '')
        call_id = payload.get('call_id')
        if isinstance(tool_name, str) and isinstance(call_id, str):
            self._pending[call_id] = {'tool_name': tool_name}

    def _on_tool_completed(self, payload: dict[str, object]) -> None:
        """Commit transaction after successful tool call."""
        call_id = payload.get('call_id')
        if not isinstance(call_id, str) or call_id not in self._pending:
            return

        tool_info = self._pending.pop(call_id)
        tool_name = tool_info['tool_name']

        # Commit for destructive path-based tools and mutating shell tools
        if tool_name in {
            'workspace_write_file',
            'workspace_apply_patch',
            'workspace_edit_at_hash',
            'workspace_run_shell_mutate',
            'workspace_run_shell',
        }:
            self._sandbox.commit_transaction(tool_name, call_id)

    def _on_tool_failed(self, payload: dict[str, object]) -> None:
        """Discard pending transaction on failure."""
        call_id = payload.get('call_id')
        if isinstance(call_id, str):
            self._pending.pop(call_id, None)

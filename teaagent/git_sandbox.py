"""Git-native checkpoint branching for safe agent rollbacks.

This module provides GitBranchSandbox, which wraps git operations to create
temporary branches for agent runs, enabling safe rollbacks via native git
commands instead of manual file copying.
"""

from __future__ import annotations

import json
import subprocess
import time
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class GitSandboxResult:
    """Result of git sandbox operations."""

    success: bool
    branch_name: Optional[str] = None
    original_branch: Optional[str] = None
    error: Optional[str] = None
    stash_id: Optional[str] = None
    has_conflicts: bool = False
    conflicted_files: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class TestExecutionResult:
    """Result of test execution on a sandbox branch."""

    option: str
    branch_name: str
    passed: bool
    duration_seconds: float
    exit_code: int
    output: str
    error: str = ''


class VFSSandbox:
    """In-memory virtual file system overlay for zero-pollution parallel experiments.

    Intercepts file writes and stores them in memory until explicitly flushed.
    Reads fall through to the actual filesystem for files not in memory.
    """

    def __init__(self, root: str | Path):
        """Initialize VFS sandbox.

        Args:
            root: Repository root path.
        """
        self._root = Path(root).resolve()
        self._memory_files: Dict[str, str] = {}
        self._deleted_files: set[str] = set()

    def write_file(self, path: str, content: str) -> None:
        """Write file to memory overlay.

        Args:
            path: Relative path from root.
            content: File content.
        """
        self._memory_files[path] = content
        self._deleted_files.discard(path)

    def read_file(self, path: str) -> str:
        """Read file from memory overlay or filesystem.

        Args:
            path: Relative path from root.

        Returns:
            File content.
        """
        if path in self._memory_files:
            return self._memory_files[path]
        if path in self._deleted_files:
            raise FileNotFoundError(f'File deleted in VFS: {path}')

        full_path = self._root / path
        if full_path.exists():
            return full_path.read_text(encoding='utf-8')
        raise FileNotFoundError(f'File not found: {path}')

    def delete_file(self, path: str) -> None:
        """Mark file as deleted in memory overlay.

        Args:
            path: Relative path from root.
        """
        self._memory_files.pop(path, None)
        self._deleted_files.add(path)

    def file_exists(self, path: str) -> bool:
        """Check if file exists in memory overlay or filesystem.

        Args:
            path: Relative path from root.

        Returns:
            True if file exists.
        """
        if path in self._memory_files:
            return True
        if path in self._deleted_files:
            return False
        return (self._root / path).exists()

    def list_files(self) -> list[str]:
        """List all files in memory overlay.

        Returns:
            List of file paths.
        """
        return list(self._memory_files.keys())

    def flush_to_disk(self) -> dict[str, bool]:
        """Flush all memory files to disk.

        Returns:
            Dict mapping file paths to flush success status.
        """
        results: dict[str, bool] = {}

        for path, content in self._memory_files.items():
            try:
                full_path = self._root / path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(content, encoding='utf-8')
                results[path] = True
            except Exception:
                results[path] = False

        # Delete files marked for deletion
        for path in self._deleted_files:
            try:
                full_path = self._root / path
                if full_path.exists():
                    full_path.unlink()
                results[path] = True
            except Exception:
                results[path] = False

        return results

    def clear(self) -> None:
        """Clear all memory files and deletions."""
        self._memory_files.clear()
        self._deleted_files.clear()

    def get_memory_size(self) -> int:
        """Get total size of memory files in bytes.

        Returns:
            Size in bytes.
        """
        return sum(len(content) for content in self._memory_files.values())


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

    def merge(
        self,
        *,
        squash: bool = False,
        enable_self_healing: bool = True,
        conflict_provider: str | None = None,
        conflict_model: str | None = None,
    ) -> GitSandboxResult:
        """Merge sandbox branch back to original branch.

        Args:
            squash: If True, squash all commits into a single commit.
            enable_self_healing: Whether to enable LSP self-healing for conflicts.
            conflict_provider: LLM provider for conflict resolution.
            conflict_model: Model name for conflict resolution.

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
                    [
                        'git',
                        'commit',
                        '-m',
                        f'chore: applied TeaAgent modifications for run {self._run_id}',
                    ],
                    cwd=self._root,
                    capture_output=True,
                    text=True,
                    check=True,
                )
            else:
                # Normal merge
                try:
                    subprocess.run(
                        ['git', 'merge', self._branch_name],
                        cwd=self._root,
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                except subprocess.CalledProcessError as e:
                    # Merge failed, check for conflicts
                    # Check if the failure was due to conflicts or other issues
                    if has_merge_conflicts(self._root):
                        # This is a conflict - proceed to conflict resolution
                        pass
                    else:
                        # This is a different merge error (e.g., unrelated histories, local changes)
                        return GitSandboxResult(
                            success=False,
                            error=f'Merge failed (not a conflict): {e.stderr or e.stdout or "Unknown error"}',
                        )

            # Check for merge conflicts
            if has_merge_conflicts(self._root):
                conflicted_files = get_conflicted_files(self._root)

                # Attempt self-healing conflict resolution if enabled
                if enable_self_healing and conflict_provider and conflict_model:
                    resolution_results = resolve_conflicts_with_llm(
                        self._root,
                        conflicted_files,
                        conflict_provider,
                        conflict_model,
                        enable_self_healing=True,
                        max_iterations=3,
                    )

                    # Check if all conflicts were resolved
                    manual_files = [
                        f
                        for f, status in resolution_results.items()
                        if status in ('manual', 'failed')
                    ]

                    if not manual_files:
                        # All conflicts resolved, stage and commit
                        subprocess.run(
                            ['git', 'add', '.'],
                            cwd=self._root,
                            capture_output=True,
                            text=True,
                            check=True,
                        )
                        subprocess.run(
                            [
                                'git',
                                'commit',
                                '-m',
                                f'chore: resolved merge conflicts for run {self._run_id}',
                            ],
                            cwd=self._root,
                            capture_output=True,
                            text=True,
                            check=True,
                        )
                    else:
                        return GitSandboxResult(
                            success=False,
                            error=f'Self-healing incomplete. {len(manual_files)} files require manual resolution: {manual_files}',
                            has_conflicts=True,
                            conflicted_files=manual_files,
                        )
                else:
                    return GitSandboxResult(
                        success=False,
                        error='Merge conflicts detected. Resolve conflicts manually or use conflict resolution tools.',
                        has_conflicts=True,
                        conflicted_files=conflicted_files,
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
        elif event.event_type in {
            'tool_call_failed',
            'tool_call_blocked',
            'tool_call_denied',
        }:
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


def find_orphaned_sandbox_branches(
    root: str | Path,
    background_store: Optional[object] = None,
) -> list[dict[str, Any]]:
    """Find orphaned sandbox branches that have no corresponding active run.

    Args:
        root: Git repository root path.
        background_store: Optional BackgroundRunStore to check for active runs.

    Returns:
        List of orphaned branch info dicts with keys: branch_name, run_id, reason.
    """
    from teaagent.ergonomics.background_run import BackgroundRunStore

    root_path = Path(root).resolve()

    if not is_git_repository(root_path):
        return []

    try:
        # Get all branches
        result = subprocess.run(
            ['git', 'branch', '--format=%(refname:short)'],
            cwd=root_path,
            capture_output=True,
            text=True,
            check=True,
        )
        branches = result.stdout.strip().split('\n') if result.stdout.strip() else []
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []

    # Initialize background store if not provided
    if background_store is None:
        try:
            background_store = BackgroundRunStore(root_path, readonly=True)
        except Exception:
            background_store = None

    # Get active run IDs from background store
    active_run_ids: set[str] = set()
    if background_store is not None:
        try:
            for record_file in background_store.dir.glob('*.json'):  # type: ignore[attr-defined]
                try:
                    data = json.loads(record_file.read_text(encoding='utf-8'))
                    if data.get('status') not in {'stopped', 'failed', 'completed'}:
                        background_id = data.get('background_id')
                        if background_id:
                            active_run_ids.add(background_id)
                except (json.JSONDecodeError, IOError):
                    continue
        except Exception:
            pass

    orphaned: list[dict[str, Any]] = []

    for branch in branches:
        # Check if branch matches sandbox patterns
        run_id = None
        if branch.startswith('teaagent-sandbox-'):
            run_id = branch.replace('teaagent-sandbox-', '')
        elif branch.startswith('teaagent-run-'):
            run_id = branch.replace('teaagent-run-', '')
        else:
            continue

        if not run_id:
            continue

        # Check if run is still active
        if run_id in active_run_ids:
            continue

        # Branch is orphaned
        orphaned.append(
            {
                'branch_name': branch,
                'run_id': run_id,
                'reason': 'no_active_run',
            }
        )

    return orphaned


def prune_sandbox_branch(root: str | Path, branch_name: str) -> bool:
    """Delete a sandbox branch.

    Args:
        root: Git repository root path.
        branch_name: Branch name to delete.

    Returns:
        True if deletion succeeded, False otherwise.
    """
    root_path = Path(root).resolve()

    if not is_git_repository(root_path):
        return False

    try:
        subprocess.run(
            ['git', 'branch', '-D', branch_name],
            cwd=root_path,
            capture_output=True,
            text=True,
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def has_merge_conflicts(root: str | Path) -> bool:
    """Check if there are unmerged files (merge conflicts) in the worktree.

    Args:
        root: Git repository root path.

    Returns:
        True if there are merge conflicts, False otherwise.
    """
    root_path = Path(root).resolve()

    if not is_git_repository(root_path):
        return False

    try:
        result = subprocess.run(
            ['git', 'status', '--porcelain'],
            cwd=root_path,
            capture_output=True,
            text=True,
            check=True,
        )
        # Check for lines with 'UU' (both modified) or 'AA' (both added)
        for line in result.stdout.strip().split('\n'):
            if line.startswith(('UU', 'AA', 'DD', 'AU', 'UA', 'DU', 'UD')):
                return True
        return False
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def get_conflicted_files(root: str | Path) -> list[str]:
    """Get list of files with merge conflicts.

    Args:
        root: Git repository root path.

    Returns:
        List of file paths with conflicts.
    """
    root_path = Path(root).resolve()

    if not is_git_repository(root_path):
        return []

    try:
        result = subprocess.run(
            ['git', 'diff', '--name-only', '--diff-filter=U'],
            cwd=root_path,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip().split('\n') if result.stdout.strip() else []
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []


def resolve_conflict_accept_ours(root: str | Path, file_path: str) -> bool:
    """Accept our version (current branch) for a conflicted file.

    Args:
        root: Git repository root path.
        file_path: Relative path to conflicted file.

    Returns:
        True if resolution succeeded, False otherwise.
    """
    root_path = Path(root).resolve()

    if not is_git_repository(root_path):
        return False

    try:
        subprocess.run(
            ['git', 'checkout', '--ours', file_path],
            cwd=root_path,
            capture_output=True,
            text=True,
            check=True,
        )
        subprocess.run(
            ['git', 'add', file_path],
            cwd=root_path,
            capture_output=True,
            text=True,
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def resolve_conflict_accept_theirs(root: str | Path, file_path: str) -> bool:
    """Accept their version (incoming branch) for a conflicted file.

    Args:
        root: Git repository root path.
        file_path: Relative path to conflicted file.

    Returns:
        True if resolution succeeded, False otherwise.
    """
    root_path = Path(root).resolve()

    if not is_git_repository(root_path):
        return False

    try:
        subprocess.run(
            ['git', 'checkout', '--theirs', file_path],
            cwd=root_path,
            capture_output=True,
            text=True,
            check=True,
        )
        subprocess.run(
            ['git', 'add', file_path],
            cwd=root_path,
            capture_output=True,
            text=True,
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def abort_merge(root: str | Path) -> bool:
    """Abort the current merge operation.

    Args:
        root: Git repository root path.

    Returns:
        True if abort succeeded, False otherwise.
    """
    root_path = Path(root).resolve()

    if not is_git_repository(root_path):
        return False

    try:
        subprocess.run(
            ['git', 'merge', '--abort'],
            cwd=root_path,
            capture_output=True,
            text=True,
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def extract_conflict_context(
    root: str | Path, file_path: str
) -> Optional[dict[str, str]]:
    """Extract conflict markers and context from a conflicted file.

    Args:
        root: Git repository root path.
        file_path: Relative path to conflicted file.

    Returns:
        Dict with 'ours', 'theirs', and 'base' content, or None if extraction fails.
    """
    root_path = Path(root).resolve()
    file_full_path = root_path / file_path

    if not file_full_path.exists():
        return None

    try:
        content = file_full_path.read_text(encoding='utf-8')

        # Extract conflict sections
        lines = content.split('\n')
        sections = {'ours': '', 'theirs': '', 'base': ''}
        current_section = None

        for line in lines:
            if line.startswith('<<<<<<<'):
                current_section = 'ours'
                sections['ours'] = ''
            elif line.startswith('======='):
                current_section = 'theirs'
                sections['theirs'] = ''
            elif line.startswith('>>>>>>>'):
                current_section = None
            elif current_section:
                sections[current_section] += line + '\n'

        # Try to get base version using git show
        try:
            result = subprocess.run(
                ['git', 'show', ':1:' + file_path],
                cwd=root_path,
                capture_output=True,
                text=True,
                check=True,
            )
            sections['base'] = result.stdout
        except (subprocess.CalledProcessError, FileNotFoundError):
            sections['base'] = ''

        return sections
    except (IOError, UnicodeDecodeError):
        return None


def apply_llm_resolution(
    root: str | Path, file_path: str, resolved_content: str
) -> bool:
    """Apply LLM-resolved content to a conflicted file.

    Args:
        root: Git repository root path.
        file_path: Relative path to conflicted file.
        resolved_content: The resolved content from LLM.

    Returns:
        True if application succeeded, False otherwise.
    """
    root_path = Path(root).resolve()
    file_full_path = root_path / file_path

    try:
        file_full_path.write_text(resolved_content, encoding='utf-8')
        subprocess.run(
            ['git', 'add', file_path],
            cwd=root_path,
            capture_output=True,
            text=True,
            check=True,
        )
        return True
    except (IOError, subprocess.CalledProcessError):
        return False


def resolve_conflicts_with_llm(
    root: str | Path,
    conflicted_files: list[str],
    provider: str,
    model: str,
    *,
    enable_self_healing: bool = True,
    max_iterations: int = 3,
) -> dict[str, str]:
    """Resolve merge conflicts using LLM with optional self-healing.

    Args:
        root: Git repository root path.
        conflicted_files: List of conflicted file paths.
        provider: LLM provider to use.
        model: Model name to use.
        enable_self_healing: Whether to enable LSP/compiler feedback loop.
        max_iterations: Maximum self-healing iterations per file.

    Returns:
        Dict mapping file paths to resolution status ('resolved', 'failed', 'skipped', 'manual').
    """
    from teaagent.llm._config import PROVIDER_CONFIGS, create_llm_adapter

    root_path = Path(root).resolve()
    results: dict[str, str] = {}

    config = PROVIDER_CONFIGS.get(provider)
    if not config:
        for file_path in conflicted_files:
            results[file_path] = 'skipped'
        return results

    try:
        adapter = create_llm_adapter(provider, model=model)
    except Exception:
        for file_path in conflicted_files:
            results[file_path] = 'skipped'
        return results

    for file_path in conflicted_files:
        context = extract_conflict_context(root_path, file_path)
        if not context:
            results[file_path] = 'failed'
            continue

        # Self-healing loop
        resolved_content = None
        for iteration in range(max_iterations + 1):
            # Build prompt for LLM
            if iteration == 0:
                prompt = f"""You are a code merge conflict resolver. Resolve the following merge conflict by intelligently combining both versions.

File: {file_path}

Base version (common ancestor):
```
{context['base']}
```

Our version (current branch):
```
{context['ours']}
```

Their version (incoming branch):
```
{context['theirs']}
```

Instructions:
1. Analyze the differences between the three versions
2. Create a merged version that preserves the intent of both changes
3. Remove all conflict markers (<<<<<<<, =======, >>>>>>>)
4. Output ONLY the resolved file content, no explanations
5. If the changes are truly incompatible, prefer the incoming (their) version for agent changes

Resolved file content:"""
            else:
                # Self-healing iteration with error feedback
                prompt = f"""You are a code merge conflict resolver. The previous merge attempt failed with errors. Fix the issues.

File: {file_path}

Previous attempt had these errors:
{context.get('lsp_errors', 'No error details available')}

Previous merged content:
```
{resolved_content}
```

Instructions:
1. Fix the syntax/type errors shown above
2. Ensure the code is valid and compiles
3. Preserve the merge intent from the original conflict
4. Output ONLY the corrected file content, no explanations

Corrected file content:"""

            try:
                from teaagent.llm._types import LLMRequest, LLMMessage
                request = LLMRequest(
                    messages=[LLMMessage(role='user', content=prompt)],
                    max_tokens=8192,
                    temperature=0.1
                )
                response = adapter.complete(request)
                resolved_content = str(response).strip()

                # Apply resolution
                if not apply_llm_resolution(root_path, file_path, resolved_content):
                    results[file_path] = 'failed'
                    break

                # LSP validation if self-healing enabled
                if enable_self_healing and iteration < max_iterations:
                    lsp_errors = run_lsp_validation(root_path, file_path)
                    if lsp_errors:
                        context['lsp_errors'] = lsp_errors
                        continue  # Try again with error feedback

                # Success
                results[file_path] = 'resolved'
                break

            except Exception:
                results[file_path] = 'failed'
                break

        # Mark for manual resolution if max iterations reached without success
        if file_path not in results:
            results[file_path] = 'manual'

    return results


def run_lsp_validation(root: Path, file_path: str) -> str:
    """Run LSP/compiler validation on a file.

    Args:
        root: Repository root path.
        file_path: Path to the file to validate.

    Returns:
        Error message string, or empty string if no errors.
    """
    import subprocess

    full_path = root / file_path

    # Determine file type and run appropriate linter
    if file_path.endswith('.py'):
        try:
            result = subprocess.run(
                ['ruff', 'check', str(full_path)],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                return result.stdout or result.stderr
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        try:
            result = subprocess.run(
                ['mypy', str(full_path)],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                return result.stdout or result.stderr
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    return ''


class ParallelExperimentStack:
    """Manage multiple parallel sandbox branches for experimentation."""

    def __init__(self, root: str | Path, run_id: str, options: list[str]):
        """Initialize parallel experiment stack.

        Args:
            root: Git repository root path.
            run_id: Base run ID for all experiments.
            options: List of option names (e.g., ['optA', 'optB', 'optC']).
        """
        self._root = Path(root).resolve()
        self._run_id = run_id
        self._options = options
        self._sandboxes: dict[str, GitBranchSandbox] = {}
        self._original_branch: Optional[str] = None

    def start_all(self, auto_stash: bool = False) -> dict[str, GitSandboxResult]:
        """Start all sandbox branches for parallel experimentation.

        Args:
            auto_stash: Whether to auto-stash uncommitted changes.

        Returns:
            Dict mapping option names to their sandbox results.
        """
        results: dict[str, GitSandboxResult] = {}

        if not is_git_repository(self._root):
            for option in self._options:
                results[option] = GitSandboxResult(
                    success=False,
                    error='Not a git repository',
                )
            return results

        # Get original branch
        try:
            result = subprocess.run(
                ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                cwd=self._root,
                capture_output=True,
                text=True,
                check=True,
            )
            self._original_branch = result.stdout.strip()
        except subprocess.CalledProcessError:
            for option in self._options:
                results[option] = GitSandboxResult(
                    success=False,
                    error='Failed to get current branch',
                )
            return results

        # Create sandbox for each option
        for option in self._options:
            GitBranchSandbox(self._root, run_id=f'{self._run_id}-{option}')
            self._sandboxes[option] = GitBranchSandbox(
                self._root, run_id=f'{self._run_id}-{option}'
            )
            results[option] = self._sandboxes[option].start(auto_stash=auto_stash)

        return results

    def get_sandbox(self, option: str) -> Optional[GitBranchSandbox]:
        """Get sandbox for a specific option.

        Args:
            option: Option name.

        Returns:
            GitBranchSandbox instance or None if not found.
        """
        return self._sandboxes.get(option)

    def compare_branches(self) -> dict[str, dict[str, Any]]:
        """Compare all experimental branches against original.

        Returns:
            Dict mapping option names to comparison stats (files_changed, insertions, deletions).
        """
        comparisons: dict[str, dict[str, Any]] = {}

        if not self._original_branch:
            return comparisons

        for option, sandbox in self._sandboxes.items():
            try:
                result = subprocess.run(
                    [
                        'git',
                        'diff',
                        '--stat',
                        self._original_branch,
                        sandbox._branch_name,
                    ],
                    cwd=self._root,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                stats = result.stdout.strip()

                # Parse stats
                files_changed = 0
                insertions = 0
                deletions = 0

                for line in stats.split('\n'):
                    if 'file' in line or 'files' in line:
                        parts = line.split()
                        if parts:
                            with suppress(ValueError):
                                files_changed = int(parts[0])
                    if 'insertion' in line or 'insertions' in line:
                        parts = line.split()
                        if parts:
                            with suppress(ValueError):
                                insertions = int(parts[0])
                    if 'deletion' in line or 'deletions' in line:
                        parts = line.split()
                        if parts:
                            with suppress(ValueError):
                                deletions = int(parts[0])

                comparisons[option] = {
                    'files_changed': files_changed,
                    'insertions': insertions,
                    'deletions': deletions,
                    'diff_stat': stats,
                }
            except subprocess.CalledProcessError:
                comparisons[option] = {
                    'files_changed': 0,
                    'insertions': 0,
                    'deletions': 0,
                    'diff_stat': 'Failed to compare',
                }

        return comparisons

    def cleanup_all(
        self, keep_best: Optional[str] = None, cleanup_memory: bool = True
    ) -> dict[str, bool]:
        """Delete all sandbox branches, optionally keeping the best one.

        Args:
            keep_best: Option name to keep (e.g., 'optA').
            cleanup_memory: Whether to clean up memory entries for deleted branches.

        Returns:
            Dict mapping option names to deletion success status.
        """
        results: dict[str, bool] = {}

        # Switch back to original branch first
        if self._original_branch:
            with suppress(subprocess.CalledProcessError):
                subprocess.run(
                    ['git', 'checkout', self._original_branch],
                    cwd=self._root,
                    capture_output=True,
                    text=True,
                    check=True,
                )

        # Clean up memory for deleted branches
        if cleanup_memory:
            try:
                from teaagent.memory import MemoryCatalog

                catalog = MemoryCatalog(self._root)
                for option, sandbox in self._sandboxes.items():
                    if keep_best and option == keep_best:
                        continue
                    # Quarantine memory for deleted branch
                    catalog.quarantine_by_branch(
                        sandbox._branch_name,
                        reason=f'Experiment branch {option} deleted during cleanup',
                    )
            except Exception:
                pass  # Continue with git cleanup even if memory cleanup fails

        for option, sandbox in self._sandboxes.items():
            if keep_best and option == keep_best:
                results[option] = True  # Kept, not deleted
                continue

            try:
                subprocess.run(
                    ['git', 'branch', '-D', sandbox._branch_name],
                    cwd=self._root,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                results[option] = True
            except subprocess.CalledProcessError:
                results[option] = False

        return results

    def run_tests(
        self,
        test_command: list[str],
        timeout_seconds: int = 300,
    ) -> dict[str, TestExecutionResult]:
        """Run tests on all sandbox branches and collect results.

        Args:
            test_command: Test command to run (e.g., ['pytest', '-xvs']).
            timeout_seconds: Maximum time to wait for tests per branch.

        Returns:
            Dict mapping option names to their test results.
        """
        results: dict[str, TestExecutionResult] = {}

        if not is_git_repository(self._root):
            for option in self._options:
                results[option] = TestExecutionResult(
                    option=option,
                    branch_name='',
                    passed=False,
                    duration_seconds=0.0,
                    exit_code=-1,
                    output='',
                    error='Not a git repository',
                )
            return results

        # Switch back to original branch first
        original_branch = self._original_branch
        if original_branch:
            with suppress(subprocess.CalledProcessError):
                subprocess.run(
                    ['git', 'checkout', original_branch],
                    cwd=self._root,
                    capture_output=True,
                    text=True,
                    check=True,
                )

        for option, sandbox in self._sandboxes.items():
            try:
                # Switch to sandbox branch
                subprocess.run(
                    ['git', 'checkout', sandbox._branch_name],
                    cwd=self._root,
                    capture_output=True,
                    text=True,
                    check=True,
                )

                # Run tests with timeout
                start_time = time.time()
                try:
                    result = subprocess.run(
                        test_command,
                        cwd=self._root,
                        capture_output=True,
                        text=True,
                        timeout=timeout_seconds,
                    )
                    duration = time.time() - start_time
                    passed = result.returncode == 0

                    results[option] = TestExecutionResult(
                        option=option,
                        branch_name=sandbox._branch_name,
                        passed=passed,
                        duration_seconds=duration,
                        exit_code=result.returncode,
                        output=result.stdout,
                        error=result.stderr,
                    )
                except subprocess.TimeoutExpired:
                    duration = time.time() - start_time
                    results[option] = TestExecutionResult(
                        option=option,
                        branch_name=sandbox._branch_name,
                        passed=False,
                        duration_seconds=duration,
                        exit_code=-1,
                        output='',
                        error=f'Tests timed out after {timeout_seconds} seconds',
                    )
            except subprocess.CalledProcessError as e:
                results[option] = TestExecutionResult(
                    option=option,
                    branch_name=sandbox._branch_name,
                    passed=False,
                    duration_seconds=0.0,
                    exit_code=e.returncode,
                    output='',
                    error=str(e),
                )
            except Exception as e:
                results[option] = TestExecutionResult(
                    option=option,
                    branch_name=sandbox._branch_name,
                    passed=False,
                    duration_seconds=0.0,
                    exit_code=-1,
                    output='',
                    error=str(e),
                )

        # Switch back to original branch
        if original_branch:
            with suppress(subprocess.CalledProcessError):
                subprocess.run(
                    ['git', 'checkout', original_branch],
                    cwd=self._root,
                    capture_output=True,
                    text=True,
                    check=True,
                )

        return results


class OSSandbox:
    """OS-level sandboxing for shell command execution.

    Provides process isolation and filesystem restrictions for safe
    execution of agent shell commands.
    """

    def __init__(self, root: str | Path, allowed_paths: Optional[list[str]] = None):
        """Initialize OS-level sandbox.

        Args:
            root: Git repository root path (primary allowed path).
            allowed_paths: Additional allowed paths (e.g., temp directories).
        """
        self._root = Path(root).resolve()
        self._allowed_paths: list[str] = [str(self._root)]
        if allowed_paths:
            self._allowed_paths.extend([str(Path(p).resolve()) for p in allowed_paths])

    def is_path_allowed(self, path: str) -> bool:
        """Check if a path is within allowed sandbox boundaries.

        Args:
            path: Path to check.

        Returns:
            True if path is allowed, False otherwise.
        """
        try:
            resolved_path = Path(path).resolve()
            for allowed in self._allowed_paths:
                allowed_path = Path(allowed).resolve()
                try:
                    resolved_path.relative_to(allowed_path)
                    return True
                except ValueError:
                    continue
            return False
        except (ValueError, OSError):
            return False

    def sanitize_environment(
        self, env: Optional[dict[str, str]] = None
    ) -> dict[str, str]:
        """Sanitize environment variables for safe execution.

        Args:
            env: Original environment (uses os.environ if None).

        Returns:
            Sanitized environment dict.
        """
        import os

        if env is None:
            env = dict(os.environ)

        # Remove sensitive environment variables
        sensitive_keys = [
            'SSH_PRIVATE_KEY',
            'SSH_KEY',
            'AWS_SECRET_ACCESS_KEY',
            'GOOGLE_APPLICATION_CREDENTIALS',
            'GITHUB_TOKEN',
            'API_KEY',
            'SECRET_KEY',
            'PASSWORD',
            'TOKEN',
        ]

        for key in list(env.keys()):
            if any(sensitive in key.upper() for sensitive in sensitive_keys):
                del env[key]

        # Restrict PATH to safe directories
        safe_path = '/usr/bin:/bin:/usr/local/bin'
        env['PATH'] = safe_path

        # Set sandbox indicator
        env['TEAAGENT_SANDBOX'] = '1'

        return env

    def execute_sandboxed(
        self,
        command: list[str],
        cwd: Optional[str] = None,
        timeout: int = 300,
    ) -> dict[str, Any]:
        """Execute command in sandboxed environment.

        Args:
            command: Command and arguments to execute.
            cwd: Working directory (must be within allowed paths).
            timeout: Maximum execution time in seconds.

        Returns:
            Dict with 'success', 'stdout', 'stderr', 'exit_code'.
        """

        if cwd and not self.is_path_allowed(cwd):
            return {
                'success': False,
                'stdout': '',
                'stderr': f'Working directory {cwd} is outside sandbox boundaries',
                'exit_code': -1,
            }

        working_dir = cwd if cwd else str(self._root)

        env = self.sanitize_environment()

        try:
            result = subprocess.run(
                command,
                cwd=working_dir,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return {
                'success': result.returncode == 0,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'exit_code': result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'stdout': '',
                'stderr': f'Command timed out after {timeout} seconds',
                'exit_code': -1,
            }
        except (subprocess.CalledProcessError, FileNotFoundError, OSError) as e:
            return {
                'success': False,
                'stdout': '',
                'stderr': str(e),
                'exit_code': -1,
            }

    def set_resource_limits(self) -> bool:
        """Set resource limits for the current process (Unix only).

        Args:
            None

        Returns:
            True if limits were set successfully, False otherwise.
        """
        try:
            import resource

            # Limit CPU time to 5 minutes
            resource.setrlimit(resource.RLIMIT_CPU, (300, 300))

            # Limit memory to 1GB
            resource.setrlimit(
                resource.RLIMIT_AS, (1024 * 1024 * 1024, 1024 * 1024 * 1024)
            )

            # Limit number of processes
            resource.setrlimit(resource.RLIMIT_NPROC, (100, 100))

            return True
        except (ImportError, ValueError, OSError):
            # Not available on Windows or permission denied
            return False

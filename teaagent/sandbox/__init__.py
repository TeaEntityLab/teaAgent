"""Sandbox primitives for TeaAgent."""

from __future__ import annotations

from teaagent.sandbox._git_branch import (
    GitBranchSandbox,
    GitSandboxResult,
    GitTransactionSink,
    abort_merge,
    apply_llm_resolution,
    extract_conflict_context,
    find_orphaned_sandbox_branches,
    get_conflicted_files,
    has_merge_conflicts,
    is_git_repository,
    is_worktree_clean,
    prune_sandbox_branch,
    resolve_conflict_accept_ours,
    resolve_conflict_accept_theirs,
    resolve_conflicts_with_llm,
    run_lsp_validation,
    stash_pop,
    stash_save,
)
from teaagent.sandbox._os_sandbox import OSSandbox
from teaagent.sandbox._parallel_experiment import (
    ParallelExperimentStack,
    TestExecutionResult,
)
from teaagent.sandbox._vfs_sandbox import VFSSandbox

__all__ = [
    'GitBranchSandbox',
    'GitSandboxResult',
    'GitTransactionSink',
    'OSSandbox',
    'ParallelExperimentStack',
    'TestExecutionResult',
    'VFSSandbox',
    'abort_merge',
    'apply_llm_resolution',
    'extract_conflict_context',
    'find_orphaned_sandbox_branches',
    'get_conflicted_files',
    'has_merge_conflicts',
    'is_git_repository',
    'is_worktree_clean',
    'prune_sandbox_branch',
    'resolve_conflict_accept_ours',
    'resolve_conflict_accept_theirs',
    'resolve_conflicts_with_llm',
    'run_lsp_validation',
    'stash_pop',
    'stash_save',
]

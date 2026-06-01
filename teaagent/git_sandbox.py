"""Backward-compatible shim for sandbox primitives.

Public sandbox APIs live in :mod:`teaagent.sandbox`. This module remains for
existing imports such as ``from teaagent.git_sandbox import GitBranchSandbox``.
"""

from __future__ import annotations

from teaagent.sandbox import (
    GitBranchSandbox,
    GitSandboxResult,
    GitTransactionSink,
    OSSandbox,
    ParallelExperimentStack,
    TestExecutionResult,
    VFSSandbox,
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

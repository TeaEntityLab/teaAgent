"""Git sandbox lifecycle helpers for agent run completion."""

from __future__ import annotations

import logging
import subprocess
import sys
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from teaagent.audit import AuditLogger
    from teaagent.runner import RunResult
    from teaagent.sandbox import GitBranchSandbox

logger = logging.getLogger(__name__)


def git_sandbox_audit_payload(sandbox: GitBranchSandbox) -> dict[str, Any]:
    """Serialize sandbox lifecycle fields for audit/evidence.

    Note: ``run_id`` is intentionally excluded — it is passed as the second
    positional argument to ``AuditLogger.record()``, and including it in the
    payload dict would cause a ``multiple values for argument 'run_id'`` error.
    """
    return {
        'branch_name': sandbox._branch_name,
        'original_branch': sandbox._original_branch,
        'stash_id': sandbox._stash_id,
    }


def record_git_sandbox_started(
    audit: AuditLogger,
    run_id: str,
    sandbox: GitBranchSandbox,
    *,
    auto_stash: bool,
    success: bool,
    error: str | None = None,
) -> None:
    """Record sandbox start in the run audit trail."""
    audit.record(
        'git_sandbox_started',
        run_id,
        auto_stash=auto_stash,
        success=success,
        error=error,
        **git_sandbox_audit_payload(sandbox),
    )


def record_git_sandbox_resolved(
    audit: AuditLogger,
    run_id: str,
    sandbox: GitBranchSandbox,
    *,
    resolution: str,
    success: bool,
    error: str | None = None,
) -> None:
    """Record sandbox resolution outcome in the run audit trail."""
    audit.record(
        'git_sandbox_resolved',
        run_id,
        resolution=resolution,
        success=success,
        error=error,
        **git_sandbox_audit_payload(sandbox),
    )


def _pop_stash(root: str, sandbox: GitBranchSandbox) -> None:
    if not sandbox._stash_id:
        return
    from teaagent.sandbox import stash_pop

    stash_pop(root, sandbox._stash_id)


def _handle_merge_conflicts(
    merge_result: Any,
    sandbox: GitBranchSandbox,
    args: Any,
) -> tuple[str, bool, str | None]:
    """Interactive conflict resolution after a failed merge."""
    print(
        f'[TeaAgent] Merge conflicts detected in {len(merge_result.conflicted_files)} file(s):'
    )
    for file in merge_result.conflicted_files:
        print(f'  - {file}')
    print('\nResolve conflicts:')
    print('  [l] Let LLM auto-resolve conflicts')
    print('  [a] Accept Agent version (theirs)')
    print('  [d] Accept Developer version (ours)')
    print('  [b] Abort merge and keep sandbox branch')
    print('  [m] Launch mergetool for manual resolution')
    resolution = input('Choice: ').strip().lower()

    from teaagent.sandbox import (
        abort_merge,
        resolve_conflict_accept_ours,
        resolve_conflict_accept_theirs,
        resolve_conflicts_with_llm,
    )

    if resolution == 'l':
        print('[TeaAgent] Using LLM to resolve conflicts...')
        llm_results = resolve_conflicts_with_llm(
            args.root,
            merge_result.conflicted_files,
            args.provider,
            args.model,
        )
        resolved_count = sum(
            1 for status in llm_results.values() if status == 'resolved'
        )
        failed_count = sum(1 for status in llm_results.values() if status == 'failed')
        skipped_count = sum(1 for status in llm_results.values() if status == 'skipped')
        print('[TeaAgent] LLM resolution results:')
        print(f'  Resolved: {resolved_count}')
        print(f'  Failed: {failed_count}')
        print(f'  Skipped: {skipped_count}')
        if resolved_count == len(merge_result.conflicted_files):
            subprocess.run(
                ['git', 'commit', '--no-edit'],
                cwd=args.root,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ['git', 'branch', '-D', sandbox._branch_name],
                cwd=args.root,
                check=True,
                capture_output=True,
            )
            _pop_stash(args.root, sandbox)
            print('[TeaAgent] All conflicts resolved by LLM. Merge completed.')
            return 'merge', True, None
        print(
            '[TeaAgent] Some conflicts could not be resolved. Manual intervention required.',
            file=sys.stderr,
        )
        abort_merge(args.root)
        print(
            '[TeaAgent] Merge aborted. Sandbox branch preserved for manual resolution.',
            file=sys.stderr,
        )
        return 'keep', False, 'conflicts_unresolved'

    if resolution == 'a':
        for file in merge_result.conflicted_files:
            if resolve_conflict_accept_theirs(args.root, file):
                print(f'  Accepted Agent version for {file}')
            else:
                print(f'  Failed to resolve {file}', file=sys.stderr)
        subprocess.run(
            ['git', 'commit', '--no-edit'],
            cwd=args.root,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ['git', 'branch', '-D', sandbox._branch_name],
            cwd=args.root,
            check=True,
            capture_output=True,
        )
        _pop_stash(args.root, sandbox)
        print('[TeaAgent] Conflicts resolved using Agent version.')
        return 'merge', True, None

    if resolution == 'd':
        for file in merge_result.conflicted_files:
            if resolve_conflict_accept_ours(args.root, file):
                print(f'  Accepted Developer version for {file}')
            else:
                print(f'  Failed to resolve {file}', file=sys.stderr)
        subprocess.run(
            ['git', 'commit', '--no-edit'],
            cwd=args.root,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ['git', 'branch', '-D', sandbox._branch_name],
            cwd=args.root,
            check=True,
            capture_output=True,
        )
        _pop_stash(args.root, sandbox)
        print('[TeaAgent] Conflicts resolved using Developer version.')
        return 'merge', True, None

    if resolution == 'b':
        abort_merge(args.root)
        print(
            '[TeaAgent] Merge aborted. Sandbox branch preserved for manual resolution.',
            file=sys.stderr,
        )
        return 'keep', True, None

    if resolution == 'm':
        print('[TeaAgent] Launching mergetool...')
        subprocess.run(['git', 'mergetool'], cwd=args.root)
        subprocess.run(
            ['git', 'commit', '--no-edit'],
            cwd=args.root,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ['git', 'branch', '-D', sandbox._branch_name],
            cwd=args.root,
            check=True,
            capture_output=True,
        )
        _pop_stash(args.root, sandbox)
        print(
            '[TeaAgent] Merge completed with manual resolution.',
            file=sys.stderr,
        )
        return 'merge', True, None

    return 'keep', False, 'unknown_conflict_resolution'


def resolve_git_sandbox_after_run(
    *,
    audit: AuditLogger,
    run_id: str,
    sandbox: GitBranchSandbox,
    args: Any,
    result: RunResult,
    show_interactive_diff: Any,
) -> None:
    """Prompt for sandbox resolution and persist lifecycle state in audit."""
    if not sandbox.is_available():
        return

    try:
        diff_result = subprocess.run(
            ['git', 'diff', '--stat', f'{sandbox._original_branch}..HEAD'],
            cwd=args.root,
            capture_output=True,
            text=True,
        )
        if diff_result.stdout.strip():
            print('\n[TeaAgent] Changes in sandbox branch:')
            print(diff_result.stdout)
        else:
            print('\n[TeaAgent] No changes made in sandbox branch.')
    except Exception as exc:
        print('\n[TeaAgent] Could not generate diff summary.')
        logger.warning('Failed to generate diff summary: %s', exc)

    if result.status == 'completed':
        print(f"\nApply changes back to '{sandbox._original_branch}'?")
        if not show_interactive_diff(args.root, sandbox._branch_name):
            print('[TeaAgent] Merge cancelled by user.')
            record_git_sandbox_resolved(
                audit,
                run_id,
                sandbox,
                resolution='cancelled',
                success=True,
            )
            return

        print(
            '  [m]erge (normal) / [s]quash and commit / [d]iscard / [k]eep branch for review: ',
            end='',
        )
        choice = input().strip().lower()
    else:
        print('\n[TeaAgent] Run did not complete. Resolve sandbox branch:')
        print('  [d]iscard / [k]eep branch for review: ', end='')
        choice = input().strip().lower()

    resolution = 'keep'
    success = True
    error: str | None = None

    if choice in ('m', ''):
        resolution = 'merge'
        merge_result = sandbox.merge(squash=False)
        if merge_result.success:
            print('[TeaAgent] Merged sandbox branch successfully.')
        elif merge_result.has_conflicts:
            resolution, success, error = _handle_merge_conflicts(
                merge_result, sandbox, args
            )
        else:
            success = False
            error = merge_result.error
            print(f'[TeaAgent] Merge failed: {error}', file=sys.stderr)
    elif choice == 's':
        resolution = 'squash'
        merge_result = sandbox.merge(squash=True)
        if merge_result.success:
            print('[TeaAgent] Squash-merged sandbox branch successfully.')
        else:
            success = False
            error = merge_result.error
            print(f'[TeaAgent] Squash merge failed: {error}', file=sys.stderr)
    elif choice == 'd':
        resolution = 'discard'
        discard_result = sandbox.discard()
        if discard_result.success:
            print('[TeaAgent] Discarded sandbox branch changes.')
        else:
            success = False
            error = discard_result.error
            print(f'[TeaAgent] Discard failed: {error}', file=sys.stderr)
    elif choice == 'k':
        resolution = 'keep'
        keep_result = sandbox.keep()
        if keep_result.success:
            print(
                f'[TeaAgent] Kept sandbox branch {keep_result.branch_name} for review.'
            )
        else:
            success = False
            error = keep_result.error
    else:
        resolution = 'keep'
        keep_result = sandbox.keep()
        if keep_result.success:
            print(
                f'[TeaAgent] Unknown choice; kept sandbox branch {keep_result.branch_name}.'
            )
        else:
            success = False
            error = keep_result.error

    record_git_sandbox_resolved(
        audit,
        run_id,
        sandbox,
        resolution=resolution,
        success=success,
        error=error,
    )

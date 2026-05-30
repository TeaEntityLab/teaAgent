"""Parallel experiment CLI handlers for teaagent.

This module provides handlers for the `teaagent experiment` command group,
which allows CLI operators to manage parallel sandbox branches for experimentation.
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from teaagent.cli._output import print_json
from teaagent.sandbox import (
    ParallelExperimentStack,
    find_orphaned_sandbox_branches,
    is_git_repository,
    prune_sandbox_branch,
)


def experiment_list(args: argparse.Namespace) -> int:
    """List all active and orphaned sandbox branches.

    Args:
        args: CLI arguments with `root` attribute.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    root = Path(args.root).resolve()

    if not is_git_repository(root):
        print_json(
            {
                'ok': False,
                'error': 'Not a git repository',
                'branches': [],
            }
        )
        return 1

    # Find orphaned branches
    orphaned = find_orphaned_sandbox_branches(root)

    # Get all sandbox branches
    try:
        result = subprocess.run(
            ['git', 'branch', '--format=%(refname:short)'],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        )
        all_branches = (
            result.stdout.strip().split('\n') if result.stdout.strip() else []
        )
    except subprocess.CalledProcessError:
        all_branches = []

    # Filter sandbox branches
    sandbox_branches = [
        b
        for b in all_branches
        if b.startswith('teaagent-sandbox-') or b.startswith('teaagent-run-')
    ]

    # Get current branch
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        )
        current_branch = result.stdout.strip()
    except subprocess.CalledProcessError:
        current_branch = None

    # Build branch info
    branches_info = []
    for branch in sandbox_branches:
        is_orphaned = any(o['branch_name'] == branch for o in orphaned)
        is_current = branch == current_branch

        # Extract run ID
        run_id = None
        if branch.startswith('teaagent-sandbox-'):
            run_id = branch.replace('teaagent-sandbox-', '')
        elif branch.startswith('teaagent-run-'):
            run_id = branch.replace('teaagent-run-', '')

        branches_info.append(
            {
                'branch_name': branch,
                'run_id': run_id,
                'orphaned': is_orphaned,
                'current': is_current,
            }
        )

    print_json(
        {
            'ok': True,
            'current_branch': current_branch,
            'branches': branches_info,
            'orphaned_count': len(orphaned),
        }
    )
    return 0


def experiment_compare(args: argparse.Namespace) -> int:
    """Compare experimental branches against the original branch.

    Args:
        args: CLI arguments with `root`, `run_id`, and `options` attributes.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    root = Path(args.root).resolve()

    if not is_git_repository(root):
        print_json(
            {
                'ok': False,
                'error': 'Not a git repository',
                'comparisons': {},
            }
        )
        return 1

    # Parse options
    options = args.options.split(',') if args.options else []
    if not options:
        print_json(
            {
                'ok': False,
                'error': 'No options specified. Use --options opt1,opt2,...',
                'comparisons': {},
            }
        )
        return 1

    # Create parallel experiment stack
    stack = ParallelExperimentStack(root, args.run_id, options)

    # Compare branches
    comparisons = stack.compare_branches()

    # Run tests if requested
    test_results = {}
    if getattr(args, 'run_tests', False):
        test_command_str = getattr(args, 'test_command', 'pytest -xvs')
        test_command = test_command_str.split()
        timeout = getattr(args, 'test_timeout', 300)
        test_results_raw = stack.run_tests(test_command, timeout_seconds=timeout)
        # Convert TestResult to dict for JSON serialization
        for option, result in test_results_raw.items():
            test_results[option] = {
                'passed': result.passed,
                'duration_seconds': result.duration_seconds,
                'exit_code': result.exit_code,
                'output': result.output[:1000]
                if result.output
                else '',  # Truncate output
                'error': result.error[:500] if result.error else '',  # Truncate error
            }

    print_json(
        {
            'ok': True,
            'run_id': args.run_id,
            'options': options,
            'comparisons': comparisons,
            'test_results': test_results if test_results else None,
        }
    )
    return 0


def experiment_select(args: argparse.Namespace) -> int:
    """Select and merge the best experimental branch, deleting others.

    Args:
        args: CLI arguments with `root`, `run_id`, `options`, and `select` attributes.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    root = Path(args.root).resolve()

    if not is_git_repository(root):
        print_json(
            {
                'ok': False,
                'error': 'Not a git repository',
            }
        )
        return 1

    # Parse options
    options = args.options.split(',') if args.options else []
    selected = args.select

    if not options:
        print_json(
            {
                'ok': False,
                'error': 'No options specified. Use --options opt1,opt2,...',
            }
        )
        return 1

    if selected not in options:
        print_json(
            {
                'ok': False,
                'error': f'Selected option "{selected}" not in options: {options}',
            }
        )
        return 1

    # Create parallel experiment stack
    stack = ParallelExperimentStack(root, args.run_id, options)

    # Get the selected sandbox
    selected_sandbox = stack.get_sandbox(selected)
    if not selected_sandbox:
        print_json(
            {
                'ok': False,
                'error': f'Sandbox for option "{selected}" not found',
            }
        )
        return 1

    # Merge selected branch with self-healing if configured
    enable_self_healing = not getattr(args, 'no_self_healing', False)
    conflict_provider = getattr(args, 'conflict_provider', None)
    conflict_model = getattr(args, 'conflict_model', None)

    merge_result = selected_sandbox.merge(
        squash=args.squash,
        enable_self_healing=enable_self_healing,
        conflict_provider=conflict_provider,
        conflict_model=conflict_model,
    )

    if not merge_result.success:
        print_json(
            {
                'ok': False,
                'error': merge_result.error,
                'has_conflicts': merge_result.has_conflicts,
                'conflicted_files': merge_result.conflicted_files,
            }
        )
        return 1

    # Cleanup other branches
    cleanup_results = stack.cleanup_all(keep_best=selected)

    print_json(
        {
            'ok': True,
            'selected': selected,
            'merge_result': {
                'success': merge_result.success,
                'branch_name': merge_result.branch_name,
            },
            'cleanup_results': cleanup_results,
        }
    )
    return 0


def experiment_cancel(args: argparse.Namespace) -> int:
    """Cancel and delete all experimental branches without merging.

    Args:
        args: CLI arguments with `root`, `run_id`, and `options` attributes.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    root = Path(args.root).resolve()

    if not is_git_repository(root):
        print_json(
            {
                'ok': False,
                'error': 'Not a git repository',
                'deleted': [],
            }
        )
        return 1

    # Parse options
    options = args.options.split(',') if args.options else []

    if not options:
        # If no options specified, delete all orphaned branches
        orphaned = find_orphaned_sandbox_branches(root)
        deleted = []
        for branch_info in orphaned:
            if prune_sandbox_branch(root, branch_info['branch_name']):
                deleted.append(branch_info['branch_name'])

        print_json(
            {
                'ok': True,
                'deleted': deleted,
                'orphaned_only': True,
            }
        )
        return 0

    # Delete specific experimental branches
    stack = ParallelExperimentStack(root, args.run_id, options)
    cleanup_results = stack.cleanup_all()

    deleted = [opt for opt, success in cleanup_results.items() if success]

    print_json(
        {
            'ok': True,
            'deleted': deleted,
            'cleanup_results': cleanup_results,
        }
    )
    return 0

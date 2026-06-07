from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Optional

from teaagent.cli._output import print_json
from teaagent.run_store import RunStore

from .run import _execute_agent_task, _resolve_auto_compact


def agent_resume_command(args: argparse.Namespace) -> int:
    store = RunStore(args.root)
    try:
        original_task = store.task_for_run(args.run_id)
    except (FileNotFoundError, ValueError) as exc:
        print_json({'status': 'error', 'message': str(exc)})
        return 1

    initial_observations: list[dict[str, Any]] = []
    initial_context_extra: Optional[dict[str, Any]] = None
    auto_approved: Optional[str] = None

    # Load scoped approvals for this specific run only
    from teaagent.ergonomics.approval_store import ApprovalPresetStore

    approval_store = ApprovalPresetStore(args.root)

    if not args.fresh_restart:
        checkpoint_path = getattr(args, 'checkpoint_store', None)
        checkpoint = None
        if checkpoint_path:
            from teaagent.checkpoint import SQLiteCheckpointStore

            checkpoint = SQLiteCheckpointStore(checkpoint_path).load(args.run_id)
        if checkpoint is not None:
            initial_observations = checkpoint.get('observations', [])
            initial_context_extra = {
                k: v for k, v in checkpoint.items() if k not in ('task', 'observations')
            }
        else:
            initial_observations = store.observations_for_run(args.run_id)
            if _resolve_auto_compact(args) and len(initial_observations) > 40:
                initial_observations = initial_observations[-20:]
                initial_context_extra = {
                    'resume_compaction': {
                        'truncated': True,
                        'kept_observations': 20,
                    }
                }
        pending = store.pending_approval_for_run(args.run_id)
        if pending and pending['call_id'] not in args.approve_call_id:
            digest = pending.get('argument_digest')
            if not digest:
                import sys

                print(
                    f"Warning: Pending call '{pending['call_id']}' is a legacy record and "
                    f'cannot be auto-approved safely due to redacted arguments. '
                    f'Please approve explicitly with --approve-call-id {pending["call_id"]}.',
                    file=sys.stderr,
                )
            else:
                # Check if this pending call already has a valid scoped approval to avoid duplicate storage writes
                if not approval_store.check_scoped_approval_digest(
                    run_id=args.run_id,
                    call_id=pending['call_id'],
                    tool_name=pending['tool_name'],
                    argument_digest=digest,
                ):
                    approval_store.add_scoped_approval(
                        run_id=args.run_id,
                        call_id=pending['call_id'],
                        tool_name=pending['tool_name'],
                        arguments=pending['arguments'],
                        argument_digest=digest,
                    )
                auto_approved = pending['call_id']

    # Legacy Escape Hatch: keep only explicitly provided bare call IDs from the --approve-call-id CLI flag
    # for backward compatibility. We never merge database-persisted scoped approvals here as bare IDs.
    args.approve_call_id = frozenset(args.approve_call_id)

    return _execute_agent_task(
        args,
        original_task,
        resumed_from=args.run_id,
        initial_observations=initial_observations,
        initial_context_extra=initial_context_extra,
        auto_approved_call_id=auto_approved,
    )


def _load_suspension_data(root_path: Path, run_id: str) -> dict[str, Any] | None:
    """Load and validate suspension data for a given run_id.

    Args:
        root_path: The workspace root directory
        run_id: The background task run_id to review

    Returns:
        Suspension data dict, or None if loading fails
    """
    tea_dir = root_path / '.teaagent'
    suspension_file = tea_dir / f'suspension-{run_id}.json'

    if not suspension_file.exists():
        print(f'[TeaAgent] Error: No suspension data found for run_id {run_id}')
        print(f'[TeaAgent] Expected file: {suspension_file}')
        return None

    try:
        with open(suspension_file) as f:
            suspension_data = json.load(f)
    except json.JSONDecodeError as exc:
        print(f'[TeaAgent] Error: Corrupted suspension data: {exc}')
        return None
    except Exception as exc:
        print(f'[TeaAgent] Error loading suspension data: {exc}')
        return None

    # Verify ACP compliance
    if 'acp_version' not in suspension_data:
        print('[TeaAgent] Warning: Suspension data missing ACP version field')

    return suspension_data


def _display_review_header(run_id: str, suspension_data: dict[str, Any]) -> None:
    """Display the review mode header with run information.

    Args:
        run_id: The background task run_id
        suspension_data: The loaded suspension data
    """
    print('\n=== Interactive Review Mode ===')
    print(f'Reviewing results from run: {run_id}')
    print(f'Original mode: {suspension_data.get("mode", "unknown")}')
    print(
        f'Suspended at: {__import__("time").ctime(suspension_data.get("timestamp", 0))}'
    )
    print()


def _get_changed_files(root_path: Path) -> list[str] | None:
    """Get list of changed files from git.

    Args:
        root_path: The workspace root directory

    Returns:
        List of changed file paths, or None if git fails
    """
    try:
        result = subprocess.run(
            ['git', 'diff', '--name-only'],
            cwd=root_path,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0 or not result.stdout.strip():
            print('[TeaAgent] No changes detected to review.')
            return None

        return result.stdout.strip().split('\n')
    except FileNotFoundError:
        print('[TeaAgent] Git not found in PATH')
        return None
    except Exception as exc:
        print(f'[TeaAgent] Error getting changed files: {exc}')
        return None


def _display_file_list(changed_files: list[str]) -> None:
    """Display the list of changed files and review commands.

    Args:
        changed_files: List of changed file paths
    """
    print(f'Found {len(changed_files)} changed file(s) to review:')
    for i, file in enumerate(changed_files, 1):
        print(f'  {i}. {file}')

    print()
    print('Review commands:')
    print('  y - Accept file changes')
    print('  e - Edit file in external editor')
    print('  r - Reject and request AI reconsideration')
    print('  n - Next file (skip)')
    print('  q - Quit review')
    print()


def _show_file_diff(root_path: Path, file_path: str) -> None:
    """Display git diff for a specific file.

    Args:
        root_path: The workspace root directory
        file_path: Path to the file to show diff for
    """
    diff_result = subprocess.run(
        ['git', 'diff', '--color=always', file_path],
        cwd=root_path,
        capture_output=True,
        text=True,
    )

    if diff_result.stdout:
        # Show limited diff (first 20 lines)
        diff_lines = diff_result.stdout.split('\n')
        print('\n'.join(diff_lines[:20]))
        if len(diff_lines) > 20:
            print(f'... ({len(diff_lines) - 20} more lines)')


def _handle_review_choice(
    choice: str,
    file_path: str,
    root_path: Path,
    review_decisions: dict[str, str],
) -> bool:
    """Handle user's review choice for a file.

    Args:
        choice: User's choice (y/e/r/n/q)
        file_path: Path to the file being reviewed
        root_path: The workspace root directory
        review_decisions: Dict to store review decisions

    Returns:
        True if review should continue, False if user quit
    """
    if choice == 'y':
        review_decisions[file_path] = 'accepted'
        print(f'✓ Accepted {file_path}')
        return True
    elif choice == 'e':
        # Open in external editor
        editor = os.environ.get('EDITOR', 'vim')
        subprocess.run([editor, str(root_path / file_path)], cwd=root_path)
        review_decisions[file_path] = 'edited'
        print(f'✓ Edited {file_path}')
        return True
    elif choice == 'r':
        review_decisions[file_path] = 'rejected'
        print(f'✗ Rejected {file_path} (marked for AI reconsideration)')
        # Apply rejection by reverting the file
        subprocess.run(
            ['git', 'checkout', '--', file_path],
            cwd=root_path,
            capture_output=True,
        )
        print(f'  Reverted changes to {file_path}')
        return True
    elif choice == 'n':
        print(f'→ Skipped {file_path}')
        return True
    elif choice == 'q':
        print('Review quit by user.')
        return False
    else:
        print('Invalid choice. Please try again.')
        return True


def _display_review_summary(
    review_decisions: dict[str, str], changed_files: list[str]
) -> None:
    """Display summary of review decisions.

    Args:
        review_decisions: Dict of file path to decision
        changed_files: List of all changed files
    """
    print('\n=== Review Summary ===')
    accepted = sum(1 for d in review_decisions.values() if d == 'accepted')
    edited = sum(1 for d in review_decisions.values() if d == 'edited')
    rejected = sum(1 for d in review_decisions.values() if d == 'rejected')

    print(f'Accepted: {accepted}')
    print(f'Edited: {edited}')
    print(f'Rejected: {rejected}')
    print(f'Skipped: {len(changed_files) - len(review_decisions)}')


def _save_review_decisions(
    tea_dir: Path,
    run_id: str,
    review_decisions: dict[str, str],
    suspension_data: dict[str, Any],
    changed_files: list[str],
) -> None:
    """Save review decisions to file with ACP compliance.

    Args:
        tea_dir: The .teaagent directory
        run_id: The background task run_id
        review_decisions: Dict of file path to decision
        suspension_data: The loaded suspension data
        changed_files: List of all changed files
    """
    review_file = tea_dir / f'review-{run_id}.json'

    try:
        with open(review_file, 'w') as f:
            json.dump(
                {
                    'run_id': run_id,
                    'timestamp': time.time(),
                    'acp_version': '1.0.0',  # ACP protocol version
                    'mode': 'interactive_review',  # Track current mode
                    'decisions': review_decisions,
                    # audit_trail was a pre-CG-10 placeholder; real governance record is in RunStore
                },
                f,
                indent=2,
            )
        print(f'\nReview decisions saved to {review_file}')
    except Exception as exc:
        print(f'Warning: Could not save review decisions: {exc}')


def interactive_review_mode(root: str | Path, run_id: str) -> int:
    """Launch interactive review mode for background task results.

    Args:
        root: The workspace root directory
        run_id: The background task run_id to review

    Returns:
        Exit code (0 for success, non-zero for errors)
    """
    from pathlib import Path

    root_path = Path(root).resolve()

    # Load and validate suspension data
    suspension_data = _load_suspension_data(root_path, run_id)
    if suspension_data is None:
        return 1

    # Display review header
    _display_review_header(run_id, suspension_data)

    # Get changed files from git
    changed_files = _get_changed_files(root_path)
    if changed_files is None:
        return 1

    # Display file list and commands
    _display_file_list(changed_files)

    # Interactive review loop
    current_index = 0
    review_decisions: dict[str, str] = {}

    while current_index < len(changed_files):
        file_path = changed_files[current_index]
        print(
            f'\n--- Reviewing file {current_index + 1}/{len(changed_files)}: {file_path} ---'
        )

        # Show diff for this file
        _show_file_diff(root_path, file_path)

        print(f'\nAction for {file_path} [y/e/r/n/q]: ', end='')
        choice = input().strip().lower()

        should_continue = _handle_review_choice(
            choice, file_path, root_path, review_decisions
        )
        if not should_continue:
            return 0  # Early exit on quit
        elif choice in ('y', 'e', 'r', 'n'):
            current_index += 1

    # Display summary
    _display_review_summary(review_decisions, changed_files)

    # Save review decisions
    tea_dir = root_path / '.teaagent'
    _save_review_decisions(
        tea_dir, run_id, review_decisions, suspension_data, changed_files
    )

    return 0


def interactive_review_command(args: argparse.Namespace) -> int:
    """CLI command for interactive review mode."""
    return interactive_review_mode(args.root, args.run_id)

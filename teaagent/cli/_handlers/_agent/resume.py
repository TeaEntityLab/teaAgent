from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

from teaagent.cli._output import print_json

from .config import _resolve_auto_compact, warn_if_approve_call_id_used
from .run import _execute_agent_task

if TYPE_CHECKING:
    from teaagent.chat_agent import ChatAgentConfig


def suspend_to_background(
    config: ChatAgentConfig, session_context: dict, targeted_files: set[Path]
) -> str:
    """Suspend a chat session and write a resumable checkpoint.

    Writes ``.teaagent/suspension-<run_id>.json`` (the format consumed by
    :func:`_load_suspension_data` / ``agent interactive-review``) plus a
    ``run_started`` audit event so the suspended run is discoverable.

    Relocated here from the retired ``cli._handlers.chat_repl`` module
    (U-P2-1) so this checkpoint producer lives beside its readers. NOTE:
    no production surface currently *calls* this — the TUI does not yet wire
    suspend-to-checkpoint (see action register follow-up). Kept to preserve
    the capability and its read-path contract.

    Returns:
        run_id of the created checkpoint, or empty string on failure.
    """
    from teaagent.cli.execution import AgentExecutionFactory

    root = config.root.resolve()

    print('[TeaAgent] Suspending session as a checkpoint...')

    run_id = str(uuid.uuid4())[:8]

    tea_dir = root / '.teaagent'
    tea_dir.mkdir(parents=True, exist_ok=True)

    # Save session state with ACP compliance
    suspension_data = {
        'run_id': run_id,
        'timestamp': time.time(),
        'acp_version': '1.0.0',  # ACP protocol version for state compatibility
        'mode': 'suspended_from_repl',  # Track origin mode
        'config': {
            'model': config.model,
            'permission_mode': config.permission_mode.value
            if config.permission_mode
            else None,
            'max_iterations': config.max_iterations,
            'max_tool_calls': config.max_tool_calls,
            'max_estimated_cost_cents': config.max_estimated_cost_cents,
        },
        'session_context': {
            'observations_count': len(session_context.get('observations', [])),
            'compaction_count': session_context.get('compaction_count', 0),
            'observations': session_context.get('observations', [])[-10:]
            if session_context.get('observations')
            else [],  # Keep last 10 for context
        },
        'targeted_files': [
            str(f.resolve().relative_to(root.resolve()))
            for f in targeted_files
            if f.resolve().is_relative_to(root.resolve())
        ],
    }

    suspension_file = tea_dir / f'suspension-{run_id}.json'
    try:
        suspension_file.write_text(
            json.dumps(suspension_data, indent=2), encoding='utf-8'
        )
    except Exception as exc:
        print(f'[TeaAgent] Error saving suspension state: {exc}')
        return ''

    # Check if workspace is dirty and warn user
    branch_created = False
    try:
        result = subprocess.run(
            ['git', 'status', '--porcelain'],
            cwd=root,
            capture_output=True,
            text=True,
        )

        if result.stdout.strip():
            print('[TeaAgent] Warning: Workspace has uncommitted changes.')
            print('[TeaAgent] Session is suspended on current branch.')
            print('[TeaAgent] Uncommitted changes remain in working directory.')
            branch_created = False
    except FileNotFoundError:
        print('[TeaAgent] Git not found, skipping workspace check')
    except Exception as exc:
        print(f'[TeaAgent] Warning: Could not check workspace status: {exc}')

    # Emit audit event for suspension
    factory = AgentExecutionFactory(root)
    try:
        store = factory.create_run_store()
        audit = store.audit_logger()
        audit.record(
            event_type='session_suspended',
            run_id=run_id,
            mode='suspended_from_repl',
            observations_count=len(session_context.get('observations', [])),
            targeted_files_count=len(targeted_files),
            branch_created=branch_created,
        )
    except Exception as exc:
        print(f'[TeaAgent] Warning: Could not emit suspension audit event: {exc}')

    # Write a run_started event so agent_resume_command can find this run
    try:
        resume_store = factory.create_run_store()
        resume_audit = resume_store.audit_logger(run_id=run_id)
        observations = session_context.get('observations', [])
        last_task = '(resumed from REPL suspension)'
        if observations:
            last_obs = observations[-1]
            if isinstance(last_obs, dict) and 'task' in last_obs:
                last_task = last_obs['task']
        resume_audit.record(
            event_type='run_started',
            run_id=run_id,
            task=last_task,
            suspended_from='repl',
        )
    except Exception as exc:
        print(f'[TeaAgent] Warning: Could not write resume event: {exc}')

    print('[TeaAgent] Session suspended successfully!')
    print(f'[TeaAgent] Run ID: {run_id}')
    print(f'[TeaAgent] To review: teaagent agent interactive-review {run_id}')
    print('[TeaAgent] Note: This is a suspension checkpoint, not background execution.')

    return run_id


def agent_resume_command(args: argparse.Namespace) -> int:
    from teaagent.integration.resume_preparation import (
        ResumePreparationError,
        prepare_run_resume,
    )

    warn_if_approve_call_id_used(args)
    try:
        prepared = prepare_run_resume(
            args.root,
            args.run_id,
            # Call-id preapproval was removed (G-P2-2); flag is inert.
            approve_call_ids=frozenset(),
            fresh_restart=args.fresh_restart,
            auto_compact=_resolve_auto_compact(args),
            checkpoint_path=getattr(args, 'checkpoint_store', None),
        )
    except ResumePreparationError as exc:
        print_json({'status': 'error', 'message': str(exc)})
        return 1

    if prepared.pending_warning:
        import sys

        print(f'Warning: {prepared.pending_warning}', file=sys.stderr)

    args.approve_call_id = frozenset(args.approve_call_id)

    return _execute_agent_task(
        args,
        prepared.original_task,
        resumed_from=prepared.run_id,
        initial_observations=prepared.initial_observations,
        initial_context_extra=prepared.initial_context_extra,
        auto_approved_call_id=prepared.auto_approved_call_id,
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

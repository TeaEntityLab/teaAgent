"""Agent review and subagent review commands."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path

from teaagent.cli._output import print_json


def interactive_review_mode(root: str, run_id: str) -> int:
    """Interactive review mode for suspended sessions.

    Args:
        root: Workspace root directory
        run_id: Run ID to review

    Returns:
        Exit code
    """
    root_path = Path(root).resolve()
    tea_dir = root_path / '.teaagent'
    suspension_file = tea_dir / f'suspension-{run_id}.json'

    if not suspension_file.exists():
        print(f'[TeaAgent] Error: Suspension file not found for run {run_id}')
        return 1

    try:
        with open(suspension_file, 'r') as f:
            suspension_data = json.load(f)
    except Exception as exc:
        print(f'[TeaAgent] Error loading suspension data: {exc}')
        return 1

    print('[TeaAgent] Interactive Review Mode')
    print(f'[TeaAgent] Run ID: {run_id}')
    print(f'[TeaAgent] Mode: {suspension_data.get("mode", "unknown")}')
    print(f'Suspended at: {time.ctime(suspension_data.get("timestamp", 0))}')
    print()

    # Get changed files from the run
    try:
        # First, check if we can get changes from git
        result = subprocess.run(
            ['git', 'diff', '--name-only'],
            cwd=root_path,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0 or not result.stdout.strip():
            print('[TeaAgent] No changes detected to review.')
            return 0

        changed_files = result.stdout.strip().split('\n')
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

        # Interactive review loop
        current_index = 0
        review_decisions = {}

        while current_index < len(changed_files):
            file_path = changed_files[current_index]
            print(
                f'\n--- Reviewing file {current_index + 1}/{len(changed_files)}: {file_path} ---'
            )

            # Show diff for this file
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

            print(f'\nAction for {file_path} [y/e/r/n/q]: ', end='')
            choice = input().strip().lower()

            if choice == 'y':
                review_decisions[file_path] = 'accepted'
                print(f'✓ Accepted {file_path}')
                current_index += 1
            elif choice == 'e':
                # Open in external editor
                editor = os.environ.get('EDITOR', 'vim')
                subprocess.run([editor, str(root_path / file_path)], cwd=root_path)
                review_decisions[file_path] = 'edited'
                print(f'✓ Edited {file_path}')
                current_index += 1
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
                current_index += 1
            elif choice == 'n':
                print(f'→ Skipped {file_path}')
                current_index += 1
            elif choice == 'q':
                print('Review quit by user.')
                return 0  # Early exit on quit
            else:
                print('Invalid choice. Please try again.')

        # Summary
        print('\n=== Review Summary ===')
        accepted = sum(1 for d in review_decisions.values() if d == 'accepted')
        edited = sum(1 for d in review_decisions.values() if d == 'edited')
        rejected = sum(1 for d in review_decisions.values() if d == 'rejected')

        print(f'Accepted: {accepted}')
        print(f'Edited: {edited}')
        print(f'Rejected: {rejected}')
        print(f'Skipped: {len(changed_files) - len(review_decisions)}')

        # Save review decisions with ACP compliance
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
                        'audit_trail': {
                            'review_time': time.time(),
                            'original_mode': suspension_data.get('mode', 'unknown'),
                            'transition_type': 'robot_to_keyboard',
                            'files_reviewed': len(changed_files),
                            'suspension_data': suspension_data.get('audit_trail', {}),
                        },
                    },
                    f,
                    indent=2,
                )
            print(f'\nReview decisions saved to {review_file}')
        except Exception as exc:
            print(f'Warning: Could not save review decisions: {exc}')

        return 0

    except FileNotFoundError:
        print('[TeaAgent] Git not found in PATH')
        return 1
    except Exception as exc:
        print(f'[TeaAgent] Error during review: {exc}')
        return 1


def interactive_review_command(args: argparse.Namespace) -> int:
    """CLI command for interactive review mode."""
    return interactive_review_mode(args.root, args.run_id)


def agent_subagent_review_list_command(args: argparse.Namespace) -> int:
    from teaagent.subagents._review import list_subagent_reviews

    print_json(
        {
            'status': 'ok',
            'reviews': list_subagent_reviews(
                args.root, parent_run_id=getattr(args, 'parent_run_id', None)
            ),
        }
    )
    return 0


def agent_subagent_review_show_command(args: argparse.Namespace) -> int:
    from teaagent.subagents._review import load_subagent_review

    try:
        review = load_subagent_review(
            args.root,
            args.review_id,
            parent_run_id=getattr(args, 'parent_run_id', None),
        )
    except FileNotFoundError as exc:
        print_json({'status': 'error', 'message': str(exc)})
        return 1
    print_json({'status': 'ok', 'review': review})
    return 0


def agent_subagent_review_check_command(args: argparse.Namespace) -> int:
    from teaagent.subagents._review import check_subagent_review

    try:
        payload = check_subagent_review(
            args.root,
            args.review_id,
            parent_run_id=getattr(args, 'parent_run_id', None),
        )
    except FileNotFoundError as exc:
        print_json({'status': 'error', 'message': str(exc)})
        return 1
    print_json(payload)
    return 0 if payload['ok'] else 2


def agent_subagent_review_apply_command(args: argparse.Namespace) -> int:
    from teaagent.subagents._review import apply_subagent_review

    try:
        payload = apply_subagent_review(
            args.root,
            args.review_id,
            parent_run_id=getattr(args, 'parent_run_id', None),
        )
    except FileNotFoundError as exc:
        print_json({'status': 'error', 'message': str(exc)})
        return 1
    print_json(payload)
    return 0 if payload['ok'] else 2

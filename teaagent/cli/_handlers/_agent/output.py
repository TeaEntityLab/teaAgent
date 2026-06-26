from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Any

from teaagent.cli._output import print_json
from teaagent.cli.execution import AgentExecutionFactory
from teaagent.ergonomics.cli_output import wants_human_cli
from teaagent.run_store import RunStore
from teaagent.runner import RunResult

# Constants for pagination and display limits
DEFAULT_DIFF_PREVIEW_LINES = 30
DEFAULT_PAGINATION_LINES = 50


def _display_recovery_guidance(
    result: RunResult,
    args: argparse.Namespace,
    store: RunStore,
) -> None:
    """Display recovery guidance for failed or partial success runs.

    Args:
        result: RunResult from the failed run
        args: CLI arguments
        store: RunStore for accessing audit logs
    """
    from teaagent.guided_recovery import (
        FailureAnalyzer,
        RecoveryAdviceFormatter,
        RecoverySelector,
    )

    # Load audit log if available
    audit_path = store.run_path(result.run_id)
    audit = (
        AgentExecutionFactory.create_audit_logger_from_path(audit_path)
        if audit_path.is_file()
        else None
    )

    # Load undo journal if available
    undo_journal = None
    undo_path = store.undo_path(result.run_id)
    if undo_path.is_file():
        factory = AgentExecutionFactory(args.root)
        undo_journal = factory.create_undo_journal(path=undo_path)

    # Analyze failure
    analyzer = FailureAnalyzer(audit_logger=audit)
    failure = analyzer.classify(result)

    # Select recovery strategy
    selector = RecoverySelector(undo_journal=undo_journal)
    advice = selector.select(failure)

    # Format and display advice
    formatter = RecoveryAdviceFormatter()
    formatted_advice = formatter.format(advice, run_id=result.run_id)

    print('\n' + formatted_advice, file=sys.stderr)


def _emit_readiness_payload(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    if wants_human_cli(args):
        from teaagent.ergonomics.human_output import format_readiness_summary

        print(format_readiness_summary(payload, root=args.root))
        return
    print_json(payload)


def _emit_run_completion_output(
    args: argparse.Namespace,
    *,
    store: RunStore,
    run_id: str,
    payload: dict[str, Any],
) -> None:
    """Print human receipt or JSON run payload (F3: plain language first on TTY)."""
    if getattr(args, 'json_stream', False):
        from teaagent.streaming.events import StreamEvent, emit_stream_event

        emit_stream_event(StreamEvent('run_result', payload))
        return

    from teaagent.run_receipt import build_run_receipt

    if wants_human_cli(args):
        print(build_run_receipt(store, run_id, args.root))
        return

    print_json(payload)
    if sys.stderr.isatty():
        print(build_run_receipt(store, run_id, args.root), file=sys.stderr)


def show_interactive_diff(root: str | Path, sandbox_branch: str) -> bool:
    """Show interactive diff before merge prompt.

    Args:
        root: The workspace root directory
        sandbox_branch: The sandbox branch name

    Returns:
        True if user wants to proceed, False to cancel
    """
    from pathlib import Path

    root_path = Path(root).resolve()

    print('\n=== Sandbox Merge Preview ===')
    print(f'Branch: {sandbox_branch}')
    print()

    # Get diff summary
    try:
        # Get list of changed files
        result = subprocess.run(
            ['git', 'diff', '--stat', f'{sandbox_branch}'],
            cwd=root_path,
            capture_output=True,
            text=True,
        )

        if result.returncode == 0 and result.stdout.strip():
            print('Changed files:')
            print(result.stdout)
        else:
            print('No changes detected in sandbox branch.')
            return True

        # Ask if user wants to see detailed diff
        print('\nView detailed diff? [Y/n]: ', end='')
        choice = input().strip().lower()

        if choice in ('n', 'no'):
            return True

        # Show detailed diff with color
        print('\n=== Detailed Changes ===')
        result = subprocess.run(
            ['git', 'diff', '--color=always', f'{sandbox_branch}'],
            cwd=root_path,
            capture_output=True,
            text=True,
        )

        if result.stdout:
            # Paginate output if it's long
            lines = result.stdout.split('\n')
            if len(lines) > DEFAULT_PAGINATION_LINES:
                # Show first N lines
                print('\n'.join(lines[:DEFAULT_DIFF_PREVIEW_LINES]))
                print(f'\n... ({len(lines) - DEFAULT_DIFF_PREVIEW_LINES} more lines)')
                print('Press Enter to see more, or q to quit: ', end='')
                more = input().strip().lower()
                if more != 'q':
                    print('\n'.join(lines[30:]))
            else:
                print(result.stdout)
        else:
            print('No detailed changes available.')

        print('\n=== End of Diff ===')

    except FileNotFoundError:
        print('[TeaAgent] Git not found in PATH')
        return True
    except Exception as exc:
        print(f'[TeaAgent] Error getting diff: {exc}')
        return True

    return True

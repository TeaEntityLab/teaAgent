"""CLI handlers for time-travel replay (TASK-012)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from teaagent.audit import AuditLogger
from teaagent.run_store import RunStore


def print_json(data: dict) -> None:
    """Print JSON output."""
    print(json.dumps(data, indent=2))


def replay_list(args: argparse.Namespace) -> int:
    """List available runs for time-travel replay.

    Args:
        args: CLI arguments with `root` and `limit` attributes.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    root = Path(args.root).resolve()
    limit = args.limit

    run_store = RunStore(root, readonly=True)

    try:
        summaries = run_store.list_runs(limit=limit)
    except Exception as exc:
        print_json({
            'ok': False,
            'error': f'Failed to list runs: {exc}',
        })
        return 1

    print_json({
        'ok': True,
        'count': len(summaries),
        'runs': [s.to_dict() for s in summaries],
    })
    return 0


def replay_steps(args: argparse.Namespace) -> int:
    """List steps in a run for replay inspection.

    Args:
        args: CLI arguments with `root` and `run_id` attributes.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    root = Path(args.root).resolve()
    run_id = args.run_id

    run_store = RunStore(root, readonly=True)
    run_path = run_store.run_path(run_id)

    if not run_path.exists():
        print_json({
            'ok': False,
            'error': f'Run not found: {run_id}',
        })
        return 1

    try:
        audit = AuditLogger(path=run_path)
        entries = audit.events
    except Exception as exc:
        print_json({
            'ok': False,
            'error': f'Failed to read audit log: {exc}',
        })
        return 1

    steps = []
    for i, entry in enumerate(entries):
        steps.append({
            'step_number': i,
            'event_type': entry.event_type,
            'timestamp': entry.created_at,
            'summary': entry.payload.get('summary', ''),
        })

    print_json({
        'ok': True,
        'run_id': run_id,
        'total_steps': len(steps),
        'steps': steps,
    })
    return 0


def replay_fork(args: argparse.Namespace) -> int:
    """Fork a new branch at a specific step for time-travel replay.

    Args:
        args: CLI arguments with `root`, `run_id`, `step`, and `branch_name` attributes.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    root = Path(args.root).resolve()
    run_id = args.run_id
    step_number = args.step
    branch_name = args.branch_name

    run_store = RunStore(root, readonly=True)
    run_path = run_store.run_path(run_id)

    if not run_path.exists():
        print_json({
            'ok': False,
            'error': f'Run not found: {run_id}',
        })
        return 1

    try:
        audit = AuditLogger(path=run_path)
        entries = audit.events
    except Exception as exc:
        print_json({
            'ok': False,
            'error': f'Failed to read audit log: {exc}',
        })
        return 1

    if step_number < 0 or step_number >= len(entries):
        print_json({
            'ok': False,
            'error': f'Invalid step number: {step_number}. Run has {len(entries)} steps.',
        })
        return 1

    # Get the entry at the fork point
    fork_entry = entries[step_number]

    # Create a replay checkpoint file
    checkpoint_dir = root / '.teaagent' / 'replay'
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    checkpoint_path = checkpoint_dir / f'{branch_name}.json'
    checkpoint_data = {
        'run_id': run_id,
        'fork_step': step_number,
        'branch_name': branch_name,
        'fork_timestamp': fork_entry.created_at,
        'fork_entry': {
            'event_id': fork_entry.event_id,
            'event_type': fork_entry.event_type,
            'run_id': fork_entry.run_id,
            'created_at': fork_entry.created_at,
            'payload': fork_entry.payload,
        },
    }

    try:
        checkpoint_path.write_text(json.dumps(checkpoint_data, indent=2), encoding='utf-8')
    except Exception as exc:
        print_json({
            'ok': False,
            'error': f'Failed to write checkpoint: {exc}',
        })
        return 1

    print_json({
        'ok': True,
        'run_id': run_id,
        'fork_step': step_number,
        'branch_name': branch_name,
        'checkpoint_path': str(checkpoint_path),
        'fork_event_type': fork_entry.event_type,
        'fork_summary': fork_entry.payload.get('summary', ''),
    })
    return 0


def replay_resume(args: argparse.Namespace) -> int:
    """Resume execution from a replay checkpoint.

    Args:
        args: CLI arguments with `root` and `branch_name` attributes.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    root = Path(args.root).resolve()
    branch_name = args.branch_name

    checkpoint_path = root / '.teaagent' / 'replay' / f'{branch_name}.json'

    if not checkpoint_path.exists():
        print_json({
            'ok': False,
            'error': f'Checkpoint not found for branch: {branch_name}',
        })
        return 1

    try:
        checkpoint_data = json.loads(checkpoint_path.read_text(encoding='utf-8'))
    except Exception as exc:
        print_json({
            'ok': False,
            'error': f'Failed to read checkpoint: {exc}',
        })
        return 1

    print_json({
        'ok': True,
        'message': 'Replay checkpoint loaded. Use teaagent run to continue execution.',
        'checkpoint': checkpoint_data,
    })
    return 0

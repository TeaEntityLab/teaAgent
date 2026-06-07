from __future__ import annotations

import argparse
from pathlib import Path

from teaagent.cli._output import print_json
from teaagent.sandbox import ParallelExperimentStack


def _execute_parallel_experiment(
    args: argparse.Namespace, task: str, parallel_options: str
) -> int:
    """Execute parallel experiments using ParallelExperimentStack.

    Args:
        args: CLI arguments.
        task: Task description.
        parallel_options: Comma-separated options (e.g., opt1,opt2,opt3).

    Returns:
        Exit code.
    """
    from uuid import uuid4

    options = [opt.strip() for opt in parallel_options.split(',') if opt.strip()]
    if not options:
        print_json(
            {
                'status': 'error',
                'message': 'No options provided for parallel experiment',
            }
        )
        return 1

    run_id = uuid4().hex
    root = Path(args.root).resolve()

    # Create parallel experiment stack
    stack = ParallelExperimentStack(root, run_id, options)

    # Start all sandboxes
    print_json(
        {
            'status': 'starting_parallel_experiments',
            'run_id': run_id,
            'options': options,
            'message': f'Starting {len(options)} parallel experiment branches',
        }
    )

    start_results = stack.start_all(
        auto_stash=getattr(args, 'git_sandbox_auto_stash', False)
    )

    failed = [opt for opt, success in start_results.items() if not success]
    if failed:
        print_json(
            {
                'status': 'error',
                'message': f'Failed to start {len(failed)} sandbox branches',
                'failed_options': failed,
            }
        )
        return 1

    branches: dict[str, str | None] = {}
    for opt in options:
        sandbox = stack.get_sandbox(opt)
        if sandbox is not None:
            # Access branch_name as a public attribute
            branch_name = getattr(sandbox, '_branch_name', None)
            branches[opt] = str(branch_name) if branch_name is not None else None
        else:
            branches[opt] = None

    print_json(
        {
            'status': 'parallel_experiments_started',
            'run_id': run_id,
            'options': options,
            'branches': branches,
            'message': 'Use "teaagent experiment compare" to compare results, then "teaagent experiment select" to merge the best option',
        }
    )

    return 0

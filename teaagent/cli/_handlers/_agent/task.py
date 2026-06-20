from __future__ import annotations

import argparse
from typing import Any, Optional

from teaagent.ergonomics.workspace_defaults import load_workspace_defaults


def _prepare_task(args: argparse.Namespace, task: str) -> str:
    from teaagent.ergonomics.context_inject import expand_at_references
    from teaagent.ergonomics.daily_cost import check_daily_cost_cap

    expanded, _refs = expand_at_references(task, root=args.root)
    defaults = load_workspace_defaults(args.root)
    cap = int(defaults.get('daily_cost_cap_cents') or 0)
    check_daily_cost_cap(args.root, cap)
    return expanded


def _resolve_run_task(
    args: argparse.Namespace,
) -> tuple[str, Optional[Any]]:
    from teaagent.plan import load_plan_contract

    plan_contract = None
    if getattr(args, 'from_plan', None):
        plan_contract = load_plan_contract(
            args.from_plan,
            root=args.root,
            allow_external_plan=getattr(args, 'allow_external_plan', False),
        )
    if plan_contract is not None:
        raw_task = plan_contract.task
    elif getattr(args, 'task', None):
        raw_task = args.task
    else:
        raise ValueError('task or --from-plan is required')
    return _prepare_task(args, raw_task), plan_contract

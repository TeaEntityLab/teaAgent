"""Goal list and status commands."""

from __future__ import annotations

import argparse

from teaagent.cli._output import print_json
from teaagent.goal_record import GoalStore


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + '...'


def goal_list_command(args: argparse.Namespace) -> int:
    store = GoalStore(args.root)
    goals = store.list()
    result = []
    for g in goals:
        result.append({
            'goal_id': g.goal_id,
            'objective': _truncate(g.objective, 60),
            'status': g.status,
            'cost_cents': g.cost_cents,
            'updated_at': g.updated_at,
        })
    print_json(result)
    return 0


def goal_status_command(args: argparse.Namespace) -> int:
    store = GoalStore(args.root)
    try:
        goal = store.load(args.goal_id)
    except FileNotFoundError as exc:
        print_json({'status': 'error', 'message': str(exc)})
        return 1
    print_json(goal.to_dict())
    return 0

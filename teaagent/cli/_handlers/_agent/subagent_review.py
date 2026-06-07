from __future__ import annotations

import argparse

from teaagent.cli._output import print_json
from teaagent.subagents._review import (
    list_subagent_reviews,
    load_subagent_review,
)


def agent_subagent_review_list_command(args: argparse.Namespace) -> int:
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

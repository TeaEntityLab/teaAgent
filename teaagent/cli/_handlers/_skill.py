from __future__ import annotations

import argparse
from typing import Any

from teaagent.skill_candidates import SkillCandidateStore


def _print_json(value: Any) -> None:
    import json

    print(json.dumps(value, ensure_ascii=False, sort_keys=True))


def skill_candidate_propose_command(args: argparse.Namespace) -> int:
    try:
        row = SkillCandidateStore(args.root).create_from_run(
            run_id=args.from_run,
            name=args.name,
            description=args.description,
        )
    except (FileNotFoundError, ValueError) as exc:
        _print_json({'status': 'error', 'message': str(exc)})
        return 1
    _print_json({'status': 'proposed', 'candidate': row.to_dict()})
    return 0


def skill_candidate_list_command(args: argparse.Namespace) -> int:
    rows = [row.to_dict() for row in SkillCandidateStore(args.root).list()]
    _print_json(rows)
    return 0


def skill_candidate_show_command(args: argparse.Namespace) -> int:
    store = SkillCandidateStore(args.root)
    try:
        row = store.show(args.candidate_id)
    except FileNotFoundError as exc:
        _print_json({'status': 'error', 'message': str(exc)})
        return 1
    _print_json(
        {
            'candidate': row.to_dict(),
            'skill_path': str(store.skill_path(args.candidate_id)),
        }
    )
    return 0


def skill_candidate_review_command(args: argparse.Namespace) -> int:
    store = SkillCandidateStore(args.root)
    try:
        row = store.review(args.candidate_id)
    except FileNotFoundError as exc:
        _print_json({'status': 'error', 'message': str(exc)})
        return 1
    _print_json({'status': row.status, 'candidate': row.to_dict()})
    return 0


def skill_candidate_install_command(args: argparse.Namespace) -> int:
    store = SkillCandidateStore(args.root)
    try:
        payload = store.install(args.candidate_id, scope=args.scope)
    except (FileNotFoundError, ValueError) as exc:
        _print_json({'status': 'error', 'message': str(exc)})
        return 1
    _print_json({'status': 'installed', **payload})
    return 0

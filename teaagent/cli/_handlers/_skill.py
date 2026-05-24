from __future__ import annotations

import argparse
from typing import Any, Literal

from teaagent.skill_candidates import SkillCandidateStore
from teaagent.skill_loader import explain_skill_activation


def _print_json(value: Any) -> None:
    import json

    print(json.dumps(value, ensure_ascii=False, sort_keys=True))


def skill_explain_command(args: argparse.Namespace) -> int:
    prompt_mode: Literal['eager', 'index_only'] = (
        'index_only' if getattr(args, 'skill_index_only', False) else 'eager'
    )
    if getattr(args, 'no_auto_skills', False) or getattr(
        args, 'skill_index_only', False
    ):
        selected: frozenset[str] | None = frozenset()
    else:
        names = [
            str(item).strip()
            for item in (getattr(args, 'skill', None) or [])
            if str(item).strip()
        ]
        selected = frozenset(names) if names else None
    report = explain_skill_activation(
        args.root,
        selected_names=selected,
        skill_prompt_mode=prompt_mode,
    )
    _print_json({'status': 'ok', 'activation': report.to_dict()})
    return 0


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

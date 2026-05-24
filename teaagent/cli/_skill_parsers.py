from __future__ import annotations

import argparse
from typing import Callable


def register(
    subparsers: argparse._SubParsersAction,  # type: ignore[type-arg]
    handlers: dict[str, Callable],
) -> None:
    skill = subparsers.add_parser('skill', help='Manage skill candidates and installs.')
    subs = skill.add_subparsers(dest='skill_command', required=True)

    candidate = subs.add_parser('candidate', help='Skill candidate workflow.')
    candidate_subs = candidate.add_subparsers(
        dest='skill_candidate_command', required=True
    )

    propose = candidate_subs.add_parser(
        'propose', help='Propose a candidate from a run.'
    )
    propose.add_argument('--root', default='.', help='Workspace root.')
    propose.add_argument('--from-run', required=True, dest='from_run')
    propose.add_argument('--name', required=True)
    propose.add_argument('--description', required=True)
    propose.set_defaults(func=handlers['candidate_propose'])

    lst = candidate_subs.add_parser('list', help='List skill candidates.')
    lst.add_argument('--root', default='.', help='Workspace root.')
    lst.set_defaults(func=handlers['candidate_list'])

    show = candidate_subs.add_parser('show', help='Show one skill candidate.')
    show.add_argument('candidate_id')
    show.add_argument('--root', default='.', help='Workspace root.')
    show.set_defaults(func=handlers['candidate_show'])

    review = candidate_subs.add_parser('review', help='Review one candidate.')
    review.add_argument('candidate_id')
    review.add_argument('--root', default='.', help='Workspace root.')
    review.set_defaults(func=handlers['candidate_review'])

    install = candidate_subs.add_parser(
        'install', help='Install reviewed candidate into skill directories.'
    )
    install.add_argument('candidate_id')
    install.add_argument('--root', default='.', help='Workspace root.')
    install.add_argument('--scope', choices=['project', 'personal'], default='project')
    install.set_defaults(func=handlers['candidate_install'])

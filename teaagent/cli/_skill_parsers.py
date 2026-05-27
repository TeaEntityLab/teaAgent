from __future__ import annotations

import argparse
from typing import Callable


def register(
    subparsers: argparse._SubParsersAction,  # type: ignore[type-arg]
    handlers: dict[str, Callable],
) -> None:
    skill = subparsers.add_parser('skill', help='Manage skill candidates and installs.')
    subs = skill.add_subparsers(dest='skill_command', required=True)

    explain = subs.add_parser(
        'explain',
        help='Show which skills load, shadow duplicates, and token contribution.',
    )
    explain.add_argument('--root', default='.', help='Workspace root.')
    explain.add_argument(
        '--skill',
        action='append',
        default=[],
        metavar='NAME',
        help='Explicit skill names (same as agent run --skill).',
    )
    explain.add_argument(
        '--no-auto-skills',
        action='store_true',
        help='Match automation default: load no skills.',
    )
    explain.add_argument(
        '--skill-index-only',
        action='store_true',
        help='Match agent run --skill-index-only (metadata only, zero skill tokens).',
    )
    explain.set_defaults(func=handlers['explain'])

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

    eval_cmd = candidate_subs.add_parser(
        'eval', help='Run offline eval checks on a skill candidate.'
    )
    eval_cmd.add_argument('candidate_id')
    eval_cmd.add_argument('--root', default='.', help='Workspace root.')
    eval_cmd.set_defaults(func=handlers['candidate_eval'])

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
    install.add_argument(
        '--i-attest-personal-install',
        action='store_true',
        help='Required when installing a reviewed candidate into personal skills.',
    )
    install.set_defaults(func=handlers['candidate_install'])

    publish = subs.add_parser(
        'publish', help='Publish a skill to the local marketplace registry.'
    )
    publish.add_argument('name', help='Skill name.')
    publish.add_argument('--description', default='', help='Skill description.')
    publish.add_argument('--version', default='0.1.0', help='Skill version.')
    publish.add_argument('--author', default='', help='Author name.')
    publish.add_argument('--skill-path', default='', help='Path to SKILL.md.')
    publish.add_argument(
        '--tags', action='append', default=[], help='Tags. Repeatable.'
    )
    publish.add_argument('--json', action='store_true', help='Output as JSON.')
    publish.add_argument('--root', default='.', help='Workspace root.')
    publish.set_defaults(func=handlers['publish'])

    search = subs.add_parser(
        'search', help='Search the local marketplace registry for skills.'
    )
    search.add_argument('query', nargs='?', default='', help='Search query.')
    search.add_argument('--tag', default=None, help='Filter by tag.')
    search.add_argument('--limit', type=int, default=20, help='Max results.')
    search.add_argument('--json', action='store_true', help='Output as JSON.')
    search.add_argument('--root', default='.', help='Workspace root.')
    search.set_defaults(func=handlers['search'])

    mkt_list = subs.add_parser(
        'marketplace-list', help='List all published skills in local marketplace.'
    )
    mkt_list.add_argument('--limit', type=int, default=50, help='Max results.')
    mkt_list.add_argument('--json', action='store_true', help='Output as JSON.')
    mkt_list.add_argument('--root', default='.', help='Workspace root.')
    mkt_list.set_defaults(func=handlers['marketplace-list'])

    install_mkt = subs.add_parser(
        'install-from-marketplace',
        help='Install a skill from the remote agentskills.io marketplace.',
    )
    install_mkt.add_argument('name', help='Skill name to search and install.')
    install_mkt.add_argument('--root', default='.', help='Workspace root.')
    install_mkt.set_defaults(func=handlers['install-from-marketplace'])

    publish_tsb = subs.add_parser(
        'publish-tsb',
        help='Publish a skill as a cryptographically attested TSB bundle.',
    )
    publish_tsb.add_argument('skill_path', help='Path to skill directory.')
    publish_tsb.add_argument('audit_log', help='Path to audit log file.')
    publish_tsb.add_argument('--output', help='Output TSB file path.')
    publish_tsb.add_argument('--name', help='Skill name (defaults to directory name).')
    publish_tsb.add_argument('--version', default='1.0.0', help='Skill version.')
    publish_tsb.add_argument('--author', help='Author name.')
    publish_tsb.add_argument('--key', help='Path to SSH/GPG key for signing.')
    publish_tsb.add_argument('--sigstore', action='store_true', help='Use Sigstore keyless signing instead of SSH key.')
    publish_tsb.add_argument('--identity-token', help='OIDC identity token for Sigstore signing.')
    publish_tsb.add_argument('--environment-type', default='uv', help='Environment type (uv, nix, docker).')
    publish_tsb.set_defaults(func=handlers.get('publish_tsb'))

    verify_tsb = subs.add_parser(
        'verify-tsb',
        help='Verify a TSB bundle integrity and attestation.',
    )
    verify_tsb.add_argument('tsb_path', help='Path to TSB file.')
    verify_tsb.add_argument('--skip-signature', action='store_true', help='Skip signature verification.')
    verify_tsb.add_argument('--identity', help='Require specific OIDC identity (e.g., email).')
    verify_tsb.add_argument('--issuer', help='Require specific OIDC issuer (e.g., https://accounts.google.com).')
    verify_tsb.set_defaults(func=handlers.get('verify_tsb'))

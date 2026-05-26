"""CLI handlers for ``teaagent skill marketplace`` commands."""

from __future__ import annotations

import json
from argparse import Namespace


def skill_publish_command(args: Namespace) -> int:
    from teaagent.marketplace import MarketplaceRegistry

    registry = MarketplaceRegistry(args.root)
    entry = registry.publish(
        name=args.name,
        description=args.description,
        version=args.version,
        author=args.author,
        skill_path=args.skill_path,
        tags=args.tags,
    )
    if args.json:
        print(json.dumps(entry.to_dict()))
    else:
        print(f'Published {entry.name} v{entry.version} (id={entry.entry_id[:8]})')
    return 0


def skill_search_command(args: Namespace) -> int:
    from teaagent.marketplace import MarketplaceRegistry

    registry = MarketplaceRegistry(args.root)
    results = registry.search(args.query, tag=args.tag, limit=args.limit)
    if args.json:
        print(json.dumps([e.to_dict() for e in results]))
    else:
        for e in results:
            print(f'{e.name:<24}  v{e.version:<8}  {e.description[:60]}')
    return 0


def skill_marketplace_list_command(args: Namespace) -> int:
    from teaagent.marketplace import MarketplaceRegistry

    registry = MarketplaceRegistry(args.root)
    entries = registry.list(limit=args.limit)
    if args.json:
        print(json.dumps([e.to_dict() for e in entries]))
    else:
        for e in entries:
            print(
                f'{e.name:<24}  v{e.version:<8}  {e.author:<16}  {e.description[:50]}'
            )
    return 0


def skill_install_marketplace_command(args: Namespace) -> int:
    from teaagent.marketplace import MarketplaceClient, MarketplaceRegistry

    client = MarketplaceClient()
    remote_skills = client.fetch(query=args.name, limit=5)
    for s in remote_skills:
        if s.name == args.name or args.name in s.name:
            dest = f'.teaagent/skills/{args.name}/SKILL.md'
            if client.download(s, dest):
                print(f'Installed {args.name} to {dest}')
                MarketplaceRegistry(args.root).publish(
                    name=s.name,
                    description=s.description,
                    version=s.version,
                    author=s.author,
                    skill_path=dest,
                )
                return 0
    print(f'Skill {args.name!r} not found in remote marketplace')
    return 1

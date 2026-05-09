from __future__ import annotations

import argparse
import json
from typing import Any

from teaagent.llm import available_providers


def doctor_graphqlite(args: argparse.Namespace) -> int:
    ok, message = args._check_graphqlite(args.database)  # type: ignore[attr-defined]
    print(json.dumps({'ok': ok, 'message': message}, sort_keys=True))
    return 0 if ok else 1


def doctor_model(args: argparse.Namespace) -> int:
    ok, message = args._check_llm(args.provider)  # type: ignore[attr-defined]
    print(
        json.dumps(
            {'ok': ok, 'message': message, 'provider': args.provider}, sort_keys=True
        )
    )
    return 0 if ok else 1


def doctor_all(args: argparse.Namespace) -> int:
    checks: dict[str, Any] = {}
    gql_ok, gql_message = args._check_graphqlite(args.database)  # type: ignore[attr-defined]
    checks['graphqlite'] = {'ok': gql_ok, 'message': gql_message}
    provider_results = []
    for provider in args.provider or available_providers():
        ok, message = args._check_llm(provider)  # type: ignore[attr-defined]
        provider_results.append({'provider': provider, 'ok': ok, 'message': message})
    checks['providers'] = provider_results
    ok = gql_ok and all(item['ok'] for item in provider_results)
    print_json({'ok': ok, 'checks': checks})
    return 0 if ok else 1


def print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))

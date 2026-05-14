from __future__ import annotations

import argparse
import json
import os
from typing import Any

from teaagent.llm import LLMMessage, LLMRequest, available_providers
from teaagent.model_routing import route_model


def model_providers(_args: argparse.Namespace) -> int:
    print_json(available_providers())
    return 0


def model_smoke(args: argparse.Namespace) -> int:
    live_env_var = getattr(args, 'live_env_var', None)
    if live_env_var is not None and os.environ.get(live_env_var) != '1':
        print_json(
            {
                'provider': args.provider,
                'skipped': True,
                'reason': f'gated by env {live_env_var}=1',
            }
        )
        return 0
    adapter = args._adapter_factory(args.provider, model=args.model)  # type: ignore[attr-defined]
    response = adapter.complete(
        LLMRequest(
            messages=[LLMMessage(role='user', content=args.prompt)],
            max_tokens=args.max_tokens,
        )
    )
    print_json(
        {
            'provider': response.provider,
            'model': response.model,
            'content': response.content,
        }
    )
    return 0


def model_conformance(args: argparse.Namespace) -> int:
    kwargs = {
        'prompt': args.prompt,
        'expected_content': args.expect if args.expect else None,
        'max_tokens': args.max_tokens,
        'model': args.model,
    }
    if args.live_env_var is not None:
        kwargs['live_env_var'] = args.live_env_var
    report = args._run_model_conformance(args.provider, **kwargs)  # type: ignore[attr-defined]
    print_json(report.as_dict())
    return 0 if report.ok else 1


def model_route(args: argparse.Namespace) -> int:
    print_json(
        route_model(args.task, provider=args.provider, model=args.model).to_dict()
    )
    return 0


def print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))

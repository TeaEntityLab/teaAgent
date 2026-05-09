from __future__ import annotations

import argparse
import json
from typing import Any

from teaagent.llm import LLMMessage, LLMRequest, available_providers
from teaagent.model_routing import route_model


def model_providers(_args: argparse.Namespace) -> int:
    print_json(available_providers())
    return 0


def model_smoke(args: argparse.Namespace) -> int:
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
    report = args._run_model_conformance(  # type: ignore[attr-defined]
        args.provider,
        prompt=args.prompt,
        expected_content=args.expect if args.expect else None,
        max_tokens=args.max_tokens,
        model=args.model,
    )
    print_json(report.as_dict())
    return 0 if report.ok else 1


def model_route(args: argparse.Namespace) -> int:
    print_json(
        route_model(args.task, provider=args.provider, model=args.model).to_dict()
    )
    return 0


def print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))

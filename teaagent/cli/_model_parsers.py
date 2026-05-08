from __future__ import annotations

import argparse
from typing import Callable

from teaagent.llm import available_providers


def register(
    subparsers: argparse._SubParsersAction,  # type: ignore[type-arg]
    handlers: dict[str, Callable],
) -> None:
    model = subparsers.add_parser('model', help='Run model adapter operations.')
    subs = model.add_subparsers(dest='model_command', required=True)

    providers = subs.add_parser('providers', help='List configured provider names.')
    providers.set_defaults(func=handlers['providers'])

    smoke = subs.add_parser('smoke', help='Run a minimal prompt against a provider.')
    smoke.add_argument('provider', choices=available_providers(), help='Model provider to call.')
    smoke.add_argument('--model', default=None, help='Override model name.')
    smoke.add_argument('--prompt', default='Reply with exactly: ok', help='Prompt to send.')
    smoke.add_argument('--max-tokens', type=int, default=32, help='Maximum output tokens.')
    smoke.set_defaults(func=handlers['smoke'])

    conformance = subs.add_parser(
        'conformance', help='Run live conformance checks across providers.'
    )
    conformance.add_argument(
        '--provider',
        action='append',
        choices=available_providers(),
        default=None,
        help='Provider to check. Can be repeated. Defaults to all providers.',
    )
    conformance.add_argument(
        '--model',
        default=None,
        help='Override model name for all selected providers.',
    )
    conformance.add_argument(
        '--prompt', default='Reply with exactly: ok', help='Prompt to send.'
    )
    conformance.add_argument(
        '--expect',
        default='ok',
        help='Exact response content required for pass. Use an empty string to only require non-empty output.',
    )
    conformance.add_argument('--max-tokens', type=int, default=32, help='Maximum output tokens.')
    conformance.set_defaults(func=handlers['conformance'])

    route = subs.add_parser(
        'route', help='Classify a task and choose a provider-specific model.'
    )
    route.add_argument('task', help='Task to route.')
    route.add_argument(
        '--provider',
        default='gpt',
        choices=available_providers(),
        help='Provider to route within.',
    )
    route.add_argument('--model', default=None, help='Explicit model override.')
    route.set_defaults(func=handlers['route'])

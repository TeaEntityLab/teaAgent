from __future__ import annotations

import argparse
from typing import Callable, Optional

from teaagent.llm import available_providers
from teaagent.policy import PermissionMode


def _add_workspace_bootstrap_args(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        '--root', default='.', help='Workspace root. Defaults to current directory.'
    )
    p.add_argument(
        '--provider',
        choices=available_providers(),
        default=None,
        help='Default provider to set. If omitted, prompts interactively.',
    )
    p.add_argument(
        '--api-key',
        default=None,
        help='Provider API key. If omitted, prompts interactively (hidden).',
    )
    p.add_argument(
        '--permission-mode',
        choices=[mode.value for mode in PermissionMode],
        default=PermissionMode.PROMPT.value,
        help='Default permission mode written to config.',
    )
    p.add_argument(
        '--max-iterations',
        type=int,
        default=10,
        help='Default max_iterations written to config.',
    )
    p.add_argument(
        '--max-tool-calls',
        type=int,
        default=10,
        help='Default max_tool_calls written to config.',
    )
    p.add_argument(
        '--write-env',
        action='store_true',
        help='Also write .teaagent/env export line for the selected provider API key.',
    )
    p.add_argument(
        '--context-profile',
        choices=['lean', 'balanced', 'deep'],
        default='balanced',
        help='Default context profile written to config.',
    )
    p.add_argument(
        '--heartbeat',
        type=float,
        default=0.0,
        help='Default heartbeat interval (seconds) written to config.',
    )
    p.add_argument(
        '--daily-cost-cap-cents',
        type=int,
        default=0,
        help='Daily estimated cost cap in cents (0 disables).',
    )
    p.add_argument(
        '--human',
        action='store_true',
        help='Print a beginner-friendly summary instead of JSON.',
    )


def _init(
    subparsers: argparse._SubParsersAction,  # argparse private class lacks generic type param
    handler: Optional[Callable] = None,
) -> None:
    p = subparsers.add_parser(
        'init',
        help='Initialize workspace TeaAgent config (legacy bootstrap).',
        description='Create .teaagent/config.json and optionally .teaagent/env for provider keys.',
    )
    _add_workspace_bootstrap_args(p)
    p.add_argument(
        '--wizard',
        action='store_true',
        help='Run the guided first-session setup flow (same as `teaagent setup`).',
    )
    p.set_defaults(func=handler)


def _setup(
    subparsers: argparse._SubParsersAction,  # argparse private class lacks generic type param
    handler: Optional[Callable] = None,
) -> None:
    p = subparsers.add_parser(
        'setup',
        help='Guided first-session setup (recommended).',
        description=(
            'Configure provider, workspace defaults, AGENTS.md, env order checks, '
            'and return a safe next command.'
        ),
    )
    _add_workspace_bootstrap_args(p)
    p.set_defaults(func=handler)


def _clarify(
    subparsers: argparse._SubParsersAction, handler: Callable
) -> None:  # argparse private class lacks generic type param
    p = subparsers.add_parser(
        'clarify', help='Score a task for ambiguity before running an agent.'
    )
    p.add_argument('task', help='Task to clarify.')
    p.set_defaults(func=handler)


def _configure(
    subparsers: argparse._SubParsersAction,  # argparse private class lacks generic type param
    handler: Optional[Callable] = None,
) -> None:
    p = subparsers.add_parser(
        'configure',
        help='Interactively set provider API keys.',
        description='Check which providers are missing API keys and prompt for each one.',
    )
    p.add_argument(
        '--provider',
        action='append',
        choices=available_providers(),
        default=None,
        help='Provider to configure. Can be repeated. Defaults to all providers.',
    )
    p.set_defaults(func=handler)


def _completion(
    subparsers: argparse._SubParsersAction, handler: Callable
) -> None:  # argparse private class lacks generic type param
    p = subparsers.add_parser('completion', help='Print a shell completion snippet.')
    p.add_argument(
        'shell', choices=['bash', 'zsh', 'fish'], help='Shell to generate for.'
    )
    p.set_defaults(func=handler)

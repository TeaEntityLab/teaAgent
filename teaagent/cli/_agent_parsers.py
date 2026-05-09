from __future__ import annotations

import argparse
from typing import Callable

from teaagent.llm import available_providers
from teaagent.policy import PermissionMode


def register(
    subparsers: argparse._SubParsersAction,  # type: ignore[type-arg]
    handlers: dict[str, Callable],
) -> None:
    agent = subparsers.add_parser('agent', help='Run model-driven agent tasks.')
    subs = agent.add_subparsers(dest='agent_command', required=True)
    _run(subs, handlers['run'])
    _preflight(subs, handlers['preflight'])
    _resume(subs, handlers['resume'])
    _status(subs, handlers['status'])
    _runs(subs, handlers['runs'])
    _show(subs, handlers['show'])
    _card(subs, handlers['card'])


def _run(subs: argparse._SubParsersAction, handler: Callable) -> None:  # type: ignore[type-arg]
    p = subs.add_parser(
        'run',
        help='Run one autonomous task with workspace tools.',
        description='Run one autonomous task with workspace tools.',
    )
    p.add_argument(
        'provider', choices=available_providers(), help='Model provider to use.'
    )
    p.add_argument('task', help='Task for the agent to perform.')
    p.add_argument(
        '--root', default='.', help='Workspace root. Defaults to current directory.'
    )
    p.add_argument('--model', default=None, help='Override model name.')
    p.add_argument(
        '--route-model',
        action='store_true',
        help='Choose a provider-specific model from the task category when --model is not set.',
    )
    p.add_argument(
        '--max-iterations', type=int, default=10, help='Maximum agent loop iterations.'
    )
    p.add_argument('--max-tool-calls', type=int, default=10, help='Maximum tool calls.')
    p.add_argument(
        '--clarify',
        action='store_true',
        help='Run deterministic ambiguity scoring before calling the model.',
    )
    p.add_argument(
        '--allow-destructive',
        action='store_true',
        help='Allow destructive tools such as write, patch, and shell.',
    )
    p.add_argument(
        '--approve-call-id',
        action='append',
        default=[],
        help='Approve one exact destructive tool call id. Can be repeated.',
    )
    p.add_argument(
        '--hitl-approval',
        action='store_true',
        help='Prompt before executing unapproved destructive tool calls in prompt permission mode.',
    )
    p.add_argument(
        '--permission-mode',
        choices=[mode.value for mode in PermissionMode],
        default=PermissionMode.PROMPT.value,
        help='Permission mode for workspace tools.',
    )
    p.add_argument(
        '--subagent',
        action='store_true',
        help="Expose the 'subagent' tool so the model can delegate sub-tasks.",
    )
    p.add_argument(
        '--max-subagent-depth',
        type=int,
        default=1,
        help='Maximum nested subagent depth.',
    )
    p.add_argument(
        '--heartbeat',
        type=float,
        default=0.0,
        help='Emit a heartbeat audit event every N seconds while running. 0 disables.',
    )
    p.add_argument(
        '--telemetry-otlp-endpoint',
        default=None,
        metavar='URL',
        help='Export OpenTelemetry traces to this OTLP HTTP endpoint (e.g. http://localhost:4318/v1/traces).',
    )
    p.add_argument(
        '--telemetry-service-name',
        default='teaagent',
        help='OTel service.name resource attribute. Default: teaagent.',
    )
    p.add_argument(
        '--telemetry-console',
        action='store_true',
        help='Also print OpenTelemetry spans to stderr (debug).',
    )
    p.add_argument(
        '--checkpoint-store',
        default=None,
        metavar='PATH',
        help='SQLite path for run checkpoint storage. Saves context after each tool call.',
    )
    p.set_defaults(func=handler)


def _preflight(subs: argparse._SubParsersAction, handler: Callable) -> None:  # type: ignore[type-arg]
    p = subs.add_parser(
        'preflight',
        help='Summarize clarify, routing, memory, and tool state without calling a model.',
    )
    p.add_argument(
        'provider', choices=available_providers(), help='Model provider to plan for.'
    )
    p.add_argument('task', help='Task to evaluate.')
    p.add_argument(
        '--root', default='.', help='Workspace root. Defaults to current directory.'
    )
    p.add_argument('--model', default=None, help='Override model name.')
    p.add_argument(
        '--route-model', action='store_true', help='Apply task category routing.'
    )
    p.add_argument(
        '--permission-mode',
        choices=[mode.value for mode in PermissionMode],
        default=PermissionMode.PROMPT.value,
        help='Permission mode to report.',
    )
    p.add_argument(
        '--memory-limit',
        type=int,
        default=5,
        help='Maximum matched memories to include.',
    )
    p.set_defaults(func=handler)


def _resume(subs: argparse._SubParsersAction, handler: Callable) -> None:  # type: ignore[type-arg]
    p = subs.add_parser(
        'resume',
        help="Re-run a persisted run's task using the original recorded task.",
    )
    p.add_argument(
        'provider', choices=available_providers(), help='Model provider to use.'
    )
    p.add_argument('run_id', help='Run id to resume.')
    p.add_argument(
        '--root', default='.', help='Workspace root. Defaults to current directory.'
    )
    p.add_argument('--model', default=None, help='Override model name.')
    p.add_argument(
        '--route-model', action='store_true', help='Apply task category routing.'
    )
    p.add_argument(
        '--max-iterations', type=int, default=10, help='Maximum agent loop iterations.'
    )
    p.add_argument('--max-tool-calls', type=int, default=10, help='Maximum tool calls.')
    p.add_argument(
        '--clarify',
        action='store_true',
        help='Run deterministic ambiguity scoring before calling the model.',
    )
    p.add_argument(
        '--allow-destructive', action='store_true', help='Allow destructive tools.'
    )
    p.add_argument(
        '--approve-call-id',
        action='append',
        default=[],
        help='Approve one exact destructive tool call id. Can be repeated.',
    )
    p.add_argument(
        '--hitl-approval',
        action='store_true',
        help='Prompt before unapproved destructive tool calls.',
    )
    p.add_argument(
        '--permission-mode',
        choices=[mode.value for mode in PermissionMode],
        default=PermissionMode.PROMPT.value,
        help='Permission mode for workspace tools.',
    )
    p.add_argument(
        '--subagent', action='store_true', help="Expose the 'subagent' tool."
    )
    p.add_argument(
        '--max-subagent-depth',
        type=int,
        default=1,
        help='Maximum nested subagent depth.',
    )
    p.add_argument(
        '--heartbeat',
        type=float,
        default=0.0,
        help='Heartbeat interval seconds. 0 disables.',
    )
    p.add_argument(
        '--fresh-restart',
        action='store_true',
        help='Re-run the original task from scratch instead of replaying observations from the prior run.',
    )
    p.add_argument(
        '--checkpoint-store',
        default=None,
        metavar='PATH',
        help='SQLite path for checkpoint storage. Used to restore compacted context on resume.',
    )
    p.set_defaults(func=handler)


def _status(subs: argparse._SubParsersAction, handler: Callable) -> None:  # type: ignore[type-arg]
    p = subs.add_parser('status', help='Show liveness status of a persisted run.')
    p.add_argument('run_id', help='Run id to inspect.')
    p.add_argument(
        '--root', default='.', help='Workspace root. Defaults to current directory.'
    )
    p.set_defaults(func=handler)


def _runs(subs: argparse._SubParsersAction, handler: Callable) -> None:  # type: ignore[type-arg]
    p = subs.add_parser('runs', help='List persisted agent runs.')
    p.add_argument(
        '--root', default='.', help='Workspace root. Defaults to current directory.'
    )
    p.add_argument('--limit', type=int, default=20, help='Maximum runs to list.')
    p.set_defaults(func=handler)


def _show(subs: argparse._SubParsersAction, handler: Callable) -> None:  # type: ignore[type-arg]
    p = subs.add_parser('show', help='Show one persisted run JSONL record.')
    p.add_argument('run_id', help='Run id to show.')
    p.add_argument(
        '--root', default='.', help='Workspace root. Defaults to current directory.'
    )
    p.set_defaults(func=handler)


def _card(subs: argparse._SubParsersAction, handler: Callable) -> None:  # type: ignore[type-arg]
    p = subs.add_parser(
        'card',
        help='Print an AgentCard describing this agent and its registered tools.',
    )
    p.add_argument(
        '--root', default='.', help='Workspace root. Defaults to current directory.'
    )
    p.add_argument(
        '--agent-name',
        default='teaagent',
        help='Agent name to embed in the card. Default: teaagent.',
    )
    p.add_argument(
        '--endpoint',
        default=None,
        help='Public endpoint URL to embed in the card (optional).',
    )
    p.set_defaults(func=handler)

"""Sandbox CLI argument parsers."""

from __future__ import annotations

import argparse
from typing import Any, Callable, Optional


def _sandbox_route(
    subparsers: argparse._SubParsersAction,  # type: ignore[type-arg]
    route_handler: Optional[Callable] = None,
) -> None:
    """Register sandbox route subcommand."""
    route_cmd = subparsers.add_parser(
        'route', help='Route a skill to the appropriate sandbox'
    )
    route_cmd.add_argument('skill_path', help='Path to the skill directory')
    route_cmd.add_argument(
        '--risk-level',
        choices=['low', 'medium', 'high', 'critical'],
        default='medium',
        help='Risk level of the skill',
    )
    route_cmd.add_argument(
        '--preferred-sandbox',
        choices=['auto', 'directory-snapshot', 'docker', 'wasm'],
        help='Preferred sandbox type',
    )
    route_cmd.add_argument(
        '--default-sandbox',
        choices=['auto', 'directory-snapshot', 'docker', 'wasm'],
        default='auto',
        help='Default sandbox type',
    )
    route_cmd.add_argument(
        '--wasm-memory-limit-mb', type=int, default=256, help='WASM memory limit in MB'
    )
    route_cmd.add_argument(
        '--docker-cpu-quota', type=float, help='Docker CPU quota in cores'
    )
    route_cmd.add_argument(
        '--docker-memory-limit', help='Docker memory limit (e.g., 1g, 512m)'
    )
    route_cmd.add_argument(
        '--show-config', action='store_true', help='Show sandbox configuration'
    )
    route_cmd.set_defaults(func=route_handler)


def _sandbox_execute(
    subparsers: argparse._SubParsersAction,  # type: ignore[type-arg]
    execute_handler: Optional[Callable] = None,
) -> None:
    execute_cmd = subparsers.add_parser(
        'execute', help='Execute a skill inside a routed sandbox'
    )
    execute_cmd.add_argument('skill_path', help='Path to the skill directory')
    execute_cmd.add_argument(
        '--payload',
        default='{}',
        help='JSON object payload passed to skill run()',
    )
    execute_cmd.add_argument(
        '--risk-level',
        choices=['low', 'medium', 'high', 'critical'],
        default='medium',
        help='Risk level of the skill',
    )
    execute_cmd.add_argument(
        '--preferred-sandbox',
        choices=['auto', 'directory-snapshot', 'docker', 'wasm'],
        help='Preferred sandbox type',
    )
    execute_cmd.add_argument(
        '--default-sandbox',
        choices=['auto', 'directory-snapshot', 'docker', 'wasm'],
        default='auto',
        help='Default sandbox type',
    )
    execute_cmd.add_argument(
        '--wasm-memory-limit-mb', type=int, default=256, help='WASM memory limit in MB'
    )
    execute_cmd.add_argument(
        '--docker-cpu-quota', type=float, help='Docker CPU quota in cores'
    )
    execute_cmd.add_argument(
        '--docker-memory-limit', help='Docker memory limit (e.g., 1g, 512m)'
    )
    execute_cmd.set_defaults(func=execute_handler)


def _sandbox_monitor(
    subparsers: argparse._SubParsersAction,  # type: ignore[type-arg]
    monitor_handler: Optional[Callable] = None,
) -> None:
    """Register sandbox monitor subcommand."""
    monitor_cmd = subparsers.add_parser(
        'monitor', help='Monitor resource usage for a container'
    )
    monitor_cmd.add_argument('container_id', help='Docker container ID')
    monitor_cmd.add_argument('--cpu-limit-cores', type=float, help='CPU limit in cores')
    monitor_cmd.add_argument('--memory-limit-mb', type=float, help='Memory limit in MB')
    monitor_cmd.add_argument(
        '--duration', type=float, help='Monitor duration in seconds'
    )
    monitor_cmd.add_argument(
        '--check-interval', type=float, default=5.0, help='Check interval in seconds'
    )
    monitor_cmd.set_defaults(func=monitor_handler)


def _sandbox_check(
    subparsers: argparse._SubParsersAction,  # type: ignore[type-arg]
    check_wasm_handler: Optional[Callable] = None,
    check_compatibility_handler: Optional[Callable] = None,
) -> None:
    """Register sandbox check subcommands."""
    check_parser = subparsers.add_parser('check', help='Check sandbox capabilities')

    check_subs = check_parser.add_subparsers(
        dest='check_command', help='Check commands'
    )

    # Check WASM availability
    wasm_cmd = check_subs.add_parser('wasm', help='Check if WASM runtime is available')
    wasm_cmd.set_defaults(func=check_wasm_handler)

    # Check skill compatibility
    compat_cmd = check_subs.add_parser(
        'compatibility', help='Check skill compatibility with WASM'
    )
    compat_cmd.add_argument('skill_path', help='Path to the skill directory')
    compat_cmd.add_argument(
        '--memory-limit-mb', type=int, default=256, help='WASM memory limit in MB'
    )
    compat_cmd.set_defaults(func=check_compatibility_handler)


def register(
    subparsers: argparse._SubParsersAction,
    handlers: dict[str, Any],
) -> None:
    """Register sandbox subcommands."""
    _sandbox(
        subparsers,
        handlers.get('route'),
        handlers.get('monitor'),
        handlers.get('check_wasm'),
        handlers.get('check_compatibility'),
        handlers.get('execute'),
        handlers.get('wasm_contract'),
    )


def _sandbox(
    subparsers: argparse._SubParsersAction,  # type: ignore[type-arg]
    route_handler: Optional[Callable] = None,
    monitor_handler: Optional[Callable] = None,
    check_wasm_handler: Optional[Callable] = None,
    check_compatibility_handler: Optional[Callable] = None,
    execute_handler: Optional[Callable] = None,
    wasm_contract_handler: Optional[Callable] = None,
) -> None:
    """Register sandbox subcommands."""
    sandbox_parser = subparsers.add_parser('sandbox', help='Sandbox management')

    sandbox_subs = sandbox_parser.add_subparsers(
        dest='sandbox_command', help='Sandbox commands'
    )

    _sandbox_route(sandbox_subs, route_handler)
    _sandbox_execute(sandbox_subs, execute_handler)
    _sandbox_monitor(sandbox_subs, monitor_handler)
    _sandbox_check(sandbox_subs, check_wasm_handler, check_compatibility_handler)
    contract_cmd = sandbox_subs.add_parser(
        'wasm-contract', help='Show or write WASM invoke contract for a skill'
    )
    contract_cmd.add_argument('skill_path', help='Path to the skill directory')
    contract_cmd.add_argument(
        '--write-manifest',
        action='store_true',
        help='Write wasm_manifest.json beside the skill',
    )
    contract_cmd.add_argument(
        '--validate',
        action='store_true',
        help='Include WASM module validation in output',
    )
    contract_cmd.add_argument(
        '--memory-limit-mb', type=int, default=256, help='WASM memory limit in MB'
    )
    contract_cmd.set_defaults(func=wasm_contract_handler)

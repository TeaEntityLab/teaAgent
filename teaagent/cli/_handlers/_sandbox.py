"""Sandbox CLI handlers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from teaagent.resource_monitor import ResourceMonitor
from teaagent.skill_router import SandboxType, SkillRouter
from teaagent.wasm_runtime import is_wasm_available


def sandbox_route_command(args: argparse.Namespace) -> int:
    """Route a skill to the appropriate sandbox."""
    skill_path = Path(args.skill_path)
    if not skill_path.exists():
        print(f'Error: Skill path does not exist: {skill_path}')
        return 1

    from teaagent.consensus import RiskLevel

    risk_level = RiskLevel(args.risk_level)
    preferred_sandbox = (
        SandboxType(args.preferred_sandbox) if args.preferred_sandbox else None
    )

    router = SkillRouter(
        default_sandbox=SandboxType(args.default_sandbox),
        wasm_memory_limit_mb=args.wasm_memory_limit_mb,
        docker_cpu_quota=args.docker_cpu_quota,
        docker_memory_limit=args.docker_memory_limit,
    )

    decision = router.route_skill(skill_path, risk_level, preferred_sandbox)

    print(f'Sandbox Type: {decision.sandbox_type.value}')
    print(f'Reason: {decision.reason}')
    if decision.warnings:
        print('Warnings:')
        for warning in decision.warnings:
            print(f'  - {warning}')

    if args.show_config:
        config = router.get_sandbox_config(decision.sandbox_type)
        print('\nConfiguration:')
        print(json.dumps(config, indent=2))

    return 0


def sandbox_monitor_command(args: argparse.Namespace) -> int:
    """Monitor resource usage for a container."""
    monitor = ResourceMonitor(
        container_id=args.container_id,
        cpu_limit_cores=args.cpu_limit_cores,
        memory_limit_mb=args.memory_limit_mb,
    )

    monitor.start()

    if args.duration:
        # Monitor for a duration
        from teaagent.resource_monitor import monitor_container

        snapshots = monitor_container(
            container_id=args.container_id,
            cpu_limit_cores=args.cpu_limit_cores,
            memory_limit_mb=args.memory_limit_mb,
            duration_seconds=args.duration,
            check_interval_seconds=args.check_interval,
        )

        print(f'Monitored for {args.duration} seconds')
        print(f'Snapshots collected: {len(snapshots)}')

        if snapshots:
            avg_cpu = sum(s.cpu_percent for s in snapshots) / len(snapshots)
            avg_memory = sum(s.memory_mb for s in snapshots) / len(snapshots)
            print(f'Average CPU: {avg_cpu:.1f}%')
            print(f'Average Memory: {avg_memory:.1f} MB')
    else:
        # Single snapshot
        usage = monitor.get_current_usage()
        if usage:
            print(f'CPU: {usage.cpu_percent:.1f}%')
            print(f'Memory: {usage.memory_mb:.1f} MB')
            if usage.memory_limit_mb:
                print(f'Memory Limit: {usage.memory_limit_mb:.1f} MB')
            if usage.cpu_limit_cores:
                print(f'CPU Limit: {usage.cpu_limit_cores:.1f} cores')
        else:
            print('Failed to get resource usage')
            return 1

    monitor.stop()
    return 0


def sandbox_check_wasm_command(args: argparse.Namespace) -> int:
    """Check if WASM runtime is available."""
    available = is_wasm_available()

    if available:
        print('WASM runtime is available')
        return 0
    else:
        print('WASM runtime is not available')
        print('Install with: pip install teaagent[wasm]')
        return 1


def sandbox_check_compatibility_command(args: argparse.Namespace) -> int:
    """Check skill compatibility with WASM."""
    if not is_wasm_available():
        print('WASM runtime is not available')
        print('Install with: pip install teaagent[wasm]')
        return 1

    skill_path = Path(args.skill_path)
    if not skill_path.exists():
        print(f'Error: Skill path does not exist: {skill_path}')
        return 1

    from teaagent.wasm_runtime import WASMRuntime

    runtime = WASMRuntime(memory_limit_mb=args.memory_limit_mb)
    result = runtime.check_compatibility(skill_path)

    print(f'Compatible: {result["compatible"]}')
    if result['issues']:
        print('Issues:')
        for issue in result['issues']:
            print(f'  - {issue}')
    if result['warnings']:
        print('Warnings:')
        for warning in result['warnings']:
            print(f'  - {warning}')

    return 0

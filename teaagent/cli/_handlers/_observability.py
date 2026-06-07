"""CLI handlers for health, metrics, and credential rotation."""

from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone
from pathlib import Path

from teaagent.cli._output import print_json
from teaagent.health import collect_health_report
from teaagent.llm import available_providers
from teaagent.llm._config import PROVIDER_CONFIGS
from teaagent.operation_metrics import get_operation_metrics
from teaagent.structured_logging import configure_structured_logging
from teaagent.telemetry._metrics import InMemoryMetricsSink
from teaagent.wizard import merge_env_exports, provider_env_var


def health_command(args: argparse.Namespace) -> int:
    report = collect_health_report(args.root)
    if getattr(args, 'json', False) or not getattr(args, 'human', False):
        print_json(report)
    else:
        print(f'Status: {report["status"]}')
        for name, section in report.get('checks', {}).items():
            ok = section.get('ok', False)
            marker = '✓' if ok else '✗'
            print(f'  {marker} {name}')
    return 0 if report['status'] == 'healthy' else 2


def metrics_command(args: argparse.Namespace) -> int:
    if getattr(args, 'structured_logs', False):
        configure_structured_logging(json_output=True)

    snapshot = get_operation_metrics().snapshot()
    # Include in-memory telemetry sink if any audit events were recorded
    in_memory = InMemoryMetricsSink()
    telemetry_snapshot = in_memory.snapshot()
    payload = {
        'operation_metrics': snapshot,
        'telemetry_counters': telemetry_snapshot.counters,
        'telemetry_histograms': {
            key: {'count': len(values), 'sum': sum(values)}
            for key, values in telemetry_snapshot.histograms.items()
        },
    }
    print_json(payload)
    return 0


def credentials_rotate_command(args: argparse.Namespace) -> int:
    provider = args.provider
    if provider not in available_providers():
        print_json({'status': 'error', 'message': f'unknown provider: {provider}'})
        return 1

    env_var = provider_env_var(provider)
    if not env_var:
        print_json(
            {'status': 'error', 'message': f'no env var for provider {provider}'}
        )
        return 1

    new_key = getattr(args, 'api_key', None) or os.environ.get(env_var)
    if not new_key and not getattr(args, 'dry_run', False):
        print_json(
            {
                'status': 'error',
                'message': f'provide --api-key or set {env_var} in the environment',
            }
        )
        return 1

    root = Path(args.root).resolve()
    targets: list[str] = []

    if getattr(args, 'write_env', False) and new_key:
        env_path = root / '.teaagent' / 'env'
        merge_env_exports(
            env_path,
            {env_var: new_key},
            f'# Rotated by `teaagent credentials rotate` at {datetime.now(timezone.utc).isoformat()}',
        )
        targets.append(str(env_path))

    global_env = Path.home() / '.teaagent' / 'providers_env.zsh'
    if getattr(args, 'write_global', False) and new_key and global_env.parent.exists():
        merge_env_exports(
            global_env,
            {env_var: new_key},
            f'# Rotated by `teaagent credentials rotate` at {datetime.now(timezone.utc).isoformat()}',
        )
        targets.append(str(global_env))

    meta = PROVIDER_CONFIGS.get(provider)
    print_json(
        {
            'status': 'ok' if new_key or getattr(args, 'dry_run', False) else 'pending',
            'provider': provider,
            'env_var': env_var,
            'files_updated': targets,
            'dry_run': bool(getattr(args, 'dry_run', False)),
            'model_default': getattr(meta, 'default_model', None) if meta else None,
            'next_steps': [
                f'export {env_var}=<new-key>',
                f'teaagent doctor model {provider}',
            ],
        }
    )
    return 0

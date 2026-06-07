"""Workspace and harness health checks."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from teaagent.audit_chain import verify_audit_chain
from teaagent.config_loader import ConfigResolver
from teaagent.llm import check_llm_configuration


def collect_health_report(root: str | Path) -> dict[str, Any]:
    """Run health checks and return a JSON-serializable report."""
    workspace = Path(root).resolve()
    checks: dict[str, Any] = {}

    # Config validity
    try:
        resolved = ConfigResolver(workspace_root=workspace).resolve()
        checks['config'] = {
            'ok': True,
            'keys': sorted(resolved.values.keys()),
        }
    except (OSError, ValueError, TypeError) as exc:
        checks['config'] = {'ok': False, 'error': str(exc)}

    # Disk space (best effort)
    try:
        usage = shutil.disk_usage(workspace)
        free_gb = usage.free / (1024**3)
        checks['disk'] = {
            'ok': free_gb > 0.5,
            'free_gb': round(free_gb, 2),
        }
    except OSError as exc:
        checks['disk'] = {'ok': False, 'error': str(exc)}

    # Audit chain integrity
    audit_path = workspace / '.teaagent' / 'audit.jsonl'
    if audit_path.is_file():
        result = verify_audit_chain(audit_path)
        checks['audit_chain'] = {
            'ok': result.valid,
            'event_count': result.event_count,
            'failure_count': len(result.failures),
        }
    else:
        checks['audit_chain'] = {'ok': True, 'status': 'no_audit_log'}

    # Provider reachability (optional — only when configured)
    provider = None
    if checks.get('config', {}).get('ok'):
        provider = ConfigResolver(workspace_root=workspace).resolve().get('provider')
    if provider:
        ok, message = check_llm_configuration(str(provider))
        checks['provider'] = {'ok': ok, 'provider': provider, 'message': message}
    else:
        checks['provider'] = {'ok': True, 'status': 'not_configured'}

    overall_ok = all(
        section.get('ok', False)
        for section in checks.values()
        if isinstance(section, dict)
    )
    return {
        'status': 'healthy' if overall_ok else 'degraded',
        'root': str(workspace),
        'checks': checks,
    }

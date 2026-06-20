from __future__ import annotations

import argparse
import getpass
import os
from pathlib import Path
from typing import Any

from teaagent.ergonomics.approval_store import ApprovalPresetStore
from teaagent.llm._config import PROVIDER_CONFIGS

from .sanitize import _is_sensitive_key, print_json


def doctor_project(args: argparse.Namespace) -> int:
    if getattr(args, 'wizard', False):
        return _doctor_project_wizard(args)
    root = Path(getattr(args, 'root', '.')).resolve()
    security = ApprovalPresetStore(root, readonly=True).check_security_health()
    overall_ok = security['ok']
    payload = {
        'ok': overall_ok,
        'mode': 'checklist',
        'root': str(root),
        'security': security,
        'next_steps': [
            f'teaagent setup --root {root}',
            'teaagent doctor providers',
            'teaagent doctor all',
            f'teaagent mcp serve --http --port 7330 --root {root}',
        ],
    }
    print_json(payload)
    return 0 if overall_ok else 1


def doctor_mcp(args: argparse.Namespace) -> int:
    if getattr(args, 'wizard', False):
        return _doctor_mcp_wizard(args)
    root = str(Path(getattr(args, 'root', '.')).resolve())
    payload = {
        'ok': True,
        'mode': 'checklist',
        'root': root,
        'next_steps': [
            f'teaagent mcp serve --http --host 127.0.0.1 --port 7330 --root {root}',
            'Use --auth-token or OAuth when binding non-loopback hosts.',
        ],
    }
    print_json(payload)
    return 0


def doctor_env_order(args: argparse.Namespace) -> int:
    root = Path(getattr(args, 'root', '.')).resolve()
    home = Path.home()
    global_new = home / '.teaagent' / 'providers_env.zsh'
    global_legacy = home / '.teaagent' / 'provider_keys.zsh'
    project_env = root / '.teaagent' / 'env'

    global_providers_env_exists = global_new.is_file()
    global_provider_keys_exists = global_legacy.is_file()
    project_env_exists = project_env.is_file()
    checks: dict[str, Any] = {
        'global_providers_env': {
            'path': str(global_new),
            'exists': global_providers_env_exists,
        },
        'global_provider_keys': {
            'path': str(global_legacy),
            'exists': global_provider_keys_exists,
        },
        'project_env': {'path': str(project_env), 'exists': project_env_exists},
        'workers_ai_base_url_loaded': bool(os.environ.get('WORKERS_AI_BASE_URL')),
        'cloudflare_api_token_loaded': bool(os.environ.get('CLOUDFLARE_API_TOKEN')),
    }
    ok = global_providers_env_exists or global_provider_keys_exists
    next_steps = []
    if not global_providers_env_exists:
        next_steps.append('cp scripts/providers_env.zsh ~/.teaagent/providers_env.zsh')
        next_steps.append("echo 'source ~/.teaagent/providers_env.zsh' >> ~/.zshrc")
    if project_env_exists:
        next_steps.append('source .teaagent/env')
    else:
        next_steps.append(
            'Generate project overrides when needed: teaagent doctor aigateway --wizard --write-env --root .'
        )
    next_steps.append('teaagent doctor aigateway')
    next_steps.append(
        'teaagent model smoke aigateway --prompt "Reply with exactly: ok"'
    )

    payload = {
        'ok': ok,
        'root': str(root),
        'checks': checks,
        'recommended_order': [
            'source ~/.teaagent/providers_env.zsh',
            'source .teaagent/env',
        ],
        'next_steps': next_steps,
    }
    print_json(payload)
    return 0 if ok else 1


def doctor_config(args: argparse.Namespace) -> int:
    """Print effective workspace config with per-key provenance (TASK-005).

    Shows where each effective config value came from in the precedence chain:
    ``default`` -> ``config:config.toml`` -> ``config:config.json`` ->
    ``env:VAR``. CLI flags override all of these at run time (via the ``_UNSET``
    sentinel in ``apply_workspace_defaults_to_namespace``), but ``doctor`` is not
    the agent run, so the CLI layer is noted rather than resolved. Sensitive
    values (tokens/secrets) are redacted.
    """
    from teaagent.ergonomics.workspace_defaults import resolve_config_provenance

    root = Path(getattr(args, 'root', '.')).resolve()
    prov = resolve_config_provenance(root)

    # Credential-bearing endpoints whose VALUE is redacted in this view even
    # though the key name is not a generic secret marker (a webhook URL can
    # embed a token in its path/query). Scoped to this command — not a change to
    # the global redaction policy. Source/provenance is still shown.
    _credential_endpoint_keys = {'automation_webhook_url'}

    # A list of entries (not a dict keyed by config key): the doctor JSON sink
    # redacts dict VALUES whose KEY is sensitive, which would collapse a
    # secret-keyed entry to a string and lose its provenance. Keying on neutral
    # 'key'/'value'/'source' preserves the source while the value is redacted.
    config: list[dict[str, Any]] = []
    for key in sorted(prov):
        entry = prov[key]
        value = entry['value']
        redact = _is_sensitive_key(key) or key in _credential_endpoint_keys
        if redact and value not in (None, ''):
            value = '***REDACTED***'
        config.append({'key': key, 'value': value, 'source': entry['source']})

    payload = {
        'ok': True,
        'root': str(root),
        'precedence': [
            'cli',
            'env',
            'env-file:.teaagent/env',
            'config:config.json',
            'config:config.toml',
            'default',
        ],
        'note': (
            'CLI flags override env/config/default at run time; doctor shows the '
            'non-CLI layers (it is not the agent run). "env" is the shell '
            'environment; "env-file:.teaagent/env" is the workspace env file '
            '(the shell wins when both define a var).'
        ),
        'config': config,
    }
    print_json(payload)
    return 0


def doctor_config_lint_command(args: argparse.Namespace) -> int:
    from teaagent.config_lint import lint_runtime_config

    permission_mode = getattr(args, 'permission_mode', 'prompt') or 'prompt'
    findings = lint_runtime_config(
        root=getattr(args, 'root', '.') or '.',
        permission_mode=permission_mode,
        allow_destructive=bool(getattr(args, 'allow_destructive', False)),
        subagent_isolation=getattr(args, 'subagent_isolation', None),
    )
    errors = [f for f in findings if f.severity == 'error']
    print_json(
        {
            'status': 'error' if errors else 'ok',
            'finding_count': len(findings),
            'findings': [finding.to_dict() for finding in findings],
        }
    )
    return 1 if errors else 0


# ── Wizard implementations ────────────────────────────────────────────────


def _doctor_project_wizard(args: argparse.Namespace) -> int:
    root = str(Path(getattr(args, 'root', '.')).resolve())
    provider = input('Default provider for project (default gpt): ').strip() or 'gpt'
    if provider not in PROVIDER_CONFIGS:
        print_json({'ok': False, 'error': f'unknown provider: {provider}'})
        return 1
    permission_mode = (
        input(
            'Permission mode [read-only/workspace-write/prompt/allow] (default prompt): '
        )
        .strip()
        .lower()
        or 'prompt'
    )
    if permission_mode not in ('read-only', 'workspace-write', 'prompt', 'allow'):
        print_json(
            {'ok': False, 'error': f'unsupported permission mode: {permission_mode}'}
        )
        return 1

    payload = {
        'ok': True,
        'mode': 'wizard',
        'root': root,
        'provider': provider,
        'permission_mode': permission_mode,
        'next_steps': [
            f'teaagent setup --root {root} --provider {provider} --permission-mode {permission_mode}',
            f'teaagent doctor model {provider}',
            f'teaagent agent run {provider} "Summarize this repository" --root {root} --permission-mode read-only',
            f'teaagent mcp serve --http --port 7330 --root {root}',
        ],
    }
    print_json(payload)
    return 0


def _doctor_mcp_wizard(args: argparse.Namespace) -> int:
    root = str(Path(getattr(args, 'root', '.')).resolve())
    host = input('MCP host (default 127.0.0.1): ').strip() or '127.0.0.1'
    port = input('MCP port (default 7330): ').strip() or '7330'
    auth_choice = input('Enable bearer auth token? [y/N]: ').strip().lower() in (
        'y',
        'yes',
    )
    auth_token = ''
    if auth_choice:
        auth_token = getpass.getpass('Auth token (hidden): ').strip()

    cmd = f'teaagent mcp serve --http --host {host} --port {port} --root {root}'
    launch_command = cmd
    if auth_token:
        launch_command += ' --auth-token <redacted>'
    payload = {
        'ok': True,
        'mode': 'wizard',
        'config': {'host': host, 'port': port, 'auth_token': bool(auth_token)},
        'launch_command': launch_command,
        'next_steps': [launch_command],
    }
    print_json(payload)
    return 0

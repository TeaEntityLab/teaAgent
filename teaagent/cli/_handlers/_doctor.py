from __future__ import annotations

import argparse
import getpass
import json
import os
from pathlib import Path
from typing import Any

from teaagent.llm import available_providers
from teaagent.llm._config import PROVIDER_CONFIGS
from teaagent.wizard import (
    merge_env_exports,
    read_keychain_secret,
    redact_wizard_payload,
)

_REDACTED = '***REDACTED***'
_SENSITIVE_KEY_MARKERS = (
    'token',
    'password',
    'passwd',
    'secret',
    'api_key',
    'apikey',
    'authorization',
    'auth',
)
_SENSITIVE_EXACT_KEYS = {
    'api_token',
    'api_key_env',
    'authorization',
    'cf_aig_authorization',
}


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace('-', '_')
    if normalized in {'token_source'}:
        return False
    if normalized in _SENSITIVE_EXACT_KEYS:
        return True
    return any(marker in normalized for marker in _SENSITIVE_KEY_MARKERS)


def _looks_like_sensitive_string(value: str) -> bool:
    candidate = value.strip()
    if not candidate:
        return False
    lower = candidate.lower()
    if lower.startswith('bearer '):
        return True
    if candidate.startswith(('sk-', 'rk-', 'pk-', 'ghp_', 'xoxb-', 'xoxp-')):
        return True
    if len(candidate) >= 20 and any(ch.isdigit() for ch in candidate) and any(
        ch.isalpha() for ch in candidate
    ):
        return True
    return False


def _redact_sensitive_fields(
    value: Any, known_sensitive_values: set[str] | None = None
) -> Any:
    if known_sensitive_values is None:
        known_sensitive_values = set()

    if isinstance(value, dict):
        redacted: dict[Any, Any] = {}
        for k, v in value.items():
            key_str = str(k)
            if _is_sensitive_key(key_str):
                if isinstance(v, str) and v:
                    known_sensitive_values.add(v)
                redacted[k] = _REDACTED
            else:
                redacted[k] = _redact_sensitive_fields(v, known_sensitive_values)
        return redacted
    if isinstance(value, list):
        return [
            _redact_sensitive_fields(item, known_sensitive_values) for item in value
        ]
    if isinstance(value, str) and (
        value in known_sensitive_values or _looks_like_sensitive_string(value)
    ):
        return _REDACTED
    return value


def doctor_graphqlite(args: argparse.Namespace) -> int:
    ok, message = args._check_graphqlite(args.database)  # type: ignore[attr-defined]
    print(json.dumps({'ok': ok, 'message': message}, sort_keys=True))
    return 0 if ok else 1


def doctor_model(args: argparse.Namespace) -> int:
    if getattr(args, 'wizard', False):
        return _doctor_model_wizard(args)
    ok, message = args._check_llm(args.provider)  # type: ignore[attr-defined]
    print(
        json.dumps(
            {'ok': ok, 'message': message, 'provider': args.provider}, sort_keys=True
        )
    )
    return 0 if ok else 1


def doctor_aigateway(args: argparse.Namespace) -> int:
    if getattr(args, 'wizard', False):
        return _doctor_aigateway_wizard(args)

    provider = 'aigateway'
    ok, message = args._check_llm(provider)  # type: ignore[attr-defined]
    requested_mode = getattr(args, 'mode', 'workers-ai')
    compat_base_url = os.environ.get('AIGATEWAY_BASE_URL', '').strip()
    workers_base_url = os.environ.get('WORKERS_AI_BASE_URL', '').strip()
    base_url = compat_base_url if requested_mode == 'compat' else workers_base_url
    if not base_url and requested_mode == 'compat':
        base_url = workers_base_url
    extra_headers = os.environ.get('WORKERS_AI_EXTRA_HEADERS', '').strip()
    base_url_env = (
        'AIGATEWAY_BASE_URL' if requested_mode == 'compat' else 'WORKERS_AI_BASE_URL'
    )

    checks: dict[str, Any] = {
        'api_token': {'ok': ok, 'message': message, 'env': 'CLOUDFLARE_API_TOKEN'},
        'base_url': {
            'ok': bool(base_url),
            'env': base_url_env,
            'value': base_url or None,
            'message': (
                'configured'
                if base_url
                else (
                    'missing AIGATEWAY_BASE_URL (set to https://gateway.ai.cloudflare.com/v1/<account_id>/<gateway_id>/compat)'
                    if requested_mode == 'compat'
                    else 'missing WORKERS_AI_BASE_URL (set to Workers AI or AI Gateway workers-ai endpoint)'
                )
            ),
        },
        'aig_auth_header': {
            'ok': bool(extra_headers),
            'env': 'WORKERS_AI_EXTRA_HEADERS',
            'value': extra_headers or None,
            'message': (
                'configured (authenticated gateway mode)'
                if extra_headers
                else 'optional (required only when AI Gateway authenticated mode is ON)'
            ),
        },
    }

    uses_gateway = base_url.startswith('https://gateway.ai.cloudflare.com/')
    uses_gateway_compat = uses_gateway and '/compat' in base_url
    uses_gateway_workers = uses_gateway and '/workers-ai/' in base_url
    uses_workers_ai_direct = '/ai/v1' in base_url and not uses_gateway
    mode = (
        'gateway-compat'
        if uses_gateway_compat
        else 'gateway-workers-ai'
        if uses_gateway_workers
        else 'workers-ai-direct'
        if uses_workers_ai_direct
        else 'unknown'
    )
    all_ok = checks['api_token']['ok'] and checks['base_url']['ok']
    endpoint_profile = (
        'gateway-openai-compatible-unified'
        if mode == 'gateway-compat'
        else 'gateway-workers-ai-openai-compatible'
        if mode == 'gateway-workers-ai'
        else 'workers-ai-direct-openai-compatible'
        if mode == 'workers-ai-direct'
        else 'unrecognized'
    )
    next_steps = [
        'teaagent doctor model aigateway',
        'teaagent model smoke aigateway --prompt "Reply with exactly: ok"',
    ]
    if requested_mode == 'compat':
        next_steps.insert(
            0,
            'Set AIGATEWAY_BASE_URL to https://gateway.ai.cloudflare.com/v1/<account_id>/<gateway_id>/compat',
        )
        next_steps.append(
            'Use model names like dynamic/default or <provider>/<model> (for example: openai/gpt-5-mini).'
        )
    elif mode != 'gateway-workers-ai':
        next_steps.insert(
            0,
            'Set WORKERS_AI_BASE_URL to AI Gateway workers-ai endpoint: https://gateway.ai.cloudflare.com/v1/<account_id>/<gateway_id>/workers-ai/v1',
        )
    if not checks['aig_auth_header']['ok']:
        next_steps.append(
            'If Authenticated Gateway is enabled: export WORKERS_AI_EXTRA_HEADERS=\'{"cf-aig-authorization":"Bearer <gateway_token>"}\''
        )
    payload = {
        'ok': all_ok,
        'provider': provider,
        'requested_mode': requested_mode,
        'mode': mode,
        'endpoint_profile': endpoint_profile,
        'boundary': {
            'workers_ai': 'inference provider endpoint',
            'ai_gateway': 'optional policy/routing layer in front of Workers AI',
        },
        'checks': checks,
        'next_steps': next_steps,
    }

    if getattr(args, 'write_env', False):
        root = Path(getattr(args, 'root', '.')).resolve()
        env_file = root / '.teaagent' / 'env'
        base_url_key = (
            'AIGATEWAY_BASE_URL'
            if requested_mode == 'compat'
            else 'WORKERS_AI_BASE_URL'
        )
        updates: dict[str, str] = {
            'CLOUDFLARE_API_TOKEN': os.environ.get('CLOUDFLARE_API_TOKEN', '').strip()
        }
        if base_url:
            updates[base_url_key] = base_url
        if extra_headers:
            updates['WORKERS_AI_EXTRA_HEADERS'] = extra_headers
        merge_env_exports(
            env_file,
            updates,
            '# Updated by `teaagent doctor aigateway --write-env`.',
        )
        payload['env_status'] = 'written'
        payload['env_path'] = str(env_file)

    print_json(payload)
    return 0 if all_ok else 1


def doctor_providers(args: argparse.Namespace) -> int:
    if getattr(args, 'wizard', False):
        return _doctor_providers_wizard(args)

    results = []
    for provider in available_providers():
        ok, message = args._check_llm(provider)  # type: ignore[attr-defined]
        env_name = PROVIDER_CONFIGS[provider].api_key_env
        keychain_present = bool(read_keychain_secret(env_name))
        results.append(
            {
                'provider': provider,
                'ok': ok,
                'message': message,
                'env': env_name,
                'env_loaded': bool(os.environ.get(env_name)),
                'keychain_present': keychain_present,
            }
        )
    payload = {
        'ok': all(item['ok'] for item in results),
        'checks': results,
        'next_steps': [
            'teaagent doctor providers --wizard',
            'teaagent model smoke <provider> --prompt "Reply with exactly: ok"',
        ],
    }
    print_json(payload)
    return 0 if payload['ok'] else 1


def doctor_project(args: argparse.Namespace) -> int:
    if getattr(args, 'wizard', False):
        return _doctor_project_wizard(args)
    root = str(Path(getattr(args, 'root', '.')).resolve())
    payload = {
        'ok': True,
        'mode': 'checklist',
        'root': root,
        'next_steps': [
            f'teaagent setup --root {root}',
            'teaagent doctor providers',
            'teaagent doctor all',
            f'teaagent mcp serve --http --port 7330 --root {root}',
        ],
    }
    print_json(payload)
    return 0


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


def _doctor_aigateway_wizard(args: argparse.Namespace) -> int:
    requested_mode = getattr(args, 'mode', 'workers-ai')
    account_id = input('Cloudflare account id: ').strip()
    gateway_id = input('AI Gateway id: ').strip()
    api_token = getpass.getpass('CLOUDFLARE_API_TOKEN (hidden): ').strip()
    if not api_token:
        api_token = os.environ.get('CLOUDFLARE_API_TOKEN', '').strip()
    if not api_token:
        api_token = read_keychain_secret('CLOUDFLARE_API_TOKEN')
    auth_enabled = input('Authenticated Gateway enabled? [y/N]: ').strip().lower() in (
        'y',
        'yes',
    )
    gateway_token = ''
    if auth_enabled:
        gateway_token = getpass.getpass(
            'Gateway auth token (for cf-aig-authorization, hidden): '
        ).strip()

    base_url = ''
    if account_id and gateway_id:
        if requested_mode == 'compat':
            base_url = (
                f'https://gateway.ai.cloudflare.com/v1/{account_id}/{gateway_id}/compat'
            )
            os.environ['AIGATEWAY_BASE_URL'] = base_url
        else:
            base_url = f'https://gateway.ai.cloudflare.com/v1/{account_id}/{gateway_id}/workers-ai/v1'
            os.environ['WORKERS_AI_BASE_URL'] = base_url
    if api_token:
        os.environ['CLOUDFLARE_API_TOKEN'] = api_token
    if auth_enabled and gateway_token:
        os.environ['WORKERS_AI_EXTRA_HEADERS'] = json.dumps(
            {'cf-aig-authorization': f'Bearer {gateway_token}'}
        )

    env_status = 'not-written'
    env_path: str | None = None
    if getattr(args, 'write_env', False):
        root = Path(getattr(args, 'root', '.')).resolve()
        env_file = root / '.teaagent' / 'env'
        updates = {
            'CLOUDFLARE_API_TOKEN': api_token,
            (
                'AIGATEWAY_BASE_URL'
                if requested_mode == 'compat'
                else 'WORKERS_AI_BASE_URL'
            ): base_url,
        }
        if auth_enabled and gateway_token:
            updates['WORKERS_AI_EXTRA_HEADERS'] = json.dumps(
                {'cf-aig-authorization': f'Bearer {gateway_token}'}
            )
        merge_env_exports(
            env_file,
            updates,
            '# Updated by `teaagent doctor aigateway --wizard`.',
        )
        env_status = 'written'
        env_path = str(env_file)

    ok = bool(base_url and api_token)
    payload: dict[str, Any] = {
        'ok': ok,
        'mode': 'wizard',
        'provider': 'aigateway',
        'requested_mode': requested_mode,
        'configured': {
            'CLOUDFLARE_API_TOKEN': bool(api_token),
            (
                'AIGATEWAY_BASE_URL'
                if requested_mode == 'compat'
                else 'WORKERS_AI_BASE_URL'
            ): bool(base_url),
            'WORKERS_AI_EXTRA_HEADERS': bool(auth_enabled and gateway_token),
        },
        'next_steps': [
            'teaagent doctor aigateway',
            'teaagent doctor model aigateway',
            'teaagent model smoke aigateway --prompt "Reply with exactly: ok"',
        ],
        'env_status': env_status,
    }
    if env_path:
        payload['env_path'] = env_path
    print_json(payload)
    return 0 if ok else 1


def _doctor_model_wizard(args: argparse.Namespace) -> int:
    provider = args.provider
    config = PROVIDER_CONFIGS[provider]
    env_name = config.api_key_env

    key = getpass.getpass(f'{env_name} (hidden, empty to auto-detect): ').strip()
    token_source = 'prompt'
    if not key:
        key = os.environ.get(env_name, '').strip()
        token_source = 'env'
    if not key:
        key = read_keychain_secret(env_name)
        token_source = 'keychain' if key else 'missing'
    if key:
        os.environ[env_name] = key

    base_url_value = ''
    if config.base_url_env:
        base_url_value = input(f'{config.base_url_env} override (optional): ').strip()
        if base_url_value:
            os.environ[config.base_url_env] = base_url_value

    env_status = 'not-written'
    env_path: str | None = None
    if getattr(args, 'write_env', False):
        root = Path(getattr(args, 'root', '.')).resolve()
        env_file = root / '.teaagent' / 'env'
        updates = {env_name: key}
        if config.base_url_env and base_url_value:
            updates[config.base_url_env] = base_url_value
        merge_env_exports(
            env_file,
            updates,
            f'# Updated by `teaagent doctor model {provider} --wizard`.',
        )
        env_status = 'written'
        env_path = str(env_file)

    ok, message = args._check_llm(provider)  # type: ignore[attr-defined]
    payload: dict[str, Any] = {
        'ok': ok,
        'mode': 'wizard',
        'provider': provider,
        'env': env_name,
        'token_source': token_source,
        'message': message,
        'env_status': env_status,
        'next_steps': [
            f'teaagent doctor model {provider}',
            f'teaagent model smoke {provider} --prompt "Reply with exactly: ok"',
        ],
    }
    if env_path:
        payload['env_path'] = env_path
    print_json(payload)
    return 0 if ok else 1


def _doctor_providers_wizard(args: argparse.Namespace) -> int:
    selected = args.provider or available_providers()

    configured = []
    skipped = []
    auto_resolved = []
    env_updates: dict[str, str] = {}
    for provider in selected:
        ok, _message = args._check_llm(provider)  # type: ignore[attr-defined]
        env_name = PROVIDER_CONFIGS[provider].api_key_env
        if ok:
            skipped.append({'provider': provider, 'reason': 'already configured'})
            continue
        key = getpass.getpass(
            f'Enter {env_name} for {provider} (empty to auto-detect): '
        ).strip()
        source = 'prompt'
        if not key:
            key = os.environ.get(env_name, '').strip()
            source = 'env'
        if not key:
            key = read_keychain_secret(env_name)
            source = 'keychain' if key else 'missing'
        if not key:
            skipped.append({'provider': provider, 'reason': 'missing'})
            continue
        os.environ[env_name] = key
        configured.append(provider)
        env_updates[env_name] = key
        if source != 'prompt':
            auto_resolved.append({'provider': provider, 'source': source})

    env_status = 'not-written'
    env_path: str | None = None
    if getattr(args, 'write_env', False):
        root = Path(getattr(args, 'root', '.')).resolve()
        env_file = root / '.teaagent' / 'env'
        merge_env_exports(
            env_file,
            env_updates,
            '# Updated by `teaagent doctor providers --wizard`.',
        )
        env_status = 'written'
        env_path = str(env_file)

    unresolved = [item for item in skipped if item.get('reason') == 'missing']
    ok = len(unresolved) == 0
    payload: dict[str, Any] = {
        'ok': ok,
        'mode': 'wizard',
        'selected': selected,
        'configured': configured,
        'auto_resolved': auto_resolved,
        'skipped': skipped,
        'unresolved': unresolved,
        'env_status': env_status,
        'next_steps': [
            'teaagent doctor providers',
            'teaagent doctor all',
            'teaagent model smoke <provider> --prompt "Reply with exactly: ok"',
        ],
    }
    if env_path:
        payload['env_path'] = env_path
    print_json(payload)
    return 0 if ok else 1


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


def doctor_all(args: argparse.Namespace) -> int:
    checks: dict[str, Any] = {}
    gql_ok, gql_message = args._check_graphqlite(args.database)  # type: ignore[attr-defined]
    checks['graphqlite'] = {'ok': gql_ok, 'message': gql_message}
    provider_results = []
    configured_providers = args.provider
    if isinstance(configured_providers, str):
        providers = [configured_providers]
    else:
        providers = configured_providers or available_providers()
    for provider in providers:
        ok, message = args._check_llm(provider)  # type: ignore[attr-defined]
        provider_results.append({'provider': provider, 'ok': ok, 'message': message})
    checks['providers'] = provider_results
    ok = gql_ok and all(item['ok'] for item in provider_results)
    print_json({'ok': ok, 'checks': checks})
    return 0 if ok else 1


def doctor_migration_command(args: argparse.Namespace) -> int:
    from teaagent.schema_migration import SQLiteMigrationStore

    store_path = getattr(args, 'store', None)
    if not store_path:
        print_json(
            {'ok': False, 'error': '--store <path> is required for migration check'}
        )
        return 1
    try:
        store = SQLiteMigrationStore(store_path)
        status = store.status([])
        print_json({'ok': True, 'store': store_path, 'status': status})
        return 0
    except Exception as exc:
        print_json({'ok': False, 'error': str(exc)})
        return 1


def print_json(value: Any) -> None:
    if isinstance(value, dict) and value.get('mode') in {'wizard', 'setup'}:
        value = redact_wizard_payload(value)
    safe_value = _redact_sensitive_fields(value)
    print(json.dumps(safe_value, ensure_ascii=False, sort_keys=True))

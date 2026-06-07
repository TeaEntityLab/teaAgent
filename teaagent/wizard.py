from __future__ import annotations

import json
import logging
import os
import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from teaagent.llm import available_providers
from teaagent.llm._config import PROVIDER_CONFIGS
from teaagent.policy import PermissionMode

logger = logging.getLogger(__name__)

_SECRET_KEY_FRAGMENTS = (
    'api_key',
    'api-key',
    'auth_token',
    'secret',
    'password',
    'credential',
)
_SECRET_VALUE_MARKERS = ('sk-', 'Bearer ')
_REDACTED = '[redacted]'


@dataclass
class WizardResult:
    ok: bool
    mode: str
    root: str
    checks: dict[str, Any] = field(default_factory=dict)
    configured: dict[str, Any] = field(default_factory=dict)
    files_written: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)
    safe_command: str = ''
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            'ok': self.ok,
            'mode': self.mode,
            'root': self.root,
            'checks': self.checks,
            'configured': self.configured,
            'files_written': self.files_written,
            'warnings': self.warnings,
            'next_steps': self.next_steps,
            'safe_command': self.safe_command,
        }
        payload.update(self.extra)
        return redact_wizard_payload(payload)


def redact_wizard_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a JSON-safe wizard payload with secrets removed."""

    def _walk(value: Any, key: str = '') -> Any:
        if isinstance(value, dict):
            return {k: _walk(v, k) for k, v in value.items()}
        if isinstance(value, list):
            return [_walk(item, key) for item in value]
        if isinstance(value, str):
            lowered = key.lower()
            if any(fragment in lowered for fragment in _SECRET_KEY_FRAGMENTS):
                return _REDACTED if value else value
            if value.lower().startswith('bearer '):
                return 'Bearer [redacted]'
            if any(marker in value for marker in _SECRET_VALUE_MARKERS):
                redacted = value
                if 'Bearer ' in redacted:
                    redacted = redacted.replace('Bearer ', 'Bearer [redacted] ', 1)
                for marker in ('sk-',):
                    if marker in redacted:
                        start = redacted.index(marker)
                        end = start + 3
                        while end < len(redacted) and redacted[end] not in ' \t\n"\')':
                            end += 1
                        redacted = redacted[:start] + _REDACTED + redacted[end:]
                return redacted
            if 'export ' in value and '=' in value:
                name, _, _rest = value.partition('=')
                return f'{name}={_REDACTED}'
        return value

    redacted = _walk(payload)
    text = json.dumps(redacted, ensure_ascii=False)
    for secret_marker in ('sk-', 'Bearer '):
        if secret_marker in text and _REDACTED not in text:
            return json.loads(
                json.dumps(payload, ensure_ascii=False).replace(
                    secret_marker, _REDACTED
                )
            )
    return redacted if isinstance(redacted, dict) else payload


def provider_env_var(provider: str) -> str:
    config = PROVIDER_CONFIGS.get(provider)
    return config.api_key_env if config else ''


def read_existing_exports(env_file: Path) -> dict[str, str]:
    if not env_file.is_file():
        return {}
    exports: dict[str, str] = {}
    for raw_line in env_file.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line.startswith('export '):
            continue
        assignment = line[len('export ') :]
        key, sep, value = assignment.partition('=')
        if not sep:
            continue
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        try:
            exports[key] = shlex.split(value)[0] if value else ''
        except ValueError:
            exports[key] = value.strip('"\'')
    return exports


def merge_env_exports(env_file: Path, updates: dict[str, str], header: str) -> None:
    env_file.parent.mkdir(parents=True, exist_ok=True)
    existing = read_existing_exports(env_file)
    merged = {**existing, **{k: v for k, v in updates.items() if v}}
    lines = [header]
    for key in sorted(merged.keys()):
        lines.append(f'export {key}={shlex.quote(merged[key])}')
    env_file.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def read_keychain_secret(env_var: str) -> str:
    service = f'teaagent/{env_var}'
    try:
        proc = subprocess.run(
            [
                'security',
                'find-generic-password',
                '-a',
                os.environ.get('USER', ''),
                '-s',
                service,
                '-w',
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        logger.debug('Keychain lookup failed')
        return ''
    if proc.returncode != 0:
        return ''
    return proc.stdout.strip()


def resolve_api_key(
    provider: str,
    *,
    api_key: Optional[str] = None,
    prompt: bool = True,
    getpass_fn: Callable[[str], str] = __import__('getpass').getpass,
) -> tuple[str, str]:
    env_name = provider_env_var(provider)
    if api_key:
        if env_name:
            os.environ[env_name] = api_key
        return api_key, 'flag'
    if env_name and os.environ.get(env_name, '').strip():
        return os.environ[env_name].strip(), 'env'
    keychain = read_keychain_secret(env_name) if env_name else ''
    if keychain:
        os.environ[env_name] = keychain
        return keychain, 'keychain'
    if not prompt:
        return '', 'missing'
    entered = getpass_fn(f'Enter {env_name} (hidden, empty to skip): ').strip()
    if entered and env_name:
        os.environ[env_name] = entered
        return entered, 'prompt'
    return '', 'missing'


def write_workspace_config(
    root: Path,
    *,
    provider: str,
    permission_mode: str,
    max_iterations: int,
    max_tool_calls: int,
    context_profile: str,
    heartbeat: float,
    daily_cost_cap_cents: int,
) -> tuple[Path, Path]:
    tea_dir = root / '.teaagent'
    tea_dir.mkdir(parents=True, exist_ok=True)
    config = {
        'provider': provider,
        'permission_mode': permission_mode,
        'max_iterations': int(max_iterations),
        'max_tool_calls': int(max_tool_calls),
        'context_profile': context_profile,
        'heartbeat': float(heartbeat),
        'daily_cost_cap_cents': int(daily_cost_cap_cents),
        'auto_compact_on_resume': True,
    }
    cfg_path = tea_dir / 'config.json'
    cfg_path.write_text(json.dumps(config, sort_keys=True, indent=2), encoding='utf-8')
    toml_path = tea_dir / 'config.toml'
    toml_path.write_text(
        '\n'.join(
            [
                f'provider = "{provider}"',
                f'permission_mode = "{permission_mode}"',
                f'max_iterations = {int(max_iterations)}',
                f'max_tool_calls = {int(max_tool_calls)}',
                f'context_profile = "{context_profile}"',
                f'heartbeat = {config["heartbeat"]}',
                f'daily_cost_cap_cents = {config["daily_cost_cap_cents"]}',
                'auto_compact_on_resume = true',
                '',
            ]
        ),
        encoding='utf-8',
    )
    return cfg_path, toml_path


def ensure_agents_md(root: Path) -> tuple[Path, str]:
    agents_md_path = root / 'AGENTS.md'
    if agents_md_path.exists():
        return agents_md_path, 'existing'
    agents_md_path.write_text(
        (
            '# TeaAgent Project Instructions\n\n'
            '- Keep edits minimal, reviewable, and reversible.\n'
            '- Prefer tests-first for behavior changes.\n'
            '- Verify with focused tests before finalizing.\n'
        ),
        encoding='utf-8',
    )
    return agents_md_path, 'created'


def build_env_order_checks(root: Path) -> dict[str, Any]:
    home = Path.home()
    global_new = home / '.teaagent' / 'providers_env.zsh'
    global_legacy = home / '.teaagent' / 'provider_keys.zsh'
    project_env = root / '.teaagent' / 'env'
    return {
        'global_providers_env': {
            'path': str(global_new),
            'exists': global_new.is_file(),
        },
        'global_provider_keys': {
            'path': str(global_legacy),
            'exists': global_legacy.is_file(),
        },
        'project_env': {'path': str(project_env), 'exists': project_env.is_file()},
    }


def verify_setup(
    root: str | Path, *, check_llm: Callable[[str], tuple[bool, str]]
) -> WizardResult:
    """Verify an existing workspace setup without modifying files."""
    root_path = Path(root).resolve()
    cfg_path = root_path / '.teaagent' / 'config.json'
    warnings: list[str] = []
    if not cfg_path.is_file():
        return WizardResult(
            ok=False,
            mode='verify',
            root=str(root_path),
            warnings=['missing .teaagent/config.json — run teaagent setup'],
            next_steps=['teaagent setup --root .'],
            safe_command='teaagent setup',
        )

    import json

    cfg = json.loads(cfg_path.read_text(encoding='utf-8'))
    provider = str(cfg.get('provider') or 'gpt')
    provider_ok, provider_message = check_llm(provider)
    env_order = build_env_order_checks(root_path)
    if not provider_ok:
        warnings.append(provider_message)

    return WizardResult(
        ok=provider_ok,
        mode='verify',
        root=str(root_path),
        checks={
            'provider': {'ok': provider_ok, 'message': provider_message},
            'env_order': env_order,
        },
        configured={'provider': provider, 'config_path': str(cfg_path)},
        warnings=warnings,
        next_steps=['teaagent health --root .']
        if provider_ok
        else [f'teaagent doctor model {provider}'],
        safe_command=f'teaagent daily "summarize repo" --dry-run --root {shlex.quote(str(root_path))}',
    )


def run_first_session_setup(
    args: Any,
    *,
    check_llm: Callable[[str], tuple[bool, str]],
    input_fn: Callable[[str], str] = input,
    getpass_fn: Callable[[str], str] = __import__('getpass').getpass,
) -> WizardResult:
    root = Path(args.root).resolve()
    mode = 'setup'
    files_written: list[str] = []
    warnings: list[str] = []

    provider = getattr(args, 'provider', None)
    if not provider:
        choices = ', '.join(available_providers())
        provider = input_fn(f'Select provider ({choices}) [gpt]: ').strip() or 'gpt'
    if provider not in available_providers():
        return WizardResult(
            ok=False,
            mode=mode,
            root=str(root),
            warnings=[f'unknown provider: {provider}'],
            next_steps=['teaagent setup --provider gpt'],
            safe_command='teaagent setup --provider gpt --permission-mode read-only',
        )

    permission_mode = getattr(args, 'permission_mode', PermissionMode.PROMPT.value)
    non_interactive = bool(
        getattr(args, 'provider', None) and getattr(args, 'api_key', None)
    )
    api_key, token_source = resolve_api_key(
        provider,
        api_key=getattr(args, 'api_key', None),
        prompt=not non_interactive,
        getpass_fn=getpass_fn,
    )
    env_var = provider_env_var(provider)

    cfg_path, toml_path = write_workspace_config(
        root,
        provider=provider,
        permission_mode=permission_mode,
        max_iterations=int(getattr(args, 'max_iterations', 10)),
        max_tool_calls=int(getattr(args, 'max_tool_calls', 10)),
        context_profile=getattr(args, 'context_profile', 'balanced'),
        heartbeat=float(getattr(args, 'heartbeat', 0.0)),
        daily_cost_cap_cents=int(getattr(args, 'daily_cost_cap_cents', 0)),
    )
    files_written.extend([str(cfg_path), str(toml_path)])

    agents_path, agents_status = ensure_agents_md(root)
    if agents_status == 'created':
        files_written.append(str(agents_path))

    env_status = 'skipped'
    if getattr(args, 'write_env', False) and env_var and api_key:
        env_path = root / '.teaagent' / 'env'
        merge_env_exports(
            env_path,
            {env_var: api_key},
            '# Updated by `teaagent setup`.',
        )
        files_written.append(str(env_path))
        env_status = 'written'
    elif getattr(args, 'write_env', False) and not api_key:
        warnings.append(f'missing API key for {env_var}; env file not written')
        env_status = 'skipped (missing key)'

    provider_ok, provider_message = check_llm(provider)
    env_order = build_env_order_checks(root)
    tools_count = 0
    try:
        from teaagent.workspace_tools import build_workspace_tool_registry

        tools_count = len(build_workspace_tool_registry(root).mcp_metadata())
    except (ImportError, ValueError, TypeError, OSError) as exc:
        logger.warning('Failed to load workspace tools metadata: %s', exc)
        warnings.append(f'workspace tools metadata: {exc}')

    daily_dry_run: dict[str, Any] = {'ok': False}
    if provider_ok or api_key:
        try:
            from teaagent.ergonomics.dry_run import build_dry_run_payload
            from teaagent.policy import parse_permission_mode

            brief = build_dry_run_payload(
                task='readiness',
                root=root,
                provider=provider,
                model=getattr(args, 'model', None),
                permission_mode=parse_permission_mode(permission_mode),
            )
            daily_dry_run = {
                'ok': True,
                'usage_level': brief.get('token_budget', {}).get('usage_level'),
            }
        except (ImportError, ValueError, TypeError, OSError) as exc:
            logger.warning('Daily dry-run planning failed: %s', exc)
            daily_dry_run = {'ok': False, 'error': str(exc)}
            warnings.append(f'daily dry-run planning failed: {exc}')

    safe_command = f'teaagent daily "summarize this repo" --dry-run --root {shlex.quote(str(root))}'
    next_steps = [
        safe_command,
        'teaagent recipes run review-staged --print-only',
        f'teaagent doctor mcp --wizard --root {shlex.quote(str(root))}',
        f'teaagent model capabilities --per-model --provider {provider}',
    ]
    if not provider_ok:
        next_steps.insert(0, f'teaagent doctor model {provider}')
        warnings.append(provider_message)

    return WizardResult(
        ok=provider_ok or bool(api_key),
        mode=mode,
        root=str(root),
        checks={
            'provider': {'ok': provider_ok, 'message': provider_message},
            'env_order': env_order,
            'workspace_tools': {'ok': tools_count > 0, 'tool_count': tools_count},
            'daily_dry_run': daily_dry_run,
        },
        configured={
            'provider': provider,
            'permission_mode': permission_mode,
            'api_key_env': env_var or None,
            'api_key_present': bool(api_key),
            'token_source': token_source,
            'env_status': env_status,
            'agents_md_status': agents_status,
        },
        files_written=files_written,
        warnings=warnings,
        next_steps=next_steps,
        safe_command=safe_command,
        extra={'provider': provider},
    )

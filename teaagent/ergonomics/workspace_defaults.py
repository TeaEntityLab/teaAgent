from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - py3.10
    try:
        import tomli as tomllib  # type: ignore[no-redef, unused-ignore]
    except ModuleNotFoundError:
        tomllib = None  # type: ignore[assignment,misc]

DEFAULT_KEYS = {
    'provider': None,
    'model': None,
    'permission_mode': 'prompt',
    'max_iterations': 10,
    'max_tool_calls': 10,
    'context_profile': 'balanced',
    'heartbeat': 0.0,
    'daily_cost_cap_cents': 0,
    'auto_compact_on_resume': True,
    'root': '.',
}


def _parse_flat_toml(text: str) -> dict[str, Any]:
    """Parse flat ``key = value`` TOML used by ``.teaagent/config.toml`` (py3.10 fallback)."""
    result: dict[str, Any] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        if '=' not in stripped:
            continue
        key, _, raw = stripped.partition('=')
        key = key.strip()
        raw = raw.strip()
        if (raw.startswith('"') and raw.endswith('"')) or (
            raw.startswith("'") and raw.endswith("'")
        ):
            result[key] = raw[1:-1]
        elif raw == 'true':
            result[key] = True
        elif raw == 'false':
            result[key] = False
        else:
            try:
                result[key] = int(raw) if '.' not in raw else float(raw)
            except ValueError:
                result[key] = raw
    return result


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding='utf-8')
    except OSError:
        return {}
    if tomllib is not None:
        try:
            data = tomllib.loads(text)
        except ValueError:
            return {}
        return data if isinstance(data, dict) else {}
    return _parse_flat_toml(text)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def load_workspace_defaults(root: str | Path = '.') -> dict[str, Any]:
    """Merge ``.teaagent/config.toml`` then ``config.json`` with env overrides."""
    root_path = Path(root).resolve()
    tea_dir = root_path / '.teaagent'
    merged = dict(DEFAULT_KEYS)
    toml_path = tea_dir / 'config.toml'
    json_path = tea_dir / 'config.json'
    if toml_path.is_file():
        merged.update(_read_toml(toml_path))
    if json_path.is_file():
        merged.update(_read_json(json_path))
    env_map = {
        'provider': 'TEAAGENT_PROVIDER',
        'model': 'TEAAGENT_MODEL',
        'permission_mode': 'TEAAGENT_PERMISSION_MODE',
        'context_profile': 'TEAAGENT_CONTEXT_PROFILE',
    }
    for key, env_name in env_map.items():
        if os.environ.get(env_name):
            merged[key] = os.environ[env_name]
    if os.environ.get('TEAAGENT_HEARTBEAT'):
        merged['heartbeat'] = float(os.environ['TEAAGENT_HEARTBEAT'])
    if os.environ.get('TEAAGENT_DAILY_COST_CAP_CENTS'):
        merged['daily_cost_cap_cents'] = int(
            os.environ['TEAAGENT_DAILY_COST_CAP_CENTS']
        )
    if os.environ.get('TEAAGENT_AUTOMATION_WEBHOOK_URL'):
        merged['automation_webhook_url'] = os.environ['TEAAGENT_AUTOMATION_WEBHOOK_URL']
    if os.environ.get('TEAAGENT_AUTOMATION_WEBHOOK_SECRET'):
        merged['automation_webhook_secret'] = os.environ[
            'TEAAGENT_AUTOMATION_WEBHOOK_SECRET'
        ]
    return merged


def apply_workspace_defaults_to_namespace(
    args: Any, *, root: str | Path = '.', require_provider: bool = False
) -> None:
    defaults = load_workspace_defaults(root)
    if require_provider and not getattr(args, 'provider', None):
        provider = defaults.get('provider')
        if not provider:
            raise SystemExit(
                'provider required: run `teaagent setup` or pass provider on the command line'
            )
        args.provider = provider
    for key, value in defaults.items():
        if value is None:
            continue
        if not hasattr(args, key):
            continue
        current = getattr(args, key, None)
        if current in (None, '', 0, 0.0, DEFAULT_KEYS.get(key)):
            setattr(args, key, value)

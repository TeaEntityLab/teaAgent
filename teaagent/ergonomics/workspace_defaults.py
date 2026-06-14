from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

try:
    import tomllib

    TOMLLIB_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover - py3.10
    try:
        import tomli as _tomli

        tomllib = _tomli
        TOMLLIB_AVAILABLE = True
    except ModuleNotFoundError:
        tomllib = None
        TOMLLIB_AVAILABLE = False

# Sentinel value to detect when an argument was not explicitly set by the user
_UNSET = object()

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
    'git_sandbox_consent': 'prompt',
    'fallback_provider': None,
    'fallback_model': None,
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


def _load_env_file(root: str | Path) -> None:
    """Load ``.teaagent/env`` into ``os.environ`` without overwriting existing vars.

    This makes API keys written by ``teaagent setup --write-env`` available
    to the LLM adapter layer without requiring the user to manually
    ``source .teaagent/env`` in their shell.
    """
    env_path = Path(root).resolve() / '.teaagent' / 'env'
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line.startswith('export '):
            continue
        assignment = line[len('export ') :]
        key, sep, raw_value = assignment.partition('=')
        if not sep:
            continue
        key = key.strip()
        if not key or key in os.environ:
            continue
        value = raw_value.strip()
        # shlex.quote() wraps in single quotes; unstrip them
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        if value:
            os.environ[key] = value


# Env var that overrides each config key (the env layer of precedence).
_ENV_MAP = {
    'provider': 'TEAAGENT_PROVIDER',
    'model': 'TEAAGENT_MODEL',
    'permission_mode': 'TEAAGENT_PERMISSION_MODE',
    'context_profile': 'TEAAGENT_CONTEXT_PROFILE',
}
# Env-only keys with no default/config layer, plus their value coercion.
_ENV_ONLY: dict[str, tuple[str, Any]] = {
    'heartbeat': ('TEAAGENT_HEARTBEAT', float),
    'daily_cost_cap_cents': ('TEAAGENT_DAILY_COST_CAP_CENTS', int),
    'automation_webhook_url': ('TEAAGENT_AUTOMATION_WEBHOOK_URL', str),
    'automation_webhook_secret': ('TEAAGENT_AUTOMATION_WEBHOOK_SECRET', str),
}


def resolve_config_provenance(root: str | Path = '.') -> dict[str, dict[str, Any]]:
    """Resolve effective workspace config with the source of each key's value.

    Walks the precedence layers in order — ``default`` -> ``config:config.toml``
    -> ``config:config.json`` -> ``env:VAR`` — recording which layer last set
    each key. The CLI layer sits above these (the run namespace, via the
    ``_UNSET`` sentinel in :func:`apply_workspace_defaults_to_namespace`); it is
    not observable here because ``doctor`` is not the agent run, so callers that
    have a run namespace should overlay it themselves.

    Returns ``{key: {'value': ..., 'source': ...}}``. This is the single source
    of truth for the layering; :func:`load_workspace_defaults` is derived from it
    so the two cannot drift.
    """
    root_path = Path(root).resolve()
    tea_dir = root_path / '.teaagent'
    _load_env_file(root_path)

    prov: dict[str, dict[str, Any]] = {
        key: {'value': value, 'source': 'default'}
        for key, value in DEFAULT_KEYS.items()
    }

    for fname, reader in (('config.toml', _read_toml), ('config.json', _read_json)):
        path = tea_dir / fname
        if path.is_file():
            for key, value in reader(path).items():
                prov[key] = {'value': value, 'source': f'config:{fname}'}

    for key, env_name in _ENV_MAP.items():
        if os.environ.get(env_name):
            prov[key] = {'value': os.environ[env_name], 'source': f'env:{env_name}'}

    for key, (env_name, coerce) in _ENV_ONLY.items():
        raw = os.environ.get(env_name)
        if raw:
            prov[key] = {'value': coerce(raw), 'source': f'env:{env_name}'}

    return prov


def load_workspace_defaults(root: str | Path = '.') -> dict[str, Any]:
    """Merge ``.teaagent/config.toml`` then ``config.json`` with env overrides.

    Derived from :func:`resolve_config_provenance` so the layering logic has a
    single source of truth.
    """
    return {
        key: entry['value'] for key, entry in resolve_config_provenance(root).items()
    }


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
        if current is _UNSET:
            # Flag not given on the CLI — config may fill it.
            setattr(args, key, value)
        elif key == 'permission_mode':
            # A concrete mode is an explicit user choice; config never
            # overrides it (V8: neither demotion nor escalation).
            continue
        elif current in (None, '', 0, 0.0, DEFAULT_KEYS.get(key)):
            setattr(args, key, value)

    # If neither CLI nor config produced a mode, fall back to the default
    # so the sentinel never leaks into downstream parsing.
    if getattr(args, 'permission_mode', None) is _UNSET:
        args.permission_mode = DEFAULT_KEYS['permission_mode']

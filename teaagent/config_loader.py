"""Config layering with explicit source attribution.

Resolution order (highest precedence first):

1. **Environment variables** — ``TEAAGENT_<KEY>`` (upper-cased key).
2. **Workspace config** — ``<root>/.teaagent/config.json``.
3. **User config** — ``~/.teaagent/config.json``.
4. **Defaults** — hard-coded fallbacks.

Usage::

    from teaagent.config_loader import ConfigResolver

    rc = ConfigResolver(workspace_root=Path('.')).resolve()
    print(rc.get('permission_mode'))       # resolved value
    print(rc.source('permission_mode'))    # ConfigLayer.WORKSPACE
    for line in rc.show():
        print(line)
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class ConfigLayer(str, Enum):
    DEFAULT = 'default'
    USER = 'user'
    WORKSPACE = 'workspace'
    ENV = 'env'


# Canonical config keys with their env-var name and default value.
CONFIG_KEYS: dict[str, dict[str, Any]] = {
    'permission_mode': {
        'env': 'TEAAGENT_PERMISSION_MODE',
        'default': 'prompt',
        'type': str,
    },
    'max_iterations': {
        'env': 'TEAAGENT_MAX_ITERATIONS',
        'default': 10,
        'type': int,
    },
    'max_tool_calls': {
        'env': 'TEAAGENT_MAX_TOOL_CALLS',
        'default': 10,
        'type': int,
    },
    'model': {
        'env': 'TEAAGENT_MODEL',
        'default': None,
        'type': str,
    },
    'provider': {
        'env': 'TEAAGENT_PROVIDER',
        'default': None,
        'type': str,
    },
}


@dataclass(frozen=True)
class ResolvedConfig:
    """Merged configuration values with per-key source annotation."""

    values: dict[str, Any]
    sources: dict[str, ConfigLayer]

    def get(self, key: str, *, default: Any = None) -> Any:
        return self.values.get(key, default)

    def source(self, key: str) -> Optional[ConfigLayer]:
        return self.sources.get(key)

    def show(self) -> list[str]:
        """Return human-readable lines like ``permission_mode = prompt  [workspace]``."""
        lines = []
        for key in sorted(self.values):
            val = self.values[key]
            src = self.sources.get(key, ConfigLayer.DEFAULT)
            lines.append(f'{key} = {val!r}  [{src.value}]')
        return lines


def _coerce(value: Any, typ: type) -> Any:
    if value is None:
        return None
    if typ is int:
        return int(value)
    if typ is float:
        return float(value)
    if typ is bool:
        if isinstance(value, str):
            return value.lower() in {'1', 'true', 'yes'}
        return bool(value)
    return value


def _read_json_config(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return {}


def load_workspace_config(root: str | Path) -> dict[str, Any]:
    """Read ``<root>/.teaagent/config.json`` and return its contents."""
    path = Path(root).resolve() / '.teaagent' / 'config.json'
    if not path.is_file():
        return {}
    return _read_json_config(path)


class ConfigResolver:
    """Resolves configuration by merging all layers in precedence order.

    Parameters
    ----------
    workspace_root:
        Project root directory.  The resolver looks for
        ``<workspace_root>/.teaagent/config.json``.
    user_home:
        Override for the home directory (default: ``Path.home()``).  Used
        for ``<user_home>/.teaagent/config.json``.
    """

    def __init__(
        self,
        workspace_root: str | Path = '.',
        user_home: Optional[str | Path] = None,
    ) -> None:
        self._workspace = Path(workspace_root).resolve()
        self._user_home = Path(user_home).resolve() if user_home else Path.home()

    def resolve(self) -> ResolvedConfig:
        values: dict[str, Any] = {}
        sources: dict[str, ConfigLayer] = {}

        user_cfg = _read_json_config(self._user_home / '.teaagent' / 'config.json')
        workspace_cfg = _read_json_config(self._workspace / '.teaagent' / 'config.json')

        for key, meta in CONFIG_KEYS.items():
            typ = meta['type']
            default = meta['default']

            # 1. Default
            resolved: Any = default
            layer = ConfigLayer.DEFAULT

            # 2. User config
            if key in user_cfg:
                resolved = _coerce(user_cfg[key], typ)
                layer = ConfigLayer.USER

            # 3. Workspace config
            if key in workspace_cfg:
                resolved = _coerce(workspace_cfg[key], typ)
                layer = ConfigLayer.WORKSPACE

            # 4. Environment variable
            env_key = meta['env']
            env_val = os.environ.get(env_key)
            if env_val is not None:
                resolved = _coerce(env_val, typ)
                layer = ConfigLayer.ENV

            if resolved is not None:
                values[key] = resolved
                sources[key] = layer

        return ResolvedConfig(values=values, sources=sources)

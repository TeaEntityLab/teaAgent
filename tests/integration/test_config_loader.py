"""IT: Config layering and workspace profile.

ConfigResolver merges values across layers (env > workspace > user > defaults)
and annotates each key with its source.  ChatAgentConfig.from_root() applies
workspace profile when .teaagent/config.json is present.
"""

from __future__ import annotations

import json
import os
from unittest.mock import patch

from teaagent.config_loader import (
    CONFIG_KEYS,
    ConfigLayer,
    ConfigResolver,
    ResolvedConfig,
    load_workspace_config,
)

# ---------------------------------------------------------------------------
# ResolvedConfig
# ---------------------------------------------------------------------------


def test_resolved_config_get_returns_value():
    rc = ResolvedConfig(
        values={'permission_mode': 'workspace-write'},
        sources={'permission_mode': ConfigLayer.WORKSPACE},
    )
    assert rc.get('permission_mode') == 'workspace-write'
    assert rc.source('permission_mode') == ConfigLayer.WORKSPACE


def test_resolved_config_get_default():
    rc = ResolvedConfig(values={}, sources={})
    assert rc.get('permission_mode', default='prompt') == 'prompt'


def test_resolved_config_show_format():
    rc = ResolvedConfig(
        values={'permission_mode': 'allow', 'max_iterations': 20},
        sources={
            'permission_mode': ConfigLayer.ENV,
            'max_iterations': ConfigLayer.WORKSPACE,
        },
    )
    lines = rc.show()
    assert any('permission_mode' in line and 'env' in line.lower() for line in lines)
    assert any(
        'max_iterations' in line and 'workspace' in line.lower() for line in lines
    )


# ---------------------------------------------------------------------------
# ConfigResolver layer precedence
# ---------------------------------------------------------------------------


def test_defaults_used_when_no_files(tmp_path):
    with patch.dict(os.environ, {}, clear=False):
        rc = ConfigResolver(workspace_root=tmp_path, user_home=tmp_path).resolve()
    # Config resolver returns a ResolvedConfig; no error
    assert isinstance(rc, ResolvedConfig)


def test_workspace_config_loaded(tmp_path):
    cfg_dir = tmp_path / '.teaagent'
    cfg_dir.mkdir()
    (cfg_dir / 'config.json').write_text(
        json.dumps({'permission_mode': 'workspace-write', 'max_iterations': 15}),
        encoding='utf-8',
    )
    rc = ConfigResolver(workspace_root=tmp_path, user_home=tmp_path).resolve()
    assert rc.get('permission_mode') == 'workspace-write'
    assert rc.get('max_iterations') == 15
    assert rc.source('permission_mode') == ConfigLayer.WORKSPACE


def test_user_config_loaded(tmp_path):
    user_home = tmp_path / 'home'
    user_home.mkdir()
    user_dir = user_home / '.teaagent'
    user_dir.mkdir()
    (user_dir / 'config.json').write_text(
        json.dumps({'max_tool_calls': 30}), encoding='utf-8'
    )
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    rc = ConfigResolver(workspace_root=workspace, user_home=user_home).resolve()
    assert rc.get('max_tool_calls') == 30
    assert rc.source('max_tool_calls') == ConfigLayer.USER


def test_workspace_overrides_user(tmp_path):
    user_home = tmp_path / 'home'
    user_home.mkdir()
    (user_home / '.teaagent').mkdir()
    (user_home / '.teaagent' / 'config.json').write_text(
        json.dumps({'max_iterations': 5}), encoding='utf-8'
    )
    workspace = tmp_path / 'ws'
    workspace.mkdir()
    (workspace / '.teaagent').mkdir()
    (workspace / '.teaagent' / 'config.json').write_text(
        json.dumps({'max_iterations': 25}), encoding='utf-8'
    )
    rc = ConfigResolver(workspace_root=workspace, user_home=user_home).resolve()
    assert rc.get('max_iterations') == 25
    assert rc.source('max_iterations') == ConfigLayer.WORKSPACE


def test_env_overrides_workspace(tmp_path):
    cfg_dir = tmp_path / '.teaagent'
    cfg_dir.mkdir()
    (cfg_dir / 'config.json').write_text(
        json.dumps({'permission_mode': 'read-only'}), encoding='utf-8'
    )
    with patch.dict(os.environ, {'TEAAGENT_PERMISSION_MODE': 'allow'}):
        rc = ConfigResolver(workspace_root=tmp_path, user_home=tmp_path).resolve()
    assert rc.get('permission_mode') == 'allow'
    assert rc.source('permission_mode') == ConfigLayer.ENV


def test_env_max_iterations(tmp_path):
    with patch.dict(os.environ, {'TEAAGENT_MAX_ITERATIONS': '42'}):
        rc = ConfigResolver(workspace_root=tmp_path, user_home=tmp_path).resolve()
    assert rc.get('max_iterations') == 42
    assert rc.source('max_iterations') == ConfigLayer.ENV


# ---------------------------------------------------------------------------
# load_workspace_config helper
# ---------------------------------------------------------------------------


def test_load_workspace_config_returns_dict(tmp_path):
    cfg_dir = tmp_path / '.teaagent'
    cfg_dir.mkdir()
    (cfg_dir / 'config.json').write_text(
        json.dumps({'permission_mode': 'prompt', 'model': 'gpt-4o'}),
        encoding='utf-8',
    )
    data = load_workspace_config(tmp_path)
    assert data['permission_mode'] == 'prompt'
    assert data['model'] == 'gpt-4o'


def test_load_workspace_config_empty_when_missing(tmp_path):
    data = load_workspace_config(tmp_path)
    assert data == {}


# ---------------------------------------------------------------------------
# Workspace profile applied to ChatAgentConfig
# ---------------------------------------------------------------------------


def test_chat_agent_config_from_root_applies_profile(tmp_path):
    from teaagent.chat_agent import ChatAgentConfig
    from teaagent.policy import PermissionMode

    cfg_dir = tmp_path / '.teaagent'
    cfg_dir.mkdir()
    (cfg_dir / 'config.json').write_text(
        json.dumps({'permission_mode': 'workspace-write', 'max_iterations': 7}),
        encoding='utf-8',
    )
    config = ChatAgentConfig.from_root(tmp_path)
    assert config.permission_mode == PermissionMode.WORKSPACE_WRITE
    assert config.max_iterations == 7


def test_chat_agent_config_from_root_defaults_when_no_profile(tmp_path):
    from teaagent.chat_agent import ChatAgentConfig
    from teaagent.policy import PermissionMode

    config = ChatAgentConfig.from_root(tmp_path)
    assert config.permission_mode == PermissionMode.PROMPT  # default
    assert config.max_iterations == 10  # default


def test_chat_agent_config_kwargs_override_profile(tmp_path):
    """Explicit kwargs to from_root() beat the workspace profile."""
    from teaagent.chat_agent import ChatAgentConfig
    from teaagent.policy import PermissionMode

    cfg_dir = tmp_path / '.teaagent'
    cfg_dir.mkdir()
    (cfg_dir / 'config.json').write_text(
        json.dumps({'permission_mode': 'read-only'}), encoding='utf-8'
    )
    config = ChatAgentConfig.from_root(tmp_path, permission_mode=PermissionMode.ALLOW)
    assert config.permission_mode == PermissionMode.ALLOW


# ---------------------------------------------------------------------------
# CONFIG_KEYS registry
# ---------------------------------------------------------------------------


def test_config_keys_includes_known_keys():
    assert 'permission_mode' in CONFIG_KEYS
    assert 'max_iterations' in CONFIG_KEYS
    assert 'max_tool_calls' in CONFIG_KEYS
    assert 'model' in CONFIG_KEYS

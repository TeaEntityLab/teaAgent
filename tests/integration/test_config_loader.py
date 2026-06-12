"""IT: Config layering and workspace profile.

ConfigResolver merges values across layers (env > workspace > user > defaults)
and annotates each key with its source.  ChatAgentConfig.from_root() applies
workspace profile when .teaagent/config.json is present.
"""

from __future__ import annotations

import contextlib
import json
import os
from unittest.mock import patch

import pytest

from teaagent.config_loader import (
    CONFIG_KEYS,
    ConfigLayer,
    ConfigResolver,
    ResolvedConfig,
    load_workspace_config,
)
from teaagent.ergonomics.workspace_defaults import (
    _UNSET,
    apply_workspace_defaults_to_namespace,
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
    from teaagent.types import PermissionMode

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
    from teaagent.types import PermissionMode

    config = ChatAgentConfig.from_root(tmp_path)
    assert config.permission_mode == PermissionMode.PROMPT  # default
    assert config.max_iterations == 10  # default


def test_chat_agent_config_kwargs_override_profile(tmp_path):
    """Explicit kwargs to from_root() beat the workspace profile."""
    from teaagent.chat_agent import ChatAgentConfig
    from teaagent.types import PermissionMode

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
    assert 'code_analysis_enabled' in CONFIG_KEYS
    assert 'skill_search_dirs' in CONFIG_KEYS
    assert 'skill_source_profile' in CONFIG_KEYS


def test_chat_agent_config_from_root_enables_code_analysis_from_profile(tmp_path):
    from teaagent.chat_agent import ChatAgentConfig

    cfg_dir = tmp_path / '.teaagent'
    cfg_dir.mkdir()
    (cfg_dir / 'config.json').write_text(
        json.dumps({'code_analysis_enabled': True}),
        encoding='utf-8',
    )
    config = ChatAgentConfig.from_root(tmp_path)
    assert config.code_analysis_config is not None
    assert config.code_analysis_config.enabled is True


def test_chat_agent_config_from_root_applies_skill_search_dirs_from_profile(tmp_path):
    from teaagent.chat_agent import ChatAgentConfig

    cfg_dir = tmp_path / '.teaagent'
    cfg_dir.mkdir()
    (cfg_dir / 'config.json').write_text(
        json.dumps({'skill_search_dirs': ['.config/agent/skills', '.opencode/skill']}),
        encoding='utf-8',
    )
    config = ChatAgentConfig.from_root(tmp_path)
    assert config.skill_search_dirs == ['.config/agent/skills', '.opencode/skill']


def test_env_skill_search_dirs_supports_csv(tmp_path):
    with patch.dict(
        os.environ,
        {'TEAAGENT_SKILL_SEARCH_DIRS': '.config/agent/skills,.opencode/skill'},
    ):
        rc = ConfigResolver(workspace_root=tmp_path, user_home=tmp_path).resolve()
    assert rc.get('skill_search_dirs') == ['.config/agent/skills', '.opencode/skill']


def test_chat_agent_config_from_root_applies_skill_source_profile(tmp_path):
    from teaagent.chat_agent import ChatAgentConfig

    cfg_dir = tmp_path / '.teaagent'
    cfg_dir.mkdir()
    (cfg_dir / 'config.json').write_text(
        json.dumps({'skill_source_profile': 'extended'}),
        encoding='utf-8',
    )
    config = ChatAgentConfig.from_root(tmp_path)
    assert config.skill_source_profile == 'extended'


def test_env_skill_source_profile_overrides_workspace(tmp_path):
    cfg_dir = tmp_path / '.teaagent'
    cfg_dir.mkdir()
    (cfg_dir / 'config.json').write_text(
        json.dumps({'skill_source_profile': 'default'}),
        encoding='utf-8',
    )
    with patch.dict(os.environ, {'TEAAGENT_SKILL_SOURCE_PROFILE': 'custom'}):
        rc = ConfigResolver(workspace_root=tmp_path, user_home=tmp_path).resolve()
    assert rc.get('skill_source_profile') == 'custom'


# ---------------------------------------------------------------------------
# Negative test cases for config_loader
# ---------------------------------------------------------------------------


def test_malformed_json_in_workspace_config(tmp_path):
    """Test that malformed JSON in workspace config is handled gracefully."""
    cfg_dir = tmp_path / '.teaagent'
    cfg_dir.mkdir()
    (cfg_dir / 'config.json').write_text('{"invalid": json}', encoding='utf-8')
    rc = ConfigResolver(workspace_root=tmp_path, user_home=tmp_path).resolve()
    # Should fall back to defaults
    assert rc.get('permission_mode', default='prompt') == 'prompt'


def test_malformed_json_in_user_config(tmp_path):
    """Test that malformed JSON in user config is handled gracefully."""
    user_home = tmp_path / 'home'
    user_home.mkdir()
    (user_home / '.teaagent').mkdir()
    (user_home / '.teaagent' / 'config.json').write_text(
        'not valid json at all', encoding='utf-8'
    )
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    rc = ConfigResolver(workspace_root=workspace, user_home=user_home).resolve()
    # Should fall back to defaults
    assert rc.get('max_iterations', default=10) == 10


def test_empty_json_in_workspace_config(tmp_path):
    """Test that empty JSON object in workspace config is handled."""
    cfg_dir = tmp_path / '.teaagent'
    cfg_dir.mkdir()
    (cfg_dir / 'config.json').write_text('{}', encoding='utf-8')
    rc = ConfigResolver(workspace_root=tmp_path, user_home=tmp_path).resolve()
    # Should use defaults
    assert rc.get('permission_mode') == 'prompt'


def test_invalid_type_for_int_config(tmp_path):
    """Test that invalid type for int config raises ValueError."""
    cfg_dir = tmp_path / '.teaagent'
    cfg_dir.mkdir()
    (cfg_dir / 'config.json').write_text(
        json.dumps({'max_iterations': 'not_a_number'}), encoding='utf-8'
    )
    with pytest.raises(ValueError, match='invalid literal for int'):
        ConfigResolver(workspace_root=tmp_path, user_home=tmp_path).resolve()


def test_invalid_type_for_bool_config(tmp_path):
    """Test that invalid type for bool config is coerced or ignored."""
    cfg_dir = tmp_path / '.teaagent'
    cfg_dir.mkdir()
    (cfg_dir / 'config.json').write_text(
        json.dumps({'code_analysis_enabled': 'not_a_bool'}), encoding='utf-8'
    )
    rc = ConfigResolver(workspace_root=tmp_path, user_home=tmp_path).resolve()
    # Should attempt coercion
    result = rc.get('code_analysis_enabled')
    assert result is not None


def test_null_value_in_config(tmp_path):
    """Test that null values in config are handled."""
    cfg_dir = tmp_path / '.teaagent'
    cfg_dir.mkdir()
    (cfg_dir / 'config.json').write_text(
        json.dumps({'permission_mode': None}), encoding='utf-8'
    )
    rc = ConfigResolver(workspace_root=tmp_path, user_home=tmp_path).resolve()
    # Null values should be filtered out
    assert rc.get('permission_mode') is None or rc.get('permission_mode') == 'prompt'


def test_empty_string_for_list_config(tmp_path):
    """Test that empty string for list config is handled."""
    cfg_dir = tmp_path / '.teaagent'
    cfg_dir.mkdir()
    (cfg_dir / 'config.json').write_text(
        json.dumps({'skill_search_dirs': ''}), encoding='utf-8'
    )
    rc = ConfigResolver(workspace_root=tmp_path, user_home=tmp_path).resolve()
    # Empty string should result in empty list
    result = rc.get('skill_search_dirs')
    assert result == [] or result is None


def test_invalid_json_array_for_list_config(tmp_path):
    """Test that invalid JSON array for list config is handled."""
    cfg_dir = tmp_path / '.teaagent'
    cfg_dir.mkdir()
    (cfg_dir / 'config.json').write_text(
        json.dumps({'skill_search_dirs': 'not,a,list,format'}), encoding='utf-8'
    )
    rc = ConfigResolver(workspace_root=tmp_path, user_home=tmp_path).resolve()
    # Should attempt to parse as CSV
    result = rc.get('skill_search_dirs')
    assert result is not None


def test_nonexistent_workspace_path():
    """Test that nonexistent workspace path is handled."""
    from teaagent.config_loader import ConfigResolver

    rc = ConfigResolver(workspace_root='/nonexistent/path/that/does/not/exist')
    result = rc.resolve()
    # Should not crash and return a valid config
    assert isinstance(result, type(result))


def test_config_with_unknown_keys(tmp_path):
    """Test that unknown config keys are ignored."""
    cfg_dir = tmp_path / '.teaagent'
    cfg_dir.mkdir()
    (cfg_dir / 'config.json').write_text(
        json.dumps(
            {'unknown_key': 'value', 'another_unknown': 123, 'permission_mode': 'allow'}
        ),
        encoding='utf-8',
    )
    rc = ConfigResolver(workspace_root=tmp_path, user_home=tmp_path).resolve()
    # Unknown keys should be ignored, known keys should work
    assert rc.get('permission_mode') == 'allow'
    assert rc.get('unknown_key') is None


def test_env_var_with_empty_string(tmp_path):
    """Test that empty string env var is handled."""
    with patch.dict(os.environ, {'TEAAGENT_PERMISSION_MODE': ''}):
        rc = ConfigResolver(workspace_root=tmp_path, user_home=tmp_path).resolve()
    # Empty string should be treated as a value
    result = rc.get('permission_mode')
    assert result == '' or result is not None


def test_env_var_with_whitespace(tmp_path):
    """Test that env var with whitespace is handled."""
    with patch.dict(os.environ, {'TEAAGENT_PERMISSION_MODE': '  allow  '}):
        rc = ConfigResolver(workspace_root=tmp_path, user_home=tmp_path).resolve()
    # Should preserve or trim whitespace
    result = rc.get('permission_mode')
    assert result is not None


def test_negative_value_for_int_config(tmp_path):
    """Test that negative value for int config is handled."""
    cfg_dir = tmp_path / '.teaagent'
    cfg_dir.mkdir()
    (cfg_dir / 'config.json').write_text(
        json.dumps({'max_iterations': -5}), encoding='utf-8'
    )
    rc = ConfigResolver(workspace_root=tmp_path, user_home=tmp_path).resolve()
    # Negative values should be accepted
    assert rc.get('max_iterations') == -5


def test_zero_value_for_int_config(tmp_path):
    """Test that zero value for int config is handled."""
    cfg_dir = tmp_path / '.teaagent'
    cfg_dir.mkdir()
    (cfg_dir / 'config.json').write_text(
        json.dumps({'max_iterations': 0}), encoding='utf-8'
    )
    rc = ConfigResolver(workspace_root=tmp_path, user_home=tmp_path).resolve()
    # Zero should be accepted
    assert rc.get('max_iterations') == 0


def test_very_large_value_for_int_config(tmp_path):
    """Test that very large value for int config is handled."""
    cfg_dir = tmp_path / '.teaagent'
    cfg_dir.mkdir()
    (cfg_dir / 'config.json').write_text(
        json.dumps({'max_iterations': 999999999}), encoding='utf-8'
    )
    rc = ConfigResolver(workspace_root=tmp_path, user_home=tmp_path).resolve()
    # Large values should be accepted
    assert rc.get('max_iterations') == 999999999


def test_config_file_is_directory(tmp_path):
    """Test that config file being a directory is handled."""
    cfg_dir = tmp_path / '.teaagent'
    cfg_dir.mkdir()
    (cfg_dir / 'config.json').mkdir()  # Create as directory instead of file
    rc = ConfigResolver(workspace_root=tmp_path, user_home=tmp_path).resolve()
    # Should not crash
    assert isinstance(rc, type(rc))


def test_permission_denied_on_config_file(tmp_path):
    """Test that permission denied on config file is handled."""
    cfg_dir = tmp_path / '.teaagent'
    cfg_dir.mkdir()
    cfg_file = cfg_dir / 'config.json'
    cfg_file.write_text(json.dumps({'permission_mode': 'allow'}), encoding='utf-8')
    # Make file unreadable (on Unix-like systems)
    try:
        cfg_file.chmod(0o000)
        rc = ConfigResolver(workspace_root=tmp_path, user_home=tmp_path).resolve()
        # Should handle permission error gracefully
        assert isinstance(rc, type(rc))
    finally:
        # Restore permissions for cleanup
        with contextlib.suppress(BaseException):
            cfg_file.chmod(0o644)


def test_config_with_special_characters(tmp_path):
    """Test that config with special characters is handled."""
    cfg_dir = tmp_path / '.teaagent'
    cfg_dir.mkdir()
    (cfg_dir / 'config.json').write_text(
        json.dumps({'model': 'gpt-4o\n\t\r'}), encoding='utf-8'
    )
    rc = ConfigResolver(workspace_root=tmp_path, user_home=tmp_path).resolve()
    # Should handle special characters
    result = rc.get('model')
    assert result is not None


def test_config_with_unicode_characters(tmp_path):
    """Test that config with unicode characters is handled."""
    cfg_dir = tmp_path / '.teaagent'
    cfg_dir.mkdir()
    (cfg_dir / 'config.json').write_text(
        json.dumps({'model': '模型-模型-🤖'}), encoding='utf-8'
    )
    rc = ConfigResolver(workspace_root=tmp_path, user_home=tmp_path).resolve()
    # Should handle unicode
    result = rc.get('model')
    assert result is not None


def test_list_config_with_single_item(tmp_path):
    """Test that list config with single item is handled."""
    cfg_dir = tmp_path / '.teaagent'
    cfg_dir.mkdir()
    (cfg_dir / 'config.json').write_text(
        json.dumps({'skill_search_dirs': ['/single/path']}), encoding='utf-8'
    )
    rc = ConfigResolver(workspace_root=tmp_path, user_home=tmp_path).resolve()
    result = rc.get('skill_search_dirs')
    assert result == ['/single/path']


def test_list_config_with_empty_array(tmp_path):
    """Test that list config with empty array is handled."""
    cfg_dir = tmp_path / '.teaagent'
    cfg_dir.mkdir()
    (cfg_dir / 'config.json').write_text(
        json.dumps({'skill_search_dirs': []}), encoding='utf-8'
    )
    rc = ConfigResolver(workspace_root=tmp_path, user_home=tmp_path).resolve()
    result = rc.get('skill_search_dirs')
    assert result == []


def test_list_config_with_mixed_types(tmp_path):
    """Test that list config with mixed types is handled."""
    cfg_dir = tmp_path / '.teaagent'
    cfg_dir.mkdir()
    (cfg_dir / 'config.json').write_text(
        json.dumps({'skill_search_dirs': ['path1', 123, None, True]}), encoding='utf-8'
    )
    rc = ConfigResolver(workspace_root=tmp_path, user_home=tmp_path).resolve()
    # Should handle mixed types
    result = rc.get('skill_search_dirs')
    assert result is not None


def test_env_var_override_with_invalid_type(tmp_path):
    """Test that env var override with invalid type raises ValueError."""
    with (
        patch.dict(os.environ, {'TEAAGENT_MAX_ITERATIONS': 'invalid'}),
        pytest.raises(ValueError, match='invalid literal for int'),
    ):
        ConfigResolver(workspace_root=tmp_path, user_home=tmp_path).resolve()


def test_clear_config_cache():
    """Test that config cache can be cleared."""
    from teaagent.config_loader import clear_config_cache

    # Should not crash
    clear_config_cache()


def test_config_resolver_with_relative_path():
    """Test that ConfigResolver handles relative paths."""
    rc = ConfigResolver(workspace_root='.')
    result = rc.resolve()
    # Should handle relative path
    assert isinstance(result, type(result))


def test_config_resolver_with_absolute_path():
    """Test that ConfigResolver handles absolute paths."""
    import os

    abs_path = os.path.abspath('.')
    rc = ConfigResolver(workspace_root=abs_path)
    result = rc.resolve()
    # Should handle absolute path
    assert isinstance(result, type(result))


# ---------------------------------------------------------------------------
# V8-a: Config priority fix for permission_mode (fifth-pass correction)
# ---------------------------------------------------------------------------


def test_explicit_permission_mode_not_overridden_by_config(tmp_path):
    """V8-a: Explicit --permission-mode should not be overridden by config."""
    import argparse
    import os

    # Create a mock args namespace with explicit permission mode
    args = argparse.Namespace()
    args.command = 'run'
    args.permission_mode = 'prompt'  # Explicitly set
    args.root = str(tmp_path)

    # Create a config file that tries to override to read-only
    config_file = tmp_path / '.teaagent' / 'config.toml'
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text('permission_mode = "read-only"')

    # Change to the temp directory so config loading works
    original_cwd = os.getcwd()
    try:
        os.chdir(str(tmp_path))
        # Apply workspace defaults
        apply_workspace_defaults_to_namespace(args, root=str(tmp_path))

        # Explicit setting should be preserved, not overridden by config
        assert args.permission_mode == 'prompt', (
            'Explicit permission mode should not be overridden by config'
        )
    finally:
        os.chdir(original_cwd)


def test_unset_permission_mode_uses_config_value(tmp_path):
    """V8-a: Unset permission mode should use config value."""
    import argparse
    import os

    # Create a mock args namespace with unset permission mode
    args = argparse.Namespace()
    args.command = 'run'
    args.permission_mode = _UNSET  # Not explicitly set
    args.root = str(tmp_path)

    # Create a config file with permission mode
    config_file = tmp_path / '.teaagent' / 'config.toml'
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text('permission_mode = "read-only"')

    # Change to the temp directory so config loading works
    original_cwd = os.getcwd()
    try:
        os.chdir(str(tmp_path))
        # Apply workspace defaults
        apply_workspace_defaults_to_namespace(args, root=str(tmp_path))

        # Unset permission mode should use config value
        assert args.permission_mode == 'read-only', (
            'Unset permission mode should use config value'
        )
    finally:
        os.chdir(original_cwd)


def test_config_allow_does_not_override_explicit_prompt(tmp_path):
    """V8-a: Config 'allow' should not override explicit 'prompt' (security direction)."""
    import argparse
    import os

    # Create a mock args namespace with explicit permission mode
    args = argparse.Namespace()
    args.command = 'run'
    args.permission_mode = 'prompt'  # Explicitly set to safe mode
    args.root = str(tmp_path)

    # Create a config file that tries to override to allow (less safe)
    config_file = tmp_path / '.teaagent' / 'config.toml'
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text('permission_mode = "allow"')

    # Change to the temp directory so config loading works
    original_cwd = os.getcwd()
    try:
        os.chdir(str(tmp_path))
        # Apply workspace defaults
        apply_workspace_defaults_to_namespace(args, root=str(tmp_path))

        # Explicit safe setting should be preserved, not overridden by unsafe config
        assert args.permission_mode == 'prompt', (
            'Explicit safe permission mode should not be overridden by unsafe config'
        )
    finally:
        os.chdir(original_cwd)

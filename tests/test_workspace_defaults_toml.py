from __future__ import annotations

import os
from pathlib import Path

import pytest

from teaagent.ergonomics.workspace_defaults import (
    _load_env_file,
    _parse_flat_toml,
    load_workspace_defaults,
)


def test_parse_flat_toml_skips_comments_and_blank_lines() -> None:
    assert _parse_flat_toml('# comment\n\nkey = "v"\n') == {'key': 'v'}


def test_parse_flat_toml_reads_strings_and_numbers() -> None:
    payload = _parse_flat_toml(
        'provider = "gpt"\nheartbeat = 5.0\ndaily_cost_cap_cents = 50\nenabled = true\n'
    )
    assert payload['provider'] == 'gpt'
    assert payload['heartbeat'] == 5.0
    assert payload['daily_cost_cap_cents'] == 50
    assert payload['enabled'] is True
    assert _parse_flat_toml('disabled = false\n')['disabled'] is False


def test_load_env_file_skips_missing_file(tmp_path: Path) -> None:
    key = '_TEST_LOAD_ENV_GHOST'
    os.environ.pop(key, None)
    _load_env_file(tmp_path)
    assert key not in os.environ


def test_load_env_file_loads_exports(tmp_path: Path) -> None:
    env = tmp_path / '.teaagent' / 'env'
    env.parent.mkdir(parents=True)
    env.write_text(
        'export OPENCODEZEN_API_KEY=sk-test123\nexport ANTHROPIC_API_KEY=sk-ant-test\n',
        encoding='utf-8',
    )
    os.environ.pop('OPENCODEZEN_API_KEY', None)
    os.environ.pop('ANTHROPIC_API_KEY', None)
    _load_env_file(tmp_path)
    assert os.environ['OPENCODEZEN_API_KEY'] == 'sk-test123'
    assert os.environ['ANTHROPIC_API_KEY'] == 'sk-ant-test'


def test_load_env_file_does_not_overwrite_existing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env = tmp_path / '.teaagent' / 'env'
    env.parent.mkdir(parents=True)
    env.write_text(
        'export OPENCODEZEN_API_KEY=wrong\n',
        encoding='utf-8',
    )
    monkeypatch.setenv('OPENCODEZEN_API_KEY', 'right')
    _load_env_file(tmp_path)
    assert os.environ['OPENCODEZEN_API_KEY'] == 'right'


def test_load_env_file_skips_non_export_lines(tmp_path: Path) -> None:
    env = tmp_path / '.teaagent' / 'env'
    env.parent.mkdir(parents=True)
    env.write_text(
        '# comment line\nexport SECRET_KEY=real-value\necho hello\nPATH=/usr/bin\n',
        encoding='utf-8',
    )
    os.environ.pop('SECRET_KEY', None)
    os.environ.pop('PATH', None)
    _load_env_file(tmp_path)
    assert os.environ['SECRET_KEY'] == 'real-value'
    # PATH should not be set from a bare assignment (no export keyword)
    assert os.environ.get('PATH') is None or os.environ['PATH'] != '/usr/bin'


def test_load_env_file_strips_quotes(tmp_path: Path) -> None:
    env = tmp_path / '.teaagent' / 'env'
    env.parent.mkdir(parents=True)
    env.write_text(
        "export SINGLE='single-quoted'\n"
        'export DOUBLE="double-quoted"\n'
        'export PLAIN=no-quotes\n',
        encoding='utf-8',
    )
    os.environ.pop('SINGLE', None)
    os.environ.pop('DOUBLE', None)
    os.environ.pop('PLAIN', None)
    _load_env_file(tmp_path)
    assert os.environ['SINGLE'] == 'single-quoted'
    assert os.environ['DOUBLE'] == 'double-quoted'
    assert os.environ['PLAIN'] == 'no-quotes'


def test_load_env_file_handles_empty_value(tmp_path: Path) -> None:
    env = tmp_path / '.teaagent' / 'env'
    env.parent.mkdir(parents=True)
    env.write_text('export EMPTY=\n', encoding='utf-8')
    os.environ.pop('EMPTY', None)
    _load_env_file(tmp_path)
    assert 'EMPTY' not in os.environ


def test_load_env_file_integration_via_load_workspace_defaults(
    tmp_path: Path,
) -> None:
    tea = tmp_path / '.teaagent'
    tea.mkdir()
    (tea / 'config.toml').write_text('provider = "opencodezen-go"\n', encoding='utf-8')
    (tea / 'env').write_text(
        'export OPENCODEZEN_API_KEY=sk-integrated\n', encoding='utf-8'
    )
    os.environ.pop('OPENCODEZEN_API_KEY', None)
    defaults = load_workspace_defaults(tmp_path)
    assert defaults['provider'] == 'opencodezen-go'
    assert os.environ.get('OPENCODEZEN_API_KEY') == 'sk-integrated'


def test_load_env_file_no_teaagent_dir_is_noop(tmp_path: Path) -> None:
    os.environ.pop('_TEST_NO_DIR', None)
    _load_env_file(tmp_path)
    assert '_TEST_NO_DIR' not in os.environ


def test_load_env_file_skips_lines_without_equals(tmp_path: Path) -> None:
    env = tmp_path / '.teaagent' / 'env'
    env.parent.mkdir(parents=True)
    env.write_text(
        'export JUST_A_KEY\nexport ALSO=valid\n',
        encoding='utf-8',
    )
    os.environ.pop('JUST_A_KEY', None)
    os.environ.pop('ALSO', None)
    _load_env_file(tmp_path)
    assert 'JUST_A_KEY' not in os.environ
    assert os.environ['ALSO'] == 'valid'


def test_load_env_file_loaded_via_load_workspace_defaults_does_not_break_existing_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tea = tmp_path / '.teaagent'
    tea.mkdir()
    (tea / 'env').write_text('export MY_KEY=from-file\n', encoding='utf-8')
    # Same key set in real environment — must win
    monkeypatch.setenv('MY_KEY', 'from-env')
    load_workspace_defaults(tmp_path)
    assert os.environ['MY_KEY'] == 'from-env'


def test_load_env_file_loaded_via_load_workspace_defaults_missing_env_no_error(
    tmp_path: Path,
) -> None:
    tea = tmp_path / '.teaagent'
    tea.mkdir()
    (tea / 'config.toml').write_text('provider = "gpt"\n', encoding='utf-8')
    # No env file — must not crash
    defaults = load_workspace_defaults(tmp_path)
    assert defaults['provider'] == 'gpt'


def test_load_env_file_loaded_via_load_workspace_defaults_with_complex_value(
    tmp_path: Path,
) -> None:
    tea = tmp_path / '.teaagent'
    tea.mkdir()
    (tea / 'env').write_text('export TOKEN=ghp_abc123!@#\n', encoding='utf-8')
    os.environ.pop('TOKEN', None)
    load_workspace_defaults(tmp_path)
    assert os.environ['TOKEN'] == 'ghp_abc123!@#'


def test_load_env_file_default_root_is_dot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    env = tmp_path / '.teaagent' / 'env'
    env.parent.mkdir(parents=True)
    env.write_text('export CWD_KEY=cwd-value\n', encoding='utf-8')
    os.environ.pop('CWD_KEY', None)
    _load_env_file('.')
    assert os.environ['CWD_KEY'] == 'cwd-value'


def test_load_workspace_defaults_env_overrides(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tea = tmp_path / '.teaagent'
    tea.mkdir()
    (tea / 'config.toml').write_text('provider = "local"\n', encoding='utf-8')
    monkeypatch.setenv('TEAAGENT_PROVIDER', 'from-env')
    monkeypatch.setenv('TEAAGENT_AUTOMATION_WEBHOOK_URL', 'https://env.example/hook')
    monkeypatch.setenv('TEAAGENT_AUTOMATION_WEBHOOK_SECRET', 'env-secret')
    defaults = load_workspace_defaults(tmp_path)
    assert defaults['provider'] == 'from-env'
    assert defaults['automation_webhook_url'] == 'https://env.example/hook'
    assert defaults['automation_webhook_secret'] == 'env-secret'


def test_apply_workspace_defaults_require_provider_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import argparse

    from teaagent.ergonomics.workspace_defaults import (
        apply_workspace_defaults_to_namespace,
    )

    monkeypatch.chdir(tmp_path)
    args = argparse.Namespace(provider=None, root=str(tmp_path))
    with pytest.raises(SystemExit):
        apply_workspace_defaults_to_namespace(
            args, root=tmp_path, require_provider=True
        )


def test_load_workspace_defaults_reads_toml_on_py310_path(tmp_path: Path) -> None:
    tea = tmp_path / '.teaagent'
    tea.mkdir()
    (tea / 'config.toml').write_text(
        'automation_webhook_url = "https://example.com/hook"\nprovider = "gpt"\n',
        encoding='utf-8',
    )
    defaults = load_workspace_defaults(tmp_path)
    assert defaults['provider'] == 'gpt'
    assert defaults['automation_webhook_url'] == 'https://example.com/hook'

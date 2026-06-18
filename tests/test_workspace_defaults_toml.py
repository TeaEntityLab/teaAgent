from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from teaagent.ergonomics.workspace_defaults import (
    _load_env_file,
    _parse_flat_toml,
    load_workspace_defaults,
)


@pytest.fixture(autouse=True)
def _restore_process_environment() -> Iterator[None]:
    """Keep env-file loading tests from contaminating random-order workers."""
    original = os.environ.copy()
    yield
    os.environ.clear()
    os.environ.update(original)


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


# --- TASK-005: config provenance ------------------------------------------


def test_resolve_config_provenance_layers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each key reports the precedence layer that set its effective value."""
    from teaagent.ergonomics.workspace_defaults import resolve_config_provenance

    tea = tmp_path / '.teaagent'
    tea.mkdir()
    (tea / 'config.toml').write_text(
        'provider = "anthropic"\npermission_mode = "auto-edit"\n', encoding='utf-8'
    )
    for var in ('TEAAGENT_MODEL', 'TEAAGENT_PERMISSION_MODE'):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv('TEAAGENT_MODEL', 'claude-x')

    prov = resolve_config_provenance(tmp_path)

    # config-file layer
    assert prov['provider'] == {'value': 'anthropic', 'source': 'config:config.toml'}
    assert prov['permission_mode']['source'] == 'config:config.toml'
    # env layer overrides default
    assert prov['model'] == {'value': 'claude-x', 'source': 'env:TEAAGENT_MODEL'}
    # untouched key falls through to default
    assert prov['max_iterations']['source'] == 'default'


def test_resolve_config_provenance_env_overrides_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Env beats config for the same key (precedence is preserved)."""
    from teaagent.ergonomics.workspace_defaults import resolve_config_provenance

    tea = tmp_path / '.teaagent'
    tea.mkdir()
    (tea / 'config.toml').write_text('provider = "from_config"\n', encoding='utf-8')
    monkeypatch.setenv('TEAAGENT_PROVIDER', 'from_env')

    prov = resolve_config_provenance(tmp_path)
    assert prov['provider'] == {'value': 'from_env', 'source': 'env:TEAAGENT_PROVIDER'}


def test_resolve_config_provenance_distinguishes_env_file_from_shell(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A value from .teaagent/env is sourced to the file; a shell var wins and is
    sourced to the shell (review F-A)."""
    from teaagent.ergonomics.workspace_defaults import resolve_config_provenance

    tea = tmp_path / '.teaagent'
    tea.mkdir()
    (tea / 'env').write_text(
        'export TEAAGENT_MODEL=model-from-envfile\n'
        'export TEAAGENT_PROVIDER=provider-from-envfile\n',
        encoding='utf-8',
    )
    # model only in the env file; provider also set in the shell (shell wins).
    monkeypatch.delenv('TEAAGENT_MODEL', raising=False)
    monkeypatch.setenv('TEAAGENT_PROVIDER', 'provider-from-shell')

    prov = resolve_config_provenance(tmp_path)
    assert prov['model'] == {
        'value': 'model-from-envfile',
        'source': 'env-file:.teaagent/env',
    }
    assert prov['provider'] == {
        'value': 'provider-from-shell',
        'source': 'env:TEAAGENT_PROVIDER',
    }


def test_resolve_config_provenance_ignores_malformed_numeric_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A malformed numeric env var is ignored (falls back), not a crash (F-D)."""
    from teaagent.ergonomics.workspace_defaults import (
        load_workspace_defaults,
        resolve_config_provenance,
    )

    monkeypatch.setenv('TEAAGENT_DAILY_COST_CAP_CENTS', 'not-a-number')

    prov = resolve_config_provenance(tmp_path)
    assert prov['daily_cost_cap_cents']['value'] == 0  # default, override ignored
    assert prov['daily_cost_cap_cents']['source'] == 'default'
    # load_workspace_defaults (derived) must also not crash.
    assert load_workspace_defaults(tmp_path)['daily_cost_cap_cents'] == 0


def test_doctor_config_redacts_webhook_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The webhook URL value is redacted (may embed a token) but its source is
    still shown (F-C)."""
    import argparse
    import json

    from teaagent.cli._handlers._doctor import doctor_config

    monkeypatch.setenv(
        'TEAAGENT_AUTOMATION_WEBHOOK_URL', 'https://example.com/hook?token=abc123secret'
    )
    rc = doctor_config(argparse.Namespace(root=str(tmp_path)))
    assert rc == 0

    cfg = {e['key']: e for e in json.loads(capsys.readouterr().out)['config']}
    assert 'abc123secret' not in json.dumps(cfg)
    assert cfg['automation_webhook_url']['value'] != (
        'https://example.com/hook?token=abc123secret'
    )
    assert cfg['automation_webhook_url']['source'] == (
        'env:TEAAGENT_AUTOMATION_WEBHOOK_URL'
    )


def test_load_workspace_defaults_matches_provenance_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """load_workspace_defaults is derived from the resolver — they cannot drift."""
    from teaagent.ergonomics.workspace_defaults import (
        load_workspace_defaults,
        resolve_config_provenance,
    )

    tea = tmp_path / '.teaagent'
    tea.mkdir()
    (tea / 'config.toml').write_text('provider = "p"\nmodel = "m"\n', encoding='utf-8')
    monkeypatch.setenv('TEAAGENT_PERMISSION_MODE', 'read-only')

    defaults = load_workspace_defaults(tmp_path)
    prov = resolve_config_provenance(tmp_path)
    assert defaults == {k: v['value'] for k, v in prov.items()}


def test_doctor_config_command_reports_sources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`teaagent doctor config` prints per-key provenance and redacts secrets."""
    import argparse
    import json

    from teaagent.cli._handlers._doctor import doctor_config

    tea = tmp_path / '.teaagent'
    tea.mkdir()
    (tea / 'config.toml').write_text('provider = "anthropic"\n', encoding='utf-8')
    monkeypatch.setenv('TEAAGENT_MODEL', 'claude-x')
    monkeypatch.setenv('TEAAGENT_AUTOMATION_WEBHOOK_SECRET', 'super-secret-token-value')

    rc = doctor_config(argparse.Namespace(root=str(tmp_path)))
    assert rc == 0

    payload = json.loads(capsys.readouterr().out)
    cfg = {entry['key']: entry for entry in payload['config']}
    assert cfg['provider']['value'] == 'anthropic'
    assert cfg['provider']['source'] == 'config:config.toml'
    assert cfg['model']['value'] == 'claude-x'
    assert cfg['model']['source'] == 'env:TEAAGENT_MODEL'
    assert cfg['max_iterations']['source'] == 'default'
    # secret value is redacted, but its source/provenance is still shown.
    assert cfg['automation_webhook_secret']['value'] != 'super-secret-token-value'
    assert cfg['automation_webhook_secret']['source'] == (
        'env:TEAAGENT_AUTOMATION_WEBHOOK_SECRET'
    )

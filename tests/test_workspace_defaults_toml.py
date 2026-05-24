from __future__ import annotations

from pathlib import Path

import pytest

from teaagent.ergonomics.workspace_defaults import (
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

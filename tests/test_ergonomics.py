from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from teaagent.ergonomics.approval_store import ApprovalPresetStore
from teaagent.ergonomics.context_inject import expand_at_references
from teaagent.ergonomics.daily_journal import (
    daily_journal_path,
)
from teaagent.ergonomics.guidance import collect_workspace_guidance
from teaagent.ergonomics.workspace_defaults import load_workspace_defaults
from teaagent.recipes.registry import list_recipes, run_recipe


def test_load_workspace_defaults_merges_toml_and_json(tmp_path: Path) -> None:
    tea = tmp_path / '.teaagent'
    tea.mkdir()
    (tea / 'config.toml').write_text(
        'provider = "gpt"\nheartbeat = 5.0\n', encoding='utf-8'
    )
    (tea / 'config.json').write_text(
        json.dumps({'context_profile': 'lean', 'daily_cost_cap_cents': 50}),
        encoding='utf-8',
    )
    defaults = load_workspace_defaults(tmp_path)
    assert defaults['provider'] == 'gpt'
    assert defaults['heartbeat'] == 5.0
    assert defaults['context_profile'] == 'lean'
    assert defaults['daily_cost_cap_cents'] == 50


def test_expand_at_references(tmp_path: Path) -> None:
    readme = tmp_path / 'README.md'
    readme.write_text('hello world', encoding='utf-8')
    task, refs = expand_at_references('Please read @README.md', root=tmp_path)
    assert 'hello world' in task
    assert refs[0]['path'] == 'README.md'


def test_approval_preset_store(tmp_path: Path) -> None:
    store = ApprovalPresetStore(tmp_path)
    store.grant('workspace_write_file', scope='session')
    assert store.is_allowed('workspace_write_file', permission_mode='prompt')
    store.deny('workspace_apply_patch')
    assert not store.is_allowed('workspace_apply_patch', permission_mode='prompt')


def test_recipes_registry() -> None:
    names = {item['name'] for item in list_recipes()}
    assert 'review-staged' in names
    payload = run_recipe('review-staged')
    assert payload['recipe'] == 'review-staged'


def test_guidance_collects_agents_md(tmp_path: Path) -> None:
    (tmp_path / 'AGENTS.md').write_text('# rules', encoding='utf-8')
    info = collect_workspace_guidance(tmp_path)
    assert any(item['path'] == 'AGENTS.md' for item in info['files'])


def test_daily_journal_path(tmp_path: Path) -> None:
    path = daily_journal_path(tmp_path, day=date(2026, 5, 22))
    assert path.name == '2026-05-22.md'
    assert path.parent.name == 'daily'


def test_cli_init_writes_toml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import argparse

    from teaagent.cli._handlers._misc import init_command

    args = argparse.Namespace(
        root=str(tmp_path),
        provider='gpt',
        api_key='test-key',
        permission_mode='read-only',
        max_iterations=5,
        max_tool_calls=5,
        write_env=False,
        context_profile='lean',
        heartbeat=0.0,
        daily_cost_cap_cents=100,
    )
    monkeypatch.setattr(
        'teaagent.cli._handlers._misc.available_providers', lambda: ['gpt']
    )
    assert init_command(args) == 0
    assert (tmp_path / '.teaagent' / 'config.toml').is_file()


def test_top_level_shortcut_daily_argv() -> None:
    from teaagent.cli import _expand_argv

    assert _expand_argv(['daily', 'gpt']) == ['agent', 'daily', 'gpt']

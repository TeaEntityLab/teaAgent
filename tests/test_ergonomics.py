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


def test_scoped_approval_path_glob(tmp_path: Path) -> None:
    store = ApprovalPresetStore(tmp_path)
    store.grant(
        'workspace_write_file',
        scope='session',
        path_globs=['src/**'],
    )
    assert store.is_allowed(
        'workspace_write_file',
        permission_mode='prompt',
        arguments={'path': 'src/module.py'},
    )
    assert not store.is_allowed(
        'workspace_write_file',
        permission_mode='prompt',
        arguments={'path': 'etc/passwd'},
    )


def test_scoped_approval_command_prefix(tmp_path: Path) -> None:
    store = ApprovalPresetStore(tmp_path)
    store.grant(
        'run_terminal_cmd',
        scope='session',
        command_prefixes=['pytest '],
    )
    assert store.is_allowed(
        'run_terminal_cmd',
        permission_mode='prompt',
        arguments={'command': 'pytest -q tests'},
    )
    assert not store.is_allowed(
        'run_terminal_cmd',
        permission_mode='prompt',
        arguments={'command': 'rm -rf /'},
    )


def test_scoped_approval_once_consumed(tmp_path: Path) -> None:
    store = ApprovalPresetStore(tmp_path)
    store.grant('workspace_write_file', scope='once')
    assert store.is_allowed('workspace_write_file', permission_mode='prompt')
    assert not store.is_allowed('workspace_write_file', permission_mode='prompt')


def test_cli_approval_handler_honors_run_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from teaagent.cli._handlers._agent import make_cli_approval_handler
    from teaagent.runner import ApprovalRequest

    workspace = tmp_path / 'repo'
    workspace.mkdir()
    other_cwd = tmp_path / 'other'
    other_cwd.mkdir()
    ApprovalPresetStore(workspace).grant('workspace_write_file', scope='always')
    handler = make_cli_approval_handler(workspace, permission_mode='prompt')
    request = ApprovalRequest(
        call_id='call-1',
        tool_name='workspace_write_file',
        arguments={'path': 'src/x.py'},
        reason='destructive',
        annotations={'destructive': True},
    )
    monkeypatch.chdir(other_cwd)
    assert handler(request) is True


def test_scoped_approval_expired_grant(tmp_path: Path) -> None:
    store = ApprovalPresetStore(tmp_path)
    store.grant('workspace_write_file', scope='session')
    data = store._load()
    assert isinstance(data['grants'][0], dict)
    data['grants'][0]['expires_at'] = '2020-01-01T00:00:00+00:00'
    store._save(data)
    assert not store.is_allowed('workspace_write_file', permission_mode='prompt')


def test_first_hour_recipe_listed() -> None:
    names = {item['name'] for item in list_recipes()}
    assert 'first-hour' in names


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


def test_top_level_daily_parser_is_visible() -> None:
    from teaagent.cli import build_parser

    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(['daily', '--help'])
    args = parser.parse_args(['daily', 'gpt', 'hello', '--root', '.'])
    assert args.command == 'agent'
    assert args.agent_command == 'daily'


def test_normalize_providerless_run_task(tmp_path: Path) -> None:
    import argparse

    from teaagent.cli import _normalize_optional_provider_args

    args = argparse.Namespace(
        command='agent',
        agent_command='run',
        provider='fix the failing test',
        task=None,
        root=str(tmp_path),
    )
    _normalize_optional_provider_args(args)
    assert args.provider is None
    assert args.task == 'fix the failing test'


def test_attach_follow_exits_on_terminal_run(tmp_path: Path) -> None:
    from teaagent.ergonomics.session_stream import stream_run_events
    from teaagent.run_store import RunStore

    store = RunStore(tmp_path)
    audit = store.audit_logger('run-attach-1')
    audit.record('run_started', 'run-attach-1', task='hello')
    audit.record('run_completed', 'run-attach-1', answer='done')
    events = list(stream_run_events('run-attach-1', root=tmp_path, follow=True))
    assert any(e.get('event_type') == 'run_completed' for e in events)


def test_session_stream_yields_events(tmp_path: Path) -> None:
    from teaagent.ergonomics.session_stream import stream_run_events
    from teaagent.run_store import RunStore

    store = RunStore(tmp_path)
    audit = store.audit_logger('run-ergo-1')
    audit.record('run_started', 'run-ergo-1', task='hello')
    audit.record('run_completed', 'run-ergo-1', answer='done')
    events = list(stream_run_events('run-ergo-1', root=tmp_path))
    assert any(event.get('event_type') == 'run_started' for event in events)


def test_model_capabilities_table() -> None:
    from teaagent.model_capabilities import (
        build_capability_table,
        build_model_capability_table,
    )

    rows = build_capability_table()
    providers = {row['provider'] for row in rows}
    assert 'gpt' in providers
    assert all('default_model' in row for row in rows)
    model_rows = build_model_capability_table(provider='gpt')
    assert model_rows
    assert all(row['model'] for row in model_rows)


def test_list_at_candidates(tmp_path: Path) -> None:
    from teaagent.ergonomics.context_inject import list_at_candidates

    (tmp_path / 'src').mkdir()
    (tmp_path / 'src' / 'main.py').write_text('x = 1\n', encoding='utf-8')
    paths = list_at_candidates(tmp_path, prefix='src/')
    assert 'src/main.py' in paths


def test_merge_acp_context_blocks() -> None:
    from teaagent.ergonomics.context_inject import merge_acp_context_blocks

    merged, meta = merge_acp_context_blocks(
        'Review this',
        [{'type': 'selection', 'label': 'foo.py', 'content': 'def foo(): pass'}],
    )
    assert 'selection' in merged
    assert meta


def test_model_capabilities_match_providers() -> None:
    from teaagent.llm import available_providers
    from teaagent.model_capabilities import build_capability_table

    table_providers = {row['provider'] for row in build_capability_table()}
    assert table_providers == set(available_providers())


def test_provider_required_without_init(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from teaagent.cli import main

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv('TEAAGENT_PROVIDER', raising=False)
    monkeypatch.delenv('TEAAGENT_MODEL', raising=False)
    with pytest.raises(SystemExit):
        main(['agent', 'run', 'task without provider', '--root', str(tmp_path)])


def test_resolve_auto_compact_defaults(tmp_path: Path) -> None:
    import argparse

    from teaagent.cli._handlers._agent import _resolve_auto_compact

    args = argparse.Namespace(auto_compact=None, root=str(tmp_path))
    assert _resolve_auto_compact(args) is True

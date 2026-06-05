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
    store.deny('workspace_apply_patch', path_globs=['src/**'])
    assert not store.is_allowed(
        'workspace_apply_patch',
        permission_mode='prompt',
        arguments={'path': 'src/example.py'},
    )


def test_approval_preset_store_rejects_blank_scoped_patterns(tmp_path: Path) -> None:
    store = ApprovalPresetStore(tmp_path)
    with pytest.raises(ValueError):
        store.grant(
            'workspace_write_file',
            scope='session',
            path_globs=[''],
        )
    with pytest.raises(ValueError):
        store.deny(
            'workspace_apply_patch',
            command_prefixes=[' '],
        )


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


def test_multiple_grants_same_tool(tmp_path: Path) -> None:
    store = ApprovalPresetStore(tmp_path)
    store.grant(
        'workspace_write_file',
        scope='session',
        path_globs=['src/**'],
    )
    store.grant(
        'workspace_write_file',
        scope='session',
        path_globs=['docs/**'],
    )
    assert len(store.list_grants()) == 2
    assert store.is_allowed(
        'workspace_write_file',
        permission_mode='prompt',
        arguments={'path': 'src/a.py'},
    )
    assert store.is_allowed(
        'workspace_write_file',
        permission_mode='prompt',
        arguments={'path': 'docs/readme.md'},
    )
    assert not store.is_allowed(
        'workspace_write_file',
        permission_mode='prompt',
        arguments={'path': 'etc/passwd'},
    )


def test_scoped_deny_blocks_only_matching_paths(tmp_path: Path) -> None:
    store = ApprovalPresetStore(tmp_path)
    store.grant(
        'workspace_write_file',
        scope='session',
        path_globs=['src/**'],
    )
    store.deny('workspace_write_file', path_globs=['src/secret/**'])
    assert store.is_allowed(
        'workspace_write_file',
        permission_mode='prompt',
        arguments={'path': 'src/public.txt'},
    )
    assert not store.is_allowed(
        'workspace_write_file',
        permission_mode='prompt',
        arguments={'path': 'src/secret/key.txt'},
    )


def test_once_consumes_single_grant_only(tmp_path: Path) -> None:
    store = ApprovalPresetStore(tmp_path)
    first = store.grant(
        'workspace_write_file',
        scope='once',
        path_globs=['src/**'],
    )
    second = store.grant(
        'workspace_write_file',
        scope='once',
        path_globs=['docs/**'],
    )
    assert store.is_allowed(
        'workspace_write_file',
        permission_mode='prompt',
        arguments={'path': 'src/a.py'},
    )
    assert len(store.list_grants()) == 1
    remaining = store.list_grants()[0]
    assert remaining.grant_id == second.grant_id
    assert store.is_allowed(
        'workspace_write_file',
        permission_mode='prompt',
        arguments={'path': 'docs/readme.md'},
    )
    assert not store.is_allowed(
        'workspace_write_file',
        permission_mode='prompt',
        arguments={'path': 'src/a.py'},
    )
    assert first.grant_id != second.grant_id


def test_approval_check_reports_deny_before_allow(tmp_path: Path) -> None:
    store = ApprovalPresetStore(tmp_path)
    store.grant('workspace_write_file', scope='session', path_globs=['src/**'])
    store.deny('workspace_write_file', path_globs=['src/secret/**'])
    blocked = store.check(
        'workspace_write_file',
        permission_mode='prompt',
        path='src/secret/key.txt',
    )
    assert blocked['decision'] == 'deny'
    assert blocked['allowed'] is False
    assert blocked['matched_grant']['scope'] == 'deny'
    allowed = store.check(
        'workspace_write_file',
        permission_mode='prompt',
        path='src/public.txt',
    )
    assert allowed['decision'] == 'allow'
    assert allowed['allowed'] is True
    assert 'policy_order' in allowed


def test_approval_check_does_not_consume_once(tmp_path: Path) -> None:
    store = ApprovalPresetStore(tmp_path)
    args = {'path': 'src/example.py'}
    store.grant('workspace_write_file', scope='once', path_globs=['src/**'])
    first = store.check('workspace_write_file', permission_mode='prompt', **args)
    second = store.check('workspace_write_file', permission_mode='prompt', **args)
    assert first['decision'] == 'allow'
    assert second['decision'] == 'allow'
    assert len(store.list_grants()) == 1
    assert store.is_allowed(
        'workspace_write_file', permission_mode='prompt', arguments=args
    )
    assert not store.is_allowed(
        'workspace_write_file', permission_mode='prompt', arguments=args
    )


def test_approval_revoke_removes_grant(tmp_path: Path) -> None:
    store = ApprovalPresetStore(tmp_path)
    grant = store.grant('workspace_write_file', scope='always', path_globs=['src/**'])
    assert store.revoke(grant.grant_id)
    assert store.list_grants() == []
    assert not store.revoke(grant.grant_id)


def test_migrate_grant_id_writes_audit(tmp_path: Path) -> None:
    import json

    store = ApprovalPresetStore(tmp_path)
    store.path.parent.mkdir(parents=True, exist_ok=True)
    store.path.write_text(
        json.dumps(
            {
                'grants': [{'tool_name': 'workspace_write_file', 'scope': 'session'}],
                'audit': [],
            }
        ),
        encoding='utf-8',
    )
    # list_grants should NOT write migration (readonly path)
    grants = store.list_grants()
    assert len(grants) == 1
    assert grants[0].grant_id.startswith('leg-')
    audit = store.audit_tail(5)
    assert not any(row.get('action') == 'migrate_grant_id' for row in audit)

    # Mutating operation should trigger migration
    store.grant('workspace_read_file', scope='always', path_globs=['README.md'])
    audit = store.audit_tail(5)
    assert any(row.get('action') == 'migrate_grant_id' for row in audit)


def test_legacy_once_grant_without_grant_id_is_consumed(tmp_path: Path) -> None:
    import json

    store = ApprovalPresetStore(tmp_path)
    store.path.parent.mkdir(parents=True, exist_ok=True)
    store.path.write_text(
        json.dumps(
            {
                'grants': [
                    {
                        'tool_name': 'workspace_write_file',
                        'scope': 'once',
                        'created_at': '2026-01-01T00:00:00+00:00',
                    }
                ],
                'audit': [],
            }
        ),
        encoding='utf-8',
    )
    assert store.is_allowed('workspace_write_file', permission_mode='prompt')
    assert not store.is_allowed('workspace_write_file', permission_mode='prompt')
    assert store.list_grants() == []


def test_scoped_approval_once_consumed(tmp_path: Path) -> None:
    store = ApprovalPresetStore(tmp_path)
    args = {'path': 'src/example.py'}
    store.grant('workspace_write_file', scope='once', path_globs=['src/**'])
    assert store.is_allowed(
        'workspace_write_file', permission_mode='prompt', arguments=args
    )
    assert not store.is_allowed(
        'workspace_write_file', permission_mode='prompt', arguments=args
    )


def test_cli_approval_handler_honors_run_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from teaagent.cli._handlers._agent import make_cli_approval_handler
    from teaagent.runner import ApprovalRequest

    workspace = tmp_path / 'repo'
    workspace.mkdir()
    other_cwd = tmp_path / 'other'
    other_cwd.mkdir()
    ApprovalPresetStore(workspace).grant(
        'workspace_write_file', scope='always', path_globs=['src/**']
    )
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


def test_scoped_approval_hardening_and_observability(tmp_path: Path) -> None:
    store = ApprovalPresetStore(tmp_path)

    # 1. Test listing all scoped approvals (empty first)
    assert store.list_all_scoped_approvals() == []

    # 2. Add some scoped approvals
    rec1 = store.add_scoped_approval(
        run_id='run-1',
        call_id='call-1',
        tool_name='workspace_write_file',
        arguments={'path': 'a.txt', 'content': 'hello'},
        ttl_hours=1.0,
    )
    rec2 = store.add_scoped_approval(
        run_id='run-1',
        call_id='call-2',
        tool_name='workspace_write_file',
        arguments={'path': 'b.txt', 'content': 'world'},
        ttl_hours=1.0,
    )

    # Check all are listed with active status
    all_scoped = store.list_all_scoped_approvals()
    assert len(all_scoped) == 2
    assert all(r['status'] == 'active' for r in all_scoped)

    # 3. Consume one
    assert store.consume_scoped_approval(rec1.record_id) is True
    all_scoped = store.list_all_scoped_approvals()
    assert any(
        r['record_id'] == rec1.record_id and r['status'] == 'consumed'
        for r in all_scoped
    )
    assert any(
        r['record_id'] == rec2.record_id and r['status'] == 'active' for r in all_scoped
    )

    # 4. Pruning
    pruned_count = store.prune_scoped_approvals()
    assert pruned_count == 1  # consumed one pruned
    all_scoped = store.list_all_scoped_approvals()
    assert len(all_scoped) == 1
    assert all_scoped[0]['record_id'] == rec2.record_id

    # 5. Clear legacy bare approved call IDs
    store.add_approved_call_id('bare-call-123')
    assert 'bare-call-123' in store.list_approved_call_ids()
    cleared = store.clear_legacy_approved_call_ids()
    assert cleared == 1
    assert store.list_approved_call_ids() == []


def test_approval_doctor_scoped_auditing_and_pruning(tmp_path: Path) -> None:
    import argparse

    from teaagent.cli._handlers._ergonomics import approval_doctor_command

    store = ApprovalPresetStore(tmp_path)

    # Add a consumed scoped approval and a legacy bare approved_call_id
    rec = store.add_scoped_approval(
        run_id='run-doctor',
        call_id='call-doctor-1',
        tool_name='workspace_write_file',
        arguments={'path': 'doc.txt'},
    )
    store.consume_scoped_approval(rec.record_id)
    store.add_approved_call_id('legacy-bare-id')

    # Run doctor in audit/diagnostic mode (should return 1 because issues found)
    args_diag = argparse.Namespace(
        root=str(tmp_path),
        prune_expired=False,
        fix_duplicates=False,
    )
    # Mock print_json to inspect the result
    reported_payload = None

    def mock_print_json(val):
        nonlocal reported_payload
        reported_payload = val

    import teaagent.cli._handlers._ergonomics as ergonomics_mod

    orig_print = ergonomics_mod.print_json
    ergonomics_mod.print_json = mock_print_json
    try:
        exit_code = approval_doctor_command(args_diag)
        assert exit_code == 1
        assert any(
            'expired or consumed scoped approvals' in iss
            for iss in reported_payload['issues']
        )
        assert any(
            'legacy bare approved_call_ids residue' in iss
            for iss in reported_payload['issues']
        )

        # Now run doctor with fixes
        args_fix = argparse.Namespace(
            root=str(tmp_path),
            prune_expired=True,
            fix_duplicates=True,
        )
        exit_code_fix = approval_doctor_command(args_fix)
        assert exit_code_fix == 0
        assert not any(
            'expired or consumed scoped approvals' in iss
            for iss in reported_payload['issues']
        )
        assert not any(
            'legacy bare approved_call_ids residue' in iss
            for iss in reported_payload['issues']
        )
        assert (
            'Pruned 1 expired or consumed scoped approvals'
            in reported_payload['actions_taken']
        )
        assert (
            'Cleared 1 legacy bare approved_call_ids residue'
            in reported_payload['actions_taken']
        )
    finally:
        ergonomics_mod.print_json = orig_print


def test_agent_resume_auto_approve_creates_scoped_approval(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import argparse

    from teaagent.cli._handlers._agent import agent_resume_command
    from teaagent.run_store import RunStore

    # 1. Setup the RunStore and mock run audit trail
    store = RunStore(tmp_path)
    run_id = 'run-resume-test-123'
    audit = store.audit_logger(run_id)

    # Write events: run_started and a tool_call_pending_approval
    audit.record('run_started', run_id, task='write a file')

    from teaagent.ergonomics._approval_grants import _compute_argument_digest

    args_payload = {'path': 'hello.txt', 'data': 'hi'}
    digest = _compute_argument_digest(args_payload)

    audit.record(
        'tool_call_pending_approval',
        run_id,
        call_id='pending-call-456',
        tool_name='workspace_write_file',
        arguments=args_payload,
        argument_digest=digest,
        argument_digest_version='v1',
    )

    # 2. Mock _execute_agent_task so it doesn't run the LLM Decision loop
    execute_args = {}

    def mock_execute(args, task, **kwargs):
        execute_args['args'] = args
        execute_args['task'] = task
        execute_args['kwargs'] = kwargs
        return 0

    monkeypatch.setattr(
        'teaagent.cli._handlers._agent._execute_agent_task', mock_execute
    )

    # 3. Call agent_resume_command
    args = argparse.Namespace(
        run_id=run_id,
        root=str(tmp_path),
        fresh_restart=False,
        approve_call_id=[],
        provider='mock-provider',
        model='mock-model',
        auto_compact=None,
    )

    exit_code = agent_resume_command(args)
    assert exit_code == 0

    # 4. Verify that:
    # A. _execute_agent_task was called with auto_approved_call_id='pending-call-456'
    assert execute_args['kwargs']['auto_approved_call_id'] == 'pending-call-456'

    # B. A run-scoped approval record was added to ApprovalPresetStore
    approval_store = ApprovalPresetStore(tmp_path)
    scoped_records = approval_store.list_scoped_approvals_for_run(run_id)
    assert len(scoped_records) == 1
    record = scoped_records[0]
    assert record.call_id == 'pending-call-456'
    assert record.tool_name == 'workspace_write_file'
    # Argument digest check
    from teaagent.ergonomics._approval_grants import _compute_argument_digest

    expected_digest = _compute_argument_digest({'path': 'hello.txt', 'data': 'hi'})
    assert record.argument_digest == expected_digest

    # C. Verify that bare approved_call_id remains an empty frozenset (not degraded to bare ID)
    assert not execute_args['args'].approve_call_id
    assert 'pending-call-456' not in execute_args['args'].approve_call_id


def test_resume_policy_strict_exact_match_wiring(tmp_path: Path) -> None:
    from teaagent.ergonomics.approval_store import ApprovalPresetStore
    from teaagent.errors import ToolPermissionError
    from teaagent.policy import ApprovalPolicy, PermissionMode

    store = ApprovalPresetStore(tmp_path)
    run_id = 'run-wiring-test-999'

    # 1. Register a scoped approval for run-wiring-test-999
    store.add_scoped_approval(
        run_id=run_id,
        call_id='c1',
        tool_name='workspace_write_file',
        arguments={'path': 'hello.txt', 'data': 'hi'},
    )

    # 2. Build ApprovalPolicy with empty legacy approved_call_ids
    policy = ApprovalPolicy(
        permission_mode=PermissionMode.PROMPT,
        approval_store=store,
        approval_origin_run_id=run_id,
    )

    # 3. Correct call should be allowed
    policy.assert_allowed(
        tool_name='workspace_write_file',
        call_id='c1',
        destructive=True,
        arguments={'path': 'hello.txt', 'data': 'hi'},
    )

    # 4. A different tool call with same call_id must be strictly BLOCKED
    with pytest.raises(ToolPermissionError) as exc_tool:
        policy.assert_allowed(
            tool_name='workspace_run_shell_mutate',
            call_id='c1',
            destructive=True,
            arguments={'command': 'rm -rf /'},
        )
    assert 'requires explicit approval' in str(exc_tool.value)

    # 5. Same tool call with different arguments must be strictly BLOCKED
    with pytest.raises(ToolPermissionError) as exc_args:
        policy.assert_allowed(
            tool_name='workspace_write_file',
            call_id='c1',
            destructive=True,
            arguments={'path': 'dangerous.sh', 'data': 'malicious'},
        )
    assert 'requires explicit approval' in str(exc_args.value)


def test_legacy_approval_list_returns_stable_id_without_migration(
    tmp_path: Path,
) -> None:
    """Verify that readonly list_grants returns leg-* IDs without writing migration."""
    from teaagent.ergonomics.approval_store import ApprovalPresetStore

    # Create a legacy grant without grant_id
    tea = tmp_path / '.teaagent'
    tea.mkdir()
    approvals_path = tea / 'approvals.json'
    legacy_data = {
        'grants': [
            {
                'tool_name': 'workspace_write_file',
                'scope': 'session',
                'permission_mode': 'prompt',
                'created_at': '2026-05-22T00:00:00+00:00',
                # Note: no grant_id field
            }
        ],
        'audit': [],
        'approved_call_ids': [],
        'scoped_approvals': [],
    }
    original_content = json.dumps(legacy_data, indent=2)
    approvals_path.write_text(original_content, encoding='utf-8')

    # List grants with readonly store
    readonly_store = ApprovalPresetStore(tmp_path, readonly=True)
    grants = readonly_store.list_grants()

    # Should return one grant with stable leg-* ID
    assert len(grants) == 1
    assert grants[0].tool_name == 'workspace_write_file'
    assert grants[0].grant_id.startswith('leg-')

    # But file should not be modified (no migration written)
    current_content = approvals_path.read_text(encoding='utf-8')
    assert current_content == original_content
    current_data = json.loads(current_content)
    assert 'grant_id' not in current_data['grants'][0]

    # Mutating operations should still trigger migration
    writable_store = ApprovalPresetStore(tmp_path, readonly=False)
    writable_store.grant(
        'workspace_read_file', scope='always', path_globs=['README.md']
    )

    # Now file should be modified with migration
    current_content = approvals_path.read_text(encoding='utf-8')
    current_data = json.loads(current_content)
    # Original grant should now have grant_id
    assert 'grant_id' in current_data['grants'][0]
    assert current_data['grants'][0]['grant_id'].startswith('leg-')
    # New grant should have fresh ID
    assert 'grant_id' in current_data['grants'][1]

from __future__ import annotations

import shlex
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from teaagent.daily import build_daily_brief
from teaagent.graphqlite_store import (
    GraphQLiteRuntimeError,
    GraphQLiteUnavailableError,
    check_graphqlite_runtime,
)
from teaagent.intent import clarify_task
from teaagent.llm import available_providers
from teaagent.model_routing import route_model
from teaagent.policy import parse_permission_mode
from teaagent.preflight import preflight
from teaagent.run_store import RunStore

if TYPE_CHECKING:
    from teaagent.session import ChatSession
    from teaagent.tui import TeaAgentTUI


def _handle_tui_command(tui: 'TeaAgentTUI', raw_command: str) -> bool:
    command = raw_command.strip()
    if not command:
        return True
    try:
        parts = shlex.split(command)
    except ValueError as exc:
        tui.output_fn(f'error: {exc}')
        return True

    action = parts[0].lower()
    if action.startswith('/'):
        action = action[1:]
    args = parts[1:]
    if action in {'exit', 'quit'}:
        tui.output_fn('bye')
        return False
    if action == 'help':
        tui.output_fn(tui.help_text.rstrip())
        return True
    if action == 'setup':
        from teaagent.tui._setup import run_tui_setup

        write_env = 'write-env' in args
        rest = [item for item in args if item != 'write-env']
        provider: str | None = None
        if rest:
            if rest[0] not in available_providers():
                tui.output_fn(f"error: unknown provider '{rest[0]}'")
                return True
            provider = rest[0]
        run_tui_setup(tui, write_env=write_env, provider=provider)
        return True
    if action == 'doctor':
        ok, message = check_graphqlite_runtime(tui.database)
        tui._print_json({'ok': ok, 'message': message})
        return True
    if action == 'provider':
        if len(args) != 1:
            tui.output_fn('error: provider requires exactly one provider name')
            return True
        if args[0] not in available_providers():
            tui.output_fn(f"error: unknown provider '{args[0]}'")
            return True
        tui.provider = args[0]
        tui.output_fn(f'provider: {tui.provider}')
        tui._save_tui_state()
        return True
    if action == 'model':
        if len(args) != 1:
            tui.output_fn("error: model requires a model name or 'default'")
            return True
        tui.model = None if args[0] == 'default' else args[0]
        tui.output_fn(f'model: {tui.model or "default"}')
        tui._save_tui_state()
        return True
    if action == 'route-model':
        if len(args) != 1 or args[0] not in {'on', 'off'}:
            tui.output_fn("error: route-model requires 'on' or 'off'")
            return True
        tui.route_model_enabled = args[0] == 'on'
        tui.output_fn(f'route-model: {"on" if tui.route_model_enabled else "off"}')
        tui._save_tui_state()
        return True
    if action == 'route':
        if not args:
            tui.output_fn('error: route requires a task')
            return True
        tui._print_json(
            route_model(
                ' '.join(args), provider=tui.provider, model=tui.model
            ).to_dict()
        )
        return True
    if action == 'root':
        if len(args) != 1:
            tui.output_fn('error: root requires exactly one path')
            return True
        tui.root = Path(args[0]).resolve()
        tui.output_fn(f'root: {tui.root}')
        tui._save_tui_state()
        return True
    if action == 'destructive':
        if len(args) != 1 or args[0] not in {'on', 'off'}:
            tui.output_fn("error: destructive requires 'on' or 'off'")
            return True
        tui.allow_destructive = args[0] == 'on'
        tui.output_fn(f'destructive: {"on" if tui.allow_destructive else "off"}')
        tui._save_tui_state()
        return True
    if action == 'progress':
        if len(args) != 1 or args[0] not in {'on', 'off'}:
            tui.output_fn("error: progress requires 'on' or 'off'")
            return True
        tui.progress = args[0] == 'on'
        tui.output_fn(f'progress: {"on" if tui.progress else "off"}')
        tui._save_tui_state()
        return True
    if action == 'stream':
        if len(args) != 1 or args[0] not in {'on', 'off'}:
            tui.output_fn("error: stream requires 'on' or 'off'")
            return True
        tui.stream = args[0] == 'on'
        tui.output_fn(f'stream: {"on" if tui.stream else "off"}')
        tui._save_tui_state()
        return True
    if action == 'subagent':
        if len(args) != 1 or args[0] not in {'on', 'off'}:
            tui.output_fn("error: subagent requires 'on' or 'off'")
            return True
        tui.subagent = args[0] == 'on'
        tui.output_fn(f'subagent: {"on" if tui.subagent else "off"}')
        tui._save_tui_state()
        return True
    if action == 'chat':
        if len(args) != 1 or args[0] not in {'on', 'off'}:
            tui.output_fn("error: chat requires 'on' or 'off'")
            return True
        tui.chat = args[0] == 'on'
        if tui.chat and not tui.session_id:
            tui._ensure_session()
        tui.output_fn(
            f'chat: {"on" if tui.chat else "off"}'
            + (f' (session: {tui.session_id[:8]})' if tui.session_id else '')
        )
        tui._save_tui_state()
        return True
    if action == 'session':
        if not args:
            tui.output_fn('error: session requires new, list, switch, clear, or show')
            return True
        sub = args[0]
        if sub == 'new':
            tui.chat = True
            tui.session_id = None
            new_session = tui._ensure_session()
            tui.output_fn(f'session new: {new_session.id}')
            tui._save_tui_state()
            return True
        if sub == 'list':
            sessions = tui._get_session_store().list_sessions()
            for s in sessions:
                marker = ' *' if s['id'] == tui.session_id else ''
                tui.output_fn(
                    f'  {s["id"][:8]}  {s.get("label", "")}  '
                    f'msgs:{s["message_count"]}{marker}'
                )
            if not sessions:
                tui.output_fn('  (no sessions)')
            return True
        if sub == 'switch':
            if len(args) != 2:
                tui.output_fn('error: session switch requires a session id')
                return True
            sid = args[1]
            switched_session: Optional[ChatSession] = tui._get_session_store().load(sid)
            if switched_session is None:
                tui.output_fn(f'error: session {sid[:8]} not found')
                return True
            tui.chat = True
            tui.session_id = switched_session.id
            tui.output_fn(
                f'session switch: {switched_session.id[:8]}  msgs:{len(switched_session.messages)}'
            )
            tui._save_tui_state()
            return True
        if sub == 'clear':
            if tui.session_id:
                cleared_session: Optional[ChatSession] = tui._current_session()
                if cleared_session:
                    cleared_session.messages.clear()
                    tui._get_session_store().save(cleared_session)
                    tui.output_fn(f'session clear: {tui.session_id[:8]}')
            else:
                tui.output_fn('session clear: no active session')
            return True
        if sub == 'show':
            if not tui.session_id:
                tui.output_fn('session show: no active session')
                return True
            shown_session: Optional[ChatSession] = tui._current_session()
            if shown_session is None:
                tui.output_fn('session show: session not found')
                return True
            tui._print_json(shown_session.to_dict())
            return True
        tui.output_fn(f"error: unknown session subcommand '{sub}'")
        return True
    if action == 'heartbeat':
        if len(args) != 1:
            tui.output_fn('error: heartbeat requires a seconds value (0 disables)')
            return True
        try:
            seconds = float(args[0])
        except ValueError:
            tui.output_fn('error: heartbeat seconds must be a number')
            return True
        tui.heartbeat_seconds = max(0.0, seconds)
        tui.output_fn(f'heartbeat: {tui.heartbeat_seconds}')
        tui._save_tui_state()
        return True
    if action == 'status':
        if len(args) != 1:
            tui.output_fn('error: status requires a run id')
            return True
        try:
            tui._print_json(RunStore(tui.root).heartbeat_for_run(args[0]))
        except FileNotFoundError as exc:
            tui.output_fn(f'error: {exc}')
        return True
    if action == 'permission':
        if len(args) != 1:
            tui.output_fn('error: permission requires one mode')
            return True
        try:
            tui.permission_mode = parse_permission_mode(args[0])
        except ValueError as exc:
            tui.output_fn(f'error: {exc}')
            return True
        tui.output_fn(f'permission: {tui.permission_mode.value}')
        tui._save_tui_state()
        return True
    if action == 'approve':
        if len(args) != 1:
            tui.output_fn('error: approve requires one call id')
            return True
        tui.approved_call_ids.add(args[0])
        tui.output_fn(f'approved: {args[0]}')
        return True
    if action == 'unapprove':
        if len(args) != 1:
            tui.output_fn('error: unapprove requires one call id')
            return True
        tui.approved_call_ids.discard(args[0])
        tui.output_fn(f'unapproved: {args[0]}')
        return True
    if action == 'approvals':
        if not args:
            tui._print_json(sorted(tui.approved_call_ids))
            return True
        sub = args[0]
        if sub == 'check':
            from teaagent.ergonomics.approval_store import ApprovalPresetStore

            if len(args) < 2:
                tui.output_fn('error: approvals check requires a tool_name')
                return True
            tool_name = args[1]
            approval_store = ApprovalPresetStore(tui.root)
            # Parse additional arguments
            arguments = {}
            for arg in args[2:]:
                if '=' in arg:
                    key, value = arg.split('=', 1)
                    arguments[key] = value
            result = approval_store.check(
                tool_name,
                permission_mode=tui.permission_mode.value,
                arguments=arguments or None,
            )
            tui._print_json(result)
            return True
        if sub == 'revoke':
            from teaagent.ergonomics.approval_store import ApprovalPresetStore

            if len(args) < 2:
                tui.output_fn('error: approvals revoke requires a grant_id')
                return True
            grant_id = args[1]
            approval_store = ApprovalPresetStore(tui.root)
            revoked = approval_store.revoke(grant_id)
            if not revoked:
                tui.output_fn(f"error: grant '{grant_id}' not found")
            else:
                tui.output_fn(f'revoked: {grant_id}')
            return True
        if sub == 'pending':
            store = RunStore(tui.root)
            pending_runs = []
            for summary in store.list_runs(limit=20):
                pending = store.pending_approval_for_run(summary.run_id)
                if pending:
                    pending_runs.append(
                        {
                            'run_id': summary.run_id,
                            'task': summary.task,
                            'status': summary.status,
                            'pending_approval': pending,
                        }
                    )
            tui._print_json(pending_runs)
            return True
        tui.output_fn(f"error: unknown approvals subcommand '{sub}'")
        return True
    if action == 'ask':
        if not args:
            tui.output_fn('error: ask requires a task')
            return True
        clarify_first = args[0] == '--clarify'
        task_args = args[1:] if clarify_first else args
        if not task_args:
            tui.output_fn('error: ask --clarify requires a task')
            return True
        try:
            tui._run_agent_task(' '.join(task_args), clarify_first=clarify_first)
        except Exception as exc:
            tui._print_json({'error': str(exc), 'status': 'failed:system'})
        return True
    if action == 'clarify':
        if not args:
            tui.output_fn('error: clarify requires a task')
            return True
        tui._print_json(clarify_task(' '.join(args)).to_dict())
        return True
    if action == 'context':
        from teaagent.ergonomics.context_inject import list_at_candidates

        prefix = args[0] if args else ''
        paths = list_at_candidates(tui.root, prefix=prefix)
        tui._print_json({'prefix': prefix or None, 'paths': paths})
        return True
    if action == 'preflight':
        if not args:
            tui.output_fn('error: preflight requires a task')
            return True
        from teaagent.ergonomics.context_inject import expand_at_references

        task, _refs = expand_at_references(' '.join(args), root=tui.root)
        report = preflight(
            task,
            root=tui.root,
            provider=tui.provider,
            model=tui.model,
            permission_mode=tui.permission_mode,
            route=tui.route_model_enabled,
        )
        tui._print_json(report.to_dict())
        return True
    if action == 'plan':
        if not args:
            tui.output_fn('error: plan requires a task')
            return True
        from teaagent.ergonomics.context_inject import expand_at_references
        from teaagent.plan import write_plan_artifact

        plan_task, _refs = expand_at_references(' '.join(args), root=tui.root)
        report = preflight(
            plan_task,
            root=tui.root,
            provider=tui.provider,
            model=tui.model,
            permission_mode=tui.permission_mode,
            route=tui.route_model_enabled,
        )
        artifact = write_plan_artifact(report, root=tui.root)
        payload = report.to_dict()
        payload['plan_artifact'] = str(artifact)
        tui.output_fn(f'plan saved: {artifact}')
        tui._print_json(payload)
        return True
    if action in {'run', 'permissions', 'undo', 'mcp'}:
        if action == 'run':
            if not args:
                tui.output_fn('error: run requires a task')
                return True
            try:
                tui._run_agent_task(' '.join(args))
            except Exception as exc:
                tui._print_json({'error': str(exc), 'status': 'failed:system'})
            return True
        if action == 'permissions':
            from teaagent.ergonomics.approval_store import ApprovalPresetStore

            approval_store = ApprovalPresetStore(tui.root)
            tui._print_json([grant.to_dict() for grant in approval_store.list_grants()])
            return True
        if action == 'mcp':
            tui.output_fn(
                'mcp: run `teaagent doctor mcp --wizard` or `teaagent mcp serve` from a shell'
            )
            return True
        from teaagent.run_undo import UndoJournal

        run_store = RunStore(tui.root)
        run_id = args[0] if args else run_store.latest_run_with_undo()
        if run_id is None:
            tui.output_fn('error: no undo journal found for recent runs')
            return True
        undo_path = run_store.undo_path(run_id)
        if not undo_path.is_file():
            tui.output_fn(f'error: no undo journal for run {run_id}')
            return True
        journal = UndoJournal(tui.root, path=undo_path)
        restore_result = journal.restore()
        status = 'restored' if restore_result.ok else 'partial'
        audit_recorded = run_store.record_undo_applied(
            run_id,
            status=status,
            restored=restore_result.restored,
            deleted=restore_result.deleted,
            errors=restore_result.errors,
            undo_journal_path=undo_path.resolve()
            .relative_to(run_store.root)
            .as_posix(),
        )
        if restore_result.ok:
            undo_path.unlink(missing_ok=True)
        tui._print_json(
            {
                'status': status,
                'run_id': run_id,
                'restored': restore_result.restored,
                'deleted': restore_result.deleted,
                'errors': restore_result.errors,
                'audit_recorded': audit_recorded,
            }
        )
        return True
    if action == 'daily':
        from teaagent.ergonomics.context_inject import expand_at_references

        daily_task: str | None = ' '.join(args) if args else None
        if daily_task:
            daily_task, _refs = expand_at_references(daily_task, root=tui.root)
        brief = build_daily_brief(
            task=daily_task,
            root=tui.root,
            provider=tui.provider,
            model=tui.model,
            permission_mode=tui.permission_mode,
            route=tui.route_model_enabled,
        )
        payload = brief.to_dict()
        from teaagent.ergonomics.human_output import format_readiness_summary

        tui.output_fn(
            f'daily: ready={payload["ready"]} '
            f'token={payload["token_budget"]["usage_level"]} '
            f'runs={len(payload["recent_runs"])}'
        )
        for line in format_readiness_summary(
            payload, root=str(tui.root), title='TeaAgent daily'
        ).splitlines():
            tui.output_fn(line)
        for recommendation in payload['recommendations'][:1]:
            tui.output_fn(f'next: {recommendation["command"]}')
        tui._print_json(payload)
        return True
    if action == 'memory':
        tui._handle_memory(args)
        return True
    if action == 'runs':
        store = RunStore(tui.root)
        tui._print_json([summary.to_dict() for summary in store.list_runs()])
        return True
    if action == 'show':
        if len(args) != 1:
            tui.output_fn('error: show requires a run id')
            return True
        tui._print_json(RunStore(tui.root).show_run(args[0]))
        return True
    if action == 'resume':
        if len(args) != 1:
            tui.output_fn('error: resume requires a run id')
            return True
        store = RunStore(tui.root)
        try:
            original_task = store.task_for_run(args[0])
            observations = store.observations_for_run(args[0])
            pending = store.pending_approval_for_run(args[0])
        except (FileNotFoundError, ValueError) as exc:
            tui.output_fn(f'error: {exc}')
            return True
        if pending:
            from teaagent.ergonomics.approval_store import ApprovalPresetStore

            approval_store = ApprovalPresetStore(tui.root)
            digest = pending.get('argument_digest')
            if not digest:
                tui.output_fn(
                    f"warning: pending call '{pending['call_id']}' is a legacy record and "
                    f'cannot be auto-approved safely. Please approve it interactively.'
                )
            else:
                if not approval_store.check_scoped_approval_digest(
                    run_id=args[0],
                    call_id=pending['call_id'],
                    tool_name=pending['tool_name'],
                    argument_digest=digest,
                ):
                    approval_store.add_scoped_approval(
                        run_id=args[0],
                        call_id=pending['call_id'],
                        tool_name=pending['tool_name'],
                        arguments=pending['arguments'],
                        argument_digest=digest,
                    )
                tui.output_fn(
                    f'auto-approved pending call (run-scoped exact-match): {pending["call_id"]}'
                )
        tui.output_fn(f'resume: {args[0]}')
        tui._run_agent_task(
            original_task,
            initial_observations=observations if observations else None,
            resumed_from=args[0],
        )
        return True
    if action == 'use':
        if len(args) != 1:
            tui.output_fn('error: use requires exactly one database path')
            return True
        tui.database = args[0]
        tui._store = None
        tui.output_fn(f'database: {tui.database}')
        return True
    if action == 'smoke':
        try:
            graph_store = tui._get_store()
            graph_store.graph.upsert_node(
                'teaagent', {'name': 'TeaAgent'}, label='SmokeTest'
            )
            tui._print_json(graph_store.query('MATCH (n:SmokeTest) RETURN n.name'))
        except (GraphQLiteRuntimeError, GraphQLiteUnavailableError) as exc:
            tui.output_fn(f'error: {exc}')
        return True
    if action == 'query':
        if not args:
            tui.output_fn('error: query requires a Cypher string')
            return True
        try:
            tui._print_json(tui._get_store().query(' '.join(args)))
        except (GraphQLiteRuntimeError, GraphQLiteUnavailableError) as exc:
            tui.output_fn(f'error: {exc}')
        return True

    if tui.chat:
        return _handle_tui_command(tui, f'ask {raw_command}')
    tui.output_fn(f"error: unknown command '{action}'. Type 'help'.")
    return True

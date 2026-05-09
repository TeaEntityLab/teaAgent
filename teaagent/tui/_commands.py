from __future__ import annotations

import shlex
from pathlib import Path
from typing import TYPE_CHECKING

from teaagent.graphqlite_store import check_graphqlite_runtime
from teaagent.intent import clarify_task
from teaagent.llm import available_providers
from teaagent.model_routing import route_model
from teaagent.policy import parse_permission_mode
from teaagent.preflight import preflight
from teaagent.run_store import RunStore

if TYPE_CHECKING:
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
    args = parts[1:]
    if action in {'exit', 'quit'}:
        tui.output_fn('bye')
        return False
    if action == 'help':
        tui.output_fn(tui.help_text.rstrip())
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
        return True
    if action == 'model':
        if len(args) != 1:
            tui.output_fn("error: model requires a model name or 'default'")
            return True
        tui.model = None if args[0] == 'default' else args[0]
        tui.output_fn(f'model: {tui.model or "default"}')
        return True
    if action == 'route-model':
        if len(args) != 1 or args[0] not in {'on', 'off'}:
            tui.output_fn("error: route-model requires 'on' or 'off'")
            return True
        tui.route_model_enabled = args[0] == 'on'
        tui.output_fn(f'route-model: {"on" if tui.route_model_enabled else "off"}')
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
        return True
    if action == 'destructive':
        if len(args) != 1 or args[0] not in {'on', 'off'}:
            tui.output_fn("error: destructive requires 'on' or 'off'")
            return True
        tui.allow_destructive = args[0] == 'on'
        tui.output_fn(f'destructive: {"on" if tui.allow_destructive else "off"}')
        return True
    if action == 'progress':
        if len(args) != 1 or args[0] not in {'on', 'off'}:
            tui.output_fn("error: progress requires 'on' or 'off'")
            return True
        tui.progress = args[0] == 'on'
        tui.output_fn(f'progress: {"on" if tui.progress else "off"}')
        return True
    if action == 'stream':
        if len(args) != 1 or args[0] not in {'on', 'off'}:
            tui.output_fn("error: stream requires 'on' or 'off'")
            return True
        tui.stream = args[0] == 'on'
        tui.output_fn(f'stream: {"on" if tui.stream else "off"}')
        return True
    if action == 'subagent':
        if len(args) != 1 or args[0] not in {'on', 'off'}:
            tui.output_fn("error: subagent requires 'on' or 'off'")
            return True
        tui.subagent = args[0] == 'on'
        tui.output_fn(f'subagent: {"on" if tui.subagent else "off"}')
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
        tui._print_json(sorted(tui.approved_call_ids))
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
        tui._run_agent_task(' '.join(task_args), clarify_first=clarify_first)
        return True
    if action == 'clarify':
        if not args:
            tui.output_fn('error: clarify requires a task')
            return True
        tui._print_json(clarify_task(' '.join(args)).to_dict())
        return True
    if action == 'preflight':
        if not args:
            tui.output_fn('error: preflight requires a task')
            return True
        report = preflight(
            ' '.join(args),
            root=tui.root,
            provider=tui.provider,
            model=tui.model,
            permission_mode=tui.permission_mode,
            route=tui.route_model_enabled,
        )
        tui._print_json(report.to_dict())
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
            tui.approved_call_ids.add(pending['call_id'])
            tui.output_fn(f'auto-approved pending call: {pending["call_id"]}')
        tui.output_fn(f'resume: {args[0]}')
        tui._run_agent_task(
            original_task,
            initial_observations=observations if observations else None,
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
        graph_store = tui._get_store()
        graph_store.graph.upsert_node(
            'teaagent', {'name': 'TeaAgent'}, label='SmokeTest'
        )
        tui._print_json(graph_store.query('MATCH (n:SmokeTest) RETURN n.name'))
        return True
    if action == 'query':
        if not args:
            tui.output_fn('error: query requires a Cypher string')
            return True
        tui._print_json(tui._get_store().query(' '.join(args)))
        return True

    tui.output_fn(f"error: unknown command '{action}'. Type 'help'.")
    return True

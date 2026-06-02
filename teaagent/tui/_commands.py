from __future__ import annotations

import difflib
import logging
import shlex
import subprocess
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
from teaagent.model_routing import analyze_complexity, estimate_tokens, route_model
from teaagent.policy import parse_permission_mode
from teaagent.preflight import preflight
from teaagent.run_store import RunStore
from teaagent.sandbox import (
    GitSandboxResult,
    ParallelExperimentStack,
    abort_merge,
    get_conflicted_files,
    resolve_conflict_accept_ours,
    resolve_conflict_accept_theirs,
)

logger = logging.getLogger(__name__)

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

    # Dispatch to command handler
    handler = _COMMAND_DISPATCH.get(action)
    if handler:
        return handler(tui, args)

    # Handle chat mode fallback
    if tui.chat:
        return _handle_tui_command(tui, f'ask {raw_command}')

    tui.output_fn(f"error: unknown command '{action}'. Type 'help'.")
    return True


def _cmd_exit(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle exit/quit commands."""
    tui.output_fn('bye')
    return False


def _cmd_help(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle help command."""
    tui.output_fn(tui.help_text.rstrip())
    return True


def _cmd_setup(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle setup command."""
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


def _cmd_doctor(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle doctor command."""
    ok, message = check_graphqlite_runtime(tui.database)
    tui._print_json({'ok': ok, 'message': message})
    return True


def _cmd_provider(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle provider command."""
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


def _cmd_model(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle model command."""
    if len(args) != 1:
        tui.output_fn("error: model requires a model name or 'default'")
        return True
    tui.model = None if args[0] == 'default' else args[0]
    tui.output_fn(f'model: {tui.model or "default"}')
    tui._save_tui_state()
    return True


def _cmd_route_model(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle route-model command."""
    if len(args) != 1 or args[0] not in {'on', 'off'}:
        tui.output_fn("error: route-model requires 'on' or 'off'")
        return True
    tui.route_model_enabled = args[0] == 'on'
    tui.output_fn(f'route-model: {"on" if tui.route_model_enabled else "off"}')
    tui._save_tui_state()
    return True


def _cmd_root(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle root command."""
    if len(args) != 1:
        tui.output_fn('error: root requires exactly one path')
        return True
    tui.root = Path(args[0]).resolve()
    tui.output_fn(f'root: {tui.root}')
    tui._save_tui_state()
    return True


def _cmd_destructive(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle destructive command."""
    if len(args) != 1 or args[0] not in {'on', 'off'}:
        tui.output_fn("error: destructive requires 'on' or 'off'")
        return True
    tui.allow_destructive = args[0] == 'on'
    tui.output_fn(f'destructive: {"on" if tui.allow_destructive else "off"}')
    tui._save_tui_state()
    return True


def _cmd_progress(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle progress command."""
    if len(args) != 1 or args[0] not in {'on', 'off'}:
        tui.output_fn("error: progress requires 'on' or 'off'")
        return True
    tui.progress = args[0] == 'on'
    tui.output_fn(f'progress: {"on" if tui.progress else "off"}')
    tui._save_tui_state()
    return True


def _cmd_stream(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle stream command."""
    if len(args) != 1 or args[0] not in {'on', 'off'}:
        tui.output_fn("error: stream requires 'on' or 'off'")
        return True
    tui.stream = args[0] == 'on'
    tui.output_fn(f'stream: {"on" if tui.stream else "off"}')
    tui._save_tui_state()
    return True


def _cmd_subagent(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle subagent command."""
    if len(args) != 1 or args[0] not in {'on', 'off'}:
        tui.output_fn("error: subagent requires 'on' or 'off'")
        return True
    tui.subagent = args[0] == 'on'
    tui.output_fn(f'subagent: {"on" if tui.subagent else "off"}')
    tui._save_tui_state()
    return True


def _cmd_chat(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle chat command."""
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


def _cmd_heartbeat(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle heartbeat command."""
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


def _cmd_permission(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle permission command."""
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


def _cmd_approve(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle approve command."""
    if len(args) != 1:
        tui.output_fn('error: approve requires one call id')
        return True
    tui.approved_call_ids.add(args[0])
    tui.output_fn(f'approved: {args[0]}')
    return True


def _cmd_unapprove(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle unapprove command."""
    if len(args) != 1:
        tui.output_fn('error: unapprove requires one call id')
        return True
    tui.approved_call_ids.discard(args[0])
    tui.output_fn(f'unapproved: {args[0]}')
    return True


def _cmd_approvals(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle approvals command."""
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


def _cmd_memory(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle memory command."""
    tui._handle_memory(args)
    return True


def _cmd_runs(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle runs command."""
    store = RunStore(tui.root)
    tui._print_json([summary.to_dict() for summary in store.list_runs()])
    return True


def _cmd_show(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle show command."""
    if len(args) != 1:
        tui.output_fn('error: show requires a run id')
        return True
    tui._print_json(RunStore(tui.root).show_run(args[0]))
    return True


def _cmd_use(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle use command."""
    if len(args) != 1:
        tui.output_fn('error: use requires exactly one database path')
        return True
    tui.database = args[0]
    tui._store = None
    tui.output_fn(f'database: {tui.database}')
    return True


def _cmd_smoke(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle smoke command."""
    try:
        graph_store = tui._get_store()
        graph_store.graph.upsert_node(
            'teaagent', {'name': 'TeaAgent'}, label='SmokeTest'
        )
        tui._print_json(graph_store.query('MATCH (n:SmokeTest) RETURN n.name'))
    except (GraphQLiteRuntimeError, GraphQLiteUnavailableError) as exc:
        tui.output_fn(f'error: {exc}')
    return True


def _cmd_query(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle query command."""
    if not args:
        tui.output_fn('error: query requires a Cypher string')
        return True
    try:
        tui._print_json(tui._get_store().query(' '.join(args)))
    except (GraphQLiteRuntimeError, GraphQLiteUnavailableError) as exc:
        tui.output_fn(f'error: {exc}')
    return True


def _cmd_pin(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle pin command."""
    tui._handle_pin(args)
    return True


def _cmd_unpin(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle unpin command."""
    tui._handle_unpin(args)
    return True


def _cmd_pinned(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle pinned command."""
    tui._handle_pinned()
    return True


def _cmd_compact(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle compact command."""
    tui._handle_compact()
    return True


def _cmd_cost(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle cost command."""
    tui._handle_cost()
    return True


def _cmd_effort(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle effort command."""
    tui._handle_effort(args)
    return True


def _cmd_budget(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle budget command."""
    tui._handle_budget()
    return True


def _cmd_checkpoint(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle checkpoint command."""
    tui._handle_checkpoint()
    return True


def _cmd_undo(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle undo command."""
    tui._handle_undo()
    return True


def _cmd_background(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle background command."""
    tui._handle_background()
    return True


def _cmd_handoff(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle handoff command."""
    tui._handle_background()
    return True


# Command dispatch dictionary
_COMMAND_DISPATCH: dict[str, callable] = {
    'exit': _cmd_exit,
    'quit': _cmd_exit,
    'help': _cmd_help,
    'setup': _cmd_setup,
    'doctor': _cmd_doctor,
    'provider': _cmd_provider,
    'model': _cmd_model,
    'route-model': _cmd_route_model,
    'root': _cmd_root,
    'destructive': _cmd_destructive,
    'progress': _cmd_progress,
    'stream': _cmd_stream,
    'subagent': _cmd_subagent,
    'chat': _cmd_chat,
    'heartbeat': _cmd_heartbeat,
    'permission': _cmd_permission,
    'approve': _cmd_approve,
    'unapprove': _cmd_unapprove,
    'approvals': _cmd_approvals,
    'memory': _cmd_memory,
    'runs': _cmd_runs,
    'show': _cmd_show,
    'use': _cmd_use,
    'smoke': _cmd_smoke,
    'query': _cmd_query,
    'pin': _cmd_pin,
    'unpin': _cmd_unpin,
    'pinned': _cmd_pinned,
    'compact': _cmd_compact,
    'cost': _cmd_cost,
    'effort': _cmd_effort,
    'budget': _cmd_budget,
    'checkpoint': _cmd_checkpoint,
    'undo': _cmd_undo,
    'background': _cmd_background,
    'handoff': _cmd_handoff,
    'route': _cmd_route,
    'complexity': _cmd_complexity,
    'estimate': _cmd_estimate,
    'session': _cmd_session,
    'status': _cmd_status,
    'ask': _cmd_ask,
    'clarify': _cmd_clarify,
    'context': _cmd_context,
    'preflight': _cmd_preflight,
    'plan': _cmd_plan,
    'run': _cmd_run,
    'permissions': _cmd_permissions,
    'mcp': _cmd_mcp,
    'undo': _cmd_undo,
    'daily': _cmd_daily,
    'resume': _cmd_resume,
    'parallel': _cmd_parallel,
    'select': _cmd_select,
    'cancel': _cmd_cancel,
    'conflict': _cmd_conflict,
    'o': _cmd_conflict_accept_ours,
    't': _cmd_conflict_accept_theirs,
    'n': _cmd_conflict_next,
    'p': _cmd_conflict_prev,
    'a': _cmd_conflict_abort,
}

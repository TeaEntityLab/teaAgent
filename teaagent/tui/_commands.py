from __future__ import annotations

import logging
import shlex
import typing
from pathlib import Path
from typing import TYPE_CHECKING

from teaagent.approval import parse_permission_mode
from teaagent.graphqlite_store import (
    GraphQLiteRuntimeError,
    GraphQLiteUnavailableError,
    check_graphqlite_runtime,
)
from teaagent.llm import available_providers
from teaagent.run_store import RunStore

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from teaagent.tui import TeaAgentTUI


def _safe_run_agent_task(
    tui: 'TeaAgentTUI',
    task: str,
    clarify_first: bool = False,
    resumed_from: str | None = None,
    initial_observations: list[dict[str, object]] | None = None,
    initial_context_extra: dict[str, object] | None = None,
) -> None:
    """Run _run_agent_task with error guard to prevent TUI crash on adapter/network errors.

    Without this wrapper, an unhandled exception from the chat agent (e.g. network
    failure, API error, corrupt store) would propagate up and crash the TUI loop.
    """
    try:
        tui._run_agent_task(
            task,
            clarify_first=clarify_first,
            resumed_from=resumed_from,
            initial_observations=initial_observations,
            initial_context_extra=initial_context_extra,
        )
    except (OSError, ValueError, TypeError, RuntimeError) as exc:
        tui.output_fn(f'error: agent task failed — {exc}')


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

    # Handle chat mode fallback: unknown command → prompt before forwarding as task
    if tui.chat:
        return _handle_unknown_chat_command(tui, raw_command)

    tui.output_fn(f"error: unknown command '{action}'. Type 'help'.")
    return True


def _handle_unknown_chat_command(tui: 'TeaAgentTUI', raw_command: str) -> bool:
    """Prompt user before forwarding an unknown command as a task in chat mode."""
    command = raw_command.strip()
    prompt_text = f'unknown command "{command}"; send as task? [y/N] '
    if tui.input_fn is None:
        tui.output_fn(prompt_text + 'declined (non-interactive)')
        return True
    try:
        answer = tui.input_fn(prompt_text)
    except EOFError:
        tui.output_fn(prompt_text + 'declined (EOF)')
        return True
    if answer.strip().lower() in ('y', 'yes'):
        _safe_run_agent_task(tui, command)
        return True
    tui.output_fn(prompt_text + 'declined')
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
    tui._root_explicit = True
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
    """Handle progress command: toggle on/off or show run progress."""
    if len(args) == 1 and args[0] in {'on', 'off'}:
        tui.progress = args[0] == 'on'
        tui.output_fn(f'progress: {"on" if tui.progress else "off"}')
        tui._save_tui_state()
        return True
    if len(args) == 1:
        run_id = args[0]
        store = RunStore(tui.root)
        from teaagent.run_progress import (
            build_run_progress_summary,
            format_run_progress_summary,
        )

        try:
            summary = build_run_progress_summary(store, run_id)
            tui.output_fn(format_run_progress_summary(summary))
            return True
        except FileNotFoundError:
            tui.output_fn(f'error: run {run_id} not found')
            return True
    tui.output_fn("error: progress requires 'on', 'off', or a run_id")
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
    """Handle approve command: `approve <call_id>` or `approve --selector N [--resume]`."""
    resume = '--resume' in args
    args = [arg for arg in args if arg != '--resume']
    call_id: str | None = None

    if len(args) >= 2 and args[0] == '--selector':
        try:
            selector = int(args[1])
        except ValueError:
            tui.output_fn(f'error: selector must be an integer, got {args[1]!r}')
            return True
        store = RunStore(tui.root)
        from teaagent.approval.selectors import (
            collect_pending_approval_views,
            resolve_selector,
        )

        views = collect_pending_approval_views(store)
        if not views:
            tui.output_fn('error: no pending approvals')
            return True
        view = resolve_selector(views, selector)
        if view is None:
            tui.output_fn(f'error: selector {selector} out of range (1..{len(views)})')
            return True
        call_id = view.call_id
        selector_label = f' (via selector {selector})'
    elif len(args) == 1:
        call_id = args[0]
        selector_label = ''
    else:
        tui.output_fn('error: approve requires one call id or --selector N')
        return True

    from teaagent.integration.approval_parity import grant_pending_approval

    grant = grant_pending_approval(tui.root, call_id)
    if grant is not None:
        tui.approved_call_ids.add(call_id)
        tui.output_fn(f'approved: {call_id}{selector_label}')
        if resume:
            return _handle_tui_command(tui, f'resume {grant["run_id"]}')
        return True

    # Session pre-approval: track call_id in-memory until the tool call arrives.
    # Persisted scoped approvals still require a pending request (grant above).
    tui.approved_call_ids.add(call_id)
    tui.output_fn(f'approved: {call_id}{selector_label}')
    return True


def _cmd_receipt(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle receipt command: `receipt <run_id>`."""
    if len(args) != 1:
        tui.output_fn('error: receipt requires a run id')
        return True
    store = RunStore(tui.root)
    from teaagent.run_receipt import build_run_receipt

    tui.output_fn(build_run_receipt(store, args[0], tui.root))
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
        from teaagent.integration.approval_parity import (
            build_pending_approvals_snapshot,
        )

        run_store = RunStore(tui.root)
        tui._print_json(build_pending_approvals_snapshot(run_store, limit=20))
        return True
    tui.output_fn(f"error: unknown approvals subcommand '{sub}'")
    return True


def _cmd_memory(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle memory command."""
    tui._handle_memory(args)
    return True


def _cmd_runs(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle runs command."""
    run_store = RunStore(tui.root)
    tui._print_json([summary.to_dict() for summary in run_store.list_runs()])
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


def _cmd_pressure(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle pressure command — print context pressure score as JSON."""
    try:
        from teaagent.context_pressure import compute_context_pressure

        score = compute_context_pressure(tui.root)
        import json

        tui.output_fn(json.dumps(score.to_dict(), indent=2))
    except Exception as exc:
        tui.output_fn(f'error: could not compute context pressure — {exc}')
    return True


def _cmd_background(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle background command."""
    tui._handle_background()
    return True


def _cmd_handoff(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle handoff command — alias for suspension checkpoint (NOT background execution)."""
    tui.output_fn(
        'handoff: /handoff is a suspension checkpoint alias (not background execution). '
        'This is the same as the background command — it creates a suspension checkpoint.'
    )
    tui._handle_background()
    return True


def _cmd_skills(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle skills command — print loaded skill details as JSON."""
    from teaagent.skill_loader import explain_skill_activation

    explain = explain_skill_activation(tui.root, skill_prompt_mode='index_only')
    tui._print_json(explain.to_dict())
    return True


def _cmd_artifact(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle artifact command — read or list stored tool result artifacts."""
    if not args:
        tui.output_fn('error: artifact requires a subcommand (read or list)')
        return True

    sub = args[0]
    rest = args[1:]

    if sub == 'read':
        return _cmd_artifact_read(tui, rest)
    if sub == 'list':
        return _cmd_artifact_list(tui, rest)

    tui.output_fn(f"error: unknown artifact subcommand '{sub}'")
    return True


def _cmd_artifact_read(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle artifact read — read stored artifact content."""
    from teaagent.long_result_envelope import readback_artifact

    if len(args) < 2:
        tui.output_fn('error: artifact read requires <run_id> <tool_call_id>')
        return True

    run_id = args[0]
    tool_call_id = args[1]
    cursor: str | None = None
    max_bytes: int = 50_000

    i = 2
    while i < len(args):
        if args[i] == '--cursor' and i + 1 < len(args):
            cursor = args[i + 1]
            if not cursor.startswith('offset:'):
                tui.output_fn(
                    f"error: --cursor must have format 'offset:<N>', got '{cursor}'"
                )
                return True
            try:
                int(cursor[len('offset:') :])
            except ValueError:
                tui.output_fn(f"error: invalid cursor offset '{cursor}'")
                return True
            i += 2
        elif args[i] == '--max-bytes' and i + 1 < len(args):
            try:
                max_bytes = int(args[i + 1])
            except ValueError:
                tui.output_fn(f"error: invalid --max-bytes value '{args[i + 1]}'")
                return True
            if max_bytes <= 0:
                tui.output_fn(f'error: --max-bytes must be positive, got {max_bytes}')
                return True
            i += 2
        else:
            tui.output_fn(f"error: unexpected argument '{args[i]}'")
            return True

    artifact_path = f'.teaagent/artifacts/tool-results/{run_id}/{tool_call_id}.txt'
    try:
        content = readback_artifact(
            tui.root, artifact_path, cursor=cursor, max_bytes=max_bytes
        )
    except (FileNotFoundError, OSError, ValueError) as exc:
        tui.output_fn(f'error: {exc}')
        return True

    tui.output_fn(content)
    return True


def _cmd_skill_diagnostics(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle skill-diagnostics command — print comprehensive skill diagnostics as JSON."""
    from teaagent.skill_loader import get_skill_diagnostics

    try:
        diagnostics = get_skill_diagnostics(tui.root)
    except Exception as exc:
        tui.output_fn(f'error: skill diagnostics failed — {exc}')
        return True

    iso_status = diagnostics.get('isolation_status', {})
    downgrade_label = iso_status.get('downgrade_label', '')
    if downgrade_label == 'native-execution-fallback':
        tui.output_fn(
            '\033[93m[WARN] Skill isolation degraded: native execution fallback active. '
            'No WASM or Docker sandbox available. Skills run on host OS.\033[0m'
        )
    elif downgrade_label == 'partial-isolation':
        tui.output_fn(
            '\033[93m[WARN] Partial skill isolation: not all sandbox backends available.\033[0m'
        )
    tui._print_json(diagnostics)
    return True


def _cmd_skill_health(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    from teaagent.skill_loader import get_skill_health

    try:
        health = get_skill_health(tui.root)
    except Exception as exc:
        tui.output_fn(f'error: skill health failed — {exc}')
        return True
    tui._print_json(health)
    return True


def _cmd_artifact_list(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle artifact list — list stored artifacts grouped by run_id."""
    import json

    artifact_dir = tui.root / '.teaagent' / 'artifacts' / 'tool-results'
    if not artifact_dir.is_dir():
        tui.output_fn('{}')
        return True

    runs: dict[str, list[dict[str, object]]] = {}
    for run_dir in sorted(artifact_dir.iterdir()):
        if not run_dir.is_dir():
            continue
        run_id = run_dir.name
        files = []
        for artifact_file in sorted(run_dir.iterdir()):
            if not artifact_file.is_file():
                continue
            tool_call_id = artifact_file.stem
            try:
                size = artifact_file.stat().st_size
            except OSError:
                size = 0
            files.append(
                {
                    'tool_call_id': tool_call_id,
                    'path': str(artifact_file.relative_to(tui.root)),
                    'bytes': size,
                }
            )
        if files:
            runs[run_id] = files

    tui.output_fn(json.dumps(runs, indent=2))
    return True


def _cmd_conflict_shortcut(tui: 'TeaAgentTUI', args: list[str], shortcut: str) -> bool:
    """Handle conflict resolution shortcut keys."""
    shortcuts = {
        'o': 'accept_ours',
        't': 'accept_theirs',
        'n': 'next_conflict',
        'p': 'prev_conflict',
        'a': 'abort_conflict',
    }
    tui._print_json(
        {
            'status': 'not_available',
            'shortcut': shortcut,
            'action': shortcuts[shortcut],
            'message': 'Conflict resolution shortcuts are not available',
            'hint': 'Use git tools: git checkout --ours/theirs, git diff, etc.',
        }
    )
    return True


def _cmd_ask_run(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle ask/run command."""
    if not args or args[0] == '--clarify':
        if len(args) < 2 or (args[0] == '--clarify' and len(args) < 2):
            tui.output_fn('error: ask requires a task')
            return True
        # Handle ask --clarify
        if args[0] == '--clarify':
            task = ' '.join(args[1:])
            _safe_run_agent_task(tui, task, clarify_first=True)
            return True
    task = ' '.join(args)
    _safe_run_agent_task(tui, task)
    return True


def _cmd_clarify(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle clarify command."""
    if not args:
        tui.output_fn('error: clarify requires a task')
        return True
    from teaagent.intent import clarify_task

    task = ' '.join(args)
    clarification = clarify_task(task)
    tui._print_json(clarification.to_dict())
    return True


def _cmd_preflight(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle preflight command."""
    if not args:
        tui.output_fn('error: preflight requires a task')
        return True
    task = ' '.join(args)
    from teaagent.preflight import preflight

    report = preflight(
        task,
        root=tui.root,
        provider=tui.provider or 'gpt',
        model=tui.model,
        permission_mode=tui.permission_mode,
        route=tui.route_model_enabled,
        memory_limit=tui.memory_limit,
    )
    tui._print_json(report.to_dict())
    return True


def _cmd_route(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle route command."""
    if not args:
        tui.output_fn('error: route requires a task')
        return True
    from teaagent.model_routing import route_model

    task = ' '.join(args)
    provider = tui.provider or 'gpt'
    routing = (
        route_model(task, provider=provider, model=tui.model)
        if tui.route_model_enabled
        else None
    )
    if routing:
        tui._print_json(routing.to_dict())
    else:
        tui._print_json({'model': tui.model or 'default', 'task': task})
    return True


def _cmd_complexity(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle complexity command."""
    if not args:
        tui.output_fn('error: complexity requires a task')
        return True
    from teaagent.model_routing import analyze_complexity

    task = ' '.join(args)
    complexity = analyze_complexity(task)
    tui._print_json({'complexity': complexity, 'task': task})
    return True


def _cmd_estimate(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle estimate command."""
    if not args:
        tui.output_fn('error: estimate requires a task')
        return True
    from teaagent.model_routing import estimate_tokens

    task = ' '.join(args)
    estimate = estimate_tokens(task, complexity='medium')
    tui._print_json({'estimate': estimate, 'task': task})
    return True


def _cmd_session(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle session command."""
    if not args:
        tui.output_fn(
            'error: session requires a subcommand (new, list, switch, clear, show)'
        )
        return True
    subcommand = args[0]
    if subcommand == 'new':
        tui._ensure_session()
        tui.output_fn(
            f'session new: {tui.session_id[:8] if tui.session_id else "none"}'
        )
    elif subcommand == 'list':
        store = tui._get_session_store()
        sessions = store.list_sessions()
        tui._print_json(sessions)
    elif subcommand == 'switch':
        if len(args) < 2:
            tui.output_fn('error: session switch requires a session id')
            return True
        tui.session_id = args[1]
        tui.output_fn(f'session: {tui.session_id[:8]}')
    elif subcommand == 'clear':
        session = tui._current_session()
        if session:
            session.messages.clear()
            tui._get_session_store().save(session)
            tui.output_fn('session cleared')
        else:
            tui.output_fn('error: no active session')
    elif subcommand == 'show':
        session = tui._current_session()
        if session:
            tui._print_json(session.to_dict())
    else:
        tui.output_fn(f"error: unknown session subcommand '{subcommand}'")
    return True


def _cmd_status(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle status command."""
    if not args:
        tui.output_fn('error: status requires a run id')
        return True
    run_id = args[0]
    run_store = RunStore(tui.root)
    try:
        tui._print_json(run_store.heartbeat_for_run(run_id))
    except FileNotFoundError:
        tui.output_fn(f"error: run '{run_id}' not found")
    return True


def _cmd_plan(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle plan command."""
    if not args:
        tui.output_fn('error: plan requires a task')
        return True
    task = ' '.join(args)
    from teaagent.intent import clarify_task

    try:
        clarification = clarify_task(task)
        tui._print_json(
            {
                'task': task,
                'plan': clarification.to_dict(),
                'status': 'clarification_generated',
            }
        )
    except Exception as e:
        tui._print_json({'task': task, 'plan': f'error: {str(e)}', 'status': 'error'})
    return True


def _cmd_permissions(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle permissions command."""
    from teaagent.ergonomics.approval_store import ApprovalPresetStore

    approval_store = ApprovalPresetStore(str(tui.root))
    presets = approval_store.list_presets()  # type: ignore[attr-defined]
    tui._print_json([p.to_dict() for p in presets])
    return True


def _cmd_mcp(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle mcp command."""
    tui.output_fn('error: mcp commands are run from the shell, not the TUI')
    return True


def _cmd_context(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle context command."""
    if not args:
        tui.output_fn('error: context requires a subcommand (list)')
        return True
    subcommand = args[0]
    if subcommand == 'list':
        tui._print_json([])
    else:
        tui.output_fn(f"error: unknown context subcommand '{subcommand}'")
    return True


def _cmd_daily(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle daily command."""
    task_str: str | None = ' '.join(args) if args else None
    from teaagent.daily import build_daily_brief

    provider = tui.provider or 'gpt'
    brief = build_daily_brief(
        task=task_str,
        root=tui.root,
        provider=provider,
        permission_mode=tui.permission_mode,
    )
    tui.output_fn(f'daily: ready={brief.ready}')
    tui._print_json(brief.to_dict())
    return True


def _cmd_resume(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle resume command."""
    if not args:
        tui.output_fn('error: resume requires a run id')
        return True
    run_id = args[0]
    from teaagent.ergonomics.workspace_defaults import load_workspace_defaults
    from teaagent.integration.resume_preparation import (
        ResumePreparationError,
        prepare_run_resume,
    )

    defaults = load_workspace_defaults(tui.root)
    auto_compact = bool(defaults.get('auto_compact_on_resume', True))
    try:
        prepared = prepare_run_resume(
            tui.root,
            run_id,
            approve_call_ids=frozenset(tui.approved_call_ids),
            auto_compact=auto_compact,
            auto_approve_pending=False,
        )
    except ResumePreparationError as exc:
        tui.output_fn(f'error: {exc}')
        return True

    if prepared.pending_warning:
        tui.output_fn(f'warning: {prepared.pending_warning}')
    elif prepared.auto_approved_call_id:
        tui.output_fn(
            f'resume: {run_id} (auto-approved pending call {prepared.auto_approved_call_id})'
        )
    else:
        tui.output_fn(f'resume: {run_id}')
    _safe_run_agent_task(
        tui,
        prepared.original_task,
        resumed_from=prepared.run_id,
        initial_observations=prepared.initial_observations,
        initial_context_extra=prepared.initial_context_extra,
    )
    return True


def _cmd_parallel(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle parallel command."""
    if not args:
        tui.output_fn('error: parallel requires at least one option')
        return True
    # Store parallel options for later selection
    tui._parallel_options = args
    tui._print_json(
        {
            'options': args,
            'count': len(args),
            'status': 'options_stored',
            'hint': 'use "select <index>" to choose an option',
        }
    )
    return True


def _cmd_select(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle select command."""
    if not args:
        tui.output_fn('error: select requires an option index or value')
        return True
    if not hasattr(tui, '_parallel_options') or not tui._parallel_options:
        tui.output_fn('error: no parallel options available. Use "parallel" first.')
        return True
    selection = args[0]
    try:
        # Try to parse as index
        index = int(selection)
        if 0 <= index < len(tui._parallel_options):
            selected = tui._parallel_options[index]
            tui._print_json(
                {'selected': selected, 'index': index, 'status': 'selected'}
            )
            tui._parallel_options = None  # Clear after selection
        else:
            tui.output_fn(
                f'error: index {index} out of range (0-{len(tui._parallel_options) - 1})'
            )
    except ValueError:
        # Try to match as value
        if tui._parallel_options and selection in tui._parallel_options:
            tui._print_json({'selected': selection, 'status': 'selected'})
            tui._parallel_options = None
        else:
            tui.output_fn(f'error: option "{selection}" not found in parallel options')
    return True


def _cmd_cancel(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle cancel command."""
    if hasattr(tui, '_parallel_options') and tui._parallel_options:
        tui._parallel_options = None
        tui._print_json({'status': 'cancelled', 'action': 'cleared_parallel_options'})
    else:
        tui._print_json({'status': 'cancelled', 'action': 'no_active_operation'})
    return True


def _cmd_conflict(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle conflict command."""
    tui._print_json(
        {
            'status': 'not_available',
            'message': 'Conflict resolution mode is not available',
            'hint': 'Use git tools directly for conflict resolution',
        }
    )
    return True


def _cmd_conflict_shortcut_o(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle conflict shortcut 'o'."""
    return _cmd_conflict_shortcut(tui, args, 'o')


def _cmd_conflict_shortcut_t(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle conflict shortcut 't'."""
    return _cmd_conflict_shortcut(tui, args, 't')


def _cmd_conflict_shortcut_n(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle conflict shortcut 'n'."""
    return _cmd_conflict_shortcut(tui, args, 'n')


def _cmd_conflict_shortcut_p(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle conflict shortcut 'p'."""
    return _cmd_conflict_shortcut(tui, args, 'p')


def _cmd_conflict_shortcut_a(tui: 'TeaAgentTUI', args: list[str]) -> bool:
    """Handle conflict shortcut 'a'."""
    return _cmd_conflict_shortcut(tui, args, 'a')


# Command dispatch dictionary
_COMMAND_DISPATCH: dict[str, typing.Callable[[TeaAgentTUI, list[str]], bool]] = {
    'artifact': _cmd_artifact,
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
    'receipt': _cmd_receipt,
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
    'skills': _cmd_skills,
    'skill-diagnostics': _cmd_skill_diagnostics,
    'skill-health': _cmd_skill_health,
    'a': _cmd_conflict_shortcut_a,
    'ask': _cmd_ask_run,
    'cancel': _cmd_cancel,
    'clarify': _cmd_clarify,
    'complexity': _cmd_complexity,
    'conflict': _cmd_conflict,
    'context': _cmd_context,
    'daily': _cmd_daily,
    'estimate': _cmd_estimate,
    'mcp': _cmd_mcp,
    'n': _cmd_conflict_shortcut_n,
    'o': _cmd_conflict_shortcut_o,
    'p': _cmd_conflict_shortcut_p,
    'parallel': _cmd_parallel,
    'permissions': _cmd_permissions,
    'plan': _cmd_plan,
    'preflight': _cmd_preflight,
    'resume': _cmd_resume,
    'route': _cmd_route,
    'run': _cmd_ask_run,
    'select': _cmd_select,
    'session': _cmd_session,
    'status': _cmd_status,
    't': _cmd_conflict_shortcut_t,
}

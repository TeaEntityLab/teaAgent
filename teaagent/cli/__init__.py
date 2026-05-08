from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Optional

from teaagent import __version__
from teaagent.chat_agent import ChatAgentConfig, run_chat_agent
from teaagent.graphqlite_store import (
    GraphQLiteConfig,
    GraphQLiteGraphStore,
    check_graphqlite_runtime,
)
from teaagent.intent import build_task_spec, clarify_task
from teaagent.llm import (
    LLMMessage,
    LLMRequest,
    available_providers,
    check_llm_configuration,
    create_llm_adapter,
)
from teaagent.llm_conformance import run_model_conformance
from teaagent.mcp_http import is_loopback_host, serve_mcp_http
from teaagent.mcp_server import serve_mcp_stdio
from teaagent.memory import MemoryCatalog
from teaagent.model_routing import route_model
from teaagent.policy import PermissionMode, parse_permission_mode
from teaagent.preflight import preflight
from teaagent.run_store import RunStore
from teaagent.runner import ApprovalRequest, RunResult
from teaagent.tui import run_tui
from teaagent.ultrawork import UltraworkStore
from teaagent.workspace_tools import build_workspace_tool_registry


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    apply_config_defaults(args)
    return args.func(args)


def build_parser() -> argparse.ArgumentParser:
    from teaagent.cli._agent_parsers import register as register_agent
    from teaagent.cli._mcp_parsers import register as register_mcp
    from teaagent.cli._memory_parsers import register as register_memory
    from teaagent.cli._misc_parsers import register as register_misc
    from teaagent.cli._model_parsers import register as register_model

    parser = argparse.ArgumentParser(
        prog='teaagent', description='TeaAgent harness utilities.'
    )
    parser.add_argument(
        '--version', action='version', version=f'teaagent {__version__}'
    )
    parser.add_argument(
        '--config',
        default=None,
        help='JSON config file with defaults such as root, model, provider, permission_mode.',
    )
    subparsers = parser.add_subparsers(dest='command', required=True)

    register_misc(
        subparsers,
        {
            'clarify': clarify_command,
            'tui': start_tui,
            'doctor_graphqlite': doctor_graphqlite,
            'doctor_model': doctor_model,
            'doctor_all': doctor_all,
            'graphqlite_query': graphqlite_query,
            'graphqlite_smoke': graphqlite_smoke,
            'ultrawork_start': ultrawork_start_command,
            'ultrawork_list': ultrawork_list_command,
            'ultrawork_show': ultrawork_show_command,
            'ultrawork_stop': ultrawork_stop_command,
            'workspace_tools': workspace_tools_metadata,
            'completion': completion_command,
            'audit_list': audit_list_command,
            'audit_show': audit_show_command,
            'audit_prune': audit_prune_command,
        },
    )
    register_memory(
        subparsers,
        {
            'add': memory_add_command,
            'list': memory_list_command,
            'search': memory_search_command,
            'show': memory_show_command,
        },
    )
    register_agent(
        subparsers,
        {
            'run': agent_run_task,
            'preflight': agent_preflight_command,
            'resume': agent_resume_command,
            'status': agent_status_command,
            'runs': agent_runs_list,
            'show': agent_run_show,
        },
    )
    register_model(
        subparsers,
        {
            'providers': model_providers,
            'smoke': model_smoke,
            'conformance': model_conformance,
            'route': model_route,
        },
    )
    register_mcp(
        subparsers,
        {
            'serve': mcp_serve_command,
        },
    )

    return parser


def apply_config_defaults(args: argparse.Namespace) -> None:
    config_path = getattr(args, 'config', None)
    if not config_path:
        return
    data = json.loads(Path(config_path).read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise SystemExit('--config must contain a JSON object')
    defaults = {
        'root': '.',
        'model': None,
        'provider': 'gpt',
        'permission_mode': PermissionMode.PROMPT.value,
    }
    for key, value in data.items():
        if not hasattr(args, key):
            continue
        if getattr(args, key) == defaults.get(key):
            setattr(args, key, value)


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------


def doctor_graphqlite(args: argparse.Namespace) -> int:
    ok, message = check_graphqlite_runtime(args.database)
    print(json.dumps({'ok': ok, 'message': message}, sort_keys=True))
    return 0 if ok else 1


def doctor_all(args: argparse.Namespace) -> int:
    checks: dict[str, Any] = {}
    gql_ok, gql_message = check_graphqlite_runtime(args.database)
    checks['graphqlite'] = {'ok': gql_ok, 'message': gql_message}
    provider_results = []
    for provider in args.provider or available_providers():
        ok, message = check_llm_configuration(provider)
        provider_results.append({'provider': provider, 'ok': ok, 'message': message})
    checks['providers'] = provider_results
    ok = gql_ok and all(item['ok'] for item in provider_results)
    print_json({'ok': ok, 'checks': checks})
    return 0 if ok else 1


def clarify_command(args: argparse.Namespace) -> int:
    print_json(clarify_task(args.task).to_dict())
    return 0


def memory_add_command(args: argparse.Namespace) -> int:
    entry = MemoryCatalog(args.root).add(args.content, tags=tuple(args.tag))
    print_json(entry.to_dict())
    return 0


def memory_list_command(args: argparse.Namespace) -> int:
    print_json(
        [entry.to_dict() for entry in MemoryCatalog(args.root).list(limit=args.limit)]
    )
    return 0


def memory_search_command(args: argparse.Namespace) -> int:
    print_json(
        [
            entry.to_dict()
            for entry in MemoryCatalog(args.root).search(args.query, limit=args.limit)
        ]
    )
    return 0


def memory_show_command(args: argparse.Namespace) -> int:
    print_json(MemoryCatalog(args.root).show(args.memory_id).to_dict())
    return 0


def agent_run_task(args: argparse.Namespace) -> int:
    return _execute_agent_task(args, args.task)


def agent_resume_command(args: argparse.Namespace) -> int:
    store = RunStore(args.root)
    try:
        original_task = store.task_for_run(args.run_id)
    except (FileNotFoundError, ValueError) as exc:
        print_json({'status': 'error', 'message': str(exc)})
        return 1

    initial_observations: list[dict[str, Any]] = []
    auto_approved: Optional[str] = None
    if not args.fresh_restart:
        initial_observations = store.observations_for_run(args.run_id)
        pending = store.pending_approval_for_run(args.run_id)
        if pending and pending['call_id'] not in args.approve_call_id:
            args.approve_call_id = list(args.approve_call_id) + [pending['call_id']]
            auto_approved = pending['call_id']

    return _execute_agent_task(
        args,
        original_task,
        resumed_from=args.run_id,
        initial_observations=initial_observations,
        auto_approved_call_id=auto_approved,
    )


def _execute_agent_task(
    args: argparse.Namespace,
    task: str,
    *,
    resumed_from: Optional[str] = None,
    initial_observations: Optional[list[dict[str, Any]]] = None,
    auto_approved_call_id: Optional[str] = None,
) -> int:
    task_spec = None
    if args.clarify:
        clarification = clarify_task(task)
        if clarification.needs_clarification:
            print_json(
                {
                    'status': 'needs_clarification',
                    'clarification': clarification.to_dict(),
                }
            )
            return 2
        task_spec = build_task_spec(task, clarification)

    routing = (
        route_model(task, provider=args.provider, model=args.model)
        if args.route_model
        else None
    )
    selected_model = routing.model if routing else args.model
    adapter = create_llm_adapter(args.provider, model=selected_model)
    store = RunStore(args.root)
    audit = store.audit_logger()

    # --- OpenTelemetry wiring ---
    _telemetry_sink = None
    if getattr(args, 'telemetry_otlp_endpoint', None) or getattr(
        args, 'telemetry_console', False
    ):
        try:
            from teaagent.telemetry import (
                TelemetryConfig,
                TracingHTTPTransport,
                configure_telemetry,
            )

            cfg = TelemetryConfig(
                service_name=getattr(args, 'telemetry_service_name', 'teaagent'),
                otlp_endpoint=getattr(args, 'telemetry_otlp_endpoint', None),
                console=getattr(args, 'telemetry_console', False),
            )
            _telemetry_sink, tracer = configure_telemetry(cfg)
            audit.add_sink(_telemetry_sink.handle_event)
            adapter = create_llm_adapter(
                args.provider,
                model=selected_model,
                transport=TracingHTTPTransport(adapter.transport, tracer),  # type: ignore[attr-defined]
            )
        except Exception as exc:
            print(f'Telemetry setup failed: {exc}', file=sys.stderr)
    # --- end telemetry wiring ---

    approval_handler = cli_approval_handler if args.hitl_approval else None
    result = run_chat_agent(
        task=task,
        adapter=adapter,
        config=ChatAgentConfig.from_root(
            args.root,
            max_iterations=args.max_iterations,
            max_tool_calls=args.max_tool_calls,
            allow_destructive=args.allow_destructive,
            model=selected_model,
            permission_mode=parse_permission_mode(args.permission_mode),
            approved_call_ids=frozenset(args.approve_call_id),
            enable_subagent=args.subagent,
            max_subagent_depth=args.max_subagent_depth,
            heartbeat_seconds=args.heartbeat,
            approval_handler=approval_handler,
        ),
        audit=audit,
        task_spec=task_spec,
        initial_observations=initial_observations,
    )
    store.logger_for_result(result, audit)
    if _telemetry_sink is not None:
        from contextlib import suppress

        with suppress(Exception):
            _telemetry_sink.force_flush()
    payload = run_result_payload(result, routing=routing.to_dict() if routing else None)
    if resumed_from:
        payload['resumed_from'] = resumed_from
        payload['task'] = task
        if initial_observations:
            payload['replayed_observations'] = len(initial_observations)
        if auto_approved_call_id is not None:
            payload['auto_approved_call_id'] = auto_approved_call_id
    print_json(payload)
    return 0 if result.status == 'completed' else 1


def run_result_payload(
    result: RunResult, *, routing: Optional[dict[str, Any]]
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        'run_id': result.run_id,
        'status': result.status,
        'iterations': result.iterations,
        'tool_calls': result.tool_calls,
        'routing': routing,
        'final_answer': result.final_answer.content if result.final_answer else None,
    }
    if 'approval' in result.metadata:
        payload['approval'] = result.metadata['approval']
    return payload


def cli_approval_handler(request: ApprovalRequest) -> bool:
    print(
        json.dumps(
            {'status': 'approval_required', 'approval': request.to_dict()},
            sort_keys=True,
        ),
        file=sys.stderr,
    )
    print(
        f'Approve destructive tool call {request.call_id} ({request.tool_name})? [y/N] ',
        end='',
        file=sys.stderr,
    )
    answer = input()
    return answer.strip().lower() in {'y', 'yes'}


def agent_preflight_command(args: argparse.Namespace) -> int:
    report = preflight(
        args.task,
        root=args.root,
        provider=args.provider,
        model=args.model,
        permission_mode=parse_permission_mode(args.permission_mode),
        route=args.route_model,
        memory_limit=args.memory_limit,
    )
    print_json(report.to_dict())
    return 0 if report.to_dict()['ready'] else 2


def agent_status_command(args: argparse.Namespace) -> int:
    store = RunStore(args.root)
    try:
        print_json(store.heartbeat_for_run(args.run_id))
    except FileNotFoundError as exc:
        print_json({'status': 'error', 'message': str(exc)})
        return 1
    return 0


def agent_runs_list(args: argparse.Namespace) -> int:
    store = RunStore(args.root)
    print_json([summary.to_dict() for summary in store.list_runs(limit=args.limit)])
    return 0


def agent_run_show(args: argparse.Namespace) -> int:
    store = RunStore(args.root)
    print_json(store.show_run(args.run_id))
    return 0


def doctor_model(args: argparse.Namespace) -> int:
    ok, message = check_llm_configuration(args.provider)
    print(
        json.dumps(
            {'ok': ok, 'message': message, 'provider': args.provider}, sort_keys=True
        )
    )
    return 0 if ok else 1


def model_providers(_args: argparse.Namespace) -> int:
    print_json(available_providers())
    return 0


def model_smoke(args: argparse.Namespace) -> int:
    adapter = create_llm_adapter(args.provider, model=args.model)
    response = adapter.complete(
        LLMRequest(
            messages=[LLMMessage(role='user', content=args.prompt)],
            max_tokens=args.max_tokens,
        )
    )
    print_json(
        {
            'provider': response.provider,
            'model': response.model,
            'content': response.content,
        }
    )
    return 0


def model_conformance(args: argparse.Namespace) -> int:
    report = run_model_conformance(
        args.provider,
        prompt=args.prompt,
        expected_content=args.expect if args.expect else None,
        max_tokens=args.max_tokens,
        model=args.model,
    )
    print_json(report.as_dict())
    return 0 if report.ok else 1


def model_route(args: argparse.Namespace) -> int:
    print_json(
        route_model(args.task, provider=args.provider, model=args.model).to_dict()
    )
    return 0


def start_tui(args: argparse.Namespace) -> int:
    return run_tui(
        database=args.database,
        provider=args.provider,
        model=args.model,
        root=args.root,
        allow_destructive=args.allow_destructive,
        permission_mode=parse_permission_mode(args.permission_mode),
    )


def graphqlite_query(args: argparse.Namespace) -> int:
    store = GraphQLiteGraphStore(GraphQLiteConfig(database=args.database))
    print_json(store.query(args.cypher))
    return 0


def graphqlite_smoke(args: argparse.Namespace) -> int:
    store = GraphQLiteGraphStore(GraphQLiteConfig(database=args.database))
    store.graph.upsert_node('teaagent', {'name': 'TeaAgent'}, label='SmokeTest')
    result = store.query('MATCH (n:SmokeTest) RETURN n.name')
    print_json(result)
    return 0


def ultrawork_start_command(args: argparse.Namespace) -> int:
    command = [
        sys.executable,
        '-m',
        'teaagent.cli',
        'agent',
        'run',
        args.provider,
        args.task,
        '--root',
        args.root,
        '--heartbeat',
        str(args.heartbeat),
        '--permission-mode',
        args.permission_mode,
    ]
    if args.model:
        command.extend(['--model', args.model])
    record = UltraworkStore(args.root).start(command, label=args.label)
    print_json(record.to_dict())
    return 0


def ultrawork_list_command(args: argparse.Namespace) -> int:
    print_json(UltraworkStore(args.root).list())
    return 0


def ultrawork_show_command(args: argparse.Namespace) -> int:
    try:
        print_json(UltraworkStore(args.root).show(args.worker_id))
    except FileNotFoundError as exc:
        print_json({'status': 'error', 'message': str(exc)})
        return 1
    return 0


def ultrawork_stop_command(args: argparse.Namespace) -> int:
    try:
        print_json(UltraworkStore(args.root).stop(args.worker_id))
    except FileNotFoundError as exc:
        print_json({'status': 'error', 'message': str(exc)})
        return 1
    return 0


def mcp_serve_command(args: argparse.Namespace) -> int:
    from teaagent.oauth21 import OAuth21AuthorizationServer

    registry = build_workspace_tool_registry(args.root)
    if args.http:
        oauth_server = None
        if args.oauth_issuer and args.oauth_signing_key:
            oauth_server = OAuth21AuthorizationServer(
                signing_key=args.oauth_signing_key,
                issuer=args.oauth_issuer,
                token_ttl=args.oauth_token_ttl,
            )
            for spec in args.oauth_client or []:
                parts = spec.split(':', 2)
                if len(parts) != 3:
                    print(
                        f'Invalid --oauth-client format: {spec} (expected ID:SECRET:REDIRECT_URI)',
                        file=sys.stderr,
                    )
                    return 1
                oauth_server.register_client(*parts)
        elif args.oauth_issuer or args.oauth_signing_key:
            print(
                'Both --oauth-issuer and --oauth-signing-key must be provided to enable OAuth.',
                file=sys.stderr,
            )
            return 1
        if (
            not is_loopback_host(args.host)
            and not args.auth_token
            and oauth_server is None
        ):
            print(
                'Refusing to serve MCP HTTP on a non-loopback host without --auth-token or OAuth.',
                file=sys.stderr,
            )
            return 1
        return serve_mcp_http(
            registry,
            host=args.host,
            port=args.port,
            auth_token=args.auth_token,
            allowed_origins=args.allowed_origin or None,
            oauth_server=oauth_server,
        )
    return serve_mcp_stdio(registry)


def workspace_tools_metadata(args: argparse.Namespace) -> int:
    registry = build_workspace_tool_registry(args.root)
    print_json(registry.mcp_metadata())
    return 0


def completion_command(args: argparse.Namespace) -> int:
    if args.shell == 'bash':
        print(
            'complete -W "agent audit clarify completion doctor graphqlite mcp memory model tui ultrawork workspace" teaagent'
        )
    elif args.shell == 'zsh':
        print(
            '#compdef teaagent\n_arguments "1: :((agent audit clarify completion doctor graphqlite mcp memory model tui ultrawork workspace))"'
        )
    else:
        print(
            'complete -c teaagent -f -a "agent audit clarify completion doctor graphqlite mcp memory model tui ultrawork workspace"'
        )
    return 0


def audit_list_command(args: argparse.Namespace) -> int:
    store = RunStore(args.root)
    print_json([summary.to_dict() for summary in store.list_runs(limit=args.limit)])
    return 0


def audit_show_command(args: argparse.Namespace) -> int:
    store = RunStore(args.root)
    try:
        print_json(store.show_run(args.run_id))
    except FileNotFoundError as exc:
        print_json({'status': 'error', 'message': str(exc)})
        return 1
    return 0


def audit_prune_command(args: argparse.Namespace) -> int:
    if args.days is None and args.keep is None and not args.all:
        print_json({'status': 'error', 'message': 'audit prune requires --days, --keep, or --all'})
        return 1
    store = RunStore(args.root)
    cutoff = time.time() - (args.days * 86400) if args.days is not None else None
    run_paths = sorted(
        store.store_dir.glob('*.jsonl'), key=lambda p: p.stat().st_mtime, reverse=True
    )
    keep = set(run_paths[: args.keep]) if args.keep is not None else set()
    deleted: list[str] = []
    for path in run_paths:
        if path in keep:
            continue
        if cutoff is not None and path.stat().st_mtime >= cutoff:
            continue
        path.unlink(missing_ok=True)
        path.with_suffix(path.suffix + '.lock').unlink(missing_ok=True)
        deleted.append(path.name)
    print_json({'count': len(deleted), 'deleted': deleted})
    return 0


def print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))

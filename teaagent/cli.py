from __future__ import annotations

import argparse
import json
from typing import Any, Optional

from teaagent import __version__
from teaagent.chat_agent import ChatAgentConfig, run_chat_agent
from teaagent.graphqlite_store import GraphQLiteConfig, GraphQLiteGraphStore, check_graphqlite_runtime
from teaagent.intent import build_task_spec, clarify_task
from teaagent.llm import LLMMessage, LLMRequest, available_providers, check_llm_configuration, create_llm_adapter
from teaagent.memory import MemoryCatalog
from teaagent.model_routing import route_model
from teaagent.policy import PermissionMode, parse_permission_mode
from teaagent.preflight import preflight
from teaagent.run_store import RunStore
from teaagent.tui import run_tui
from teaagent.workspace_tools import build_workspace_tool_registry


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="teaagent", description="TeaAgent harness utilities.")
    parser.add_argument("--version", action="version", version=f"teaagent {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    clarify = subparsers.add_parser("clarify", help="Score a task for ambiguity before running an agent.")
    clarify.add_argument("task", help="Task to clarify.")
    clarify.set_defaults(func=clarify_command)

    memory = subparsers.add_parser("memory", help="Manage local workspace memory.")
    memory_subparsers = memory.add_subparsers(dest="memory_command", required=True)

    memory_add = memory_subparsers.add_parser("add", help="Add one memory entry.")
    memory_add.add_argument("content", help="Memory content to store.")
    memory_add.add_argument("--root", default=".", help="Workspace root. Defaults to current directory.")
    memory_add.add_argument("--tag", action="append", default=[], help="Tag to attach. Can be repeated.")
    memory_add.set_defaults(func=memory_add_command)

    memory_list = memory_subparsers.add_parser("list", help="List recent memory entries.")
    memory_list.add_argument("--root", default=".", help="Workspace root. Defaults to current directory.")
    memory_list.add_argument("--limit", type=int, default=20, help="Maximum memories to list.")
    memory_list.set_defaults(func=memory_list_command)

    memory_search = memory_subparsers.add_parser("search", help="Search memory entries.")
    memory_search.add_argument("query", help="Search query.")
    memory_search.add_argument("--root", default=".", help="Workspace root. Defaults to current directory.")
    memory_search.add_argument("--limit", type=int, default=10, help="Maximum memories to return.")
    memory_search.set_defaults(func=memory_search_command)

    memory_show = memory_subparsers.add_parser("show", help="Show one memory entry.")
    memory_show.add_argument("memory_id", help="Memory id to show.")
    memory_show.add_argument("--root", default=".", help="Workspace root. Defaults to current directory.")
    memory_show.set_defaults(func=memory_show_command)

    agent = subparsers.add_parser("agent", help="Run model-driven agent tasks.")
    agent_subparsers = agent.add_subparsers(dest="agent_command", required=True)
    agent_run = agent_subparsers.add_parser(
        "run",
        help="Run one autonomous task with workspace tools.",
        description="Run one autonomous task with workspace tools.",
    )
    agent_run.add_argument("provider", choices=available_providers(), help="Model provider to use.")
    agent_run.add_argument("task", help="Task for the agent to perform.")
    agent_run.add_argument("--root", default=".", help="Workspace root. Defaults to current directory.")
    agent_run.add_argument("--model", default=None, help="Override model name.")
    agent_run.add_argument(
        "--route-model",
        action="store_true",
        help="Choose a provider-specific model from the task category when --model is not set.",
    )
    agent_run.add_argument("--max-iterations", type=int, default=10, help="Maximum agent loop iterations.")
    agent_run.add_argument("--max-tool-calls", type=int, default=10, help="Maximum tool calls.")
    agent_run.add_argument(
        "--clarify",
        action="store_true",
        help="Run deterministic ambiguity scoring before calling the model.",
    )
    agent_run.add_argument(
        "--allow-destructive",
        action="store_true",
        help="Allow destructive tools such as write, patch, and shell.",
    )
    agent_run.add_argument(
        "--approve-call-id",
        action="append",
        default=[],
        help="Approve one exact destructive tool call id. Can be repeated.",
    )
    agent_run.add_argument(
        "--permission-mode",
        choices=[mode.value for mode in PermissionMode],
        default=PermissionMode.PROMPT.value,
        help="Permission mode for workspace tools.",
    )
    agent_run.set_defaults(func=agent_run_task)

    agent_preflight = agent_subparsers.add_parser(
        "preflight",
        help="Summarize clarify, routing, memory, and tool state without calling a model.",
    )
    agent_preflight.add_argument("provider", choices=available_providers(), help="Model provider to plan for.")
    agent_preflight.add_argument("task", help="Task to evaluate.")
    agent_preflight.add_argument("--root", default=".", help="Workspace root. Defaults to current directory.")
    agent_preflight.add_argument("--model", default=None, help="Override model name.")
    agent_preflight.add_argument("--route-model", action="store_true", help="Apply task category routing.")
    agent_preflight.add_argument(
        "--permission-mode",
        choices=[mode.value for mode in PermissionMode],
        default=PermissionMode.PROMPT.value,
        help="Permission mode to report.",
    )
    agent_preflight.add_argument("--memory-limit", type=int, default=5, help="Maximum matched memories to include.")
    agent_preflight.set_defaults(func=agent_preflight_command)

    agent_list = agent_subparsers.add_parser("runs", help="List persisted agent runs.")
    agent_list.add_argument("--root", default=".", help="Workspace root. Defaults to current directory.")
    agent_list.add_argument("--limit", type=int, default=20, help="Maximum runs to list.")
    agent_list.set_defaults(func=agent_runs_list)

    agent_show = agent_subparsers.add_parser("show", help="Show one persisted run JSONL record.")
    agent_show.add_argument("run_id", help="Run id to show.")
    agent_show.add_argument("--root", default=".", help="Workspace root. Defaults to current directory.")
    agent_show.set_defaults(func=agent_run_show)

    tui = subparsers.add_parser(
        "tui",
        help="Start an interactive terminal UI.",
        description="Start an interactive terminal UI.",
    )
    tui.add_argument("--database", default=":memory:", help="SQLite database path. Defaults to :memory:.")
    tui.add_argument("--provider", default="gpt", choices=available_providers(), help="Default model provider for ask commands.")
    tui.add_argument("--model", default=None, help="Default model override for ask commands.")
    tui.add_argument("--root", default=".", help="Workspace root for ask commands.")
    tui.add_argument(
        "--allow-destructive",
        action="store_true",
        help="Allow destructive tools for ask commands.",
    )
    tui.add_argument(
        "--permission-mode",
        choices=[mode.value for mode in PermissionMode],
        default=PermissionMode.PROMPT.value,
        help="Permission mode for ask commands.",
    )
    tui.set_defaults(func=start_tui)

    doctor = subparsers.add_parser("doctor", help="Run environment checks.")
    doctor_subparsers = doctor.add_subparsers(dest="doctor_command", required=True)
    graphqlite_doctor = doctor_subparsers.add_parser("graphqlite", help="Check GraphQLite runtime availability.")
    graphqlite_doctor.add_argument("--database", default=":memory:", help="SQLite database path. Defaults to :memory:.")
    graphqlite_doctor.set_defaults(func=doctor_graphqlite)

    model_doctor = doctor_subparsers.add_parser("model", help="Check model provider configuration.")
    model_doctor.add_argument("provider", choices=available_providers(), help="Model provider to check.")
    model_doctor.set_defaults(func=doctor_model)

    model = subparsers.add_parser("model", help="Run model adapter operations.")
    model_subparsers = model.add_subparsers(dest="model_command", required=True)

    providers = model_subparsers.add_parser("providers", help="List configured provider names.")
    providers.set_defaults(func=model_providers)

    smoke_model = model_subparsers.add_parser("smoke", help="Run a minimal prompt against a provider.")
    smoke_model.add_argument("provider", choices=available_providers(), help="Model provider to call.")
    smoke_model.add_argument("--model", default=None, help="Override model name.")
    smoke_model.add_argument("--prompt", default="Reply with exactly: ok", help="Prompt to send.")
    smoke_model.add_argument("--max-tokens", type=int, default=32, help="Maximum output tokens.")
    smoke_model.set_defaults(func=model_smoke)

    route = model_subparsers.add_parser("route", help="Classify a task and choose a provider-specific model.")
    route.add_argument("task", help="Task to route.")
    route.add_argument("--provider", default="gpt", choices=available_providers(), help="Provider to route within.")
    route.add_argument("--model", default=None, help="Explicit model override.")
    route.set_defaults(func=model_route)

    graphqlite = subparsers.add_parser("graphqlite", help="Run GraphQLite operations.")
    graphqlite_subparsers = graphqlite.add_subparsers(dest="graphqlite_command", required=True)

    query = graphqlite_subparsers.add_parser("query", help="Execute a Cypher query against GraphQLite.")
    query.add_argument("cypher", help="Cypher query to execute.")
    query.add_argument("--database", default=":memory:", help="SQLite database path. Defaults to :memory:.")
    query.set_defaults(func=graphqlite_query)

    smoke = graphqlite_subparsers.add_parser("smoke", help="Create a node and run a real GraphQLite query.")
    smoke.add_argument("--database", default=":memory:", help="SQLite database path. Defaults to :memory:.")
    smoke.set_defaults(func=graphqlite_smoke)

    workspace = subparsers.add_parser("workspace", help="Inspect workspace tool pack.")
    workspace_subparsers = workspace.add_subparsers(dest="workspace_command", required=True)
    workspace_tools = workspace_subparsers.add_parser("tools", help="List workspace tool metadata.")
    workspace_tools.add_argument("--root", default=".", help="Workspace root. Defaults to current directory.")
    workspace_tools.set_defaults(func=workspace_tools_metadata)
    return parser


def doctor_graphqlite(args: argparse.Namespace) -> int:
    ok, message = check_graphqlite_runtime(args.database)
    print(json.dumps({"ok": ok, "message": message}, sort_keys=True))
    return 0 if ok else 1


def clarify_command(args: argparse.Namespace) -> int:
    print_json(clarify_task(args.task).to_dict())
    return 0


def memory_add_command(args: argparse.Namespace) -> int:
    entry = MemoryCatalog(args.root).add(args.content, tags=tuple(args.tag))
    print_json(entry.to_dict())
    return 0


def memory_list_command(args: argparse.Namespace) -> int:
    print_json([entry.to_dict() for entry in MemoryCatalog(args.root).list(limit=args.limit)])
    return 0


def memory_search_command(args: argparse.Namespace) -> int:
    print_json([entry.to_dict() for entry in MemoryCatalog(args.root).search(args.query, limit=args.limit)])
    return 0


def memory_show_command(args: argparse.Namespace) -> int:
    print_json(MemoryCatalog(args.root).show(args.memory_id).to_dict())
    return 0


def agent_run_task(args: argparse.Namespace) -> int:
    task_spec = None
    if args.clarify:
        clarification = clarify_task(args.task)
        if clarification.needs_clarification:
            print_json({"status": "needs_clarification", "clarification": clarification.to_dict()})
            return 2
        task_spec = build_task_spec(args.task, clarification)

    routing = route_model(args.task, provider=args.provider, model=args.model) if args.route_model else None
    selected_model = routing.model if routing else args.model
    adapter = create_llm_adapter(args.provider, model=selected_model)
    store = RunStore(args.root)
    audit = store.audit_logger()
    result = run_chat_agent(
        task=args.task,
        adapter=adapter,
        config=ChatAgentConfig.from_root(
            args.root,
            max_iterations=args.max_iterations,
            max_tool_calls=args.max_tool_calls,
            allow_destructive=args.allow_destructive,
            model=selected_model,
            permission_mode=parse_permission_mode(args.permission_mode),
            approved_call_ids=frozenset(args.approve_call_id),
        ),
        audit=audit,
        task_spec=task_spec,
    )
    store.logger_for_result(result, audit)
    print_json(
        {
            "run_id": result.run_id,
            "status": result.status,
            "iterations": result.iterations,
            "tool_calls": result.tool_calls,
            "routing": routing.to_dict() if routing else None,
            "final_answer": result.final_answer.content if result.final_answer else None,
        }
    )
    return 0 if result.status == "completed" else 1


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
    return 0 if report.to_dict()["ready"] else 2


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
    print(json.dumps({"ok": ok, "message": message, "provider": args.provider}, sort_keys=True))
    return 0 if ok else 1


def model_providers(_args: argparse.Namespace) -> int:
    print_json(available_providers())
    return 0


def model_smoke(args: argparse.Namespace) -> int:
    adapter = create_llm_adapter(args.provider, model=args.model)
    response = adapter.complete(
        LLMRequest(
            messages=[LLMMessage(role="user", content=args.prompt)],
            max_tokens=args.max_tokens,
        )
    )
    print_json(
        {
            "provider": response.provider,
            "model": response.model,
            "content": response.content,
        }
    )
    return 0


def model_route(args: argparse.Namespace) -> int:
    print_json(route_model(args.task, provider=args.provider, model=args.model).to_dict())
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
    store.graph.upsert_node("teaagent", {"name": "TeaAgent"}, label="SmokeTest")
    result = store.query("MATCH (n:SmokeTest) RETURN n.name")
    print_json(result)
    return 0


def workspace_tools_metadata(args: argparse.Namespace) -> int:
    registry = build_workspace_tool_registry(args.root)
    print_json(registry.mcp_metadata())
    return 0


def print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())

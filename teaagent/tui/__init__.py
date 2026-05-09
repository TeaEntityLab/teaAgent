from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Optional

from teaagent import __version__
from teaagent.audit import AuditEvent
from teaagent.chat_agent import ChatAgentConfig, run_chat_agent
from teaagent.graphqlite_store import (
    GraphQLiteConfig,
    GraphQLiteGraphStore,
)
from teaagent.intent import build_task_spec, clarify_task
from teaagent.llm import LLMAdapter, create_llm_adapter
from teaagent.memory import MemoryCatalog
from teaagent.model_routing import route_model
from teaagent.policy import PermissionMode
from teaagent.run_store import RunStore
from teaagent.runner import ApprovalRequest, RunResult

InputFn = Callable[[str], str]
OutputFn = Callable[..., None]
AdapterFactory = Callable[[str, Optional[str]], LLMAdapter]


def default_adapter_factory(provider: str, model: Optional[str]) -> LLMAdapter:
    return create_llm_adapter(provider, model=model)


HELP_TEXT = """Commands:
  help                      Show this help.
  doctor                    Check GraphQLite runtime.
  provider <name>           Set model provider: claude, gpt, gemini, openrouter, opencodezen-go.
  model <name|default>      Set or clear model override.
  route-model <on|off>      Enable or disable task-based model routing.
  route <task>              Preview model route for a task.
  root <path>               Set workspace root for agent tasks.
  destructive <on|off>      Allow or block destructive workspace tools.
  progress <on|off>         Stream brief audit-event progress lines during ask runs.
  stream <on|off>           Stream model output token-by-token during ask runs.
  subagent <on|off>         Expose the 'subagent' tool so the model can delegate sub-tasks.
  heartbeat <seconds>       Set heartbeat interval for ask runs. 0 disables.
  status <run_id>           Show heartbeat liveness for a persisted run.
  permission <mode>         Set permission mode: read-only, workspace-write, prompt, allow, danger-full-access.
  approve <call_id>         Approve one exact destructive tool call id.
  unapprove <call_id>       Remove one approved call id.
  approvals                 List approved call ids for this session.
  clarify <task>            Score task ambiguity without calling a model.
  preflight <task>          Show clarify, routing, memory, and tool plan without calling a model.
  ask <task>                Run a model-driven agent task with workspace tools.
  ask --clarify <task>      Clarify first; stop if key details are missing.
  memory add <text>         Add a workspace memory entry.
  memory list               List recent workspace memories.
  memory search <query>     Search workspace memories.
  memory show <id>          Show one workspace memory.
  runs                      List recent persisted agent runs.
  show <run_id>             Show one persisted run record.
  resume <run_id>           Re-run the original task from a persisted run id.
  use <database>            Switch database path. Use :memory: for in-memory.
  smoke                     Create a SmokeTest node and query it.
  query <cypher>            Execute a Cypher query.
  exit | quit               Leave the TUI.
"""


class TeaAgentTUI:
    def __init__(
        self,
        *,
        database: str = ':memory:',
        provider: str = 'gpt',
        model: Optional[str] = None,
        root: str | Path = '.',
        allow_destructive: bool = False,
        permission_mode: PermissionMode = PermissionMode.PROMPT,
        input_fn: InputFn = input,
        output_fn: OutputFn = print,
        adapter_factory: AdapterFactory = default_adapter_factory,
    ) -> None:
        self.database = database
        self.provider = provider
        self.model = model
        self.route_model_enabled = False
        self.root = Path(root).resolve()
        self.allow_destructive = allow_destructive
        self.permission_mode = permission_mode
        self.progress = False
        self.stream = False
        self.subagent = False
        self.heartbeat_seconds = 0.0
        self.approved_call_ids: set[str] = set()
        self.input_fn = input_fn
        self.output_fn = output_fn
        self.adapter_factory = adapter_factory
        self._store: Optional[GraphQLiteGraphStore] = None

    def run(self) -> int:
        self._print_header()
        while True:
            try:
                raw_command = self.input_fn(self._prompt())
            except EOFError:
                self.output_fn('bye')
                return 0

            should_continue = self.handle_command(raw_command)
            if not should_continue:
                return 0

    @property
    def help_text(self) -> str:
        return HELP_TEXT

    @property
    def route_model(self) -> bool:
        return self.route_model_enabled

    @route_model.setter
    def route_model(self, value: bool) -> None:
        self.route_model_enabled = value

    def handle_command(self, raw_command: str) -> bool:
        from teaagent.tui._commands import _handle_tui_command

        return _handle_tui_command(self, raw_command)

    def _handle_memory(self, args: list[str]) -> None:
        if not args:
            self.output_fn('error: memory requires add, list, search, or show')
            return
        catalog = MemoryCatalog(self.root)
        action = args[0]
        rest = args[1:]
        if action == 'add':
            if not rest:
                self.output_fn('error: memory add requires text')
                return
            self._print_json(catalog.add(' '.join(rest)).to_dict())
            return
        if action == 'list':
            self._print_json([entry.to_dict() for entry in catalog.list()])
            return
        if action == 'search':
            if not rest:
                self.output_fn('error: memory search requires a query')
                return
            self._print_json(
                [entry.to_dict() for entry in catalog.search(' '.join(rest))]
            )
            return
        if action == 'show':
            if len(rest) != 1:
                self.output_fn('error: memory show requires one id')
                return
            self._print_json(catalog.show(rest[0]).to_dict())
            return
        self.output_fn(f"error: unknown memory command '{action}'")

    def _run_agent_task(
        self,
        task: str,
        *,
        clarify_first: bool = False,
        initial_observations: Optional[list[dict[str, Any]]] = None,
    ) -> None:
        task_spec = None
        if clarify_first:
            clarification = clarify_task(task)
            if clarification.needs_clarification:
                self._print_json(
                    {
                        'status': 'needs_clarification',
                        'clarification': clarification.to_dict(),
                    }
                )
                return
            task_spec = build_task_spec(task, clarification)
        routing = (
            route_model(task, provider=self.provider, model=self.model)
            if self.route_model_enabled
            else None
        )
        selected_model = routing.model if routing else self.model
        self.output_fn(f'agent: provider={self.provider} root={self.root}')
        adapter = self.adapter_factory(self.provider, selected_model)
        store = RunStore(self.root)
        audit = store.audit_logger()
        if self.progress:
            audit.add_sink(self._progress_sink)
        result = run_chat_agent(
            task=task,
            adapter=adapter,
            config=ChatAgentConfig.from_root(
                self.root,
                model=selected_model,
                allow_destructive=self.allow_destructive,
                permission_mode=self.permission_mode,
                approved_call_ids=frozenset(self.approved_call_ids),
                enable_subagent=self.subagent,
                heartbeat_seconds=self.heartbeat_seconds,
                stream=self.stream,
                on_chunk=self._stream_chunk if self.stream else None,
                approval_handler=self._approval_handler,
            ),
            audit=audit,
            task_spec=task_spec,
            initial_observations=initial_observations,
        )
        store.logger_for_result(result, audit)
        payload = self._run_result_payload(
            result, routing=routing.to_dict() if routing else None
        )
        if initial_observations:
            payload['replayed_observations'] = len(initial_observations)
        self._print_json(payload)

    def _approval_handler(self, request: ApprovalRequest) -> bool:
        self._print_json({'status': 'approval_required', 'approval': request.to_dict()})
        answer = self.input_fn(
            f'approve {request.call_id} ({request.tool_name})? [y/N] '
        )
        approved = answer.strip().lower() in {'y', 'yes'}
        self.output_fn(
            f'approval: {"approved" if approved else "denied"} {request.call_id}'
        )
        if approved:
            self.approved_call_ids.add(request.call_id)
        return approved

    def _run_result_payload(
        self, result: RunResult, *, routing: Optional[dict]
    ) -> dict:
        payload = {
            'run_id': result.run_id,
            'status': result.status,
            'iterations': result.iterations,
            'tool_calls': result.tool_calls,
            'routing': routing,
            'final_answer': result.final_answer.content
            if result.final_answer
            else None,
        }
        if 'approval' in result.metadata:
            payload['approval'] = result.metadata['approval']
        return payload

    def _progress_sink(self, event: AuditEvent) -> None:
        payload = event.payload or {}
        if event.event_type == 'iteration_started':
            self.output_fn(f'  iter {payload.get("iteration")}')
        elif event.event_type == 'tool_call_started':
            self.output_fn(
                f'  tool: {payload.get("tool_name")} ({payload.get("call_id")})'
            )
        elif event.event_type == 'tool_call_completed':
            self.output_fn(f'  tool ok: {payload.get("tool_name")}')
        elif event.event_type == 'run_failed':
            self.output_fn(
                f'  failed: {payload.get("category")}: {payload.get("message")}'
            )

    def _stream_chunk(self, chunk: str) -> None:
        self.output_fn(chunk, end='')

    def _get_store(self) -> GraphQLiteGraphStore:
        if self._store is None:
            self._store = GraphQLiteGraphStore(GraphQLiteConfig(database=self.database))
        return self._store

    def _print_header(self) -> None:
        self.output_fn(f'TeaAgent TUI {__version__}')
        self.output_fn("Type 'help' for commands. Type 'exit' to quit.")

    def _prompt(self) -> str:
        destructive = '!' if self.allow_destructive else ''
        model = self.model or 'default'
        routed = ':route' if self.route_model_enabled else ''
        return f'teaagent[{self.provider}:{model}{routed}:{self.permission_mode.value}{destructive}]> '

    def _print_json(self, value: Any) -> None:
        self.output_fn(json.dumps(value, ensure_ascii=False, sort_keys=True))


def run_tui(
    *,
    database: str = ':memory:',
    provider: str = 'gpt',
    model: Optional[str] = None,
    root: str | Path = '.',
    allow_destructive: bool = False,
    permission_mode: PermissionMode = PermissionMode.PROMPT,
) -> int:
    return TeaAgentTUI(
        database=database,
        provider=provider,
        model=model,
        root=root,
        allow_destructive=allow_destructive,
        permission_mode=permission_mode,
    ).run()

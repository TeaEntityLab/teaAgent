from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional

if TYPE_CHECKING:
    from prompt_toolkit import PromptSession

from teaagent import __version__
from teaagent.audit import AuditEvent
from teaagent.chat_agent import ChatAgentConfig, run_chat_agent
from teaagent.git_sandbox import (
    ParallelExperimentStack,
)
from teaagent.graphqlite_store import (
    GraphQLiteConfig,
    GraphQLiteGraphStore,
)
from teaagent.intent import build_task_spec, clarify_task
from teaagent.llm import LLMAdapter, LLMMessage, create_llm_adapter
from teaagent.memory import MemoryCatalog
from teaagent.model_routing import route_model
from teaagent.policy import PermissionMode
from teaagent.run_store import RunStore, summarize_audit_events
from teaagent.runner import ApprovalRequest, RunResult
from teaagent.session import ChatMessage, ChatSession, SessionStore

InputFn = Callable[[str], str]
OutputFn = Callable[..., None]
AdapterFactory = Callable[[str, Optional[str]], LLMAdapter]


def default_adapter_factory(provider: str, model: Optional[str]) -> LLMAdapter:
    return create_llm_adapter(provider, model=model)


HELP_TEXT = """Commands:
  help                      Show this help.
  setup [write-env]         Guided first-session workspace setup (same as teaagent setup).
  doctor                    Check GraphQLite runtime.
  provider <name>           Set model provider: claude, gpt, gemini, openrouter, ollama, vllm, opencodezen-go, workers-ai, aigateway.
  model <name|default>      Set or clear model override.
  route-model <on|off>      Enable or disable task-based model routing.
  route <task>              Preview model route for a task.
  complexity <task>         Analyze task complexity (high/medium/low).
  estimate <task>           Estimate token budget for a task.
  root <path>               Set workspace root for agent tasks.
  destructive <on|off>      Allow or block destructive workspace tools.
  progress <on|off>         Stream brief audit-event progress lines during ask runs.
  stream <on|off>           Stream model output token-by-token during ask runs.
  subagent <on|off>         Expose the 'subagent' tool so the model can delegate sub-tasks.
  chat <on|off>             Enable or disable multi-turn chat mode with session history.
  session new               Create a new chat session.
  session list              List saved chat sessions.
  session switch <id>       Switch to another chat session.
  session clear             Clear messages in the current chat session.
  session show              Show the current chat session details.
  heartbeat <seconds>       Set heartbeat interval for ask runs. 0 disables.
  status <run_id>           Show heartbeat liveness for a persisted run.
  permission <mode>         Set permission mode: read-only, workspace-write, prompt, allow, danger-full-access.
  approve <call_id>         Approve one exact destructive tool call id.
  unapprove <call_id>       Remove one approved call id.
  approvals                 List approved call ids for this session.
  approvals subagents       Batch view of parallel subagent destructive-tool queue.
  approvals subagents approve|deny|approve-all|deny-all
  clarify <task>            Score task ambiguity without calling a model.
  preflight <task>          Show clarify, routing, memory, and tool plan without calling a model.
  plan <task>               Write a read-only plan artifact under .teaagent/plans.
  daily [task]              Show readiness, recent runs, harness health, and token budget.
  run <task>                Run a model-driven agent task (alias for ask).
  ask <task>                Run a model-driven agent task with workspace tools.
  undo [run_id]             Restore workspace files from the last undo journal (or a run id).
  permissions               List destructive-tool approval presets for this workspace.
  mcp                       Hint for MCP doctor / serve commands (run from a shell).
  ask --clarify <task>      Clarify first; stop if key details are missing.
  memory add <text>         Add a workspace memory entry.
  memory list               List recent workspace memories.
  memory search <query>     Search workspace memories.
  memory show <id>          Show one workspace memory.
  runs                      List recent persisted agent runs.
  show <run_id>             Show one persisted run record.
  resume <run_id>           Re-run the original task from a persisted run id.
  context list [prefix]     List workspace files for @-mentions in tasks.
  use <database>            Switch database path. Use :memory: for in-memory.
  smoke                     Create a SmokeTest node and query it.
  query <cypher>            Execute a Cypher query.
  parallel <optA> <optB>... Start parallel experiment branches for comparison.
  select <option>           Merge selected parallel experiment branch.
  cancel                    Cancel and cleanup all parallel experiment branches.
  conflict                  Enter conflict resolution mode for merge conflicts.
  o                         Accept Our version (current branch) in conflict mode.
  t                         Accept Their version (incoming branch) in conflict mode.
  n                         Next conflicted file in conflict mode.
  p                         Previous conflicted file in conflict mode.
  a                         Abort merge in conflict mode.
  exit | quit               Leave the TUI.

Slash aliases (/daily, /plan, /run, …) are accepted for the same commands.
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
        input_fn: Optional[InputFn] = None,
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
        self.progress = True
        self.stream = False
        self.subagent = False
        self.heartbeat_seconds = 0.0
        self.chat = False
        self._chat_explicit = False
        self.session_id: Optional[str] = None
        self.approved_call_ids: set[str] = set()
        self.last_run_id: Optional[str] = None
        self.input_fn = input_fn
        self.output_fn = output_fn
        self.adapter_factory = adapter_factory
        self._store: Optional[GraphQLiteGraphStore] = None
        self._session_store: Optional[SessionStore] = None
        self._session: Optional['PromptSession'] = None
        self._parallel_stack: Optional[ParallelExperimentStack] = None
        self._parallel_options: list[str] = []
        self._conflict_mode: bool = False
        self._conflicted_files: list[str] = []
        self._current_conflict_index: int = 0

    def _should_use_split_pane(self) -> bool:
        """Check if terminal is large enough for split-pane layout."""
        try:
            columns, lines = shutil.get_terminal_size()
            return columns >= 120 and lines >= 30
        except (OSError, ValueError):
            return False

    def _print_state_panel(self) -> None:
        """Print the state panel showing token budget, files, and memory."""
        try:
            columns, lines = shutil.get_terminal_size()
        except (OSError, ValueError):
            return

        # Clear screen and print header
        print('\033[2J\033[H', end='')  # Clear screen
        print('=' * columns)
        print(f'TeaAgent TUI {__version__} - State Panel')
        print('=' * columns)

        # Conflict resolution mode
        if self._conflict_mode and self._conflicted_files:
            print('\n[Conflict Resolution Mode]')
            print(
                f'File {self._current_conflict_index + 1}/{len(self._conflicted_files)}: {self._conflicted_files[self._current_conflict_index]}'
            )
            print('\n[Commands]')
            print('  [o] Accept Our version (current branch)')
            print('  [t] Accept Their version (incoming branch)')
            print('  [n] Next conflicted file')
            print('  [p] Previous conflicted file')
            print('  [a] Abort merge')
            print('=' * columns)
            return

        # Left panel: Chat area placeholder
        print('\n[Chat Area - Enter commands below]')
        print('-' * columns)

        # Right panel: State information
        print('\n[State Panel]')
        print(f'Provider: {self.provider}')
        print(f'Model: {self.model or "default"}')
        print(f'Root: {self.root}')
        print(f'Permission Mode: {self.permission_mode.value}')
        print(f'Destructive: {"allowed" if self.allow_destructive else "blocked"}')
        print(f'Chat: {"enabled" if self.chat else "disabled"}')

        # Parallel experiments panel
        if self._parallel_stack and self._parallel_options:
            print('\n[Parallel Experiments]')
            comparisons = self._parallel_stack.compare_branches()
            for option in self._parallel_options:
                if option in comparisons:
                    stats = comparisons[option]
                    print(
                        f'  {option}: +{stats["insertions"]} -{stats["deletions"]} ({stats["files_changed"]} files)'
                    )
            print('  [Enter] to merge selected branch')
            print('  [q] to cancel experiments')

        # Recent runs
        try:
            from teaagent.run_store import RunStore

            store = RunStore(self.root, readonly=True)
            recent_runs = store.list_runs(limit=3)
            print(f'\nRecent Runs: {len(recent_runs)}')
            for run in recent_runs:
                print(f'  - {run.run_id[:8]}: {run.status}')
        except Exception:
            print('\nRecent Runs: (unavailable)')

        # Memory catalog
        try:
            from teaagent.memory import MemoryCatalog

            memory = MemoryCatalog(self.root, readonly=True)
            memories = memory.list(limit=3)
            print(f'\nMemory Entries: {len(memories)}')
            for mem in memories:
                print(f'  - {mem.memory_id[:8]}: {mem.content[:30]}...')
        except Exception:
            print('\nMemory Entries: (unavailable)')

        print('=' * columns)
        print()

    def run(self, *, run_setup: bool = False, setup_write_env: bool = False) -> int:
        self._load_workspace_defaults()
        self._load_tui_state()
        self._print_header()
        if run_setup:
            from teaagent.tui._setup import run_tui_setup

            run_tui_setup(self, write_env=setup_write_env)

        # Check if we should use split-pane layout
        use_split_pane = self._should_use_split_pane()
        if use_split_pane:
            self.output_fn(
                '[TeaAgent] Split-pane layout enabled (terminal size >= 120x30)'
            )

        # Initialize prompt_toolkit session if available and no custom input_fn is provided
        if self.input_fn is None:
            try:
                from prompt_toolkit import PromptSession
                from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
                from prompt_toolkit.history import FileHistory

                history_path = self._state_path.parent / 'history.txt'
                history_path.parent.mkdir(parents=True, exist_ok=True)
                self._session = PromptSession(
                    history=FileHistory(str(history_path)),
                    auto_suggest=AutoSuggestFromHistory(),
                )
            except (ImportError, OSError):
                self._session = None

        while True:
            try:
                if use_split_pane:
                    self._print_state_panel()

                if self.input_fn:
                    raw_command = self.input_fn(self._prompt())
                elif self._session:
                    raw_command = self._session.prompt(self._prompt())
                else:
                    raw_command = input(self._prompt())
            except (EOFError, KeyboardInterrupt):
                self.output_fn('bye')
                self._save_tui_state()
                return 0

            should_continue = self.handle_command(raw_command)
            if not should_continue:
                self._save_tui_state()
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

    def _get_session_store(self) -> SessionStore:
        if self._session_store is None:
            self._session_store = SessionStore(self.root)
        return self._session_store

    def _current_session(self) -> Optional[ChatSession]:
        if not self.session_id:
            return None
        return self._get_session_store().load(self.session_id)

    def _ensure_session(self) -> ChatSession:
        session = self._current_session()
        if session is not None:
            return session
        from uuid import uuid4

        session = ChatSession(id=uuid4().hex)
        self.session_id = session.id
        self._get_session_store().save(session)
        return session

    def _run_agent_task(
        self,
        task: str,
        *,
        clarify_first: bool = False,
        initial_observations: Optional[list[dict[str, Any]]] = None,
        resumed_from: Optional[str] = None,
    ) -> None:
        from teaagent.ergonomics.context_inject import expand_at_references

        task, _refs = expand_at_references(task, root=self.root)
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

        chat_messages = None
        if self.chat:
            session = self._ensure_session()
            chat_messages = [
                LLMMessage(role=m.role, content=m.content) for m in session.messages
            ]

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
                stream_text_only=True,
                approval_handler=self._approval_handler,
                chat_messages=chat_messages,
            ),
            audit=audit,
            task_spec=task_spec,
            initial_observations=initial_observations,
            initial_context_extra={'resumed_from': resumed_from}
            if resumed_from
            else None,
        )
        store.logger_for_result(result, audit)
        self.last_run_id = result.run_id
        audit_summary = summarize_audit_events(store.show_run(result.run_id))

        if self.chat:
            chat_session: Optional[ChatSession] = self._current_session()
            if chat_session is not None:
                chat_session.messages.append(ChatMessage(role='user', content=task))
                answer = (
                    result.final_answer.content
                    if result.final_answer
                    else f'[{result.status}]'
                )
                chat_session.messages.append(
                    ChatMessage(role='assistant', content=answer)
                )
                self._get_session_store().save(chat_session)

        if self.chat and result.status == 'completed' and result.final_answer:
            self.output_fn(result.final_answer.content)
        else:
            payload = self._run_result_payload(
                result,
                routing=routing.to_dict() if routing else None,
                audit_summary=audit_summary,
            )
            if initial_observations:
                payload['replayed_observations'] = len(initial_observations)
            self._print_json(payload)

    def _approval_handler(self, request: ApprovalRequest) -> bool:
        from teaagent.ergonomics.approval_store import ApprovalPresetStore

        store = ApprovalPresetStore(self.root)
        if store.is_allowed(
            request.tool_name,
            permission_mode=self.permission_mode.value,
            arguments=request.arguments,
        ):
            self.output_fn(f'approval: preset allowed {request.tool_name}')
            return True
        self._print_json({'status': 'approval_required', 'approval': request.to_dict()})
        fn = self.input_fn or input
        answer = (
            fn(
                f'approve {request.call_id} ({request.tool_name})? [y]es / [n]o / always for this [p]ath / always for this [t]ool / [s]top run: '
            )
            .strip()
            .lower()
        )
        if answer in {'y', 'yes'}:
            self.output_fn(f'approval: approved {request.call_id}')
            if not request.run_id:
                self.approved_call_ids.add(request.call_id)
            return True
        elif answer in {'s', 'stop'}:
            self.output_fn('approval: stop run requested by operator')
            raise SystemExit('Task aborted by operator.')
        elif answer == 'p':
            path = None
            if request.arguments:
                path = (
                    request.arguments.get('path')
                    or request.arguments.get('TargetFile')
                    or request.arguments.get('target_file')
                    or request.arguments.get('AbsolutePath')
                )
            if path:
                store.grant(
                    request.tool_name,
                    scope='session',
                    permission_mode=self.permission_mode.value,
                    path_globs=[str(path)],
                    ttl_hours=8.0,
                )
                self.output_fn(
                    f'approval: registered session grant for {request.tool_name} matching path: {path}'
                )
            else:
                store.grant(
                    request.tool_name,
                    scope='session',
                    permission_mode=self.permission_mode.value,
                    ttl_hours=8.0,
                )
                self.output_fn(
                    f'approval: registered global session grant for {request.tool_name}'
                )
            return True
        elif answer == 't':
            store.grant(
                request.tool_name,
                scope='session',
                permission_mode=self.permission_mode.value,
                ttl_hours=8.0,
            )
            self.output_fn(
                f'approval: registered global session grant for {request.tool_name}'
            )
            return True

        self.output_fn(f'approval: denied {request.call_id}')
        return False

    def _run_result_payload(
        self,
        result: RunResult,
        *,
        routing: Optional[dict],
        audit_summary: Optional[dict[str, Any]] = None,
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
        if audit_summary is not None:
            payload['audit_summary'] = audit_summary
        if result.error_message is not None:
            payload['error'] = result.error_message
        return payload

    def _progress_sink(self, event: AuditEvent) -> None:
        from teaagent.streaming.events import format_progress_line

        line = format_progress_line(event)
        if line:
            self.output_fn(line)

    def _stream_chunk(self, chunk: str) -> None:
        self.output_fn(chunk, end='')

    @property
    def _state_path(self) -> Path:
        return Path.home() / '.teaagent' / 'tui_state.json'

    def _load_tui_state(self) -> None:
        if not self._state_path.is_file():
            return
        try:
            data = json.loads(self._state_path.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, OSError):
            return
        if not isinstance(data, dict):
            return
        self.provider = data.get('provider', self.provider)
        self.model = data.get('model', self.model)
        self.root = Path(data.get('root', str(self.root))).resolve()
        self.permission_mode = PermissionMode(
            data.get('permission_mode', self.permission_mode.value)
        )
        self.allow_destructive = data.get('allow_destructive', self.allow_destructive)
        self.progress = data.get('progress', self.progress)
        self.stream = data.get('stream', self.stream)
        self.subagent = data.get('subagent', self.subagent)
        self.route_model_enabled = data.get(
            'route_model_enabled', self.route_model_enabled
        )
        self.heartbeat_seconds = data.get('heartbeat_seconds', self.heartbeat_seconds)
        if not self._chat_explicit:
            self.chat = data.get('chat', self.chat)
        self.session_id = data.get('session_id', self.session_id)
        self.progress = data.get('progress', self.progress)
        self.stream = data.get('stream', self.stream)
        self.subagent = data.get('subagent', self.subagent)
        self.route_model_enabled = data.get(
            'route_model_enabled', self.route_model_enabled
        )
        self.heartbeat_seconds = data.get('heartbeat_seconds', self.heartbeat_seconds)

    def _save_tui_state(self) -> None:
        data = {
            'provider': self.provider,
            'model': self.model,
            'root': str(self.root),
            'permission_mode': self.permission_mode.value,
            'allow_destructive': self.allow_destructive,
            'progress': self.progress,
            'stream': self.stream,
            'subagent': self.subagent,
            'route_model_enabled': self.route_model_enabled,
            'heartbeat_seconds': self.heartbeat_seconds,
            'chat': self.chat,
            'session_id': self.session_id,
        }
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            self._state_path.write_text(
                json.dumps(data, indent=2, sort_keys=True), encoding='utf-8'
            )
        except OSError:
            return

    def _get_store(self) -> GraphQLiteGraphStore:
        if self._store is None:
            self._store = GraphQLiteGraphStore(GraphQLiteConfig(database=self.database))
        return self._store

    def _load_workspace_defaults(self) -> None:
        from teaagent.ergonomics.workspace_defaults import load_workspace_defaults
        from teaagent.policy import parse_permission_mode

        defaults = load_workspace_defaults(self.root)
        provider = defaults.get('provider')
        if isinstance(provider, str) and provider:
            self.provider = provider
        permission_mode = defaults.get('permission_mode')
        if isinstance(permission_mode, str) and permission_mode:
            self.permission_mode = parse_permission_mode(permission_mode)
        heartbeat = defaults.get('heartbeat')
        if isinstance(heartbeat, (int, float)):
            self.heartbeat_seconds = float(heartbeat)

    def _print_header(self) -> None:
        from teaagent.tui._setup import workspace_configured

        self.output_fn(f'TeaAgent TUI {__version__}')
        self.output_fn("Type 'help' for commands. Type 'exit' to quit.")
        if not workspace_configured(self.root):
            self.output_fn(
                "Workspace not configured — type 'setup' or run 'teaagent setup'."
            )

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
    chat: bool = False,
    input_fn: Optional[InputFn] = None,
    run_setup: bool = False,
    setup_write_env: bool = False,
) -> int:
    tui = TeaAgentTUI(
        database=database,
        provider=provider,
        model=model,
        root=root,
        allow_destructive=allow_destructive,
        permission_mode=permission_mode,
        input_fn=input_fn,
    )
    if chat:
        tui.chat = True
        tui._chat_explicit = True
    return tui.run(run_setup=run_setup, setup_write_env=setup_write_env)

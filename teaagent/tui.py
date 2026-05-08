from __future__ import annotations

import json
from pathlib import Path
import shlex
from typing import Callable, Optional

from teaagent import __version__
from teaagent.chat_agent import ChatAgentConfig, run_chat_agent
from teaagent.graphqlite_store import GraphQLiteConfig, GraphQLiteGraphStore, check_graphqlite_runtime
from teaagent.llm import LLMAdapter, available_providers, create_llm_adapter
from teaagent.run_store import RunStore


InputFn = Callable[[str], str]
OutputFn = Callable[[str], None]
AdapterFactory = Callable[[str, Optional[str]], LLMAdapter]


HELP_TEXT = """Commands:
  help                      Show this help.
  doctor                    Check GraphQLite runtime.
  provider <name>           Set model provider: claude, gpt, gemini, openrouter, opencodezen-go.
  model <name|default>      Set or clear model override.
  root <path>               Set workspace root for agent tasks.
  destructive <on|off>      Allow or block destructive workspace tools.
  ask <task>                Run a model-driven agent task with workspace tools.
  runs                      List recent persisted agent runs.
  show <run_id>             Show one persisted run record.
  use <database>            Switch database path. Use :memory: for in-memory.
  smoke                     Create a SmokeTest node and query it.
  query <cypher>            Execute a Cypher query.
  exit | quit               Leave the TUI.
"""


class TeaAgentTUI:
    def __init__(
        self,
        *,
        database: str = ":memory:",
        provider: str = "gpt",
        model: Optional[str] = None,
        root: str | Path = ".",
        allow_destructive: bool = False,
        input_fn: InputFn = input,
        output_fn: OutputFn = print,
        adapter_factory: AdapterFactory = create_llm_adapter,
    ) -> None:
        self.database = database
        self.provider = provider
        self.model = model
        self.root = Path(root).resolve()
        self.allow_destructive = allow_destructive
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
                self.output_fn("bye")
                return 0

            should_continue = self.handle_command(raw_command)
            if not should_continue:
                return 0

    def handle_command(self, raw_command: str) -> bool:
        command = raw_command.strip()
        if not command:
            return True
        try:
            parts = shlex.split(command)
        except ValueError as exc:
            self.output_fn(f"error: {exc}")
            return True

        action = parts[0].lower()
        args = parts[1:]
        if action in {"exit", "quit"}:
            self.output_fn("bye")
            return False
        if action == "help":
            self.output_fn(HELP_TEXT.rstrip())
            return True
        if action == "doctor":
            ok, message = check_graphqlite_runtime(self.database)
            self._print_json({"ok": ok, "message": message})
            return True
        if action == "provider":
            if len(args) != 1:
                self.output_fn("error: provider requires exactly one provider name")
                return True
            if args[0] not in available_providers():
                self.output_fn(f"error: unknown provider '{args[0]}'")
                return True
            self.provider = args[0]
            self.output_fn(f"provider: {self.provider}")
            return True
        if action == "model":
            if len(args) != 1:
                self.output_fn("error: model requires a model name or 'default'")
                return True
            self.model = None if args[0] == "default" else args[0]
            self.output_fn(f"model: {self.model or 'default'}")
            return True
        if action == "root":
            if len(args) != 1:
                self.output_fn("error: root requires exactly one path")
                return True
            self.root = Path(args[0]).resolve()
            self.output_fn(f"root: {self.root}")
            return True
        if action == "destructive":
            if len(args) != 1 or args[0] not in {"on", "off"}:
                self.output_fn("error: destructive requires 'on' or 'off'")
                return True
            self.allow_destructive = args[0] == "on"
            self.output_fn(f"destructive: {'on' if self.allow_destructive else 'off'}")
            return True
        if action == "ask":
            if not args:
                self.output_fn("error: ask requires a task")
                return True
            self._run_agent_task(" ".join(args))
            return True
        if action == "runs":
            store = RunStore(self.root)
            self._print_json([summary.to_dict() for summary in store.list_runs()])
            return True
        if action == "show":
            if len(args) != 1:
                self.output_fn("error: show requires a run id")
                return True
            self._print_json(RunStore(self.root).show_run(args[0]))
            return True
        if action == "use":
            if len(args) != 1:
                self.output_fn("error: use requires exactly one database path")
                return True
            self.database = args[0]
            self._store = None
            self.output_fn(f"database: {self.database}")
            return True
        if action == "smoke":
            store = self._get_store()
            store.graph.upsert_node("teaagent", {"name": "TeaAgent"}, label="SmokeTest")
            self._print_json(store.query("MATCH (n:SmokeTest) RETURN n.name"))
            return True
        if action == "query":
            if not args:
                self.output_fn("error: query requires a Cypher string")
                return True
            self._print_json(self._get_store().query(" ".join(args)))
            return True

        self.output_fn(f"error: unknown command '{action}'. Type 'help'.")
        return True

    def _run_agent_task(self, task: str) -> None:
        self.output_fn(f"agent: provider={self.provider} root={self.root}")
        adapter = self.adapter_factory(self.provider, self.model)
        store = RunStore(self.root)
        audit = store.audit_logger()
        result = run_chat_agent(
            task=task,
            adapter=adapter,
            config=ChatAgentConfig.from_root(
                self.root,
                model=self.model,
                allow_destructive=self.allow_destructive,
            ),
            audit=audit,
        )
        store.logger_for_result(result, audit)
        self._print_json(
            {
                "run_id": result.run_id,
                "status": result.status,
                "iterations": result.iterations,
                "tool_calls": result.tool_calls,
                "final_answer": result.final_answer.content if result.final_answer else None,
            }
        )

    def _get_store(self) -> GraphQLiteGraphStore:
        if self._store is None:
            self._store = GraphQLiteGraphStore(GraphQLiteConfig(database=self.database))
        return self._store

    def _print_header(self) -> None:
        self.output_fn(f"TeaAgent TUI {__version__}")
        self.output_fn("Type 'help' for commands. Type 'exit' to quit.")

    def _prompt(self) -> str:
        destructive = "!" if self.allow_destructive else ""
        model = self.model or "default"
        return f"teaagent[{self.provider}:{model}{destructive}]> "

    def _print_json(self, value) -> None:
        self.output_fn(json.dumps(value, ensure_ascii=False, sort_keys=True))


def run_tui(
    *,
    database: str = ":memory:",
    provider: str = "gpt",
    model: Optional[str] = None,
    root: str | Path = ".",
    allow_destructive: bool = False,
) -> int:
    return TeaAgentTUI(
        database=database,
        provider=provider,
        model=model,
        root=root,
        allow_destructive=allow_destructive,
    ).run()

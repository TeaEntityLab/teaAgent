from __future__ import annotations

import json
import shlex
from typing import Callable, Optional

from teaagent import __version__
from teaagent.graphqlite_store import GraphQLiteConfig, GraphQLiteGraphStore, check_graphqlite_runtime


InputFn = Callable[[str], str]
OutputFn = Callable[[str], None]


HELP_TEXT = """Commands:
  help                      Show this help.
  doctor                    Check GraphQLite runtime.
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
        input_fn: InputFn = input,
        output_fn: OutputFn = print,
    ) -> None:
        self.database = database
        self.input_fn = input_fn
        self.output_fn = output_fn
        self._store: Optional[GraphQLiteGraphStore] = None

    def run(self) -> int:
        self._print_header()
        while True:
            try:
                raw_command = self.input_fn(f"teaagent[{self.database}]> ")
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

    def _get_store(self) -> GraphQLiteGraphStore:
        if self._store is None:
            self._store = GraphQLiteGraphStore(GraphQLiteConfig(database=self.database))
        return self._store

    def _print_header(self) -> None:
        self.output_fn(f"TeaAgent TUI {__version__}")
        self.output_fn("Type 'help' for commands. Type 'exit' to quit.")

    def _print_json(self, value) -> None:
        self.output_fn(json.dumps(value, ensure_ascii=False, sort_keys=True))


def run_tui(*, database: str = ":memory:") -> int:
    return TeaAgentTUI(database=database).run()

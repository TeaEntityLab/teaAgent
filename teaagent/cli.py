from __future__ import annotations

import argparse
import json
from typing import Any, Optional

from teaagent import __version__
from teaagent.graphqlite_store import GraphQLiteConfig, GraphQLiteGraphStore, check_graphqlite_runtime
from teaagent.tui import run_tui


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="teaagent", description="TeaAgent harness utilities.")
    parser.add_argument("--version", action="version", version=f"teaagent {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    tui = subparsers.add_parser(
        "tui",
        help="Start an interactive terminal UI.",
        description="Start an interactive terminal UI.",
    )
    tui.add_argument("--database", default=":memory:", help="SQLite database path. Defaults to :memory:.")
    tui.set_defaults(func=start_tui)

    doctor = subparsers.add_parser("doctor", help="Run environment checks.")
    doctor_subparsers = doctor.add_subparsers(dest="doctor_command", required=True)
    graphqlite_doctor = doctor_subparsers.add_parser("graphqlite", help="Check GraphQLite runtime availability.")
    graphqlite_doctor.add_argument("--database", default=":memory:", help="SQLite database path. Defaults to :memory:.")
    graphqlite_doctor.set_defaults(func=doctor_graphqlite)

    graphqlite = subparsers.add_parser("graphqlite", help="Run GraphQLite operations.")
    graphqlite_subparsers = graphqlite.add_subparsers(dest="graphqlite_command", required=True)

    query = graphqlite_subparsers.add_parser("query", help="Execute a Cypher query against GraphQLite.")
    query.add_argument("cypher", help="Cypher query to execute.")
    query.add_argument("--database", default=":memory:", help="SQLite database path. Defaults to :memory:.")
    query.set_defaults(func=graphqlite_query)

    smoke = graphqlite_subparsers.add_parser("smoke", help="Create a node and run a real GraphQLite query.")
    smoke.add_argument("--database", default=":memory:", help="SQLite database path. Defaults to :memory:.")
    smoke.set_defaults(func=graphqlite_smoke)
    return parser


def doctor_graphqlite(args: argparse.Namespace) -> int:
    ok, message = check_graphqlite_runtime(args.database)
    print(json.dumps({"ok": ok, "message": message}, sort_keys=True))
    return 0 if ok else 1


def start_tui(args: argparse.Namespace) -> int:
    return run_tui(database=args.database)


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


def print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())

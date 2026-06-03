"""Working example: registering a custom tool and running a chat session.

Run without API keys (uses deterministic decide function):

    python3 docs/guides/examples/custom_tool.py
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

from teaagent.audit import AuditLogger
from teaagent.budget import RunBudget
from teaagent.policy import ApprovalPolicy, PermissionMode
from teaagent.runner import AgentRunner, FinalAnswer, ToolRequest
from teaagent.tools import ToolAnnotations, ToolRegistry
from teaagent.workspace_tools import build_workspace_tool_registry


def make_db(path: Path) -> None:
    con = sqlite3.connect(path)
    con.execute(
        'CREATE TABLE issues (id INTEGER PRIMARY KEY, title TEXT, open INTEGER)'
    )
    con.executemany(
        'INSERT INTO issues VALUES (?,?,?)',
        [(1, 'Fix login bug', 1), (2, 'Update deps', 1), (3, 'Old closed issue', 0)],
    )
    con.commit()
    con.close()


def build_registry(workspace: Path, db_path: Path) -> ToolRegistry:
    registry = build_workspace_tool_registry(workspace)

    # Register a custom read-only SQL tool
    registry.register(
        name='query_issues',
        description=(
            'Run a read-only SELECT against the issues database. '
            'Returns rows as a list of dicts.'
        ),
        input_schema={
            'type': 'object',
            'properties': {
                'sql': {
                    'type': 'string',
                    'description': 'SELECT statement. No writes allowed.',
                },
            },
            'required': ['sql'],
        },
        output_schema={
            'type': 'object',
            'properties': {
                'rows': {'type': 'array'},
                'count': {'type': 'integer'},
            },
            'required': ['rows', 'count'],
        },
        annotations=ToolAnnotations(read_only=True, idempotent=True),
        handler=lambda args: _run_query(db_path, args['sql']),
    )
    return registry


def _run_query(db_path: Path, sql: str) -> dict:
    sql_upper = sql.strip().upper()
    if not sql_upper.startswith('SELECT'):
        raise ValueError('Only SELECT statements are allowed.')
    con = sqlite3.connect(db_path)
    cur = con.execute(sql)
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, row)) for row in cur.fetchall()]
    con.close()
    return {'rows': rows, 'count': len(rows)}


def demo() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        workspace = Path(tmp)
        db_path = workspace / 'project.db'
        make_db(db_path)

        registry = build_registry(workspace, db_path)
        audit = AuditLogger(path=workspace / '.teaagent' / 'audit.jsonl')

        budget = RunBudget(max_iterations=5, max_tool_calls=3)
        policy = ApprovalPolicy(permission_mode=PermissionMode.READ_ONLY)

        # Deterministic decide function — no LLM needed for this demo
        step = [0]

        def decide(context):
            step[0] += 1
            if step[0] == 1:
                return ToolRequest(
                    tool_name='query_issues',
                    arguments={'sql': 'SELECT id, title FROM issues WHERE open=1'},
                )
            return FinalAnswer(content='Open issues retrieved successfully.')

        runner = AgentRunner(
            registry=registry, audit=audit, budget=budget, approval_policy=policy
        )
        result = runner.run(task='List all open issues', decide=decide)

        print(f'Status:      {result.status}')
        print(f'Iterations:  {result.iterations}')
        print(f'Tool calls:  {result.tool_calls}')
        observations = [
            o for o in result.observations if o.get('tool_name') == 'query_issues'
        ]
        if observations:
            rows = observations[0].get('result', {}).get('rows', [])
            for row in rows:
                print(f'  #{row["id"]} {row["title"]}')


if __name__ == '__main__':
    demo()

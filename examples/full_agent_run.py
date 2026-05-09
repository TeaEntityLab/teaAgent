"""Full Agent Lifecycle Example.

Run this example without any LLM API keys:

    python3 examples/full_agent_run.py

It demonstrates the complete TeaAgent lifecycle:
1. Workspace tool registration
2. Audit logging
3. Memory catalog
4. Budget and approval policy
5. Agent runner with a deterministic decision function
6. Tool execution and observation collection
7. Run store persistence and replay
8. Audit log inspection and pruning
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from uuid import uuid4

from teaagent.audit import AuditLogger
from teaagent.budget import RunBudget
from teaagent.memory import MemoryCatalog
from teaagent.policy import ApprovalPolicy, PermissionMode
from teaagent.run_store import RunStore
from teaagent.runner import AgentRunner, FinalAnswer, ToolRequest
from teaagent.telemetry import InMemoryMetricsSink
from teaagent.workspace_tools import WorkspaceToolConfig, build_workspace_tool_registry


def demo() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        workspace = Path(tmp) / 'workspace'
        workspace.mkdir()
        rprint('=== workspace', str(workspace))

        # ── 1. Workspace tools ──────────────────────────────────────────
        config = WorkspaceToolConfig.from_root(workspace)
        registry = build_workspace_tool_registry(workspace)
        rprint('=== tools', len(registry.mcp_metadata()))
        rprint(
            '=== config max_read',
            config.max_read_bytes,
            'max_write',
            config.max_write_bytes,
        )

        # ── 2. Audit + metrics ──────────────────────────────────────────
        audit = AuditLogger(path=workspace / '.teaagent' / 'audit.jsonl')
        metrics = InMemoryMetricsSink()
        audit.add_sink(metrics.handle_event)

        # ── 3. Memory catalog ───────────────────────────────────────────
        memory = MemoryCatalog(workspace)
        memory.add('Prefer concise answers.', tags=('style',))
        rprint('=== memory entries', len(memory.list()))

        # ── 4. Budget and approval ──────────────────────────────────────
        budget = RunBudget(max_iterations=5, max_tool_calls=3)
        approval = ApprovalPolicy(permission_mode=PermissionMode.WORKSPACE_WRITE)

        # ── 5. Deterministic decision function (no LLM needed) ──────────
        step = [0]

        def decide(context):
            step[0] += 1
            if step[0] == 1:
                # Write a file that says hello.
                return ToolRequest(
                    tool_name='workspace_write_file',
                    arguments={'path': 'greeting.txt', 'content': 'hello from agent\n'},
                )
            if step[0] == 2:
                # Read it back.
                return ToolRequest(
                    tool_name='workspace_read_file',
                    arguments={'path': 'greeting.txt'},
                )
            # After reading, emit a final answer.
            return FinalAnswer(content='done')

        # ── 6. Agent runner ─────────────────────────────────────────────
        runner = AgentRunner(
            registry=registry,
            audit=audit,
            budget=budget,
            approval_policy=approval,
        )
        result = runner.run(
            task='write a greeting file then read it back', decide=decide
        )
        rprint(
            '=== result',
            result.status,
            'itr',
            result.iterations,
            'tc',
            result.tool_calls,
        )

        # ── 7. Run store ────────────────────────────────────────────────
        store = RunStore(workspace)
        store.logger_for_result(result, audit)
        runs = store.list_runs(limit=5)
        rprint('=== runs', len(runs))
        rprint('=== run summary', runs[0].task, runs[0].status)

        # ── 8. Audit replay ─────────────────────────────────────────────
        events = store.show_run(result.run_id)
        rprint('=== audit events', len(events))
        for evt in events:
            rprint(f'    {evt["event_type"]:30s}  run_id={evt["run_id"][:8]}...')

        # ── 9. Metrics snapshot ─────────────────────────────────────────
        snap = metrics.snapshot()
        rprint('=== counters', dict(snap.counters))

        # ── 10. Cleanup ─────────────────────────────────────────────────
        audit_pruner = AuditLogger()
        audit_pruner.record('run_started', uuid4().hex)
        audit_pruner.record('run_completed', uuid4().hex)
        rprint('=== ok')


def rprint(label, *values):
    print(f'{label:<24}', *values)


if __name__ == '__main__':
    demo()

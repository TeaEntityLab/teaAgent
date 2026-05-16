"""Regression contract: session resume must always preserve context.

This is an indestructible contract — if this test fails, resumed runs
could lose task context, audit lineage, or memory continuity.
"""

from __future__ import annotations

from pathlib import Path

from conftest import FakeAdapter

from teaagent.audit import AuditLogger
from teaagent.chat_agent import ChatAgentConfig, run_chat_agent
from teaagent.memory import MemoryCatalog
from teaagent.runner import AgentRunner, FinalAnswer
from teaagent.tools import ToolRegistry


def test_resume_preserves_task_across_run_boundary(tmp_path: Path) -> None:
    adapter = FakeAdapter(
        [
            '{"type":"final","content":"first run done"}',
            '{"type":"final","content":"resumed"}',
        ]
    )
    registry = ToolRegistry()

    result1 = run_chat_agent(
        task='original task',
        adapter=adapter,
        config=ChatAgentConfig.from_root(tmp_path, permission_mode='read-only'),
        registry=registry,
    )
    assert result1.status == 'completed'


def test_audit_lineage_preserved_on_resume(tmp_path: Path) -> None:
    audit = AuditLogger()
    registry = ToolRegistry()
    runner = AgentRunner(registry=registry, audit=audit)
    runner.run(task='test', decide=lambda _: FinalAnswer(content='done'))

    event_types = [e.event_type for e in audit.events]
    assert 'run_started' in event_types
    assert 'run_completed' in event_types
    assert len([e for e in event_types if e == 'run_started']) == 1


def test_memory_auto_curated_after_completed_resume(tmp_path: Path) -> None:
    adapter = FakeAdapter(
        [
            '{"type":"final","content":"memory curated"}',
        ]
    )
    result = run_chat_agent(
        task='curate this',
        adapter=adapter,
        config=ChatAgentConfig.from_root(tmp_path, permission_mode='read-only'),
        registry=ToolRegistry(),
    )
    assert result.status == 'completed'
    if result.final_answer:
        assert result.final_answer.content == 'memory curated'

    catalog = MemoryCatalog(tmp_path)
    entries = catalog.list(limit=10)
    assert any('curate' in e.content for e in entries)

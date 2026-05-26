"""AC: failed workspace writes must not create undoable journals."""

from __future__ import annotations

from pathlib import Path

from conftest import FakeAdapter

from teaagent.audit import AuditLogger
from teaagent.chat_agent import ChatAgentConfig, run_chat_agent
from teaagent.run_store import RunStore
from teaagent.run_undo import UndoJournal


def test_failed_write_does_not_persist_undo_journal(tmp_path: Path) -> None:
    target = tmp_path / 'notes.txt'
    target.write_text('user-owned\n', encoding='utf-8')

    adapter = FakeAdapter(
        [
            '{"type":"tool","tool_name":"workspace_apply_patch","arguments":{"path":"notes.txt","old":"missing text","new":"agent\\n"},"call_id":"fail-write"}',
            '{"type":"final","content":"attempted write"}',
        ]
    )

    audit = AuditLogger()
    journal = UndoJournal(tmp_path)
    audit.add_sink(journal)

    result = run_chat_agent(
        task='Try to update notes.txt',
        adapter=adapter,
        config=ChatAgentConfig.from_root(
            tmp_path,
            allow_destructive=True,
            max_iterations=4,
            max_tool_calls=4,
        ),
        audit=audit,
    )

    assert result.status == 'completed'
    assert target.read_text(encoding='utf-8') == 'user-owned\n'
    assert not journal.has_entries
    assert not RunStore(tmp_path).undo_path(result.run_id).exists()

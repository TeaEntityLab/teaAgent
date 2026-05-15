"""AC-NEW-21: Reversible change recovery flow.

As a user, I want to recover from agent-authored file edits by restoring the
workspace to its pre-run state.

Acceptance criteria:
- Undo journal captures pre-write state for modified and newly created files.
- Restoring undo journal reverts modified files and deletes newly created files.
- Restore summary reports restored/deleted paths with no errors.
"""

from __future__ import annotations

from pathlib import Path

from conftest import FakeAdapter

from teaagent.audit import AuditLogger
from teaagent.chat_agent import ChatAgentConfig, run_chat_agent
from teaagent.run_undo import UndoJournal


def test_run_undo_restores_workspace_after_agent_writes(tmp_path: Path) -> None:
    existing = tmp_path / "notes.txt"
    existing.write_text("before\n", encoding="utf-8")

    adapter = FakeAdapter(
        [
            '{"type":"tool","tool_name":"workspace_write_file","arguments":{"path":"notes.txt","content":"after\\n"},"call_id":"write-existing"}',
            '{"type":"tool","tool_name":"workspace_write_file","arguments":{"path":"new.txt","content":"created\\n"},"call_id":"write-new"}',
            '{"type":"final","content":"writes complete"}',
        ]
    )

    audit = AuditLogger()
    journal = UndoJournal(tmp_path, path=tmp_path / ".teaagent" / "undo.jsonl")
    audit.add_sink(journal)

    result = run_chat_agent(
        task="Update notes and create a companion file",
        adapter=adapter,
        config=ChatAgentConfig.from_root(
            tmp_path,
            allow_destructive=True,
            max_iterations=6,
            max_tool_calls=6,
        ),
        audit=audit,
    )

    assert result.status == "completed"
    assert existing.read_text(encoding="utf-8") == "after\n"
    assert (tmp_path / "new.txt").read_text(encoding="utf-8") == "created\n"

    undo = journal.restore()
    assert undo.ok is True
    assert "notes.txt" in undo.restored
    assert "new.txt" in undo.deleted
    assert undo.errors == []
    assert existing.read_text(encoding="utf-8") == "before\n"
    assert not (tmp_path / "new.txt").exists()

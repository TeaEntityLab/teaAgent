"""AC-NEW-16: Memory auto-curation flow.

As a user, I want successful agent runs to auto-curate a concise memory entry,
so that future runs can reuse high-signal outcomes without manual memory add.

Acceptance criteria:
- Completed runs append one curated memory entry.
- Curated memory includes task and final answer.
- Curated memory records the last tool name when tools were used.
"""

from __future__ import annotations

from pathlib import Path

from conftest import FakeAdapter

from teaagent import ChatAgentConfig, MemoryCatalog, run_chat_agent


def test_completed_run_auto_curates_memory(tmp_path: Path) -> None:
    (tmp_path / 'README.md').write_text('hello', encoding='utf-8')
    adapter = FakeAdapter(
        [
            '{"type":"tool","tool_name":"workspace_read_file","arguments":{"path":"README.md"},"call_id":"read-1"}',
            '{"type":"final","content":"summarized README"}',
        ]
    )

    result = run_chat_agent(
        ChatAgentConfig.from_root(tmp_path),
        'Summarize README',
        adapter=adapter,
    )

    assert result.status == 'completed'
    memories = MemoryCatalog(tmp_path).list_quarantined(limit=5)
    assert memories, 'expected at least one quarantined memory entry'
    latest = memories[0]
    assert 'Summarize README' in latest.content
    assert 'summarized README' in latest.content
    assert 'workspace_read_file' in latest.content
    assert 'auto-curated' in latest.tags


def test_auto_curated_memory_deduplicates_identical_summary(tmp_path: Path) -> None:
    (tmp_path / 'README.md').write_text('hello', encoding='utf-8')
    first = run_chat_agent(
        ChatAgentConfig.from_root(tmp_path),
        'Summarize README',
        adapter=FakeAdapter(
            [
                '{"type":"tool","tool_name":"workspace_read_file","arguments":{"path":"README.md"},"call_id":"read-1"}',
                '{"type":"final","content":"summarized README"}',
            ]
        ),
    )
    second = run_chat_agent(
        ChatAgentConfig.from_root(tmp_path),
        'Summarize README',
        adapter=FakeAdapter(
            [
                '{"type":"tool","tool_name":"workspace_read_file","arguments":{"path":"README.md"},"call_id":"read-1"}',
                '{"type":"final","content":"summarized README"}',
            ]
        ),
    )

    assert first.status == 'completed'
    assert second.status == 'completed'
    memories = MemoryCatalog(tmp_path).list_quarantined(limit=20)
    matches = [m for m in memories if 'Outcome: summarized README' in m.content]
    assert len(matches) == 1


def test_auto_curated_memory_not_written_for_pending_approval(tmp_path: Path) -> None:
    result = run_chat_agent(
        ChatAgentConfig.from_root(tmp_path),
        'Create TODO',
        adapter=FakeAdapter(
            [
                '{"type":"tool","tool_name":"workspace_write_file","arguments":{"path":"TODO.md","content":"x"},"call_id":"write-1"}'
            ]
        ),
    )

    assert result.status == 'pending_approval'
    quarantined = MemoryCatalog(tmp_path).list_quarantined(limit=10)
    auto_curated = [m for m in quarantined if 'auto-curated' in m.tags]
    assert auto_curated == []

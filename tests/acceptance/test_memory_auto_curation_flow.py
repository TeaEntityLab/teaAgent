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
        task='Summarize README',
        adapter=adapter,
        config=ChatAgentConfig.from_root(tmp_path),
    )

    assert result.status == 'completed'
    memories = MemoryCatalog(tmp_path).list(limit=5)
    assert memories, 'expected at least one memory entry'
    latest = memories[0]
    assert 'Summarize README' in latest.content
    assert 'summarized README' in latest.content
    assert 'workspace_read_file' in latest.content
    assert 'auto-curated' in latest.tags

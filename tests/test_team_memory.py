from __future__ import annotations

import tempfile

from teaagent.memory.team_memory import TeamMemory


class TestTeamMemory:
    def test_add_appends_entry_with_timestamp(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            memory = TeamMemory(root=tmp)
            line = memory.add('shared coding standards for auth module')

            assert 'shared coding standards for auth module' in line
            assert memory._path.is_file()
            content = memory._path.read_text(encoding='utf-8')
            assert 'shared coding standards for auth module' in content
            assert content.startswith('-')

    def test_list_returns_added_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            memory = TeamMemory(root=tmp)
            memory.add('first team note')
            memory.add('second team note')

            entries = memory.list()
            assert len(entries) == 2
            assert any('first team note' in e for e in entries)
            assert any('second team note' in e for e in entries)

    def test_list_empty_when_no_file(self) -> None:
        memory = TeamMemory(root='/nonexistent/path')
        assert memory.list() == []

    def test_inject_prompt_includes_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            memory = TeamMemory(root=tmp)
            memory.add('important team convention')
            memory.add('security policy update')

            snippet = memory.inject_prompt(limit_tokens=2048)
            assert '[team-memory]' in snippet
            assert 'important team convention' in snippet
            assert 'security policy update' in snippet

    def test_inject_prompt_empty_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            memory = TeamMemory(root=tmp)
            snippet = memory.inject_prompt()
            assert 'No shared team context available' in snippet

    def test_inject_prompt_respects_token_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            memory = TeamMemory(root=tmp)
            long_entry = 'x' * 5000
            memory.add(long_entry)

            snippet = memory.inject_prompt(limit_tokens=10)
            assert len(snippet) < 2000

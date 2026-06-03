"""AC: REPL undo cannot destroy un-agented work (P0-2, fixes CG-02)."""

from __future__ import annotations

import base64
import io
import json
from pathlib import Path

from teaagent.chat_session_controller import ChatSessionController
from teaagent.run_store import RunStore


def test_undo_preserves_manual_edits(tmp_path: Path) -> None:
    """Test that /undo only reverts agent-authored files, not manual edits (CG-02)."""
    # Create manual edit to file A (un-agented work)
    file_a = tmp_path / 'manual.txt'
    file_a.write_text('manual edit\n', encoding='utf-8')
    original_a_content = file_a.read_text(encoding='utf-8')

    # Task will edit file B (agent-authored work)
    file_b = tmp_path / 'agent.txt'
    file_b.write_text('original\n', encoding='utf-8')

    # Simulate agent editing file B by creating a manual undo journal
    store = RunStore(tmp_path)
    run_id = 'test-run-001'
    undo_path = store.undo_path(run_id)
    undo_path.parent.mkdir(parents=True, exist_ok=True)

    # Create journal entry for file B only (not file A)
    original_content_b64 = base64.b64encode(b'original\n').decode('ascii')
    journal_entry = {
        'path': 'agent.txt',
        'existed_before': True,
        'content_b64': original_content_b64,
    }
    undo_path.write_text(json.dumps(journal_entry), encoding='utf-8')

    # Create a minimal run summary so latest_run_with_undo can find it
    run_summary_path = store.store_dir / f'{run_id}.jsonl'
    run_summary_path.write_text(
        json.dumps(
            {
                'run_id': run_id,
                'task': 'edit agent.txt',
                'status': 'completed',
                'created_at': '2026-06-02T00:00:00Z',
                'updated_at': '2026-06-02T00:00:00Z',
            }
        ),
        encoding='utf-8',
    )

    # Actually edit file B
    file_b.write_text('agent edited\n', encoding='utf-8')

    output_buffer = io.StringIO()

    def output_fn(s: str) -> None:
        output_buffer.write(s + '\n')

    controller = ChatSessionController(tmp_path, output_fn=output_fn)

    # Undo should only revert file B, not file A
    undo_success = controller.undo_last_run()

    assert undo_success, 'Undo should succeed'
    assert file_a.read_text(encoding='utf-8') == original_a_content, (
        'Manual edit should be preserved'
    )
    assert file_b.read_text(encoding='utf-8') == 'original\n', (
        'Agent edit should be reverted'
    )


def test_undo_noop_without_journal(tmp_path: Path) -> None:
    """Test that /undo with no journal is a no-op (CG-02)."""
    # Create files
    file_a = tmp_path / 'file_a.txt'
    file_b = tmp_path / 'file_b.txt'
    file_a.write_text('content a\n', encoding='utf-8')
    file_b.write_text('content b\n', encoding='utf-8')

    # Get initial state
    initial_a = file_a.read_text(encoding='utf-8')
    initial_b = file_b.read_text(encoding='utf-8')

    output_buffer = io.StringIO()

    def output_fn(s: str) -> None:
        output_buffer.write(s + '\n')

    controller = ChatSessionController(tmp_path, output_fn=output_fn)

    # Undo with no journal should be a no-op
    undo_success = controller.undo_last_run()

    assert not undo_success, 'Undo should fail with no journal'
    assert file_a.read_text(encoding='utf-8') == initial_a, 'File A should be unchanged'
    assert file_b.read_text(encoding='utf-8') == initial_b, 'File B should be unchanged'

    output = output_buffer.getvalue()
    assert 'Nothing to undo' in output or 'no undo journal' in output, (
        f'Expected "nothing to undo" message, got: {output}'
    )


def test_undo_preserves_untracked_files(tmp_path: Path) -> None:
    """Test that /undo does not affect files the agent never touched (CG-02)."""
    # Create multiple files
    untouched = tmp_path / 'untouched.txt'
    untouched.write_text('never touched\n', encoding='utf-8')

    edited = tmp_path / 'edited.txt'
    edited.write_text('before\n', encoding='utf-8')

    # Simulate agent editing edited.txt by creating a manual undo journal
    store = RunStore(tmp_path)
    run_id = 'test-run-002'
    undo_path = store.undo_path(run_id)
    undo_path.parent.mkdir(parents=True, exist_ok=True)

    # Create journal entry for edited.txt only (not untouched.txt)
    before_content_b64 = base64.b64encode(b'before\n').decode('ascii')
    journal_entry = {
        'path': 'edited.txt',
        'existed_before': True,
        'content_b64': before_content_b64,
    }
    undo_path.write_text(json.dumps(journal_entry), encoding='utf-8')

    # Create a minimal run summary so latest_run_with_undo can find it
    run_summary_path = store.store_dir / f'{run_id}.jsonl'
    run_summary_path.write_text(
        json.dumps(
            {
                'run_id': run_id,
                'task': 'edit edited.txt',
                'status': 'completed',
                'created_at': '2026-06-02T00:00:00Z',
                'updated_at': '2026-06-02T00:00:00Z',
            }
        ),
        encoding='utf-8',
    )

    # Actually edit edited.txt
    edited.write_text('after\n', encoding='utf-8')

    output_buffer = io.StringIO()

    def output_fn(s: str) -> None:
        output_buffer.write(s + '\n')

    controller = ChatSessionController(tmp_path, output_fn=output_fn)

    # Undo
    undo_success = controller.undo_last_run()

    assert undo_success, 'Undo should succeed'
    assert edited.read_text(encoding='utf-8') == 'before\n', (
        'Edited file should be reverted'
    )
    assert untouched.read_text(encoding='utf-8') == 'never touched\n', (
        'Untouched file should remain unchanged'
    )

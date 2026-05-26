"""AC: user-facing undo restores agent-authored workspace edits."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from conftest import FakeAdapter

from teaagent.cli import main
from teaagent.run_store import RunStore


def test_agent_undo_restores_last_run_writes(tmp_path: Path) -> None:
    existing = tmp_path / 'notes.txt'
    existing.write_text('before\n', encoding='utf-8')

    adapter = FakeAdapter(
        [
            '{"type":"tool","tool_name":"workspace_write_file","arguments":{"path":"notes.txt","content":"after\\n"},"call_id":"write-existing"}',
            '{"type":"tool","tool_name":"workspace_write_file","arguments":{"path":"new.txt","content":"created\\n"},"call_id":"write-new"}',
            '{"type":"final","content":"writes complete"}',
        ]
    )

    run_out = io.StringIO()
    with (
        patch('teaagent.cli.create_llm_adapter', return_value=adapter),
        redirect_stdout(run_out),
    ):
        run_code = main(
            [
                'run',
                'gpt',
                'Update notes and create a companion file',
                '--root',
                str(tmp_path),
                '--permission-mode',
                'workspace-write',
                '--max-iterations',
                '6',
                '--max-tool-calls',
                '6',
            ]
        )
    run_payload = json.loads(run_out.getvalue())
    assert run_code == 0
    assert existing.read_text(encoding='utf-8') == 'after\n'
    assert (tmp_path / 'new.txt').is_file()

    undo_out = io.StringIO()
    with redirect_stdout(undo_out):
        undo_code = main(['agent', 'undo', '--root', str(tmp_path)])
    undo_payload = json.loads(undo_out.getvalue())
    assert undo_code == 0
    assert undo_payload['status'] == 'restored'
    assert undo_payload['audit_recorded'] is True
    assert undo_payload['run_id'] == run_payload['run_id']
    run_events = RunStore(tmp_path).show_run(run_payload['run_id'])
    undo_audit = [e for e in run_events if e.get('event_type') == 'undo_applied']
    assert len(undo_audit) == 1
    assert undo_audit[0]['payload']['restored'] == undo_payload['restored']
    assert 'notes.txt' in undo_payload['restored']
    assert 'new.txt' in undo_payload['deleted']
    assert existing.read_text(encoding='utf-8') == 'before\n'
    assert not (tmp_path / 'new.txt').exists()

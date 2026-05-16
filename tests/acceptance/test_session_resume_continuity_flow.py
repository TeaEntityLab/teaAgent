"""AC-NEW-23: Session resume continuity flow.

As a user, I want paused runs to resume with preserved context and audit
lineage, so work can continue across process boundaries.

Acceptance criteria:
- Initial run pauses on approval after prior observations are recorded.
- Resume replays prior observations via checkpoint/store continuity.
- Resume preserves task lineage and auto-approval metadata.
- Completed resumed run emits auto-curated memory.
"""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from conftest import FakeAdapter

from teaagent.cli import main
from teaagent.memory import MemoryCatalog


def test_session_resume_preserves_observations_audit_and_memory(tmp_path: Path) -> None:
    (tmp_path / 'README.md').write_text('hello teaagent', encoding='utf-8')
    checkpoint_db = tmp_path / '.teaagent' / 'checkpoints.sqlite3'

    first_adapter = FakeAdapter(
        [
            '{"type":"tool","tool_name":"workspace_read_file","arguments":{"path":"README.md"},"call_id":"read-1"}',
            '{"type":"tool","tool_name":"workspace_write_file","arguments":{"path":"TODO.md","content":"done"},"call_id":"write-1"}',
        ]
    )
    first_output = io.StringIO()
    with (
        patch('teaagent.cli.create_llm_adapter', return_value=first_adapter),
        redirect_stdout(first_output),
    ):
        first_exit = main(
            [
                'agent',
                'run',
                'gpt',
                'Summarize README and then create TODO.md',
                '--root',
                str(tmp_path),
                '--checkpoint-store',
                str(checkpoint_db),
            ]
        )
    first_payload = json.loads(first_output.getvalue())

    assert first_exit == 1
    assert first_payload['status'] == 'pending_approval'
    assert first_payload['approval']['call_id'] == 'write-1'
    assert first_payload['audit_summary']['approval_required'] is True
    assert first_payload['audit_summary']['tool_names'] == ['workspace_read_file']

    resume_adapter = FakeAdapter(
        [
            '{"type":"tool","tool_name":"workspace_write_file","arguments":{"path":"TODO.md","content":"done"},"call_id":"write-1"}',
            '{"type":"final","content":"created todo"}',
        ]
    )
    resume_output = io.StringIO()
    with (
        patch('teaagent.cli.create_llm_adapter', return_value=resume_adapter),
        redirect_stdout(resume_output),
    ):
        resume_exit = main(
            [
                'agent',
                'resume',
                'gpt',
                first_payload['run_id'],
                '--root',
                str(tmp_path),
                '--checkpoint-store',
                str(checkpoint_db),
            ]
        )
    resume_payload = json.loads(resume_output.getvalue())

    assert resume_exit == 0
    assert resume_payload['status'] == 'completed'
    assert resume_payload['resumed_from'] == first_payload['run_id']
    assert resume_payload['task'] == 'Summarize README and then create TODO.md'
    assert resume_payload['auto_approved_call_id'] == 'write-1'
    assert resume_payload['replayed_observations'] == 1
    assert resume_payload['audit_summary']['destructive_tool_calls'] == 1
    assert (tmp_path / 'TODO.md').read_text(encoding='utf-8') == 'done'

    show_output = io.StringIO()
    with redirect_stdout(show_output):
        show_exit = main(
            ['agent', 'show', resume_payload['run_id'], '--root', str(tmp_path)]
        )
    events = json.loads(show_output.getvalue())
    assert show_exit == 0
    run_started = next(
        event for event in events if event['event_type'] == 'run_started'
    )
    assert run_started['payload']['replayed_observations'] == 1

    memories = MemoryCatalog(tmp_path).search('created todo', limit=10)
    assert any(
        'created todo' in memory.content and 'auto-curated' in memory.tags
        for memory in memories
    )

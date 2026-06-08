"""IT: undo_applied events append to run audit logs with intact hash chain."""

from __future__ import annotations

from pathlib import Path

from teaagent.run_store import RunStore
from teaagent.runner import FinalAnswer, RunResult
from teaagent.types import verify_audit_chain


def test_record_undo_applied_appends_chained_event(tmp_path: Path) -> None:
    store = RunStore(tmp_path)
    run_id = 'run-undo-audit'
    audit = store.audit_logger(run_id)
    audit.record('run_started', run_id, task='write files')
    audit.record('run_completed', run_id, answer='done')
    store.logger_for_result(
        RunResult(
            run_id=run_id,
            status='completed',
            iterations=1,
            tool_calls=0,
            final_answer=FinalAnswer('done'),
        ),
        audit,
    )

    recorded = store.record_undo_applied(
        run_id,
        status='restored',
        restored=['notes.txt'],
        deleted=['new.txt'],
        errors=[],
        undo_journal_path='.teaagent/undo/run-undo-audit.jsonl',
    )
    assert recorded is True

    events = store.show_run(run_id)
    undo_events = [e for e in events if e.get('event_type') == 'undo_applied']
    assert len(undo_events) == 1
    payload = undo_events[0]['payload']
    assert payload['status'] == 'restored'
    assert payload['restored'] == ['notes.txt']
    assert payload['deleted'] == ['new.txt']

    result = verify_audit_chain(store.run_path(run_id))
    assert result.valid is True
    assert result.event_count == 3


def test_record_undo_applied_returns_false_when_run_missing(tmp_path: Path) -> None:
    store = RunStore(tmp_path)
    assert (
        store.record_undo_applied(
            'missing-run',
            status='restored',
            restored=[],
            deleted=[],
            errors=[],
        )
        is False
    )

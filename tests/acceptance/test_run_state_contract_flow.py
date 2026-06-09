"""SURF-001 acceptance: run-state contract is surface-independent."""

from __future__ import annotations

from teaagent.integration.run_state import build_run_state_snapshot
from teaagent.run_store import RunStore
from teaagent.types import AuditLogger


def test_run_state_contract_survives_background_attach_query(tmp_path) -> None:
    """Background attach and CLI status must read the same persisted contract."""
    run_id = 'bg-parity-run'
    store = RunStore(tmp_path)
    audit = AuditLogger(path=store.run_path(run_id))
    audit.record('run_started', run_id, task='background parity')
    audit.record('heartbeat', run_id, tick=3, interval_seconds=5.0)
    audit.record('run_paused', run_id, status='pending_approval')

    via_store = store.heartbeat_for_run(run_id)
    via_builder = build_run_state_snapshot(
        store.show_run(run_id),
        run_id,
        undo_available=store.undo_path(run_id).is_file(),
    ).to_dict()

    assert via_store == via_builder
    assert via_store['status'] == 'pending_approval'
    assert via_store['last_heartbeat_tick'] == 3
    assert via_store['schema_version'] == '1'

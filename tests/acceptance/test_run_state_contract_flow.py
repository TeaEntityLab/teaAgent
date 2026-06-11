"""Test module for run-state contract surface independence.

This module tests the run-state contract, which ensures that agent state is
represented consistently across different surfaces (CLI, TUI, background processes).
The contract enables surfaces to attach to running agents and query their state
without surface-specific coupling.

Key concepts tested:
- Surface Independence: Run state is accessible from CLI, TUI, and background processes
- Contract Consistency: Different surfaces read the same persisted state
- Background Attach: CLI can attach to background runs and query state
- State Snapshot: build_run_state_snapshot creates consistent state representations
- Heartbeat Tracking: State includes last heartbeat tick and interval
- Schema Versioning: State includes schema version for compatibility

Acceptance Criteria:
- AC1: Background attach and CLI status read the same persisted contract
- AC2: Run state includes status, last_heartbeat_tick, and schema_version
- AC3: State via RunStore matches state via build_run_state_snapshot
- AC4: Undo availability is correctly reflected in state contract
- AC5: Schema version is included for future compatibility

Technical Details:
- RunStore manages run state persistence and querying
- build_run_state_snapshot creates a consistent state representation
- Heartbeat tracking includes tick count and interval_seconds
- State contract is surface-independent (CLI, TUI, background)
- Undo availability is determined by undo_path existence
- Schema version enables future contract evolution

References:
- SURF-001 design: /docs/architecture/surf_001.md
- Run state contract: /docs/specs/run_state_contract.md
- Background attach: /docs/architecture/background_attach.md
"""

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

"""WDH-002 stranger session capture tooling."""

from __future__ import annotations

from teaagent.governance.stranger_session import (
    run_pilot_battery,
    run_simulated_happy_path_session,
)


def test_simulated_happy_path_meets_three_concept_target() -> None:
    record = run_simulated_happy_path_session(participant_id='test-01')
    assert record.completed_happy_path is True
    assert record.happy_path_concept_count == 3
    assert record.participant_type == 'simulated_pilot'


def test_pilot_battery_produces_three_records() -> None:
    records = run_pilot_battery()
    assert len(records) == 3
    assert sum(1 for record in records if record.completed_happy_path) >= 2

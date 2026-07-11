# test-type: behavior
"""Executable specification for the M4 operator-cockpit acceptance contract.

Companion to docs/specs/operator-cockpit-acceptance-spec-2026-07-11.md
(M4 exit criterion "control-plane operator cockpit acceptance", allowed under
the DR-006 owner-override co-maintainer-dogfood carve-out).

Pins the snapshot schema stability contract (spec section 3.2): frozen v1
top-level sections, the control-section field set the operator-question
mapping depends on, and plain-JSON serializability for automation consumers.
Core-section presence and CLI emission are already covered by
tests/acceptance/test_cockpit_snapshot_flow.py and are not duplicated here.
"""

from __future__ import annotations

import json
from pathlib import Path

from teaagent.integration.cockpit_parity import (
    COCKPIT_SNAPSHOT_SCHEMA_VERSION,
    build_cockpit_snapshot,
)

_V1_TOPLEVEL_SECTIONS = {
    'schema_version',
    'control',
    'pending_approvals',
    'stale_workspace',
}

_CONTROL_OPERATOR_FIELDS = {
    'spec',
    'goal',
    'model_route',
    'memory',
    'review',
    'skill',
    'approval',
    'cost',
    'last_updated',
}


def test_snapshot_toplevel_schema_is_frozen_for_v1(tmp_path: Path) -> None:
    """Schema v1 has exactly four top-level sections.

    Spec section 3.2: adding or removing a top-level section is a
    schema-version review event. This pin fails on any change, forcing the
    version bump + spec note to land in the same commit. schema_version is
    pinned to '1' for the same reason.
    """
    payload = build_cockpit_snapshot(tmp_path)
    assert set(payload) == _V1_TOPLEVEL_SECTIONS
    assert payload['schema_version'] == COCKPIT_SNAPSHOT_SCHEMA_VERSION == '1'


def test_control_section_carries_operator_answer_fields(
    tmp_path: Path,
) -> None:
    """The control section answers the spec's operator questions.

    Superset assertion (additive-only contract): the nine documented fields
    must be present; new fields may be added freely. Also verifies the
    snapshot reflects its inputs (Q3: cost spent against state) so the CLI
    flags are not decorative.
    """
    payload = build_cockpit_snapshot(
        tmp_path,
        permission_mode='read-only',
        cost_cents=350.0,
        cost_limit_cents=1000,
        cost_state='estimated',
    )
    control = payload['control']
    assert set(control) >= _CONTROL_OPERATOR_FIELDS
    assert control['cost']['spent_cents'] == 350.0
    assert control['approval']['pending_count'] == 0
    assert control['last_updated'] is not None


def test_snapshot_is_json_serializable_and_key_stable(tmp_path: Path) -> None:
    """The full payload serializes with the stdlib encoder and stable keys.

    Automation consumers (dashboards, --json scripting) rely on
    json.dumps working without a custom encoder, and on key sets being
    deterministic for the same workspace state. Values containing
    timestamps may differ between builds; key structure must not.
    """
    first = build_cockpit_snapshot(tmp_path)
    second = build_cockpit_snapshot(tmp_path)

    serialized = json.dumps(first)
    assert json.loads(serialized) == first

    assert set(first) == set(second)
    assert set(first['control']) == set(second['control'])
    assert set(first['stale_workspace']) == set(second['stale_workspace'])

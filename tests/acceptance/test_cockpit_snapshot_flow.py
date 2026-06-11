"""Test module for cockpit snapshot contract.

This module tests the cockpit snapshot system, which provides a unified view
of workspace state for operator dashboards. The snapshot includes control
status, pending approvals, and workspace health indicators.

Key concepts tested:
- Snapshot Construction: build_cockpit_snapshot creates unified workspace view
- Schema Version: Snapshot includes COCKPIT_SNAPSHOT_SCHEMA_VERSION
- Core Sections: Snapshot includes control, pending_approvals, stale_workspace
- CLI Integration: CLI cockpit command emits snapshot contract
- Operator Dashboard: Snapshot is designed for operator consumption

Acceptance Criteria:
- AC1: build_cockpit_snapshot includes schema_version field
- AC2: build_cockpit_snapshot includes control section
- AC3: build_cockpit_snapshot includes pending_approvals section
- AC4: build_cockpit_snapshot includes stale_workspace section
- AC5: CLI cockpit command returns snapshot with schema_version
- AC6: Control section includes approval subsection

Technical Details:
- COCKPIT_SNAPSHOT_SCHEMA_VERSION ensures schema compatibility
- build_cockpit_snapshot aggregates state from multiple sources
- Control section includes: approval, budget, sessions
- Pending approvals shows current approval queue
- Stale workspace detects files changed on disk
- CLI cockpit command returns JSON snapshot

References:
- Cockpit design: /docs/architecture/cockpit.md
- Snapshot spec: /docs/specs/cockpit_snapshot.md
"""

from __future__ import annotations

import io
import json
import tempfile
from contextlib import redirect_stdout

from teaagent.cli import main
from teaagent.integration.cockpit_parity import (
    COCKPIT_SNAPSHOT_SCHEMA_VERSION,
    build_cockpit_snapshot,
)


def test_build_cockpit_snapshot_includes_core_sections() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        payload = build_cockpit_snapshot(tmp)
        assert payload['schema_version'] == COCKPIT_SNAPSHOT_SCHEMA_VERSION
        assert 'control' in payload
        assert 'pending_approvals' in payload
        assert 'stale_workspace' in payload
        assert 'approval' in payload['control']


def test_cli_cockpit_emits_snapshot_contract() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(['cockpit', '--root', tmp])
        assert code == 0
        payload = json.loads(out.getvalue())
        assert payload['schema_version'] == COCKPIT_SNAPSHOT_SCHEMA_VERSION

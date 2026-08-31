"""Guard for H4 shadow demo scaffold (ADR-0031 criterion 1 exercisable).

Runs scripts/exercise_h4_shadow_demo.py as a subprocess and asserts it
emits 2 h4_governance_shadow events with allowed=false, without touching
production audit logs or flipping modes. This ensures the 12-day runway
scaffold remains green in CI.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / 'scripts' / 'exercise_h4_shadow_demo.py'


def test_h4_shadow_demo_emits_two_denial_candidates(tmp_path: Path) -> None:
    output = tmp_path / 'h4_demo.jsonl'
    result = subprocess.run(
        [sys.executable, str(SCRIPT), '--output', str(output)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f'demo failed: {result.stdout}\n{result.stderr}'
    assert output.is_file(), 'demo did not create output'

    events = [
        json.loads(line) for line in output.read_text().splitlines() if line.strip()
    ]
    h4_events = [e for e in events if e.get('event_type') == 'h4_governance_shadow']
    assert len(h4_events) == 2, (
        f'expected 2 h4_governance_shadow, got {len(h4_events)}: {events}'
    )

    for event in h4_events:
        payload = event.get('payload', {})
        assert payload.get('allowed') is False, f'expected allowed=false: {payload}'
        assert payload.get('enforced') is False, (
            f'expected enforced=false (shadow): {payload}'
        )
        assert payload.get('mode') == 'shadow'
        assert payload.get('surface') in {'approval', 'subagent_launch'}

    # Also verify prepare_h4_evidence sees 2 candidates
    from teaagent.governance.h4_evidence import (
        build_h4_evidence_report,
        load_events_from_paths,
    )

    report = build_h4_evidence_report(
        load_events_from_paths([output]), since='2026-08-13', until='2026-09-11'
    )
    assert report.observed_events == 2
    assert len(report.candidates) == 2
    assert report.skipped_malformed == 0
    for cand in report.candidates:
        assert cand.owner_verdict is None
        assert cand.surface in {'approval', 'subagent_launch'}

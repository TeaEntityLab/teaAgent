from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from scripts.check_review_institution_gate import _touches_high_risk_paths


def test_ci_high_risk_classification_uses_shared_yaml(tmp_path: Path) -> None:
    config = tmp_path / 'high_risk_paths.yaml'
    config.write_text('patterns:\n  - "custom/security/**"\n', encoding='utf-8')

    assert _touches_high_risk_paths(['custom/security/gate.py'], config_path=config)
    assert not _touches_high_risk_paths(['teaagent/policy.py'], config_path=config)


def test_review_gate_runs_as_a_script() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    env = {
        **os.environ,
        'PR_BODY': ('Action: S-P2-4\nRisk class: low\nSelf-review checklist: complete'),
        'PR_NUMBER': '42',
        'PR_BASE_SHA': '',
        'PR_HEAD_SHA': 'HEAD',
    }

    result = subprocess.run(
        [sys.executable, 'scripts/check_review_institution_gate.py'],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert 'Review institution gates pass' in result.stdout

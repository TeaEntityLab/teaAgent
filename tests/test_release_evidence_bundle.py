from __future__ import annotations

import json
from pathlib import Path

from scripts.build_release_evidence_bundle import build_release_evidence_bundle


def test_release_evidence_bundle_counts_only_smoke(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    out = tmp_path / 'evidence.json'
    payload = build_release_evidence_bundle(
        repo_root=repo_root,
        output_path=out,
        run_profile='counts-only',
    )
    assert payload['ok'] is True
    assert payload['git']['commit']
    assert isinstance(payload['pytest_counts']['acceptance_collected'], int)
    assert isinstance(payload['pytest_counts']['suite_collected'], int)
    assert out.is_file()
    loaded = json.loads(out.read_text(encoding='utf-8'))
    assert loaded['git']['commit'] == payload['git']['commit']
